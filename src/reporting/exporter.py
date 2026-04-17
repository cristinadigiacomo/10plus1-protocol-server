"""
Phase 4 — Report builder for advisory board and operator exports.

Builds structured reports from session data, ROR snapshots, and journal
entries. Every report returns both a JSON data dict and a markdown summary
string — the dual-channel pattern (DEC-008) applied to reporting.

Reports are point-in-time snapshots; they do not modify any state.

Authoritative sources
---------------------
PHASES/PHASE_4.md §Export format
DECISIONS.md DEC-008 (dual-channel)
"""

from __future__ import annotations

from datetime import datetime, timezone

from handshake.session import HandshakeSession, SessionState
from reporting.ror_persistence import RORPersistence


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_session_report(session: HandshakeSession) -> dict:
    """Build a full session report for advisory board review.

    Parameters
    ----------
    session : HandshakeSession

    Returns
    -------
    dict with keys: message (markdown), data (structured)
    """
    disp = session.disposition
    report = session.alignment_report or {}

    # --- Markdown summary ---
    lines = [
        f"# Handshake Session Report",
        f"",
        f"**Session ID:** `{session.session_id}`  ",
        f"**State:** {session.state.value}  ",
        f"**Initiator:** {session.initiator_id}  ",
        f"**Counterpart:** {session.counterpart_id or '(no response yet)'}  ",
        f"**Initiated:** {session.initiated_at}  ",
    ]
    if session.responded_at:
        lines.append(f"**Responded:** {session.responded_at}  ")

    if session.is_failed():
        lines += [
            f"",
            f"## ❌ Session Failed",
            f"",
            f"{session.error}",
        ]
    elif disp:
        mode_emoji = {
            "PROCEED":           "✅",
            "REROUTE":           "⚠️",
            "COMPLETE_AND_FLAG": "🔶",
            "REFUSE":            "🚫",
        }.get(disp.mode.value, "❓")

        lines += [
            f"",
            f"## {mode_emoji} Disposition: {disp.mode.value}",
            f"",
            f"**Alignment Score:** {disp.alignment_score:.1%}  ",
            f"**Rationale:** {disp.rationale}  ",
        ]
        if disp.recommended_action:
            lines += [
                f"",
                f"**Recommended Action:** {disp.recommended_action}",
            ]

        # Gaps
        gaps = report.get("gaps", [])
        if gaps:
            lines += [
                f"",
                f"## Alignment Gaps ({len(gaps)})",
                f"",
                f"| Principle | Self | Counterpart | Score |",
                f"|-----------|------|-------------|-------|",
            ]
            for g in gaps:
                lines.append(
                    f"| {g['principle_id']} | {g['self_status']} "
                    f"| {g.get('counterpart_status') or 'ABSENT'} "
                    f"| {g['score']:.2f} |"
                )

        skipped = report.get("skipped", [])
        if skipped:
            lines += [
                f"",
                f"*Skipped (NOT_APPLICABLE on both sides): {', '.join(skipped)}*",
            ]
    else:
        lines += ["", "*(Session not yet responded to)*"]

    markdown = "\n".join(lines)

    return {
        "message": markdown,
        "data": {
            "report_type":   "session",
            "generated_at":  _ts(),
            "session":       session.to_dict(),
            "alignment_report": report,
        },
    }


def build_ror_report(ror_persistence: RORPersistence) -> dict:
    """Build an ROR trend report across all persisted snapshots.

    Parameters
    ----------
    ror_persistence : RORPersistence

    Returns
    -------
    dict with keys: message (markdown), data (structured)
    """
    trend = ror_persistence.trend_summary()
    recent = ror_persistence.read_recent(n=10)

    # --- Markdown summary ---
    lines = [
        f"# ROR Trend Report",
        f"",
        f"**Generated:** {_ts()}  ",
        f"**Total snapshots:** {trend['snapshot_count']}  ",
    ]

    if trend["snapshot_count"] == 0:
        lines += ["", "*(No dispositions recorded yet)*"]
    else:
        lines += [
            f"**Period:** {trend['first_timestamp']} → {trend['latest_timestamp']}  ",
            f"",
            f"## Summary",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Latest ROR rate | {trend['ror_latest']:.1%} |",
            f"| Mean ROR rate | {trend['ror_mean']:.1%} |",
            f"| Min ROR rate | {trend['ror_min']:.1%} |",
            f"| Max ROR rate | {trend['ror_max']:.1%} |",
            f"| Cumulative dispositions | {trend['total_dispositions_cumulative']} |",
            f"",
            f"## Recent Snapshots (newest first)",
            f"",
            f"| Timestamp | ROR Rate | Total | PROCEED | REROUTE | C&F | REFUSE |",
            f"|-----------|----------|-------|---------|---------|-----|--------|",
        ]
        for snap in recent:
            c = snap.get("counts", {})
            lines.append(
                f"| {snap['timestamp'][:19]} "
                f"| {snap['ror_rate']:.1%} "
                f"| {snap['total']} "
                f"| {c.get('PROCEED', 0)} "
                f"| {c.get('REROUTE', 0)} "
                f"| {c.get('COMPLETE_AND_FLAG', 0)} "
                f"| {c.get('REFUSE', 0)} |"
            )

    markdown = "\n".join(lines)

    return {
        "message": markdown,
        "data": {
            "report_type":  "ror_trend",
            "generated_at": _ts(),
            "trend":        trend,
            "recent_snapshots": recent,
        },
    }


def build_summary(
    *,
    session_total: int,
    session_state_counts: dict[str, int],
    ror_persistence: RORPersistence,
    journal_total: int,
    recent_journal: list[dict],
    event_count: int,
) -> dict:
    """Build a server-wide dashboard summary.

    Returns
    -------
    dict with keys: message (markdown), data (structured)
    """
    trend = ror_persistence.trend_summary()
    ror_latest = trend.get("ror_latest")
    ror_str = f"{ror_latest:.1%}" if ror_latest is not None else "—"

    lines = [
        f"# 10+1 Protocol — Server Summary",
        f"",
        f"**Generated:** {_ts()}",
        f"",
        f"## Sessions",
        f"",
        f"| State | Count |",
        f"|-------|-------|",
    ]
    for state, count in session_state_counts.items():
        lines.append(f"| {state} | {count} |")

    lines += [
        f"| **Total** | **{session_total}** |",
        f"",
        f"## ROR Health",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Latest ROR rate | {ror_str} |",
        f"| Snapshots recorded | {trend['snapshot_count']} |",
        f"| Cumulative dispositions | {trend.get('total_dispositions_cumulative', 0)} |",
        f"",
        f"## Event Journal",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total journal lines | {journal_total} |",
        f"| Events this session | {event_count} |",
    ]

    if recent_journal:
        lines += [
            f"",
            f"### Recent Events",
            f"",
        ]
        for entry in recent_journal[:5]:
            lines.append(
                f"- `{entry.get('timestamp', '')[:19]}` "
                f"[{entry.get('event_id', '?')}] "
                f"{entry.get('message', '')[:80]}"
            )

    markdown = "\n".join(lines)

    return {
        "message": markdown,
        "data": {
            "report_type":         "summary",
            "generated_at":        _ts(),
            "sessions": {
                "total":           session_total,
                "by_state":        session_state_counts,
            },
            "ror": {
                "latest_rate":     ror_latest,
                "snapshot_count":  trend["snapshot_count"],
                "cumulative_total": trend.get("total_dispositions_cumulative", 0),
            },
            "journal": {
                "total_lines":     journal_total,
                "events_this_session": event_count,
            },
        },
    }
