# AGENTS.md — harness rules for this repo

Every rule below exists because an agent did the wrong thing without me noticing. Nothing here
is aspirational. If you add a rule, add the failure that caused it — a rule with no story behind
it will not survive the next refactor.

**Read this file before your first edit. Do not skip to the task.**

---

## Scope

This repository holds documentation and one Python script. There is no application, no build
step, and no test suite. Do not invent one.

---

## Rules, and the failure behind each

### R1 — Never edit prose in `README.md` without reading the whole section first

**Failure:** an agent rewrote the "Why it matters" section and silently dropped the caveats
attached to the 7.8× harness-variance figure, turning a hedged research result into a marketing
claim. The figure comes from Zhang et al., *Stop Comparing LLM Agents Without Disclosing the
Harness* (arXiv, May 2026), and its limitations are stated in the README beside it.

Every numeric claim in this repo carries its source and its limitation. If you remove a
number, keep or remove the sentence that bounds it. Numbers without provenance are the single
easiest thing to get wrong here.

### R2 — Do not "improve" the quoted definitions

**Failure:** an agent paraphrased Mitchell Hashimoto's definition of harness engineering, and
the paraphrase lost the entire force of the word *never* — turning "the agent never makes that
mistake again" into "reduce repeated mistakes."

Definitions from primary sources are quoted verbatim in blockquotes. If you cannot quote the
source, paraphrase it and label it clearly as your own summary. Never blur the two.

### R3 — Mermaid diagrams must be validated before commit

**Failure:** `subgraph PINE[("...")]` — nested parentheses inside a node label — was committed and
rendered as a parse error on GitHub. It looked fine in the source.

Before committing any change that touches a ```mermaid block, run:

```bash
python scripts/verify.py --diagrams
```

If the validator cannot reach the network, say so in your commit message rather than skipping
the check silently. An unvalidated diagram is a broken README.

### R4 — Do not add dependencies

**Failure:** an agent added `requests` to the verification script for one HTTP call, which broke
the script for anyone running it on a clean Python install.

`scripts/verify.py` must run on a bare Python 3.8+ install with **no third-party packages**.
Everything it needs is in the standard library. This is checked by the script itself.

### R5 — Keep dates and version claims explicit

**Failure:** an agent described harness engineering as a "recent trend" without dates, which
made a discipline named in February 2026 sound like a 2024 idea.

This field is moving fast enough that undated claims are misleading. When stating when
something was said or published, give the date and the source.

### R6 — Do not edit `LICENSE`

**Failure:** none yet. This rule is here because it is cheap and the file is load-bearing.

### R7 — Do not add new top-level directories without asking

**Failure:** an agent created `src/` and `tests/` for a docs repository, then wrote a passing
empty test suite into it. Nothing was verified.

If a check seems to deserve its own directory, propose it in your summary instead.

---

## Definition of done

Run `python scripts/verify.py` and paste the output into your final message. If any check fails,
either fix it or explain why it is acceptable in the same message. Do not report success you did
not observe.

---

## Working agreement

- Make the smallest change that solves the task. Do not refactor adjacent sections.
- If the task is ambiguous in a way that changes the output, stop and ask.
- If you find a bug in the docs that is out of scope, report it. Do not fix it unprompted.