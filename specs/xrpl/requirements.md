# CONN-EMERALD-EXCHANGE-XRPL — Requirements

Governing spec: [spec.md](spec.md).

Each row is one requirement. A row names the file it touches and the test that proves it. The generator sets each row's state in `status.json`.

| ID | Requirement | Acceptance |
|---|---|---|
| `CONN-EMERALD-EXCHANGE-XRPL-R001` | **Agent wallet create, load and sign.** The connector creates an XRPL agent wallet, loads one by address reference, and signs transactions. Every signature previews first; scoped auto-sign applies only inside the approved scope. The test network is the default. | `tests/test_xrpl_wallet.py::test_wallet_create_load_sign_preview` |
| `CONN-EMERALD-EXCHANGE-XRPL-R002` | **XRP and RLUSD payments.** The connector sends XRP payments and RLUSD payments from the agent wallet. Each payment reports fee, destination and ledger result. | `tests/test_xrpl_payments.py::test_xrp_and_rusd_payments` |
| `CONN-EMERALD-EXCHANGE-XRPL-R003` | **Trust lines.** The connector sets, raises and removes issuer trust lines and reads each current limit and balance. RLUSD flows need the issuer trust line first. | `tests/test_xrpl_trust_lines.py::test_trust_line_lifecycle` |
| `CONN-EMERALD-EXCHANGE-XRPL-R004` | **Escrow-gated work.** The connector escrows funds against a work order. The escrow releases on acceptance, returns on refusal, and expires on timeout. | `tests/test_xrpl_escrow.py::test_escrow_release_refuse_expire` |
| `CONN-EMERALD-EXCHANGE-XRPL-R005` | **Native DEX and AMM market operations.** The connector places, cancels and inspects native DEX offers and AMM swaps. Each mutating call previews first. | `tests/test_xrpl_dex.py::test_dex_offer_and_amm_swap` |
| `CONN-EMERALD-EXCHANGE-XRPL-R006` | **Account and portfolio queries.** The connector reads account info, balances, trust lines, offers and escrow state as read-only tools. | `tests/test_xrpl_account.py::test_account_and_portfolio_queries` |
| `CONN-EMERALD-EXCHANGE-XRPL-R007` | **Agent attribution and audit trail.** Every agent-initiated transaction carries the agent SourceTag and a Memo naming the agent and originating request. The pair reads back from the ledger into an audit trail. | `tests/test_xrpl_attribution.py::test_source_tag_memo_audit_trail` |
| `CONN-EMERALD-EXCHANGE-XRPL-R008` | **Spending-limit checks and kill-switch.** Every outbound value passes the spending-limit check before it signs. Over-limit values refuse. The kill-switch stops all outbound operations and reports the halt. | `tests/test_xrpl_risk.py::test_spending_limit_and_kill_switch` |
| `CONN-EMERALD-EXCHANGE-XRPL-R009` | **Safety defaults.** Paper or testnet is the default. Signing previews before it signs. No production network call succeeds without an explicit opt-in row in this spec, recorded as a plan amendment. | `tests/test_xrpl_safety.py::test_paper_testnet_default_and_production_refusal` |
| `CONN-EMERALD-EXCHANGE-XRPL-R010` | **Resource serving.** The connector serves docs, network endpoints, fee schedules and live network status as MCP resources. Live entries refresh from the network. | `tests/test_xrpl_resources.py::test_docs_endpoints_fees_status_resources` |
| `CONN-EMERALD-EXCHANGE-XRPL-R011` | **Prompts.** The connector packages natural-language prompts for payment, escrow-gated work and spending-limit checks. | `tests/test_xrpl_prompts.py::test_packaged_prompts_list` |
| `CONN-EMERALD-EXCHANGE-XRPL-R012` | **Skills.** The connector packages the XRPL Agent Wallet, Payments and Trading skills through the existing skill provider surface. | `tests/test_xrpl_skills.py::test_xrpl_skill_packages` |
| `CONN-EMERALD-EXCHANGE-XRPL-R013` | **Ontology content.** The connector publishes XRPL transaction types, payment, escrow and DEX concepts, RLUSD, agent attribution and risk constraints as ConnectorPack ontology content for Epistemic Graph ingest. | `tests/test_xrpl_ontology.py::test_xrpl_ontology_pack` |
