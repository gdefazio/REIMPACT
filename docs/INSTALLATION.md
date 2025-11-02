# Installation Guide - ELIXIR.IT_IMPACT

## Quick Installation

### Prerequisites
- Miniconda or Anaconda installed
- API keys for OpenAlex and/or Scopus

### Option 1: One-Step Environment Setup (Recommended)
```bash
cd ELIXIR.IT_IMPACT
conda env create -f environment.yml
conda activate elixir_impact
```

### Option 2: Manual Setup
```bash
conda create -n elixir_impact python=3.11 -y
conda activate elixir_impact
conda install -c gdefazio pybliometrics -y   # CRITICAL: must use gdefazio channel
cd ELIXIR.IT_IMPACT
pip install -r requirements.txt
```

> **Note:**
> - You **must** install `pybliometrics` from the `gdefazio` channel to avoid Scopus parsing errors.
> - Standard pybliometrics 4.4 is NOT compatible (see Troubleshooting).

### Step 3: Verify Installation
```bash
python -c "import pybliometrics; print(pybliometrics.__version__)"

python -c "import pyalex; import pandas; import openpyxl; import argcomplete; import numpy; print('✅ All packages installed')"
```

---

## Configuration

### OpenAlex API
- **Option 1**: API Key (100k requests/day)
  ```bash
  export OPENALEX_API_KEY="your_key_here"
  ```
- **Option 2**: Polite Pool (10 req/s) - requires email
  ```bash
  export OPENALEX_MAILTO="your.email@domain.com"
  ```

### Scopus API

**⚠️ Important: Requires API Key + Authorization**

#### Step 1: Obtain API Key
1. Visit https://dev.elsevier.com/apikey/manage
2. Register or log in with institutional credentials
3. Accept terms and conditions
4. Generate your API key

#### Step 2: Request API Access Authorization
After obtaining your API key, you **must request authorization** from Elsevier Data Support for the following APIs used by the package:
- AuthorSearch
- AbstractRetrieval
- ScopusSearch
- AuthorRetrieval


#### Step 3: Configure API Key
```bash
export SCOPUS_API_KEY="your_scopus_key"
```
See [API_SETUP](API_SETUP.md) for detailed instructions.

---

## Troubleshooting

- If you encounter errors with Scopus or pybliometrics, ensure you are using the correct version from the `gdefazio` channel.
- For more help, see the [Troubleshooting section](SCOPUS_API_SETUP.md#troubleshooting) or contact the authors.
