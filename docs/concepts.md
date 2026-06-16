# Concept Registry — emerald-exchange

> **Prefix**: `CONCEPT:EE-*`
> **Version**: 0.1.0
> **Bridge**: [`CONCEPT:ECO-4.0`](https://github.com/Knuckles-Team/agent-utilities/blob/main/docs/concepts.md) (Unified Toolkit Ingestion)

---

## Project-Specific Concepts

| Concept ID | Name | Description |
|------------|------|-------------|
| `CONCEPT:EE-001` | MCP Server | MCP entrypoint — action-routed finance tools with config.json backend resolution |
| `CONCEPT:EE-002` | Exchange Backend Protocol | Abstract `ExchangeBackend` protocol with factory registry pattern |
| `CONCEPT:EE-003` | Paper Backend | Full simulation backend — default for all new installations |
| `CONCEPT:EE-004` | Alpaca Backend | Alpaca Markets integration (equities + crypto, FREE paper trading) |
| `CONCEPT:EE-005` | CCXT Backend | CCXT multi-exchange crypto support (Binance, Coinbase, Kraken, 100+) |
| `CONCEPT:EE-006` | Freqtrade Backend | Freqtrade REST API strategy execution backend |
| `CONCEPT:EE-007` | Risk Guards | Pre-trade risk validation, circuit breakers, kill switch (OS-5.1) |
| `CONCEPT:EE-008` | Market Data Tools | MCP tool domain `market_data` — quote, historical, exchanges |
| `CONCEPT:EE-009` | Order Management Tools | MCP tool domain `orders` — submit, cancel, status, halt, resume |
| `CONCEPT:EE-010` | Portfolio Tools | MCP tool domain `portfolio` — positions, account |
| `CONCEPT:EE-011` | Risk Management Tools | MCP tool domain `risk` — drawdown_check, daily_loss_check, kelly, limits |
| `CONCEPT:EE-012` | Signal Generation Tools | MCP tool domain `signals` — regime, alpha, fuse |
| `CONCEPT:EE-013` | Strategy Management Tools | MCP tool domain `strategy` — list, promote, export |
| `CONCEPT:EE-014` | Trading Mode Enum | Paper/Live mode gating with config-driven default |
| `CONCEPT:EE-015` | Kelly Criterion Sizing | Half-Kelly position sizing capped at configurable max_position_pct |
| `CONCEPT:EE-016` | Circuit Breaker Engine | Drawdown + daily loss + regime shift auto-halt system |
| `CONCEPT:EE-017` | Kill Switch | Emergency halt/resume lifecycle for all trading activity |
| `CONCEPT:EE-018` | Crypto-Native Analytics | `crypto` MCP domain: funding rates, whale alerts, arb scan via CCXT |
| `CONCEPT:EE-019` | Trading Debate Engine | `debate` MCP domain: multi-agent bull/bear debate with risk veto |
| `CONCEPT:EE-020` | A2A Server Integration | Native agent-to-agent interface via `agent_server.py` |
| `CONCEPT:EE-021` | Engine Client (lazy) | Lazy/cached `SyncEpistemicGraphClient` accessor; import never requires a running engine |
| `CONCEPT:EE-022` | Polymarket V2 Fee Model | Category-aware taker fee / maker rebate schedule (`fees.py`) |
| `CONCEPT:EE-023` | Market-Making Controller | Per-book-update quoting policy (microprice/OFI/AS/logit/VPIN gate); decision-only, never places orders (`market_making.py`) |
| `CONCEPT:EE-024` | Event-Driven Backtester | Heap event-loop with latency injection, L2 queue, fee accounting + deflated-Sharpe/CPCV/PBO validation hooks (`backtester.py`) |
| `CONCEPT:EE-025` | Production WebSocket Client | Polymarket market-channel subscriber: auto-reconnect, heartbeat watchdog, sequence-gap resync (`ws_client.py`) |
| `CONCEPT:EE-026` | Forensic Screener | Two-year Beneish/Altman/Piotroski/Sloan screen via engine `forensic_report` (`forensic.py`) |
| `CONCEPT:EE-027` | Fundamentals (SEC EDGAR) | `emerald_fundamentals` MCP domain: filings/financials/risk_factors/mdna/full_text_search/standardize + `forensic_screen` chaining standardize→engine `forensic_report` (`data/edgar.py`, optional `edgartools`) |
| `CONCEPT:EE-028` | Wallet Intelligence | `emerald_wallet_intel` MCP domain: Polymarket rank_wallets/wallet_profile/smart_money_convergence/exit_behavior over a `poly_data` trade dataset (`data/wallet_intel.py`, optional `polars`) |
| `CONCEPT:EE-029` | Dynamic-Beta Hedging | Time-varying CAPM Kalman-beta hedge: current beta + uncertainty band → beta-neutral hedge ratio via engine `kalman_beta` (KG-2.20h). `hedging.py`; `emerald_statarb` action `dynamic_beta`. Decision-only |
| `CONCEPT:EE-030` | OU Statistical-Arbitrage Signal | Cross-venue spread → ADF stationarity gate → OU calibration + optimal thresholds → entry/exit signal via engine `adf_test`/`ou_calibrate`/`ou_optimal_thresholds` (KG-2.20h). `stat_arb.py`; `emerald_statarb` action `ou_signal`. Decision-only |
| `CONCEPT:EE-031` | Conviction Gate + Calibration | Convergence gate (engine `convergence_gate`, KG-2.20i) wired ON by default into the market-making decision path (no N/N strong-signal agreement ⇒ withdraw); empirical-Kelly sizing (`empirical_kelly`) on `RiskGuard`; Brier calibration helper (`brier_score`). `market_making.py`/`risk_guards.py`; `emerald_market_making` action `brier`, `emerald_risk` action `empirical_kelly` |
| `CONCEPT:EE-032` | Execution Bridge | Routes a strategy/debate/optimizer `TradeDecision` (side/size/symbol/type/venue) to an `ExchangeBackend` behind the live-approval gate: paper executes freely, LIVE is BLOCKED while `require_human_approval_live` is set (returns `approval_required`), and every routed order still clears `RiskGuard.pre_trade_check`. Decision→action seam (`execution_bridge.py`) |
| `CONCEPT:EE-033` | Live Cockpit (text-mode) | GUI-free cockpit rendering a structured snapshot + rich/plain table: engine status, account/positions, risk (kill-switch/drawdown/daily-loss), watchlist quotes, signals. Offline-safe (`engine: offline`). `emerald-cockpit` console script + `cockpit()` (`cockpit.py`) |
| `CONCEPT:EE-034` | SABR Volatility Surface | `emerald_derivatives` MCP domain delegating to engine SABR kernels (`sabr_implied_vol`/`sabr_smile`/`sabr_calibrate`, KG-2.20j): implied_vol/smile/calibrate + a decision-only `vol_arb` helper diffing market vs SABR-fair smile (rich/cheap strikes). `derivatives.py`; lazy/optional engine |
| `CONCEPT:EE-038` | Paper-First Staged Execution | Execution-policy gating (`data/execution_policy.json`): default `paper` stage, human-only promotion (`RiskGuard.approve_stage` + token; the agent never self-escalates), and `evaluate_graduation` reporting paper→advisory→bounded_autonomous eligibility against policy thresholds. `risk_guards.py` |
| `CONCEPT:EE-042` | Kyle Insider/Stealth Surveillance Signal | `emerald_signals` action `surveillance` calling the engine `surveillance_risk` kernel (KG-2.20k, distils arXiv:2605.27684) → informed-flow/detection-hazard/legal-risk scores; registers a discoverable `MicrostructureSignal` whose priors are set later by `emerald_strategy` backtest (EE-033). DEFENSIVE: informed-flow detection, not trade concealment. `mcp/mcp_signals.py` |
| `CONCEPT:EE-043` | Kyle Legal-Risk / Adverse-Selection Gate | Market-making `decide` always computes + surfaces the Kyle `legal_risk_score`/`informed_share` (engine `surveillance_risk`) and withdraws quotes when it exceeds `MMConfig.legal_risk_max` (default 1.0 ⇒ no-op until tightened); `RiskGuard.evaluate_graduation` blocks promotion on `max_legal_risk`. `market_making.py`/`risk_guards.py` |
| `CONCEPT:EE-044` | Insider Equilibrium under Dynamic Legal Risk | `emerald_signals` action `insider_equilibrium` routes to `agent_utilities.domains.finance.insider_equilibrium` (KG-2.6, distils arXiv:2605.27684 Qiao & Xia) — deepens the snapshot EE-042 surveillance score into the full continuous-time Kyle game: solves equilibrium trading intensity β*, the end-of-window acceleration schedule, and a penalty-policy verdict (criminal cost suppresses β* exactly; civil fines have diminishing, enforcement-gated effect). DEFENSIVE: surveillance/enforcement-design tool, not a concealment aid. `mcp/mcp_signals.py` |

## Cross-Project References (from agent-utilities)

| Concept ID | Name | Origin |
|------------|------|--------|
| `CONCEPT:ECO-4.0` | Unified Toolkit Ingestion | agent-utilities |
| `CONCEPT:ORCH-1.2` | Confidence-Gated Router | agent-utilities |
| `CONCEPT:OS-5.1` | Prompt Injection Defense / Financial Hardening | agent-utilities |
| `CONCEPT:OS-5.2` | Cognitive Scheduler | agent-utilities |
| `CONCEPT:OS-5.3` | Guardrail Engine | agent-utilities |
| `CONCEPT:OS-5.4` | Audit Logging | agent-utilities |
| `CONCEPT:KG-2.0` | Knowledge Graph Core | agent-utilities |
| `CONCEPT:KG-2.6` | Finance Domain | agent-utilities |

## Synergy with agent-utilities

This project integrates with `agent-utilities` via `CONCEPT:ECO-4.0` (Unified Toolkit Ingestion). The `emerald_exchange` MCP server registers its tools with the agent-utilities FastMCP middleware, enabling automatic discovery, telemetry, and Knowledge Graph ingestion of all EE-* concepts.

**Finance Domain Integration**:
- Signal generation routes to `agent_utilities.domains.finance` (regime_detector, alpha_factors, signal_fusion)
- Strategy lifecycle uses `agent_utilities.domains.finance.strategy_engine`
- Heavy compute (qlib backtest, model training) routes to `data-science-mcp`
- Risk monitoring integrates with KG-native cron scheduling
