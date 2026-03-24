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
import pyalex
import pybliometrics.scopus
from pybliometrics.scopus import CitationOverview
from functools import reduce
from datetime import datetime as dt
from typing import Optional
import pandas as pd
import numpy as np
import argparse
import requests
from collections import deque
from .utils.utils import (
    setup_logging,
    validate_file,
    validate_output_directory,
    sanitize_doi,
    get_available_databases,
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
        required=True,
        default=os.getenv('OPENALEX_API_KEY'),
        help="OpenAlex API key (required, or set OPENALEX_API_KEY env var)",
        metavar="OPENALEX_API_KEY"
    )
    api_group.add_argument(
        "--openalex_data_version",
        type=int,
        choices=[1, 2],
        default=2,
        help="OpenAlex data version: 1=Classic (old), 2=Walden (new, default). See https://oreo.openalex.org/",
        metavar="VERSION"
    )
    api_group.add_argument(
        "-s", "--scopus_key",
        type=str,
        default=os.getenv('SCOPUS_API_KEY'),
        help="Scopus API key for pybliometrics. Can also set SCOPUS_API_KEY env var",
        metavar="SCOPUS_API_KEY"
    )

    # Behavior
    behavior_group = parser.add_argument_group('Behavior')
    behavior_group.add_argument(
        "--skip_scopus",
        action="store_true",
        help="Skip Scopus search (use when outside institutional network)"
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
        argcomplete.autocomplete(parser)  # type: ignore

    args = parser.parse_args()

    # Validation
    if not args.openalex_key:
        parser.error("You must provide an OpenAlex API key (-a).")
    if not args.skip_scopus and not args.scopus_key:
        parser.error("Scopus API key (-s) is required unless --skip_scopus is specified.")

    return args

# =============================
# OpenAlex
# =============================
_OPENALEX_SESSION = requests.Session()
_OPENALEX_RATE_LOG = deque(maxlen=200)

class OpenAlexDoi:
    def __init__(self, service, platform, doi) -> None:
        self.service = service
        self.platform = platform
        # Clean DOI to handle URL-encoded strings
        cleaned_doi = sanitize_doi(doi)
        if not cleaned_doi:
            raise ValueError(f"Invalid DOI: {doi}")
        self.doi = cleaned_doi
        
        # Direct access using DOI URL (original logic)
        try:
            obj = pyalex.Works()[f"https://doi.org/{cleaned_doi}"]
            logger.debug(f"pyalex.Works() returned type: {type(obj)}; repr: {repr(obj)}")
            # pyalex may return OpenAlexResponseList, tuple, list, or dict. Always get dict.
            if isinstance(obj, dict):
                self.object = obj
            elif type(obj).__name__ == 'OpenAlexResponseList' and hasattr(obj, '__len__') and len(obj) > 0 and isinstance(obj[0], dict):
                self.object = obj[0]
            elif isinstance(obj, (list, tuple)) and len(obj) > 0 and isinstance(obj[0], dict):
                self.object = obj[0]
            else:
                logger.error(f"pyalex.Works() returned unexpected type: {type(obj)}; repr: {repr(obj)}")
                raise TypeError(f"pyalex.Works() did not return a dict for DOI {cleaned_doi}. Type: {type(obj)}. See logs for details.")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise ValueError(f"DOI not found in OpenAlex: {cleaned_doi}")
            else:
                raise ValueError(f"OpenAlex HTTP error {e.response.status_code} for DOI {cleaned_doi}: {e}")
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Network error retrieving DOI {cleaned_doi} from OpenAlex: {e}")
        except KeyError as e:
            raise ValueError(f"DOI not found in OpenAlex: {cleaned_doi}")
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
        melt['platform'] = self.platform
        melt['doi'] = self.doi
        return melt

    def get_citing_works(self) -> tuple:
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
        api_key = os.environ.get('OPENALEX_API_KEY', None)
        headers = {"Accept": "application/json"}
        params = {"filter": f"cites:{openalex_id}", "per-page": 200}
        if api_key:
            params["api_key"] = api_key
        page = 1
        total_cited_by = 0
        rows = []
        while True:
            params["page"] = page
            response = requests.get("https://api.openalex.org/works", headers=headers, params=params)
            if response.status_code != 200:
                logger.debug(f"OpenAlex API error {response.status_code}: {response.text}")
                break
            data = response.json()
            results = data.get("results", [])
            if not results:
                break
            for work in results:
                cited_by_count = work.get('cited_by_count', 0)
                total_cited_by += cited_by_count
                doiOfIter = work.get('doi', None)
                for dict_author in work.get('authorships', []):
                    row = {
                        'service': self.service,
                        'platform': self.platform,
                        'doi': self.doi,
                        'doiOfCiting': doiOfIter,
                        'institution': dict_author['institutions'][0]['display_name'] if dict_author['institutions'] else np.nan,
                        'country': dict_author['institutions'][0]['country_code'] if dict_author['institutions'] else np.nan
                    }
                    rows.append(row)
            if len(results) < params["per-page"]:
                break
            page += 1
        logger.debug(f"Total citations of citings for DOI {self.doi}: {total_cited_by}")
        citing_df = pd.DataFrame(rows) if rows else None
        return total_cited_by if total_cited_by > 0 else (0 if citing_df is not None else None), citing_df

class OpenAlexService:
    def __init__(self, service, platform, doiString: str) -> None:
        self.service = service
        self.platform = platform
        self.doiSplit = [el.strip() for el in doiString.split(',')]
        
        # Try each DOI individually and collect only successful ones
        self.openAlexDict = {}
        failed_dois = []

        for doi in self.doiSplit:
            doi = sanitize_doi(doi)
            try:
                self.openAlexDict[doi] = OpenAlexDoi(service, platform, doi)
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
        OfCiting = [el.get_citing_works() for el in self.openAlexDict.values()]
        self.citationsOfCiting = sum([el[0] for el in OfCiting if el[0] is not None])
        self.institutionsOfCiting = pd.concat([el[1] for el in OfCiting if el[1] is not None], axis=0) if any(el[1] is not None for el in OfCiting) else pd.DataFrame()
        del OfCiting
        self.institutions = None
        try:
            self.institutions = pd.concat([el.get_institutions() for el in self.openAlexDict.values()],
                                          axis=0,
                                          ignore_index=True).drop_duplicates().reset_index(drop=True)
        except ValueError:
            print(service, doiString)
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
        super().__init__(identifier=identifier, date=date_range,
                         id_type=id_type,
                         apykey=apykey)
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
        src = src[~src['Primary doi first then others'].isna()]
    except Exception as e:
        logger.error(f"Failed to load input Excel: {e}")
        sys.exit(1)
    # Prompt for database selection
    search_config = choose_search_databases(args.skip_scopus)

    # OpenAlex processing
    if search_config['openalex']:
        logger.info('\n🔍  Starting OpenAlex information retrieval...')
        OpenAlexServiceDict = {}
        openalex_citations = []
        openalex_citations_of_citing = []
        
        for idx, row in src.iterrows():
            service = row['Service']
            logger.info(f"\n📰 Processing service: {service}")
            platform = row['Platform']
            doi_string = row['Primary doi first then others']
            
            try:
                service_obj = OpenAlexService(service, platform, doi_string)
                OpenAlexServiceDict[service] = service_obj
                openalex_citations.append(service_obj.citations)
                openalex_citations_of_citing.append(service_obj.citationsOfCiting)
                logger.info(f"\r📰 Processing service: {service} ✅")
            except Exception as e:
                logger.warning(f"OpenAlex retrieval failed for service '{service}': {e}")
                OpenAlexServiceDict[service] = None
                openalex_citations.append(np.nan)
                openalex_citations_of_citing.append(np.nan)
        
        logger.info('\n🔍  Starting OpenAlex citations data elaboration...')
        src['OpenAlexCitations'] = openalex_citations
        logger.info('\n🔍  Starting OpenAlex impact data elaboration...')
        src['OpenAlexCitationsOfCiting'] = openalex_citations_of_citing
        
        # Collect institutions only from successful retrievals
        institutions = pd.concat(
            [el.institutions for el in OpenAlexServiceDict.values() 
             if el is not None and el.institutions is not None], 
            axis=0, 
            ignore_index=True
        ) if any(el is not None and el.institutions is not None for el in OpenAlexServiceDict.values()) else pd.DataFrame()
        
        institutionsOfCitings = pd.concat(
            [el.institutionsOfCiting for el in OpenAlexServiceDict.values() 
             if el is not None and el.institutionsOfCiting is not None and not el.institutionsOfCiting.empty], 
            axis=0
        ) if any(el is not None and el.institutionsOfCiting is not None and not el.institutionsOfCiting.empty for el in OpenAlexServiceDict.values()) else pd.DataFrame()
    else:
        OpenAlexServiceDict = {}
        src['OpenAlexCitations'] = np.nan
        src['OpenAlexCitationsOfCiting'] = np.nan
        institutions = pd.DataFrame()
        institutionsOfCitings = pd.DataFrame()
    
    # Scopus processing
    scopus_failed = False
    if search_config['scopus']:
        logger.info('\n🔍  Starting Scopus information retrieval...')
        PyBlioInstanceDict = {}
        pyblio_citations = []
        _scopus_start = dt.now().timetuple()[0] - 20
        _scopus_end = dt.now().timetuple()[0]
        try:
            for idx, row in src.iterrows():
                service = row['Service']
                doi_string = row['Primary doi first then others']
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
                    logger.warning(f"⚠️  Scopus retrieval failed for service '{service}': {exc}")
                    PyBlioInstanceDict[service] = None
                    pyblio_citations.append(np.nan)
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
        src.to_excel(buf, sheet_name='summary')
        if not institutions.empty:
            institutions.to_excel(buf, sheet_name='institutions')
        if not institutionsOfCitings.empty:
            institutionsOfCitings.to_excel(buf, sheet_name='institutionsOfCitings')
    
    logger.info('\n🗃️  Starting service-specific data storage...')
    # Create services directory in the same directory as the output file
    services_dir = os.path.join(output_dir if output_dir else '.', "services")
    os.makedirs(services_dir, exist_ok=True)
    for k, df in OpenAlexServiceDict.items():
        if df is None:
            logger.warning(f"Skipping {k} (failed during retrieval)")
            continue
        if not scopus_failed and search_config['scopus'] and k in PyBlioInstanceDict and PyBlioInstanceDict[k] is not None:
            scopus_df = PyBlioInstanceDict[k].cit4year
            openalex_df = df.mgd_citby_year
            # Only concat if both have data to avoid FutureWarning
            if not scopus_df.empty and not openalex_df.empty:
                aux = pd.concat([scopus_df, openalex_df], axis=0)
            elif not scopus_df.empty:
                aux = scopus_df
            else:
                aux = openalex_df
        else:
            aux = df.mgd_citby_year
        aux.fillna(0, inplace=True)
        aux.to_csv(os.path.join(services_dir, re.sub(r"[/@)(]", "_", k) + ".csv"))

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
