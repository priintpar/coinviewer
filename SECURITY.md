# Security and privacy

The template intentionally leaves `API_KEY` hardcoded as a placeholder in the tracked `coinviewer.py`.

- **Never commit a real API key.** Copy the script to `coinviewer.local.py` (ignored by Git), then put the real key in that local copy.
- **Never commit real portfolio CSV files.** By default `.gitignore` excludes all CSV files outside `examples/`; the examples use fictitious amounts and investment values.
- Treat any leaked key as compromised: revoke/rotate it in CoinMarketCap and check Git history.
- `.gitignore` does not hide changes in files that Git already tracks.
- Keep dependencies current and run offline unit tests before releasing changes.

The application sends asset identifiers and requested currencies to CoinMarketCap, not private portfolio amounts or cost bases.
