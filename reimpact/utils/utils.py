import os
import re
import requests
import logging
import pandas as pd
import sys
from typing import Optional
from urllib.parse import unquote

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    pass

__all__ = [
    'setup_logging',
    'sanitize_filename',
    'validate_file',
    'validate_email',
    'validate_output_directory',
    'validate_api_key',
    'validate_author_name',
    'validate_authors_file',
    'validate_max_works',
    'ValidationError',
    'choose_search_databases',
    'get_available_databases',
    'check_scopus_key',
    'set_openalex_apikey',
    'sanitize_doi',
    'configure_apis',
]
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

def sanitize_filename(name: str) -> str:
    """
    Sanitize author name for use in filename.
    
    Args:
        name: Author name
        
    Returns:
        Sanitized filename-safe string
    """
    return name.replace(',', '').replace(' ', '_').replace('.', '').strip()

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
    
    # If directory doesn't exist, check if we can create it
    if not dir_path.exists():
        # Walk up the directory tree to find the first existing ancestor
        current = dir_path.parent
        while current and not current.exists():
            current = current.parent
        
        # Check if the first existing ancestor is writable
        if current and current.exists():
            if not os.access(str(current), os.W_OK):
                raise ValidationError(f"Cannot create directory in: {current} (not writable)")
        else:
            # Reached root without finding existing directory (very unusual)
            raise ValidationError(f"Cannot determine if path is writable: {dirpath}")
    else:
        # Directory exists, check if it's actually a directory
        if not dir_path.is_dir():
            raise ValidationError(f"Path exists but is not a directory: {dirpath}")
        # Check write permissions
        if not os.access(str(dir_path), os.W_OK):
            raise ValidationError(f"Directory is not writable: {dirpath}")
    
    return True

# =============================
# DATABASE CONFIGURATION & VALIDATION
# =============================

def get_available_databases(openalex_key: Optional[str], scopus_key: Optional[str], skip_scopus: bool = False, verbose: bool = False) -> dict:
    """
    Centralized logic to determine which databases are available for search.
    Returns a dict: { 'openalex': bool, 'scopus': bool, 'reasons': { 'openalex': str, 'scopus': str } }
    """
    reasons = {'openalex': '', 'scopus': ''}
    # OpenAlex validation
    openalex_ok = False
    try:
        if openalex_key:
            validate_api_key(openalex_key, 'OpenAlex API key')
            openalex_ok = True
        else:
            reasons['openalex'] = 'No OpenAlex API key provided.'
    except Exception as e:
        reasons['openalex'] = str(e)
        openalex_ok = False

    # Scopus validation
    scopus_ok = False
    if skip_scopus:
        reasons['scopus'] = 'Scopus search skipped by user (--skip_scopus).'
    else:
        try:
            if scopus_key:
                validate_api_key(scopus_key, 'Scopus API key')
                # Try a real API call to check institutional access
                if verbose:
                    logger.info('Checking Scopus API key and institutional access...')
                try:
                    _ = check_scopus_key(scopus_key)
                    scopus_ok = True
                except ValidationError as ve:
                    # If forbidden, mark as not available and explain
                    if 'code 401' in str(ve) or 'code 402' in str(ve) or 'code 403' in str(ve):
                        reasons['scopus'] = f'Scopus unavailable: {ve} (likely not on institutional network)'
                    else:
                        reasons['scopus'] = f'Scopus API key error: {ve}'
            else:
                reasons['scopus'] = 'No Scopus API key provided.'
        except Exception as e:
            reasons['scopus'] = str(e)
            scopus_ok = False

    return {'openalex': openalex_ok, 'scopus': scopus_ok, 'reasons': reasons}

def choose_search_databases(args) -> dict:
    """
    Prompt user to select which databases to use, but only among those actually available.
    Returns: dict with 'openalex' and 'scopus' boolean flags
    """
    if args is None:
        raise RuntimeError("choose_search_databases must be called after argument parsing and args assignment.")
    db_status = get_available_databases(
        getattr(args, 'openalex_key', None),
        getattr(args, 'scopus_key', None),
        getattr(args, 'skip_scopus', False),
        getattr(args, 'verbose', False)
    )
    available = []
    if db_status['openalex']:
        available.append('OpenAlex')
    if db_status['scopus']:
        available.append('Scopus')
    if not available:
        logger.error("No valid database available. Check your API keys and network access.")
        logger.info(f"Reasons: {db_status['reasons']}")
        sys.exit(1)
    if len(available) == 1:
        logger.info(f"\n✅ Only {available[0]} is available and will be used.")
        return {'openalex': db_status['openalex'], 'scopus': db_status['scopus']}
    logger.info("\n==============================")
    logger.info("     🗃️  DATABASE SELECTION")
    logger.info("==============================")
    logger.info("Where do you want to search?")
    for idx, db in enumerate(available, 1):
        logger.info(f"  [{idx}] {db}")
    if len(available) == 2:
        logger.info(f"  [3] Both")
    while True:
        choice = input(f"Enter your choice (1-{len(available)+1 if len(available)==2 else len(available)}): ").strip()
        if choice == '1':
            return {'openalex': db_status['openalex'], 'scopus': False}
        elif choice == '2' and len(available) > 1:
            return {'openalex': False, 'scopus': db_status['scopus']}
        elif choice == '3' and len(available) == 2:
            return {'openalex': True, 'scopus': True}
        else:
            logger.error("Invalid choice. Please enter a valid option.")

# Helper for real Scopus API check (minimal query)
def check_scopus_key(api_key: str) -> bool:
    url = "https://api.elsevier.com/content/search/scopus"
    headers = {
        "X-ELS-APIKey": api_key,
        "Accept": "application/json"
    }
    params = {
        "query": "TITLE(test)",
        "count": 1
    }
    response = requests.get(url, headers=headers, params=params, timeout=10)
    logger.debug(f"Scopus API check response: {response.status_code}")
    if response.status_code == 200:
        return True
    elif response.status_code == 401:
        raise ValidationError("APIkey verification: code 401 - invalid key")
    elif response.status_code == 402:
        raise ValidationError("APIkey verification: code 402 - valid key without permission")
    else:
        raise ValidationError(f"APIkey verification: code {response.status_code}")
    
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

def set_openalex_apikey(api_key: Optional[str]) -> None:
    """
    Set the OpenAlex API key for authentication (both env var and pyalex.config).
    Args:
        api_key: OpenAlex API key string
    """
    import os
    try:
        import pyalex
    except ImportError:
        return
    if api_key:
        os.environ['OPENALEX_API_KEY'] = api_key
        try:
            pyalex.config.api_key = api_key
        except Exception:
            pass
        
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

# ============================================================================
# API CONFIGURATION (CENTRALIZED)
# ============================================================================
def configure_apis(options, logger=logger):
    """
    Centrally configure and validate APIs for OpenAlex and Scopus.
    - Validates email and API keys
    - Sets pyalex.config (api_key, data_version)
    - Sets up pybliometrics (create_config/init)
    - Logs configuration summary
    - Returns None if OK, or an error string if blocking error
    """
    import pyalex
    import pybliometrics
    import pybliometrics.scopus
    # OpenAlex
    alex_key = getattr(options, 'openalex_key', None)
    data_version = getattr(options, 'openalex_data_version', 2)
    scopus_key = getattr(options, 'scopus_key', None)
    skip_scopus = getattr(options, 'skip_scopus', False)
    verbose = getattr(options, 'verbose', False)
    # Logging
    logger.info('\n==============================')
    logger.info('    📡 API Configuration')
    logger.info('==============================')
    # OpenAlex: validazione e settaggio
    if alex_key:
        set_openalex_apikey(alex_key)
        logger.info("✅  OpenAlex: API key (100k requests/day)")
        pyalex.config.data_version = data_version
        version_name = "Walden (new)" if data_version == 2 else "Classic (old)"
        logger.info(f"📊  OpenAlex data version: {data_version} ({version_name})")
    else:
        logger.warning("OpenAlex: no API key provided (OpenAlex will be unavailable)")
    # Scopus
    if skip_scopus:
        logger.info("⏭️  Scopus search will be skipped (--skip_scopus set). Using only OpenAlex.")
    elif scopus_key:
        try:
            logger.info("⚙️  Scopus: Configuring API key...")
            pybliometrics.scopus.create_config(keys=[scopus_key]) # type: ignore
            pybliometrics.scopus.init() # type: ignore
            logger.info("✅  Scopus: API key configured")
        except Exception as exc:
            logger.error(f"Scopus configuration failed: {exc}")
            return f"Scopus configuration failed: {exc}"
    else:
        logger.warning("Scopus: no API key provided (Scopus will be unavailable)")
    return None