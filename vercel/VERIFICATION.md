# Verification — 23 October 2026

## Source preservation

The uploaded app.py was copied byte-for-byte to original_streamlit.py. A direct byte comparison passed. SOURCE_SHA256.txt records its SHA-256. Production executes that same source through a scoped Streamlit UI adapter. No model AST rewriting, JavaScript numerical rewrite, float precision reduction, simulation batching, or silent sample-count reduction is used.

## Numerical and transport regression tests

Command: `python -m pytest tests -q`

Result: **22 passed in 5.06 seconds** in Python 3.12.14 with NumPy 2.3.5, pandas 2.2.3, Plotly 5.24.1 and yfinance 0.2.66.

Coverage:
- Four scenarios, two seeds per scenario.
- Original program execution compared with the production scoped-import bridge, using identical fixed market data and NumPy random state.
- Full portfolio path arrays, daily returns, volatility/correlation, means, ADTV, risk parameters, stress covariance, final values, return distributions, VaR/CVaR quantities, loss probability, chart sample indices and classifier DataFrame.
- Exact equality (no numerical tolerance) for arrays; identical four displayed metric strings and four Plotly figure JSON objects.
- Vietnamese ticker benchmark branch, SPY download failure fallback and negative weights.
- Non-positive-definite covariance / eigenvalue repair branch.
- Maximum sliders: 252 days and 10,000 paths for a one-asset stress portfolio.
- Market cache expiry and cached random draw reuse.
- Invalid input validation, Flask HTTP/JSON transport and same-instance concurrency response.
- Checked representative JSON response sizes below 4.5 MB.

This is an execution/transport equivalence test, not an independent validation of the financial model. The exact original model is used as the reference. Test-only synthetic market data are confined to tests/ and are never substituted into the production app.

## Live data smoke test

A genuine yfinance request for JNJ, WMT and PG, normal scenario, 30 trading days and 1,000 paths completed successfully in the development environment. All four displayed metrics were returned. This was not a request from Vercel infrastructure and does not establish future Yahoo availability there.

## Browser checks

Automated Chromium test against a local Flask server with deterministic test market data:
- Initial automatic simulation; 101 traces in the path chart (100 sampled paths plus initial capital).
- Distribution and correlation tabs render.
- Classifier table has all three default tickers.
- Switching to Black Swan scenario triggers an updated result.
- Invalid zero-sum weights produce a visible error and hide stale results.
- Corrected inputs recover successfully.
- Desktop 1440 px and mobile 390 px layouts inspected.
- Fixed a mobile chart overflow and reran: passed, no JavaScript page errors, no page-level horizontal overflow.
- Python compile and JavaScript syntax checks passed.

## What is not established

- No deployment has been performed in the user's Vercel account; build success, account quotas, production routing and Yahoo access from that deployment still need the README smoke test.
- The old Streamlit deployment's dependency lockfile was not provided. Core dependency versions are pinned in this package, but identity with the old deployment's dependency environment cannot be asserted.
- Independent random runs or different Yahoo snapshots are not expected to produce the same numbers.
- Streamlit cache contents and cache lifetime across server restarts cannot be preserved across a hosting migration. The replacement cache is ephemeral per instance and bounded to 128 MiB.
- Unlimited ticker counts with maximum simulations are not guaranteed to fit the Hobby RAM/time limits. The original allocations and formulas are kept, not simplified to fit them.
