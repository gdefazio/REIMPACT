#!/usr/env/bin python3

"""
Citation overview system for bibliometric assessment relying on OpenAlex and Scopus 
"""
__author__ = ["Giuseppe Defazio", "Vincenzo Angiulli"]
__version__ = "2.0"

import sys
import os
import re
import logging
import time
import pyalex
import pybliometrics.scopus
from pybliometrics.scopus import CitationOverview
from functools import reduce
from datetime import datetime as dt
from typing import Optional, Dict, Mapping
import pandas as pd
import numpy as np
import argparse
import requests
from collections import deque
from urllib.parse import quote
from .utils.utils import (
    setup_logging,
    validate_file,
    validate_output_directory,
    sanitize_doi,
    choose_search_databases,
    ValidationError
)
# Optional dependency
try:
    import argcomplete
    ARGCOMPLETE_AVAILABLE = True
except ImportError:
    ARGCOMPLETE_AVAILABLE = False

# =============================
# LOGGING SETUP
# =============================
logger = logging.getLogger(__name__)

EXCEL_MAX_ROWS = 1048576
EXCEL_MAX_COLS = 16384

__all__ = [
    "OpenAlexDoi",
    "OpenAlexService",
    "MyCitationOverview",
    "MyCitationOverviewChunked"
]
# =============================
# ARGUMENT PARSING
# =============================
def parse_arguments() -> argparse.Namespace:
    """
    Parse and validate command line arguments for impact.

    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
            description="This script interrogates OpenAlex and Scopus APIs to obtain bibliometric features of papers related to ELIXIR IT services.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
    Basic usage:
        %(prog)s --input_excel input.xlsx --output ./results --openalex_key YOUR_OPENALEX_API_KEY --scopus_key YOUR_SCOPUS_API_KEY

    Skip Scopus (e.g., outside institutional network):
        %(prog)s --input_excel input.xlsx --output ./results --openalex_key YOUR_OPENALEX_API_KEY --skip_scopus
                """
        )

    # Input options
    input_group = parser.add_argument_group('Input Options')
    input_group.add_argument(
        "-i", "--input_excel",
        type=str,
        required=True,
        help="Path to the input Excel file.",
        metavar="FILE"
    )

    # Output options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument(
        "-o", "--output",
        type=str,
        default="./reimpact_results/REIMPACT.xlsx",
        help="Output Excel file name or full path (default: REIMPACT.xlsx in ./reimpact_results/)",
        metavar="FILE"
    )

    # API configuration
    api_group = parser.add_argument_group('API Configuration')
    api_group.add_argument(
        "-k", "--openalex_key",
        type=str,
        default=os.getenv('OPENALEX_API_KEY'),
        help="OpenAlex API key (required, or set OPENALEX_API_KEY env var)",
        metavar="OPENALEX_API_KEY"
    )
    api_group.add_argument(
        "-s", "--scopus_key",
        type=str,
        default=os.getenv('SCOPUS_API_KEY'),
        help="Scopus API key for pybliometrics. Can also set SCOPUS_API_KEY env var",
        metavar="SCOPUS_API_KEY"
    )

    # Behavior
    behavior_group = parser.add_argument_group('Behavior Options')
    behavior_group.add_argument(
        "--skip_scopus",
        action="store_true",
        help="Skip Scopus search (use when outside institutional network)"
    )
    behavior_group.add_argument(
        "--resume",
        action="store_true",
        help="Resume OpenAlex processing from existing checkpoints"
    )
    behavior_group.add_argument(
        "--openalex_data_version",
        type=int,
        choices=[1, 2],
        default=2,
        help="OpenAlex data version: 1=Classic (old), 2=Walden (new, default). See https://oreo.openalex.org/",
        metavar="VERSION"
    )
    behavior_group.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level)"
    )
    behavior_group.add_argument(
        "--log_file",
        type=str,
        default=None,
        help="Log file path (default: console only)",
        metavar="FILE"
    )

    if ARGCOMPLETE_AVAILABLE:
        argcomplete.autocomplete(parser)

    args = parser.parse_args()
    return args

# =============================
# OpenAlex
# =============================
_OPENALEX_SESSION = requests.Session()
_OPENALEX_RATE_LOG = deque(maxlen=200)
_OPENALEX_LAST_REQUEST_TS = 0.0
_OPENALEX_COOLDOWN_UNTIL = 0.0


def _safe_service_filename(service_name: str) -> str:
    """Return a filesystem-safe name for per-service checkpoint artifacts."""
    return re.sub(r"[/@)(]", "_", str(service_name))


def _openalex_checkpoint_dir(output_path: str) -> str:
    """Return checkpoint directory colocated with the output file."""
    output_dir = os.path.dirname(output_path) if os.path.dirname(output_path) else "."
    return os.path.join(output_dir, ".reimpact_checkpoints", "openalex")


def _openalex_summary_checkpoint_path(checkpoint_dir: str) -> str:
    """Path to OpenAlex summary checkpoint table."""
    return os.path.join(checkpoint_dir, "summary.tsv")


def _persist_openalex_summary_checkpoint(checkpoint_path: str, records: Dict[str, dict]) -> None:
    """Persist OpenAlex checkpoint rows atomically as TSV."""
    if not records:
        return
    df = pd.DataFrame(records.values())
    tmp_path = f"{checkpoint_path}.tmp"
    df.to_csv(tmp_path, sep='\t', index=False, encoding='utf-8')
    os.replace(tmp_path, checkpoint_path)


def _load_openalex_summary_checkpoint(checkpoint_path: str) -> Dict[str, dict]:
    """Load OpenAlex checkpoint rows keyed by service name."""
    if not os.path.exists(checkpoint_path):
        return {}
    try:
        ckpt_df = pd.read_csv(checkpoint_path, sep='\t', dtype=str)
        records: Dict[str, dict] = {}
        for _, row in ckpt_df.iterrows():
            service = str(row.get('service', '')).strip()
            if not service:
                continue
            citations = row.get('openalex_citations', None)
            citations_of_citing = row.get('openalex_citations_of_citing', None)
            records[service] = {
                'service': service,
                'applicant': row.get('applicant', ''),
                'platform': row.get('platform', ''),
                'status': row.get('status', ''),
                'openalex_citations': float(citations) if citations not in (None, '', 'nan') else np.nan,
                'openalex_citations_of_citing': float(citations_of_citing) if citations_of_citing not in (None, '', 'nan') else np.nan,
            }
        return records
    except Exception as exc:
        logger.warning(f"Unable to load OpenAlex checkpoint from {checkpoint_path}: {exc}")
        return {}


def _is_transient_openalex_error(exc: Exception) -> bool:
    """Return True for transient OpenAlex/network errors that are worth retrying."""
    msg = str(exc).lower()
    transient_signals = [
        "temporary failure in name resolution",
        "name resolution",
        "failed to resolve",
        "max retries exceeded",
        "connection aborted",
        "connection reset",
        "read timed out",
        "connect timeout",
        "too many requests",
        "429",
        "500",
        "502",
        "503",
        "504",
        "service unavailable",
    ]
    return any(signal in msg for signal in transient_signals)


def _openalex_base_params() -> Dict[str, str]:
    """Build common OpenAlex query params from environment."""
    params: Dict[str, str] = {}
    api_key = os.environ.get('OPENALEX_API_KEY')
    mailto = os.environ.get('OPENALEX_MAILTO')
    if api_key:
        params['api_key'] = api_key
    if mailto:
        params['mailto'] = mailto
    return params


def _openalex_min_interval_seconds() -> float:
    """Polite pacing between OpenAlex requests; stricter when no API key is configured."""
    return 0.25 if os.environ.get('OPENALEX_API_KEY') else 1.0


def _openalex_wait_slot() -> None:
    """Respect global pacing/cooldown before the next OpenAlex request."""
    global _OPENALEX_LAST_REQUEST_TS
    now = time.time()
    if _OPENALEX_COOLDOWN_UNTIL > now:
        time.sleep(_OPENALEX_COOLDOWN_UNTIL - now)
        now = time.time()
    wait = _openalex_min_interval_seconds() - (now - _OPENALEX_LAST_REQUEST_TS)
    if wait > 0:
        time.sleep(wait)
    _OPENALEX_LAST_REQUEST_TS = time.time()


def _openalex_parse_retry_after(headers: Mapping[str, str]) -> Optional[int]:
    """Return Retry-After (seconds) when provided and parseable."""
    retry_after = headers.get('Retry-After') if headers else None
    if not retry_after:
        return None
    try:
        return max(0, int(retry_after))
    except (TypeError, ValueError):
        return None


def _openalex_request_json(path: str, params: Optional[Dict[str, str]] = None, max_attempts: int = 6) -> dict:
    """Perform resilient OpenAlex JSON GET with retries for transient errors and 429."""
    global _OPENALEX_COOLDOWN_UNTIL
    url = f"https://api.openalex.org{path}"
    merged_params = _openalex_base_params()
    if params:
        merged_params.update(params)

    for attempt in range(1, max_attempts + 1):
        _openalex_wait_slot()
        try:
            response = _OPENALEX_SESSION.get(
                url,
                params=merged_params,
                headers={"Accept": "application/json", "User-Agent": "REIMPACT/2.0"},
                timeout=30,
            )
            _OPENALEX_RATE_LOG.append((time.time(), response.status_code))

            if response.status_code == 404:
                raise ValueError(f"OpenAlex resource not found: {path}")

            if response.status_code == 429:
                retry_after = _openalex_parse_retry_after(response.headers)
                delay = retry_after if retry_after is not None else max(5, 2 ** (attempt - 1))
                _OPENALEX_COOLDOWN_UNTIL = max(_OPENALEX_COOLDOWN_UNTIL, time.time() + delay)
                if attempt < max_attempts:
                    logger.warning(
                        "OpenAlex rate limit reached (429) on %s. Retrying in %ss (%s/%s).",
                        path,
                        delay,
                        attempt,
                        max_attempts,
                    )
                    continue
                raise ValueError(f"OpenAlex rate limit reached repeatedly (429) on {path}")

            if response.status_code in (500, 502, 503, 504):
                delay = max(2, 2 ** (attempt - 1))
                if attempt < max_attempts:
                    logger.warning(
                        "OpenAlex transient HTTP error %s on %s. Retrying in %ss (%s/%s).",
                        response.status_code,
                        path,
                        delay,
                        attempt,
                        max_attempts,
                    )
                    time.sleep(delay)
                    continue
                raise ValueError(f"OpenAlex HTTP error {response.status_code} on {path}")

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as exc:
            if attempt < max_attempts and _is_transient_openalex_error(exc):
                delay = max(1, 2 ** (attempt - 1))
                logger.warning(
                    "OpenAlex network error on %s: %s. Retrying in %ss (%s/%s).",
                    path,
                    exc,
                    delay,
                    attempt,
                    max_attempts,
                )
                time.sleep(delay)
                continue
            raise ValueError(f"OpenAlex request failed for {path}: {exc}") from exc

    raise ValueError(f"OpenAlex request failed after {max_attempts} attempts for {path}")


def _fetch_openalex_work_by_doi(cleaned_doi: str) -> dict:
    """Retrieve an OpenAlex work by DOI through resilient direct API calls."""
    encoded_doi = quote(cleaned_doi, safe='')
    data = _openalex_request_json(f"/works/https://doi.org/{encoded_doi}")
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected OpenAlex payload type for DOI {cleaned_doi}: {type(data)}")
    return data


def _write_dataframe_excel_chunked(
    writer: pd.ExcelWriter,
    df: pd.DataFrame,
    base_sheet_name: str,
    max_rows: int = EXCEL_MAX_ROWS,
) -> None:
    """Write a DataFrame to one or more Excel sheets, chunking by row limit when necessary."""
    if df is None or df.empty:
        return

    if df.shape[1] > EXCEL_MAX_COLS:
        raise ValueError(
            f"DataFrame has {df.shape[1]} columns, which exceeds the Excel column limit of {EXCEL_MAX_COLS}."
        )

    # Excel's row limit includes the header row, so reserve one row for column names.
    data_rows_per_sheet = max_rows - 1

    if len(df) <= data_rows_per_sheet:
        df.to_excel(writer, sheet_name=base_sheet_name, index=False)
        return

    total_chunks = (len(df) + data_rows_per_sheet - 1) // data_rows_per_sheet
    logger.warning(
        "DataFrame '%s' has %d rows and exceeds the Excel sheet limit (%d). Splitting into %d sheets.",
        base_sheet_name,
        len(df),
        max_rows,
        total_chunks,
    )
    for chunk_index, start in enumerate(range(0, len(df), data_rows_per_sheet), start=1):
        end = min(start + data_rows_per_sheet, len(df))
        chunk = df.iloc[start:end]
        sheet_name = f"{base_sheet_name}_{chunk_index}"
        if len(sheet_name) > 31:
            sheet_name = sheet_name[:31]
        chunk.to_excel(writer, sheet_name=sheet_name, index=False)


def _tsv_fallback_path(base_output_path: str, stem: str) -> str:
    """Return a lossless TSV fallback path next to the Excel output file."""
    base_dir = os.path.dirname(base_output_path)
    filename = f"{stem}.full.tsv"
    return os.path.join(base_dir, filename) if base_dir else filename


def _maybe_write_tsv_fallback(df: pd.DataFrame, excel_output_path: str, stem: str) -> None:
    """Write a full TSV fallback when the DataFrame exceeds Excel sheet limits."""
    if df is None or df.empty:
        return
    if len(df) <= (EXCEL_MAX_ROWS - 1) and df.shape[1] <= EXCEL_MAX_COLS:
        return

    tsv_path = _tsv_fallback_path(excel_output_path, stem)
    df.to_csv(tsv_path, sep='\t', index=False, encoding='utf-8')
    logger.warning(
        "DataFrame '%s' exceeds Excel limits (rows=%d, cols=%d). Excel is saved in chunks and a full TSV fallback was written to %s.",
        stem,
        len(df),
        df.shape[1],
        tsv_path,
    )


def _normalize_yearly_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize yearly citation columns before combining providers."""
    if df is None or df.empty:
        return df

    year_columns = {}
    provider = None
    for column in df.columns:
        column_name = str(column)
        if column_name.lower() == 'provider':
            if provider is None:
                provider = df[column]
            continue
        if re.fullmatch(r'\d{4}', column_name):
            year_columns.setdefault(column_name, []).append(df[column])

    normalized = pd.DataFrame(index=df.index)
    for year in sorted(year_columns, key=int):
        values = pd.concat(year_columns[year], axis=1)
        normalized[year] = values.bfill(axis=1).iloc[:, 0]
    if provider is not None:
        normalized['provider'] = provider
    return normalized

class OpenAlexDoi:
    def __init__(self, service, applicant, platform, doi) -> None:
        self.service = service
        self.applicant = applicant
        self.platform = platform
        # Clean DOI to handle URL-encoded strings
        cleaned_doi = sanitize_doi(doi)
        if not cleaned_doi:
            raise ValueError(f"Invalid DOI: {doi}")
        self.doi = cleaned_doi
        
        # DOI metadata retrieval through resilient direct OpenAlex API call.
        try:
            self.object = _fetch_openalex_work_by_doi(cleaned_doi)
        except ValueError as exc:
            if "not found" in str(exc).lower():
                raise ValueError(f"DOI not found in OpenAlex: {cleaned_doi}")
            raise
        except Exception as e:
            logger.error(f"Exception in OpenAlexDoi __init__: {e}")
            raise ValueError(f"Failed to retrieve DOI {cleaned_doi} from OpenAlex: {e}")

        self.citations = self.object.get('cited_by_count', 0)
        self.authors = pd.DataFrame(self.object.get('authorships', []))
        self.cit_by_years = pd.DataFrame(self.object.get('counts_by_year', []))

    def get_institutions(self) -> pd.DataFrame:
        melt_info = list()
        for i in range(0, self.authors.shape[0]):
            affil = self.authors.loc[i, 'raw_affiliation_strings'] if 'raw_affiliation_strings' in self.authors.columns else None
            # Only check len if affil is a list or str
            if affil is not None and (isinstance(affil, (list, str)) and len(affil) != 0):
                try:
                    insts = self.authors.loc[i, 'institutions'] if 'institutions' in self.authors.columns else []
                    if isinstance(insts, list) and len(insts) > 0 and isinstance(insts[-1], dict):
                        melt_info.append((insts[-1].get('display_name', np.nan), insts[-1].get('country_code', np.nan)))
                except Exception:
                    pass
        melt_info = set(melt_info)
        melt = pd.DataFrame(melt_info, columns=['institution', 'country'])
        melt['weight'] = self.citations
        melt['service'] = self.service
        melt['applicant'] = self.applicant
        melt['platform'] = self.platform
        melt['doi'] = self.doi
        return melt

    def get_citing_works_requests(self) -> tuple:
        """
        Extracts the works that cite this DOI using the OpenAlex API directly (requests), not pyalex.Works.
        Returns the sum of citations of the citing works and a DataFrame with their institutions.
        Returns:
            tuple: (total_citations_of_citings, citing_institutions_df)
                - total_citations_of_citings (int): Sum of citations of all citing works.
                - citing_institutions_df (pd.DataFrame): DataFrame with institutions of citing works' authors.
        """
        work_id = self.object.get('id', None)
        if not work_id:
            logger.debug("No OpenAlex work ID found for this DOI.")
            return None, None

        # Extract only the OpenAlex ID (e.g., W1234567890) from the URL if present
        openalex_id = work_id.split('/')[-1] if isinstance(work_id, str) and '/' in work_id else work_id
        logger.debug(f"work_id: {work_id} | openalex_id: {openalex_id}")

        # Use OpenAlex API directly
        params = {"filter": f"cites:{openalex_id}", "per-page": 200}
        page = 1
        total_cited_by = 0
        rows = []
        while True:
            params["page"] = page
            try:
                data = _openalex_request_json("/works", params=params)
            except ValueError as exc:
                logger.debug(f"OpenAlex API error while fetching citing works for DOI {self.doi}: {exc}")
                break
            results = data.get("results", [])
            if not results:
                break
            for work in results:
                cited_by_count = work.get('cited_by_count', 0)
                total_cited_by += cited_by_count
                doiOfIter = work.get('doi', None)
                for dict_author in work.get('authorships', []):
                    insts = dict_author.get('institutions', []) if isinstance(dict_author, dict) else []
                    if not insts or not isinstance(insts[0], dict):
                        continue
                    institution = insts[0].get('display_name', None)
                    country = insts[0].get('country_code', None)
                    if not institution or not country:
                        continue
                    if isinstance(institution, str) and not institution.strip():
                        continue
                    if isinstance(country, str) and not country.strip():
                        continue
                    row = {
                        'service': self.service,
                        'applicant': self.applicant,
                        'platform': self.platform,
                        'doi': self.doi,
                        'doiOfCiting': doiOfIter,
                        'institution': institution,
                        'country': country
                    }
                    rows.append(row)
            if len(results) < params["per-page"]:
                break
            page += 1
        logger.debug(f"Total citations of citings for DOI {self.doi}: {total_cited_by}")
        citing_df = pd.DataFrame(rows) if rows else None
        return total_cited_by if total_cited_by > 0 else (0 if citing_df is not None else None), citing_df

    def get_citing_works_pyalex(self, per_page: int = 200) -> tuple:
        """
        Extracts works citing this DOI using pyalex.Works().filter(cites=<openalex_id>).
        Returns the sum of citations of the citing works and a DataFrame with their institutions.

        Returns:
            tuple: (total_citations_of_citings, citing_institutions_df)
                - total_citations_of_citings (int): Sum of citations of all citing works.
                - citing_institutions_df (pd.DataFrame): DataFrame with institutions of citing works' authors.
        """
        work_id = self.object.get('id', None)
        if not work_id:
            logger.debug("No OpenAlex work ID found for this DOI.")
            return None, None

        openalex_id = work_id.split('/')[-1] if isinstance(work_id, str) and '/' in work_id else work_id
        logger.debug(f"work_id: {work_id} | openalex_id: {openalex_id} (pyalex)")

        api_key = os.environ.get('OPENALEX_API_KEY', None)
        if api_key:
            pyalex.config.api_key = api_key
        page = 1
        total_cited_by = 0
        rows = []
        while True:
            try:
                results = pyalex.Works().filter(cites=openalex_id).get(per_page=per_page, page=page)
            except Exception as e:
                logger.debug(f"pyalex citing-works retrieval error for DOI {self.doi}: {e}")
                break
            if not results:
                break
            for work in results:
                cited_by_count = work.get('cited_by_count', 0)
                total_cited_by += cited_by_count
                doi_of_iter = work.get('doi', None)

                for dict_author in work.get('authorships', []):
                    insts = dict_author.get('institutions', [])
                    if not insts or not isinstance(insts[0], dict):
                        continue
                    institution = insts[0].get('display_name', None)
                    country = insts[0].get('country_code', None)
                    if not institution or not country:
                        continue
                    if isinstance(institution, str) and not institution.strip():
                        continue
                    if isinstance(country, str) and not country.strip():
                        continue
                    row = {
                        'service': self.service,
                        'applicant': self.applicant,
                        'platform': self.platform,
                        'doi': self.doi,
                        'doiOfCiting': doi_of_iter,
                        'institution': institution,
                        'country': country
                    }
                    rows.append(row)
            if len(results) < per_page:
                break
            page += 1
        logger.debug(f"Total citations of citings for DOI {self.doi} (pyalex): {total_cited_by}")
        citing_df = pd.DataFrame(rows) if rows else None
        return total_cited_by if total_cited_by > 0 else (0 if citing_df is not None else None), citing_df

class OpenAlexService:
    def __init__(self, service, applicant, platform, doiString: str) -> None:
        self.service = service
        self.applicant = applicant
        self.platform = platform
        self.doiSplit = [el.strip() for el in doiString.split(',')]
        
        # Try each DOI individually and collect only successful ones
        self.openAlexDict = {}
        failed_dois = []

        for doi in self.doiSplit:
            doi = sanitize_doi(doi)
            try:
                self.openAlexDict[doi] = OpenAlexDoi(service, applicant, platform, doi)
            except Exception as e:
                logger.warning(f"{e}")
                failed_dois.append(doi)
        
        # If all DOIs failed, raise an error to stop processing this service
        if len(self.openAlexDict) == 0:
            if failed_dois:
                raise ValueError(f"All {len(failed_dois)} DOI(s) failed for service '{service}': {', '.join(failed_dois)}")
            else:
                raise ValueError(f"No valid DOIs found for service '{service}'")
        # If only some DOIs failed, log warning and continue
        if failed_dois:
            logger.warning(f"{len(failed_dois)}/{len(self.doiSplit)} DOI(s) skipped for '{service}'")
        
        self.citations = sum([el.citations for el in self.openAlexDict.values()])
        OfCiting = []
        for el in self.openAlexDict.values():
            try:
                OfCiting.append(el.get_citing_works_pyalex())
            except Exception as e:
                logger.debug(
                    f"pyalex citing-works retrieval failed for DOI {el.doi}: {e}. Falling back to requests-based retrieval."
                )
                OfCiting.append(el.get_citing_works_requests())
        self.citationsOfCiting = sum([el[0] for el in OfCiting if el[0] is not None])
        self.institutionsOfCiting = pd.concat(
            [el[1] for el in OfCiting if el[1] is not None],
            axis=0,
            ignore_index=True
        ) if any(el[1] is not None for el in OfCiting) else pd.DataFrame()
        if not self.institutionsOfCiting.empty:
            dedup_cols = [
                col for col in ['service', 'applicant', 'platform', 'doi', 'doiOfCiting', 'institution', 'country']
                if col in self.institutionsOfCiting.columns
            ]
            if dedup_cols:
                self.institutionsOfCiting = self.institutionsOfCiting.drop_duplicates(
                    subset=dedup_cols
                ).reset_index(drop=True)
        del OfCiting
        self.institutions = None
        try:
            self.institutions = pd.concat([el.get_institutions() for el in self.openAlexDict.values()],
                                          axis=0,
                                          ignore_index=True).drop_duplicates().reset_index(drop=True)
        except ValueError:
            logger.error("Error occurred while processing institutions for service '%s' and DOIs '%s'", service, doiString)
        if len(self.openAlexDict) > 1:
            citdf_list = []
            for doi, obj in self.openAlexDict.items():
                citdf = obj.cit_by_years
                if citdf.shape[0] > 0:
                    citdf.columns = ['year', doi]
                    citdf_list.append(citdf)
            self.mgd_citby_year = reduce(lambda x, y: x.merge(y, on='year', how='outer'), citdf_list)
        else:
            key = list(self.openAlexDict.keys())[0]
            self.mgd_citby_year = self.openAlexDict[key].cit_by_years
            self.mgd_citby_year.columns = ['year', key]
        self.mgd_citby_year.index = self.mgd_citby_year['year']
        self.mgd_citby_year.drop(['year'], axis=1, inplace=True)
        self.mgd_citby_year.fillna(0, inplace=True)
        self.mgd_citby_year = self.mgd_citby_year.T
        self.mgd_citby_year['provider'] = 'OpenAlex'

# =============================
# Scopus
# =============================
class MyCitationOverview(CitationOverview):
    def __init__(self, identifier, servname, apykey,
                 start=dt.now().timetuple()[0]-20,
                 end=dt.now().timetuple()[0],
                 id_type='doi'):
        date_range = f"{start}-{end}"
        try:
            super().__init__(identifier=identifier, date=date_range,
                             id_type=id_type,
                             apykey=apykey)
        except KeyError as e:
            # pybliometrics can raise KeyError('MyCitationOverview') when the runtime environment/package setup is inconsistent.
            if str(e).strip("'") == 'MyCitationOverview':
                raise RuntimeError(
                    "Scopus disabled: incompatible pybliometrics runtime detected "
                    "(KeyError: MyCitationOverview). Activate the correct environment "
                    "and ensure a compatible pybliometrics version is installed."
                ) from e
            raise
        self.start = start
        self.end = end
        self.servname = servname
    @property
    def grandTotal(self) -> int:
        return sum(self.rangeCount)
    @property
    def cit4year(self) -> pd.DataFrame:
        timeline_df = [[tx[1] for tx in el] for el in self.cc]
        timeline_df = pd.DataFrame(timeline_df)
        timeline_df.columns = range(self.start, self.end + 1)
        timeline_df.index = self.doi
        timeline_df['provider'] = 'Scopus'
        return timeline_df

class MyCitationOverviewChunked:
    """
    Wrapper to handle Scopus' 1-25 identifier limit by chunking the DOI list.
    - Splits the identifier list into chunks of 25 DOIs.
    - Builds a MyCitationOverview per chunk.
    - Exposes grandTotal as the sum across chunks and cit4year as the vertical concat.
    - Handles errors by trying DOIs individually to identify problematic ones.
    """
    def __init__(self, identifier, servname, apykey,
                 start, end, id_type='doi'):
        self._instances = []
        self._start = start
        self._end = end
        clean_ids = [el.strip() for el in identifier if el and el.strip()]
        import traceback
        for i in range(0, len(clean_ids), 25):
            chunk = clean_ids[i:i+25]
            if not chunk:
                continue
            try:
                inst = MyCitationOverview(
                    identifier=chunk,
                    servname=servname,
                    apykey=apykey,
                    start=start,
                    end=end,
                    id_type=id_type,
                )
                self._instances.append(inst)
            except Exception as e:
                if isinstance(e, RuntimeError) and 'Scopus disabled: incompatible pybliometrics runtime detected' in str(e):
                    raise
                error_name = type(e).__name__
                logger.debug(f"Chunk {i//25 + 1} failed with error: {error_name}: {e}\n{traceback.format_exc()}")

                for doi in chunk:
                    try:
                        inst = MyCitationOverview(
                            identifier=[doi],
                            servname=servname,
                            apykey=apykey,
                            start=start,
                            end=end,
                            id_type=id_type,
                        )
                        self._instances.append(inst)
                    except Exception as doi_error:
                        if isinstance(doi_error, RuntimeError) and 'Scopus disabled: incompatible pybliometrics runtime detected' in str(doi_error):
                            raise
                        if hasattr(pybliometrics.scopus, 'exception'):
                            if isinstance(doi_error, pybliometrics.scopus.exception.Scopus404Error):
                                logger.warning(f"DOI {doi}: Not found in Scopus (404)")
                            elif isinstance(doi_error, pybliometrics.scopus.exception.Scopus401Error) or isinstance(doi_error, pybliometrics.scopus.exception.Scopus403Error):
                                logger.error(f"DOI {doi}: Unauthorized access to Scopus (401/403). Check API key and network access.")
                        logger.debug(f"DOI {doi} failed with error: {type(doi_error).__name__}: {doi_error}\n{traceback.format_exc()}")
    @property
    def grandTotal(self) -> int:
        return int(sum(inst.grandTotal for inst in self._instances)) if self._instances else 0
    @property
    def cit4year(self) -> pd.DataFrame:
        if not self._instances:
            return pd.DataFrame(columns=range(self._start, self._end + 1))
        dfs = [inst.cit4year for inst in self._instances]
        return pd.concat(dfs, axis=0, ignore_index=False)

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
def main():
    try:
        args = parse_arguments()
        setup_logging(verbose=args.verbose, log_file=args.log_file)
        # Centralized API configuration and validation
        from .utils.utils import configure_apis
        err = configure_apis(args, logger=logger)
        if err:
            print(f"❌ {err}")
            return 1
        # Validate input Excel
        try:
            validate_file(args.input_excel)
            # Process output path: if it's just a filename, prepend default directory
            if os.path.dirname(args.output) == '':
                args.output = os.path.join(os.path.curdir, 'reimpact_results', args.output)
            if not args.output.endswith('.xlsx'):
                args.output = f"{args.output}.xlsx"
            output_dir = os.path.dirname(args.output)
            if output_dir:
                validate_output_directory(output_dir)
        except ValidationError as e:
            logger.error(f"Input validation error: {e}")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user\n")
        return 1
    except Exception as exc:
        print(f"\n❌ Error during initialization: {exc}\n")
        return 1
    # Header
    logger.info('''
################################################################################################
#                                                                                              #
#      CITATION OVERVIEW SYSTEM FOR BIBLIOMETRIC ASSESSMENT RELYING ON OPENALEX AND SCOPUS     #
#                                    POWERED BY ELIXIR-IIB                                     #
#                                                                                              #
################################################################################################
''')
    print('''\n=============================
  ⚙️  CONFIGURATION SUMMARY
=============================''')
    logger.info(f" Input excel file: {args.input_excel}")
    logger.info(f"📁 Output file: {args.output}")
    # Load input
    try:
        src = pd.read_excel(args.input_excel)
        if src.shape[1] < 4:
            logger.error(
                "Input Excel must have at least 4 columns in positional order: "
                "[Service, Applicant, Platform, Primary doi first then others]."
            )
            sys.exit(1)
        service_col = src.columns[0]
        applicant_col = src.columns[1]
        platform_col = src.columns[2]
        doi_col = src.columns[3]
        initial_rows = len(src)
        src = src[src[service_col].notna()]
        src = src[src[service_col].astype(str).str.strip() != ""]
        src = src[src[doi_col].notna()]
        src = src[src[doi_col].astype(str).str.strip() != ""]
        dropped_rows = initial_rows - len(src)
        if dropped_rows > 0:
            logger.warning(
                f"Dropped {dropped_rows} row(s): mandatory columns are first (service/author) and fourth (DOIs)."
            )
        if src.empty:
            logger.error(
                "No valid input rows found after enforcing mandatory first (service/author) "
                "and fourth (DOIs) columns."
            )
            sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to load input Excel: {e}")
        sys.exit(1)
    checkpoint_dir = _openalex_checkpoint_dir(args.output)
    checkpoint_summary_path = _openalex_summary_checkpoint_path(checkpoint_dir)
    openalex_ckpt_records: Dict[str, dict] = {}
    if args.resume:
        openalex_ckpt_records = _load_openalex_summary_checkpoint(checkpoint_summary_path)
        if openalex_ckpt_records:
            logger.info(f"Loaded OpenAlex checkpoint with {len(openalex_ckpt_records)} service(s): {checkpoint_summary_path}")
    else:
        logger.info("OpenAlex checkpoint resume disabled; processing all services from scratch.")

    # Prompt for database selection
    search_config = choose_search_databases(args)

    # OpenAlex processing
    if search_config['openalex']:
        logger.info('\n🔍  Starting OpenAlex information retrieval...')
        OpenAlexServiceDict = {}
        openalex_citations = []
        openalex_citations_of_citing = []
        openalex_any_success = False
        openalex_yearly_by_service = {}
        institutions_frames = []
        institutions_of_citing_frames = []
        checkpoint_services_dir = os.path.join(checkpoint_dir, "services")
        checkpoint_institutions_dir = os.path.join(checkpoint_dir, "institutions")
        checkpoint_citing_institutions_dir = os.path.join(checkpoint_dir, "institutions_of_citing")
        if args.resume:
            os.makedirs(checkpoint_services_dir, exist_ok=True)
            os.makedirs(checkpoint_institutions_dir, exist_ok=True)
            os.makedirs(checkpoint_citing_institutions_dir, exist_ok=True)
        
        for idx, row in src.iterrows():
            service = row[service_col]
            applicant = row[applicant_col]
            platform = row[platform_col]
            doi_string = row[doi_col]
            logger.info(f"\n📰 Processing service: {service}")

            service_key = str(service)
            safe_service = _safe_service_filename(service_key)
            yearly_ckpt_path = os.path.join(checkpoint_services_dir, f"{safe_service}.csv")
            inst_ckpt_path = os.path.join(checkpoint_institutions_dir, f"{safe_service}.tsv")
            inst_citing_ckpt_path = os.path.join(checkpoint_citing_institutions_dir, f"{safe_service}.tsv")

            existing = openalex_ckpt_records.get(service_key) if args.resume else None
            if existing and existing.get('status') == 'success' and os.path.exists(yearly_ckpt_path):
                try:
                    openalex_citations.append(existing.get('openalex_citations', np.nan))
                    openalex_citations_of_citing.append(existing.get('openalex_citations_of_citing', np.nan))
                    openalex_yearly_by_service[service_key] = pd.read_csv(yearly_ckpt_path, index_col=0)
                    if os.path.exists(inst_ckpt_path):
                        inst_df = pd.read_csv(inst_ckpt_path, sep='\t')
                        if not inst_df.empty:
                            institutions_frames.append(inst_df)
                    if os.path.exists(inst_citing_ckpt_path):
                        inst_citing_df = pd.read_csv(inst_citing_ckpt_path, sep='\t')
                        if not inst_citing_df.empty:
                            institutions_of_citing_frames.append(inst_citing_df)
                    openalex_any_success = True
                    logger.info(f"🧩 Loaded OpenAlex checkpoint for service: {service}")
                    continue
                except Exception as exc:
                    logger.warning(f"Checkpoint for service '{service}' is invalid/corrupted ({exc}). Recomputing.")

            try:
                service_obj = OpenAlexService(service, applicant, platform, doi_string)
                OpenAlexServiceDict[service_key] = service_obj
                openalex_citations.append(service_obj.citations)
                openalex_citations_of_citing.append(service_obj.citationsOfCiting)
                openalex_yearly_by_service[service_key] = service_obj.mgd_citby_year

                if service_obj.institutions is not None and not service_obj.institutions.empty:
                    institutions_frames.append(service_obj.institutions)
                if service_obj.institutionsOfCiting is not None and not service_obj.institutionsOfCiting.empty:
                    institutions_of_citing_frames.append(service_obj.institutionsOfCiting)

                if args.resume:
                    service_obj.mgd_citby_year.to_csv(yearly_ckpt_path)
                    if service_obj.institutions is not None and not service_obj.institutions.empty:
                        service_obj.institutions.to_csv(inst_ckpt_path, sep='\t', index=False, encoding='utf-8')
                    elif os.path.exists(inst_ckpt_path):
                        os.remove(inst_ckpt_path)

                    if service_obj.institutionsOfCiting is not None and not service_obj.institutionsOfCiting.empty:
                        service_obj.institutionsOfCiting.to_csv(inst_citing_ckpt_path, sep='\t', index=False, encoding='utf-8')
                    elif os.path.exists(inst_citing_ckpt_path):
                        os.remove(inst_citing_ckpt_path)

                    openalex_ckpt_records[service_key] = {
                        'service': service_key,
                        'applicant': str(applicant),
                        'platform': str(platform),
                        'status': 'success',
                        'openalex_citations': service_obj.citations,
                        'openalex_citations_of_citing': service_obj.citationsOfCiting,
                    }
                    _persist_openalex_summary_checkpoint(checkpoint_summary_path, openalex_ckpt_records)
                openalex_any_success = True
                logger.info(f"\r📰 Processing service: {service} ✅")
            except Exception as e:
                logger.warning(f"OpenAlex retrieval failed for service '{service}': {e}")
                OpenAlexServiceDict[service_key] = None
                openalex_citations.append(np.nan)
                openalex_citations_of_citing.append(np.nan)
                if args.resume:
                    openalex_ckpt_records[service_key] = {
                        'service': service_key,
                        'applicant': str(applicant),
                        'platform': str(platform),
                        'status': 'failed',
                        'openalex_citations': np.nan,
                        'openalex_citations_of_citing': np.nan,
                    }
                    _persist_openalex_summary_checkpoint(checkpoint_summary_path, openalex_ckpt_records)

        if not openalex_any_success and not search_config.get('scopus', False):
            logger.error("Stopping execution: OpenAlex is unavailable and no other database is selected.")
            return 1
        
        logger.info('\n🔍  Starting OpenAlex citations data elaboration...')
        src['OpenAlexCitations'] = openalex_citations
        logger.info('\n🔍  Starting OpenAlex impact data elaboration...')
        src['OpenAlexCitationsOfCiting'] = openalex_citations_of_citing
        
        # Collect institutions from live retrieval and checkpoints.
        institutions = pd.concat(institutions_frames, axis=0, ignore_index=True) if institutions_frames else pd.DataFrame()

        institutionsOfCitings = pd.concat(institutions_of_citing_frames, axis=0, ignore_index=True) if institutions_of_citing_frames else pd.DataFrame()
        if not institutionsOfCitings.empty:
            dedup_cols = [
                col for col in ['service', 'applicant', 'platform', 'doi', 'doiOfCiting', 'institution', 'country']
                if col in institutionsOfCitings.columns
            ]
            if dedup_cols:
                institutionsOfCitings = institutionsOfCitings.drop_duplicates(
                    subset=dedup_cols
                ).reset_index(drop=True)
    else:
        OpenAlexServiceDict = {}
        openalex_yearly_by_service = {}
        src = src.drop(columns=['OpenAlexCitations', 'OpenAlexCitationsOfCiting'], errors='ignore')
        institutions = pd.DataFrame()
        institutionsOfCitings = pd.DataFrame()
    
    # Scopus processing
    scopus_failed = False
    if search_config['scopus']:
        logger.info('\n🔍  Starting Scopus information retrieval...')
        PyBlioInstanceDict = {}
        pyblio_citations = []
        scopus_env_mismatch = False
        _scopus_start = dt.now().timetuple()[0] - 20
        _scopus_end = dt.now().timetuple()[0]
        try:
            for idx, row in src.iterrows():
                service = row[service_col]
                doi_string = row[doi_col]
                identifiers = [el.strip() for el in str(doi_string).split(',') if el and el.strip()]
                try:
                    inst = MyCitationOverviewChunked(
                        servname=service,
                        identifier=identifiers,
                        start=_scopus_start,
                        end=_scopus_end,
                        id_type='doi',
                        apykey=args.scopus_key,
                    )
                    PyBlioInstanceDict[service] = inst
                    pyblio_citations.append(inst.grandTotal)
                    logger.debug(f"✅ Successfully processed Scopus: {service}")
                except Exception as exc:
                    if isinstance(exc, RuntimeError) and 'Scopus disabled: incompatible pybliometrics runtime detected' in str(exc):
                        logger.error(str(exc))
                        scopus_env_mismatch = True
                        break
                    logger.warning(f"⚠️  Scopus retrieval failed for service '{service}': {exc}")
                    PyBlioInstanceDict[service] = None
                    pyblio_citations.append(np.nan)
            if scopus_env_mismatch:
                scopus_failed = True
                if not search_config.get('openalex', False):
                    logger.error("Stopping execution: Scopus is unavailable and no other database is selected.")
                    return 1
            else:
                src['PyBlioCitations'] = pyblio_citations
        except Exception as exc:
            logger.error(f"❌ Scopus block failed: {exc}. Will save only OpenAlex results.")
            scopus_failed = True
    else:
        PyBlioInstanceDict = {}

    logger.info('\n🗃️  Starting overall data storage...')
    # Create output directory from the file path
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # If Scopus failed, drop the column if present
    if scopus_failed and 'PyBlioCitations' in src.columns:
        src = src.drop(columns=['PyBlioCitations'])
    
    # Write Excel file
    with pd.ExcelWriter(args.output) as buf:
        _write_dataframe_excel_chunked(buf, src, 'summary')
        if not institutions.empty:
            _write_dataframe_excel_chunked(buf, institutions, 'institutions')
        if not institutionsOfCitings.empty:
            _write_dataframe_excel_chunked(buf, institutionsOfCitings, 'institutionsOfCitings')

    _maybe_write_tsv_fallback(src, args.output, 'summary')
    _maybe_write_tsv_fallback(institutions, args.output, 'institutions')
    _maybe_write_tsv_fallback(institutionsOfCitings, args.output, 'institutionsOfCitings')
    
    logger.info('\n🗃️  Starting service-specific data storage...')
    # Create services directory in the same directory as the output file
    services_dir = os.path.join(output_dir if output_dir else '.', "services")
    os.makedirs(services_dir, exist_ok=True)
    for k, yearly_df in openalex_yearly_by_service.items():
        if not scopus_failed and search_config['scopus'] and k in PyBlioInstanceDict and PyBlioInstanceDict[k] is not None:
            scopus_df = PyBlioInstanceDict[k].cit4year
            openalex_df = yearly_df
            # Only concat if both have data to avoid FutureWarning
            if not scopus_df.empty and not openalex_df.empty:
                aux = pd.concat([scopus_df, openalex_df], axis=0)
            elif not scopus_df.empty:
                aux = scopus_df
            else:
                aux = openalex_df
        else:
            aux = yearly_df
        aux = _normalize_yearly_dataframe(aux)
        aux.fillna(0, inplace=True)
        aux.to_csv(os.path.join(services_dir, _safe_service_filename(k) + ".csv"))

    logger.info(f"\n✅ All data saved successfully to {args.output}")
    logger.info(f"\n✅ Service-specific data saved to {services_dir}")
    logger.info('\n✅ Finished...Good bye 👋')

    return 0

if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code if exit_code is not None else 0)
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user\n")
        sys.exit(130)  # Standard exit code for SIGINT
    except Exception as exc:
        print(f"\n❌ Fatal error: {exc}\n")
        sys.exit(1)
