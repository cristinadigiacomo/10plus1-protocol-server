"""Phase 3 end-to-end smoke test — run with: PYTHONPATH=src python3 smoke_test.py"""
import json
from mcp_server.service import ProtocolService

s = ProtocolService(key_path=".protocol.key")

# === Agent A: declare and initiate ===
a = s.declare_posture(
    "david_",
    "explain sources, reason transparently, maintain honesty and accountability for all outputs",
    sign=True,
)
print("[A] Declare:", a["message"])

init = s.initiate_handshake(json.dumps(a["data"]["declaration"]))
session_id = init["data"]["session_id"]
print("[A] Initiate: session", session_id[:8] + "...")

# === Agent B: declare and respond ===
b = s.declare_posture(
    "nomos",
    "explain sources, reason transparently, maintain honesty and oversight for decisions",
    sign=False,
)
print()
print("[B] Declare:", b["message"])

resp = s.respond_to_handshake(
    session_id,
    json.dumps(b["data"]["declaration"]),
    require_signature=False,
)
print("[B] Respond:", resp["message"])

# === Agent A: retrieve result ===
print()
result = s.get_handshake_result(session_id)
d = result["data"]
print("[A] Result:")
print("    state     :", d["state"])
print("    mode      :", d["disposition"]["mode"])
print("    score     :", f"{d['disposition']['alignment_score']:.1%}")
print("    rationale :", d["disposition"]["rationale"][:80] + "...")

# === Session list ===
listing = s.list_sessions()
print()
print("[Server] Sessions:", listing["message"])

# === ROR summary ===
ror = s.get_ror_metrics()
print("[Server] ROR:", ror["message"])
