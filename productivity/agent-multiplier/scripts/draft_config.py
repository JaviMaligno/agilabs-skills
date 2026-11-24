#!/usr/bin/env python3
"""Draft a config.json (categories by kind of work) from your own transcripts.

  python3 draft_config.py [--days 60] [--out ~/.agent-multiplier/config.draft.json]

All local and read-only:
  * collects the working directory of every interactive Claude Code and Codex conversation of the
    last --days days and counts conversations per folder;
  * finds each folder's git repo and the owner of its `origin` remote (GitHub/GitLab/Bitbucket owner,
    Azure DevOps organisation): one category per owner, matched by the repos' folder names;
  * a folder with no repo of its own that holds repos of one owner counts with that owner; the busiest
    one that holds repos of three or more owners is your coordination folder (the root of your work);
  * repos whose name looks like a website, blog or writing get kind "creative"; the rest "delegable".
Meetings and Other are always there. Review the draft (owner names are often not the names you use:
rename, merge or split), then save it as config.json. Never overwrites config.json.
"""
from __future__ import annotations

import argparse
import collections
from datetime import datetime, timedelta
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure as M  # noqa: E402

CREATIVE = re.compile(r"(website|blog|personal-site|portfolio|articles?|writing|newsletter|docs-site)", re.I)


def git(path: str, *args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, timeout=15)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def owner_of(url: str) -> str | None:
    """Owner from a remote URL: GitHub/GitLab/Bitbucket owner, or the Azure DevOps organisation."""
    url = (url or "").strip()
    m = re.search(r"dev\.azure\.com[:/](?:v3/)?([^/]+)/|([^/@.]+)\.visualstudio\.com", url)
    if m:
        return m.group(1) or m.group(2)
    m = re.search(r"[:/]([^/:]+)/[^/]+?(?:\.git)?/?$", url)
    return m.group(1) if m else None


def first_cwd_claude(path: str) -> str | None:
    for i, (_, o) in enumerate(M._read_jsonl(path, M.CLAUDE_TYPES)):
        if o.get("entrypoint") == "sdk-cli":
            return None
        if o.get("cwd"):
            return o["cwd"]
        if i > 60:
            return None
    return None


def first_cwd_codex(path: str) -> str | None:
    for i, (_, o) in enumerate(M._read_jsonl(path)):
        p = o.get("payload") if isinstance(o.get("payload"), dict) else {}
        if o.get("type") == "session_meta":
            if p.get("originator") == "codex_exec" or p.get("source") == "exec":
                return None
            if p.get("cwd"):
                return p["cwd"]
        if i > 20:
            return None
    return None


def collect(claude_root: str, codex_root: str, days: int) -> collections.Counter:
    since = (datetime.now() - timedelta(days=days)).timestamp()
    convs = collections.Counter()
    for files, reader in ((M.claude_main_files(claude_root) if os.path.isdir(claude_root) else [], first_cwd_claude),
                          (M.codex_files(codex_root) if os.path.isdir(codex_root) else [], first_cwd_codex)):
        for f in files:
            try:
                if os.path.getmtime(f) < since:
                    continue
            except OSError:
                continue
            cwd = reader(f)
            if cwd:
                convs[os.path.normpath(cwd)] += 1
    return convs


def owners_below(folder: str) -> collections.Counter:
    """Owners of the git repos one or two levels below a folder."""
    found = collections.Counter()
    try:
        kids = [os.path.join(folder, k) for k in os.listdir(folder)]
    except OSError:
        return found
    for k in kids:
        if not os.path.isdir(k):
            continue
        try:
            grand = [os.path.join(k, g) for g in os.listdir(k)[:40]]
        except OSError:
            grand = []
        for d in [k] + grand:
            if os.path.exists(os.path.join(d, ".git")):
                o = owner_of(git(d, "remote", "get-url", "origin"))
                if o:
                    found[o] += 1
    return found


def draft(convs: collections.Counter, home: str | None = None) -> tuple[dict, str | None, collections.Counter]:
    by_owner: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    loose = collections.Counter()
    for cwd, n in convs.items():
        if not os.path.isdir(cwd):
            continue
        top = git(cwd, "rev-parse", "--show-toplevel")
        if not top:
            loose[cwd] += n
            continue
        common = git(top, "rev-parse", "--path-format=absolute", "--git-common-dir")
        main_repo = os.path.dirname(common) if common.endswith(".git") else top  # worktrees -> main repo
        owner = owner_of(git(main_repo, "remote", "get-url", "origin")) or "no remote"
        by_owner[owner][os.path.basename(os.path.normpath(main_repo))] += n

    home = os.path.normpath(home or os.path.expanduser("~"))
    below = {cwd: owners_below(cwd) for cwd in loose if os.path.normpath(cwd) != home}
    below = {k: v for k, v in below.items() if sum(v.values())}
    multi = [k for k, v in below.items() if len(v) >= 3]
    coord = max(multi, key=lambda k: (len(below[k]), loose[k])) if multi else None
    for cwd, owners in below.items():
        if cwd == coord:
            continue
        top, k = owners.most_common(1)[0]
        if k >= 0.5 * sum(owners.values()):
            by_owner[top][os.path.basename(cwd) + "/"] += loose[cwd]

    cats = []
    for owner, repos in sorted(by_owner.items(), key=lambda kv: -sum(kv[1].values())):
        creative = [r for r in repos if CREATIVE.search(r)]
        rest = [r for r in repos if r not in creative]
        if rest:
            cats.append({"name": owner, "match": sorted(r.lower().rstrip("/") for r in rest),
                         "definition": f"Repos of {owner}: " + ", ".join(sorted(rest)) + ".", "kind": "delegable",
                         "_conversations": sum(repos[r] for r in rest)})
        if creative:
            cats.append({"name": "Writing and web", "match": sorted(r.lower() for r in creative),
                         "definition": "Website or blog: " + ", ".join(sorted(creative)) + ".", "kind": "creative",
                         "_conversations": sum(repos[r] for r in creative)})
    norm = lambda p: p.replace("\\", "/").lower().rstrip("/")
    return {
        "_comment": "Draft from draft_config.py: rename, merge or split the categories, then save as config.json. _conversations is informative.",
        "categories": cats,
        "coordination": {"name": "Coordination",
                         "dir_suffix": "/" + "/".join(norm(coord).split("/")[-2:]) if coord else "",
                         "definition": "Sessions opened at the root of your work, with no repo." if coord else "No coordination folder found."},
        "meeting": dict(M.DEFAULT_CONFIG["meeting"]),
        "other": dict(M.DEFAULT_CONFIG["other"]),
        "routine_marker": M.DEFAULT_ROUTINE_MARKER,
    }, coord, loose


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--out", default=os.path.expanduser("~/.agent-multiplier/config.draft.json"))
    ap.add_argument("--claude-root", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--codex-root", default=os.path.expanduser("~/.codex/sessions"))
    a = ap.parse_args(argv)
    if os.path.basename(a.out) == "config.json":
        sys.exit("refusing to overwrite config.json: write the draft elsewhere and copy it by hand")
    convs = collect(a.claude_root, a.codex_root, a.days)
    cfg, coord, loose = draft(convs)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=1)
    print(f"{sum(convs.values())} conversations in {len(convs)} folders (last {a.days} days) -> {a.out}")
    for c in cfg["categories"]:
        more = "..." if len(c["match"]) > 6 else ""
        print(f"  {c['name'][:28]:28s} {c['kind']:10s} {c['_conversations']:4d} conv · {', '.join(c['match'][:6])}{more}")
    print(f"  Coordination folder: {coord or '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
