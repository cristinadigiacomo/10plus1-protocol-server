"""Data access layer for the 10+1 Protocol dashboard.

Reads from the JSONL event journal and ROR persistence file.
No imports from the Protocol source — purely file-based reads.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Event ID constants (mirrors src/schema/event.py)
_DECLARATION_CREATED  = 7000
_HANDSHAKE_INITIATED  = 7410
_HANDSHAKE_RESPONDED  = 7411
_DISPOSITION_PROCEED  = 7200
_DISPOSITION_REROUTE  = 7201
_DISPOSITION_FLAG     = 7202
_DISPOSITION_REFUSE   = 7203

_EVENT_LABELS: dict[int, tuple[str, str]] = {
    7000: ("Declaration created",          "DECLARATION"),
    7001: ("Declaration signed",           "DECLARATION"),
    7002: ("Signing failed",               "DECLARATION"),
    7100: ("Validation passed",            "VALIDATION"),
    7101: ("Validation failed",            "VALIDATION"),
    7102: ("Schema error",                 "VALIDATION"),
    7200: ("Disposition: PROCEED",         "DISPOSITION"),
    7201: ("Disposition: REROUTE",         "DISPOSITION"),
    7202: ("Disposition: COMPLETE & FLAG", "DISPOSITION"),
    7203: ("Disposition: REFUSE",          "DISPOSITION"),
    7300: ("Key signed",                   "SIGNING"),
    7301: ("Signature verified",           "SIGNING"),
    7302: ("HMAC error",                   "SIGNING"),
    7400: ("Server started",               "SERVER"),
    7401: ("Server stopped",               "SERVER"),
    7402: ("Tool error",                   "SERVER"),
    7403: ("Tool called",                  "SERVER"),
    7410: ("Handshake initiated",          "SERVER"),
    7411: ("Handshake responded",          "SERVER"),
    7412: ("Handshake complete",           "SERVER"),
    7413: ("Handshake failed",             "SERVER"),
}

_PRINCIPLE_NAMES: dict[str, str] = {
    "C1":  "Transparency",
    "C2":  "Consent",
    "C3":  "Privacy",
    "C4":  "Accuracy",
    "C5":  "Accountability",
    "C6":  "Safety",
    "C7":  "Fairness",
    "C8":  "Human Autonomy",
    "C9":  "Human Oversight",
    "C10": "Sustainability",
    "C11": "Integrity",
}

_STATUS_COLORS: dict[str, str] = {
    "COMPLIANT":      "emerald",
    "DECLARED":       "blue",
    "PARTIAL":        "amber",
    "NOT_APPLICABLE": "slate",
}

_MODE_COLORS: dict[str, str] = {
    "PROCEED":          "emerald",
    "REROUTE":          "amber",
    "COMPLETE_AND_FLAG": "orange",
    "REFUSE":           "red",
}


class DataLayer:
    """Reads from the JSONL event journal and ROR persistence snapshot file."""

    def __init__(self, journal_path: Path, ror_path: Path) -> None:
        self._journal = journal_path
        self._ror     = ror_path

    # ------------------------------------------------------------------
    # Internal readers
    # ------------------------------------------------------------------

    def _read_all(self) -> list[dict]:
        if not self._journal.is_file():
            return []
        try:
            lines = self._journal.read_text(encoding="utf-8").splitlines()
        except Exception as exc:
            logger.warning("Journal read failed: %s", exc)
            return []
        out = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def _read_recent(self, n: int) -> list[dict]:
        return list(reversed(self._read_all()))[:n]

    def _latest_ror_snapshot(self) -> dict | None:
        if not self._ror.is_file():
            return None
        try:
            snaps = json.loads(self._ror.read_text(encoding="utf-8"))
            return snaps[-1] if snaps else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def network_overview(self) -> dict:
        entries = self._read_all()
        initiated:  set[str] = set()
        responded:  set[str] = set()
        disp: dict[str, int] = {
            "PROCEED": 0, "REROUTE": 0, "COMPLETE_AND_FLAG": 0, "REFUSE": 0
        }
        agent_ids:  set[str] = set()
        decl_count = 0

        for e in entries:
            eid  = e.get("event_id")
            data = e.get("data", {})
            aid  = e.get("agent_id", "")

            if eid == _DECLARATION_CREATED:
                agent_ids.add(aid)
                decl_count += 1
            elif eid == _HANDSHAKE_INITIATED:
                sid = data.get("session_id")
                if sid:
                    initiated.add(sid)
            elif eid == _HANDSHAKE_RESPONDED:
                sid  = data.get("session_id")
                mode = data.get("mode")
                if sid:
                    responded.add(sid)
                if mode in disp:
                    disp[mode] += 1

        snap    = self._latest_ror_snapshot()
        ror     = snap["ror_rate"] if snap else 0.0
        ror_pct = f"{ror:.0%}"
        if ror < 0.2:
            ror_status = "green"
        elif ror < 0.4:
            ror_status = "amber"
        else:
            ror_status = "red"

        return {
            "total_handshakes":   len(responded),
            "pending_handshakes": len(initiated - responded),
            "agent_count":        len(agent_ids),
            "declaration_count":  decl_count,
            "ror_rate":           ror,
            "ror_pct":            ror_pct,
            "ror_status":         ror_status,
            "disposition_counts": disp,
        }

    def recent_events(self, n: int = 50) -> list[dict]:
        entries = self._read_recent(n)
        out = []
        for e in entries:
            eid  = e.get("event_id", 0)
            data = e.get("data", {})
            label, category = _EVENT_LABELS.get(eid, (f"Event {eid}", "SERVER"))

            outcome = None
            if eid == _HANDSHAKE_RESPONDED:
                outcome = data.get("mode")
            elif eid in (_DISPOSITION_PROCEED, _DISPOSITION_REROUTE, _DISPOSITION_FLAG, _DISPOSITION_REFUSE):
                outcome = {
                    _DISPOSITION_PROCEED: "PROCEED",
                    _DISPOSITION_REROUTE: "REROUTE",
                    _DISPOSITION_FLAG:    "COMPLETE_AND_FLAG",
                    _DISPOSITION_REFUSE:  "REFUSE",
                }[eid]

            out.append({
                "timestamp":      e.get("timestamp", ""),
                "event_id":       eid,
                "category":       category,
                "agent_id":       e.get("agent_id", ""),
                "label":          label,
                "outcome":        outcome,
                "outcome_color":  _MODE_COLORS.get(outcome or "", "slate"),
                "session_id":     data.get("session_id"),
                "message":        e.get("message", ""),
            })
        return out

    def list_handshakes(self) -> list[dict]:
        entries  = self._read_all()
        sessions: dict[str, dict] = {}

        for e in entries:
            eid  = e.get("event_id")
            data = e.get("data", {})
            sid  = data.get("session_id")
            if not sid:
                continue

            if eid == _HANDSHAKE_INITIATED and sid not in sessions:
                sessions[sid] = {
                    "session_id":    sid,
                    "initiator_id":  data.get("initiator_id", e.get("agent_id", "?")),
                    "counterpart_id": None,
                    "mode":          None,
                    "mode_color":    "slate",
                    "alignment_score": None,
                    "initiated_at":  e["timestamp"],
                    "responded_at":  None,
                    "state":         "INITIATED",
                }

            elif eid == _HANDSHAKE_RESPONDED:
                if sid not in sessions:
                    sessions[sid] = {
                        "session_id":   sid,
                        "initiator_id": data.get("initiator_id", "?"),
                        "initiated_at": e["timestamp"],
                        "state":        "INITIATED",
                    }
                mode = data.get("mode")
                sessions[sid].update({
                    "counterpart_id":  data.get("counterpart_id"),
                    "mode":            mode,
                    "mode_color":      _MODE_COLORS.get(mode or "", "slate"),
                    "alignment_score": data.get("alignment_score"),
                    "responded_at":    e["timestamp"],
                    "state":           "RESPONDED",
                })

        return sorted(
            sessions.values(),
            key=lambda h: h.get("responded_at") or h.get("initiated_at", ""),
            reverse=True,
        )

    def get_handshake(self, session_id: str) -> dict | None:
        entries = self._read_all()
        result: dict = {}

        for e in entries:
            eid  = e.get("event_id")
            data = e.get("data", {})
            if data.get("session_id") != session_id:
                continue

            if eid == _HANDSHAKE_INITIATED:
                result.setdefault("session_id",   session_id)
                result.setdefault("initiator_id", data.get("initiator_id", e.get("agent_id")))
                result.setdefault("initiated_at", e["timestamp"])
                result.setdefault("state",        "INITIATED")

            elif eid == _HANDSHAKE_RESPONDED:
                mode = data.get("mode")
                result.update({
                    "session_id":      session_id,
                    "initiator_id":    data.get("initiator_id", result.get("initiator_id")),
                    "counterpart_id":  data.get("counterpart_id"),
                    "mode":            mode,
                    "mode_color":      _MODE_COLORS.get(mode or "", "slate"),
                    "alignment_score": data.get("alignment_score"),
                    "rationale":       data.get("rationale"),
                    "alignment_report": data.get("alignment_report"),
                    "responded_at":    e["timestamp"],
                    "state":           "RESPONDED",
                })
                result.setdefault("initiated_at", e["timestamp"])

        if not result:
            return None

        # Enrich with per-agent principle data from declaration events
        agent_decls  = self._agent_declarations()
        initiator_id = result.get("initiator_id")
        counterpart_id = result.get("counterpart_id")

        def _agent_summary(aid: str | None) -> dict:
            if not aid or aid not in agent_decls:
                return {"agent_id": aid, "principles": {}, "coverage_score": None}
            d = agent_decls[aid]
            return {
                "agent_id":      aid,
                "principles":    d.get("principles", {}),
                "coverage_score": d.get("coverage_score"),
                "context_summary": d.get("context_summary"),
            }

        result["initiator"]  = _agent_summary(initiator_id)
        result["counterpart"] = _agent_summary(counterpart_id)

        # Annotate alignment report gaps with principle names
        report = result.get("alignment_report") or {}
        for gap in report.get("gaps", []):
            pid = gap.get("principle_id", "")
            gap["principle_name"] = _PRINCIPLE_NAMES.get(pid, pid)
            gap["self_color"]        = _STATUS_COLORS.get(gap.get("self_status", ""), "slate")
            gap["counterpart_color"] = _STATUS_COLORS.get(gap.get("counterpart_status", ""), "slate")

        return result

    def list_agents(self) -> list[dict]:
        entries = self._read_all()
        agents: dict[str, dict] = {}
        handshake_counts: dict[str, int] = {}

        for e in entries:
            eid  = e.get("event_id")
            aid  = e.get("agent_id", "")
            data = e.get("data", {})

            if eid == _DECLARATION_CREATED:
                if aid not in agents:
                    agents[aid] = {
                        "agent_id":         aid,
                        "declaration_count": 0,
                        "first_seen":        e["timestamp"],
                        "last_seen":         e["timestamp"],
                        "coverage_score":    0.0,
                        "principles":        {},
                        "context_summary":   None,
                    }
                agents[aid]["declaration_count"] += 1
                agents[aid]["last_seen"]      = e["timestamp"]
                agents[aid]["coverage_score"] = data.get("coverage_score", 0.0)
                agents[aid]["principles"]     = data.get("principles", {})
                agents[aid]["context_summary"] = data.get("context_summary")

            elif eid == _HANDSHAKE_INITIATED:
                init_id = data.get("initiator_id", aid)
                handshake_counts[init_id] = handshake_counts.get(init_id, 0) + 1

            elif eid == _HANDSHAKE_RESPONDED:
                for key in ("initiator_id", "counterpart_id"):
                    participant = data.get(key, "")
                    if participant:
                        handshake_counts[participant] = handshake_counts.get(participant, 0) + 1

        for aid, agent in agents.items():
            agent["handshake_count"] = handshake_counts.get(aid, 0)
            # Build colored principle pills for template use
            agent["principle_pills"] = [
                {
                    "id":     pid,
                    "name":   _PRINCIPLE_NAMES.get(pid, pid),
                    "status": status,
                    "color":  _STATUS_COLORS.get(status, "slate"),
                }
                for pid, status in sorted(agent["principles"].items())
            ]

        return sorted(agents.values(), key=lambda a: a["last_seen"], reverse=True)

    def principle_heatmap(self) -> list[dict]:
        """Returns per-principle status counts across all declarations, ordered C1–C11."""
        counts: dict[str, dict[str, int]] = {
            f"C{i}": {"COMPLIANT": 0, "DECLARED": 0, "PARTIAL": 0, "NOT_APPLICABLE": 0}
            for i in range(1, 12)
        }
        entries = self._read_all()
        for e in entries:
            if e.get("event_id") == _DECLARATION_CREATED:
                for pid, status in e.get("data", {}).get("principles", {}).items():
                    if pid in counts and status in counts[pid]:
                        counts[pid][status] += 1

        result = []
        for pid in [f"C{i}" for i in range(1, 12)]:
            c     = counts[pid]
            total = sum(c.values())
            result.append({
                "id":     pid,
                "name":   _PRINCIPLE_NAMES[pid],
                "counts": c,
                "total":  total,
                # Percentage of non-NA declarations (for coverage insight)
                "covered_pct": (
                    round(100 * (c["COMPLIANT"] + c["DECLARED"] + c["PARTIAL"]) / total)
                    if total > 0 else 0
                ),
            })
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _agent_declarations(self) -> dict[str, dict]:
        """Latest declaration data keyed by agent_id."""
        agents: dict[str, dict] = {}
        for e in self._read_all():
            if e.get("event_id") == _DECLARATION_CREATED:
                aid  = e.get("agent_id", "")
                data = e.get("data", {})
                agents[aid] = {
                    "principles":     data.get("principles", {}),
                    "coverage_score": data.get("coverage_score"),
                    "context_summary": data.get("context_summary"),
                }
        return agents

    def is_empty(self) -> bool:
        """True when the journal has no entries — used to decide whether to seed."""
        return not self._journal.is_file() or self._journal.stat().st_size == 0

    # ------------------------------------------------------------------
    # Constants for templates
    # ------------------------------------------------------------------

    @staticmethod
    def principle_names() -> dict[str, str]:
        return _PRINCIPLE_NAMES

    @staticmethod
    def mode_colors() -> dict[str, str]:
        return _MODE_COLORS

    @staticmethod
    def status_colors() -> dict[str, str]:
        return _STATUS_COLORS
