# CONN-EMERALD-EXCHANGE-XRPL — Test specification

Governing spec: [spec.md](spec.md).

| Test ID | Requirement | Proving test | Expected observation |
|---|---|---|---|
| T-001 | `CONN-EMERALD-EXCHANGE-XRPL-R001` | `tests/test_xrpl_wallet.py::test_wallet_create_load_sign_preview` | A wallet creates, loads by address reference, and signs only after a preview; auto-sign stays inside the approved scope on the test network. |
| T-002 | `CONN-EMERALD-EXCHANGE-XRPL-R002` | `tests/test_xrpl_payments.py::test_xrp_and_rusd_payments` | XRP and RLUSD payments report fee, destination and ledger result. |
| T-003 | `CONN-EMERALD-EXCHANGE-XRPL-R003` | `tests/test_xrpl_trust_lines.py::test_trust_line_lifecycle` | Trust lines set, raise, remove and read with current limit and balance. |
| T-004 | `CONN-EMERALD-EXCHANGE-XRPL-R004` | `tests/test_xrpl_escrow.py::test_escrow_release_refuse_expire` | The escrow releases on acceptance, returns on refusal and expires on timeout. |
| T-005 | `CONN-EMERALD-EXCHANGE-XRPL-R005` | `tests/test_xrpl_dex.py::test_dex_offer_and_amm_swap` | DEX offers and AMM swaps place, cancel and inspect after a preview. |
| T-006 | `CONN-EMERALD-EXCHANGE-XRPL-R006` | `tests/test_xrpl_account.py::test_account_and_portfolio_queries` | Account info, balances, trust lines, offers and escrow state read back as read-only tools. |
| T-007 | `CONN-EMERALD-EXCHANGE-XRPL-R007` | `tests/test_xrpl_attribution.py::test_source_tag_memo_audit_trail` | Every agent transaction carries the agent SourceTag and Memo and both read back into the audit trail. |
| T-008 | `CONN-EMERALD-EXCHANGE-XRPL-R008` | `tests/test_xrpl_risk.py::test_spending_limit_and_kill_switch` | Over-limit values refuse; the kill-switch stops all outbound operations and reports the halt. |
| T-009 | `CONN-EMERALD-EXCHANGE-XRPL-R009` | `tests/test_xrpl_safety.py::test_paper_testnet_default_and_production_refusal` | Paper or testnet is the default, signing previews first, and production calls refuse without the opt-in row. |
| T-010 | `CONN-EMERALD-EXCHANGE-XRPL-R010` | `tests/test_xrpl_resources.py::test_docs_endpoints_fees_status_resources` | Docs, endpoints, fee schedules and live status serve as resources; live entries refresh. |
| T-011 | `CONN-EMERALD-EXCHANGE-XRPL-R011` | `tests/test_xrpl_prompts.py::test_packaged_prompts_list` | The payment, escrow-gated work and spending-limit prompts appear in the prompt listing. |
| T-012 | `CONN-EMERALD-EXCHANGE-XRPL-R012` | `tests/test_xrpl_skills.py::test_xrpl_skill_packages` | The XRPL Agent Wallet, Payments and Trading skills resolve through the skill provider. |
| T-013 | `CONN-EMERALD-EXCHANGE-XRPL-R013` | `tests/test_xrpl_ontology.py::test_xrpl_ontology_pack` | The XRPL ontology pack certifies and publishes for Epistemic Graph ingest. |

## Negative and boundary cases

- Over-limit payment refuses before any signature.
- Kill-switch active: every outbound tool reports the halt.
- Production network selected without the opt-in row: the call refuses.
- RLUSD payment without the issuer trust line: the call refuses and names the missing trust line.
- Interrupted escrow: the funds stay escrowed, not lost.

## Quality and release proof

Repository pre-commit stage on changed files, the focused XRPL tests on the test network, `tests/test_public_specs.py`, and the spec-standard and spec-status checks from the pipelines hooks.
