"""Generate optimised web images from the supplied source assets.

Usage (dev dependencies required):
    python scripts/build_images.py

Inputs  (assets/source/):
    doctor-portrait.png   - the doctor's professional portrait (supplied)
    emblem-original.png   - the supplied blue/green emblem artwork

Outputs (app/static/images/):
    doctor/portrait-{480,800,1122}.{avif,webp} + portrait-800.jpg
    logo/emblem.{png,webp} (+ @2x)      navy/gold interim emblem, transparent
    icons/favicon-*.png, favicon.ico, apple-touch-icon.png, icon-{192,512}.png
    og/social-preview.jpg               1200x630 social sharing image

The emblem is recoloured from the supplied blue/green file to the navy/gold
palette seen on the clinic signage. It is an interim derivative: replace the
files in app/static/images/logo/ with the official vector logo when available.
"""

from __future__ import annotations

import contextlib
import sys
import tempfile
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFilter, ImageFont, features

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "source"
OUT = ROOT / "app" / "static" / "images"
FONTS = ROOT / "app" / "static" / "fonts"

NAVY = (16, 47, 74)
MIDNIGHT = (7, 27, 45)
GOLD = (201, 162, 79)
GOLD_SOFT = (229, 212, 167)
IVORY = (248, 246, 241)


# --------------------------------------------------------------------------- helpers
def hex_stops(stops: list[tuple[float, tuple[int, int, int]]], t: np.ndarray) -> np.ndarray:
    """Piecewise-linear colour gradient lookup. t in [0, 1] -> RGB floats in [0, 1]."""
    xs = np.array([s[0] for s in stops])
    out = np.zeros((*t.shape, 3), dtype=np.float32)
    for c in range(3):
        ys = np.array([s[1][c] / 255 for s in stops])
        out[..., c] = np.interp(t, xs, ys)
    return out


def rgb_to_hsv(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    delta = mx - mn
    s = np.where(mx > 0, delta / np.maximum(mx, 1e-6), 0)
    h = np.zeros_like(mx)
    mask = delta > 1e-6
    rc = np.where(mask, (mx - r) / np.maximum(delta, 1e-6), 0)
    gc = np.where(mask, (mx - g) / np.maximum(delta, 1e-6), 0)
    bc = np.where(mask, (mx - b) / np.maximum(delta, 1e-6), 0)
    h = np.where(r == mx, bc - gc, h)
    h = np.where(g == mx, 2.0 + rc - bc, h)
    h = np.where(b == mx, 4.0 + gc - rc, h)
    h = (h / 6.0) % 1.0
    h = np.where(mask, h, 0)
    return h * 360, s, mx


def smoothstep(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def save_webp(img: Image.Image, path: Path, quality: int = 82) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "WEBP", quality=quality, method=6)


# --------------------------------------------------------------------------- emblem
def build_emblem() -> Image.Image:
    src = Image.open(SRC / "emblem-original.png").convert("RGB")
    w, h = src.size

    # 1. Background mask: flood-fill the near-white area connected to the edges.
    key = (255, 0, 255)
    probe = src.copy()
    for xy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 2), (w // 2, h - 3)]:
        if probe.getpixel(xy) != key:
            ImageDraw.floodfill(probe, xy, key, thresh=42)
    parr = np.asarray(probe)
    bg = (parr[..., 0] == 255) & (parr[..., 1] == 0) & (parr[..., 2] == 255)

    rgb = np.asarray(src).astype(np.float32) / 255

    # 2. Soft alpha on the boundary ring to keep anti-aliasing.
    bg_img = Image.fromarray((bg * 255).astype(np.uint8))
    near = np.asarray(bg_img.filter(ImageFilter.MaxFilter(5))) > 0
    ring = near & ~bg
    minc = rgb.min(axis=-1)
    alpha = np.ones(bg.shape, dtype=np.float32)
    alpha[bg] = 0
    ring_alpha = np.clip((1 - minc) / 0.30, 0, 1)
    alpha[ring] = ring_alpha[ring]
    safe = np.maximum(alpha, 1e-3)[..., None]
    rgb = np.where(ring[..., None], np.clip((rgb - (1 - safe)) / safe, 0, 1), rgb)

    # 3. Recolour by hue family: blues -> navy scale, greens -> gold scale.
    hue, sat, val = rgb_to_hsv(rgb)
    weight = smoothstep(0.16, 0.42, sat)
    blue = (hue >= 165) & (hue <= 275)
    green = (hue >= 45) & (hue < 165)

    def norm(v: np.ndarray, sel: np.ndarray) -> np.ndarray:
        lo, hi = np.percentile(v[sel & (weight > 0.5)], [2, 98])
        return np.clip((v - lo) / max(hi - lo, 1e-3), 0, 1)

    navy_scale = hex_stops(
        [(0.0, (5, 20, 34)), (0.45, (12, 38, 61)), (0.75, (19, 55, 86)), (1.0, (52, 104, 138))],
        norm(val, blue),
    )
    gold_scale = hex_stops(
        [(0.0, (126, 94, 32)), (0.45, (186, 148, 68)), (0.8, (214, 182, 106)), (1.0, (236, 222, 178))],
        norm(val, green),
    )
    neutral = np.repeat(val[..., None], 3, axis=-1)
    mapped = np.where(blue[..., None], navy_scale, np.where(green[..., None], gold_scale, neutral))
    w3 = weight[..., None]
    out_rgb = neutral * (1 - w3) + mapped * w3

    rgba = np.dstack([out_rgb, alpha]).clip(0, 1)
    img = Image.fromarray((rgba * 255).round().astype(np.uint8), "RGBA")
    bbox = img.getchannel("A").point(lambda a: 255 if a > 10 else 0).getbbox()
    img = img.crop(bbox)
    # square canvas with a little breathing room
    side = int(max(img.size) * 1.04)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
    return canvas


def write_emblem_assets(emblem: Image.Image) -> None:
    logo_dir = OUT / "logo"
    logo_dir.mkdir(parents=True, exist_ok=True)
    big = emblem.resize((512, 512), Image.LANCZOS)
    big.save(logo_dir / "emblem-512.png", optimize=True)
    for size in (96, 192):
        im = emblem.resize((size, size), Image.LANCZOS)
        im.save(logo_dir / f"emblem-{size}.png", optimize=True)
        save_webp(im, logo_dir / f"emblem-{size}.webp", quality=90)

    icons = OUT / "icons"
    icons.mkdir(parents=True, exist_ok=True)

    def on_badge(size: int, pad: float, bg=(255, 255, 255, 255), round_bg: bool = False) -> Image.Image:
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0) if round_bg else bg)
        if round_bg:
            ImageDraw.Draw(canvas).ellipse((0, 0, size - 1, size - 1), fill=bg)
        inner = int(size * (1 - 2 * pad))
        mark = emblem.resize((inner, inner), Image.LANCZOS)
        canvas.paste(mark, ((size - inner) // 2, (size - inner) // 2), mark)
        return canvas

    on_badge(32, 0.02, round_bg=True).save(icons / "favicon-32.png", optimize=True)
    on_badge(16, 0.0, round_bg=True).save(icons / "favicon-16.png", optimize=True)
    on_badge(64, 0.02, round_bg=True).save(icons / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    on_badge(180, 0.12, bg=(*IVORY, 255)).convert("RGB").save(icons / "apple-touch-icon.png", optimize=True)
    on_badge(192, 0.16, bg=(*IVORY, 255)).save(icons / "icon-192.png", optimize=True)
    on_badge(512, 0.16, bg=(*IVORY, 255)).save(icons / "icon-512.png", optimize=True)


# --------------------------------------------------------------------------- portrait
def write_portrait() -> Image.Image:
    src = Image.open(SRC / "doctor-portrait.png").convert("RGB")
    out = OUT / "doctor"
    out.mkdir(parents=True, exist_ok=True)
    avif = features.check("avif")
    for width in (480, 800, 1122):
        height = round(src.height * width / src.width)
        im = src.resize((width, height), Image.LANCZOS) if width != src.width else src
        save_webp(im, out / f"portrait-{width}.webp", quality=80)
        if avif:
            im.save(out / f"portrait-{width}.avif", "AVIF", quality=58)
        if width == 800:
            im.save(out / "portrait-800.jpg", "JPEG", quality=82, optimize=True, progressive=True)
    print(f"portrait sizes written (AVIF {'on' if avif else 'unavailable'})")
    return src


# --------------------------------------------------------------------------- social preview
def load_font(woff2: str, size: int, weight: int, tmp: Path) -> ImageFont.FreeTypeFont:
    ttf = tmp / (Path(woff2).stem + ".ttf")
    if not ttf.exists():
        font = TTFont(FONTS / woff2)
        font.flavor = None
        font.save(ttf)
    f = ImageFont.truetype(str(ttf), size)
    with contextlib.suppress(OSError, ValueError):  # static fonts have no weight axis
        f.set_variation_by_axes([weight])
    return f


def draw_tracked(draw: ImageDraw.ImageDraw, xy, text: str, font, fill, tracking: float) -> None:
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking


def write_social(portrait: Image.Image, emblem: Image.Image) -> None:
    W, H = 1200, 630
    grad = np.linspace(0, 1, W)[None, :, None]
    a = np.array(MIDNIGHT, dtype=np.float32)
    b = np.array(NAVY, dtype=np.float32)
    bg = (a * (1 - grad) + b * grad).repeat(H, axis=0)
    img = Image.fromarray(bg.astype(np.uint8), "RGB").convert("RGBA")
    draw = ImageDraw.Draw(img)

    # Decorative gold arcs (alpha-composited so they stay subtle behind the text)
    arcs = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ad = ImageDraw.Draw(arcs)
    for r, alpha in ((350, 70), (420, 42)):
        ad.arc((935 - r, 330 - r, 935 + r, 330 + r), 95, 265, fill=(*GOLD, alpha), width=2)
    img = Image.alpha_composite(img, arcs)
    draw = ImageDraw.Draw(img)

    # Portrait in an arch frame
    fw, fh = 400, 540
    fx, fy = 735, 60
    crop_w = portrait.width
    crop_h = round(crop_w * fh / fw)
    photo = portrait.crop((0, 0, crop_w, min(crop_h, portrait.height))).resize((fw, fh), Image.LANCZOS)
    mask = Image.new("L", (fw, fh), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse((0, 0, fw, fw), fill=255)
    md.rectangle((0, fw // 2, fw, fh), fill=255)
    outline = ImageDraw.Draw(img)
    outline.rounded_rectangle(
        (fx - 14, fy - 14 + fw // 2, fx + fw + 14, fy + fh + 14), radius=4, outline=(*GOLD, 120), width=2
    )
    outline.arc((fx - 14, fy - 14, fx + fw + 14, fy + fw + 14), 180, 360, fill=(*GOLD, 120), width=2)
    img.paste(photo, (fx, fy), mask)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        serif = lambda s, w=600: load_font("playfair-display-latin-wght-normal.woff2", s, w, tmp)  # noqa: E731
        serif_i = lambda s, w=500: load_font("playfair-display-latin-wght-italic.woff2", s, w, tmp)  # noqa: E731
        sans = lambda s, w=600: load_font("manrope-latin-wght-normal.woff2", s, w, tmp)  # noqa: E731

        # Emblem on a white disc
        disc = 104
        badge = Image.new("RGBA", (disc, disc), (0, 0, 0, 0))
        ImageDraw.Draw(badge).ellipse((0, 0, disc - 1, disc - 1), fill=(255, 255, 255, 255))
        mark = emblem.resize((86, 86), Image.LANCZOS)
        badge.paste(mark, (9, 9), mark)
        img.paste(badge, (80, 72), badge)

        draw_tracked(draw, (80, 206), "SMAHIE", serif(76, 600), IVORY, 3)
        draw_tracked(draw, (82, 292), "ORTHO CARE", serif(42, 600), IVORY, 6)
        draw.line((84, 362, 380, 362), fill=GOLD, width=3)
        draw.text((80, 384), "Care That Keeps You Moving.", font=serif_i(36, 500), fill=GOLD_SOFT)
        draw_tracked(draw, (82, 446), "BONE  •  SPINE  •  JOINT  •  MOVEMENT", sans(17, 700), GOLD, 2.2)
        draw.text((80, 512), "Dr. Arun Selvan R  ·  MBBS, MS (Ortho)", font=sans(24, 700), fill=IVORY)
        draw.text(
            (80, 548), "Consultant Orthopaedic Surgeon  ·  Perungudi, Chennai", font=sans(19, 500), fill=(196, 208, 220)
        )

    og = OUT / "og"
    og.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(og / "social-preview.jpg", "JPEG", quality=86, optimize=True, progressive=True)


def main() -> int:
    if not SRC.exists():
        print(f"missing {SRC}", file=sys.stderr)
        return 1
    emblem = build_emblem()
    write_emblem_assets(emblem)
    portrait = write_portrait()
    write_social(portrait, emblem)
    print("images written to", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
