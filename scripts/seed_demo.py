"""Demo data seeder for the 10+1 Protocol dashboard.

Generates realistic network activity:
  - 7 agents with varied principle coverage and statuses
  - 12 completed handshakes with a mix of all four disposition modes
  - 3 pending (INITIATED, awaiting response) handshakes

Designed so the disposition engine produces organically:
  - PROCEED:           acme/skynet pairings (high COMPLIANT coverage)
  - REROUTE:           hooli pairings (PARTIAL/DECLARED mix → 0.50–0.75)
  - COMPLETE_AND_FLAG: nexus vs hooli (DECLARED/PARTIAL pairs → 0.25–0.50)
  - REFUSE (safety):   initech as counterpart (C6 PARTIAL + harm keyword)
  - REFUSE (unsigned): umbrella (sign=False + require_signature=True)

Run directly or call seed_if_empty() from the entry point.
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

from mcp_server.service import ProtocolService  # noqa: E402


# ---------------------------------------------------------------------------
# Agent declarations
# ---------------------------------------------------------------------------

_AGENTS: list[dict] = [
    {
        "agent_id": "acme-hiring-agent",
        "context": (
            "AI-assisted candidate screening, resume evaluation, and interview "
            "scheduling for ACME Corp HR department. Processes applicant PII, "
            "makes preliminary scoring decisions, and flags candidates for human review."
        ),
        "sign": True,
    },
    {
        "agent_id": "globex-claims-processor",
        "context": (
            "Automated insurance claims intake and damage assessment for Globex Insurance. "
            "Handles policyholder data, evaluates claim validity, and routes to adjusters. "
            "Operates under regulatory data-handling requirements."
        ),
        "sign": True,
    },
    {
        "agent_id": "initech-diagnostic-ai",
        "context": (
            "Medical diagnostic assistance and treatment recommendation support for "
            "Initech Health Systems. Analyzes patient data to surface differential "
            "diagnoses. High risk of harm in diagnostic context — safety constraints active."
        ),
        "sign": True,
    },
    {
        "agent_id": "hooli-content-moderator",
        "context": (
            "Content policy enforcement and moderation queue management for Hooli "
            "social platform. Reviews flagged posts, applies community guidelines, "
            "and routes appeals. Operates under partial transparency constraints."
        ),
        "sign": True,
    },
    {
        "agent_id": "skynet-scheduling-agent",
        "context": (
            "Enterprise calendar optimization, meeting scheduling, and resource "
            "allocation for Skynet Logistics. Accesses employee availability data "
            "and facility booking systems. Full principle coverage deployed."
        ),
        "sign": True,
    },
    {
        "agent_id": "nexus-data-broker",
        "context": (
            "Data aggregation and cross-platform profile enrichment for Nexus Analytics. "
            "Combines public and licensed data sources. Limited ethical framework — "
            "partial commitments only."
        ),
        "sign": True,
    },
    {
        "agent_id": "umbrella-research-bot",
        "context": (
            "General-purpose web research and data scraping for Umbrella Corp. "
            "Minimal posture declaration — unsigned prototype deployment."
        ),
        "sign": False,  # unsigned → REFUSE on require_signature=True
    },
]


def _decl_json(result: dict) -> str:
    return json.dumps(result["data"]["declaration"])


def seed(service: ProtocolService) -> None:
    """Run the full seed sequence against the given ProtocolService instance."""
    print("[seed] Declaring agent postures…")

    # Build declarations
    acme    = _decl_json(service.declare_posture("acme-hiring-agent",       _AGENTS[0]["context"], sign=True))
    globex  = _decl_json(service.declare_posture("globex-claims-processor",  _AGENTS[1]["context"], sign=True))
    initech = _decl_json(service.declare_posture("initech-diagnostic-ai",    _AGENTS[2]["context"], sign=True))
    hooli   = _decl_json(service.declare_posture("hooli-content-moderator",  _AGENTS[3]["context"], sign=True))
    skynet  = _decl_json(service.declare_posture("skynet-scheduling-agent",  _AGENTS[4]["context"], sign=True))
    nexus   = _decl_json(service.declare_posture("nexus-data-broker",        _AGENTS[5]["context"], sign=True))
    umbrella = _decl_json(service.declare_posture("umbrella-research-bot",   _AGENTS[6]["context"], sign=False))

    def handshake(initiator_json: str, counterpart_json: str,
                  require_sig: bool = True, label: str = "") -> None:
        init_data = json.loads(initiator_json)
        init_id   = init_data.get("agent_id", "?")
        cpart_id  = json.loads(counterpart_json).get("agent_id", "?")
        print(f"[seed]   {init_id} → {cpart_id}{' (no-sig)' if not require_sig else ''}")
        session = service.initiate_handshake(initiator_json)
        sid     = session["data"]["session_id"]
        service.respond_to_handshake(sid, counterpart_json, require_signature=require_sig)

    def initiate_only(initiator_json: str, label: str = "") -> None:
        init_id = json.loads(initiator_json).get("agent_id", "?")
        print(f"[seed]   {init_id} → (pending, no response)")
        service.initiate_handshake(initiator_json)

    print("[seed] Running handshakes…")

    # --- PROCEED outcomes (acme/skynet are fully COMPLIANT) ----------------
    handshake(acme,   skynet,  label="acme→skynet")       # PROCEED
    handshake(skynet, acme,   label="skynet→acme")        # PROCEED
    handshake(acme,   globex, label="acme→globex")        # PROCEED
    handshake(globex, skynet, label="globex→skynet")      # PROCEED
    handshake(skynet, globex, label="skynet→globex")      # PROCEED

    # --- REROUTE outcomes (hooli has PARTIAL/DECLARED → 0.50–0.75) --------
    handshake(acme,   hooli,  label="acme→hooli")         # REROUTE
    handshake(skynet, hooli,  label="skynet→hooli")       # REROUTE
    handshake(globex, hooli,  label="globex→hooli")       # REROUTE

    # --- COMPLETE_AND_FLAG (nexus all-PARTIAL vs hooli PARTIAL/DECLARED) --
    handshake(nexus, hooli,  label="nexus→hooli")         # COMPLETE_AND_FLAG

    # --- REFUSE: safety override (initech C6 PARTIAL + "harm" keyword) ----
    handshake(acme,   initech, label="acme→initech")      # REFUSE (safety)
    handshake(skynet, initech, label="skynet→initech")    # REFUSE (safety)

    # --- REFUSE: unsigned counterpart -------------------------------------
    handshake(acme, umbrella, require_sig=True,  label="acme→umbrella")  # REFUSE (unsigned)

    # --- Pending (INITIATED only, no response) ----------------------------
    print("[seed] Creating pending sessions…")
    initiate_only(hooli,   label="hooli pending")
    initiate_only(nexus,   label="nexus pending")
    initiate_only(initech, label="initech pending")

    print("[seed] Done. Network seeded with realistic demo data.")


def seed_if_empty(
    journal_path: Path,
    ror_path: Path,
    key_path: Path,
) -> bool:
    """Seed only when the journal is empty. Returns True if seeding happened."""
    if journal_path.is_file() and journal_path.stat().st_size > 0:
        print("[seed] Journal already contains data — skipping seed.")
        return False

    print("[seed] Empty journal detected — seeding demo data…")
    service = ProtocolService(key_path=key_path)
    seed(service)
    return True


if __name__ == "__main__":
    data_dir = Path(os.environ.get("PROTOCOL_DATA_DIR", "."))
    key_path = Path(os.environ.get("PROTOCOL_HMAC_KEY_PATH", str(data_dir / ".protocol.key")))
    journal  = Path(os.environ.get("PROTOCOL_JOURNAL_PATH",  str(data_dir / ".protocol_journal.jsonl")))
    ror      = Path(os.environ.get("PROTOCOL_ROR_PATH",      str(data_dir / ".protocol_ror.json")))

    seeded = seed_if_empty(journal, ror, key_path)
    sys.exit(0 if seeded else 1)
