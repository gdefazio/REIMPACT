# REIMPACT - Research infrastructure Evaluation tool for IMPACT

[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-yellow.svg)](LICENSE)

Python package for bibliometric assessment of ELIXIR services and authors, based on OpenAlex and Scopus.

---

## Main Features

### 1. Author DOI Search

- Interactive author search and disambiguation on OpenAlex and Scopus
- Output: Excel file with all DOIs associated to selected authors
- Supports single author or batch mode (Excel file with author list)
- **CLI Command**: `reimpact-author-search`

### 2. Impact Assessment via DOIs

- Analyzes bibliometric impact (citations, institutions, aggregated metrics) starting from a list of DOIs
- Input: Excel file produced by Author DOI Search or any file with a DOI column
- Output: Excel report with impact statistics per author/service
- **CLI Command**: `reimpact-impact`

---

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/gdefazio/REIMPACT.git
cd REIMPACT

# Create and activate conda environment
conda env create -f environment.yml
conda activate reimpact

# Install the package
pip install .
```

See [INSTALLATION](docs/INSTALLATION.md) for detailed instructions.

---

## Recommended Workflow

1. **Author DOI Search**

   ```bash
   reimpact-author-search \
    --input_authors test/authors_template.xlsx \
    --openalex_key YOUR_OPENALEX_API_KEY \
    --scopus_key YOUR_SCOPUS_API_KEY
   ```
2. **Impact Assessment via DOI**

   ```bash
   reimpact-impact \
     --input_excel authors_results/Authors_DOIs_OpenAlex.xlsx \
     --openalex_key YOUR_OPENALEX_API_KEY \
     --scopus_key YOUR_SCOPUS_API_KEY
   ```

---

## Usage Examples

### Search DOIs for a Single Author

```bash
reimpact-author-search \
  --author "Mario Rossi" \
  --openalex_key YOUR_OPENALEX_API_KEY \
  --scopus_key YOUR_SCOPUS_API_KEY
```

### Search DOIs for a List of Authors

```bash
reimpact-author-search \
  --input_authors test/authors_template.xlsx \
  --openalex_key YOUR_OPENALEX_API_KEY \
  --scopus_key YOUR_SCOPUS_API_KEY
```

### Impact Assessment from Authors DOI File

```bash
reimpact-impact \
  --input_excel authors_results/Authors_DOIs_OpenAlex.xlsx \
  --output output_impact/output_file.xlsx \
  --openalex_key YOUR_OPENALEX_API_KEY \
  --scopus_key YOUR_SCOPUS_API_KEY
```

### Impact Assessment from Services DOI File

```bash
  reimpact-impact \
  --input_excel test/services_template.xlsx \
  --output output_impact/output_file.xlsx \
  --openalex_key YOUR_OPENALEX_API_KEY \
  --scopus_key YOUR_SCOPUS_API_KEY
```

## Input File Format

### For author-search module

Excel file with a column "Author" (or similar):

| Author       |
| ------------ |
| Mario Rossi  |
| Anna Bianchi |

### For impact module

Excel file with at least 4 columns in this positional order:

| Service | Applicant          | Platform | Primary doi first then others |
| ------- | ------------------ | -------- | ----------------------------- |
| ELIXIR  | University of Bari | Data     | 10.1234/abc, 10.5678/def, ... |

Only the 1st and 4th columns are mandatory (service/author and DOI list); rows missing either of these are skipped.

---

## Environment Variables (Optional)

Instead of passing API keys as arguments, you can set environment variables:

```bash
export OPENALEX_API_KEY="your_openalex_key"        # Required
export SCOPUS_API_KEY="your_scopus_key"            # Required for Scopus access
```

---

## Package Structure

```
REIMPACT/
├── reimpact/
│   ├── __init__.py              # Package initialization
│   ├── author-search.py         # Author DOI search module
│   ├── impact.py                # Impact assessment module
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

## Command-Line Interface

After installation, two commands are available:

### `reimpact-author-search`

Search for authors and retrieve their publication DOIs.

```bash
reimpact-author-search --help
```

### `reimpact-impact`

Analyze bibliometric impact from a list of DOIs.

```bash
reimpact-impact --help
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

This project is licensed under the CC BY-NC 4.0 License - see the [LICENSE](LICENSE) file for details.

---

## Authors

- **Giuseppe Defazio** - giuseppe.defazio@uniba.it
- **Vincenzo Angiulli** - vincenzo.angiulli@uniba.it

---

## Support

For issues or questions:

- Open an issue on [GitHub](https://github.com/gdefazio/REIMPACT/issues)
- Check the documentation in [docs/](docs/)
- Contact the authors via email
