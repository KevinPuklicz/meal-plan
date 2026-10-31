"""Build the weekly meal-plan page (with boxed flyer proofs) from a plan JSON.

    python3 tools/build_site.py tools/plan_<week>.json

Writes:
  weeks/<week>/index.html      this week's page
  weeks/<week>/proofs/*.jpg    boxed flyer crops for each price match
  index.html                   copy of the latest week (the link in the email)
Prints a JSON summary (matches + stores) for the email step.
"""
import html
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(__file__))
import flyerkit as fk  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
e = html.escape


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]


def load_favs():
    try:
        return json.load(open(os.path.join(ROOT, "tools", "favorites.json")))
    except Exception:
        return []


def write_favorites_page(favs, css):
    rows = []
    for f in sorted(favs, key=lambda x: x.get("added", ""), reverse=True):
        meta = " · ".join(x for x in [f.get("site", ""), f.get("time", ""), f"added {f.get('added', '')}" if f.get("added") else ""] if x)
        note = f"<div class='note'>{e(f['note'])}</div>" if f.get("note") else ""
        rows.append(f"<div class='card meal'><div class='day'>{e(meta)}</div>"
                    f"<a href='{e(f['url'])}' target='_blank' rel='noopener'>{e(f['name'])}</a>{note}</div>")
    body = "".join(rows) or "<p class='note'>No favorites yet. Tap ☆ Favorite next to a dinner in the weekly email.</p>"
    html_ = (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>Favorite dinners</title><style>{css}</style></head><body><main>"
             f"<h1>★ Favorite dinners</h1><div class='sub'>{len(favs)} saved · <a href='index.html'>This week's plan</a></div>{body}</main></body></html>")
    open(os.path.join(ROOT, "favorites.html"), "w").write(html_)


def main(plan_path):
    plan = json.load(open(plan_path))
    week = plan["week_of"]
    pc = plan.get("postal_code", "N2L3G1")
    out_dir = os.path.join(ROOT, "weeks", week)
    os.makedirs(os.path.join(out_dir, "proofs"), exist_ok=True)

    flyers = {f["id"]: f for f in fk.get_flyers(pc)}
    items_cache, stores = {}, {}
    matches = []
    for g in plan["groceries"]:
        m = g.get("match")
        if not m:
            continue
        fid, iid = m["flyer_id"], m["item_id"]
        flyer = flyers.get(fid)
        if flyer is None:
            raise SystemExit(f"Flyer {fid} not found for {pc}")
        if fid not in items_cache:
            items_cache[fid] = {i["id"]: i for i in fk.get_items(fid)}
        item = items_cache[fid].get(iid)
        if item is None:
            raise SystemExit(f"Item {iid} not in flyer {fid}")
        if fid not in stores:
            stores[fid] = fk.nearby_store(fid, pc)
        st = stores[fid]
        fname = f"{slug(g['name'])}.jpg"
        fk.render_proof(flyer, item, st, os.path.join(out_dir, "proofs", fname),
                        price_text=g["price"].replace(" ea", ""))
        g["_proof"] = f"proofs/{fname}"
        g["_store"] = flyer["merchant"]
        g["_store_addr"] = (f"{st['address']}, {st['city']}" if st else "")
        matches.append(g)

    total = sum(g["est"] for g in plan["groceries"])

    # --- page ---
    css = """
:root{--bg:#f7f8f6;--card:#fff;--ink:#1f2421;--muted:#5d6b63;--accent:#1d5b3a;--tag:#fde7c4;--tagink:#7a4a00;--line:#e5e9e6}
@media (prefers-color-scheme:dark){:root{--bg:#121513;--card:#1b201d;--ink:#e8ede9;--muted:#9aa8a0;--accent:#6fcf97;--tag:#4a3a1c;--tagink:#ffd796;--line:#2a312d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 -apple-system,system-ui,Segoe UI,Roboto,Arial,sans-serif}
main{max-width:720px;margin:0 auto;padding:16px}
h1{font-size:1.5rem;margin:.2em 0}h2{font-size:1.15rem;margin:1.6em 0 .5em;color:var(--accent)}
.sub{color:var(--muted);font-size:.9rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:8px 0}
.day{font-size:.8rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
a{color:var(--accent)}.meal a{font-weight:700;text-decoration:none}.meal a:after{content:" ↗";font-weight:400}
.note{font-size:.9rem;color:var(--muted)}
.proof img{width:100%;height:auto;border-radius:8px;display:block;margin-top:8px}
.tag{display:inline-block;background:var(--tag);color:var(--tagink);border-radius:8px;padding:0 7px;font-size:.78rem;margin-left:4px}
nav{position:sticky;top:0;background:var(--bg);padding:8px 0;display:flex;gap:8px;overflow-x:auto;border-bottom:1px solid var(--line);z-index:2}
nav a{white-space:nowrap;padding:4px 10px;border:1px solid var(--line);border-radius:999px;text-decoration:none;font-size:.85rem}
.row{display:flex;justify-content:space-between;gap:10px;padding:8px 0;border-bottom:1px solid var(--line)}
.row label{display:flex;gap:8px;align-items:flex-start}.row input{margin-top:4px;width:18px;height:18px}
.price{white-space:nowrap;text-align:right;font-size:.9rem;color:var(--muted)}
.sec{font-weight:700;margin-top:14px}
.fav{color:#b8860b;text-transform:none;letter-spacing:0;font-weight:700}
"""
    p = []
    p.append(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>Dinner plan · week of {e(week)}</title><style>{css}</style></head><body><main>")
    p.append(f"<h1>Dinner plan · week of {e(week)}</h1><div class='sub'>Flyers valid {e(plan['flyer_dates'])} · Shop at {e(plan['shop_at']['name'])}, {e(plan['shop_at']['address'])} · 6 dinners, gluten-free, ≤45 min</div>")
    p.append("<nav><a href='#matches'>Price matches</a><a href='#list'>Grocery list</a><a href='#dinners'>Dinners</a><a href='{fav_href}'>★ Favorites</a></nav>")

    p.append(f"<h2 id='matches'>Price matches ({len(matches)}) — show these at the till</h2>")
    for g in matches:
        note = f" <span class='tag'>{e(g['note'])}</span>" if g.get("note") else ""
        p.append(f"<div class='card proof'><b>{e(g['name'])}</b> — {e(g['price'])} at <b>{e(g['_store'])}</b>{note}"
                 f"<div class='note'>{e(g['_store_addr'])}</div><img loading='lazy' src='{g['_proof']}' alt='{e(g['_store'])} flyer ad for {e(g['name'])}'></div>")

    p.append(f"<h2 id='list'>Grocery list — est. ${total:.2f}</h2><div class='card'>")
    for sec in ["Proteins", "Produce", "Pantry"]:
        p.append(f"<div class='sec'>{sec}</div>")
        for i, g in enumerate([x for x in plan["groceries"] if x["section"] == sec]):
            tag = f"<span class='tag'>match {e(g['_store'])}</span>" if g.get("_store") else ""
            p.append(f"<div class='row'><label><input type='checkbox'><span>{e(g['name'])} {tag}<br><span class='note'>{e(g['qty'])}</span></span></label>"
                     f"<div class='price'>{e(g['price'])}<br>${g['est']:.2f}</div></div>")
    p.append(f"<div class='row'><b>Estimated total</b><b>${total:.2f}</b></div>")
    p.append(f"<div class='note' style='margin-top:8px'>Check the pantry: {e(' · '.join(plan['pantry']))}</div></div>")

    favs = load_favs()
    fav_urls = {f["url"] for f in favs}
    p.append("<h2 id='dinners'>Dinners</h2>")
    for d in plan["dinners"]:
        star = " <span class='fav'>★ Favorite</span>" if d["url"] in fav_urls else ""
        p.append(f"<div class='card meal'><div class='day'>{e(d['day'])} · {e(d['time'])} · {e(d['site'])}{star}</div>"
                 f"<a href='{e(d['url'])}' target='_blank' rel='noopener'>{e(d['name'])}</a><div class='note'>{e(d['note'])}</div></div>")

    p.append("<p class='note'>Estimates assume 2 servings per dinner. Price matches are at staff discretion and need the same item/size. Check labels on sauces, spices and broths for gluten.</p>")
    p.append("</main></body></html>")
    page = "\n".join(p)
    open(os.path.join(out_dir, "index.html"), "w").write(page.replace("{fav_href}", "../../favorites.html"))

    # Root index = latest week (proof paths rewritten to the week folder)
    root_page = page.replace("src='proofs/", f"src='weeks/{week}/proofs/").replace("{fav_href}", "favorites.html")
    write_favorites_page(favs, css)
    open(os.path.join(ROOT, "index.html"), "w").write(root_page)
    open(os.path.join(ROOT, ".nojekyll"), "w").write("")

    summary = [{"name": g["name"], "price": g["price"], "store": g["_store"],
                "address": g["_store_addr"], "proof": g["_proof"]} for g in matches]
    json.dump(summary, open(os.path.join(out_dir, "matches.json"), "w"), indent=1)
    print(json.dumps({"week": week, "total": round(total, 2), "matches": summary}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
