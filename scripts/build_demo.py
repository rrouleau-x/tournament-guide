#!/usr/bin/env python3
"""Keep /demo/ in step with /app/.

The demo is the same page, served from /demo/. The shell detects the path itself:

    const IS_DEMO = /\\/demo\\//.test(location.pathname);

and turns on the disclaimer banner, the ?now= clock and the demo's own storage namespace.
The service worker does the same for its cache prefix (tg-demo- vs tournament-guide-), so the
app's cache cleanup can never evict the demo's (or vice versa).

So there is exactly ONE shell to maintain: demo/index.html and demo/sw.js must stay
byte-identical to the app's copies, and only the data under demo/ differs.

    python3 scripts/build_demo.py           # copy the shell across
    python3 scripts/build_demo.py --check   # fail if the two have drifted (run before deploy)
"""
import argparse
import filecmp
import os
import shutil
import sys

SHELL_FILES = ["index.html", "sw.js"]
DATA_DIRS = ["tournaments", "teams"]
DATA_FILES = ["tournaments.json", "teams.json", "manifest.json"]


def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sync(repo: str) -> int:
    app, demo = os.path.join(repo, "app"), os.path.join(repo, "demo")
    for name in SHELL_FILES:
        shutil.copy2(os.path.join(app, name), os.path.join(demo, name))
    missing = [p for p in DATA_FILES + DATA_DIRS if not os.path.exists(os.path.join(demo, p))]
    if missing:
        print("demo data missing:", ", ".join(missing), file=sys.stderr)
        return 1
    print("demo shell synced from app/")
    return 0


def check(repo: str) -> int:
    app, demo = os.path.join(repo, "app"), os.path.join(repo, "demo")
    drifted = [n for n in SHELL_FILES
               if not filecmp.cmp(os.path.join(app, n), os.path.join(demo, n), shallow=False)]
    missing = [p for p in DATA_FILES + DATA_DIRS if not os.path.exists(os.path.join(demo, p))]
    for n in drifted:
        print(f"DRIFT: demo/{n} differs from app/{n} — run scripts/build_demo.py", file=sys.stderr)
    for p in missing:
        print(f"MISSING: demo/{p}", file=sys.stderr)
    if drifted or missing:
        return 1
    print("demo shell identical to app shell; data present")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=repo_root())
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    sys.exit(check(args.repo) if args.check else sync(args.repo))
