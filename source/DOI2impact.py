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
from utils.utils import setup_logging, validate_email, validate_file, validate_output_directory, validate_api_key, ValidationError
# Optional dependency
try:
    import argcomplete
    ARGCOMPLETE_AVAILABLE = True
except ImportError:
    ARGCOMPLETE_AVAILABLE = False

# =============================
# ARGUMENT PARSING
# =============================
def parse_arguments() -> argparse.Namespace:
    """
    Parse and validate command line arguments for DOI2impact.

    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="This script interrogates OpenAlex and Scopus APIs to obtain bibliometric features of papers related to ELIXIR IT services.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Basic usage:
    %(prog)s -i input.xlsx -o ./results --openalex_mailto email@domain.com --scopus_key KEY

  Skip Scopus (e.g., outside institutional network):
    %(prog)s -i input.xlsx --skip_scopus --openalex_mailto email@domain.com
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
        "-o", "--output_directory",
        type=str,
        default="./impact_results",
        help="Output directory (default: ./impact_results)",
        metavar="DIR"
    )

    # API configuration
    api_group = parser.add_argument_group('API Configuration')
    api_group.add_argument(
        "-a", "--openalex_key",
        type=str,
        default=os.getenv('OPENALEX_API_KEY'),
        help="OpenAlex API key (optional, can also set OPENALEX_API_KEY env var)",
        metavar="KEY"
    )
    api_group.add_argument(
        "-m", "--openalex_mailto",
        type=str,
        default=os.getenv('OPENALEX_MAILTO'),
        help="Contact email for OpenAlex polite pool (REQUIRED if no API key, recommended always). Can also set openalex_mailto env var",
        metavar="EMAIL"
    )
    api_group.add_argument(
        "-s", "--scopus_key",
        type=str,
        default=os.getenv('SCOPUS_API_KEY'),
        help="Scopus API key for pybliometrics. Can also set SCOPUS_API_KEY env var",
        metavar="KEY"
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
    if not args.openalex_key and not args.openalex_mailto:
        parser.error("You must provide either an OpenAlex API key (-a) or an email (-m) for polite pool access.")
    if not args.skip_scopus and not args.scopus_key:
        parser.error("Pybliometrics API key (-s) is required unless --skip_scopus is specified.")

    return args

# =============================
# DATABASE SELECTION PROMPT
# =============================
def choose_search_databases(skip_scopus_flag: bool) -> dict:
    """
    Prompt user to select which databases to use, unless skip_scopus is set.
    Returns: dict with 'openalex' and 'scopus' boolean flags
    """
    if skip_scopus_flag:
        # print("Scopus search will be skipped (--skip_scopus set). Using only OpenAlex.")
        return {'openalex': True, 'scopus': False}
    print("\n==============================")
    print("     🗃️  DATABASE SELECTION")
    print("==============================")
    print("Where do you want to search for citations?")
    print("  [1] OpenAlex only")
    print("  [2] Scopus only")
    print("  [3] Both OpenAlex and Scopus")
    while True:
        choice = input("Enter your choice (1-3): ").strip()
        if choice == '1':
            return {'openalex': True, 'scopus': False}
        elif choice == '2':
            return {'openalex': False, 'scopus': True}
        elif choice == '3':
            return {'openalex': True, 'scopus': True}
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

# --- OpenAlex ---
_OPENALEX_SESSION = requests.Session()
_OPENALEX_RATE_LOG = deque(maxlen=200)

class OpenAlexDoi:
    def __init__(self, service, platform, doi) -> None:
        self.service = service
        self.platform = platform
        self.doi = doi
        self.object = pyalex.Works()[f"https://doi.org/{doi}"]
        self.citations = self.object['cited_by_count']
        self.authors = pd.DataFrame(self.object['authorships'])
        self.cit_by_years = pd.DataFrame(self.object['counts_by_year'])

    def get_institutions(self) -> pd.DataFrame:
        melt_info = list()
        for i in range(0, self.authors.shape[0]):
            if len(self.authors.loc[i, 'raw_affiliation_strings']) != 0:
                try:
                    melt_info.append((self.authors.loc[i, 'institutions'][-1]['display_name'],
                                      self.authors.loc[i, 'institutions'][-1]['country_code']))
                except IndexError:
                    pass
        melt_info = set(melt_info)
        melt = pd.DataFrame(melt_info, columns=['institution', 'country'])
        melt['weight'] = self.citations
        melt['service'] = self.service
        melt['platform'] = self.platform
        melt['doi'] = self.doi
        return melt

    def get_citing_works(self) -> tuple:
        cited_by_url = self.object.get('cited_by_api_url')
        if not cited_by_url:
            return None, None
        per_page = 200
        total_cited_by = 0
        rows = []
        page = 1
        while True:
            params = {"page": page, "per-page": per_page}
            ans = requests.get(cited_by_url, params=params)
            if ans.status_code != 200:
                break
            j_ans = ans.json()
            results = j_ans.get('results', [])
            if not results:
                break
            df = pd.DataFrame(results)
            for i in df.index:
                el = df.loc[i, 'authorships']
                doiOfIter = df.loc[i, 'doi']
                for dict_author in el:
                    row = {
                        'service': self.service,
                        'platform': self.platform,
                        'doi': self.doi,
                        'doiOfCiting': doiOfIter,
                        'institution': dict_author['institutions'][0]['display_name'] if dict_author['institutions'] else np.nan,
                        'country': dict_author['institutions'][0]['country_code'] if dict_author['institutions'] else np.nan
                    }
                    rows.append(row)
            total_cited_by += df['cited_by_count'].sum() if 'cited_by_count' in df else 0
            if len(results) < per_page:
                break
            page += 1
        citing_df = pd.DataFrame(rows) if rows else None
        total_cited_by = total_cited_by or None
        return total_cited_by, citing_df

class OpenAlexService:
    def __init__(self, service, platform, doiString: str) -> None:
        self.service = service
        self.platform = platform
        self.doiSplit = [el.strip() for el in doiString.split(',')]
        self.openAlexDict = {doi: OpenAlexDoi(service, platform, doi) for doi in self.doiSplit}
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

# --- Scopus ---

# --- Scopus chunked logic ---
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
    """Wrapper to handle Scopus' 1-25 identifier limit by chunking the DOI list.
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
                logging.getLogger(__name__).debug(f"Chunk {i//25 + 1} failed with error: {error_name}: {e}")
                # Try DOIs individually to identify problematic ones
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
                        logging.getLogger(__name__).debug(f"DOI {doi}: Not found in Scopus - {type(doi_error).__name__}")
                        # Continue without this DOI
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
        logger = logging.getLogger(__name__)

        # Validate inputs
        try:
            validate_file(args.input_excel)
            validate_output_directory(args.output_directory)
            if args.openalex_mailto:
                validate_email(args.openalex_mailto)
            if not args.skip_scopus:
                if not args.scopus_key:
                    raise ValidationError("Pybliometrics API key is required unless --skip_scopus is specified.")
                validate_api_key(args.scopus_key, key_name="Pybliometrics API key")
            if args.openalex_key:
                validate_api_key(args.openalex_key, key_name="OpenAlex API key")
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

    # Configuration
    print('''\n==============================
    ⚙️  CONFIGURATION SUMMARY
==============================''')
    if args.openalex_key:
        pyalex.config.api_key = args.openalex_key
        logger.info("✅ OpenAlex: API key (100k requests/day)")
    else:
        logger.info("✅ OpenAlex: Polite pool (10 req/s)")
    
    if args.openalex_mailto:
        pyalex.config.mailto = args.openalex_mailto
        logger.info(f"📧 Email: {args.openalex_mailto}")
    else:
        logger.warning("⚠️  No mailto provided")
        if not args.openalex_key:
            logger.error("❌ Need API key OR mailto for OpenAlex")
            logger.info("💡 Set OPENALEX_API_KEY or OPENALEX_MAILTO environment variable\n")
            return 1

    # Scopus configuration
    if args.skip_scopus:
        logger.info("⏭️  Scopus search will be skipped (--skip_scopus set). Using only OpenAlex.")
    elif args.scopus_key:
        try:
            logging.info("Scopus: Configuring API key...")
            pybliometrics.scopus.create_config(keys=[args.scopus_key]) # type: ignore
            pybliometrics.scopus.init() # type: ignore
            logger.info("✅ Scopus: API key configured")
        except Exception as exc:
            logger.error(f"❌ Scopus configuration failed: {exc}")    
    logger.info(f"📄 Input excel file: {args.input_excel}")
    logger.info(f"📁 Output directory: {args.output_directory}")

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
    zinput = zip(src['Service'], src['Platform'], src['Primary doi first then others'])
    if search_config['openalex']:
        logger.info('\n🔍Starting OpenAlex information retrieval...')
        OpenAlexServiceDict = {x: OpenAlexService(x, y, z) for x, y, z in zinput}
        logger.info('\n🔍   Starting OpenAlex citations data elaboration...')
        src['OpenAlexCitations'] = [el.citations for el in OpenAlexServiceDict.values()]
        logger.info('\n🔍   Starting OpenAlex impact data elaboration...')
        src['OpenAlexCitationsOfCiting'] = [el.citationsOfCiting for el in OpenAlexServiceDict.values()]
        institutions = pd.concat([el.institutions for el in OpenAlexServiceDict.values() if el.institutions is not None], axis=0, ignore_index=True)
        institutionsOfCitings = pd.concat([el.institutionsOfCiting for el in OpenAlexServiceDict.values() if el.institutionsOfCiting is not None], axis=0)
    else:
        OpenAlexServiceDict = {}
        src['OpenAlexCitations'] = np.nan
        src['OpenAlexCitationsOfCiting'] = np.nan
        institutions = pd.DataFrame()
        institutionsOfCitings = pd.DataFrame()

    zinput = zip(src['Service'], src['Primary doi first then others'])
    scopus_failed = False
    if search_config['scopus']:
        logger.info('\n🔍   Starting Scopus information retrieval...')
        PyBlioInstanceDict = {}
        pyblio_citations = []
        _scopus_start = dt.now().timetuple()[0] - 20
        _scopus_end = dt.now().timetuple()[0]
        try:
            for a, b in zinput:
                identifiers = [el.strip() for el in str(b).split(',') if el and el.strip()]
                try:
                    inst = MyCitationOverviewChunked(
                        servname=a,
                        identifier=identifiers,
                        start=_scopus_start,
                        end=_scopus_end,
                        id_type='doi',
                        apykey=args.scopus_key,
                    )
                    PyBlioInstanceDict[a] = inst
                    pyblio_citations.append(inst.grandTotal)
                except Exception as exc:
                    logger.warning(f"Scopus retrieval failed for service '{a}': {exc}")
                    PyBlioInstanceDict[a] = None
                    pyblio_citations.append(np.nan)
            src['PyBlioCitations'] = pyblio_citations
        except Exception as exc:
            logger.error(f"Scopus block failed: {exc}. Will save only OpenAlex results.")
            scopus_failed = True
    else:
        PyBlioInstanceDict = {}
        src['PyBlioCitations'] = np.nan

    logger.info('\n🗃️   Starting overall data storage...')
    os.makedirs(args.output_directory, exist_ok=True)
    # If Scopus failed, drop the column if present
    if scopus_failed and 'PyBlioCitations' in src.columns:
        src = src.drop(columns=['PyBlioCitations'])
    with pd.ExcelWriter(os.path.join(args.output_directory, 'ELIXIR.IT_IMPACT.xlsx')) as buf:
        src.to_excel(buf, sheet_name='summary')
        if not institutions.empty:
            institutions.to_excel(buf, sheet_name='institutions')
        if not institutionsOfCitings.empty:
            institutionsOfCitings.to_excel(buf, sheet_name='institutionsOfCitings')
    logger.info('\n🗃️   Starting service-specific data storage...')
    dir_services = os.path.join(args.output_directory, "services")
    os.makedirs(dir_services, exist_ok=True)
    for k, df in OpenAlexServiceDict.items():
        logger.info(f"Processing {k}")
        if not scopus_failed and search_config['scopus'] and k in PyBlioInstanceDict:
            aux = pd.concat([PyBlioInstanceDict[k].cit4year, df.mgd_citby_year], axis=0)
        else:
            aux = df.mgd_citby_year
        aux.replace(np.nan, 0, inplace=True)
        aux.to_csv(os.path.join(dir_services, re.sub(r"[/@)(]", "_", k) + ".csv"))
    logger.info('\nFinished...Good bye 👋')

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
