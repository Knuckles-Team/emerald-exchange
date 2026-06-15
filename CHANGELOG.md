# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Kyle insider/stealth surveillance signal (CONCEPT:EE-042).** `emerald_signals`
  action `surveillance` calls the engine `surveillance_risk` kernel (KG-2.20k,
  distilling arXiv:2605.27684) and returns informed-flow / detection-hazard /
  legal-risk scores, registering a discoverable `MicrostructureSignal` whose
  priors are written later by an `emerald_strategy` backtest (EE-033 loop).
- **Kyle legal-risk / adverse-selection gate (CONCEPT:EE-043).**
  `MarketMakingController.decide` always computes and surfaces
  `legal_risk_score`/`informed_share` and withdraws quotes above
  `MMConfig.legal_risk_max` (default 1.0 ⇒ behavior-safe no-op until tightened);
  `RiskGuard.evaluate_graduation` blocks stage promotion on `max_legal_risk`.
  Defensive detection + maker protection only; decision-only, never places orders.
- Documented previously-unregistered **CONCEPT:EE-038** (paper-first staged
  execution) in `docs/concepts.md`.

## [0.1.0] - 2026-05-23

### Added
- Initial release of emerald-exchange
- Exchange backend protocol with 5 implementations (Paper, Alpaca, CCXT, Freqtrade)
- 6 MCP tool domains (market-data, orders, portfolio, risk, signals, strategy)
- OS-5.1 financial hardening: Kelly criterion, circuit breakers, kill switch
- Full docs: index.md, overview.md, concepts.md (17 CONCEPT:EE-* IDs)
- Docker infrastructure (Dockerfile, compose.yml)
- Config-driven setup via `~/.config/agent-utilities/config.json`
