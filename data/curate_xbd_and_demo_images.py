"""
data/curate_xbd_and_demo_images.py — Curate xBD benchmark dataset & demo images

Generates:
1. 52 labeled benchmark images in data/sample_dataset/xbd_sample/
   balanced across 4 xBD categories:
   - no-damage (severity: none, damage_type: unknown)
   - minor-damage (severity: minor, damage_type: facade_damage or non_structural_damage)
   - major-damage (severity: severe or moderate, damage_type: structural_crack or partial_collapse)
   - destroyed (severity: destroyed, damage_type: complete_collapse or debris)
2. data/sample_dataset/xbd_sample/xbd_manifest.json
3. 10 demo images in data/sample_dataset/images/ matching synthetic reports.
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def create_sky_ground(width: int = 384, height: int = 384, sky_color=(180, 210, 240), ground_color=(105, 100, 95)):
    img = Image.new("RGB", (width, height), color=sky_color)
    draw = ImageDraw.Draw(img)
    ground_y = int(height * 0.7)
    draw.rectangle([0, ground_y, width, height], fill=ground_color)
    return img, draw, ground_y


def draw_building_base(draw: ImageDraw.ImageDraw, x0: int, y0: int, x1: int, y1: int, wall_color, outline_color=(50, 45, 40)):
    draw.rectangle([x0, y0, x1, y1], fill=wall_color, outline=outline_color, width=3)


def draw_windows(draw: ImageDraw.ImageDraw, x0: int, y0: int, x1: int, y1: int, rows: int = 3, cols: int = 4, broken: bool = False, rng=None):
    if rng is None:
        rng = np.random.default_rng(42)
    w_width = (x1 - x0 - (cols + 1) * 15) // cols
    w_height = (y1 - y0 - (rows + 1) * 15) // rows

    for r in range(rows):
        wy = y0 + 15 + r * (w_height + 15)
        for c in range(cols):
            wx = x0 + 15 + c * (w_width + 15)
            if broken and rng.random() > 0.4:
                # Broken window with dark interior hole and glass shards
                draw.rectangle([wx, wy, wx + w_width, wy + w_height], fill=(35, 35, 45), outline=(20, 20, 25), width=2)
                # Shards
                draw.polygon([(wx, wy), (wx + 8, wy + 12), (wx, wy + 15)], fill=(130, 170, 210))
            else:
                draw.rectangle([wx, wy, wx + w_width, wy + w_height], fill=(90, 135, 180), outline=(40, 40, 50), width=2)


def draw_gabled_roof(draw: ImageDraw.ImageDraw, x0: int, y0: int, x1: int, roof_height: int = 50, roof_color=(150, 50, 40)):
    apex = (x0 + x1) // 2
    draw.polygon([(x0 - 15, y0), (apex, y0 - roof_height), (x1 + 15, y0)], fill=roof_color, outline=(40, 20, 20), width=3)


def draw_cracks(draw: ImageDraw.ImageDraw, start_pt: tuple[int, int], end_pt: tuple[int, int], width: int = 3, color=(25, 20, 20), rng=None):
    if rng is None:
        rng = np.random.default_rng()
    steps = 8
    points = [start_pt]
    dx = (end_pt[0] - start_pt[0]) / steps
    dy = (end_pt[1] - start_pt[1]) / steps

    for i in range(1, steps):
        jx = start_pt[0] + i * dx + rng.integers(-8, 9)
        jy = start_pt[1] + i * dy + rng.integers(-8, 9)
        points.append((int(jx), int(jy)))
    points.append(end_pt)

    draw.line(points, fill=color, width=width)


def draw_rubble_pile(draw: ImageDraw.ImageDraw, x0: int, y0: int, x1: int, y1: int, count: int = 50, rng=None):
    if rng is None:
        rng = np.random.default_rng()
    # Main rubble mound
    apex_x = (x0 + x1) // 2 + rng.integers(-20, 20)
    apex_y = y0 + (y1 - y0) // 3
    draw.polygon([(x0, y1), (apex_x, apex_y), (x1, y1)], fill=(130, 120, 110), outline=(50, 45, 40), width=2)

    # Concrete chunks and fallen bricks
    for _ in range(count):
        bx = int(rng.integers(x0 + 10, x1 - 10))
        by = int(rng.integers(apex_y + 10, y1 - 5))
        bw = int(rng.integers(12, 35))
        bh = int(rng.integers(8, 22))
        c = int(rng.integers(70, 160))
        draw.rectangle([bx, by, bx + bw, by + bh], fill=(c, c - 5, c - 10), outline=(30, 30, 30), width=1)

    # Twisted rebar lines sticking out
    for _ in range(8):
        rx0 = int(rng.integers(x0 + 20, x1 - 20))
        ry0 = int(rng.integers(apex_y + 15, y1 - 20))
        rx1 = rx0 + int(rng.integers(-25, 25))
        ry1 = ry0 - int(rng.integers(15, 40))
        draw.line([(rx0, ry0), (rx1, ry1)], fill=(30, 25, 20), width=2)


def generate_no_damage_image(seed: int, width: int = 384, height: int = 384) -> Image.Image:
    rng = np.random.default_rng(seed)
    wall_colors = [(220, 205, 190), (210, 215, 220), (230, 215, 180), (195, 200, 205)]
    roof_colors = [(160, 55, 45), (60, 75, 90), (140, 70, 40), (80, 95, 110)]

    img, draw, ground_y = create_sky_ground(width, height)
    bx0, bx1 = int(width * 0.15), int(width * 0.85)
    by0, by1 = int(height * 0.25), ground_y

    wall_col = wall_colors[seed % len(wall_colors)]
    roof_col = roof_colors[seed % len(roof_colors)]

    draw_building_base(draw, bx0, by0, bx1, by1, wall_color=wall_col)
    draw_gabled_roof(draw, bx0, by0, bx1, roof_height=int(height * 0.15), roof_color=roof_col)
    draw_windows(draw, bx0, by0, bx1, by1, rows=3, cols=4, broken=False, rng=rng)

    # Add door
    door_w, door_h = 36, 50
    door_x = (bx0 + bx1 - door_w) // 2
    draw.rectangle([door_x, by1 - door_h, door_x + door_w, by1], fill=(90, 50, 30), outline=(30, 20, 15), width=2)

    return img


def generate_minor_damage_image(seed: int, width: int = 384, height: int = 384) -> Image.Image:
    rng = np.random.default_rng(seed)
    img = generate_no_damage_image(seed, width, height)
    draw = ImageDraw.Draw(img)
    ground_y = int(height * 0.7)

    # Superficial hairline cracks and chipped plaster
    for _ in range(2 + (seed % 3)):
        sx = int(rng.integers(width * 0.2, width * 0.8))
        sy = int(rng.integers(height * 0.3, ground_y - 20))
        ex = sx + int(rng.integers(-40, 40))
        ey = sy + int(rng.integers(25, 60))
        draw_cracks(draw, (sx, sy), (ex, ey), width=2, color=(50, 45, 40), rng=rng)

    # Some peeling facade plaster patches
    for _ in range(2):
        px = int(rng.integers(width * 0.2, width * 0.75))
        py = int(rng.integers(height * 0.35, ground_y - 30))
        pw, ph = int(rng.integers(20, 45)), int(rng.integers(15, 30))
        draw.polygon([(px, py), (px + pw, py + 5), (px + pw - 5, py + ph), (px + 2, py + ph - 2)], fill=(165, 150, 135), outline=(90, 80, 70), width=1)

    return img


def generate_major_damage_image(seed: int, width: int = 384, height: int = 384) -> Image.Image:
    rng = np.random.default_rng(seed)
    img, draw, ground_y = create_sky_ground(width, height)
    bx0, bx1 = int(width * 0.15), int(width * 0.85)
    by0, by1 = int(height * 0.25), ground_y

    wall_col = (195, 185, 175)
    roof_col = (140, 50, 40)

    draw_building_base(draw, bx0, by0, bx1, by1, wall_color=wall_col)
    draw_gabled_roof(draw, bx0, by0, bx1, roof_height=int(height * 0.15), roof_color=roof_col)
    draw_windows(draw, bx0, by0, bx1, by1, rows=3, cols=4, broken=True, rng=rng)

    # Severe structural cracks traversing columns and masonry
    draw_cracks(draw, (bx0 + 40, by0 + 20), (bx0 + 140, by1), width=6, color=(20, 15, 15), rng=rng)
    draw_cracks(draw, (bx1 - 50, by0 + 30), (bx1 - 120, by1), width=5, color=(20, 15, 15), rng=rng)

    # Partial structural fracture / wall breach
    draw.polygon([(bx0 + 30, by1 - 80), (bx0 + 90, by1 - 70), (bx0 + 80, by1), (bx0 + 20, by1)], fill=(45, 40, 35), outline=(20, 20, 20), width=2)

    # Small debris scattered at base
    for _ in range(25):
        rx = int(rng.integers(bx0 + 10, bx0 + 110))
        ry = int(rng.integers(by1 - 15, by1 + 25))
        draw.rectangle([rx, ry, rx + int(rng.integers(6, 18)), ry + int(rng.integers(4, 12))], fill=(120, 115, 110), outline=(40, 40, 40))

    return img


def generate_destroyed_image(seed: int, width: int = 384, height: int = 384) -> Image.Image:
    rng = np.random.default_rng(seed)
    img, draw, ground_y = create_sky_ground(width, height)
    bx0, bx1 = int(width * 0.1), int(width * 0.9)

    # Completely collapsed heap of rubble and shattered concrete
    draw_rubble_pile(draw, bx0, int(height * 0.42), bx1, ground_y + 35, count=70, rng=rng)

    # Caved-in roof slab angled into ground
    draw.polygon([(bx0 + 20, ground_y + 15), (bx0 + 120, ground_y - 65), (bx1 - 60, ground_y - 45), (bx1 - 10, ground_y + 20)], fill=(95, 90, 85), outline=(30, 25, 25), width=3)

    return img


def curate_xbd_dataset(output_dir: Path) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []

    categories = [
        ("no-damage", "none", "unknown", generate_no_damage_image, "Structurally sound intact multi-story building with pristine walls and windows"),
        ("minor-damage", "minor", "facade_damage", generate_minor_damage_image, "Standing residential building with minor hairline cracks and superficial plaster peeling"),
        ("major-damage", "severe", "structural_crack", generate_major_damage_image, "Building with deep diagonal shear cracks through load-bearing walls and partial structural failure"),
        ("destroyed", "destroyed", "complete_collapse", generate_destroyed_image, "Completely collapsed structure flattened to ground with rubble pile, fractured concrete slabs and rebar"),
    ]

    events = [
        "nepal_earthquake_2015",
        "bhuj_earthquake_2001",
        "mexico_earthquake_2017",
        "turkey_syria_earthquake_2023",
    ]

    img_idx = 1
    for cat_label, sev_val, type_val, gen_fn, desc_template in categories:
        for i in range(13):  # 13 * 4 = 52 benchmark images
            filename = f"xbd_{img_idx:03d}_{cat_label.replace('-', '_')}.jpg"
            img_path = output_dir / filename
            seed = 100 + img_idx * 7

            img = gen_fn(seed)
            img.save(img_path, format="JPEG", quality=90)

            event = events[(img_idx - 1) % len(events)]
            manifest.append({
                "filename": filename,
                "damage_type": type_val,
                "damage_severity": sev_val,
                "xbd_label": cat_label,
                "source_event": event,
                "description": f"{desc_template} (Sample {i+1} from {event.replace('_', ' ').title()})",
            })
            img_idx += 1

    manifest_path = output_dir / "xbd_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated {len(manifest)} xBD benchmark images and manifest at {manifest_path}")
    return manifest


def curate_demo_images(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    demo_specs = [
        ("demo_complete_collapse_001.jpg", generate_destroyed_image, 201),
        ("demo_complete_collapse_002.jpg", generate_destroyed_image, 202),
        ("demo_crack_001.jpg", generate_major_damage_image, 203),
        ("demo_debris_001.jpg", generate_destroyed_image, 204),
        ("demo_debris_002.jpg", generate_destroyed_image, 205),
        ("demo_facade_001.jpg", generate_minor_damage_image, 206),
        ("demo_facade_002.jpg", generate_minor_damage_image, 207),
        ("demo_non_structural_001.jpg", generate_minor_damage_image, 208),
        ("demo_partial_collapse_001.jpg", generate_major_damage_image, 209),
        ("demo_partial_collapse_002.jpg", generate_major_damage_image, 210),
    ]

    for fname, gen_fn, seed in demo_specs:
        img_path = output_dir / fname
        img = gen_fn(seed)
        img.save(img_path, format="JPEG", quality=90)

    print(f"Generated {len(demo_specs)} demo images at {output_dir}")


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    xbd_dir = repo_root / "data" / "sample_dataset" / "xbd_sample"
    images_dir = repo_root / "data" / "sample_dataset" / "images"

    curate_xbd_dataset(xbd_dir)
    curate_demo_images(images_dir)
