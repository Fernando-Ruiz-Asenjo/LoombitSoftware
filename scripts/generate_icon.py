"""
Genera loombit_operator/assets/loombit.ico

Diseño: 3 nodos en forma de L conectados por fibras con glow.
Representa el loom (telar) y la inicial L de Loombit.

Uso:
    python scripts/generate_icon.py
"""
from __future__ import annotations

import math
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    raise SystemExit("Instala Pillow: pip install pillow")

OUT_PATH = Path(__file__).parent.parent / "loombit_operator" / "assets" / "loombit.ico"
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)


# ── Paleta ────────────────────────────────────────────────────────────────────
BG       = (11, 17, 27)       # fondo navy profundo
TEAL     = (0, 210, 175)      # #00D2AF  — hilo principal
TEAL_DIM = (0, 120, 100)      # hilo más oscuro para glow exterior
WHITE    = (230, 255, 250)    # núcleo del nodo


def _draw_glow_line(
    draw: ImageDraw.ImageDraw,
    p1: tuple[int, int],
    p2: tuple[int, int],
    color: tuple[int, int, int],
    width: int = 3,
    layers: int = 5,
) -> None:
    """Dibuja una línea con halo gaussiano manual (capas de anchura creciente, alpha decreciente)."""
    for i in range(layers, 0, -1):
        alpha = int(255 * (0.12 if i > 1 else 0.9))
        w = width + (i - 1) * 4
        r, g, b = color
        draw.line([p1, p2], fill=(r, g, b, alpha), width=w)


def _draw_glow_circle(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    radius: int,
    color: tuple[int, int, int],
    layers: int = 5,
) -> None:
    cx, cy = center
    for i in range(layers, 0, -1):
        alpha = int(255 * (0.10 if i > 1 else 0.95))
        r_i = radius + (i - 1) * 5
        r, g, b = color
        draw.ellipse(
            [cx - r_i, cy - r_i, cx + r_i, cy + r_i],
            fill=(r, g, b, alpha),
        )


def _make_frame(size: int) -> Image.Image:
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # Fondo con esquinas redondeadas
    bg_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg_layer)
    r_corner = max(6, s // 5)
    bg_draw.rounded_rectangle([0, 0, s - 1, s - 1], radius=r_corner, fill=BG + (255,))
    img = Image.alpha_composite(img, bg_layer)

    # Nodos de la L: top, corner, right
    pad = int(s * 0.22)
    node_top    = (int(s * 0.36), pad)
    node_corner = (int(s * 0.36), s - pad)
    node_right  = (s - pad, s - pad)

    # Radio de nodos
    r_big   = max(4, s // 16)  # nodo esquina (pivote de la L)
    r_small = max(3, s // 22)  # nodos extremos

    # ── Líneas con glow ──────────────────────────────────────────────────────
    line_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ld = ImageDraw.Draw(line_layer)

    lw = max(2, s // 60)
    _draw_glow_line(ld, node_top, node_corner, TEAL, width=lw, layers=6)
    _draw_glow_line(ld, node_corner, node_right, TEAL, width=lw, layers=6)

    # Hilo diagonal tenue (fondo del telar)
    mid_top   = ((node_top[0] + node_right[0]) // 2, (node_top[1] + node_right[1]) // 2)
    _draw_glow_line(ld, node_top, node_right, TEAL_DIM, width=max(1, lw // 2), layers=3)

    img = Image.alpha_composite(img, line_layer)

    # ── Nodos ────────────────────────────────────────────────────────────────
    node_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    nd = ImageDraw.Draw(node_layer)

    for node, radius in [(node_top, r_small), (node_right, r_small), (node_corner, r_big)]:
        _draw_glow_circle(nd, node, radius, TEAL, layers=5)
        # Núcleo blanco
        cx, cy = node
        rw = max(1, radius // 2)
        nd.ellipse([cx - rw, cy - rw, cx + rw, cy + rw], fill=WHITE + (255,))

    img = Image.alpha_composite(img, node_layer)

    return img


def main() -> None:
    sizes = [256, 128, 64, 48, 32, 16]
    frames = [_make_frame(s) for s in sizes]

    # Guardar como ICO multi-resolución
    frames[0].save(
        OUT_PATH,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )
    print(f"Icono guardado: {OUT_PATH}")

    # Preview PNG para verificar visualmente
    preview = OUT_PATH.with_suffix(".png")
    frames[0].save(preview)
    print(f"Preview PNG: {preview}")


if __name__ == "__main__":
    main()
