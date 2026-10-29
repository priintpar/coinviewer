"""Offline tests for CSV parsing, financial maths, formatting and CMC V3 calls."""

import contextlib
import io
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import requests

import coinviewer as cv


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.body = json.dumps(payload)
        self.status_code = status_code
        self.text = self.body

    def json(self, *, parse_float=float):
        return json.loads(self.body, parse_float=parse_float)


class FakeSession:
    """Return a predetermined response for each request; never touch the network."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("Unexpected extra HTTP request")
        response = self.responses.pop(0)
        return response if isinstance(response, FakeResponse) else FakeResponse(response)


def item(cmc_id, symbol, slug, currency, price):
    return {
        "id": cmc_id,
        "symbol": symbol,
        "slug": slug,
        "quote": [{"symbol": currency, "price": price}],
    }


def success(*items, error_code="0"):
    return {"status": {"error_code": error_code}, "data": list(items)}


def quote_session(cmc_id=1, symbol="BTC", slug="bitcoin", eur="123.456789123456", usd="130.99"):
    return FakeSession(
        success(item(cmc_id, symbol, slug, "EUR", eur)),
        success(item(cmc_id, symbol, slug, "USD", usd)),
    )


class CsvTests(unittest.TestCase):
    def test_csv_ignores_extra_columns_and_quoted_semicolons(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "portfolio.csv"
            path.write_text(
                'Coin;Amount;Investment;Notes;More\n'
                'id:1;0.250001;1250.500;"long;term";discard\n'
                'id:1027;1.5;-250;"sold;some";discard\n',
                encoding="utf-8-sig",
            )
            rows = cv.read_portfolio(path)
        self.assertEqual([r.asset for r in rows], [cv.Asset("id", "1"), cv.Asset("id", "1027")])
        self.assertEqual(rows[0].amount, Decimal("0.250001"))
        self.assertEqual(rows[0].investment_eur, Decimal("1250.500"))
        self.assertEqual(rows[1].investment_eur, Decimal("-250"))

    def test_csv_accepts_more_than_three_columns_but_not_fewer(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "file.csv"
            path.write_text("Coin;Amount;Investment;Tag\nid:1;1\n", encoding="utf-8")
            with self.assertRaisesRegex(cv.CoinviewerError, "at least three columns"):
                cv.read_portfolio(path)

    def test_empty_csv_and_only_header_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "empty.csv"
            for content in ("", "Coin;Amount;Investment\n\n"):
                with self.subTest(content=content):
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaises(cv.CoinviewerError):
                        cv.read_portfolio(path)

    def test_blank_rows_are_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "file.csv"
            path.write_text("Coin;Amount;Investment\n\nid:1;2;100\n ; ; \n", encoding="utf-8")
            self.assertEqual(len(cv.read_portfolio(path)), 1)

    def test_unit_cost_multiplies_amount_by_per_coin_cost(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "file.csv"
            path.write_text("Coin;Amount;Price\nid:1;2.5;7.1234\n", encoding="utf-8")
            rows = cv.read_portfolio(path, unit_cost=True)
        self.assertEqual(rows[0].investment_eur, Decimal("17.80850"))

    def test_unit_cost_rejects_negative_cost(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "file.csv"
            path.write_text("Coin;Amount;Price\nid:1;1;-5\n", encoding="utf-8")
            with self.assertRaisesRegex(cv.CoinviewerError, "non-negative"):
                cv.read_portfolio(path, unit_cost=True)

    def test_negative_amount_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "file.csv"
            path.write_text("Coin;Amount;Investment\nid:1;-0.3;100\n", encoding="utf-8")
            with self.assertRaisesRegex(cv.CoinviewerError, "amount"):
                cv.read_portfolio(path)

    def test_invalid_numbers(self):
        for bad in ("NaN", "Infinity", "-Infinity", "garbage", "1,234"):
            with self.subTest(value=bad):
                with self.assertRaises(cv.CoinviewerError):
                    cv.parse_decimal(bad, "test")

    def test_identifiers(self):
        expected = {
            "1": cv.Asset("id", "1"),
            "id:1027": cv.Asset("id", "1027"),
            "BTC": cv.Asset("symbol", "BTC"),
            "symbol:btc": cv.Asset("symbol", "BTC"),
            "bitcoin": cv.Asset("slug", "bitcoin"),
            "slug:Pi-network": cv.Asset("slug", "pi-network"),
            "PI": cv.Asset("id", "35697"),
        }
        for raw, asset in expected.items():
            with self.subTest(raw=raw):
                self.assertEqual(cv.parse_asset(raw), asset)

    def test_invalid_ids_are_rejected(self):
        for value in ("id:0", "id:-5", "id:", "bitcoin coin", "symbol:"):
            with self.subTest(value=value), self.assertRaises(cv.CoinviewerError):
                cv.parse_asset(value)

    def test_missing_csv_raises_os_error(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(OSError):
                cv.read_portfolio(Path(folder) / "missing.csv")


class FormattingTests(unittest.TestCase):
    def test_prices_at_or_above_one_cent_have_two_decimals(self):
        for raw, expected in (
            ("1234567.8912", "1.234.567,89"),
            ("0.01000001", "0,01"),
            ("0.01", "0,01"),
            ("1.234567", "1,23"),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(cv.format_price(Decimal(raw)), expected)

    def test_prices_below_cent_show_up_to_six_decimals(self):
        for raw, expected in (
            ("0.009999", "0,009999"),
            ("0.0012300", "0,00123"),
            ("0.000001", "0,000001"),
            ("0.005", "0,005"),
            ("0.0000006", "0,000001"),
            ("0", "0,00"),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(cv.format_price(Decimal(raw)), expected)
        self.assertEqual(cv.format_price(None), "N/A")

    def test_amount_has_minimum_two_maximum_six_decimals(self):
        for raw, expected in (
            ("1", "1,00"),
            ("1.20", "1,20"),
            ("1000.002030", "1.000,00203"),
            ("1.123456789", "1,123457"),
            ("0.000001", "0,000001"),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(cv.format_variable(Decimal(raw)), expected)

    def test_negative_eur_and_percent_use_german_separators(self):
        self.assertEqual(cv.format_money(Decimal("-12345.678")), "-12.345,68")
        self.assertEqual(cv.format_percent(Decimal("-5"), Decimal("100")), "-5,00")
        self.assertEqual(cv.format_percent(Decimal("2"), Decimal("0")), "N/A")
        self.assertEqual(cv.format_percent(Decimal("2"), Decimal("-1")), "N/A")

    def test_rounding_is_display_only(self):
        price = Decimal("0.009999999999999999999999")
        holding = cv.Holding(cv.Asset("id", "1"), Decimal("1000000"), Decimal("0"))
        quote = cv.Quote(1, "BTC", price, Decimal("1"))
        self.assertEqual(cv.format_price(price), "0,01")
        self.assertIn("10.000,00", cv.portfolio_table([holding], {holding.asset: quote}))
        self.assertEqual(price * holding.amount, Decimal("9999.999999999999999999000000"))


class FinanceTests(unittest.TestCase):
    def test_negative_investment_profit_is_positive_and_roi_na(self):
        asset = cv.Asset("id", "1")
        row = cv.Holding(asset, Decimal("2"), Decimal("-400"))
        table = cv.portfolio_table([row], {asset: cv.Quote(1, "BTC", Decimal("300"), Decimal("350"))})
        self.assertIn("-400,00", table)
        self.assertIn("1.000,00", table)
        btc = next(line for line in table.splitlines() if line.startswith("| BTC"))
        self.assertEqual([c.strip() for c in btc.strip("|").split("|")][8], "N/A")

    def test_missing_eur_prevents_misleading_totals(self):
        asset = cv.Asset("id", "1")
        table = cv.portfolio_table(
            [cv.Holding(asset, Decimal("1"), Decimal("100"))],
            {asset: cv.Quote(1, "BTC", None, Decimal("10"))},
        )
        rows = [line for line in table.splitlines() if line.startswith("| BTC") or line.startswith("| TOTAL")]
        self.assertEqual(len(rows), 2)
        self.assertIn("N/A", rows[0])
        self.assertIn("N/A", rows[1])
        self.assertIn("10,00", rows[1])

    def test_missing_usd_does_not_destroy_eur_total(self):
        asset = cv.Asset("id", "1")
        table = cv.portfolio_table(
            [cv.Holding(asset, Decimal("2"), Decimal("25"))],
            {asset: cv.Quote(1, "BTC", Decimal("20"), None)},
        )
        self.assertIn("40,00", table)
        self.assertIn("N/A", table)

    def test_same_cmc_id_is_merged_in_combined_portfolio(self):
        a = cv.Asset("id", "1")
        b = cv.Asset("slug", "bitcoin")
        q = cv.Quote(1, "BTC", Decimal("20"), Decimal("22"))
        combined = cv.combine_holdings(
            [
                [cv.Holding(a, Decimal("1"), Decimal("200"))],
                [cv.Holding(b, Decimal("2"), Decimal("-50"))],
            ],
            {a: q, b: q},
        )
        self.assertEqual(len(combined), 1)
        self.assertEqual(combined[0].amount, Decimal("3"))
        self.assertEqual(combined[0].investment_eur, Decimal("150"))

    def test_total_allocation_is_100_when_portfolio_has_value(self):
        a, b = cv.Asset("id", "1"), cv.Asset("id", "1027")
        holdings = [cv.Holding(a, Decimal("2"), Decimal("10")), cv.Holding(b, Decimal("1"), Decimal("20"))]
        quotes = {a: cv.Quote(1, "BTC", Decimal("40"), Decimal("50")),
                  b: cv.Quote(1027, "ETH", Decimal("20"), Decimal("25"))}
        table = cv.portfolio_table(holdings, quotes)
        self.assertIn("80,00", table)
        self.assertIn("20,00", table)
        self.assertIn("100,00", next(line for line in table.splitlines() if line.startswith("| TOTAL")))


class ApiTests(unittest.TestCase):
    def test_eur_and_usd_are_two_separate_requests(self):
        session = quote_session()
        asset = cv.Asset("id", "1")
        with patch.object(cv, "API_KEY", "offline-test-key"):
            quotes = cv.fetch_quotes({asset}, session)
        self.assertEqual(quotes[asset].eur, Decimal("123.456789123456"))
        self.assertEqual(quotes[asset].usd, Decimal("130.99"))
        self.assertEqual(len(session.calls), 2)
        self.assertEqual([call[1]["params"]["convert"] for call in session.calls], ["EUR", "USD"])
        for url, request in session.calls:
            self.assertEqual(url, cv.API_URL)
            self.assertEqual(request["params"]["id"], "1")
            self.assertEqual(request["headers"]["X-CMC_PRO_API_KEY"], "offline-test-key")
            self.assertNotIn("offline-test-key", str(request["params"]))
            self.assertEqual(request["timeout"], (5, 20))
        self.assertNotIn("offline-test-key", session.calls[0][0])

    def test_null_price_is_accepted_but_not_zeroed(self):
        session = quote_session(eur=None)
        quote = cv.fetch_quotes({cv.Asset("id", "1")}, session)[cv.Asset("id", "1")]
        self.assertIsNone(quote.eur)
        self.assertEqual(quote.usd, Decimal("130.99"))

    def test_invalid_price_is_rejected(self):
        for bad in (-1, "NaN", "Infinity", "abc"):
            with self.subTest(price=bad):
                session = quote_session(eur=bad)
                with self.assertRaises(cv.CoinviewerError):
                    cv.fetch_quotes({cv.Asset("id", "1")}, session)

    def test_ambiguous_symbol_is_rejected(self):
        session = FakeSession(success(
            item(1, "XXX", "one", "EUR", 1),
            item(42, "XXX", "two", "EUR", 2),
        ))
        with self.assertRaisesRegex(cv.CoinviewerError, "Ambiguous"):
            cv.fetch_quotes({cv.Asset("symbol", "XXX")}, session)

    def test_missing_asset_is_rejected(self):
        session = FakeSession(success(), success())
        with self.assertRaisesRegex(cv.CoinviewerError, "No CoinMarketCap quote"):
            cv.fetch_quotes({cv.Asset("id", "123456")}, session)

    def test_mismatched_cmc_ids_across_currencies_rejected(self):
        session = FakeSession(
            success(item(1, "ABC", "abc", "EUR", 1)),
            success(item(42, "ABC", "abc", "USD", 2)),
        )
        with self.assertRaisesRegex(cv.CoinviewerError, "different assets"):
            cv.fetch_quotes({cv.Asset("symbol", "ABC")}, session)

    def test_unauthorized_and_quota_errors_include_details(self):
        for code, message in ((401, "API key invalid"), (429, "rate limit exceeded")):
            session = FakeSession(FakeResponse({"status": {"error_code": 1000, "error_message": message}}, code))
            with self.subTest(code=code), self.assertRaisesRegex(cv.CoinviewerError, message):
                cv.fetch_quotes({cv.Asset("id", "1")}, session)

    def test_bad_batch_splits_and_reveals_problem_id(self):
        bad = FakeResponse({"status": {"error_code": 400, "error_message": "invalid ID"}}, 400)
        session = FakeSession(bad, success(item(1, "BTC", "bitcoin", "EUR", 1)), bad)
        with self.assertRaisesRegex(cv.CoinviewerError, "id=2: 400: invalid ID"):
            cv.fetch_quotes({cv.Asset("id", "1"), cv.Asset("id", "2")}, session)
        self.assertEqual(len(session.calls), 3)

    def test_success_with_integer_status_code(self):
        session = FakeSession(
            success(item(1, "BTC", "bitcoin", "EUR", 10), error_code=0),
            success(item(1, "BTC", "bitcoin", "USD", 11), error_code=0),
        )
        self.assertEqual(cv.fetch_quotes({cv.Asset("id", "1")}, session)[cv.Asset("id", "1")].usd, Decimal("11"))

    def test_nonzero_api_status_code_is_rejected(self):
        session = FakeSession(FakeResponse({"status": {"error_code": 1002, "error_message": "Invalid key"}, "data": []}))
        with self.assertRaisesRegex(cv.CoinviewerError, "Invalid key"):
            cv.fetch_quotes({cv.Asset("id", "1")}, session)

    def test_invalid_data_shape_is_rejected(self):
        session = FakeSession({"status": {"error_code": 0}, "data": {"1": {}}})
        with self.assertRaisesRegex(cv.CoinviewerError, "must be a list"):
            cv.fetch_quotes({cv.Asset("id", "1")}, session)

    def test_timeout_is_reported(self):
        class TimeoutSession:
            def get(self, *_args, **_kwargs):
                raise requests.Timeout("Timed out")

        with self.assertRaisesRegex(cv.CoinviewerError, "Timed out"):
            cv.fetch_quotes({cv.Asset("id", "1")}, TimeoutSession())

    def test_multi_coin_batch_reduces_requests(self):
        session = FakeSession(
            success(item(1, "BTC", "bitcoin", "EUR", 10), item(1027, "ETH", "ethereum", "EUR", 20)),
            success(item(1, "BTC", "bitcoin", "USD", 11), item(1027, "ETH", "ethereum", "USD", 21)),
        )
        quotes = cv.fetch_quotes({cv.Asset("id", "1"), cv.Asset("id", "1027")}, session)
        self.assertEqual(len(quotes), 2)
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(session.calls[0][1]["params"]["id"], "1,1027")

    def test_end_to_end_offline_two_portfolios(self):
        with tempfile.TemporaryDirectory() as folder:
            first = Path(folder) / "first.csv"
            second = Path(folder) / "second.csv"
            first.write_text("Coin;Amount;Investment;Notes\nid:1;2;100;test\n", encoding="utf-8")
            second.write_text("Coin;Amount;Investment;Notes\nid:1;1;-50;test\n", encoding="utf-8")
            session = FakeSession(
                success(item(1, "BTC", "bitcoin", "EUR", "80.123456789")),
                success(item(1, "BTC", "bitcoin", "USD", "90")),
            )
            stdout = io.StringIO()
            with patch.object(cv, "API_KEY", "test-key"), \
                 patch.object(cv.requests, "Session", return_value=session), \
                 contextlib.redirect_stdout(stdout):
                result = cv.main([str(first), str(second)])
        self.assertEqual(result, 0)
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(stdout.getvalue().count("| TOTAL"), 3)
        self.assertIn("Combined portfolios", stdout.getvalue())
        self.assertIn("240,37", stdout.getvalue())
        self.assertIn("50,00", stdout.getvalue())

    def test_main_rejects_placeholder_key(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(cv.main(["does_not_need_to_exist.csv"]), 1)
        self.assertIn("Set API_KEY", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
