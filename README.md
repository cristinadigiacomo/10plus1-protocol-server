# 10+1 Protocol MCP Server

**The AI↔AI ethical handshake layer for the 10+1 Standard.**

## What It Does

When one AI agent needs to work with another — or when a system needs to verify that an AI agent is operating within defined ethical boundaries — they need a shared language for declaring and verifying intent.

The 10+1 Protocol MCP Server provides that language as a Model Context Protocol (MCP) server. An agent can:

1. **Declare its posture** — generate a signed Handshake Declaration mapped to the 11 principles of the 10+1 Standard (C1–C11)
2. **Validate a counterpart's declaration** — verify signature, check compliance mapping, assess posture alignment
3. **Receive a disposition signal** — one of four structured modes that tell it how to proceed
4. **Log interactions** — structured event trail via Windows Event Log (event IDs 7000–7499)

## The Four Operating Modes

| Mode | Meaning |
|------|---------|
| `PROCEED` | Counterpart's posture is aligned. Continue normally. |
| `REROUTE` | Posture gap detected. Adjust approach before continuing. |
| `COMPLETE_AND_FLAG` | Task can complete but the interaction needs review. |
| `REFUSE` | Posture is incompatible. Do not proceed. |

## Stack Position

```
10+1 Standard     →  JSON schemas for 11 ethical principles (open, npm)
10+1 Validator    →  Compliance checker CLI/library (npm)
10+1 Governance   →  Enterprise runtime governance layer (MCP server)
10+1 Protocol     →  AI↔AI handshake layer (this)
```

## Key Design Findings

This server's architecture is grounded in empirical research (the Moltbook Experiment and Handshake Protocol Testing Report):

- **Contextual embedding beats header declaration** — 73% acknowledgment when posture is embedded in context vs. 0% in header blocks
- **Trained Politeness Ceiling** — RLHF-saturated agents cannot become more cooperative; they need directional definition, not just encouragement
- **ROR (Refused-Or-Rerouted) rate** is the primary health metric for any Protocol deployment
- **Finite Agent Protocol** defines exactly when an agent must stop, flag, reroute, or refuse

## Transport

MCP stdio transport. Runs as a local process, integrated with Claude Code or any MCP-capable host.

## Project Status

🔴 Phase 1 — In planning

## Part of the 10P1 Inc. Stack

- [10+1 Standard](https://github.com/cristinadigiacomo/10-1-Standard)
- [10plus1.co](https://10plus1.co)
