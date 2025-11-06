"""
Utility module for ELIXIR.IT_IMPACT

Provides validation, logging, and helper functions.
"""

from .utils import (
    setup_logging,
    validate_email,
    validate_output,
    validate_api_key,
    validate_author_name,
    validate_authors_file,
    validate_max_works,
    ValidationError,
)

__all__ = [
    'setup_logging',
    'validate_email',
    'validate_output',
    'validate_api_key',
    'validate_author_name',
    'validate_authors_file',
    'validate_max_works',
    'ValidationError',
]
