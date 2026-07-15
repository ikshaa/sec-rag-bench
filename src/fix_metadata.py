"""
Backfill real SEC filing metadata into the filings table.

Day 3's chunker inserted placeholder values for accession_number,
filing_date, and report_date. This script hits EDGAR to fetch the
real values and updates each row.
"""
import os
import time

import psycopg
from dotenv import load_dotenv
from tqdm import tqdm

from src.ingest import(
    COMPANIES,
    TARGET_YEARS,
    REQUEST_DELAY_SECONDS,
    fetch_filing_index,
    pick_10k_for_year,
)

load_dotenv()

DB_CONFIG = {
    "host": os.environ["POSTGRES_HOST"],
    "port": os.environ["POSTGRES_PORT"],
    "user": os.environ["POSTGRES_USER"],
    "password": os.environ["POSTGRES_PASSWORD"],
    "dbname": os.environ["POSTGRES_DB"],
}

def fix_metadata() -> None:
    """
    For every (company, year) in our configured list, fetch real metadata
    from EDGAR and UPDATE the filings row.
    """
    tasks = [
        (company, cik, year)
        for company, cik in COMPANIES.items()
        for year in TARGET_YEARS
    ]

    print(f"Updating metadata for {len(tasks)} filings...\n")

    with psycopg.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            for company, cik, year in tqdm(tasks, desc = "Filings"):
                try:
                    filings = fetch_filing_index(cik)
                    time.sleep(REQUEST_DELAY_SECONDS)

                    filing = pick_10k_for_year(filings, year)
                    if filing is None:
                        tqdm.write(f" ✗ {company} {year}: no 10-K found")
                        continue

                    cur.execute(
                        """
                        UPDATE filings
                        SET accession_number = %s,
                            filing_date = %s,
                            report_date = %s
                        WHERE company = %s AND fiscal_year = %s
                        """,
                        (
                            filing["accession_number"],
                            filing["filing_date"],
                            filing["report_date"],
                            company,
                            year,
                        ),
                    )
                    tqdm.write(
                        f" ✓ {company} {year}:"
                        f"accession={filing['accession_number']}, "
                        f"filed={filing['filing_date']}, "
                    )
                except Exception as e:
                    tqdm.write(f" ✗  {company} {year}: {type(e).__name__}: {e}")
if __name__ == "__main__":
    fix_metadata()