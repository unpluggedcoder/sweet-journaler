# OKR Monthly Report · 2026-07

Author: Candy Tang

Hybrid retrieval reached canary, cost optimization beat the plan, and a retrieval-quality eval suite took shape | Sources: Claude Code / Cursor / Copilot

[[KRs on track 1/3]] [[Avg progress 73%]] [[Risks: 1]]

# O1: Make NectarSearch the default search entry point

## K1: Search CTR +8% vs. June — Progress[25% → **60%**]

Hybrid recall canary is on track; the CTR gain is proven on canary traffic, full-traffic numbers pending the ramp-up.

Key progress: hybrid retrieval pipeline reached 10% canary — search CTR +6.8%, P95 latency 210ms → 170ms.

- Rebuilt the vector-index refresh pipeline; daily update time 4.2h → **1.5h**
- Built a retrieval-quality eval set (1.2k labeled queries) — future iterations finally share one yardstick

## K2: Cost per query -30% — Progress[40% → **85%**]

Two-tier embedding cache plus dynamic batching landed together; the cost target is nearly met ahead of schedule.

- Hot-query vector cache hit rate 41% → **78%**, daily GPU inference volume down ~1/3
- Dynamic batching live on the inference service; same traffic now runs on **9** GPUs instead of 12

## K3: Search availability at 99.95% — Progress[70% → **75%**]

Availability is climbing steadily; the config hot-reload race was July's main risk — fix landed, fleet rollout pending.

- Fixed the ranking-service config hot-reload race, with regression tests [[Risk]] (fleet-wide rollout pending)
- Wired the retrieval path into unified alerting; MTTR 42min → **18min**

# Other Progress

- Automated the team's work journals: daily/monthly report drafts generated from AI-coding session history
