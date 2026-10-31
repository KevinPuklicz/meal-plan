"""Manage tools/favorites.json.

    python3 tools/favorites.py add "<url>" [--by kevin|wife] [--date YYYY-MM-DD]
    python3 tools/favorites.py remove "<url>"
    python3 tools/favorites.py list

`add` looks the recipe up in past plan files (tools/plan_*.json) to fill in
name/site/time/note, so only the URL from the favorite email is needed.
"""
import glob
import json
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "tools", "favorites.json")


def load():
    try:
        return json.load(open(PATH))
    except Exception:
        return []


def save(favs):
    json.dump(favs, open(PATH, "w"), indent=1, ensure_ascii=False)


def norm(u):
    return u.strip().rstrip("/").replace("http://", "https://").replace("://www.", "://")


def find_dinner(url):
    for p in sorted(glob.glob(os.path.join(ROOT, "tools", "plan_*.json")), reverse=True):
        for d in json.load(open(p)).get("dinners", []):
            if norm(d["url"]) == norm(url):
                return d
    return None


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "list"
    favs = load()
    if cmd == "list":
        for f in favs:
            print(f"{f.get('added','')}  {f['name']}  {f['url']}")
        return
    url = argv[2]
    if cmd == "remove":
        before = len(favs)
        favs = [f for f in favs if norm(f["url"]) != norm(url)]
        save(favs)
        print(f"removed {before - len(favs)}")
        return
    if cmd == "add":
        if any(norm(f["url"]) == norm(url) for f in favs):
            print("already a favorite")
            return
        by = argv[argv.index("--by") + 1] if "--by" in argv else ""
        when = argv[argv.index("--date") + 1] if "--date" in argv else date.today().isoformat()
        d = find_dinner(url) or {"name": url, "url": url}
        favs.append({"name": d["name"], "url": d["url"], "site": d.get("site", ""),
                     "time": d.get("time", ""), "note": d.get("note", ""),
                     "added": when, "by": by})
        save(favs)
        print(f"added: {d['name']}")
        return
    raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
