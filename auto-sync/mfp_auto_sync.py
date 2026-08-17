#!/usr/bin/env python3
"""Health & Fitness Hub - automatic MyFitnessPal sync.
Runs on SP's Mac via launchd. Reads the MFP diary using the logged-in Chrome
session (no password stored), converts it to the hub's feed format, and pushes
food.json to Sammypisano.github.io. The dashboard picks it up automatically.
"""
import json, os, subprocess, sys, time, datetime

HOME = os.path.expanduser("~/.hub-sync")
SITE = os.path.join(HOME, "site")
LOG = os.path.join(HOME, "log.txt")
REPO = "https://github.com/Sammypisano/Sammypisano.github.io.git"
def _read_token():
    try:
        return open(os.path.join(HOME, "token")).read().strip()
    except Exception:
        return ""
TOKEN = None  # resolved in main()
DAYS_BACK = 7

def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S") + "  " + msg
    print(line)
    try:
        with open(LOG, "a") as f: f.write(line + "\n")
    except Exception: pass

def sh(args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)

def auth_header():
    import base64
    b64 = base64.b64encode(("x-access-token:" + TOKEN).encode()).decode()
    return "http.extraHeader=Authorization: Basic " + b64

def ensure_site():
    if not os.path.isdir(os.path.join(SITE, ".git")):
        r = sh(["git", "-c", auth_header(), "clone", "-q", "--depth", "1", REPO, SITE])
        if r.returncode != 0: raise RuntimeError("clone failed: " + r.stderr[:300])
    else:
        sh(["git", "-C", SITE, "fetch", "-q", "--depth", "1", "origin", "main"])
        sh(["git", "-C", SITE, "reset", "-q", "--hard", "origin/main"])

def pull_mfp():
    import myfitnesspal
    client = myfitnesspal.Client()   # cookies from the logged-in browser
    today = datetime.date.today()
    entries, runs = [], []
    for i in range(DAYS_BACK):
        d = today - datetime.timedelta(days=i)
        try:
            day = client.get_date(d.year, d.month, d.day)
        except Exception as e:
            log("skip %s: %s" % (d, str(e)[:120])); continue
        totals = day.totals or {}
        if not totals and not day.meals: continue
        meals = {"breakfast": [], "lunch": [], "dinner": [], "snacks": []}
        for meal in day.meals:
            key = meal.name.lower()
            key = "snacks" if key.startswith("snack") else key
            if key not in meals: meals[key] = []
            for it in meal.entries:
                t = it.totals or {}
                meals[key].append({
                    "name": it.short_name or it.name,
                    "kcal": t.get("calories"), "p": t.get("protein"),
                    "c": t.get("carbohydrates"), "f": t.get("fat")})
        entry = {"date": d.isoformat(),
                 "kcal": totals.get("calories"), "protein": totals.get("protein"),
                 "carbs": totals.get("carbohydrates"), "fat": totals.get("fat"),
                 "meals": meals, "loggedAt": None}
        try:
            w = day.water  # ml or oz depending on account units
            if w: entry["water"] = round(w / 29.574) if w >= 500 else round(w)
        except Exception: pass
        has_food = entry["kcal"] or entry["protein"] or any(meals.values())
        if has_food: entries.append(entry)
        try:
            for ex in (day.exercises[0].entries if day.exercises else []):
                nfo = ex.nfo_dict if hasattr(ex, "nfo_dict") else {}
                mins = nfo.get("minutes"); kcal = nfo.get("calories burned")
                name = (ex.name or "").lower()
                if not mins or not kcal: continue
                if "adjustment" in name: continue
                if any(k in name for k in ("run", "jog", "treadmill", "walk")):
                    t2 = "long" if mins >= 50 else "easy"
                    runs.append({"date": d.isoformat(), "type": t2,
                                 "name": "Long Run" if t2 == "long" else "Easy Run",
                                 "time": mins, "dist": None, "pace": None, "kcal": round(kcal)})
        except Exception: pass
    return entries, runs

def publish(entries, runs):
    path = os.path.join(SITE, "food.json")
    feed = {"ts": 0, "entries": [], "runs": []}
    if os.path.exists(path):
        try: feed = json.load(open(path))
        except Exception: pass
    by_date = {e["date"]: e for e in feed.get("entries", [])}
    changed = 0
    def items(e): return sum(len(v) for v in (e.get("meals") or {}).values())
    for e in entries:
        cur = by_date.get(e["date"])
        if cur is None or items(e) > items(cur) or (e.get("kcal") or 0) != (cur.get("kcal") or 0) \
           or (e.get("water") or 0) > (cur.get("water") or 0):
            by_date[e["date"]] = e; changed += 1
    cut = (datetime.date.today() - datetime.timedelta(days=365)).isoformat()
    feed["entries"] = sorted([e for e in by_date.values() if e["date"] >= cut],
                             key=lambda e: e["date"], reverse=True)
    old_runs = feed.get("runs", [])
    def dupe(r):
        return any(x["date"] == r["date"] and abs((x.get("time") or 0) - (r.get("time") or 0)) < 1
                   and (x.get("kcal") is None or r.get("kcal") is None or abs(x["kcal"] - r["kcal"]) < 25)
                   for x in old_runs)
    for r in runs:
        if not dupe(r): old_runs.insert(0, r); changed += 1
    feed["runs"] = sorted([r for r in old_runs if r["date"] >= cut],
                          key=lambda r: r["date"], reverse=True)
    if not changed:
        log("no changes - feed already current"); return False
    feed["ts"] = int(time.time() * 1000)
    json.dump(feed, open(path, "w"))
    sh(["git", "-C", SITE, "add", "food.json"])
    sh(["git", "-C", SITE, "-c", "user.name=Hub Auto-Sync",
        "-c", "user.email=fwt-builder@users.noreply.github.com",
        "commit", "-qm", "auto: MyFitnessPal sync (%d update%s)" % (changed, "" if changed == 1 else "s")])
    r = sh(["git", "-C", SITE, "-c", auth_header(), "push", "-q", "origin", "main"])
    if r.returncode != 0: raise RuntimeError("push failed: " + r.stderr[:300])
    log("pushed %d update(s) - dashboard will refresh itself" % changed)
    return True

def main():
    global TOKEN
    os.makedirs(HOME, exist_ok=True)
    TOKEN = _read_token()
    if not TOKEN:
        log("ERROR: no token file at ~/.hub-sync/token - rerun the setup paste"); sys.exit(1)
    try:
        ensure_site()
        entries, runs = pull_mfp()
        if not entries and not runs:
            log("nothing found in the last %d days" % DAYS_BACK); return
        publish(entries, runs)
    except Exception as e:
        log("ERROR: " + str(e)[:400])
        if "cookie" in str(e).lower() or "login" in str(e).lower() or "browser" in str(e).lower():
            log("HINT: open Chrome, make sure you're logged in at myfitnesspal.com, then this will work on the next run.")
        sys.exit(1)

if __name__ == "__main__":
    main()
