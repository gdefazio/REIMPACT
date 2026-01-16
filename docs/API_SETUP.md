# Scopus & OpenAlex API Setup Guide

Complete guide to obtaining and configuring Scopus and OpenAlex API access for AuthorAsService and DOI2impact.

---

## Overview

AuthorAsService and DOI2impact use:

- The **Scopus API** (via `pybliometrics`) for commercial bibliometric data
- The **OpenAlex API** for open, global scholarly metadata

Access requires:

1. ✅ A valid Scopus API key (**and** endpoint authorization)
2. ✅ A valid OpenAlex API key **or** a contact email (for polite pool)
3. ✅ Institutional network access (for Scopus)

---

# OpenAlex API Setup

## What is OpenAlex?

OpenAlex (https://openalex.org/) is a free, open, and comprehensive index of scholarly works, authors, institutions, and more. It is the open alternative to commercial bibliometric databases.

---

## Step 1: Register for OpenAlex API Access

### 1.1 Using the Polite Pool (No API Key)
- You can use the OpenAlex API without an API key by providing a valid contact email ("mailto") in your requests.
- This is called the "polite pool" and is suitable for most academic use cases.

**How to use:**
- Provide your email with the `--openalex_mailto` or `-m` flag in the script, or set the `OPENALEX_MAILTO` environment variable.
- Example: `--openalex_mailto your.email@domain.com`

**Polite Pool Rate Limit:**
- 10 requests per second
- 100k requests per day

### 1.2 Register for an API Key (Recommended for Heavy Use)
- For higher rate limits (100,000 requests/day), you can request a free API key.
- **Follow these steps (see also: https://help.openalex.org/hc/en-us/articles/24397762024087-Pricing):**
  1. Go to https://openalex.org/api and click "Get an API key".
  2. You will be redirected to the OpenAlex API Key request form.
  3. Fill in your name, email, organization, and a brief description of your use case (e.g., "Academic research for ELIXIR-IIB project").
  4. Submit the form.
  5. Wait for a confirmation email from OpenAlex (usually within 1-2 business days).
  6. Once approved, you will receive your API key by email.
- You can also review the official OpenAlex pricing and fair use policy at: https://help.openalex.org/hc/en-us/articles/24397762024087-Pricing

**How to use:**
- Provide your key with the `--openalex_key` or `-a` flag, or set the `OPENALEX_API_KEY` environment variable.
- Example: `--openalex_key sk-abc123...`

**API Key Rate Limit:**
- 100,000 requests per day
- 75 requests per second

---

## Step 2: Configure OpenAlex in Your Scripts

- Always provide a valid email (mailto) for best practice, even if you use an API key.
- You can set both `OPENALEX_API_KEY` and `OPENALEX_MAILTO` as environment variables for convenience.

**Windows (PowerShell):**
```powershell
$env:OPENALEX_API_KEY = "your_openalex_key_here"
$env:OPENALEX_MAILTO = "your.email@domain.com"
```

**macOS/Linux (Bash):**
```bash
export OPENALEX_API_KEY="your_openalex_key_here"
export OPENALEX_MAILTO="your.email@domain.com"
```

---

## Step 3: Verify OpenAlex Access

- Run a simple test with your script:


```bash
python source/DOI2impact.py -i input.xlsx -o ./results --openalex_mailto your.email@domain.com
```

- If you use a key:

```bash
python source/DOI2impact.py -i input.xlsx -o ./results --openalex_key sk-abc123... --openalex_mailto your.email@domain.com
```

- If you exceed your quota, you will receive HTTP 429 errors (Too Many Requests).

---

## OpenAlex API Rate Limits & Best Practices

- **Without API key (polite pool):** 10 req/sec, 1M/month
- **With API key:** 75 req/sec, 100k/day
- Always provide a valid email for identification
- Cache results when possible
- Avoid unnecessary repeated requests
- Monitor your usage if running large jobs

---

## OpenAlex API Troubleshooting

### Error: "429 Too Many Requests"
- **Cause:** Exceeded rate limit
- **Solution:** Wait and retry, or request an API key for higher limits

### Error: "401 Unauthorized" or "Invalid API Key"
- **Cause:** Invalid or missing API key
- **Solution:** Double-check your key, or use the polite pool with a valid email

### Error: "400 Bad Request"
- **Cause:** Malformed query or missing parameters
- **Solution:** Check API documentation and your query syntax

### Error: "No results found"
- **Cause:** Query did not match any records
- **Solution:** Check your search terms, try alternate spellings or IDs

---

## OpenAlex Resources

- **OpenAlex API Docs:** https://docs.openalex.org/
- **API Playground:** https://docs.openalex.org/how-to-use-the-api/api-overview

---

# Scopus API Setup

## Step 1: Obtain API Key

### 1.1 Register on Elsevier Developer Portal
1. Visit https://dev.elsevier.com/apikey/manage
2. Click "Register" or "Log in"
3. Use your **institutional email** for registration

### 1.2 Accept Terms and Conditions
- Review and accept the Elsevier Developer API Terms of Service
- Agree to appropriate use policies

### 1.3 Generate API Key
1. Navigate to "My API Key" section
2. Click "Create API Key"
3. Copy and save your API key securely

**Example API Key Format**: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`

---

## Step 2: Request API Authorization

⚠️ **Important**: Having an API key is **NOT enough**. You must request authorization for specific API endpoints.

### 2.1 Required API Endpoints

AuthorAsService requires authorization for these **four APIs**:

| API Name | Purpose | Used By |
|----------|---------|---------|
| **AuthorSearch** | Search for author profiles by name | `ScopusAuthorSearch()` |
| **AbstractRetrieval** | Retrieve publication metadata by DOI/Scopus ID | `AbstractRetrieval()` |
| **ScopusSearch** | Search Scopus database with queries | `ScopusSearch()` |
| **AuthorRetrieval** | Get detailed author profile and publications | `AuthorRetrieval()` |

### 2.2 How to Request Authorization

1. Log in to https://dev.elsevier.com/
2. Click on "I want an API Key" or on "My API Key"
3. Request access to each of the four APIs listed above writing to **Elsevier Data Support** (support@elsevier.com or via [Data as a Service Support Center](https://service.elsevier.com/app/contact/supporthub/dataasaservice/))
    **Subject**: "API Authorization Request for AuthorSearch, AbstractRetrieval, ScopusSearch, AuthorRetrieval"
    
    Include in your message:
    ```
    Dear Elsevier Data Support,
    
    I am requesting authorization for my API key to access the following APIs 
    for academic research and bibliometric analysis:
    
    - AuthorSearch
    - AbstractRetrieval
    - ScopusSearch
    - AuthorRetrieval
    
    API Key: *[Your API Key]*
    Institution: *[Your Institution Name]*
    Purpose: Bibliometric analysis for ELIXIR-IIB research project

    Thank you,
    *[Your Name]*
    ```

### 2.3 Wait for Approval
- **Typical wait time**: 1-3 business days
- You will receive email confirmation when authorization is granted
- Check your API key status on the developer portal

---

## Step 3: Configure pybliometrics

### 3.1 First Time Setup
When you run the script for the first time, pybliometrics will create a configuration file:

**Windows**: `C:\Users\YourUsername\.config\pybliometrics.cfg`  
**macOS/Linux**: `~/.config/pybliometrics.cfg`

### 3.2 Manual Configuration (Optional)
Edit the config file to add your API key:

```ini
[Authentication]
APIKey = your_scopus_api_key_here
```

### 3.3 Environment Variable (Recommended)
Set your API key as environment variable:

**Windows (PowerShell)**:
```powershell
$env:SCOPUS_API_KEY = "your_api_key_here"
```

**macOS/Linux (Bash)**:
```bash
export SCOPUS_API_KEY="your_api_key_here"
```

**Add to profile for persistence**:
- Windows: Add to PowerShell profile
- macOS/Linux: Add to `~/.bashrc` or `~/.zshrc`

---

## Step 4: Verify Access

### 4.1 Check API Quota
Use the provided utility script:

```bash
python source/utils/check_scopus_quota.py YOUR_API_KEY
```

**Expected Output**:
```
✅ Scopus API key is valid
📊 Quota: 150/5000 requests used this week
```

### 4.2 Test with Script
Run a simple test search:

```bash
python source/AuthorAsService.py \
  -a "Author Fullname" \
  --openalex_mailto your.email@domain.com \
  --scopus_key YOUR_API_KEY \
  --max_works 5
```

---

## Troubleshooting

### Error: "401 Unauthorized" or "Authentication Failed"

**Cause**: API key not authorized for required endpoints

**Solution**:
1. Verify authorization status on https://dev.elsevier.com/apikey/manage
2. If not authorized, follow **Step 2** above
3. Wait for Elsevier approval
4. Check authorization email confirmation

### Error: "403 Forbidden"

**Cause**: Access denied from your IP address or network

**Solutions**:
1. **Use institutional network**: Connect to your university/institution network
2. **Check IP authorization**: Some API keys are restricted to specific IP ranges
3. **Contact IT department**: Request Scopus API access from your institutional network

**Workaround**: Use `--skip_scopus` flag to use OpenAlex only

### Error: "429 Too Many Requests"

**Cause**: Exceeded API rate limit

**Solutions**:
1. Check quota: `python utils/check_scopus_quota.py YOUR_KEY`
2. Wait until quota resets (weekly/monthly)
3. Reduce requests: Use `-M` flag to limit works per author
4. Contact Elsevier to request higher quota

### Error: "AttributeError: 'str' object has no attribute 'get'"

**Cause**: Wrong pybliometrics version (not the gdefazio distribution)

**Solution**:
```bash
conda uninstall pybliometrics -y
conda install -c gdefazio pybliometrics -y
```

See [INSTALLATION.md](INSTALLATION.md) for details.

---

## API Rate Limits

### Standard Limits
- **5,000 requests per week** (typical individual key)
- **20,000 requests per week** (institutional key)
- Limits reset weekly on Sunday at 00:00 UTC

### Best Practices
1. Use `-M` flag to limit works per author
2. Cache results when possible
3. Batch process authors during off-peak hours
4. Monitor quota regularly

---

## Institutional Access

### Advantages
- Higher API rate limits
- Access from institutional network (no VPN issues)
- Institutional keys may have pre-authorized API access
- Better support from Elsevier

### How to Get Institutional Key
1. Contact your **institution's library**
2. Ask if they provide Scopus API keys for researchers
3. Request access for bibliometric research
4. They may provide a shared institutional key

---

## Alternative: OpenAlex Only

If you cannot obtain Scopus API access, you can use **OpenAlex only**:

```bash
python AuthorAsService.py \
  -a "Author Name" \
  --mailto your.email@domain.com \
  --skip_scopus_author_search
```


## Additional Resources

- **Elsevier Developer Portal**: https://dev.elsevier.com/
- **Scopus API Documentation**: https://dev.elsevier.com/api_docs.html
- **pybliometrics Documentation**: https://pybliometrics.readthedocs.io/
- **OpenAlex Documentation**: https://docs.openalex.org/
- **Data Support**: Email support via developer portal or team@ourresearch.org

---

**Questions?** Check [INSTALLATION.md](INSTALLATION.md) and [README.md](README.md) troubleshooting sections, or contact the OpenAlex or Elsevier support teams.
