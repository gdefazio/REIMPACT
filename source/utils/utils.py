import os
import re
import logging
import pandas as pd
import sys
from typing import Optional
from urllib.parse import unquote

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    pass

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
    """
    Configure logging with appropriate format and level.
    
    Args:
        verbose: Enable DEBUG level logging
        log_file: Optional file path for logging (in addition to console)
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Use different formats for different log levels
    class LevelFormatter(logging.Formatter):
        """Custom formatter that uses different formats based on log level."""
        
        FORMATS = {
            logging.DEBUG: '[DEBUG] %(message)s',
            logging.INFO: '%(message)s',
            logging.WARNING: '⚠️  %(message)s',
            logging.ERROR: '❌ %(message)s',
            logging.CRITICAL: '🔥 %(message)s'
        }
        
        def format(self, record):
            log_fmt = self.FORMATS.get(record.levelno, '%(message)s')
            formatter = logging.Formatter(log_fmt)
            return formatter.format(record)
    
    # Get root logger and remove all existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)
    
    # Console handler with custom formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(LevelFormatter())
    console_handler.setLevel(log_level)
    root_logger.addHandler(console_handler)
    
    # Add file handler if specified
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
            file_handler.setFormatter(logging.Formatter(
                '[%(asctime)s] %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            file_handler.setLevel(log_level)
            root_logger.addHandler(file_handler)
        except Exception as exc:
            print(f"⚠️  Warning: Could not create log file {log_file}: {exc}")

# ============================================================================
# INPUT VALIDATION FUNCTIONS
# ============================================================================

def validate_file(filepath: str) -> bool:
    """
    Validate Excel file.
    """
    if not filepath:
        raise ValidationError("File path cannot be empty")
    if not os.path.exists(filepath):
        raise ValidationError(f"File not found: {filepath}")
    if not os.path.isfile(filepath):
        raise ValidationError(f"Path is not a file: {filepath}")
    if not filepath.lower().endswith(('.xlsx', '.xls')):
        raise ValidationError(f"Invalid file format: {filepath}")
    try:
        df = pd.read_excel(filepath, nrows=1)
    except Exception as exc:
        raise ValidationError(f"Cannot read Excel file: {exc}")
    if df.empty:
        raise ValidationError("Excel file is empty")
    return True

def validate_email(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If email format is invalid
    """
    import re
    if not email:
        raise ValidationError("Email cannot be empty")
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise ValidationError(f"Invalid email format: {email}")
    
    return True


def validate_authors_file(filepath: str) -> bool:
    """
    Validate Excel file containing authors.
    
    Args:
        filepath: Path to Excel file
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If file is invalid
    """
    from pathlib import Path
    
    if not filepath:
        raise ValidationError("Authors file path cannot be empty")
    
    file_path = Path(filepath)
    
    # Check existence
    if not file_path.exists():
        raise ValidationError(f"File not found: {filepath}")
    
    # Check if it's a file
    if not file_path.is_file():
        raise ValidationError(f"Path is not a file: {filepath}")
    
    # Check extension
    valid_extensions = ['.xlsx', '.xls']
    if file_path.suffix.lower() not in valid_extensions:
        raise ValidationError(
            f"Invalid file format: {file_path.suffix}. "
            f"Expected one of: {', '.join(valid_extensions)}"
        )
    
    # Try to read file
    try:
        df = pd.read_excel(filepath, nrows=1)
    except Exception as exc:
        raise ValidationError(f"Cannot read Excel file: {exc}")
    
    # Check if empty
    if df.empty:
        raise ValidationError("Excel file is empty")
    
    # Check for author column
    has_author_col = (
        'Author' in df.columns or 
        'author' in df.columns or 
        'AUTHORS' in df.columns or
        len(df.columns) > 0
    )
    
    if not has_author_col:
        logger.warning(
            "No 'Author' column found. Will use first column. "
            f"Available columns: {', '.join(df.columns)}"
        )
    
    return True


def validate_output_directory(dirpath: str) -> bool:
    """
    Validate output directory path and write permissions.
    
    Args:
        dirpath: Directory path
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If directory is invalid or not writable
    """
    from pathlib import Path
    
    if not dirpath:
        raise ValidationError("Output directory cannot be empty")
    
    dir_path = Path(dirpath)
    
    # If directory doesn't exist, check if parent is writable
    if not dir_path.exists():
        parent = dir_path.parent
        if not parent.exists():
            raise ValidationError(f"Parent directory does not exist: {parent}")
        if not os.access(str(parent), os.W_OK):
            raise ValidationError(f"Parent directory is not writable: {parent}")
    else:
        # Directory exists, check if it's actually a directory
        if not dir_path.is_dir():
            raise ValidationError(f"Path exists but is not a directory: {dirpath}")
        # Check write permissions
        if not os.access(str(dir_path), os.W_OK):
            raise ValidationError(f"Directory is not writable: {dirpath}")
    
    return True


def validate_api_key(api_key: Optional[str], key_name: str = "API key") -> bool:
    """
    Validate API key format (basic check).
    
    Args:
        api_key: API key to validate
        key_name: Name of the key for error messages
        
    Returns:
        True if valid (or None)
        
    Raises:
        ValidationError: If key is invalid
    """
    if api_key is None:
        return True  # None is acceptable for optional keys
    
    if not isinstance(api_key, str):
        raise ValidationError(f"{key_name} must be a string")
    
    api_key = api_key.strip()
    
    if len(api_key) == 0:
        raise ValidationError(f"{key_name} cannot be empty string")
    
    if len(api_key) < 10:
        raise ValidationError(f"{key_name} seems too short (< 10 characters)")
    
    # Check for suspicious patterns
    if api_key.lower() in ['your_key_here', 'api_key', 'key', 'none', 'null']:
        raise ValidationError(f"{key_name} appears to be a placeholder value")
    
    return True


def validate_author_name(author_name: str) -> bool:
    """
    Validate author name format.
    
    Args:
        author_name: Author name to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If name is invalid
    """
    if not author_name:
        raise ValidationError("Author name cannot be empty")
    
    author_name = author_name.strip()
    
    if len(author_name) < 2:
        raise ValidationError(f"Author name too short: '{author_name}'")
    
    # Check for at least one letter
    if not any(c.isalpha() for c in author_name):
        raise ValidationError(f"Author name must contain letters: '{author_name}'")
    
    # Warn about unusual patterns
    if author_name.isdigit():
        raise ValidationError(f"Author name cannot be only numbers: '{author_name}'")
    
    return True


def validate_max_works(max_works: Optional[int]) -> bool:
    """
    Validate max_works parameter.
    
    Args:
        max_works: Maximum number of works
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If value is invalid
    """
    if max_works is None:
        return True
    
    if not isinstance(max_works, int):
        raise ValidationError(f"max_works must be an integer, got {type(max_works).__name__}")
    
    if max_works < 1:
        raise ValidationError(f"max_works must be >= 1, got {max_works}")
    
    if max_works > 10000:
        logger.warning(f"max_works is very large ({max_works}). This may take a long time.")
    
    return True


# ============================================================================
# DOI UTILITIES
# ============================================================================

def sanitize_doi(doi: str) -> Optional[str]:
    """
    Clean and normalize DOI string, handling URL encoding.
    
    This function handles various DOI formats including:
    - URL-encoded DOIs (e.g., "https%3A%2F%2Fdoi.org%2F10.1093%2Fnar%2Fgkr930")
    - DOIs with https://doi.org/ prefix
    - Plain DOIs
    
    Args:
        doi: Raw DOI string (potentially URL-encoded)
        
    Returns:
        Cleaned DOI without prefix, or None if invalid
    """
    if not doi:
        return None
    
    # First decode URL encoding (%3A → :, %2F → /, etc.)
    doi = unquote(str(doi))
    
    # Then normalize: lowercase and strip whitespace
    doi = doi.lower().strip()
    
    # Remove common prefixes
    if doi.startswith("https://doi.org/"):
        doi = doi.replace("https://doi.org/", "", 1)
    elif doi.startswith("http://doi.org/"):
        doi = doi.replace("http://doi.org/", "", 1)
    elif doi.startswith("doi:"):
        doi = doi.replace("doi:", "", 1)
    
    return doi if doi else None