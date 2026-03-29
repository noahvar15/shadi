#!/usr/bin/env python3
"""
Mark PRD checkboxes complete based on PR body text.

Looks for lines like:  PRD: FE-001, FE-002
Updates docs/PRD.md lines containing <!-- prd:FE-001 --> from [ ] to [x].

Environment:
  PR_BODY     — merged pull request body (required)
  PRD_PATH    — path to PRD markdown (default: docs/PRD.md)
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


PRD_LINE_RE = re.compile(
    r"^\s*PRD:\s*(.+)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
ID_TOKEN_RE = re.compile(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*", re.IGNORECASE)
MARKER_RE = re.compile(r"<!--\s*prd:([^>]+)\s*-->", re.IGNORECASE)


def parse_prd_ids(pr_body: str) -> list[str]:
    ids: list[str] = []
    for m in PRD_LINE_RE.finditer(pr_body or ""):
        chunk = m.group(1)
        for token in ID_TOKEN_RE.findall(chunk):
            tid = token.upper()
            if tid not in ids:
                ids.append(tid)
    return ids


def apply_ids(content: str, ids: set[str]) -> tuple[str, int]:
    """Return updated content and count of lines changed."""
    lines = content.splitlines(keepends=True)
    changed = 0
    out: list[str] = []
    for line in lines:
        if "- [ ]" not in line:
            out.append(line)
            continue
        mm = MARKER_RE.search(line)
        if not mm:
            out.append(line)
            continue
        raw_id = mm.group(1).strip().upper()
        if raw_id not in ids:
            out.append(line)
            continue
        new_line = line.replace("- [ ]", "- [x]", 1)
        if new_line != line:
            changed += 1
        out.append(new_line)
    return "".join(out), changed


def main() -> int:
    pr_body = os.environ.get("PR_BODY", "")
    path = Path(os.environ.get("PRD_PATH", "docs/PRD.md"))
    ids = parse_prd_ids(pr_body)
    if not ids:
        print("sync_prd: no PRD: line or IDs in PR body; nothing to do.", file=sys.stderr)
        return 0
    print(f"sync_prd: parsed IDs: {ids}", file=sys.stderr)
    if not path.is_file():
        print(f"sync_prd: missing file {path}", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    new_text, n = apply_ids(text, set(ids))
    if n == 0:
        print(
            "sync_prd: no matching unchecked items (IDs may be wrong or already done).",
            file=sys.stderr,
        )
        return 0
    path.write_text(new_text, encoding="utf-8")
    print(f"sync_prd: updated {n} checkbox(es) in {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
