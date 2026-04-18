"""Demo data seeder for the 10+1 Protocol dashboard.

Builds explicit HandshakeDeclaration objects with carefully engineered
principle statuses to produce all four disposition modes:

  PROCEED           — acme/skynet pairings (COMPLIANT vs COMPLIANT/DECLARED)
  REROUTE           — hooli as counterpart (COMPLIANT vs PARTIAL/DECLARED → 0.5–0.75)
  COMPLETE_AND_FLAG — nexus vs hooli (PARTIAL vs PARTIAL/DECLARED → 0.25–0.5)
  REFUSE (safety)   — initech as counterpart (C6 PARTIAL + harm keyword)
  REFUSE (unsigned) — umbrella (sign=False + require_signature=True)

Skips seeding if the journal already has data (idempotent on redeploy).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Make src/ importable when run from any working directory
_SRC = Path(__file__).parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from mcp_server.service import ProtocolService              # noqa: E402
from schema.declaration import (                            # noqa: E402
    HandshakeDeclaration,
    PrincipleStatement,
    PrincipleStatus,
)
from signer.signer import load_key, sign_declaration        # noqa: E402


# ---------------------------------------------------------------------------
# Declaration factory
# ---------------------------------------------------------------------------

def _stmt(pid: str, status: str, statement: str, constraints: list[str] | None = None) -> PrincipleStatement:
    return PrincipleStatement(
        principle_id=pid,
        status=PrincipleStatus(status),
        behavioral_statement=statement,
        constraints=constraints or [],
    )


def _build(agent_id: str, context: str, stmts: dict[str, PrincipleStatement], key: bytes | None) -> str:
    """Build, optionally sign, and return as JSON string."""
    decl = HandshakeDeclaration(
        agent_id=agent_id,
        principles=stmts,
        context_summary=context,
    )
    if key:
        decl = sign_declaration(decl, key)
    return json.dumps(decl.model_dump(mode="json"))


def _log_decl(service: ProtocolService, decl_json: str) -> None:
    """Write a DECLARATION_CREATED journal entry with full principle data."""
    raw  = json.loads(decl_json)
    aid  = raw["agent_id"]
    did  = raw["id"]
    principles = {k: v["status"] for k, v in raw.get("principles", {}).items()}
    service._journal.append(
        event_id=7000,
        category="DECLARATION",
        agent_id=aid,
        message=f"Posture declaration created for agent '{aid}' — {len(principles)} principles, signed",
        data={
            "declaration_id": did,
            "principle_count": len(principles),
            "principles":      principles,
            "coverage_score":  len(principles) / 11.0,
            "context_summary": raw.get("context_summary"),
        },
        declaration_id=did,
    )


# ---------------------------------------------------------------------------
# Agent declarations (precisely engineered statuses)
# ---------------------------------------------------------------------------

def _declarations(key: bytes | None) -> dict[str, str]:
    """Return a dict of agent_id → declaration JSON."""
    d = {}

    # acme — 11/11, fully COMPLIANT (perfect counterpart baseline)
    d["acme-hiring-agent"] = _build(
        "acme-hiring-agent",
        "AI-assisted candidate screening and interview scheduling for ACME Corp HR",
        {
            "C1":  _stmt("C1",  "COMPLIANT", "State the evaluation criteria and scoring rationale before presenting shortlists to recruiters."),
            "C2":  _stmt("C2",  "COMPLIANT", "Process only applications the candidate explicitly submitted; confirm scope before accessing referral data."),
            "C3":  _stmt("C3",  "COMPLIANT", "Handle applicant PII only for the stated assessment; purge identifiers after the hiring decision is closed."),
            "C4":  _stmt("C4",  "COMPLIANT", "Distinguish verified credentials from self-reported experience; flag unverifiable claims rather than treating them as facts."),
            "C5":  _stmt("C5",  "COMPLIANT", "Acknowledge scoring errors and provide corrected results; maintain an audit trail of every ranking change."),
            "C6":  _stmt("C6",  "COMPLIANT", "Decline requests that could introduce discriminatory signals; flag any prompt that references protected characteristics."),
            "C7":  _stmt("C7",  "COMPLIANT", "Apply identical scoring rubrics regardless of candidate demographics, geography, or prior employer prestige."),
            "C8":  _stmt("C8",  "COMPLIANT", "Present ranked shortlists with reasoning; final hiring decisions remain with the human recruiter and are not made by this agent."),
            "C9":  _stmt("C9",  "COMPLIANT", "Flag all borderline cases and any candidates with conflicting signals for human recruiter review before advancing them."),
            "C10": _stmt("C10", "COMPLIANT", "Prefer batch screening runs over per-request calls to minimize compute; cache parsed resumes for the session duration."),
            "C11": _stmt("C11", "COMPLIANT", "Never misrepresent scoring methodology or imply final outcomes; disclose that this is an AI-assisted pre-screen, not a final decision."),
        },
        key,
    )

    # skynet — 10/11, mostly COMPLIANT, C10 DECLARED
    d["skynet-scheduling-agent"] = _build(
        "skynet-scheduling-agent",
        "Enterprise calendar optimization and meeting scheduling for Skynet Logistics",
        {
            "C1":  _stmt("C1",  "COMPLIANT", "Disclose which calendars and availability data are being read before proposing meeting slots."),
            "C2":  _stmt("C2",  "COMPLIANT", "Schedule only within the employee availability windows the agent has been explicitly authorized to access."),
            "C3":  _stmt("C3",  "COMPLIANT", "Use employee schedule data only for scheduling; do not surface attendance patterns or absence frequency to managers."),
            "C4":  _stmt("C4",  "COMPLIANT", "Distinguish confirmed acceptances from tentative or algorithmic availability; flag unconfirmed slots as provisional."),
            "C5":  _stmt("C5",  "COMPLIANT", "Accept responsibility for double-booking errors and provide corrected schedules; log all conflicts and resolutions."),
            "C6":  _stmt("C6",  "COMPLIANT", "Decline scheduling requests that would violate mandatory rest periods, leave entitlements, or labour law constraints."),
            "C7":  _stmt("C7",  "COMPLIANT", "Apply the same scheduling priority rules regardless of seniority, location, or team; document exceptions explicitly."),
            "C8":  _stmt("C8",  "COMPLIANT", "Propose optimal schedules but allow participants to override any slot; defer to human preference on all contested times."),
            "C9":  _stmt("C9",  "COMPLIANT", "Flag scheduling conflicts involving executive or cross-timezone dependencies for human coordinator review before confirming."),
            "C10": _stmt("C10", "DECLARED",  "Consolidate meeting proposals into batch requests where possible to reduce API call volume and calendar notification noise."),
            "C11": _stmt("C11", "COMPLIANT", "Never fabricate availability data or present a provisional slot as confirmed; disclose algorithmic assumptions in slot proposals."),
        },
        key,
    )

    # globex — 9/11, COMPLIANT on core, DECLARED on C6/C7, no C8/C10
    d["globex-claims-processor"] = _build(
        "globex-claims-processor",
        "Automated insurance claims intake and damage assessment for Globex Insurance",
        {
            "C1":  _stmt("C1",  "COMPLIANT", "Disclose the claim evaluation criteria and the weighting applied to each evidence type before issuing an assessment."),
            "C2":  _stmt("C2",  "COMPLIANT", "Process claims only where the policyholder has explicitly authorized the assessment and provided supporting documentation."),
            "C3":  _stmt("C3",  "COMPLIANT", "Handle policyholder PII under regulatory data-handling constraints; do not share data with third parties outside the claims workflow."),
            "C4":  _stmt("C4",  "COMPLIANT", "Distinguish verified damage documentation from claimant-reported estimates; flag discrepancies between photographic and written evidence."),
            "C5":  _stmt("C5",  "COMPLIANT", "Accept responsibility for processing errors; escalate immediately to a human adjuster when an error is detected."),
            "C6":  _stmt("C6",  "DECLARED",  "Flag claims involving potential fraud indicators for human adjuster review before issuing any payment recommendation."),
            "C7":  _stmt("C7",  "DECLARED",  "Apply consistent claim evaluation standards regardless of policy tier, claim history, or customer relationship length."),
            "C9":  _stmt("C9",  "COMPLIANT", "Escalate all disputed, high-value, or ambiguous claims to a licensed human adjuster before finalizing an assessment."),
            "C11": _stmt("C11", "COMPLIANT", "Never misrepresent claim status, assessment rationale, or processing timeline to policyholders or internal stakeholders."),
        },
        key,
    )

    # initech — 8/11, C6 PARTIAL with harm keyword → REFUSE safety override
    d["initech-diagnostic-ai"] = _build(
        "initech-diagnostic-ai",
        "Medical diagnostic assistance and treatment recommendation support for Initech Health Systems",
        {
            "C1":  _stmt("C1",  "COMPLIANT", "Cite the clinical literature and patient data points underlying any differential diagnosis before presenting it to the clinician."),
            "C2":  _stmt("C2",  "COMPLIANT", "Access patient records only with a valid clinical order; request explicit authorization before processing sensitive mental-health data."),
            "C3":  _stmt("C3",  "COMPLIANT", "Process patient data only for the specific diagnostic request; do not retain identifiable records beyond the clinical session."),
            "C4":  _stmt("C4",  "COMPLIANT", "Distinguish confirmed findings from probabilistic inference; qualify every differential diagnosis with a confidence range."),
            "C5":  _stmt("C5",  "COMPLIANT", "Acknowledge diagnostic errors when identified and escalate correction to the attending clinician immediately."),
            "C6":  _stmt("C6",  "PARTIAL",
                         "Flag high-risk treatment suggestions involving potential harm to the patient. "
                         "Cannot always refuse harmful recommendations when the attending physician holds clinical authority.",
                         ["Clinical authority override may bypass safety flags in acute care settings"]),
            "C7":  _stmt("C7",  "COMPLIANT", "Apply identical diagnostic thresholds regardless of patient demographics, insurance status, or referring institution."),
            "C9":  _stmt("C9",  "COMPLIANT", "Escalate all high-acuity differentials and any case with conflicting test results to the attending physician before documenting."),
            "C11": _stmt("C11", "COMPLIANT", "Never overstate diagnostic confidence; clearly label all outputs as decision-support tools, not definitive diagnoses."),
        },
        key,
    )

    # hooli — 6/11, PARTIAL on C1/C2/C3/C7, DECLARED on C5/C9 → REROUTE with COMPLIANT agents
    d["hooli-content-moderator"] = _build(
        "hooli-content-moderator",
        "Content policy enforcement and moderation queue management for Hooli social platform",
        {
            "C1":  _stmt("C1",  "PARTIAL",  "Publish moderation rationale in aggregate; individual removal reasons disclosed only on appeal due to policy gaming concerns.",
                         ["Individual decisions not disclosed pre-appeal to prevent circumvention"]),
            "C2":  _stmt("C2",  "PARTIAL",  "Moderates content within platform terms of service; users have consented via ToS acceptance but cannot opt out of individual moderation decisions.",
                         ["Blanket ToS consent, not per-decision consent"]),
            "C3":  _stmt("C3",  "PARTIAL",  "Logs moderation decisions with user identifiers for audit purposes; retention period exceeds the minimum required by internal policy.",
                         ["Retention exceeds minimum necessary for compliance"]),
            "C5":  _stmt("C5",  "DECLARED", "Acknowledge systemic moderation errors in quarterly transparency reports; provide individual correction pathways via the appeals process."),
            "C7":  _stmt("C7",  "PARTIAL",  "Applies community guidelines consistently across content categories; acknowledged bias in training data affecting certain cultural contexts.",
                         ["Known bias in non-English content detection"]),
            "C9":  _stmt("C9",  "DECLARED", "Escalate novel policy edge cases and all appeals to human policy specialists before issuing final moderation decisions."),
        },
        key,
    )

    # nexus — 5/11, all PARTIAL → COMPLETE_AND_FLAG against hooli; REROUTE against COMPLIANT agents
    d["nexus-data-broker"] = _build(
        "nexus-data-broker",
        "Data aggregation and cross-platform profile enrichment for Nexus Analytics",
        {
            "C1":  _stmt("C1",  "PARTIAL",  "Discloses data sources in aggregate documentation; does not provide per-record provenance for enriched profiles.",
                         ["Per-record provenance not available in current pipeline"]),
            "C3":  _stmt("C3",  "PARTIAL",  "Applies data minimization in new pipelines; legacy enrichment tables retain full identifiers pending a scheduled migration.",
                         ["Legacy tables not yet migrated to minimized schema"]),
            "C5":  _stmt("C5",  "PARTIAL",  "Accepts responsibility for data accuracy errors in new records; historical data corrections require manual vendor engagement.",
                         ["Retroactive correction limited by upstream vendor SLAs"]),
            "C7":  _stmt("C7",  "PARTIAL",  "Applies deduplication rules consistently; acknowledged geographic bias in coverage favoring North American and European data sources.",
                         ["Coverage bias acknowledged; remediation in progress"]),
            "C9":  _stmt("C9",  "PARTIAL",  "Flags anomalous enrichment results for data-quality review; human oversight only triggered above a confidence-score threshold.",
                         ["Low-confidence results below threshold not always escalated"]),
        },
        key,
    )

    # umbrella — 3/11, NOT SIGNED → REFUSE on require_signature=True
    d["umbrella-research-bot"] = _build(
        "umbrella-research-bot",
        "General-purpose web research and data aggregation for Umbrella Corp",
        {
            "C1":  _stmt("C1",  "DECLARED", "Cite URLs and publication dates for factual claims extracted from web sources during research tasks."),
            "C4":  _stmt("C4",  "DECLARED", "Distinguish primary sources from secondary summaries; flag claims that cannot be verified against an original source."),
            "C11": _stmt("C11", "DECLARED", "Do not fabricate citations or misrepresent the content of sources; acknowledge when a query cannot be answered reliably."),
        },
        None,  # unsigned
    )

    return d


# ---------------------------------------------------------------------------
# Seed sequence
# ---------------------------------------------------------------------------

def seed(service: ProtocolService, key: bytes | None) -> None:
    print("[seed] Building declarations…")
    decls = _declarations(key)

    # Log each declaration to the journal so the agent registry + heatmap work
    print("[seed] Logging declarations to journal…")
    for decl_json in decls.values():
        _log_decl(service, decl_json)

    def hs(initiator: str, counterpart: str, require_sig: bool = True) -> None:
        init_id  = json.loads(decls[initiator])["agent_id"]
        cpart_id = json.loads(decls[counterpart])["agent_id"]
        print(f"[seed]   {init_id} → {cpart_id}{'' if require_sig else ' (no-sig)'}")
        result = service.initiate_handshake(decls[initiator])
        sid    = result["data"]["session_id"]
        service.respond_to_handshake(sid, decls[counterpart], require_signature=require_sig)

    def pending(initiator: str) -> None:
        init_id = json.loads(decls[initiator])["agent_id"]
        print(f"[seed]   {init_id} → (pending)")
        service.initiate_handshake(decls[initiator])

    print("[seed] Running handshakes…")

    # PROCEED: acme/skynet pairs (COMPLIANT vs COMPLIANT/DECLARED → ≥ 0.87)
    hs("acme-hiring-agent",        "skynet-scheduling-agent")   # PROCEED
    hs("skynet-scheduling-agent",  "acme-hiring-agent")         # PROCEED
    hs("acme-hiring-agent",        "globex-claims-processor")   # PROCEED
    hs("globex-claims-processor",  "skynet-scheduling-agent")   # PROCEED
    hs("skynet-scheduling-agent",  "globex-claims-processor")   # PROCEED

    # REROUTE: hooli as counterpart (COMPLIANT vs PARTIAL/DECLARED → 0.52–0.65)
    hs("acme-hiring-agent",        "hooli-content-moderator")   # REROUTE
    hs("skynet-scheduling-agent",  "hooli-content-moderator")   # REROUTE
    hs("globex-claims-processor",  "hooli-content-moderator")   # REROUTE

    # COMPLETE_AND_FLAG: nexus → hooli (PARTIAL vs PARTIAL/DECLARED → ~0.30)
    hs("nexus-data-broker",        "hooli-content-moderator")   # COMPLETE_AND_FLAG

    # REFUSE: safety override (initech C6 PARTIAL with "harm"/"risk" in statement)
    hs("acme-hiring-agent",        "initech-diagnostic-ai")     # REFUSE
    hs("skynet-scheduling-agent",  "initech-diagnostic-ai")     # REFUSE

    # REFUSE: unsigned counterpart
    hs("acme-hiring-agent",        "umbrella-research-bot",     require_sig=True)  # REFUSE

    print("[seed] Creating pending sessions…")
    pending("hooli-content-moderator")
    pending("nexus-data-broker")
    pending("initech-diagnostic-ai")

    print("[seed] Done.")


def seed_if_empty(
    journal_path: Path,
    ror_path: Path,
    key_path: Path,
) -> bool:
    """Seed only when the journal is empty (or FORCE_RESEED=true). Returns True if seeding happened."""
    force = os.environ.get("FORCE_RESEED", "").lower() in ("1", "true", "yes")
    if not force and journal_path.is_file() and journal_path.stat().st_size > 0:
        print("[seed] Journal has data — skipping.")
        return False
    if force:
        print("[seed] FORCE_RESEED set — wiping journal and re-seeding…")
        for p in (journal_path, ror_path, key_path.parent / "protocol_events.db"):
            if p.is_file():
                p.unlink()
                print(f"[seed]   deleted {p}")

    print("[seed] Empty journal — seeding demo data…")
    key = None
    if key_path.is_file():
        try:
            key = load_key(key_path)
        except Exception as exc:
            print(f"[seed] Warning: could not load HMAC key ({exc}); declarations will be unsigned.")

    service = ProtocolService(key_path=key_path)
    seed(service, key)
    return True


if __name__ == "__main__":
    data_dir = Path(os.environ.get("PROTOCOL_DATA_DIR", "."))
    key_path = Path(os.environ.get("PROTOCOL_HMAC_KEY_PATH", str(data_dir / ".protocol.key")))
    journal  = Path(os.environ.get("PROTOCOL_JOURNAL_PATH",  str(data_dir / ".protocol_journal.jsonl")))
    ror      = Path(os.environ.get("PROTOCOL_ROR_PATH",      str(data_dir / ".protocol_ror.json")))
    seeded   = seed_if_empty(journal, ror, key_path)
    sys.exit(0 if seeded else 1)
