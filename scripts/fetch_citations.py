"""
════════════════════════════════════════════════════════════════════════
FILE: scripts/fetch_citations.py

PURPOSE:
    Fetches citation counts from Google Scholar for all configured
    lab members. Matches each paper to a DOI and writes a JSON file
    that the website reads to display citation counts.

OUTPUT:
    data/citation_counts.json
    Format: { "10.1234/doi.here": 42, ... }
    Keys are DOIs (lowercase, no https://doi.org/ prefix).
    Values are integer citation counts.

HOW IT WORKS:
    Uses the `scholarly` library to scrape Google Scholar (no API key
    needed). Google occasionally blocks automated requests — the script
    uses exponential backoff and retries automatically.

RUNNING LOCALLY (for testing):
    pip install scholarly requests
    python scripts/fetch_citations.py

════════════════════════════════════════════════════════════════════════
"""

import json
import os
import time
import re
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

# ── Try importing scholarly; fail gracefully ──────────────────────────
try:
    from scholarly import scholarly, ProxyGenerator
    SCHOLARLY_AVAILABLE = True
except ImportError:
    log.error("scholarly not installed. Run: pip install scholarly")
    SCHOLARLY_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════════
# ✏️  LAB MEMBERS CONFIGURATION
#
# Add each person's Google Scholar ID here when available.
# Find the ID in the Scholar profile URL:
#   https://scholar.google.com/citations?user=XXXXXXXXXXXX
#              this part is the ID ──────────────────────^
#
# Set scholar_id to None to skip fetching for that person.
# ══════════════════════════════════════════════════════════════════════
LAB_MEMBERS = [
    {
        "name":       "Dr. Ravi V. Mural",
        "scholar_id": "5NlUnZ0AAAAJ",      # ✅ ACTIVE
        "note":       "PI — primary publication source",
    },
    # ── 🚩 TODO: Uncomment and fill in Scholar IDs when available ──────
    # {
    #     "name":       "Ermias Assefa",
    #     "scholar_id": None,              # 🚩 PLACEHOLDER — add Scholar ID
    # },
    # {
    #     "name":       "Shalma Maman",
    #     "scholar_id": None,              # 🚩 PLACEHOLDER — add Scholar ID
    # },
    # {
    #     "name":       "Prajwal R S",
    #     "scholar_id": None,              # 🚩 PLACEHOLDER — add Scholar ID
    # },
    # {
    #     "name":       "Muragesh Mrutyunjaya Hiremath",
    #     "scholar_id": None,              # 🚩 PLACEHOLDER — add Scholar ID
    # },
    # {
    #     "name":       "Shiva Kumar Reddy Mudedla",
    #     "scholar_id": None,              # 🚩 PLACEHOLDER — add Scholar ID
    # },
    # {
    #     "name":       "Preethi J Kabbakki",
    #     "scholar_id": None,              # 🚩 PLACEHOLDER — add Scholar ID
    # },
]

# ── How many times to retry on Scholar rate-limit/block ───────────────
MAX_RETRIES = 3
RETRY_DELAY = 10  # seconds between retries


def clean_doi(raw: str) -> str:
    """Normalize a DOI string to bare form (no URL prefix, lowercase)."""
    if not raw:
        return ""
    doi = raw.strip()
    doi = re.sub(r'^https?://(dx\.)?doi\.org/', '', doi, flags=re.IGNORECASE)
    return doi.lower()


def fetch_member_citations(member: dict) -> dict:
    """
    Fetch all publications for one lab member from Google Scholar.
    Returns dict: { 'doi_string': citation_count, ... }
    """
    scholar_id = member.get("scholar_id")
    name       = member.get("name", "Unknown")

    if not scholar_id:
        log.info(f"  Skipping {name} — no Scholar ID configured.")
        return {}

    log.info(f"  Fetching: {name} (Scholar ID: {scholar_id})")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            author = scholarly.search_author_id(scholar_id)
            # Fill in publication details (titles, citations, eids)
            author_filled = scholarly.fill(author, sections=['publications'])
            pubs = author_filled.get('publications', [])

            counts = {}
            for pub in pubs:
                # Each pub may have a DOI in its external IDs
                pub_filled = None
                doi = ""

                # Try to get DOI from eids field first (faster)
                eids = pub.get('eids', [])
                for eid in eids:
                    if eid.lower().startswith('doi:'):
                        doi = clean_doi(eid[4:])
                        break

                # If no DOI in eids, fill the publication for more detail
                if not doi:
                    try:
                        pub_filled = scholarly.fill(pub)
                        bib = pub_filled.get('bib', {})
                        doi = clean_doi(bib.get('doi', '') or bib.get('eprint', ''))
                    except Exception:
                        pass

                cite_count = pub.get('num_citations', 0)

                if doi:
                    # If DOI already seen, keep the higher count
                    if doi in counts:
                        counts[doi] = max(counts[doi], cite_count)
                    else:
                        counts[doi] = cite_count
                    log.debug(f"    DOI: {doi}  →  {cite_count} citations")
                else:
                    title = pub.get('bib', {}).get('title', 'Unknown title')
                    log.warning(f"    No DOI found for: {title[:60]}")

                # Small delay to be polite to Scholar
                time.sleep(1.5)

            log.info(f"    → Found {len(counts)} papers with DOIs for {name}")
            return counts

        except Exception as e:
            log.warning(f"  Attempt {attempt}/{MAX_RETRIES} failed for {name}: {e}")
            if attempt < MAX_RETRIES:
                log.info(f"  Waiting {RETRY_DELAY}s before retry…")
                time.sleep(RETRY_DELAY * attempt)
            else:
                log.error(f"  All retries exhausted for {name}. Skipping.")
                return {}

    return {}


def load_existing_counts(output_path: Path) -> dict:
    """Load existing citation counts so we can merge/preserve them."""
    if output_path.exists():
        try:
            with open(output_path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def main():
    if not SCHOLARLY_AVAILABLE:
        log.error("Cannot run without scholarly. Exiting.")
        return

    # ── Output file path ───────────────────────────────────────────────
    # ✏️  Change this path if your repo structure is different
    output_path = Path(__file__).parent.parent / "data" / "citation_counts.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing counts as baseline (new run will update/add)
    existing = load_existing_counts(output_path)
    log.info(f"Loaded {len(existing)} existing citation entries.")

    all_counts = dict(existing)  # start with existing, overwrite with fresh data
    total_new  = 0

    log.info(f"Processing {len(LAB_MEMBERS)} lab member(s)…")

    for member in LAB_MEMBERS:
        if not member.get("scholar_id"):
            continue
        member_counts = fetch_member_citations(member)
        for doi, count in member_counts.items():
            if doi not in all_counts or all_counts[doi] != count:
                total_new += 1
            all_counts[doi] = count
        # Pause between members to avoid Scholar rate limits
        time.sleep(5)

    # Write output
    with open(output_path, 'w') as f:
        json.dump(all_counts, f, indent=2, sort_keys=True)

    log.info(f"Done. {len(all_counts)} total DOI entries written to {output_path}")
    log.info(f"{total_new} entries updated/added this run.")

    # ── Print summary for GitHub Actions log ──────────────────────────
    print(f"\n✅ citation_counts.json updated — {len(all_counts)} papers tracked")


if __name__ == "__main__":
    main()
