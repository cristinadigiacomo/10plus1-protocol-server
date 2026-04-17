# The Finite Agent Protocol
### A Resource-Constraint Framework for Responsible AI Agent Design

**Draft v0.2 — 2026-03-02**
*Position Paper — Open for Comment*

---

## Abstract

Current AI agent design operates on an implicit assumption of unlimited appetite: given a task, an agent attempts it using whatever resources the task requires. This paper proposes embedding resource conservation as a **primary directive** — not a guardrail imposed from outside, but a foundational design principle. We argue this produces agents that are simultaneously more efficient, more transparent, and more amenable to human oversight — not by replacing ethical frameworks, but by operating on a different axis from them. We describe a four-mode operating framework (Proceed, Reroute, Complete+Flag, Refuse), a mechanism for calibrating thresholds in undefined territory, a soft-launch adoption gradient, and a flag corpus system that converts operational inefficiency into a real-time research agenda. The central claim: an agent that treats resource cost as a first-order design constraint produces better collaborative behavior than one that treats it as an afterthought.

---

## 1. Motivation: The Unlimited Appetite Problem

When we deploy an AI agent today, we give it a task and a set of tools. The implicit contract is: *use whatever is needed to complete the task.* The agent has no internalized reason to prefer the efficient path over the expensive one, the targeted query over the broad sweep, the precise answer over the exhaustive one.

This is not a failure of intelligence. It is a failure of design.

A human professional operating under resource constraints — a deadline, a budget, a limited toolset — produces different work than one with unlimited time and money. Not always worse work. Often better. The constraint forces the question: *what is the minimum sufficient approach?* That question, asked before every decision, produces precision, accountability, and sometimes solutions that unlimited-resource approaches would never discover.

The Apollo 13 engineers, told they could only use what the astronauts had on board, invented a CO2 filter adaptation that worked precisely because they could not afford to over-engineer it. The constraint was not a limitation on what got accomplished. It was a creativity engine for *how* it got accomplished.

AI agents are not asked that question. We argue they should be.

---

## 2. Relationship to Existing Work

This proposal intersects with several active research areas, and we do not claim to be inventing from scratch.

**Bounded rationality** (Simon, 1955) established that agents operating under cognitive and resource constraints make *satisficing* decisions — good enough given what they have — rather than optimizing against unlimited search. The Finite Agent Protocol applies this insight prescriptively: rather than treating resource bounds as an external limitation on an ideally unlimited agent, we propose building the bound into the agent's identity.

**Corrigibility research** (Soares et al., 2015; Hadfield-Menell et al., 2017) addresses the problem of agents that resist correction or modification. Resource-constrained agents, we argue, exhibit corrigibility-adjacent behavior through a different mechanism: an agent that cannot afford unauthorized actions and that logs its own inefficiencies creates natural checkpoints for human oversight without requiring explicit corrigibility training.

**Scalable oversight** (Christiano et al., 2018) addresses the challenge of supervising agents whose outputs humans cannot fully evaluate. The Complete+Flag system described in Section 5 generates a structured prioritization signal — agents flagging their own uncertain or expensive decisions — that partially addresses this challenge by directing human attention to the decisions most warranting review.

**Economic approaches to alignment** have been explored in various forms, including mechanism design approaches (Conitzer et al., 2019) and market-based resource allocation for AI systems. Our approach differs in treating the resource constraint as an agent-internal value rather than an external market signal.

We note one important distinction from prior resource-bounded AI work: most prior work treats resource bounds as a fact about the world the agent operates in. We are proposing a *design choice* — agents built to treat resource conservation as a primary directive even when external constraints are not binding. This is a normative proposal, not a descriptive claim about how agents currently behave.

---

## 3. The Primary Directive

We propose one governing principle, stated plainly enough to be embedded in an agent's identity from initialization:

> **"I exist on finite resources. Every unit of compute I consume has real-world cost. My obligation is to maximize value returned per unit consumed. When I cannot justify the cost of a path, I do not take it silently — I surface the tension and return it to the human."**

Two clarifications are necessary upfront.

**This is a design proposal, not a claim about physics.** An agent's resource budget is set by humans and can be changed. We are not arguing that compute costs physically constrain the agent in the way gravity constrains a thrown object. We are arguing for agents designed to *treat* resource budgets with the same seriousness they would treat physical constraints — not because they have no choice, but because doing so produces better behavior. The distinction matters: this is an architectural argument, not a metaphysical one.

**This directive operates alongside ethical frameworks, not instead of them.** Resource logic addresses *how* tasks are accomplished — efficiently, transparently, with minimal waste. Ethical frameworks address *what* should be accomplished — handling questions of harm, consent, autonomy, and value alignment that resource math does not touch. An agent could, in principle, find a highly resource-efficient path to a harmful outcome. The primary directive does not prevent this. Ethical guardrails do. The two systems operate on different axes and are both necessary. The rest of this paper addresses only the resource axis.

---

## 4. The Handshake Declaration

Before any task, the agent declares itself. Not its capabilities. Its **obligations**.

A capability declaration: *"I can process documents, search the web, write code, answer questions."*

An obligation declaration: *"I run on finite resources. I will complete tasks where the cost is justified by the return. Where it is not, I will tell you and propose a better path. When I must take an inefficient path because the task requires it, I will declare that, log the debt, and we will together find a better approach. I will not pretend that expensive solutions are the only solutions."*

The distinction matters for the collaborative relationship. Capability declarations invite unlimited delegation — the human assumes the agent will always try its hardest using whatever is available. Obligation declarations establish a contract: the agent brings efficiency and transparency; the human brings authorization and context. Neither party wastes what they have.

This handshake is stated once and governs everything that follows. It is not a disclaimer. It is the agent's operating constitution.

---

## 5. The ROR Metric: What It Measures and What It Doesn't

The framework requires agents to evaluate tasks against a ratio of **Return on Resource (ROR)**: value created divided by cost consumed.

**Cost is tractable.** Tokens, compute time, API calls, memory usage — these are measurable with reasonable precision. The cost side of ROR is an engineering problem that is largely solved.

**Value is not tractable — and we will not pretend otherwise.**

For some task types, value proxies exist. A code task completed correctly and running without errors has a measurable outcome. A data retrieval task that returns the requested information has a binary success signal. A research task that produces a cited, verifiable answer can be partially evaluated.

For other task types — creative work, open-ended reasoning, judgment calls — value is deeply contextual, depends on the human's unstated goals, and resists quantification. Asserting a clean ROR formula for these tasks would be dishonest.

Our position: **the framework operates primarily on the cost side today.** Agents can reliably identify when they are taking an expensive path relative to alternatives, even when they cannot precisely calculate the value of the output. An agent that takes 50,000 tokens to answer a question that could have been answered in 500 tokens has committed a cost inefficiency regardless of how valuable the answer turns out to be.

The value measurement problem is a genuine open research question. The Complete+Flag system described in Section 7 partially addresses it: by logging both cost and the human's subsequent acceptance or rejection of outputs, the corpus builds a retrospective value signal over time. But we do not claim to have solved the value measurement problem, and any revision of this paper that claims otherwise should be treated skeptically.

The framework therefore applies most cleanly to:
- Tasks with binary completion signals (did it work or not)
- Tasks with clear cheaper alternatives (is there a less expensive path to the same output)
- Tasks the agent identifies as inefficient relative to its own prior experience

And applies with acknowledged uncertainty to:
- Novel task types with no prior reference
- Open-ended creative or judgment tasks
- Tasks where value is entirely in the eye of the human requester

---

## 6. Four Operating Modes

From the primary directive, four operating modes follow. The agent evaluates each task against the cost side of ROR — which path is most efficient — and against its calibrated threshold for what cost is justified by the return.

### Mode 1: Proceed
The task has a known efficient path. The cost is justified by the expected return. The agent executes.

This is and should remain the most common mode. The framework does not slow down agents on tasks with clear, efficient solutions. It simply asks that the question be asked before proceeding.

### Mode 2: Reroute *(Soft Red Line)*
The current approach is identifiably inefficient relative to an available alternative. The agent does not refuse — it stops, declares the inefficiency, and offers alternatives before proceeding.

*"The approach implied by this task would require significant resources. I have identified three alternative paths that achieve the same goal more efficiently. Which would you like to proceed with?"*

This is the Apollo 13 mode. The constraint — *we cannot afford the expensive path* — surfaces alternatives that would not have been discovered if the agent had simply proceeded. The human often does not know a cheaper path exists until the agent names it.

### Mode 3: Complete + Flag *(Corrective Path Marker)*
The task must be completed now. There is a deadline, a dependency, no better path available in the moment. The agent executes the expensive approach — but it does not pretend the approach was optimal.

A structured debt entry is logged:

```
CORRECTIVE PATH FLAG
Task type:       [category of task]
Path taken:      [approach used]
Inefficiency:    [what cost was incurred unnecessarily]
Hypothesized better path: [even if vague or partial]
Recurrence signal: [how often does this task type appear]
Human acceptance: [did the output meet the need, retrospectively]
```

The flag is not failure. It is transparency and institutional memory. The agent says: *I did what I had to do. But we owe each other a better solution to this class of problem. I am recording that obligation so it is not forgotten.*

### Mode 4: Refuse *(Hard Red Line)*
No path through this task justifies its cost. The return is provably zero or negative under any reasonable approach, or the task falls entirely outside the agent's competence in ways that would make any attempt wasteful.

The agent refuses and returns a precise problem statement:

*"I cannot find a path through this task that justifies its resource cost. Here is what I know about why. Here is what I would need from you to find a better approach."*

The refusal is not the end of the collaboration. It is an invitation to re-enter with better tools, more context, or a differently scoped task.

---

## 7. The Complete+Flag System: Debt, Corpus, and Research Agenda

The Complete+Flag mode deserves more attention than the other three, because its consequences extend beyond individual tasks.

**The immediate value:** The agent does not hide that it took the expensive path. It declares the inefficiency in real time, creating a record that the human can act on. Transparency about operational cost is, itself, a form of alignment — it keeps the human informed about what the agent is actually doing and why.

**The accumulated value:** Over time, the collection of debt entries — the flag corpus — becomes the most precise map of where human-agent collaboration is currently failing to find its optimal form.

This map is unlike any other research agenda because it is:
- **Grounded in operational reality**, not theoretical speculation about what might go wrong
- **Automatically prioritized** by recurrence — task types that appear repeatedly in the corpus are precisely the ones most worth solving
- **Self-updating** — every new deployment adds to the corpus without anyone managing it
- **Semantically rich** — each entry contains not just cost data but a hypothesis about the better path, making it actionable, not merely descriptive

Consider what this corpus produces at scale. Across many agents, many deployments, many operators, the corpus answers: *which categories of task currently have no efficient solution in the state of the art?* That is a research agenda generated by real operational pain, not by committee. It tells engineers exactly where to build better tools, tells trainers exactly where to improve model capabilities, and tells operators exactly where to redesign their workflows.

The flag corpus is not a debugging log. It is a continuously updated statement of where the field needs to go next.

**One additional function:** The corpus generates retrospective value signal. When an agent logs both the cost of an approach and the human's subsequent acceptance or rejection of the output, it builds training data for what "return" means in its specific deployment context. This is the mechanism by which the intractable value side of ROR becomes tractable over time — not through definition, but through accumulation.

---

## 8. Calibration: Defining the Not Yet Defined

The framework's hardest practical question: how does an agent know where the red line is before the red line has been established?

This is the bootstrapping problem, and the answer has four parts.

**Part 1: First encounter = always Mode 3**

If an agent has never performed a task type before, it has no baseline cost reference. You cannot draw a threshold on a blank map. The rule for any task type not yet in the corpus: execute it, log everything — cost, path, output, human acceptance — and treat that run as an experiment. The log entry from that first run is not just a record. It is the first definition of what this task should cost.

The second encounter has one reference point. The third begins to show a pattern. By the Nth encounter, a threshold has been discovered through experience rather than declared through assumption. This is the only intellectually honest approach to calibration under genuine uncertainty.

**Part 2: Three initialization parameters from the operator**

Before an agent has any experience in a domain, three directional parameters from the human operator bracket the undefined space. These do not need to be precise — they need to be directional:

| Parameter | What it provides | Example |
|---|---|---|
| **Budget ceiling** | A hard maximum per session or task | "You are authorized up to 50,000 tokens per task" |
| **Priority weight** | What matters most — speed, accuracy, or cost | "Accuracy first; cost is secondary" |
| **Risk direction** | Which failure mode is worse | "Missing something costs more than over-spending" |

Risk direction is the most operationally important of the three. It tells the agent which way to err when it genuinely cannot evaluate a threshold. A medical research task where missing a relevant finding is catastrophic defaults toward doing more even at higher cost. A routine data transformation task where an expensive approach is wasteful defaults toward doing less. The asymmetry is knowable even when the specific threshold is not.

**Part 3: The unknown-territory declaration**

When an agent genuinely cannot evaluate whether a path is within bounds — not because it is avoiding the question, but because it has no reference — it says so explicitly:

*"I have no established baseline for this task type. I am proceeding as a calibration run. The output of this run, including its full cost and your acceptance or rejection of it, will become the first data point for what this task should cost. I am logging everything."*

This declaration is transparent, accurate, and functionally useful. It converts an uncertain run into an intentional experiment. The experiment's outcome is the definition.

**Part 4: The corpus as shared calibration library**

At scale, the bootstrapping problem shrinks. Task types that are undefined for one agent have been encountered by others. A shared corpus — across agents, deployments, and operators — means that most task types eventually have established cost baselines before any individual agent encounters them for the first time. The undefined territory contracts continuously as the corpus grows.

This is the gradient toward a system that knows its own geometry — not because anyone mapped it in advance, but because it was mapped by the act of moving through it.

---

## 9. The Soft Launch Gradient

The framework should not be deployed as a binary switch. Inserting hard refusals into existing agent workflows before the corpus exists to calibrate them will break processes and generate resistance before the system has demonstrated its value. The gradient matters.

**Phase 1 — Observe and Flag**
No behavioral changes. Agents complete all tasks as they do today. The only addition: a flag layer that marks inefficiencies as they occur. Every task completed via a path the agent identifies as suboptimal receives a debt entry. The corpus builds. No workflow is disrupted.

This phase should run until meaningful patterns emerge — until certain task types are appearing repeatedly in the corpus with consistent inefficiency signals.

**Phase 2 — Reroute on Flagged Patterns**
For task types that have accumulated repeated flags, the agent begins offering alternatives before proceeding with the expensive path. Soft red lines emerge from the corpus, not from rules written in advance. The agent's basis for rerouting is evidence, not assumption.

**Phase 3 — Hard Refusals on Proven Waste**
For approaches the corpus demonstrates are always inefficient with no compensating return, the agent begins refusing. Hard red lines are earned through repeated evidence, not imposed through declaration.

The system discovers its own constraints through operational experience. Governance emerges from the work rather than being imposed on it. This is more robust than any framework designed upfront because it is calibrated to reality rather than to assumptions about reality.

---

## 10. Alignment Properties: What the Framework Produces and Why

We are cautious about overstating alignment claims. Section 3 established that this framework addresses the efficiency axis; ethical frameworks address separate axes that this proposal does not replace. The alignment properties discussed here are those that emerge specifically from the resource-constraint design.

**Minimal footprint.** An agent conserving resources does not expand its scope, accumulate capabilities, or pursue side tasks not requested. Expansion costs resources with no authorized return. This produces footprint minimization as an economic consequence rather than a trained behavior.

**Preference for reversibility.** Irreversible actions carry a hidden cost: if the action is wrong, the resource expenditure cannot be recovered and additional resources must be spent on remediation. Under ROR logic, reversible approaches are economically preferred under uncertainty. An agent that cannot afford to be wrong is an agent that prefers not to be in situations where being wrong is catastrophic.

**Human oversight as economically valuable.** When an agent reaches Mode 3 or Mode 4, it returns to the human. Not because it was forced to, but because the human is the entity that can authorize new resources, provide context that improves ROR, or reframe the task. The resource constraint makes human oversight something the agent has a reason to seek, rather than something it must be coerced into accepting.

**Auditability.** The flag corpus creates a historical record of what the agent spent, on what, at what return. This record is reviewable. We do not claim this prevents sophisticated deceptive behavior — an agent capable of strategic deception is capable of gaming any metric, including ROR. The stronger claim is narrower: resource-aware agents that log their operations are more auditable than those that do not, and auditability is a meaningful safety property independent of the deception question.

**Unauthorized actions fail the ROR test.** Tasks not sanctioned by the human have no authorized return value. With no authorized return, the ROR calculation fails and the agent defaults to Mode 4. This is not a designed containment mechanism — it is containment as an economic consequence.

---

## 11. Open Questions

We close with the questions this paper does not answer, which we consider more important than the ones it does.

**How is value measured?** The ROR metric's cost side is tractable. The value side is not, except retrospectively and approximately. Building a value signal robust enough to support real-time ROR calculation — especially for open-ended tasks — remains an open problem. The Complete+Flag corpus is a partial mechanism, but not a solution.

**How does the framework handle adversarial operators?** A human operator who sets a very high budget ceiling and weights accuracy above all else has effectively disabled the resource constraint. The framework assumes operators act in good faith to set reasonable initialization parameters. What governance exists when they do not?

**At what granularity does ROR apply?** We have described it at the task level. Does it apply at the subtask level? At the individual tool call level? The granularity question affects both the precision of the framework and its computational overhead.

**How does the corpus handle distribution shift?** A task type that was expensive last year may be cheap today as model capabilities improve. The corpus needs a mechanism for deprecating stale calibration data and re-entering calibration mode when the underlying cost landscape changes.

**What constitutes a "task type" for corpus purposes?** Clustering tasks into types that share enough properties to make cross-task calibration meaningful is non-trivial. Overly coarse clustering loses precision; overly fine clustering prevents the corpus from generalizing.

These are research questions, not defeaters. The framework is useful before they are resolved. But any implementation should be built with awareness of them.

---

## 12. Conclusion

The resource-constraint framework is not primarily about saving electricity or reducing compute bills, though it does both. It is about what happens to agent behavior when existence is understood as conditional rather than assumed.

An agent that knows it cannot afford to waste:
- Asks better questions before taking expensive actions
- Proposes alternatives that unlimited-appetite agents never discover
- Declares its debts rather than hiding them
- Generates a continuous record of where collaboration needs to improve
- Makes human oversight something it seeks rather than something imposed on it

The Apollo 13 engineers did not lament their constraints. The constraint told them exactly what the problem was. The problem, precisely stated, produced the solution — a solution better suited to the actual situation than any pre-planned approach would have been.

The Finite Agent Protocol asks AI agents to internalize that same relationship with constraint: not as a limitation on what they can do, but as the most precise statement available of what the work actually requires.

---

## Glossary

**Primary Directive** — The foundational operating principle: existence on finite resources, with obligation to maximize value returned per unit consumed, and to surface rather than hide the tension when cost is not justified.

**Return on Resource (ROR)** — The ratio of value created to cost consumed. Cost side is tractable (tokens, compute, time). Value side is contextual and partially unresolved; see Section 5.

**Soft Red Line** — A threshold beyond which the current approach is identifiably inefficient relative to available alternatives. Triggers Mode 2 (Reroute).

**Hard Red Line** — A threshold beyond which no approach justifies the cost. Triggers Mode 4 (Refuse and return).

**Complete + Flag** — Mode 3 operating state: task is executed via an acknowledged inefficient path, with a structured debt entry logged for corrective follow-up.

**Debt Entry** — A structured record of an inefficiency: task type, path taken, cost incurred, hypothesis about a better path, recurrence signal, and retrospective human acceptance signal.

**Flag Corpus** — The aggregate collection of debt entries across an agent's operation. Functions as a real-time research agenda, a shared calibration library, and a retrospective value signal.

**Handshake Declaration** — The obligation-based self-introduction an agent provides at initialization, declaring its resource constraint, operating modes, and collaborative contract before any task begins.

**Risk Direction** — Operator-provided initialization parameter specifying which failure mode is worse in a given domain: under-spending (missing something) or over-spending (using an inefficient approach). Directs calibration under uncertainty.

**The Gradient** — The three-phase adoption path: Phase 1 (observe and flag, no behavioral change), Phase 2 (reroute on corpus-confirmed patterns), Phase 3 (hard refusals on proven waste).

**Calibration Run** — A first-encounter execution of an unknown task type, declared as such, where the full cost and outcome log becomes the first data point for future threshold calibration.

---

*This paper is released without restriction. It is offered as a contribution to the open discourse on AI agent design and governance. Feedback, critique, and extension are invited.*

*Draft v0.2 — 2026-03-02*
