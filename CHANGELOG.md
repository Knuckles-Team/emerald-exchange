# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-23

### Added
- Initial release of emerald-exchange
- Exchange backend protocol with 5 implementations (Paper, Alpaca, CCXT, Freqtrade)
- 6 MCP tool domains (market-data, orders, portfolio, risk, signals, strategy)
- OS-5.1 financial hardening: Kelly criterion, circuit breakers, kill switch
- Full docs: index.md, overview.md, concepts.md (17 CONCEPT:EE-* IDs)
- Docker infrastructure (Dockerfile, compose.yml)
- Config-driven setup via `~/.config/agent-utilities/config.json`
