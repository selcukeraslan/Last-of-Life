"""PWA ikonlarını (static/icons/*.png) üretir; bağımlılık yok (saf Python). Çalıştırma:
    python scripts/make_pwa_icons.py
Tasarım: koyu zemin (#0f1419) üzerinde yeşil (#2fbf71) top motifi. Maskable ikonlarda içerik,
güvenli bölge (merkezden %40 yarıçap) içinde kalır; tüm ikonlar tam dolu (şeffaf piksel yok)."""
import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "static" / "icons"
BG, FG = (15, 20, 25), (47, 191, 113)
SS = 3  # piksel başına SS×SS alt örnek (kenar yumuşatma)


def _png(path: Path, size: int, rows: list[bytes]):
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    raw = b"".join(b"\x00" + r for r in rows)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _in_convex(px, py, pts):
    sign = [(bx - ax) * (py - ay) - (by - ay) * (px - ax) for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1])]
    return all(s >= 0 for s in sign) or all(s <= 0 for s in sign)


def render(size: int, radius: float) -> list[bytes]:
    """radius: top yarıçapı (görsel boyutun oranı). Koordinatlar [-0.5, 0.5] normalize."""
    pent_r, spoke_w = radius * 0.38, 0.018
    verts = [(pent_r * math.sin(2 * math.pi * k / 5), -pent_r * math.cos(2 * math.pi * k / 5)) for k in range(5)]
    rim = [(radius * 0.97 * math.sin(2 * math.pi * k / 5), -radius * 0.97 * math.cos(2 * math.pi * k / 5)) for k in range(5)]

    def inside_fg(x, y):
        if math.hypot(x, y) > radius:
            return False
        if _in_convex(x, y, verts):
            return False
        return not any(_seg_dist(x, y, *v, *r) < spoke_w for v, r in zip(verts, rim))

    rows = []
    for j in range(size):
        row = bytearray()
        for i in range(size):
            hits = sum(inside_fg((i + (a + .5) / SS) / size - .5, (j + (b + .5) / SS) / size - .5)
                       for a in range(SS) for b in range(SS))
            f = hits / (SS * SS)
            row += bytes(round(BG[c] + (FG[c] - BG[c]) * f) for c in range(3))
        rows.append(bytes(row))
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = {  # dosya: (boyut, top yarıçapı)
        "icon-192.png": (192, 0.40), "icon-512.png": (512, 0.40),
        "icon-maskable-192.png": (192, 0.32), "icon-maskable-512.png": (512, 0.32),
        "apple-touch-icon.png": (180, 0.36),
    }
    for name, (size, radius) in jobs.items():
        _png(OUT / name, size, render(size, radius))
        print("yazıldı", OUT / name)


if __name__ == "__main__":
    main()
