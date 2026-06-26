"""
SEC EDGAR ingestion script.

Downloads 10-K filings for a fixed list of companies and fiscal years,
extracts clean text from the HTML, and saves the result to data/filings/.
"""
import os
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tqdm import tqdm

# Load .env so we can pick up our email for the User-Agent header
load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Companies we're downloading 10-Ks for. CIK is SEC's unique identifier.
# We use short, lowercase slugs as filenames.
COMPANIES = {
    "apple":    "0000320193",
    "microsoft":"0000789019",
    "google":   "0001652044",
    "amazon":   "0001018724",
    "nvidia":   "0001045810",
    "tesla":    "0001318605",
    "costco":   "0000909832",
    "netflix":  "0001065280",
}

# Fiscal years we want. We'll match against the reportDate in each filing.
TARGET_YEARS = [2023, 2024]

# Where to save downloaded text files
OUTPUT_DIR = Path("data/filings")

# SEC requires a User-Agent identifying who's making requests.
# Read from .env so it isn't hardcoded.
USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "Neha Rani neha.gdd51@gmail.com"
)

# Polite delay between requests (SEC limit is 10/sec; we go much slower)
REQUEST_DELAY_SECONDS = 0.15

# Standard headers for every SEC request
HEADERS = {"User-Agent": USER_AGENT}

# ---------------------------------------------------------------------------
# Step 1: Fetch the filing index for a company
# ---------------------------------------------------------------------------

def fetch_filing_index(cik: str) -> list[dict]:
    """
    Fetch a company's filing history from EDGAR's submissions endpoint.

    Returns a list of filing records, each a dict with keys:
        accession_number, form, filing_date, report_date, primary_document

    The raw API returns parallel arrays; we transform them into a list of dicts
    so downstream code can iterate naturally.
    """
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    data = response.json()
    recent = data["filings"]["recent"]

    # Transform parallel arrays into a list of dicts
    filings = []
    num_filings = len(recent["accessionNumber"])
    for i in range(num_filings):
        filings.append({
            "accession_number": recent["accessionNumber"][i],
            "form": recent["form"][i],
            "filing_date": recent["filingDate"][i],
            "report_date": recent["reportDate"][i],
            "primary_document": recent["primaryDocument"][i],
        })

    return filings

# ---------------------------------------------------------------------------
# Step 2: Pick the 10-K for a specific fiscal year
# ---------------------------------------------------------------------------

def pick_10k_for_year(filings: list[dict], year: int) -> dict | None:
    """
    Find the 10-K filing whose report_date falls within the target fiscal year.

    Returns the filing dict if found, None otherwise.
    """
    for filing in filings:
        if filing["form"] != "10-K":
            continue
        if not filing["report_date"]:
            continue
        report_year = int(filing["report_date"][:4])
        if report_year == year:
            return filing
    return None

# ---------------------------------------------------------------------------
# Step 3: Download the filing HTML
# ---------------------------------------------------------------------------

def download_filing(cik: str, accession_number: str, primary_document: str) -> str:
    """
    Download the HTML of a filing from SEC's archives.

    Returns the raw HTML as a string.
    """
    cik_no_zeros = str(int(cik))
    accession_no_dashes = accession_number.replace("-", "")

    url = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_no_zeros}/{accession_no_dashes}/{primary_document}"
    )

    response = requests.get(url, headers=HEADERS, timeout=60)
    response.raise_for_status()
    return response.text

# ---------------------------------------------------------------------------
# Step 4: Extract clean text from filing HTML
# ---------------------------------------------------------------------------

def extract_text(html: str) -> str:
    """
    Parse the filing HTML and return clean readable text.

    SEC 10-Ks are inline XBRL documents — HTML with embedded financial tags.
    We strip XBRL tags, scripts, styles, and other non-content elements,
    then clean up whitespace.
    """
    # Suppress the "XML parsed as HTML" warning - we know what we're doing
    import warnings
    from bs4 import XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

    soup = BeautifulSoup(html, "lxml")

    # Remove non-content tags entirely
    non_content_tags = [
        "script", "style", "head", "meta", "link",
        # Inline XBRL tags - financial data markup, not human-readable content
        "ix:header", "ix:references", "ix:resources", "ix:hidden",
    ]
    for tag in soup(non_content_tags):
        tag.decompose()

    # Also remove any tag whose name starts with "ix:" (catch-all for XBRL)
    for tag in soup.find_all(lambda t: t.name and t.name.startswith("ix:")):
        tag.unwrap()  # keep its text content but remove the wrapper tag

    # Get the text
    text = soup.get_text(separator="\n")

    # Clean up whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = text.strip()

    return text

# ---------------------------------------------------------------------------
# Step 5: Orchestrator
# ---------------------------------------------------------------------------

def ingest_all() -> None:
    """
    Download and process 10-Ks for all configured companies and years.

    Saves clean text to data/filings/<company>_<year>.txt.
    Skips files that already exist (idempotent).
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Build the full list of (company, year) tasks
    tasks = [
        (company, cik, year)
        for company, cik in COMPANIES.items()
        for year in TARGET_YEARS
    ]

    print(f"Ingesting {len(tasks)} filings...\n")

    for company, cik, year in tqdm(tasks, desc="Filings"):
        output_path = OUTPUT_DIR / f"{company}_{year}.txt"

        # Skip if already downloaded
        if output_path.exists():
            tqdm.write(f"  ✓ {company} {year} already exists, skipping")
            continue

        try:
            # Fetch this company's filing index
            filings = fetch_filing_index(cik)
            time.sleep(REQUEST_DELAY_SECONDS)

            # Find the 10-K for the target year
            filing = pick_10k_for_year(filings, year)
            if filing is None:
                tqdm.write(f"  ✗ {company} {year}: no 10-K found")
                continue

            # Download and extract text
            html = download_filing(
                cik,
                filing["accession_number"],
                filing["primary_document"],
            )
            time.sleep(REQUEST_DELAY_SECONDS)

            text = extract_text(html)

            # Save to disk
            output_path.write_text(text, encoding="utf-8")
            tqdm.write(
                f"  ✓ {company} {year}: {len(text):,} chars "
                f"(filed {filing['filing_date']})"
            )

        except Exception as e:
            tqdm.write(f"  ✗ {company} {year}: {type(e).__name__}: {e}")


if __name__ == "__main__":
    ingest_all()