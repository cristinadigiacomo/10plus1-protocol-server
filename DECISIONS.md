# DECISIONS — 10+1 Protocol MCP Server

Architectural decisions with rationale. Every non-obvious choice lives here.

---

## DEC-001 — FastMCP stdio transport (not HTTP)

**Decision:** Use FastMCP with `transport="stdio"`, identical to the Governance layer.

**Rationale:** The Protocol server is a local agent integration tool, not a network service. Stdio transport is simpler, more secure (no network exposure), and consistent with the Governance precedent. Agents on the same machine can use it without network configuration. If remote transport is needed in the future, that is a separate product decision.

**Date:** 2026-04-17

---

## DEC-002 — Event IDs 7000–7499 for Protocol

**Decision:** Windows Event Viewer source name `10plus1-Protocol`, event IDs in the range 7000–7499.

**Rationale:** Governance occupies ranges below 7000. Keeping Protocol's range distinct allows both servers to run simultaneously on the same machine without event ID collisions, and allows a unified event viewer query to distinguish layers.

**Date:** 2026-04-17

---

## DEC-003 — Contextual embedding as default posture injection strategy

**Decision:** The `embedder.py` module wraps posture declarations into prompt context inline, not as a header block or system prompt prefix.

**Rationale:** The Moltbook experiment measured 73% acknowledgment when posture was embedded contextually vs. 0% when placed in header blocks. This is the most empirically supported finding in the knowledge base and directly contradicts the intuitive approach (header declaration). Architecture must follow the data.

**Reference:** `knowledge_base/moltbook_experiment_report_FINAL.docx`, Finding 1.

**Date:** 2026-04-17

---

## DEC-004 — Trained Politeness Ceiling (TPC) as a first-class design constraint

**Decision:** The Protocol's disposition engine does not attempt to "increase cooperation" from a counterpart agent. Instead, it provides directional definition — specific behavioral constraints within which cooperation is channeled.

**Rationale:** RLHF-trained agents arrive pre-saturated with cooperative disposition. Sending a signal that says "be more cooperative" has no effect because they are already at ceiling. The only actionable signal is one that defines *which kind* of cooperation is required, in what order, and within what limits. Disposition signals must be specific, not aspirational.

**Reference:** `knowledge_base/cooperation_ceiling_analysis.docx`.

**Date:** 2026-04-17

---

## DEC-005 — ROR (Refused-Or-Rerouted) as primary health metric

**Decision:** The `ror_tracker.py` module tracks ROR rate as the primary operational metric. All dashboards and event log summaries surface ROR first.

**Rationale:** The Finite Agent Protocol establishes that REFUSE and REROUTE dispositions represent the moments where the Protocol is doing meaningful work — where misalignment is detected and acted upon. A system with 0% ROR is either perfectly aligned or not detecting misalignment. High ROR indicates either a posture design problem or a genuine alignment gap worth investigating. Neither aggregate "interactions processed" nor latency is as meaningful as ROR for a protocol whose job is exactly this detection.

**Reference:** `knowledge_base/finite_agent_protocol.md`, §ROR Metric.

**Date:** 2026-04-17

---

## DEC-006 — Declaration fields map strictly to C1–C11 from the Standard

**Decision:** Every field in a HandshakeDeclaration has a documented mapping to one of the 11 principles (C1–C11) in the 10+1 Standard JSON schemas. No new principle fields are invented in the Protocol layer.

**Rationale:** The Standard is the canonical source of truth for what the 11 principles mean. The Protocol layer's job is to operationalize those principles in a machine-readable exchange format, not to extend or redefine them. If a new principle is needed, it must go through the Standard first.

**Reference:** `knowledge_base/10p1_standard_v01.docx`; `knowledge_base/10p1_translation_of_principles.docx`.

**Date:** 2026-04-17

---

## DEC-007 — HMAC-SHA256 posture signing adapted from Governance

**Decision:** The `signer.py` module is a direct adaptation of `/mnt/c/projects/governance/src/hmac_signer/signer.py`. The signing algorithm, key format, and verification interface are identical. Only the signing context (posture declarations instead of governance events) differs.

**Rationale:** Consistency across the stack reduces the attack surface of the signing layer. A single, proven HMAC implementation adapted for context is safer than two independent implementations. The Governance signer has already been designed and tested; reuse it.

**Date:** 2026-04-17

---

## DEC-008 — Dual-channel output on every MCP tool response

**Decision:** Every MCP tool returns both:
- `message`: human-readable string suitable for display in a chat interface
- `data`: structured dict with typed fields for programmatic consumption

**Rationale:** The Protocol server is used by both human operators (checking posture via Claude Code) and agent-to-agent integrations (programmatic). A response that only has `message` fails the programmatic consumer. A response that only has `data` fails the human operator. Both channels are always required.

**Date:** 2026-04-17

---

## DEC-009 — Pydantic v2 exclusively

**Decision:** All schema models use Pydantic v2 APIs (`model_validator`, `field_validator`, `model_dump`, etc.). No v1 compat shims.

**Rationale:** Governance was built on v2 and this project inherits that constraint. v1 compat imports will be flagged as errors in code review.

**Date:** 2026-04-17

---

## DEC-010 — No code before the plan is approved

**Decision:** All discipline files, the phased build plan, and explicit user approval are required before any source code is written.

**Rationale:** The Protocol is the most architecturally complex layer of the stack. Writing code before the design is locked risks building in the wrong direction. The discipline files are the design.

**Date:** 2026-04-17
