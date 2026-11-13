#!/usr/bin/env python3
"""Build /demo/ — the reviewable demo of the tournament app.

Why a loader and not a copy:
  The demo used to be a full duplicate of app/index.html, which meant every shell fix had to
  be made twice or the demo silently drifted behind the app it exists to represent. Now
  demo/index.html fetches ../app/index.html at runtime and rewrites three things:
    - the title
    - a banner saying the schedule is synthetic
    - STORE_NS, so the demo keeps its own localStorage and cannot overwrite a parent's
      saved tournament / team / offline copy (same origin shares storage).
  Because the document URL stays /demo/, every relative fetch inside the app
  (tournaments.json, teams.json, tournaments/<slug>.json, sw.js, manifest.json) resolves to
  the demo's own copies. One source of truth for the shell, separate data and storage.

The demo service worker uses the tg-demo- cache prefix. The app's worker deletes every cache
whose name starts with `tournament-guide-`, so a demo cache with that prefix would be evicted
on the parent's next app visit (and vice versa).

Usage: python3 scripts/build_demo.py [--repo /path/to/tournament-guide]
"""
import argparse
import json
import os
import re
import sys

GAMES = [
    {"date": "2027-01-23", "time": "8:00 AM", "opponent": "Florida Elite 17B", "field": "Field 3A",
     "home": True, "arrival": "7:15 AM", "status": "confirmed"},
    {"date": "2027-01-23", "time": "11:30 AM", "opponent": "Jacksonville FC 17B", "field": "Field 5",
     "home": False, "arrival": "10:45 AM", "status": "confirmed"},
    {"date": "2027-01-23", "time": "3:00 PM", "opponent": "Clay County 17B", "field": "Field 2B",
     "home": True, "arrival": "2:15 PM", "status": "confirmed"},
    {"date": "2027-01-24", "time": "9:15 AM", "opponent": "TBD (bracket)", "field": "Field 1",
     "home": None, "arrival": "8:30 AM", "status": "conditional", "type": "final"},
]

LOADER = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>Tournament Guide \u2014 Demo</title>
<style>html,body{margin:0;background:#eef1f6;font:600 14px -apple-system,BlinkMacSystemFont,sans-serif;color:#0055A4}#ld{padding:26px 20px;text-align:center}</style>
</head>
<body><p id="ld">Loading the demo\u2026</p>
<script>
/* Loader: one source of truth for the app shell (see scripts/build_demo.py).
   Relative URLs resolve against /demo/, so the data files are the demo's own. */
fetch('../app/index.html', {cache: 'no-cache'}).then(function (r) {
  if (!r.ok) throw new Error(r.status);
  return r.text();
}).then(function (h) {
  h = h.replace('<title>Tournament Guide</title>', '<title>Tournament Guide \u2014 Demo</title>');
  h = h.replace("var STORE_NS='';", "var STORE_NS='demo-';");
  h = h.replace('<div class="offlineBar" id="offlineBar"',
    '<div id="demoBar" style="background:#eef1f6;color:#0055A4;font-size:12px;font-weight:700;padding:7px 14px;text-align:center;border-bottom:1px solid #d8e0ec">Demo build \u00b7 synthetic schedule, not a real tournament<\/div>' +
    '<div class="offlineBar" id="offlineBar"');
  document.open();
  document.write(h);
  document.close();
}).catch(function () {
  var el = document.getElementById('ld');
  if (el) el.textContent = 'Could not load the demo page.';
});
</script>
</body>
</html>
"""


def build(repo: str) -> None:
    app = os.path.join(repo, "app")
    demo = os.path.join(repo, "demo")
    os.makedirs(os.path.join(demo, "tournaments"), exist_ok=True)
    os.makedirs(os.path.join(demo, "teams"), exist_ok=True)

    with open(os.path.join(demo, "index.html"), "w", encoding="utf-8") as f:
        f.write(LOADER)

    sw = open(os.path.join(app, "sw.js"), encoding="utf-8").read()
    sw = re.sub(r"const CACHE = '[^']+';", "const CACHE = 'tg-demo-v1';", sw)
    sw = re.sub(r"const PREFIX = '[^']+';", "const PREFIX = 'tg-demo-';", sw)
    with open(os.path.join(demo, "sw.js"), "w", encoding="utf-8") as f:
        f.write(sw)

    man = json.load(open(os.path.join(app, "manifest.json"), encoding="utf-8"))
    man["name"] = "Tournament Guide \u2014 Demo"
    man["short_name"] = "TG Demo"
    man["start_url"] = "./"
    json.dump(man, open(os.path.join(demo, "manifest.json"), "w", encoding="utf-8"), indent=1)

    teams = [
        {"slug": "demo-u9-premier", "label": "U9 Premier", "name": "SU 17/18B Premier",
         "shortName": "SU 17/18B Premier", "ageGroup": "U9", "format": "7v7"},
        {"slug": "demo-u10-blue", "label": "U10 Blue", "name": "SU 17/18B Blue",
         "shortName": "SU 17/18B Blue", "ageGroup": "U10", "format": "7v7"},
    ]
    shared = {
        "tournament": {"name": "Demo Test Invitational",
                       "dates": {"start": "2027-01-23", "end": "2027-01-24"}},
        "venue": {"name": "Patton Park", "address": "2839 Owen Ave, Jacksonville, FL 32205",
                  "city": "Jacksonville, FL",
                  "mapsUrl": "https://www.google.com/maps/?q=Patton+Park+Jacksonville+FL",
                  "parking": "Park on the grass lot off Owen Ave; overflow at the school next door.",
                  "amenities": {"restrooms": True, "concessions": True, "shade": "limited"}},
        "teams": teams,
        "defaultTeam": "demo-u9-premier",
        "checklist": {
            "player": ["Both uniform kits", "Cleats", "Shin guards", "Water bottle", "Extra socks",
                       "Warm-up gear", "Dry clothes", "Recovery shoes", "Medications"],
            "weather": ["Water (plenty)", "Warm layer for early kickoffs", "Beanie or headband",
                        "Gloves", "Hand warmers", "Rain shell"],
            "parent": ["Folding chairs", "Shade/canopy", "Cooler", "Snacks", "Portable charger", "Wipes"],
            "emergency": ["First-aid kit", "Ice packs", "Insurance info", "Emergency contacts"]},
        "rules": {"keyRules": [{"label": "Game length", "value": "2 x 25 min"},
                               {"label": "Format", "value": "7v7"},
                               {"label": "Roster", "value": "12 max"}],
                  "tiebreakers": ["Head to head", "Goal difference", "Goals scored"],
                  "fullLink": "https://example.com/rules"},
        "contacts": {"coaches": [{"name": "Carson Gray", "role": "Coach", "email": "carsonzgray@gmail.com"}],
                     "tournamentDirector": {"name": "Tournament HQ", "phone": "9040000000",
                                            "email": "hq@example.com"}},
        "updates": [{"title": "Schedule posted", "description": "All four games are now in the app."}],
        "weather": {"source": {"enabled": False}},
    }
    json.dump(shared, open(os.path.join(demo, "tournaments", "demo-live-test.json"), "w",
                           encoding="utf-8"), indent=1)

    base = {"ageGroup": "U9", "format": "7v7", "games": GAMES}
    json.dump(dict(base, name="SU 17/18B Premier", shortName="SU 17/18B Premier"),
              open(os.path.join(demo, "teams", "demo-u9-premier.json"), "w", encoding="utf-8"), indent=1)
    json.dump(dict(base, name="SU 17/18B Blue", shortName="SU 17/18B Blue", ageGroup="U10"),
              open(os.path.join(demo, "teams", "demo-u10-blue.json"), "w", encoding="utf-8"), indent=1)

    # the app always fetches teams.json — without it every load logged a 404
    json.dump({"teams": teams, "defaultTeam": "demo-u9-premier"},
              open(os.path.join(demo, "teams.json"), "w", encoding="utf-8"), indent=1)

    json.dump({"defaultTournament": "demo-live-test",
               "tournaments": [{"slug": "demo-live-test", "name": "Demo Test Invitational",
                                "dates": "Jan 23\u201324, 2027", "city": "Jacksonville, FL"}]},
              open(os.path.join(demo, "tournaments.json"), "w", encoding="utf-8"), indent=1)

    print("demo built:", sorted(os.listdir(demo)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    build(ap.parse_args().repo)
