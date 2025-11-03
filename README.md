# ELIXIR.IT_IMPACT - Bibliometric Impact Assessment

[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Python package for bibliometric assessment of ELIXIR services and authors, based on OpenAlex and Scopus.

---

## Main Features


### 1. Author DOI Search
- Interactive author search and disambiguation on OpenAlex and Scopus
- Output: Excel file with all DOIs associated to selected authors
- Supports single author or batch mode (Excel file with author list)
- **CLI Command**: `elixir-author-search`

### 2. Impact Assessment via DOIs
- Analyzes bibliometric impact (citations, institutions, aggregated metrics) starting from a list of DOIs
- Input: Excel file produced by Author DOI Search or any file with a DOI column
- Output: Excel report with impact statistics per author/service
- **CLI Command**: `elixir-doi-impact`

---

## Quick Start

### Installation
```bash
# Clone the repository
git clone https://github.com/gdefazio/ELIXIR.IT_IMPACT.git
cd ELIXIR.IT_IMPACT

# Create and activate conda environment
conda env create -f environment.yml
conda activate elixir_impact

# Install the package
pip install -e .
```

See [INSTALLATION](docs/INSTALLATION.md) for detailed instructions.

---

## Recommended Workflow


1. **Author DOI Search**
   ```bash
   elixir-author-search \
     --input_authors test/authors_template.xlsx \
     --openalex_mailto your.email@domain.com \
     --scopus_key YOUR_SCOPUS_KEY
   ```

2. **Impact Assessment via DOI**
   ```bash
   elixir-doi-impact \
     -i authors_results/Authors_DOIs_OpenAlex.xlsx \
     --openalex_mailto your.email@domain.com \
     --scopus_key YOUR_SCOPUS_KEY
   ```

---

## Usage Examples


### Search DOIs for a Single Author
```bash
elixir-author-search \
  -a "Mario Rossi" \
  --openalex_mailto your.email@domain.com \
  --scopus_key YOUR_SCOPUS_KEY
```

### Search DOIs for a List of Authors
```bash
elixir-author-search \
  --input_authors test/authors_template.xlsx \
  --openalex_mailto your.email@domain.com \
  --scopus_key YOUR_SCOPUS_KEY
```

### Impact Assessment from Authors DOI File
```bash
elixir-doi-impact \
  -i authors_results/Authors_DOIs_OpenAlex.xlsx \
  -o output_impact/ \
  --openalex_mailto your.email@domain.com \
  --scopus_key YOUR_SCOPUS_KEY
```

### Impact Assessment from Services DOI File
```bash
elixir-doi-impact \
  -i test/services_template.xlsx \
  -o output_impact/ \
  --openalex_mailto your.email@domain.com
```

### Using as Python Library
```python
from source import OpenAlexAuthorSearch, fetch_author_dois_openalex

# Search for authors
searcher = OpenAlexAuthorSearch(mailto="your.email@domain.com")
candidates = searcher.search("Mario Rossi")

# Fetch DOIs
if candidates:
    author_id = candidates[0]['id']
    dois = fetch_author_dois_openalex(author_id, max_works=50)
    print(f"Found {len(dois)} DOIs")
```

---

## Input File Format

### For AuthorAsService
Excel file with a column "Author" (or similar):
| Author        |
|---------------|
| Mario Rossi   |
| Anna Bianchi  |

### For DOIs2impact
Excel file with at least a column "Primary doi first then others" (or "DOI"):
| Service      | Applicant          | Platform     | Primary doi first then others     |
|--------------|--------------------|--------------|-----------------------------------|
| ELIXIR       | University of Bari | Data         | 10.1234/abc, 10.5678/def, ...     |

---

## Environment Variables (Optional)

Instead of passing API keys as arguments, you can set environment variables:

```bash
export OPENALEX_API_KEY="your_openalex_key"        # Optional: for 100k req/day
export OPENALEX_MAILTO="your.email@domain.com"     # Required if no API key
export SCOPUS_API_KEY="your_scopus_key"            # Required for Scopus access
```

---

## Package Structure

```
ELIXIR.IT_IMPACT/
├── source/
│   ├── __init__.py              # Package initialization
│   ├── AuthorAsService.py       # Author DOI search module
│   ├── DOI2impact.py            # Impact assessment module
│   └── utils/
│       ├── __init__.py
│       ├── utils.py               # Validation and logging utilities
│       └── check_scopus_quota.py  # Scopus quota checking utility
├── test/                        # Sample input files
├── docs/                        # Documentation
├── setup.py                     # Package configuration
├── requirements.txt             # Python dependencies
├── environment.yml              # Conda environment
└── README.md                    # This file
```

---

## Command-Line Interface

After installation, two commands are available:

### `elixir-author-search`
Search for authors and retrieve their publication DOIs.

```bash
elixir-author-search --help
```

### `elixir-doi-impact`
Analyze bibliometric impact from a list of DOIs.

```bash
elixir-doi-impact --help
```

---

## Installation

See [INSTALLATION](docs/INSTALLATION.md) for detailed instructions on:
- Environment setup
- Package installation
- API configuration
- Troubleshooting

---

## Documentation

- [Installation Guide](docs/INSTALLATION.md) - Setup and configuration
- [API Setup](docs/API_SETUP.md) - Obtaining and configuring API keys

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Authors

- **Giuseppe Defazio** - giuseppe.defazio@uniba.it
- **Vincenzo Angiulli** - vincenzo.angiulli@uniba.it

---

## Support

For issues or questions:
- Open an issue on [GitHub](https://github.com/gdefazio/ELIXIR.IT_IMPACT/issues)
- Check the documentation in [docs/](docs/)
- Contact the authors via email
