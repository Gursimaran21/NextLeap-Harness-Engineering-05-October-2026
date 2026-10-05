#!/usr/bin/env python3
"""
verify.py — the sensor half of this repository's harness.

An agent cannot see its own mistakes. This script exists so that a class of mistakes is
caught by a deterministic check rather than by a human reading a diff.

That is the whole idea of harness engineering: every time an agent does something wrong,
build something so it never does it again. Guides (AGENTS.md) steer. Sensors (this file)
verify. You need both.

Standard library only. No third-party packages. See AGENTS.md rule R4.

Usage:
    python scripts/verify.py              # run all local checks
    python scripts/verify.py --diagrams   # also validate mermaid blocks over the network
    python scripts/verify.py --json       # machine-readable output

Exit codes: 0 all passed, 1 failures found, 2 could not run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Windows consoles default to a legacy code page and mangle the multiplication sign and
# em dashes used in check output. Correct that before printing anything.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

# --- Rule R4's teeth: this script may not import anything outside the stdlib. -------------
ALLOWED_IMPORT_ROOTS = {
    "argparse", "json", "os", "re", "sys", "time", "urllib", "dataclasses",
    "pathlib", "__future__", "typing", "collections", "itertools", "functools",
    "textwrap",
}

# --- Rule R1/R5's teeth: numbers in prose need provenance. -------------------------------
# A bare percentage or multiplier in the README must sit near a citation.
PROSE_FILES = ["README.md", "AGENTS.md", "harness-checklist.md"]

# Secrets that must never appear in a public repository. Checked against the actual files,
# not against documentation that merely mentions the concept.
SECRET_PATTERNS = [
    (r"AKIA[0-9A-Z]{16}", "AWS access key id"),
    (r"ghp_[A-Za-z0-9]{36}", "GitHub personal access token"),
    (r"sk-[A-Za-z0-9]{20,}", "OpenAI-style API key"),
    (r"AIza[0-9A-Za-z_\-]{35}", "Google API key"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "Slack token"),
    (r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.", "JWT"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----", "private key"),
]

# n8n instances leak their trigger paths, which are effectively passwords.
N8N_INSTANCE = re.compile(r"[a-z0-9.-]+\.n8n\.cloud", re.IGNORECASE)


@dataclass
class Result:
    name: str
    status: str  # pass | fail | skip
    detail: str = ""
    items: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in ("pass", "skip")


# --------------------------------------------------------------------------------------
# Local checks
# --------------------------------------------------------------------------------------


def check_imports() -> Result:
    """Rule R4: the verification script must stay dependency-free."""
    src = (ROOT / "scripts" / "verify.py").read_text(encoding="utf-8")
    bad = []
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("import "):
            mod = stripped[len("import "):].split()[0].split(".")[0]
        elif stripped.startswith("from "):
            mod = stripped[len("from "):].split()[0].split(".")[0]
        else:
            continue
        if mod not in ALLOWED_IMPORT_ROOTS:
            bad.append(mod)
    if bad:
        return Result("stdlib-only imports", "fail",
                      f"non-stdlib import(s): {', '.join(sorted(set(bad)))}", bad)
    return Result("stdlib-only imports", "pass",
                  f"all imports within {len(ALLOWED_IMPORT_ROOTS)} allowed stdlib roots")


def check_secrets() -> Result:
    """Rule: never commit credentials. This is the check that would have caught the
    n8n credential blocks and the real email address in the early workflow exports."""
    hits = []
    scanned = 0
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        scanned += 1
        for pattern, label in SECRET_PATTERNS:
            for match in re.finditer(pattern, text):
                line_no = text[:match.start()].count("\n") + 1
                hits.append(f"{path.relative_to(ROOT)}:{line_no} {label}")
    if hits:
        return Result("no committed secrets", "fail", f"{len(hits)} finding(s)", hits)
    return Result("no committed secrets", "pass", f"{scanned} file(s) scanned")


def check_n8n_instance_leak() -> Result:
    """A real n8n Cloud hostname plus its trigger path is a usable credential."""
    hits = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for match in N8N_INSTANCE.finditer(text):
            hits.append(f"{path.relative_to(ROOT)}: {match.group(0)}")
    if hits:
        return Result("no n8n instance hostnames", "fail", f"{len(hits)} finding(s)", hits)
    return Result("no n8n instance hostnames", "pass")


def check_provenance() -> Result:
    """Rule R1: a bare statistic in prose is a claim without evidence.

    This is deliberately approximate. It flags percentage or multiplier figures that appear
    with no citation within the surrounding paragraph, so a human decides whether the
    sentence is bounded. It errs toward reporting: false positives cost a few seconds of
    reading, false negatives cost the repo its credibility.
    """
    citations = ("http", "arxiv", "martinfowler", "mitchellh", "openai.com",
                 "claude.com", "anthropic", "github.com", "agentskills",
                 "boeckeler", "böckeler", "zhang et al", "lin et al", "study", "paper")
    number = re.compile(r"(?<![\w.])(?:\d{1,3}(?:\.\d+)?\s?(?:%|×|x)(?!\w))")
    findings = []
    for name in PROSE_FILES:
        path = ROOT / name
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()

        # Blank-line separated paragraphs are the unit of citation.
        in_fence = False
        paragraphs, current = [], []
        for line in lines:
            if line.strip().startswith("```"):
                in_fence = not in_fence
                current.append(line)
                continue
            if not line.strip() and not in_fence:
                if current:
                    paragraphs.append(current)
                current = []
            else:
                current.append(line)
        if current:
            paragraphs.append(current)

        for pos, para in enumerate(paragraphs):
            body = "\n".join(para)
            if not number.search(body):
                continue

            # A bullet list or blockquote inherits its citation from the sentence that
            # introduces it: "Specifics from that study, which are more interesting
            # than the headline:" is followed by bullets citing the same source.
            scope = [body]
            if pos > 0 and re.match(r"\s*(?:[-*+]\s|\d+[.)]\s|>)", para[0]):
                scope.append("\n".join(paragraphs[pos - 1]))

            if any(c in "\n".join(scope).lower() for c in citations):
                continue

            for line in para:
                if number.search(line):
                    findings.append(f"{name}: {line.strip()[:88]}")

    if findings:
        return Result("statistics carry provenance", "fail",
                      f"{len(findings)} uncited figure(s) — confirm each is intentional", findings)
    return Result("statistics carry provenance", "pass")


# Kroki returns 4xx for reasons that are not your diagram's fault. Treating a rate limit as a
# broken diagram trains people to ignore this check, which is worse than having no check.
THROTTLE_CODES = {403, 429, 503}


def check_diagram_fences() -> Result:
    """Cheap structural check that runs offline.

    Catches the two mistakes that actually happen: an unterminated mermaid fence, and the
    nested-parenthesis label form that kroki rejects.
    """
    problems = []
    blocks = extract_mermaid_blocks()
    for name, start, body in blocks:
        for lineno, line in enumerate(body.splitlines(), start=start):
            sub = re.match(r"\s*subgraph\s+\S+", line)
            if sub and re.search(r"\[.*\(.*\).*\]", line):
                problems.append(
                    f"{name}:{lineno} nested parentheses inside a subgraph label: {line.strip()}")
    if not blocks:
        return Result("mermaid structure (offline)", "skip", "no mermaid blocks found")
    status = "fail" if problems else "pass"
    return Result("mermaid structure (offline)", status,
                  f"{len(blocks)} block(s) scanned", problems)


def check_structure() -> Result:
    """The README documents a layout. Keep them in sync."""
    required = [
        "README.md",
        "LICENSE",
        "AGENTS.md",
        "harness-checklist.md",
        "scripts/verify.py",
    ]
    missing = [r for r in required if not (ROOT / r).exists()]
    if missing:
        return Result("required files present", "fail", f"missing: {', '.join(missing)}", missing)
    return Result("required files present", "pass", f"all {len(required)} required files exist")


# --------------------------------------------------------------------------------------
# Mermaid validation (network)
# --------------------------------------------------------------------------------------


def extract_mermaid_blocks() -> list:
    blocks = []
    for name in PROSE_FILES:
        path = ROOT / name
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        inside = False
        start = 0
        buf: list = []
        for idx, line in enumerate(lines, start=1):
            if not inside and line.strip().startswith("```mermaid"):
                inside, start, buf = True, idx + 1, []
            elif inside and line.strip() == "```":
                blocks.append((name, start, "\n".join(buf)))
                inside = False
            elif inside:
                buf.append(line)
    return blocks


def check_diagrams_remote() -> Result:
    blocks = extract_mermaid_blocks()
    if not blocks:
        return Result("mermaid parse (kroki.io)", "skip", "no mermaid blocks found")

    endpoint = "https://kroki.io/mermaid/svg"
    items = []
    failures = 0
    throttled = 0
    unverifiable = False

    for index, (name, start, body) in enumerate(blocks):
        req = urllib.request.Request(
            endpoint,
            data=body.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                code = resp.status
        except urllib.error.HTTPError as exc:
            code = exc.code
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return Result("mermaid parse (kroki.io)", "skip",
                          f"network unavailable ({exc.__class__.__name__}) — say so in the commit")

        if code == 200:
            items.append(f"PASS  {name}:{start}")
        elif code in THROTTLE_CODES:
            # Not a diagram problem. Stop early rather than hammering the service.
            throttled += 1
            unverifiable = True
            items.append(f"SKIP  {name}:{start}  (kroki returned HTTP {code} — rate limited)")
            break
        else:
            failures += 1
            items.append(f"FAIL  {name}:{start}  (HTTP {code} — genuine parse error)")

        # Space requests out; the public endpoint throttles bursts.
        if index < len(blocks) - 1 and not unverifiable:
            time.sleep(1.5)

    checked = len(blocks) - throttled
    if failures:
        status, detail = "fail", f"{checked - failures}/{checked} block(s) valid"
    elif unverifiable:
        status = "skip"
        detail = f"unverifiable — kroki rate limited after {checked} block(s)"
    else:
        status, detail = "pass", f"{checked}/{checked} block(s) valid"

    return Result("mermaid parse (kroki.io)", status, detail, items)


# --------------------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------------------

LOCAL_CHECKS = [
    check_imports,
    check_secrets,
    check_n8n_instance_leak,
    check_structure,
    check_diagram_fences,
    check_provenance,
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--diagrams", action="store_true",
                        help="also validate mermaid blocks against kroki.io (needs network)")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit machine-readable results")
    args = parser.parse_args()

    checks = list(LOCAL_CHECKS)
    if args.diagrams:
        checks.append(check_diagrams_remote)

    results = [fn() for fn in checks]
    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status == "fail")
    skipped = sum(1 for r in results if r.status == "skip")

    if args.as_json:
        print(json.dumps({
            "passed": passed, "failed": failed, "skipped": skipped,
            "checks": [{"name": r.name, "status": r.status,
                        "detail": r.detail, "items": r.items} for r in results],
        }, indent=2))
    else:
        width = max(len(r.name) for r in results)
        for r in results:
            mark = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}[r.status]
            print(f"[{mark}] {r.name.ljust(width)}  {r.detail}")
            for item in r.items:
                print(f"         {item}")
        print("-" * 60)
        print(f"{passed} passed, {failed} failed, {skipped} skipped")

    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        sys.exit(2)