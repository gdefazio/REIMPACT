# ELIXIR.IT_IMPACT - Bibliometric Impact Assessment

[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)

System for bibliometric assessment of ELIXIR services and authors, based on OpenAlex and Scopus.

---

## Main Features


### 1. Author DOI Search (`AuthorAsService.py`)
- Interactive author search and disambiguation on OpenAlex and Scopus
- Output: Excel file with all DOIs associated to selected authors
- Supports single author or batch mode (Excel file with author list)

### 2. Impact Assessment via DOIs (`DOI2impact.py`)
- Analyzes bibliometric impact (citations, institutions, aggregated metrics) starting from a list of DOIs
- Input: Excel file produced by AuthorAsService or any file with a DOI column
- Output: Excel report with impact statistics per author/service

---

## Recommended Workflow


1. **Author DOI Search**
   ```bash
   python source/AuthorAsService.py \
     --input_authors test/authors_template.xlsx \
     --openalex_mailto your.email@domain.com \
     --scopus_key YOUR_SCOPUS_KEY
   ```

2. **Impact Assessment via DOI**
   ```bash
   python source/DOI2impact.py \
     -i authors_results/Authors_DOIs_OpenAlex.xlsx \
     --openalex_mailto your.email@domain.com \
     --scopus_key YOUR_SCOPUS_KEY
   ```

---

## Usage Examples


### Search DOIs for a Single Author
```bash
python source/AuthorAsService.py \
  -a "Mario Rossi" \
  --openalex_mailto your.email@domain.com \
  --scopus_key YOUR_SCOPUS_KEY
```

### Search DOIs for a List of Authors
```bash
python source/AuthorAsService.py \
  --input_authors test/authors_template.xlsx \
  --openalex_mailto your.email@domain.com \
  --scopus_key YOUR_SCOPUS_KEY
```

### Impact Assessment from authors DOI File
```bash
python source/DOI2impact.py \
  -i test/output/Authors_DOIs_OpenAlex.xlsx \
  -o output_impact/
```
### Impact Assessment from services DOI File
```bash
python source/DOI2impact.py \
  -i test/services_template.xlsx \
  -o output_impact/
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

## Installation

See [INSTALLATION](docs/INSTALLATION.md) for detailed instructions on environment, dependencies, and [API setup](docs/API_SETUP.md).

---

## Support

For issues or questions:
- Check the documentation in [docs/](docs/)
- Read the Troubleshooting section
