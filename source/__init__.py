"""
ELIXIR.IT_IMPACT - Bibliometric Impact Assessment System

A comprehensive system for bibliometric assessment of ELIXIR services and authors,
based on OpenAlex and Scopus databases.

Modules:
    - AuthorAsService: Author search and DOI retrieval
    - DOI2impact: Impact assessment from DOI lists
    - utils: Utility functions and validation
"""

__version__ = "1.0.0"
__author__ = "Vincenzo Angiulli"
__license__ = "MIT"

# Import main classes and functions for easier access
from .AuthorAsService import (
    OpenAlexAuthorSearch,
    ScopusAuthorSuggestion,
    fetch_author_dois_openalex,
    fetch_author_dois_scopus,
    process_single_author,
    build_author_row,
    sanitize_doi,
    sanitize_filename,
)

__all__ = [
    '__version__',
    '__author__',
    '__license__',
    'OpenAlexAuthorSearch',
    'ScopusAuthorSuggestion',
    'fetch_author_dois_openalex',
    'fetch_author_dois_scopus',
    'process_single_author',
    'build_author_row',
    'sanitize_doi',
    'sanitize_filename',
]
