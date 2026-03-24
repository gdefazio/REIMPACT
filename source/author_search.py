#!/usr/env/bin python3

"""
Author Metadata and DOI Retrieval System
Retrieves author publication DOIs from OpenAlex and Scopus databases.

"""
__author__ = "Vincenzo Angiulli"
__version__ = "1.0"

import os
import sys
import argparse
import logging
import pandas as pd
import pyalex
from pybliometrics.scopus import (
    AuthorSearch as ScopusAuthorSearch,
    AbstractRetrieval,
    ScopusSearch,
    AuthorRetrieval
)
from typing import List, Optional, Tuple, Dict
from .utils.utils import (
    get_available_databases,
    choose_search_databases,
    setup_logging,
    sanitize_filename, 
    validate_output_directory,
    validate_author_name,
    validate_authors_file,
    validate_max_works,
    sanitize_doi,
    ValidationError
)
# Optional dependency
try:
    import argcomplete
    ARGCOMPLETE_AVAILABLE = True
except ImportError:
    ARGCOMPLETE_AVAILABLE = False

# ============================================================================
# MODULE LOGGER
# ============================================================================
logger = logging.getLogger(__name__)

# Export control for package integration
__all__ = [
    'OpenAlexAuthorSearch',
    'ScopusAuthorSuggestion',
    'fetch_author_dois_openalex',
    'fetch_author_dois_scopus',
    'process_single_author',
    'build_author_row',
]

# =============================
# LOGGING SETUP
# =============================
logger = logging.getLogger(__name__)

# ============================================================================
# COMMAND LINE ARGUMENT PARSING
# ============================================================================
def parse_arguments() -> argparse.Namespace:
    """
    Parse and validate command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Retrieve author publication DOIs from OpenAlex and Scopus databases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Single author:
    %(prog)s --author "Surname, Firstname" --output ./authors_results --openalex_key YOUR_OPENALEX_API_KEY --scopus_key YOUR_SCOPUS_API_KEY
  
  Multiple authors from file:
    %(prog)s --input_authors authors.xlsx --output ./authors_results --openalex_key YOUR_OPENALEX_API_KEY --scopus_key YOUR_SCOPUS_API_KEY -M 50
        """
    )
    
    # Input options
    input_group = parser.add_argument_group('Input Options')
    input_group.add_argument(
        "-a", "--author",
        type=str,
        help="Single author full name (format: 'Surname, Firstname' or 'Firstname Surname')",
        metavar="NAME"
    )
    input_group.add_argument(
        "-i", "--input_authors",
        type=str,
        help="Excel file with authors (one per row, column 'Author' or first column)",
        metavar="FILE"
    )
    
    # API configuration
    api_group = parser.add_argument_group('API Configuration')
    api_group.add_argument(
        "--openalex_key",
        type=str,
        default=os.getenv('OPENALEX_API_KEY'),
        help="OpenAlex API key (required, or set OPENALEX_API_KEY env var)",
        metavar="KEY"
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
        metavar="KEY"
    )
    
    # Output and behavior
    output_group = parser.add_argument_group('Output & Behavior')
    output_group.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output Excel file name or full path. If not specified, uses 'AuthorName_DOIs_Source.xlsx' in ./authors_results/",
        metavar="FILE"
    )
    output_group.add_argument(
        "-M", "--max_works",
        type=int,
        default=None,
        help="Maximum works per author (default: all available)",
        metavar="N"
    )
    output_group.add_argument(
        "--skip_scopus",
        action="store_true",
        help="Skip Scopus search (use when outside institutional network)"
    )
    output_group.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level)"
    )
    output_group.add_argument(
        "--log_file",
        type=str,
        default=None,
        help="Log file path (default: console only)",
        metavar="FILE"
    )

    if ARGCOMPLETE_AVAILABLE:
        argcomplete.autocomplete(parser) # type: ignore
    args = parser.parse_args()
    
    # Validation
    if not args.author and not args.input_authors:
        parser.error("Must provide either --author or --input_authors")
    if args.author and args.input_authors:
        parser.error("Cannot use both --author and --input_authors")
    
    return args

# ============================================================================
# OPENALEX AUTHOR SEARCH
# ============================================================================
class OpenAlexAuthorSearch:
    """
    Search and disambiguate authors in OpenAlex database.
    
    Attributes:
        max_results: Maximum number of candidate authors to return
        per_page: Results per API page (1-200)
    """
    
    def __init__(self, max_results: int = 25, per_page: int = 25):
        self.max_results = max_results
        self.per_page = max(1, min(per_page, 200))

    def search(self, query: str) -> List[dict]:
        """Search for authors matching query string."""
        cleaned = (query or "").strip()
        if not cleaned:
            raise ValueError("Author query cannot be empty.")
        results: List[dict] = []
        query_obj = pyalex.Authors().search(cleaned)
        iterator = query_obj.paginate(method="page", per_page=self.per_page)
        for page in iterator:
            for raw_author in page:
                results.append(self._normalize_author(raw_author))
                if len(results) >= self.max_results:
                    return results
        return results

    @staticmethod
    def _normalize_author(raw_author: dict) -> dict:
        """Extract and flatten key fields from an OpenAlex author payload"""
        institutions = raw_author.get("last_known_institutions") or raw_author.get("last_known_institution") or []
        institution_name = None
        country_code = None
        if isinstance(institutions, dict):
            institution_name = institutions.get("display_name")
            country_code = institutions.get("country_code")
        elif isinstance(institutions, list) and institutions:
            first = institutions[0]
            if isinstance(first, dict):
                inst_obj = first.get("institution") if isinstance(first.get("institution"), dict) else first
                institution_name = inst_obj.get("display_name") # type: ignore
                country_code = inst_obj.get("country_code") # type: ignore
        alt_names = raw_author.get("display_name_alternatives") or []
        concepts = raw_author.get("x_concepts") or []
        topics = raw_author.get("topics") or []
        return {
            "id": raw_author.get("id"),
            "orcid": raw_author.get("orcid"),
            "display_name": raw_author.get("display_name"),
            "display_name_alternatives": ";".join(alt_names),
            "last_known_institution": institution_name,
            "country_code": country_code,
            "works_count": raw_author.get("works_count"),
            "cited_by_count": raw_author.get("cited_by_count"),
            "top_concepts": ";".join([c.get("display_name") for c in concepts[:5] if isinstance(c, dict)]), # type: ignore
            "top_topics": ";".join([t.get("display_name") for t in topics[:5] if isinstance(t, dict)]), # type: ignore
            "raw": raw_author,
        }

    @staticmethod
    def interactive_select(candidates: List[dict]) -> Optional[Tuple[List[dict], bool]]:
        """
        Interactive selection of author(s) from candidates with multi-selection support.
        
        Args:
            candidates: List of author dictionaries
            
        Returns:
            Tuple of (list of selected author dicts, aggregate flag) or None if cancelled
            aggregate flag is True if '+' was used (merge DOIs), False otherwise
        """
        if not candidates:
            print("  ⚠️  No authors found on OpenAlex\n")
            return None
            
        print("\n  📚 OpenAlex Candidates:\n")
        for idx, candidate in enumerate(candidates):
            inst = candidate.get("last_known_institution") or "n/a"
            print(
                f"  [{idx+1}] {candidate.get('display_name')}\n"
                f"      🏛️  {inst}\n"
                f"      📄 Works: {candidate.get('works_count')} | "
                f"📖 Citations: {candidate.get('cited_by_count')}\n"
                f"      🆔 {candidate.get('id')}\n"
                # f"        {candidate.get('orcid')}\n"
            )
        
        print("  💡 Tip: Use + to aggregate results (e.g., '1+3+5' merges DOIs, removes duplicates)")
        print("           Use , to keep separate (e.g., '1,3,5' creates separate rows)")
        print("           Or enter a single number for one author\n")
        
        while True:
            try:
                choice = input("  👉 Select author(s) [1-{}] or press Enter to skip: ".format(len(candidates))).strip()
                if choice == "":
                    print("")
                    return None
                
                # Determine separator: + for aggregation, , for separate results
                if '+' in choice:
                    separator = '+'
                elif ',' in choice:
                    separator = ','
                else:
                    separator = None
                
                # Parse multiple selections
                selected_indices = []
                if separator:
                    for part in choice.split(separator):
                        idx = int(part.strip()) - 1
                        if 0 <= idx < len(candidates):
                            selected_indices.append(idx)
                        else:
                            raise ValueError(f"Invalid index: {idx+1}")
                else:
                    # Single selection
                    idx = int(choice.strip()) - 1
                    if 0 <= idx < len(candidates):
                        selected_indices.append(idx)
                    else:
                        raise ValueError(f"Invalid index: {idx+1}")
                
                if selected_indices:
                    selected = [candidates[i] for i in selected_indices]
                    aggregate = (separator == '+')
                    if aggregate:
                        print(f"\n  ✅ Selected {len(selected)} author(s) - Results will be aggregated\n")
                    else:
                        print(f"\n  ✅ Selected {len(selected)} author(s)\n")
                    return (selected, aggregate)
                else:
                    print("  ❌ No valid selections. Try again.")
            except ValueError:
                print("  ❌ Invalid input. Use numbers separated by + or , (e.g., '1+3+5' or '1,3,5')")


# ============================================================================
# SCOPUS AUTHOR SEARCH
# ============================================================================
class ScopusAuthorSuggestion:
    """
    Search and disambiguate authors in Scopus database.
    
    Attributes:
        max_results: Maximum number of candidate authors to return
    """
    
    def __init__(self, max_results: int = 25):
        self.max_results = max_results

    @staticmethod
    def _build_query(author_query: str) -> str:
        """
        Build a Scopus author search query from various name formats.
        
        Supported formats:
        - "Surname, Firstname" or "Surname, F." (comma-separated, standard format)
        - "Firstname Surname" (space-separated, common format)
        - "F. Surname" or "F Surname" (initial + surname)
        - "Firstname Middle Surname" (takes first and last tokens)
        """
        cleaned = (author_query or "").strip()
        if not cleaned:
            raise ValueError("Author query cannot be empty.")
        
        # This is the most reliable format
        if "," in cleaned:
            parts = [part.strip() for part in cleaned.split(",") if part.strip()]
            if len(parts) >= 2:
                last = parts[0]
                first = parts[1]
            else:
                last = parts[0]
                first = ""
        # Case 2: Space-separated format
        else:
            tokens = cleaned.split()
            
            if len(tokens) == 0:
                raise ValueError("Author query cannot be empty.")
            elif len(tokens) == 1:
                # Only one token: assume it's the surname
                last = tokens[0]
                first = ""
            elif len(tokens) == 2:
                # Two tokens: Could be "Firstname Surname" or "F. Surname"
                # Check if first token looks like an initial (1-2 chars, possibly with dot)
                first_token = tokens[0].replace(".", "").strip()
                
                if len(first_token) <= 2:
                    # Likely an initial
                    first = first_token
                    last = tokens[1]
                else:
                    # Likely full first name
                    first = tokens[0]
                    last = tokens[1]
            else:
                # Three or more tokens
                # Strategy: Take first token as firstname, last token as surname
                # Middle tokens are ignored for the query (Scopus limitation)
                first = tokens[0]
                last = tokens[-1]
                first_cleaned = first.replace(".", "").strip()
                if len(first_cleaned) <= 2:
                    first = first_cleaned
        
        # Remove dots from initials for better Scopus matching
        first = first.replace(".", "").strip()
        last = last.replace(".", "").strip()
        
        # Build query
        query = f"AUTHLAST({last})"
        if first:
            query += f" AND AUTHFIRST({first})"
        return query

    def search(self, author_query: str) -> List[dict]:
        try:
            query = self._build_query(author_query)
        except ValueError:
            return []
        try:
            result = ScopusAuthorSearch(query)
        except Exception as exc:
            logger.error(f"Scopus AuthorSearch failed: {exc}")
            logger.info("Common causes:")
            logger.info("  1. Running outside institutional network")
            logger.info("  2. VPN/proxy connection (not supported)")
            logger.info("  3. Invalid API key or insufficient permissions")
            logger.info("Solution: Use --skip_scopus flag")
            return []
        try:
            authors = result.authors or []
        except AttributeError as exc:
            logger.error(f"pybliometrics parsing error: {exc}")
            logger.info("This may occur with certain data formats returned by Scopus API")
            return []

        suggestions: List[dict] = []
        for author in authors:
            try:
                # Format ORCID if present
                orcid_formatted = None
                if hasattr(author, 'orcid') and author.orcid: # type: ignore
                    # Remove brackets and format as URL
                    orcid_clean = str(author.orcid).strip('[]').strip() # type: ignore
                    if orcid_clean and orcid_clean.lower() != 'none':
                        orcid_formatted = f"https://orcid.org/{orcid_clean}"
                
                # Build suggestion dict
                suggestions.append({
                    "eid": author.eid if hasattr(author, 'eid') else None, # type: ignore
                    "orcid": orcid_formatted,
                    "surname": author.surname if hasattr(author, 'surname') else None, # type: ignore
                    "givenname": author.givenname if hasattr(author, 'givenname') else None, # type: ignore
                    "documents": author.documents if hasattr(author, 'documents') else 0, # type: ignore
                    "affiliation": author.affiliation if hasattr(author, 'affiliation') else None, # type: ignore
                    "affiliation_id": author.affiliation_id if hasattr(author, 'affiliation_id') else None, # type: ignore
                    "city": author.city if hasattr(author, 'city') else None, # type: ignore
                    "country": author.country if hasattr(author, 'country') else None, # type: ignore 
                })    
            except Exception as exc:
                logger.debug(f"Error processing Scopus author: {exc}")
                continue
            if len(suggestions) >= self.max_results:
                break
        
        return suggestions

    @staticmethod
    def interactive_select(candidates: List[dict]) -> Optional[Tuple[List[dict], bool]]:
        """
        Interactive selection of author(s) from Scopus candidates with multi-selection support.
        
        Args:
            candidates: List of author dictionaries
            
        Returns:
            Tuple of (list of selected author dicts, aggregate flag) or None if skipped
            aggregate flag is True if '+' was used (merge DOIs), False otherwise
        """
        if not candidates:
            print("  ⚠️  No Scopus candidates found\n")
            return None
            
        print("\n  📚 Scopus Candidates:\n")
        for idx, candidate in enumerate(candidates):
            fullname = f"{candidate.get('surname')}, {candidate.get('givenname')}".strip(", ")
            affiliation = candidate.get('affiliation') or 'n/a'
            link = f"https://www.scopus.com/authid/detail.uri?authorId={str(candidate.get('eid')).split('-')[-1]}"
            # city = candidate.get('city') or ''
            # country = candidate.get('country') or ''
            # location = f"{city}, {country}" if city and country else (city or country or 'n/a')
            
            print(
                f"  [{idx+1}] {fullname}\n"
                f"      🏛️  {affiliation}\n"
                f"      📄 Documents: {candidate.get('documents')}\n"
                f"      🆔 {link}\n"
                # f"       {candidate.get('orcid')}\n"
            )
        
        print("  💡 Tip: Use + to aggregate results (e.g., '1+3+5' merges DOIs, removes duplicates)")
        print("           Use , to keep separate (e.g., '1,3,5' creates separate rows)")
        print("           Or enter a single number for one author\n")
        
        while True:
            try:
                choice = input("  👉 Select author(s) [1-{}] or press Enter to skip: ".format(len(candidates))).strip()
                if choice == "":
                    print("")
                    return None 
                # Determine separator: + for aggregation, , for separate results
                if '+' in choice:
                    separator = '+'
                elif ',' in choice:
                    separator = ','
                else:
                    separator = None
                # Parse multiple selections
                selected_indices = []
                if separator:
                    for part in choice.split(separator):
                        idx = int(part.strip()) - 1
                        if 0 <= idx < len(candidates):
                            selected_indices.append(idx)
                        else:
                            raise ValueError(f"Invalid index: {idx+1}")
                else:
                    # Single selection
                    idx = int(choice.strip()) - 1
                    if 0 <= idx < len(candidates):
                        selected_indices.append(idx)
                    else:
                        raise ValueError(f"Invalid index: {idx+1}")   
                if selected_indices:
                    selected = [candidates[i] for i in selected_indices]
                    aggregate = (separator == '+')
                    if aggregate:
                        print(f"\n  ✅ Selected {len(selected)} author(s) - Results will be aggregated\n")
                    else:
                        print(f"\n  ✅ Selected {len(selected)} author(s)\n")
                    return (selected, aggregate)
                else:
                    print("  ❌ No valid selections. Try again.")
            except ValueError:
                print("  ❌ Invalid input. Use numbers separated by + or , (e.g., '1+3+5' or '1,3,5')")


# ============================================================================
# OPENALEX AUTHOR SEARCH
# ============================================================================
def fetch_author_dois_openalex(author_id: str, max_works: Optional[int] = None) -> List[str]:
    """
    Retrieve DOIs from OpenAlex for a given author.
    
    Args:
        author_id: OpenAlex author identifier
        max_works: Maximum number of works to retrieve (None for all)
        
    Returns:
        List of DOI strings
    """
    if not author_id:
        return []
        
    results: List[str] = []
    unique = set()
    
    try:
        works_query = pyalex.Works().filter(author={"id": author_id}).select(["doi"])
        
        count = 0
        for page in works_query.paginate(per_page=200):
            for work in page:
                doi = sanitize_doi(work.get("doi"))
                if doi and doi not in unique:
                    unique.add(doi)
                    results.append(doi)
                    count += 1
                    if max_works is not None and count >= max_works:
                        return results
        
        return results
        
    except Exception as exc:
        logger.debug(f"Failed to retrieve works from OpenAlex: {exc}")
        return []


def fetch_author_dois_scopus(author_eid: str, max_works: Optional[int] = None) -> List[str]:
    """
    Retrieve DOIs from Scopus for a given author.
    
    Args:
        author_eid: Scopus author EID
        max_works: Maximum number of works to retrieve (None for all)
        
    Returns:
        List of DOI strings
    """
    if not author_eid:
        return []
    
    results: List[str] = []
    unique = set()
    
    try:        
        # Extract just the numeric part of the EID (remove "9-s2.0-" prefix if present)
        scopus_id = author_eid.replace("9-s2.0-", "").strip()
        
        # Get author information
        author = AuthorRetrieval(scopus_id)
        
        # Check for document links
        if not hasattr(author, 'scopus_author_link') or not author.scopus_author_link:
            return []
        
        # Try document IDs approach
        doc_ids = []
        if hasattr(author, 'document_ids') and author.document_ids: # type: ignore
            doc_ids = author.document_ids if isinstance(author.document_ids, list) else [author.document_ids] # type: ignore
        
        if not doc_ids:
            # Fallback: search by author ID
            query = f"AU-ID({scopus_id})"
            search = ScopusSearch(query, download=True)
            
            if not search.results:
                return []
            
            for result in search.results:
                if max_works is not None and len(results) >= max_works:
                    break
                try:
                    doi_value = getattr(result, 'doi', None)
                    doi = sanitize_doi(doi_value) if doi_value else None
                    if doi and doi not in unique:
                        unique.add(doi)
                        results.append(doi)
                except Exception:
                    continue
        else:
            for doc_id in doc_ids:
                if max_works is not None and len(results) >= max_works:
                    break
                try:
                    doc = AbstractRetrieval(doc_id)
                    doi = sanitize_doi(doc.doi) if doc.doi else None
                    if doi and doi not in unique:
                        unique.add(doi)
                        results.append(doi)
                except Exception:
                    continue
        
        return results
        
    except Exception as exc:
        logger.debug(f"Failed to retrieve works from Scopus: {exc}")
        return []

# ============================================================================
# DATA PROCESSING FUNCTIONS
# ===========================================================================

def build_author_row(
    author: dict,
    dois: List[str],
    scopus_selection: Optional[dict] = None,
    source: str = "OpenAlex"
) -> dict:
    """
    Build Excel row for author with DOIs.
    
    Args:
        author: Author metadata dictionary
        dois: List of DOI strings
        scopus_selection: Optional Scopus author data
        source: Data source ("OpenAlex" or "Scopus")
        
    Returns:
        Dictionary with columns: Service, Applicant, Platform, Number of DOIs, Primary doi first then others
    """
    author_name = author.get('display_name', 'Unknown')
    institution = author.get('last_known_institution', '')
    
    if source == "Scopus" and scopus_selection:
        surname = scopus_selection.get('surname', '')
        givenname = scopus_selection.get('givenname', '')
        author_name = f"{givenname} {surname}".strip() if givenname and surname else author_name
        institution = scopus_selection.get('affiliation', institution)
    
    return {
        "Service": author_name,
        "Applicant": institution,
        "Platform": source,
        "Number of DOIs": len(dois),
        "Primary doi first then others": ", ".join(dois),
    }



def process_single_author(
    author_name: str,
    max_works: Optional[int],
    search_config: Dict[str, bool]
) -> Tuple[List[dict], List[dict], Optional[List[dict]], Optional[List[dict]]]:
    """
    Process single author: search, disambiguate, and retrieve DOIs.
    Supports multiple author selections per database.
    
    Args:
        author_name: Full name of author
        max_works: Max works to retrieve (None for all)
        search_config: Database selection {'openalex': bool, 'scopus': bool}
    
    Returns:
        Tuple of (openalex_rows, scopus_rows, author_selections, scopus_selections)
    """
    author_selections = None
    scopus_selections = None
    openalex_rows = []
    scopus_rows = []
    
    # OpenAlex search
    if search_config['openalex']:
        print("  🔍 Searching OpenAlex...")
        oa_search = OpenAlexAuthorSearch(max_results=25)
        try:
            oa_candidates = oa_search.search(author_name)
        except Exception as exc:
            print(f"  ⚠️  Unable to query OpenAlex: {exc}\n")
            oa_candidates = []
        
        if oa_candidates:
            selection_result = OpenAlexAuthorSearch.interactive_select(oa_candidates)
            
            if selection_result:
                author_selections, aggregate = selection_result
                
                if aggregate:
                    # Aggregate mode: merge all DOIs from selected authors
                    print(f"  ✅ Aggregating {len(author_selections)} author(s)...")
                    all_dois = set()
                    author_names = []
                    institutions = []
                    
                    for author_selection in author_selections:
                        author_names.append(author_selection.get('display_name', 'Unknown'))
                        inst = author_selection.get('last_known_institution', '')
                        if inst:
                            institutions.append(inst)
                        
                        author_id = author_selection.get('id', '')
                        if author_id:
                            openalex_dois = fetch_author_dois_openalex(author_id, max_works=max_works)
                            all_dois.update(openalex_dois)
                    
                    if all_dois:
                        # Create a single row with aggregated data - use only first author name
                        aggregated_author = {
                            'display_name': author_names[0] if author_names else 'Unknown',
                            'last_known_institution': ' / '.join(institutions) if institutions else ''
                        }
                        row = build_author_row(aggregated_author, sorted(all_dois), None, source="OpenAlex")
                        openalex_rows.append(row)
                        print(f"  ✅ Aggregated {len(all_dois)} unique DOIs from {len(author_selections)} authors\n")
                    else:
                        print(f"  ⚠️  No DOIs found\n")
                else:
                    # Separate mode: create one row per author
                    for author_selection in author_selections:
                        print(f"  ✅ Processing: {author_selection.get('display_name')} - {author_selection.get('last_known_institution', '')}")
                        author_id = author_selection.get('id', '')
                        if author_id:
                            print(f"  📥 Fetching DOIs from OpenAlex...")
                            openalex_dois = fetch_author_dois_openalex(author_id, max_works=max_works)
                            if openalex_dois:
                                row = build_author_row(author_selection, openalex_dois, None, source="OpenAlex")
                                openalex_rows.append(row)
                                print(f"  ✅ Retrieved {len(openalex_dois)} DOIs\n")
                            else:
                                print(f"  ⚠️  No DOIs found\n")
            else:
                print(f"  ⏭️  Skipped OpenAlex selection\n")
        else:
            print(f"  ⚠️  No OpenAlex candidates found\n")
    
    # Scopus search
    if search_config['scopus']:
        print("  🔍 Searching Scopus...")
        try:
            scopus_suggestions = ScopusAuthorSuggestion().search(author_name)
            if scopus_suggestions:
                selection_result = ScopusAuthorSuggestion.interactive_select(scopus_suggestions)
                if selection_result:
                    scopus_selections, aggregate = selection_result
                    
                    if aggregate:
                        # Aggregate mode: merge all DOIs from selected authors
                        print(f"  ✅ Aggregating {len(scopus_selections)} author(s)...")
                        all_dois = set()
                        author_names = []
                        affiliations = []
                        
                        for scopus_selection in scopus_selections:
                            surname = scopus_selection.get('surname', '')
                            givenname = scopus_selection.get('givenname', '')
                            fullname = f"{givenname} {surname}".strip()
                            author_names.append(fullname)
                            
                            affil = scopus_selection.get('affiliation', '')
                            if affil:
                                affiliations.append(affil)
                            
                            eid = scopus_selection.get('eid', '')
                            if eid:
                                scopus_dois = fetch_author_dois_scopus(eid, max_works=max_works)
                                all_dois.update(scopus_dois)
                        
                        if all_dois:
                            # Create a single row with aggregated data - use only first author name
                            aggregated_author = {
                                'display_name': author_names[0] if author_names else 'Unknown'
                            }
                            aggregated_scopus = {
                                'surname': scopus_selections[0].get('surname', ''),
                                'givenname': scopus_selections[0].get('givenname', ''),
                                'affiliation': ' / '.join(affiliations) if affiliations else ''
                            }
                            row = build_author_row(aggregated_author, sorted(all_dois), aggregated_scopus, source="Scopus")
                            scopus_rows.append(row)
                            print(f"  ✅ Aggregated {len(all_dois)} unique DOIs from {len(scopus_selections)} authors\n")
                        else:
                            print(f"  ⚠️  No DOIs found\n")
                    else:
                        # Separate mode: create one row per author
                        for scopus_selection in scopus_selections:
                            fullname = f"{scopus_selection.get('givenname')} {scopus_selection.get('surname')}".strip()
                            print(f"  ✅ Processing: {fullname} - {scopus_selection.get('affiliation', '')}")
                            eid = scopus_selection.get('eid', '')
                            if eid:
                                print(f"  📥 Fetching DOIs from Scopus...")
                                scopus_dois = fetch_author_dois_scopus(eid, max_works=max_works)
                                if scopus_dois:
                                    author_dict = author_selections[0] if author_selections else {'display_name': fullname}
                                    row = build_author_row(author_dict, scopus_dois, scopus_selection, source="Scopus")
                                    scopus_rows.append(row)
                                    print(f"  ✅ Retrieved {len(scopus_dois)} DOIs\n")
                                else:
                                    print(f"  ⚠️  No DOIs found\n")
                else:
                    print(f"  ⏭️  Skipped Scopus selection\n")
            else:
                print(f"  ⚠️  No Scopus candidates found\n")
        except Exception as exc:
            print(f"  ❌ Scopus search failed: {exc}\n")
    
    if not openalex_rows and not scopus_rows:
        print(f"  ⚠️  No data retrieved from any source\n")
    
    return (openalex_rows, scopus_rows, author_selections, scopus_selections)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main execution function."""
    try:
        # Parse arguments
        options = parse_arguments()
        # Setup logging
        setup_logging(verbose=options.verbose, log_file=options.log_file)
        # Centralized API configuration and validation
        from .utils.utils import configure_apis
        err = configure_apis(options, logger=logger)
        if err:
            print(f"❌ {err}")
            return 1
        # Validate author name or file
        if options.author:
            try:
                validate_author_name(options.author)
                logger.debug(f"✅ Author name valid: {options.author}")
            except ValidationError as e:
                print(f"  ❌ {e}\n")
                return 1
        if options.input_authors:
            try:
                validate_authors_file(options.input_authors)
                logger.debug(f"✅ Authors file valid: {options.input_authors}")
            except ValidationError as e:
                print(f"  ❌ {e}\n")
                return 1
        # Validate output path (only if specified)
        if options.output:
            output_dir_to_validate = os.path.dirname(options.output)
            if output_dir_to_validate:
                try:
                    validate_output_directory(output_dir_to_validate)
                    logger.debug(f"✅ Output directory valid: {output_dir_to_validate}")
                except ValidationError as e:
                    print(f"  ❌ {e}\n")
                    return 1
        # Validate max_works
        try:
            validate_max_works(options.max_works)
            if options.max_works:
                logger.debug(f"✅ max_works valid: {options.max_works}")
        except ValidationError as e:
            print(f"  ❌ {e}\n")
            return 1
        print("  ✅ All inputs validated successfully\n")
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user\n")
        return 1
    except Exception as exc:
        print(f"\n❌ Error during initialization: {exc}\n")
        logger.exception("Detailed error:")
        return 1
    # Header
    print("\n" + "="*80)
    print(f"{' '*20}AUTHOR METADATA AND DOI RETRIEVAL SYSTEM")
    print(f"{' '*30}Powered by ELIXIR-IIB")
    print("="*80 + "\n")
    # Determine output directory
    default_output_dir = os.path.join(os.getcwd(), 'authors_results')
    alex_key = options.openalex_key
    scopus_key = options.scopus_key
    author_query = options.author
    input_authors = options.input_authors
    max_works = options.max_works
    skip_scopus_author = options.skip_scopus
    
    # Prepare list of authors
    authors_to_process = []
    if author_query:
        authors_to_process = [author_query]
        print(f"  👤 Processing single author: {author_query}\n")
    elif input_authors:
        try:
            authors_df = pd.read_excel(input_authors)
            if 'Author' in authors_df.columns:
                authors_to_process = authors_df['Author'].dropna().tolist()
            elif 'author' in authors_df.columns:
                authors_to_process = authors_df['author'].dropna().tolist()
            else:
                authors_to_process = authors_df.iloc[:, 0].dropna().tolist()
            
            print(f"📁 Loaded {len(authors_to_process)} authors from file\n")
        except FileNotFoundError:
            print(f"❌ File not found: {input_authors}\n")
            return 1
        except Exception as exc:
            print(f"❌ Unable to read authors file: {exc}\n")
            return 1
    
    if not authors_to_process:
        print("❌ No authors to process\n")
        return 1
    
    # Database selection
    if skip_scopus_author:
        search_config = {'openalex': True, 'scopus': False}
        print("  🔍 Search mode: OpenAlex only (Scopus skipped)\n")
    else:
        search_config = choose_search_databases(options)

    # Configuration summary
    print("="*40)
    print("  ⚙️  CONFIGURATION SUMMARY")
    print("="*40)
    output_display = options.output if options.output else f"{default_output_dir}/<author>_DOIs_<source>.xlsx"
    print(f"  📂 Output: {output_display}")
    print(f"  👥 Authors: {len(authors_to_process)}")
    print(f"  🔍 OpenAlex: {'✅' if search_config['openalex'] else '❌'}")
    print(f"  🔍 Scopus: {'✅' if search_config['scopus'] else '❌'}")
    print(f"  📊 Number of works per author: {max_works or 'all'}")
    print("="*40 + "\n")

    # Process all authors
    openalex_rows = []
    scopus_rows = []
    
    for idx, author_name in enumerate(authors_to_process, 1):
        print(f"\n{'─'*80}")
        print(f"  👤 Author {idx}/{len(authors_to_process)}: {author_name}")
        print(f"{'─'*80}\n")
        
        (oa_rows, sc_rows, author_selections, scopus_selections) = process_single_author(
            author_name, max_works, search_config
        )
        
        # Extend lists with all rows from multi-selection
        if oa_rows:
            openalex_rows.extend(oa_rows)
        
        if sc_rows:
            scopus_rows.extend(sc_rows)
    
    if not openalex_rows and not scopus_rows:
        print("\n  ❌ No authors were successfully processed. Nothing to save.\n")
        return 0
    
    print(f"\n{'='*40}")
    print("  📊 PROCESSING RESULTS\n")
    print(f"  📖 OpenAlex: {len(openalex_rows)} authors")
    print(f"  📖 Scopus: {len(scopus_rows)} authors")
    print(f"{'='*40}\n")

    # Determine base filename
    if len(authors_to_process) == 1:
        base_filename = sanitize_filename(authors_to_process[0])
    else:
        base_filename = 'Authors'
    
    # Prepare output paths
    def prepare_output_path(base_name: str, source: str) -> str:
        """Prepare output file path based on user input or default."""
        default_filename = f'{base_name}_DOIs_{source}.xlsx'
        
        if options.output:
            # User specified output
            output_dir = os.path.dirname(options.output)
            if output_dir:
                # Full path specified
                # Extract base name and replace source
                base_output = os.path.splitext(os.path.basename(options.output))[0]
                return os.path.join(output_dir, f'{base_output}_{source}.xlsx')
            else:
                # Just filename, use default directory
                base_output = os.path.splitext(options.output)[0]
                return os.path.join(default_output_dir, f'{base_output}_{source}.xlsx')
        else:
            # No output specified, use default
            return os.path.join(default_output_dir, default_filename)
    
    # Save OpenAlex results
    if openalex_rows:
        df_openalex = pd.DataFrame(openalex_rows)
        openalex_file = prepare_output_path(base_filename, 'OpenAlex')
        
        # Create directory if needed
        os.makedirs(os.path.dirname(openalex_file), exist_ok=True)
        df_openalex.to_excel(openalex_file, index=False, engine='openpyxl')
        
        total_dois = sum(
            len(row.get("Primary doi first then others", "").split(", "))
            for row in openalex_rows
            if row.get("Primary doi first then others")
        )
        print(f"  💾 OpenAlex: {openalex_file}")
        print(f"     👥 Authors: {len(openalex_rows)} | 📄 DOIs: {total_dois}\n")
    else:
        print("  ⚠️  No OpenAlex data to save\n")
    
    # Save Scopus results
    if scopus_rows:
        df_scopus = pd.DataFrame(scopus_rows)
        scopus_file = prepare_output_path(base_filename, 'Scopus')
        
        # Create directory if needed
        os.makedirs(os.path.dirname(scopus_file), exist_ok=True)
        df_scopus.to_excel(scopus_file, index=False, engine='openpyxl')
        
        total_dois = sum(
            len(row.get("Primary doi first then others", "").split(", "))
            for row in scopus_rows
            if row.get("Primary doi first then others")
        )
        print(f"  💾 Scopus: {scopus_file}")
        print(f"     👥 Authors: {len(scopus_rows)} | 📄 DOIs: {total_dois}\n")
    else:
        print("  ⚠️  No Scopus data to save\n")
    
    print("="*80)
    print("  ✅ PROCESSING COMPLETE")
    print("="*80 + "\n")
    
    return 0


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code if exit_code is not None else 0)
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user\n")
        sys.exit(130)
    except Exception as exc:
        print(f"\n❌ Fatal error: {exc}\n")
        sys.exit(1)