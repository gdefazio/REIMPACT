"""
REIMPACT - Research infrastructure Evaluation tool for IMPACT

A comprehensive system for bibliometric assessment of ELIXIR services and authors,
based on OpenAlex and Scopus databases.

Modules:
    - author-search: Author search and DOI retrieval
    - impact: Impact assessment from DOI lists
"""

__version__ = "1.0.0"
__author__ = "Vincenzo Angiulli"
__license__ = "MIT"

# Import main classes and functions for easier access
from .author_search import (
    OpenAlexAuthorSearch,
    ScopusAuthorSuggestion,
)

from .impact import (
    OpenAlexDoi,
    OpenAlexService,
    MyCitationOverview,
    MyCitationOverviewChunked,
)

__all__ = [
    '__version__',
    '__author__',
    '__license__',
    'OpenAlexAuthorSearch',
    'ScopusAuthorSuggestion',
    'OpenAlexDoi',
    'OpenAlexService',
    'MyCitationOverview',
    'MyCitationOverviewChunked',
    ]
