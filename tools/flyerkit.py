"""flyerkit — fetch Flipp flyer data and render price-match proof images.

Each proof is a crop of the real flyer page around the item, with a box drawn
on the item and a caption strip (store, location, price, valid dates).

Usage as a library:
    import flyerkit as fk
    flyers = fk.get_flyers("N2L3G1", fk.DEFAULT_MERCHANTS)
    items = fk.get_items(flyer["id"])
    store = fk.nearby_store(flyer["id"], "N2L3G1")
    fk.render_proof(flyer, item, store, "out/ground_beef.jpg")

Needs network access to backflipp.wishabi.com, f.wishabi.net and
dam.flippenterprise.net.
"""
from __future__ import annotations

import io
import math
import os
from datetime import datetime

import requests
from PIL import Image, ImageDraw, ImageFont

BACKFLIPP = "https://backflipp.wishabi.com/flipp"
DAM = "https://dam.flippenterprise.net/api/flipp"
IMG_HOST = "https://f.wishabi.net/"
# No Frills (where they shop) + the stores they price-match against.
DEFAULT_MERCHANTS = [
    "No Frills", "Farm Boy", "Food Basics", "FreshCo", "Zehrs", "Sobeys", "Walmart",
]
UA = {"User-Agent": "Mozilla/5.0 (meal-planner; personal use)"}
_session = requests.Session()
_session.headers.update(UA)
_tile_cache: dict[str, Image.Image] = {}


def _get_json(url: str, **params):
    r = _session.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


# ---------- data ----------

def get_flyers(postal_code: str, merchants=DEFAULT_MERCHANTS, grocery_only=True):
    """Current flyers near a postal code for the given merchants."""
    data = _get_json(f"{BACKFLIPP}/flyers", locale="en-ca", postal_code=postal_code)
    flyers = data.get("flyers", data) if isinstance(data, dict) else data
    out = []
    for f in flyers:
        m = (f.get("merchant") or "").lower()
        if not any(x.lower() in m for x in merchants):
            continue
        if grocery_only and "Groceries" not in (f.get("categories") or []):
            continue
        out.append(f)
    return out


def get_items(flyer_id: int):
    data = _get_json(f"{BACKFLIPP}/flyers/{flyer_id}", locale="en-ca")
    return data.get("items", [])


def get_item_detail(item_id: int):
    data = _get_json(f"{BACKFLIPP}/items/{item_id}", locale="en-ca")
    return data.get("item", data)


def nearby_store(flyer_id: int, postal_code: str):
    """The physical store this flyer belongs to near the postal code."""
    try:
        stores = _get_json(f"{DAM}/flyers/{flyer_id}/stores/nearby",
                           postal_code=postal_code, locale="en")
        return stores[0] if stores else None
    except Exception:
        return None


# ---------- image rendering ----------

def _tile(path: str, z: int, x: int, y: int) -> Image.Image | None:
    url = f"{IMG_HOST}{path}{z}_{x}_{y}.jpg"
    if url in _tile_cache:
        return _tile_cache[url]
    r = _session.get(url, timeout=30)
    img = Image.open(io.BytesIO(r.content)).convert("RGB") if r.ok else None
    _tile_cache[url] = img
    return img


def _tile_size(path: str, z: int) -> int:
    t = _tile(path, z, 0, 0)
    return t.width if t else 256


def _zoom_for(flyer, target_scale: float) -> int:
    """Pick the zoom index whose scale (px per flyer unit) is closest to target.

    resolutions[i] is the downscale factor at zoom i (largest first), so the
    rendered scale at zoom i is 1 / resolutions[i].
    """
    res = flyer["resolutions"]
    best = min(range(len(res)), key=lambda i: abs((1 / res[i]) - target_scale))
    return best


def render_region(flyer, x0, y0, x1, y1, out_px_width=900) -> tuple[Image.Image, float]:
    """Render flyer-space rectangle (y measured downward, positive) to an image."""
    path = flyer["path"]
    target_scale = out_px_width / max(1.0, (x1 - x0))
    z = _zoom_for(flyer, target_scale)
    scale = 1 / flyer["resolutions"][z]
    ts = _tile_size(path, z)
    px0, py0 = int(x0 * scale), int(y0 * scale)
    px1, py1 = int(math.ceil(x1 * scale)), int(math.ceil(y1 * scale))
    # Tile rows are numbered from the BOTTOM of the flyer, and the tile grid is
    # anchored to the bottom edge (any partial row is at the top).
    h_px = int(round(flyer["height"] * scale))
    rows = -(-h_px // ts)
    off = rows * ts - h_px  # blank pixels above the content in grid space
    canvas = Image.new("RGB", (px1 - px0, py1 - py0), "white")
    for r in range((py0 + off) // ts, (py1 + off) // ts + 1):
        ty = rows - 1 - r
        if ty < 0 or ty >= rows:
            continue
        for tx in range(px0 // ts, px1 // ts + 1):
            t = _tile(path, z, tx, ty)
            if t is not None:
                canvas.paste(t, (tx * ts - px0, r * ts - off - py0))
    return canvas, scale


def _font(size):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Helvetica.ttc"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _fmt_dates(item):
    try:
        a = datetime.fromisoformat(item["valid_from"]).strftime("%b %-d")
        b = datetime.fromisoformat(item["valid_to"]).strftime("%b %-d")
        return f"Valid {a} – {b}"
    except Exception:
        return ""


def render_proof(flyer, item, store, out_path, price_text=None, pad_ratio=0.6,
                 out_px_width=900):
    """Crop the flyer page around `item`, box it, add a caption, save as JPEG."""
    # Flipp item y-coords are negative going down from the top edge.
    ix0, ix1 = item["left"], item["right"]
    iy0, iy1 = -item["top"], -item["bottom"]
    w, h = ix1 - ix0, iy1 - iy0
    pad_x, pad_y = w * pad_ratio, h * pad_ratio
    page_w, page_h = flyer["width"], flyer["height"]
    x0 = max(0, ix0 - pad_x)
    x1 = min(page_w, ix1 + pad_x)
    y0 = max(0, iy0 - pad_y)
    y1 = min(page_h, iy1 + pad_y)

    img, scale = render_region(flyer, x0, y0, x1, y1, out_px_width)
    # Normalize width so every proof looks the same on a phone.
    if img.width != out_px_width:
        k = out_px_width / img.width
        img = img.resize((out_px_width, int(img.height * k)), Image.LANCZOS)
        scale *= k

    d = ImageDraw.Draw(img)
    bx0 = (ix0 - x0) * scale
    by0 = (iy0 - y0) * scale
    bx1 = (ix1 - x0) * scale
    by1 = (iy1 - y0) * scale
    lw = max(5, img.width // 120)
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=14, outline=(230, 30, 30), width=lw)

    # Caption strip
    merchant = flyer.get("merchant", "")
    loc = ""
    if store:
        loc = f"{store.get('address', '')}, {store.get('city', '')}".strip(", ")
    price = price_text or (f"${item['price']}" if item.get("price") else "")
    line1 = f"{merchant}  ·  {price}"
    line2 = "  ·  ".join(x for x in [loc, _fmt_dates(item)] if x)
    f1, f2 = _font(34), _font(24)
    strip_h = 110
    out = Image.new("RGB", (img.width, img.height + strip_h), (29, 91, 58))
    out.paste(img, (0, 0))
    d2 = ImageDraw.Draw(out)
    d2.text((20, img.height + 14), line1, fill="white", font=f1)
    d2.text((20, img.height + 62), line2, fill=(220, 240, 228), font=f2)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    out.save(out_path, "JPEG", quality=82, optimize=True)
    return out_path
