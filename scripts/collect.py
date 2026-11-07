#!/usr/bin/env python3
"""Watchlist-only SEC Form 4 collector. Standard library only."""
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
AGENT = os.environ.get("SEC_USER_AGENT", "").strip()
if not AGENT:
    raise SystemExit("Set SEC_USER_AGENT to a truthful contact identifier before collecting SEC data.")

def get(url, *, sec=True):
    req = urllib.request.Request(url, headers={
        "User-Agent": AGENT if sec else "InsiderDashboard/0.1",
        "Accept": "application/json, application/xml, text/xml, */*",
        "Accept-Encoding": "identity",
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                return response.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            if attempt == 2:
                print(f"Fetch failed {url}: {exc}")
                return None
            time.sleep(2 ** attempt)
    return None

def text(node, path, default=""):
    el = node.find(path)
    return (el.text or "").strip() if el is not None else default

def roles(owner):
    rel = owner.find("reportingOwnerRelationship")
    if rel is None:
        return "Not specified"
    names = []
    for flag, label in (("isOfficer", "Officer"), ("isDirector", "Director"), ("isTenPercentOwner", "10% owner")):
        if text(rel, flag) == "1":
            names.append(label)
    title = text(rel, "officerTitle")
    if title:
        names.insert(0, title)
    return ", ".join(names) or "Other"

def parse_form4(raw, ticker, accession, filed, url):
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    if root.tag.split("}")[-1] != "ownershipDocument":
        return []
    owners = root.findall(".//reportingOwner")
    owner_names = [text(o, "reportingOwnerId/rptOwnerName") for o in owners]
    name = "; ".join(n for n in owner_names if n) or "Unknown"
    role = "; ".join(dict.fromkeys(roles(o) for o in owners))
    result = []
    for i, txn in enumerate(root.findall(".//nonDerivativeTransaction")):
        code = text(txn, "transactionCoding/transactionCode")
        if code not in ("P", "S"):
            continue
        try:
            shares = float(text(txn, "transactionAmounts/transactionShares/value"))
            price = float(text(txn, "transactionAmounts/transactionPricePerShare/value"))
        except (ValueError, TypeError):
            continue
        trade_date = text(txn, "transactionDate/value")
        if not trade_date:
            continue
        result.append({
            "id": accession + "-" + str(i),
            "ticker": ticker,
            "insider": name,
            "role": role,
            "side": "buy" if code == "P" else "sell",
            "shares": shares,
            "price_per_share": price,
            "value": round(shares * price, 2),
            "transaction_date": trade_date,
            "filed_at": filed,
            "filing_url": url,
        })
    return result

def sec_transactions(tickers):
    mapping_raw = get("https://www.sec.gov/files/company_tickers.json")
    if not mapping_raw:
        return []
    mapping = {row["ticker"].upper(): row["cik_str"] for row in json.loads(mapping_raw).values()}
    cutoff = (dt.date.today() - dt.timedelta(days=100)).isoformat()
    output = []
    for ticker in tickers:
        cik = mapping.get(ticker)
        if not cik:
            print("No SEC CIK:", ticker)
            continue
        raw = get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
        if not raw:
            continue
        recent = json.loads(raw).get("filings", {}).get("recent", {})
        filings = zip(recent.get("form", []), recent.get("accessionNumber", []),
                      recent.get("filingDate", []), recent.get("primaryDocument", []))
        count = 0
        for form, accession, filed, document in filings:
            if filed < cutoff:
                break
            if form != "4":
                continue
            if count >= 60:
                break
            count += 1
            acc_clean = accession.replace("-", "")
            base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_clean}"
            index_url = f"{base}/{document}"
            filing = get(index_url)
            time.sleep(0.16)
            if not filing:
                continue
            # The primary document is normally the ownership XML. Some issuers
            # use an HTML primary document; skip those rather than invent data.
            output.extend(parse_form4(filing, ticker, accession, filed, index_url))
        print(ticker, count, "filings checked")
        time.sleep(0.2)
    return output

def prices(tickers):
    # Yahoo chart endpoint is unofficial; outages leave an empty series.
    result = {}
    for ticker in tickers:
        symbol = urllib.parse.quote(ticker, safe="")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=6mo&interval=1d"
        raw = get(url, sec=False)
        series = []
        if raw:
            try:
                item = json.loads(raw)["chart"]["result"][0]
                timestamps = item.get("timestamp", [])
                closes = item["indicators"]["quote"][0]["close"]
                series = [{"date": dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat(),
                           "close": round(float(close), 4)}
                          for ts, close in zip(timestamps, closes) if close is not None]
            except (KeyError, IndexError, TypeError, ValueError):
                pass
        result[ticker] = series
        time.sleep(0.2)
    return result

def main():
    tickers = list(dict.fromkeys(x.strip().upper() for x in
              (DATA / "tickers.txt").read_text().splitlines()
              if x.strip() and not x.lstrip().startswith("#")))
    previous_path = DATA / "dashboard.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
    transactions = sec_transactions(tickers)
    price_data = prices(tickers)
    # Preserve prior verified data on temporary upstream failures.
    if not transactions and previous.get("transactions"):
        print("No new SEC data; preserving previously collected transactions")
        transactions = previous["transactions"]
    for ticker in tickers:
        if not price_data.get(ticker):
            price_data[ticker] = previous.get("prices", {}).get(ticker, [])
    dataset = {
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "tickers": tickers,
        "transactions": transactions,
        "prices": price_data,
    }
    previous_path.write_text(json.dumps(dataset, indent=2) + "\n")
    print("Wrote", len(transactions), "transactions for", len(tickers), "symbols")

if __name__ == "__main__":
    main()
