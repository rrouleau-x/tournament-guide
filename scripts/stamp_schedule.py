#!/usr/bin/env python3
"""Record WHEN each team's schedule was last edited.

The app shows two different times on the Next Match card:

    Schedule updated Fri, Jan 22, 6:30 PM ET · checked 8:20 AM ET

"checked" is when the phone last fetched the file. "updated" is when the games in that file
last changed - and only the person editing the schedule knows that. This script works it out
so nobody has to remember: for every team file it compares "games" with the version in the
last commit and, if they differ, writes the current time into "scheduleUpdated".

    python3 scripts/stamp_schedule.py           # stamp changed schedules (run before committing)
    python3 scripts/stamp_schedule.py --check   # fail if a changed schedule is not stamped

A team with games but no stamp at all is stamped too. Files whose games did not change are
left byte-for-byte alone.
"""
import argparse
import datetime
import glob
import json
import os
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

TEAM_GLOBS = ["app/teams/*.json", "demo/teams/*.json"]
TZ = ZoneInfo("America/New_York")


def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def committed(repo: str, rel: str):
    """The file as of the last commit, or None if it is new / not valid JSON there."""
    r = subprocess.run(["git", "-C", repo, "show", "HEAD:" + rel], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except ValueError:
        return None


def needs_stamp(now_doc: dict, old_doc) -> bool:
    games = now_doc.get("games") or []
    if not games:
        return False
    if old_doc is None:
        return not now_doc.get("scheduleUpdated")
    if games != (old_doc.get("games") or []):
        # changed since the last commit: stale unless the stamp was already refreshed
        return now_doc.get("scheduleUpdated") in (None, "", old_doc.get("scheduleUpdated"))
    return not now_doc.get("scheduleUpdated")


def write_like_original(path: str, raw: str, doc: dict) -> None:
    m = re.search(r"\n( +)\"", raw)
    indent = len(m.group(1)) if m else 2
    out = json.dumps(doc, indent=indent, ensure_ascii=("\\u" in raw))
    with open(path, "w", encoding="utf-8") as f:
        f.write(out + ("\n" if raw.endswith("\n") else ""))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=repo_root())
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    stamp = datetime.datetime.now(TZ).replace(microsecond=0).isoformat()
    stale = []
    for pattern in TEAM_GLOBS:
        for path in sorted(glob.glob(os.path.join(args.repo, pattern))):
            rel = os.path.relpath(path, args.repo)
            with open(path, encoding="utf-8") as f:
                raw = f.read()
            doc = json.loads(raw)
            if not needs_stamp(doc, committed(args.repo, rel)):
                continue
            stale.append(rel)
            if not args.check:
                doc["scheduleUpdated"] = stamp
                write_like_original(path, raw, doc)
                print(f"stamped {rel} -> {stamp}")
    if args.check and stale:
        for rel in stale:
            print(f"UNSTAMPED: {rel} has schedule changes - run scripts/stamp_schedule.py", file=sys.stderr)
        return 1
    if not stale:
        print("all schedule stamps are current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
