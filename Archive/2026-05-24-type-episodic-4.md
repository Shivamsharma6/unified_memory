---
type: episodic
date: '2026-05-24'
updated: '2026-05-24T08:03:29.025561+00:00'
tags: []
lifecycle: archived
importance: 0.3375874865420475
---
# Distilled Summary
TradePilot is an AI-powered pump detection and trading assistant for INDmoney US stocks, aiming to grow $450 to $2,700 over 12 months. Key decisions include utilizing a multi-source data stack (Alpaca, Yahoo, NewsAPI, Reddit, SEC) and adhering to PDT limits of 2 day trades per week plus one emergency reserve. To resolve platform limitations where INDmoney lacks pre/post market execution, Yahoo data is used for signals only. Regulatory compliance ensures no options or futures are traded. Risk management protocols include a default same-day exit before 3:55 PM ET, a three-gate system for overnight holds, and reduced position sizes (40% smaller) for first-time pumps scoring $\ge$ 85.

## Raw Logs
# TradePilot is an AI-powered pump detection and trading assistant for INDmoney US

## Summary
TradePilot is an AI-powered pump detection and trading assistant for INDmoney US stocks. Starting capital: $450, target: $2,700 in 12 months. Located at /Users/shivamsharma/projects/TradePilot/.

Stack: alpaca-py (market data + paper trading), yfinance (pre/post market data), Anthropic Claude API (AI reasoning), Telegram Bot API (phone alerts), NewsAPI (news detection), Reddit JSON (social scanning), SEC EDGAR (filing scanner), Finviz (screener), SQLite (local storage), pandas/numpy/scipy (data processing), schedule (scanning), python-dotenv.

Key rules: PDT max 2 day trades/week + 1 emergency reserve. INDmoney has no pre/post market execution (Yahoo data used as signal only). No options/futures (RBI LRS blocks Indian residents). Default exit: same day before 3:55 PM ET. Overnight requires 3 gates. First-time pumps score >= 85 with 40% smaller position.

Monthly cost: ~$3-5 (Claude API only) or ~$12-14 (with Alpaca SIP for extended hours).