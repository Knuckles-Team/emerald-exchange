# Concept Registry — emerald-exchange

> **Prefix**: `CONCEPT:EE-*`
> **Version**: 0.1.0
> **Bridge**: [`CONCEPT:AU-ECO.messaging.native-backend-abstraction`](https://github.com/Knuckles-Team/agent-utilities/blob/main/docs/concepts.md) (Unified Toolkit Ingestion)

---

## Project-Specific Concepts

| Concept ID | Name | Description |
|------------|------|-------------|
| `CONCEPT:AU-AHE.assimilation.autonomous-trading-ecosystem` | MCP Server | MCP entrypoint — action-routed finance tools with config.json backend resolution |
| `CONCEPT:EX-AHE.harness.ee` | Exchange Backend Protocol | Abstract `ExchangeBackend` protocol with factory registry pattern |
| `CONCEPT:EX-AHE.harness.ee-2` | Paper Backend | Full simulation backend — default for all new installations |
| `CONCEPT:EX-AHE.harness.ee-3` | Alpaca Backend | Alpaca Markets integration (equities + crypto, FREE paper trading) |
| `CONCEPT:EX-AHE.harness.ee-4` | CCXT Backend | CCXT multi-exchange crypto support (Binance, Coinbase, Kraken, 100+) |
| `CONCEPT:EX-AHE.harness.ee-5` | Freqtrade Backend | Freqtrade REST API strategy execution backend |
| `CONCEPT:EX-AHE.harness.ee-6` | Risk Guards | Pre-trade risk validation, circuit breakers, kill switch (OS-5.1) |
| `CONCEPT:EX-AHE.harness.ee-7` | Market Data Tools | MCP tool domain `market_data` — quote, historical, exchanges |
| `CONCEPT:EX-AHE.harness.ee-8` | Order Management Tools | MCP tool domain `orders` — submit, cancel, status, halt, resume |
| `CONCEPT:EX-AHE.harness.ee-9` | Portfolio Tools | MCP tool domain `portfolio` — positions, account |
| `CONCEPT:AU-AHE.assimilation.skill-workflow-ingest` | Risk Management Tools | MCP tool domain `risk` — drawdown_check, daily_loss_check, kelly, limits |
| `CONCEPT:EX-AHE.harness.ee-11` | Signal Generation Tools | MCP tool domain `signals` — regime, alpha, fuse |
| `CONCEPT:AU-AHE.assimilation.trading-ecosystem-spec` | Strategy Management Tools | MCP tool domain `strategy` — list, promote, export |
| `CONCEPT:EX-AHE.harness.ee-13` | Trading Mode Enum | Paper/Live mode gating with config-driven default |
| `CONCEPT:EX-AHE.harness.ee-14` | Kelly Criterion Sizing | Half-Kelly position sizing capped at configurable max_position_pct |
| `CONCEPT:EX-AHE.harness.ee-15` | Circuit Breaker Engine | Drawdown + daily loss + regime shift auto-halt system |
| `CONCEPT:EX-AHE.harness.ee-16` | Kill Switch | Emergency halt/resume lifecycle for all trading activity |
| `CONCEPT:EX-AHE.harness.ee-17` | Crypto-Native Analytics | `crypto` MCP domain: funding rates, whale alerts, arb scan via CCXT |
| `CONCEPT:EX-AHE.harness.ee-18` | Trading Debate Engine | `debate` MCP domain: multi-agent bull/bear debate with risk veto |
| `CONCEPT:EX-AHE.harness.ee-19` | A2A Server Integration | Native agent-to-agent interface via `agent_server.py` |
| `CONCEPT:EX-AHE.harness.ee-20` | Engine Client (lazy) | Lazy/cached `SyncEpistemicGraphClient` accessor; import never requires a running engine |
| `CONCEPT:EX-AHE.harness.ee-21` | Polymarket V2 Fee Model | Category-aware taker fee / maker rebate schedule (`fees.py`) |
| `CONCEPT:EX-AHE.harness.ee-22` | Market-Making Controller | Per-book-update quoting policy (microprice/OFI/AS/logit/VPIN gate); decision-only, never places orders (`market_making.py`) |
| `CONCEPT:EX-AHE.harness.ee-23` | Event-Driven Backtester | Heap event-loop with latency injection, L2 queue, fee accounting + deflated-Sharpe/CPCV/PBO validation hooks (`backtester.py`) |
| `CONCEPT:EX-AHE.harness.ee-24` | Production WebSocket Client | Polymarket market-channel subscriber: auto-reconnect, heartbeat watchdog, sequence-gap resync (`ws_client.py`) |
| `CONCEPT:EX-AHE.harness.ee-25` | Forensic Screener | Two-year Beneish/Altman/Piotroski/Sloan screen via engine `forensic_report` (`forensic.py`) |
| `CONCEPT:EX-AHE.harness.ee-26` | Fundamentals (SEC EDGAR) | `emerald_fundamentals` MCP domain: filings/financials/risk_factors/mdna/full_text_search/standardize + `forensic_screen` chaining standardize→engine `forensic_report` (`data/edgar.py`, optional `edgartools`) |
| `CONCEPT:EX-AHE.harness.ee-27` | Wallet Intelligence | `emerald_wallet_intel` MCP domain: Polymarket rank_wallets/wallet_profile/smart_money_convergence/exit_behavior over a `poly_data` trade dataset (`data/wallet_intel.py`, optional `polars`) |
| `CONCEPT:EX-AHE.harness.ee-28` | Dynamic-Beta Hedging | Time-varying CAPM Kalman-beta hedge: current beta + uncertainty band → beta-neutral hedge ratio via engine `kalman_beta` (EG-KG.domains.state-space-statistical-arbitrage). `hedging.py`; `emerald_statarb` action `dynamic_beta`. Decision-only |
| `CONCEPT:EX-AHE.harness.ee-29` | OU Statistical-Arbitrage Signal | Cross-venue spread → ADF stationarity gate → OU calibration + optimal thresholds → entry/exit signal via engine `adf_test`/`ou_calibrate`/`ou_optimal_thresholds` (EG-KG.domains.state-space-statistical-arbitrage). `stat_arb.py`; `emerald_statarb` action `ou_signal`. Decision-only |
| `CONCEPT:EX-AHE.harness.by-default` | Conviction Gate + Calibration | Convergence gate (engine `convergence_gate`, EG-KG.domains.quant-finance) wired ON by default into the market-making decision path (no N/N strong-signal agreement ⇒ withdraw); empirical-Kelly sizing (`empirical_kelly`) on `RiskGuard`; Brier calibration helper (`brier_score`). `market_making.py`/`risk_guards.py`; `emerald_market_making` action `brier`, `emerald_risk` action `empirical_kelly` |
| `CONCEPT:AU-AHE.assimilation.trading-ecosystem-changelog` | Execution Bridge | Routes a strategy/debate/optimizer `TradeDecision` (side/size/symbol/type/venue) to an `ExchangeBackend` behind the live-approval gate: paper executes freely, LIVE is BLOCKED while `require_human_approval_live` is set (returns `approval_required`), and every routed order still clears `RiskGuard.pre_trade_check`. Decision→action seam (`execution_bridge.py`) |
| `CONCEPT:AU-AHE.assimilation.microstructure-signal-fusion` | Live Cockpit (text-mode) | GUI-free cockpit rendering a structured snapshot + rich/plain table: engine status, account/positions, risk (kill-switch/drawdown/daily-loss), watchlist quotes, signals. Offline-safe (`engine: offline`). `emerald-cockpit` console script + `cockpit()` (`cockpit.py`) |
| `CONCEPT:AU-AHE.assimilation.decision-distillation` | SABR Volatility Surface | `emerald_derivatives` MCP domain delegating to engine SABR kernels (`sabr_implied_vol`/`sabr_smile`/`sabr_calibrate`, AU-KG.domains.derivatives): implied_vol/smile/calibrate + a decision-only `vol_arb` helper diffing market vs SABR-fair smile (rich/cheap strikes). `derivatives.py`; lazy/optional engine |
| `CONCEPT:EX-AHE.harness.bounded-autonomous-allows-small` | Paper-First Staged Execution | Execution-policy gating (`data/execution_policy.json`): default `paper` stage, human-only promotion (`RiskGuard.approve_stage` + token; the agent never self-escalates), and `evaluate_graduation` reporting paper→advisory→bounded_autonomous eligibility against policy thresholds. `risk_guards.py` |
| `CONCEPT:EX-AHE.harness.ee-31` | Kyle Insider/Stealth Surveillance Signal | `emerald_signals` action `surveillance` calling the engine `surveillance_risk` kernel (EG-KG.domains.concept-2, distils arXiv:2605.27684) → informed-flow/detection-hazard/legal-risk scores; registers a discoverable `MicrostructureSignal` whose priors are set later by `emerald_strategy` backtest (AU-AHE.assimilation.microstructure-signal-fusion). DEFENSIVE: informed-flow detection, not trade concealment. `mcp/mcp_signals.py` |
| `CONCEPT:EX-AHE.harness.sustained-adverse-selection` | Kyle Legal-Risk / Adverse-Selection Gate | Market-making `decide` always computes + surfaces the Kyle `legal_risk_score`/`informed_share` (engine `surveillance_risk`) and withdraws quotes when it exceeds `MMConfig.legal_risk_max` (default 1.0 ⇒ no-op until tightened); `RiskGuard.evaluate_graduation` blocks promotion on `max_legal_risk`. `market_making.py`/`risk_guards.py` |
| `CONCEPT:EX-AHE.harness.ee-32` | Insider Equilibrium under Dynamic Legal Risk | `emerald_signals` action `insider_equilibrium` routes to `agent_utilities.domains.finance.insider_equilibrium` (KG-2.6, distils arXiv:2605.27684 Qiao & Xia) — deepens the snapshot EX-AHE.harness.ee-31 surveillance score into the full continuous-time Kyle game: solves equilibrium trading intensity β*, the end-of-window acceleration schedule, and a penalty-policy verdict (criminal cost suppresses β* exactly; civil fines have diminishing, enforcement-gated effect). DEFENSIVE: surveillance/enforcement-design tool, not a concealment aid. `mcp/mcp_signals.py` |

## Cross-Project References (from agent-utilities)

| Concept ID | Name | Origin |
|------------|------|--------|
| `CONCEPT:AU-ECO.messaging.native-backend-abstraction` | Unified Toolkit Ingestion | agent-utilities |
| `CONCEPT:AU-ORCH.adapter.hot-cache-invalidation` | Confidence-Gated Router | agent-utilities |
| `CONCEPT:AU-OS.config.secrets-authentication` | Prompt Injection Defense / Financial Hardening | agent-utilities |
| `CONCEPT:AU-OS.state.cognitive-scheduler-preemption` | Cognitive Scheduler | agent-utilities |
| `CONCEPT:AU-OS.governance.reactive-multi-axis-budget` | Guardrail Engine | agent-utilities |
| `CONCEPT:AU-OS.governance.wasm-micro-agent-sandbox` | Audit Logging | agent-utilities |
| `CONCEPT:AU-KG.query.object-graph-mapper` | Knowledge Graph Core | agent-utilities |
| `CONCEPT:AU-KG.research.research-pipeline-runner` | Finance Domain | agent-utilities |

## Synergy with agent-utilities

This project integrates with `agent-utilities` via `CONCEPT:AU-ECO.messaging.native-backend-abstraction` (Unified Toolkit Ingestion). The `emerald_exchange` MCP server registers its tools with the agent-utilities FastMCP middleware, enabling automatic discovery, telemetry, and Knowledge Graph ingestion of all EE-* concepts.

**Finance Domain Integration**:
- Signal generation routes to `agent_utilities.domains.finance` (regime_detector, alpha_factors, signal_fusion)
- Strategy lifecycle uses `agent_utilities.domains.finance.strategy_engine`
- Heavy compute (qlib backtest, model training) routes to `data-science-mcp`
- Risk monitoring integrates with KG-native cron scheduling
