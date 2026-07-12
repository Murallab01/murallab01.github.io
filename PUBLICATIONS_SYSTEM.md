# Publication Auto-Update System

## How it works

### 1. Live publication list — ORCID API
Publications are fetched from ORCID on every page load.
- **Dr. Mural's ORCID:** `0000-0002-5489-9918`
- To add a new paper: log into [orcid.org](https://orcid.org) and add the work. It will appear on the website automatically within minutes (no code change needed).
- To add another lab member: add their ORCID to `LAB_ORCIDS` in `index.html` (search for `LAB_ORCIDS`).

### 2. Citation counts — GitHub Actions (monthly)
Citation counts are fetched from Google Scholar monthly and stored in `data/citation_counts.json`.
- **Schedule:** 1st of every month at 06:00 UTC
- **Manual trigger:** GitHub → Actions tab → "Update Citation Counts" → Run workflow
- **Output:** `data/citation_counts.json`

## Files

| File | Purpose |
|------|---------|
| `.github/workflows/update_citations.yml` | Monthly scheduler |
| `scripts/fetch_citations.py` | Fetches Scholar citation counts |
| `data/citation_counts.json` | Citation count data (read by website) |

## Adding a new lab member

### For live publications (ORCID):
1. Ask them to create an ORCID account at orcid.org and make their works public
2. In `index.html`, find `LAB_ORCIDS` and add:
   ```js
   'Their Name': '0000-0000-0000-0000',
   ```

### For citation counts (Google Scholar):
1. Find their Scholar profile URL: `scholar.google.com/citations?user=XXXX`
2. In `scripts/fetch_citations.py`, find `LAB_MEMBERS` and uncomment/add:
   ```python
   {
       "name":       "Their Name",
       "scholar_id": "XXXX",
   },
   ```

## Topic tagging
ORCID doesn't store paper topics. Topics are auto-assigned by keyword matching in the `tagTopic()` function in `index.html`. To manually override a topic for a specific paper, add it to `TOPIC_OVERRIDES` in `index.html`:
```js
const TOPIC_OVERRIDES = {
  '10.1234/your.doi': 'genomics',
};
```
Valid topic slugs: `quantitative-genetics` | `genomics` | `phenotyping` | `computational` | `ai-ml`
