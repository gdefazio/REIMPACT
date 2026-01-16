# Installation Guide - ELIXIR.IT_IMPACT

## Quick Installation

### Prerequisites
- Python 3.11 or higher
- Miniconda or Anaconda (recommended)
- Git (for cloning the repository)
- API keys for OpenAlex and/or Scopus (see [API Setup](API_SETUP.md))

---

## Installation Steps

### Step 1: Clone the Repository
```bash
git clone https://github.com/gdefazio/ELIXIR.IT_IMPACT.git
cd ELIXIR.IT_IMPACT
```

### Step 2: Create and Activate Environment

#### Option A: Using Conda (Recommended)
```bash
# Create environment from file
conda env create -f environment.yml

# Activate environment
conda activate elixir_impact
```

#### Option B: Manual Conda Setup
```bash
# Create new environment
conda create -n elixir_impact python=3.11 -y

# Activate environment
conda activate elixir_impact

# Install pybliometrics from gdefazio channel (CRITICAL)
conda install -c gdefazio pybliometrics -y

# Install other dependencies
pip install -r requirements.txt
```

> **⚠️ Critical Note:**
> You **must** install `pybliometrics` from the `gdefazio` channel to avoid Scopus parsing errors.
> Standard pybliometrics 4.4 from PyPI is NOT compatible.

### Step 3: Install the Package
```bash
# Install in editable/development mode (recommended for development)
pip install -e .

# OR install normally
pip install .
```

This will:
- Install all Python dependencies
- Create command-line tools: `elixir-author-search` and `elixir-doi-impact`
- Make the package importable as a Python library

### Step 4: Verify Installation
```bash
# Check package version
pip show elixir-impact

# Test CLI commands
elixir-author-search --help
elixir-doi-impact --help

# Test Python imports
python -c "from source import OpenAlexAuthorSearch; print('✅ Package installed successfully')"
```

---

## Usage

After installation, you can use the package in two ways:

### 1. Command-Line Interface (CLI)

The package provides two commands:

```bash
# Search for author DOIs
elixir-author-search -a "Author Name" \
  --openalex_mailto your.email@domain.com \
  --scopus_key YOUR_SCOPUS_KEY

# Analyze impact from DOIs
elixir-doi-impact -i input.xlsx \
  --openalex_mailto your.email@domain.com \
  --scopus_key YOUR_SCOPUS_KEY
```

### 2. Python Library

Import and use functions in your own scripts:

```python
from source import OpenAlexAuthorSearch, fetch_author_dois_openalex
from source.utils import validate_email

# Your code here
searcher = OpenAlexAuthorSearch(mailto="your.email@domain.com")
candidates = searcher.search("Author Name")
```

---

## Configuration

### OpenAlex API
- **Option 1**: API Key (100k requests/day) - Recommended for heavy use
  ```bash
  export OPENALEX_API_KEY="your_key_here"
  ```
- **Option 2**: Polite Pool (10 req/s) - Requires email only
  ```bash
  export OPENALEX_MAILTO="your.email@domain.com"
  ```

You can also pass these as command-line arguments:
```bash
elixir-author-search --openalex_key YOUR_KEY --openalex_mailto your.email@domain.com
```

### Scopus API

#### Configure API Key
```bash
export SCOPUS_API_KEY="your_scopus_key"
```

Or pass as command-line argument:
```bash
elixir-author-search --scopus_key YOUR_SCOPUS_KEY 
```

**⚠️ Important: Requires API Key + Authorization**
See [API_SETUP](API_SETUP.md) for detailed instructions.

---

## Package Commands Reference

### `elixir-author-search`

Search for authors and retrieve their publication DOIs.

**Basic usage:**
```bash
# Single author
elixir-author-search -a "Author Name" -m email@domain.com -s SCOPUS_KEY

# Multiple authors from file
elixir-author-search -i authors.xlsx -m email@domain.com -s SCOPUS_KEY

# Limit number of works per author
elixir-author-search -a "Author Name" -m email@domain.com -M 50

# Skip Scopus (OpenAlex only)
elixir-author-search -a "Author Name" -m email@domain.com --skip_scopus

# Verbose output with log file
elixir-author-search -a "Author Name" -m email@domain.com -v --log_file output.log
```

**Help:**
```bash
elixir-author-search --help
```

### `elixir-doi-impact`

Analyze bibliometric impact from a list of DOIs.

**Basic usage:**
```bash
# Analyze impact from file
elixir-doi-impact -i input.xlsx -o output_dir/ -m email@domain.com -s SCOPUS_KEY

# OpenAlex only (skip Scopus)
elixir-doi-impact -i input.xlsx -o output_dir/ -m email@domain.com --skip_scopus

# With verbose logging
elixir-doi-impact -i input.xlsx -o output_dir/ -m email@domain.com -v
```

**Help:**
```bash
elixir-doi-impact --help
```

---

## Uninstallation

To remove the package and environment:

```bash
# Uninstall package
pip uninstall elixir-impact

# Remove conda environment
conda deactivate
conda env remove -n elixir_impact
```

---

## Updating the Package

To update to the latest version:

```bash
# Navigate to repository
cd ELIXIR.IT_IMPACT

# Pull latest changes
git pull origin main

# Reinstall package
pip install . --upgrade
```

---

## Troubleshooting

### Common Issues

#### 1. `pybliometrics` Parsing Errors
**Problem:** Errors like "AttributeError" or parsing failures with Scopus data.

**Solution:** Ensure you're using `pybliometrics` from the `gdefazio` channel:
```bash
conda install -c gdefazio pybliometrics -y --force-reinstall
```

#### 2. Command Not Found: `elixir-author-search`
**Problem:** CLI commands not available after installation.

**Solution:** 
- Make sure you ran `pip install -e .` in the repository directory
- Verify installation: `pip show elixir-impact`
- Restart your terminal/shell

#### 3. Import Errors
**Problem:** `ModuleNotFoundError: No module named 'source'`

**Solution:**
- Ensure package is installed: `pip install -e .`
- Check you're in the correct conda environment: `conda activate elixir_impact`

#### 4. API Key Issues
**Problem:** "API key required" or authentication errors.

**Solution:**
- Verify API keys are correctly set (environment variables or command-line arguments)
- For Scopus: Ensure you've requested authorization from Elsevier (see [API_SETUP.md](API_SETUP.md))
- For OpenAlex: Either provide API key OR email (mailto)

#### 5. Scopus Network/VPN Issues
**Problem:** Scopus fails outside institutional network.

**Solution:**
```bash
# Use --skip_scopus flag to use OpenAlex only
elixir-author-search -a "Author" -m email@domain.com --skip_scopus
```

#### 6. Excel File Errors
**Problem:** Cannot read or write Excel files.

**Solution:**
- Ensure `openpyxl` is installed: `pip install openpyxl`
- Check file permissions and paths
- Verify input file format matches expected structure

---


## System Requirements

- **Operating System:** Windows, macOS, Linux
- **Python:** 3.11 or higher
- **RAM:** 4GB minimum, 8GB recommended
- **Disk Space:** 500MB for environment + data storage
- **Network:** Internet connection required for API access

---

## Additional Resources

- [API Setup Guide](API_SETUP.md) - Detailed API configuration
- [README.md](../README.md) - Package overview and usage examples
- [GitHub Repository](https://github.com/gdefazio/ELIXIR.IT_IMPACT) - Source code and issues

---

## Getting Help

If you encounter issues not covered here:

1. Check the [GitHub Issues](https://github.com/gdefazio/ELIXIR.IT_IMPACT/issues)
2. Review the documentation in [docs/](.)
3. Contact the authors:
   - Giuseppe Defazio: giuseppe.defazio@uniba.it
   - Vincenzo Angiulli: vincenzo.angiulli@uniba.it
