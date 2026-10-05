# Harness checklist

The operational version of the session. Use it on a real codebase.

The whole discipline in one rule: **every time an agent does something wrong, build something so
it never does it again.** Work through this in order — the early items are the ones teams skip
and the late items are the ones that change outcomes.

---

## 0. Before anything: can you even tell if it worked?

Do this first. Everything after it is wasted if you cannot detect failure.

- [ ] Write down, in one sentence, **how you would know** a change was correct.
- [ ] Identify which part of that is **deterministic** (a test, a type check, a query, a diff)
      and which part requires a human to judge.
- [ ] If nothing is deterministic, **stop here and build one sensor before granting more
      autonomy.** An unverifiable agent is an unmonitored agent.

> The single most common harness failure is not a missing tool. It is a missing *check* — the
> agent ran, the output looked plausible, and nobody could tell it was wrong.

---

## 1. Baseline — measure before you build

- [ ] Record agent performance on a **fixed task set** before changing anything.
- [ ] Hold the model **constant**. You are measuring the harness, so the model must not move.
- [ ] Record cost per task, not just success rate.
- [ ] Keep every failure. You need them in step 5.

> ⚠️ **If you change model and harness together, you learn nothing.** Every headline agent
> number in existence is a model-harness system, not a model.

---

## 2. Classify the subsystem

Run a change down the seven. The subsystem usually tells you what to build.

| If the failure was… | Subsystem | Go to |
| --- | --- | --- |
| It never stopped, or stopped wrong | Agent loop | §3.1 |
| It ignored context or the prompt | LLM integration | §3.2 |
| It used the wrong tool, or made one up | Tools and actions | §3.3 |
| It forgot, or drowned in stale context | Memory and context | §3.4 |
| It did something irreversible | Safety and permissions | §3.5 |
| Sub-agents fought or duplicated work | Orchestration | §3.6 |
| Adding capability took a fork | Extensibility | §3.7 |
| **You could not tell it was wrong** | *all of them* | **§0** |

### 3.1 Agent loop
- [ ] Is there a **hard step cap**?
- [ ] Is there a **time cap**?
- [ ] Is there a **token or dollar cap**?
- [ ] Do retries have **backoff and a bounded count**? An uncapped retry loop is the single most
      expensive bug in agent systems.
- [ ] Can a stuck run end cleanly instead of hanging?

### 3.2 LLM integration
- [ ] Is the prompt assembled from named parts, so you can see what is in it?
- [ ] Are tool descriptions written **for the model**, not for humans? They are the only text it
      matches against. Say *when* to use each tool, not just what it does.
- [ ] Do you cache? Re-assembly per turn is a large avoidable cost.

### 3.3 Tools and actions
- [ ] Are there **few, high-signal tools** rather than many overlapping ones? Dozens of
      near-duplicate tools measurably degrades selection.
- [ ] Does every tool's description say **when to use it and when not to**?
- [ ] Are destructive operations separately named, so permissions can distinguish them?

### 3.4 Memory and context
- [ ] Is context **rationed**, or just appended to?
- [ ] Is there a compaction/summarisation strategy for long runs?
- [ ] Does persistent memory have a **write policy** — what gets stored, and what is forbidden?
- [ ] Is stale memory invalidated, or trusted forever? An agent with a bad memory is worse than
      one with none: it compounds the error forward.

### 3.5 Safety and permissions
- [ ] Is there a sandbox, or does the agent run with your full filesystem and credentials?
- [ ] Are permissions **per-operation**, so writing and reading are not the same permission?
- [ ] Do destructive actions require explicit approval?
- [ ] Can you audit what the agent actually did, after the fact?

### 3.6 Orchestration
- [ ] Do sub-agents have **explicitly scoped** jobs, or do they overlap?
- [ ] Is there a defined hand-off contract between them?
- [ ] Who validates a sub-agent's output before it is used?

### 3.7 Extensibility
- [ ] Can you add a capability **without modifying the loop**?
- [ ] Are extensions versioned and independently removable?
- [ ] If a third party can add capability, is there a **trust boundary**?

---

## 4. Write the guides

- [ ] Create `AGENTS.md` (or equivalent) at the repository root.
- [ ] Every rule carries **the failure that caused it.** A rule with no story will not survive
      the next refactor.
- [ ] Rules are **imperative and specific**. "Write good tests" is not a rule. "Every new
      function over 20 lines needs a test that fails without the change" is.
- [ ] Keep it **short**. A long instruction file is read once and obeyed never.
- [ ] State the **non-goals** — what the agent must not invent.
- [ ] Put the highest-value rules first; there is no guarantee it reads the rest.

### Bad vs good

| Instead of | Write |
| --- | --- |
| "Follow our coding conventions" | "Use early returns; do not nest more than 2 levels. See `lint.py` rule `nest-depth`." |
| "Be careful with the database" | "Never run `db:reset`. It is not reversible. If a migration is needed, write it and stop." |
| "Write good tests" | "Every bug fix needs a test that fails on the pre-fix code. `pytest tests/ -x` must be green before you report done." |
| "Match the existing style" | "Follow the pattern in `src/api/users.ts` for any new endpoint in `src/api/`." |

---

## 5. Convert failures into sensors

This is the compounding step, and it is where the leverage is.

For **every** failure in your baseline:

1. Classify: *could a deterministic check have caught this?*
2. If yes — **write it**, wire it into your existing gate, and confirm it fails on the bad code.
3. If no — write it down as a **known limitation**, so nobody assumes it is covered.
4. Add a line to `AGENTS.md` naming the sensor.

| Failure | Deterministic? | Sensor |
| --- | --- | --- |
| Wrong tool chosen | Partly | Sharpen the tool description; add a test asserting the correct tool is exposed |
| Wrote files but changed nothing | Yes | Assert diff is non-empty |
| Broke an existing test | Yes | `pytest -x` in the gate |
| Invented an API | Yes | Type checker, or a test that imports and calls it |
| Ran a destructive command | Yes | Deny-list in the permission layer, plus an approval gate |
| Bad variable name | No | `AGENTS.md` rule. Do not pretend a linter solved it. |
| Wrong architectural direction | Partly | Architectural fitness function, if the rule is expressible |

> ⚠️ **Verify the sensor by breaking the code on purpose.** A check that has never failed is
> not a check. Confirm it goes red, then fix the code and confirm it goes green.

### Write sensors for LLM consumption

- [ ] Does the failure message tell the agent **what to do**, not just what broke?
- [ ] Is it **specific** — file, line, expected, actual?
- [ ] Is it short enough to act on without a re-read of the diff?

---

## 6. Earn autonomy in increments

Do not skip to full autonomy because the harness looks good.

- [ ] Start with **read-only** access.
- [ ] Add writes to a scratch area.
- [ ] Add writes to the real tree.
- [ ] Add execution, sandboxed.
- [ ] Add network access.
- [ ] Add anything irreversible — **last, and gated.**

At each step, hold until the failure rate is genuinely acceptable. Then extend.

> The autonomy you have should be the autonomy you have **measured**, not the autonomy you
> hope for. Every step you skip is a decision to trust a harness you have not tested.

---

## 7. Maintain it, or watch it rot

- [ ] Re-run the baseline **periodically**. A harness degrades as the codebase moves under it.
- [ ] Check for **contradictions** between guides and sensors. An instruction that fights a
      check produces non-deterministic behaviour.
- [ ] Delete rules for failures that no longer happen. A stale rule costs attention forever.
- [ ] Prune sensors that never fire. Either the quality is genuinely high or **detection is
      inadequate** — you cannot tell which without checking.
- [ ] Watch for **guidance rot**: instructions written for code that has since moved.

---

## 8. The questions

Ask these when you inherit an agent setup.

| Question | What a bad answer sounds like |
| --- | --- |
| How do we know a change was correct? | "We review the PR." |
| What can this agent do without asking? | "It does what it's asked." |
| What did it get wrong last month? | "Not sure." |
| Which rules here came from a real failure? | *(nothing)* |
| What happens when it loops? | "It stops eventually." |
| What happens when it runs out of money? | "We watch the bill." |
| Can we replay what it did? | "There's a transcript, I think." |

A bad answer to the first question means there is no harness yet — only an agent.

---

## The shortest useful version

If you do only three things:

1. **Measure.** Fixed tasks, fixed model, before you touch anything.
2. **Write one sensor** for the failure that recurs most.
3. **Turn one instruction into a check** that fails when it is violated.

That is the discipline. Everything else is scale.