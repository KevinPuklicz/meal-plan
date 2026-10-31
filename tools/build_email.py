"""Render the weekly email body from a plan JSON (run after build_site.py).

    python3 tools/build_email.py tools/plan_<week>.json > /tmp/email.html

Gmail-safe HTML: inline styles only, button uses a bgcolor table cell so it
never renders as invisible white-on-white, every price match links straight
to its boxed flyer image on GitHub Pages.
"""
import html
import json
import os
import re
import sys
from urllib.parse import quote

SITE = "https://kevinpuklicz.github.io/meal-plan"
FAV_TO = "kevinpuklicz4@gmail.com"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
e = html.escape
GREEN, MUTED, LINE, TAGINK = "#1d5b3a", "#5d6b63", "#e5e9e6", "#7a4a00"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]


def load_favs():
    p = os.path.join(ROOT, "tools", "favorites.json")
    try:
        return {f["url"] for f in json.load(open(p))}
    except Exception:
        return set()


def main(plan_path):
    plan = json.load(open(plan_path))
    week = plan["week_of"]
    page = f"{SITE}/weeks/{week}/"
    matches = [g for g in plan["groceries"] if g.get("match")]
    total = sum(g["est"] for g in plan["groceries"])
    stores = {}
    summ = os.path.join(ROOT, "weeks", week, "matches.json")
    if os.path.exists(summ):
        stores = {m["name"]: m for m in json.load(open(summ))}

    o = [f"<div style='max-width:680px;margin:0 auto;font-family:Arial,Helvetica,sans-serif;color:#1f2421;font-size:15px;line-height:1.45'>"]
    o.append(f"<p style='margin:0 0 12px;color:{MUTED}'>Flyers {e(plan['flyer_dates'])} · {e(plan['shop_at']['name'])}, {e(plan['shop_at']['address'])} · 6 dinners, gluten-free, ≤45 min</p>")
    # Bulletproof button
    o.append(f"<table role='presentation' cellpadding='0' cellspacing='0' style='margin:14px 0 6px'><tr>"
             f"<td bgcolor='{GREEN}' style='background-color:{GREEN};border-radius:8px'>"
             f"<a href='{page}' style='display:inline-block;padding:12px 20px;color:#ffffff;font-weight:bold;text-decoration:none;font-size:16px'>"
             f"Open price-match proofs &amp; checklist</a></td></tr></table>")
    o.append(f"<p style='margin:0 0 18px;font-size:13px;color:{MUTED}'>Or open: <a href='{page}' style='color:{GREEN}'>{page}</a></p>")

    o.append(f"<h2 style='font-size:18px;color:{GREEN};margin:20px 0 8px'>Dinners</h2>")
    favs = load_favs()
    for d in plan["dinners"]:
        if d["url"] in favs:
            star = f"<span style='color:#b8860b;font-size:13px'>★ Favorite</span>"
        else:
            mt = (f"mailto:{FAV_TO}?subject=" + quote(f"Favorite: {d['name']}") +
                  "&body=" + quote(f"{d['url']}\n\n(Just hit send. Next week's plan will add this to your favorites.)"))
            star = f"<a href='{e(mt)}' style='color:#b8860b;font-size:13px;text-decoration:none'>☆ Favorite</a>"
        o.append(f"<p style='margin:0 0 10px'><b>{e(d['day'])}</b> — <a href='{e(d['url'])}' style='color:{GREEN};font-weight:bold'>{e(d['name'])}</a> "
                 f"<span style='color:{MUTED}'>({e(d['site'])}, {e(d['time'])})</span> · {star}<br><span style='color:{MUTED};font-size:14px'>{e(d['note'])}</span></p>")
    o.append(f"<p style='margin:4px 0 0;font-size:12px;color:{MUTED}'>Tap ☆ Favorite on any dinner you loved and hit send — favorites come back every few weeks. "
             f"<a href='{SITE}/favorites.html' style='color:{GREEN}'>See all favorites</a></p>")

    o.append(f"<h2 style='font-size:18px;color:{GREEN};margin:20px 0 8px'>Price matches ({len(matches)})</h2>"
             f"<table style='width:100%;border-collapse:collapse;font-size:14px'>")
    for g in matches:
        s = stores.get(g["name"], {})
        img = f"{page}proofs/{slug(g['name'])}.jpg"
        note = f"<br><span style='color:{TAGINK}'>{e(g['note'])}</span>" if g.get("note") else ""
        o.append(f"<tr><td style='padding:6px 4px;border-bottom:1px solid {LINE}'><b>{e(g['name'])}</b>{note}<br>"
                 f"<a href='{img}' style='color:{GREEN};font-size:13px'>See flyer ad ›</a></td>"
                 f"<td style='padding:6px 4px;border-bottom:1px solid {LINE};white-space:nowrap'>{e(g['price'])}</td>"
                 f"<td style='padding:6px 4px;border-bottom:1px solid {LINE}'>{e(s.get('store',''))}<br><span style='color:{MUTED}'>{e(s.get('address',''))}</span></td></tr>")
    o.append("</table>")

    o.append(f"<h2 style='font-size:18px;color:{GREEN};margin:20px 0 8px'>Grocery list — est. ${total:.2f}</h2>"
             f"<table style='width:100%;border-collapse:collapse;font-size:14px'>")
    for sec in ["Proteins", "Produce", "Pantry"]:
        rows = [g for g in plan["groceries"] if g["section"] == sec]
        if not rows:
            continue
        o.append(f"<tr><td colspan='4' style='padding:10px 4px 4px;font-weight:bold'>{sec}</td></tr>")
        for g in rows:
            tag = f" <span style='color:{TAGINK}'>(match {e(stores.get(g['name'],{}).get('store',''))})</span>" if g.get("match") else ""
            o.append(f"<tr><td style='padding:4px;border-bottom:1px solid {LINE}'>☐ {e(g['name'])}{tag}</td>"
                     f"<td style='padding:4px;border-bottom:1px solid {LINE}'>{e(g['qty'])}</td>"
                     f"<td style='padding:4px;border-bottom:1px solid {LINE};white-space:nowrap'>{e(g['price'])}</td>"
                     f"<td style='padding:4px;border-bottom:1px solid {LINE};text-align:right'>${g['est']:.2f}</td></tr>")
    o.append(f"<tr><td colspan='3' style='padding:8px 4px;font-weight:bold'>Estimated total</td><td style='padding:8px 4px;text-align:right;font-weight:bold'>${total:.2f}</td></tr></table>")
    o.append(f"<p style='margin:10px 0;font-size:14px'><b>Pantry check:</b> {e(' · '.join(plan['pantry']))}</p>")
    o.append(f"<p style='margin:18px 0 0;font-size:12px;color:{MUTED}'>Estimates assume 2 servings per dinner. Price matches are at staff discretion and need the same item and size. Check labels on sauces, spices and broths for gluten.</p></div>")
    print("".join(o))


if __name__ == "__main__":
    main(sys.argv[1])
