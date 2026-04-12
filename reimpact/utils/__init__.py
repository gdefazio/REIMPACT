"""
Utility module for REIMPACT

Provides validation, logging, and helper functions.
"""

from .utils import (
    setup_logging,
    sanitize_filename,
    validate_file,
    validate_email,
    validate_output_directory,
    validate_api_key,
    validate_author_name,
    validate_authors_file,
    validate_max_works,
    choose_search_databases,
    get_available_databases,
    check_scopus_key,
    set_openalex_apikey,
    sanitize_doi,
    configure_apis,
    ValidationError,
)