# Coinviewer

**A lightweight command-line cryptocurrency portfolio viewer powered by CoinMarketCap.**

Coinviewer reads one or more semicolon-separated CSV portfolios, fetches the latest EUR and USD cryptocurrency prices, and prints readable, German-formatted portfolio tables. It supports CoinMarketCap IDs, negative net investments, multiple portfolios, and precise `Decimal` calculations.

> **Important:** This is a portfolio *valuation* tool, not an accounting or tax calculator. Market quotes are snapshots. All example portfolios contain fictional data.

## Features

- CoinMarketCap V3 `cryptocurrency/quotes/latest` endpoint.
- Separate EUR and USD API requests to support plans restricted to one `convert` currency per request.
- Batches up to 100 assets with the same identifier type per currency, reducing API calls.
- CoinMarketCap IDs (`id:1` or `1`), slugs (`bitcoin`) and ticker symbols (`BTC`). **IDs are strongly recommended** because symbols are not necessarily unique.
- Reads the **first three columns** of semicolon-delimited CSV files, ignoring any additional columns.
- Accepts **negative net investment**, for example when proceeds from sales exceed total purchases.
- Uses Python `Decimal` for calculations; display rounding does not change the underlying values.
- Handles unavailable market prices as `N/A`, never as zero, and avoids misleading aggregate totals.
- Shows each portfolio individually and a combined summary when multiple files are supplied.
- German numeric display (`1.234,56`) without requiring a German system locale.
- Automated offline tests and GitHub Actions CI (no live API key required).

## Requirements

- Python **3.10 or newer** (CI tests Python 3.11, 3.12 and 3.13).
- A valid [CoinMarketCap API key](https://coinmarketcap.com/api/).
- Python packages from `requirements.txt` (`requests` and `tabulate`).

## Quick start

```bash
# Clone your repository or download these files.
python -m pip install -r requirements.txt

# Create local files that will NOT be committed to Git.
cp coinviewer.py coinviewer.local.py
cp examples/portfolio.example.csv portfolio.csv
```

Edit **`coinviewer.local.py`** and replace the hardcoded placeholder near the top:

```python
API_KEY = "0000000000000000"  # Replace locally with your private key.
```

Run the local copy:

```bash
python coinviewer.local.py portfolio.csv
```

On Windows PowerShell, replace the `cp` commands with `Copy-Item` and use `py` in place of `python` if that is how Python is installed.

**Why a local script copy?** You asked to keep the API key hardcoded. The tracked `coinviewer.py` therefore deliberately contains **only a placeholder**. Your real key belongs exclusively in the git-ignored `coinviewer.local.py`; never commit or share that local copy. If a real key is accidentally committed, revoke/rotate it and remove it from repository history. `.gitignore` cannot protect a secret that is written into an already tracked file.

## CSV format

The CSV must be **UTF-8**, semicolon-separated, and contain a header row. Only columns 1–3 are interpreted; all later columns are ignored.

| Column | Example | Meaning |
| --- | --- | --- |
| 1. Coin | `id:1` | CoinMarketCap ID, ticker or slug |
| 2. Amount | `0.250001` | Quantity held, cannot be negative |
| 3. Net investment EUR | `-250.00` | Total EUR purchase spending **minus** proceeds from previous sales; can be negative |
| 4+ Optional | `Kraken`, `Long term` | Ignored by Coinviewer |

Example:

```csv
Coin;Amount;Net investment EUR;Exchange;Notes
id:1;0.250001;7500.00;Example Exchange;Bitcoin
id:1027;1.500001;-250.00;Example Exchange;Sale proceeds exceeded purchases
id:35697;1500;125.50;Example Wallet;Pi Network
```

- **Use decimal points in CSV numeric fields**, e.g., `1234.56`. The *output*, not the input, uses German number formatting.
- Coin IDs can be written as `1`, `1027`, `35697`, or `id:1`, `id:1027`, `id:35697`.
- Bare `PI` is mapped to CoinMarketCap ID `35697` (Pi Network) by the built-in `SYMBOL_ID_OVERRIDES`; you can instead specify an ID directly.
- If the third column contains **purchase price per coin**, rather than total net investment, add `--unit-cost`. In this mode the third value must be nonnegative and is multiplied by the amount.
- A CSV row with fewer than three columns, a negative quantity or a non-finite number is rejected with a helpful error.

## Usage

```bash
# One portfolio
python coinviewer.local.py portfolio.csv

# Two portfolios plus combined table
python coinviewer.local.py portfolio.csv /path/to/another.csv

# Treat column 3 as EUR purchase cost per coin
python coinviewer.local.py --unit-cost portfolio.csv

# Show all command-line options
python coinviewer.local.py --help
```

Running without arguments reads `portfolio.csv` next to the Python file.

## Output and accounting rules

| Column | Display rule |
| --- | --- |
| EUR price / USD price | **Exactly 2 decimal places for prices ≥ 0.01**; below 0.01, **2–6 decimal places** with unnecessary trailing zeros removed |
| Amount | **2–6 decimal places**, removing unnecessary trailing zeros but keeping at least 2 |
| Invested EUR | Exactly 2 decimal places |
| Value EUR / Value USD / P/L EUR | Exactly 2 decimal places |
| P/L % / Share % | Exactly 2 decimal places |

All numeric output uses `.` for thousands and `,` for decimals. For example, `0.009999` is shown as `0,009999`, `1.230000` as `1,23`, and `1500.000000` as `1.500,00`. Values smaller than the display precision may round to `0,00`; their **internal calculations still use the full source price**.

**Profit/loss (EUR)** is `current value in EUR − net investment in EUR`. When the net investment is zero or negative, **P/L % is `N/A`**: dividing by a nonpositive net cost does not produce a conventional return percentage. The P/L EUR amount remains meaningful under the stated accounting assumption.

**Missing quotes:** CoinMarketCap may send `null` for a price. Coinviewer warns with the coin symbol and CoinMarketCap ID, shows affected figures as `N/A`, and marks incomplete overall totals `N/A` rather than treating missing prices as zero. Missing assets and ambiguous ticker symbols are errors (use an ID).

The `TOTAL` line uses the sum of underlying, **unrounded** values; it is not the sum of the already rounded numbers displayed above it. Likewise, separate EUR and USD requests may be evaluated at slightly different instants.

A representative offline example (with **fictional** quotes, not live market data) is in [`examples/sample_output.txt`](examples/sample_output.txt).

## Tests

All tests use mock API responses; the test suite never needs a real API key or internet access.

```bash
python -m unittest discover -s tests -v
python -m py_compile coinviewer.py
```

The included GitHub Actions workflow runs the tests on every push and pull request.

## Troubleshooting

| Message | Action |
| --- | --- |
| `Set API_KEY in coinviewer.py` | Set the key in your **local copy** (`coinviewer.local.py`). |
| `Your plan is limited to 1 convert options` | The script already sends **separate** EUR and USD requests; make sure you are using this version. |
| `Ambiguous API result` | Replace the ticker with the correct CoinMarketCap ID in CSV. |
| `No CoinMarketCap quote` | Check the asset ID and whether CoinMarketCap lists it. |
| `Warning: No EUR/USD market price` | CoinMarketCap returned a null price; the affected numbers will be `N/A`. |
| `HTTP 401` or `HTTP 403` | Verify your key and API plan permissions. |
| `HTTP 429` | Check your CoinMarketCap rate limits / quota. |

API details: [CoinMarketCap Quotes Latest (V3)](https://coinmarketcap.com/api/documentation/pro-api-reference/cryptocurrency), [CoinMarketCap ID mapping](https://coinmarketcap.com/api/documentation/guides/standards-and-conventions/).

## Privacy, security and publishing

- Do **not** commit `coinviewer.local.py`, real API keys or personal portfolio CSV files. The provided `.gitignore` excludes the recommended local script and all CSV files except the fictional `examples/*.csv`.
- The CSV files under `examples/` are fictional and are safe to publish.
- The script sends requested asset identifiers and conversion currencies to CoinMarketCap. It does **not** upload your coin quantities or investment amounts.
- No external telemetry, database or cloud portfolio storage is included.

## License

No license has been selected for this project. **Choose and add a `LICENSE` file** (for example, MIT) if you want to explicitly permit others to reuse or modify your code. Publishing code on GitHub does not automatically grant an open-source license.
