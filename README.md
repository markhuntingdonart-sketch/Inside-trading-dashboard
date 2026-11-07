# Insider Trading Intelligence Dashboard

A static, browser-based US insider-trading monitor built from **SEC Form 4** filings, with stock-price charts and annotated insider transactions.

## Status
Initial MVP. This is **not** a complete US-market leaderboard yet: the scheduled collector monitors the symbols in `data/tickers.txt`. It does not imply comprehensive market coverage. Data is refreshed by GitHub Actions; until its first successful run, the UI shows an explicit empty state.

## Setup
1. In repository **Settings → Pages**, select **Deploy from a branch**, branch **main**, folder **/(root)**.
2. In repository **Settings → Secrets and variables → Actions → Variables**, add `SEC_USER_AGENT` with a truthful identifier, e.g. `Mark Huntington markhuntingtonart@gmail.com`. The SEC requests identifying User-Agent information. Do not store API keys or passwords in this public repository.
3. Enable Actions, and run **Refresh insider data** manually once. Scheduled runs happen daily.
4. Open the GitHub Pages URL shown in Settings → Pages.

## Data semantics
- Only Form 4 **non-derivative transactions** with code **P** (purchase) or **S** (sale) are included.
- CEO/CFO flags, director, officer and 10% owner status come from reported-owner fields; labels are not independently verified.
- Multiple Form 4 transactions can appear in a filing. Amended Form 4/A filings are excluded in this initial version to avoid double counting; corrections may therefore be missing.
- Price series use Yahoo Finance's public chart endpoint (unofficial and subject to availability). SEC filings are the source of transaction data.
- Ranking is **transaction notional value**, not a recommendation. Sales may be planned under Rule 10b5-1 and are not necessarily bearish.
- The data pipeline uses a small configurable watchlist; a true market-wide screener needs a more comprehensive ingestion service and a durable database.

## Run locally
```bash
python scripts/collect.py
python -m http.server 8000
```
Visit http://localhost:8000. Python 3.11+; no third-party dependencies.

## Security
This repository is public. No brokerage credentials, account statements, API secrets, or personal investment records should be committed here.
