#!/usr/bin/env python3
"""Show cryptocurrency portfolio values using CoinMarketCap market quotes.

CSV format (semicolon-delimited, with a header):
    Coin;Amount;Total investment EUR;Notes
    bitcoin;0.25;7500;Long-term holding
    BTC;0.10;3000;Additional information is ignored
    id:1027;2;4000

Only the first three columns are read; extra columns are ignored.

Identifiers: lowercase slugs, uppercase symbols, numeric CoinMarketCap IDs,
or explicit slug:/symbol:/id: prefixes. Bare PI is pinned to
CoinMarketCap ID 35697 (Pi Network); change SYMBOL_ID_OVERRIDES if needed.
By default, the third column is
NET invested EUR (purchases minus proceeds from sales) and may be negative.
Use --unit-cost if it contains the non-negative EUR cost per coin instead.
"""

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests
from tabulate import tabulate

API_KEY = "0000000000000000"  # Replace with your CoinMarketCap API key.
API_URL = "https://pro-api.coinmarketcap.com/v3/cryptocurrency/quotes/latest"
BATCH_SIZE = 100
CURRENCIES = ("EUR", "USD")
# Symbols may not be unique. This assumes PI means Pi Network (CMC ID 35697).
# If your PI asset is a different coin, update the ID or use id:<number> in the CSV.
SYMBOL_ID_OVERRIDES = {"PI": 35697}


class CoinviewerError(Exception):
    """A recoverable input or CoinMarketCap API error."""


@dataclass(frozen=True)
class Asset:
    kind: str
    value: str

    def __str__(self) -> str:
        return f"{self.kind}:{self.value}"


@dataclass(frozen=True)
class Holding:
    asset: Asset
    amount: Decimal
    investment_eur: Decimal


@dataclass(frozen=True)
class Quote:
    cmc_id: int
    symbol: str
    eur: Decimal | None
    usd: Decimal | None


def parse_asset(text: str) -> Asset:
    text = text.strip()
    if text in SYMBOL_ID_OVERRIDES:
        return Asset("id", str(SYMBOL_ID_OVERRIDES[text]))
    if ":" in text:
        kind, value = text.split(":", 1)
        kind, value = kind.lower(), value.strip()
    else:
        value = text
        kind = "id" if value.isdecimal() else "symbol" if value.isupper() else "slug"

    if kind == "id" and re.fullmatch(r"[1-9][0-9]*", value):
        return Asset(kind, value)
    if kind == "slug" and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value.lower()):
        return Asset(kind, value.lower())
    if kind == "symbol" and re.fullmatch(r"[A-Za-z0-9$@-]+", value):
        return Asset(kind, value.upper())
    raise CoinviewerError(f"Invalid coin identifier: {text!r}")


def parse_decimal(text: str, source: str, *, non_negative: bool = True) -> Decimal:
    try:
        value = Decimal(text.strip())
    except (InvalidOperation, AttributeError) as exc:
        raise CoinviewerError(f"Invalid number for {source}: {text!r}") from exc
    if not value.is_finite() or (non_negative and value < 0):
        requirement = "finite non-negative" if non_negative else "finite"
        raise CoinviewerError(f"Expected a {requirement} number for {source}: {text!r}")
    return value


def read_portfolio(path: Path, unit_cost: bool = False) -> list[Holding]:
    holdings = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, delimiter=";")
        if next(reader, None) is None:
            raise CoinviewerError(f"CSV file is empty: {path}")
        for line_number, row in enumerate(reader, start=2):
            if not any(cell.strip() for cell in row):
                continue
            if len(row) < 3:
                raise CoinviewerError(f"{path}:{line_number}: Expected at least three columns")
            coin, amount_text, investment_text = row[:3]
            source = f"{path}:{line_number}"
            asset = parse_asset(coin)
            amount = parse_decimal(amount_text, f"amount at {source}")
            investment = parse_decimal(
                investment_text, f"investment at {source}", non_negative=unit_cost
            )
            total_investment = amount * investment if unit_cost else investment
            holdings.append(Holding(asset, amount, total_investment))

    if not holdings:
        raise CoinviewerError(f"CSV contains no holdings: {path}")
    return holdings


def parse_price(item: dict, currency: str) -> Decimal | None:
    """A null price is valid in CMC responses; it is not a zero price."""
    conversions = item.get("quote")
    if not isinstance(conversions, list):
        raise CoinviewerError("Unexpected API response: 'quote' must be a list (v3 format)")
    for quote in conversions:
        if isinstance(quote, dict) and quote.get("symbol") == currency:
            price = quote.get("price")
            if price is None:
                return None
            return parse_decimal(
                str(price),
                f"{currency} market price for {item.get('symbol')} "
                f"(CMC ID {item.get('id')})",
            )
    raise CoinviewerError(f"No {currency} quote for {item.get('symbol', 'unknown coin')}")


def api_error_message(payload: object) -> str:
    """Extract the actionable CMC error message instead of only HTTP status."""
    if not isinstance(payload, dict):
        return ""
    status = payload.get("status")
    if isinstance(status, dict):
        message = status.get("error_message")
        if message:
            code = status.get("error_code")
            return f"{code}: {message}" if code is not None else str(message)
    return str(payload.get("message") or "")


def request_batch(
    session: requests.Session, kind: str, batch: list[str], currency: str
) -> list[dict]:
    """Request one currency per call, as required by lower-tier CMC plans."""
    params = {
        kind: ",".join(batch),
        "convert": currency,
        "skip_invalid": "true",
    }
    try:
        response = session.get(
            API_URL,
            headers={"X-CMC_PRO_API_KEY": API_KEY, "Accept": "application/json"},
            params=params,
            timeout=(5, 20),
        )
    except requests.RequestException as exc:
        raise CoinviewerError(f"CoinMarketCap connection failed for {kind}={params[kind]}: {exc}") from exc

    try:
        payload = response.json(parse_float=Decimal)
    except ValueError:
        payload = None

    if response.status_code >= 400:
        # Some identifiers can make an otherwise valid batch fail with HTTP 400.
        # Split only these failed batches. Never silently drop an asset.
        if response.status_code == 400 and len(batch) > 1:
            midpoint = len(batch) // 2
            return (request_batch(session, kind, batch[:midpoint], currency)
                    + request_batch(session, kind, batch[midpoint:], currency))
        detail = api_error_message(payload)
        if not detail:
            detail = " ".join(getattr(response, "text", "").split())[:250]
        detail = f": {detail}" if detail else ""
        raise CoinviewerError(
            f"CoinMarketCap HTTP {response.status_code} for "
            f"{kind}={params[kind]}{detail}"
        )

    if not isinstance(payload, dict):
        raise CoinviewerError("Unexpected CoinMarketCap response: expected JSON object")
    status = payload.get("status", {})
    if not isinstance(status, dict):
        raise CoinviewerError("Unexpected CoinMarketCap response: invalid status")
    # The V3 API may encode success as either 0 (int) or "0" (str).
    if str(status.get("error_code", 0)) != "0":
        raise CoinviewerError(
            f"CoinMarketCap error for {kind}={params[kind]}: "
            f"{api_error_message(payload) or 'Unknown API error'}"
        )
    data = payload.get("data")
    if not isinstance(data, list):
        raise CoinviewerError("Unexpected API response: 'data' must be a list (v3 format)")
    return data


def fetch_quotes(assets: set[Asset], session: requests.Session) -> dict[Asset, Quote]:
    """Fetch EUR and USD independently, then merge by asset and CoinMarketCap ID.

    Basic plans allow only one `convert` option per request. We still batch
    coins together, so a portfolio of up to 100 coins of the same identifier
    type needs only two requests (one for each currency).
    """
    result: dict[Asset, Quote] = {}
    for kind in ("id", "slug", "symbol"):
        values = sorted(asset.value for asset in assets if asset.kind == kind)
        for offset in range(0, len(values), BATCH_SIZE):
            batch = values[offset:offset + BATCH_SIZE]
            prices: dict[Asset, dict[str, tuple[int, str, Decimal | None]]] = {}

            for currency in CURRENCIES:
                for item in request_batch(session, kind, batch, currency):
                    if not isinstance(item, dict):
                        raise CoinviewerError("Unexpected API response: invalid coin record")
                    identifier = str(item.get(kind, ""))
                    if kind == "symbol":
                        identifier = identifier.upper()
                    elif kind == "slug":
                        identifier = identifier.lower()
                    if identifier not in batch:
                        continue

                    asset = Asset(kind, identifier)
                    cmc_id = item.get("id")
                    if type(cmc_id) is not int or cmc_id <= 0:
                        raise CoinviewerError(f"Unexpected CoinMarketCap ID for {asset}")
                    by_currency = prices.setdefault(asset, {})
                    if currency in by_currency:
                        previous_id = by_currency[currency][0]
                        if previous_id == cmc_id:
                            continue
                        raise CoinviewerError(
                            f"Ambiguous API result for {asset}: CMC IDs "
                            f"{previous_id} and {cmc_id}. Use id:<correct_id> "
                            "in your CSV to select the intended cryptocurrency."
                        )
                    by_currency[currency] = (
                        cmc_id, str(item.get("symbol", identifier)), parse_price(item, currency)
                    )

            for asset, by_currency in prices.items():
                absent = [currency for currency in CURRENCIES if currency not in by_currency]
                if absent:
                    raise CoinviewerError(
                        f"No {', '.join(absent)} quote for {asset}; "
                        "the two currency requests returned different assets"
                    )
                eur_id, symbol, eur = by_currency["EUR"]
                usd_id, _, usd = by_currency["USD"]
                if eur_id != usd_id:
                    raise CoinviewerError(
                        f"CoinMarketCap returned different assets for {asset} "
                        "in EUR and USD; use its unique CoinMarketCap ID in the CSV"
                    )
                result[asset] = Quote(eur_id, symbol, eur, usd)

    # Merge holdings that refer to the same underlying asset by different names.
    by_id: dict[int, Quote] = {}
    for asset, quote in result.items():
        result[asset] = by_id.setdefault(quote.cmc_id, quote)

    missing = assets - result.keys()
    if missing:
        missing_names = ", ".join(map(str, sorted(missing, key=str)))
        raise CoinviewerError(
            f"No CoinMarketCap quote for: {missing_names}. "
            "Check the symbols or use explicit CoinMarketCap IDs (id:12345)."
        )
    return result


def format_number(value: Decimal, places: int) -> str:
    """Format only the output in German notation; keep calculations precise."""
    return f"{value:,.{places}f}".translate(str.maketrans(".,", ",."))


def format_variable(value: Decimal, *, min_places: int = 2, max_places: int = 6) -> str:
    """Show up to six decimals, omitting trailing zeros but keeping at least two."""
    integer, fraction = f"{value:,.{max_places}f}".split(".")
    fraction = fraction.rstrip("0").ljust(min_places, "0")
    return f"{integer}.{fraction}".translate(str.maketrans(".,", ",."))


def format_money(value: Decimal) -> str:
    return format_number(value, 2)


def format_price(value: Decimal | None) -> str:
    """Show extra price decimals only for positive prices below one cent."""
    if value is None:
        return "N/A"
    return format_variable(value) if 0 < value < Decimal("0.01") else format_money(value)


def format_percent(numerator: Decimal, denominator: Decimal) -> str:
    # ROI percentages are not meaningful for zero or negative net investment.
    return format_number(numerator / denominator * 100, 2) if denominator > 0 else "N/A"


def portfolio_table(holdings: list[Holding], quotes: dict[Asset, Quote]) -> str:
    positions = []
    for holding in holdings:
        quote = quotes[holding.asset]
        eur = holding.amount * quote.eur if quote.eur is not None else None
        usd = holding.amount * quote.usd if quote.usd is not None else None
        positions.append((holding, quote, eur, usd))

    # Unknown values sort last; never interpret a missing market price as zero.
    positions.sort(key=lambda position: (position[2] is not None,
                                         position[2] if position[2] is not None else 0),
                   reverse=True)
    invested = sum((holding.investment_eur for holding, _, _, _ in positions), Decimal(0))
    total_eur = (sum((eur for _, _, eur, _ in positions), Decimal(0))
                 if all(eur is not None for _, _, eur, _ in positions) else None)
    total_usd = (sum((usd for _, _, _, usd in positions), Decimal(0))
                 if all(usd is not None for _, _, _, usd in positions) else None)

    def money(value: Decimal | None) -> str:
        return format_money(value) if value is not None else "N/A"

    rows = []
    for holding, quote, eur, usd in positions:
        profit = eur - holding.investment_eur if eur is not None else None
        rows.append([
            quote.symbol, format_price(quote.eur), format_price(quote.usd),
            format_variable(holding.amount), format_money(holding.investment_eur),
            money(eur), money(usd), money(profit),
            format_percent(profit, holding.investment_eur) if profit is not None else "N/A",
            format_percent(eur, total_eur) if eur is not None and total_eur else "N/A",
        ])

    total_profit = total_eur - invested if total_eur is not None else None
    rows.append([
        "TOTAL", "", "", "", format_money(invested), money(total_eur),
        money(total_usd), money(total_profit),
        format_percent(total_profit, invested) if total_profit is not None else "N/A",
        "100,00" if total_eur else "0,00" if total_eur == 0 else "N/A",
    ])
    headers = ["Coin", "EUR price", "USD price", "Amount", "Invested EUR",
               "Value EUR", "Value USD", "P/L EUR", "P/L %", "Share %"]
    return tabulate(rows, headers=headers, tablefmt="github", disable_numparse=True)


def combine_holdings(portfolios: list[list[Holding]],
                     quotes: dict[Asset, Quote]) -> list[Holding]:
    combined: dict[int, Holding] = {}
    for holdings in portfolios:
        for holding in holdings:
            cmc_id = quotes[holding.asset].cmc_id
            previous = combined.get(cmc_id)
            combined[cmc_id] = Holding(
                previous.asset if previous else holding.asset,
                holding.amount + previous.amount if previous else holding.amount,
                (holding.investment_eur + previous.investment_eur
                 if previous else holding.investment_eur),
            )
    return list(combined.values())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_files", nargs="*", type=Path,
                        help="Portfolio CSV files (default: portfolio.csv next to this script)")
    parser.add_argument("--unit-cost", action="store_true",
                        help="Interpret the third CSV column as EUR purchase price per coin")
    args = parser.parse_args(argv)
    paths = args.csv_files or [Path(__file__).with_name("portfolio.csv")]

    try:
        if API_KEY == "0000000000000000":
            raise CoinviewerError("Set API_KEY in coinviewer.py before requesting live quotes")
        portfolios = [read_portfolio(path, args.unit_cost) for path in paths]
        assets = {holding.asset for portfolio in portfolios for holding in portfolio}
        with requests.Session() as session:
            quotes = fetch_quotes(assets, session)
        for quote in sorted({q.cmc_id: q for q in quotes.values()}.values(),
                            key=lambda item: item.symbol):
            missing = [currency for currency in CURRENCIES
                       if getattr(quote, currency.lower()) is None]
            if missing:
                print(f"Warning: No {', '.join(missing)} market price for "
                      f"{quote.symbol} (CMC ID {quote.cmc_id}). "
                      "Affected values and totals are shown as N/A, not zero.",
                      file=sys.stderr)
        for path, holdings in zip(paths, portfolios):
            merged = combine_holdings([holdings], quotes)
            print(f"\nPortfolio: {path}\n{portfolio_table(merged, quotes)}")
        if len(portfolios) > 1:
            merged = combine_holdings(portfolios, quotes)
            print(f"\nCombined portfolios\n{portfolio_table(merged, quotes)}")
    except (CoinviewerError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
