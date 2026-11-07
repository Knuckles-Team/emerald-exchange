# CONN-EMERALD-EXCHANGE-X402 — Research: where agent payments belong, and the wallet decision

Status: routing and wallet provider decided. Rows it supports: `CONN-EMERALD-EXCHANGE-X402-R008` to `R015` with their child rows, and `EMERALD-OPS-R015`.

## Question

The exchange connector is to become the ecosystem's universal trading platform: crypto spot beside the existing equities, prediction-market and derivatives backends, plus agent-to-agent payments and the agentic-wallet skill content, all behind one governed connector. Where does each part live, and is the working assumption (the exchange connector owns agent payments) correct?

## Routing decision

The assumption holds, with a narrow split. The ecosystem routing standard gives a connector "the behavior of one external system: its venue or API calls, mappings and MCP tools", and gives the shared transport, contracts and helpers to the SDK. Payments to another agent over a payment rail are the calls of external settlement systems, so they are connector behavior. The exchange connector already holds the pieces a payment needs and a second connector would have to copy: the kill switch, circuit breakers, staged execution policy (paper first), notional limits, the order admission and confirmation receipts, the wallet operation proof gate, and an audit trail.

| Part | Owner | Reason |
|---|---|---|
| Trading backends (equities, derivatives, prediction markets, crypto spot incl. the major-exchange backend) | emerald-exchange | One external venue per backend; orders only through the risk-guarded order tools. |
| Wallet and custody | emerald-exchange holds the provider seam and refuses key material in results; the key itself lives in a provider outside the connector (server-side wallet, remote signer or the ledger wallet) | The connector must call a wallet, not be one. Secrets resolve through the SDK secret facade, never through connector storage. |
| Agent payment rail (ledger rail, stablecoin rail, x402 and machine-payment schemes) | emerald-exchange for the calls, mappings and `payments` MCP tools; scion-sdk for the shared types and transport | Rail calls are connector behavior; the challenge, proof and header types, HTTP safety and credential facade already ship in the SDK and are reused, not copied. |
| Payment governance (limits, kill switch, breaker, approval threshold, paper-first, attribution) | emerald-exchange, one governor reused by every rail, trading and payments alike | The hardening already exists here; a second control set would drift. Approval itself is the arbora admission and confirmation step, which the governor calls. |
| Skills (payments, wallet, trading playbooks) | universal-skills owns skill content; the connector serves its own packaged skills and references the agentic-wallet skill | Skill content is not connector code. The standalone operator playbook for the third-party payment CLI stays in universal-skills as installation guidance and points here for governed agent payments. |
| Admission, auth, MCP serving, approvals UI | arbora | The one door; the connector does not serve itself to other callers. |
| Settlement facts, spend history queries, reasoning over payments | medulla | Records and queries; the connector writes `PaymentRecord` through the SDK adapter and stores nothing. |
| Views of balances and approvals | overstory, tuig, axil via arbora | Presentation only. |

Where the assumption is narrowed: scion-sdk is not told to own a payments connector. It owns only what two or more connectors share (types, transport, credentials). If a second connector ever needs a payment rail, the rail moves to the SDK as a shared capability and the exchange connector becomes its caller; the seams in R009 and R011 keep that move mechanical.

Cross-repo handoffs, each filed in the owner's own `specs/`: universal-skills (pointer in the payment CLI playbook, and the payments skill content standard), scion-sdk (any rail helper needed by two connectors), arbora (approval confirmation above `payments.approve_above`, already ARBORA-DATA-MARKET-R007).

## Why a native exchange backend (EMERALD-OPS-R015)

The CCXT backend already trades the major exchange through a generic adapter. A native backend earns its place only on a measured difference: a native sandbox, per-portfolio account scoping, the exchange's own order types and fee tiers, and one credential shared with the wallet provider. The row carries a value gate: if the parity matrix shows nothing CCXT cannot do, the row closes REJECTED and CCXT remains the only crypto path.

## Wallet decision

Context: the third-party payment SDK's managed wallet bootstrap depends on a macOS launch daemon and the desktop keychain. The packaged runtime installs on Linux, but wallet setup is unimplemented there. The service host is Linux, so the payment lane is blocked until a wallet path is chosen.

| Option | What it is | For | Against |
|---|---|---|---|
| A. Keep the macOS managed wallet | Run the payment SDK wallet on a macOS host and call it from the connector | Upstream supported; self-custodial; no code change in the connector | Needs a macOS host kept running and reachable; a desktop-keychain secret is hard to automate and back up; a network hop from Linux with its own auth; ties a core lane to one machine |
| B. Linux source install with manual daemon | Build the SDK from source and wire the daemon by hand on Linux | Self-custodial on the existing host | Unsupported upstream: the owner carries every upgrade and the key custody design; the macOS keychain guarantees are not reproduced, so key-at-rest hardening is ours to invent |
| C. Server-side wallet from the exchange developer platform | A provider-managed agent wallet reached by API key, signing inside the provider; spend caps and allowlists enforced provider-side as well | Runs on Linux today; no key in the connector; the same credential family as the R015 backend; provider-side limits add a second line behind the governor; supports the x402 exact scheme | Custodial: the provider holds the keys and can freeze; vendor dependency; funds sit with a third party |
| D. Remote signer | A signing service the owner runs (threshold or HSM-backed) that the connector calls to sign an already-governed payload | Self-custodial and Linux-native; one signer shared across rails; clean fit for the provider seam of R011 | Most to build and operate; the owner owns signer uptime and key ceremony |

Decision (owner, 2026-11-06): a server-side, self-custodial wallet bundled in the connector image. This is option B built from the upstream packaged Linux runtime instead of a source build: the runtime release is pinned with a checksum in the image (R012.1), and its daemon runs headless on Linux from the same image as a separate process. The macOS keychain and launch-daemon bootstrap are not used. Key custody: the encrypted daemon state and its unlock password resolve only from the secret store through references, are handed to the daemon process alone (password on stdin), and never reach the image, the config file, the MCP process or a tool result (R011.1). Limits apply twice on the server: the connector governor first (R010.1), then the runtime daemon's own per-token, window and manual-approval policy, which the operator sets with the runtime admin tool. The connector exposes one typed tool per bounded runtime operation (R008.1) and one order surface across the exchange venue and the wallet rail (R015).

Consequences: upgrades of the runtime are a checksum bump owned here; wallet creation, key generation, funding, the daemon policy and the encrypted backup stay operator steps. Option C (provider-custodied wallet) and D (remote signer) remain possible later providers behind the R011 seam.

Rejected alternatives: A, because it ties a core lane to a desktop host; a source build of B, because the packaged runtime already ships the Linux daemon and a source build adds a toolchain to the image; C as the first provider, because the owner chose self-custody.

## Governance applied to payments

Every outbound value passes one governor: kill switch, execution stage (paper default), per-transaction and trailing-day limits from the audit trail, approval above a threshold, a circuit breaker on repeated rail failures, and attribution. The XRPL spend check becomes a client of that governor, so there is one set of limits and one halt for trading and payments.
