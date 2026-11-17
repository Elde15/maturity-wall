# Gate 6 sign-off: publication

Signed off 2026-11-16, with the author's approval to publish the repository. The repository becomes public on GitHub; the
site stays private until the author publishes it (D063), so the plan's definition of done ("the site is live") is not yet
met. Decisions D064 to D066 record what this gate changed.

## Checklist (SOP section 15)

| item | result | evidence |
| --- | --- | --- |
| A fresh clone builds the fixture dataset with one command and matches stored outputs | PASS | Cloned from GitHub at 6f8e8dd into an empty folder, `uv sync --extra model` installed the locked dependencies, and `uv run python -m mwall fixture` printed "fixture build matches stored outputs (6 snapshots)". `uv run pytest` in the clone: 119 passed, 5 skipped; the five are site checks that need `python -m mwall site`, which needs the full multi-hour data build. |
| The repo contains no secrets, no contact email, no raw XML, and no restricted third-party data | PASS, with the interpretations in D066 | A script read every blob in the history (434 blobs, 30 commits, 241 paths), including the inside of gzipped and Excel files. No key, token, password, private key or credentials file. The only email address is the `you@example.com` placeholder; all 30 commits carry the GitHub noreply address. Every committed version of the hand-check workbook is free of author metadata. The author's name appears only in the site byline. One notes file pointed to a local temp folder whose path includes the Windows username; the current version no longer does, and the old version stays in one commit (D066). Raw XML: only the eleven public SEC filings the fixture and golden tests need (D066). Third-party figures are cited single numbers with short verifying quotes, no source documents (D056). |
| A second reader outside the project has read the methodology page and the Los Angeles memo and noted anything unclear | PASS | 57 notes, each with its disposition, in `docs/qa/gate6_review.md` (D065). One note exposed an engine error, fixed in D064. |
| README states the thesis, headline results, limitations and how to reproduce | PASS | `README.md`: the question it answers, what the work found (including what the refinance gap does and doesn't measure), five groups of limits, a data-and-rights section, and the reproduce commands checked above. |

## Checks rerun after the review changes

- `pytest` on the working copy: 124 passed.
- axe-core: 0 violations on all eight pages at 1280 and 390px.
- Link crawl: 1,614 links on 23 rendered pages; 21 fail. Fourteen are the ones listed at Gate 5 (bot-blocked
  government and publisher pages, and the author's domain, not yet registered). Seven point to files in this repository
  and failed only because it was private; they are rechecked after publication below.

## After publication

The repository was made public on 2026-11-16 at f9e0706. Fetched without signing in, the repository page and every
repository file the site links to (selection rule, candidate list, memo, decision log, model card, model test report,
SEC schema elements, project plan) return 200. That clears the seven new failures and the repository link on the data
page, one of the fourteen from Gate 5. Thirteen remain: twelve government and publisher pages that refuse automated
requests (each opens in a browser) and the author's unregistered domain.

## What's left for the definition of done

- The site goes live when the author says so: either Cloudflare Access on the Worker's address for a private preview,
  or the public address switched on (`site/wrangler.jsonc`, D063).
- The author's domain, elidellabitta.com, is linked from the footer and doesn't resolve until it is registered.
