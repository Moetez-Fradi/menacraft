#!/usr/bin/env python3
"""
Generate MENACRAFT extension icons.
Produces icon16.png, icon48.png, icon128.png – a shield with checkmark on dark indigo.
Run: python3 generate_icons.py
"""
import struct, zlib, math

def make_png(size):
    # ── draw onto a flat RGBA buffer ──────────────────────────────────────────
    buf = bytearray(size * size * 4)

    def px(x, y, r, g, b, a=255):
        if 0 <= x < size and 0 <= y < size:
            i = (y * size + x) * 4
            # alpha-composite over existing
            sa = a / 255.0
            da = buf[i+3] / 255.0
            oa = sa + da * (1 - sa)
            if oa > 0:
                buf[i]   = int((r * sa + buf[i]   * da * (1 - sa)) / oa)
                buf[i+1] = int((g * sa + buf[i+1] * da * (1 - sa)) / oa)
                buf[i+2] = int((b * sa + buf[i+2] * da * (1 - sa)) / oa)
                buf[i+3] = int(oa * 255)

    def circle(cx, cy, radius, r, g, b, a=255, aa=True):
        for dy in range(-radius - 1, radius + 2):
            for dx in range(-radius - 1, radius + 2):
                d = math.sqrt(dx*dx + dy*dy)
                if aa:
                    alpha = max(0.0, min(1.0, radius - d + 0.5))
                    px(int(cx+dx), int(cy+dy), r, g, b, int(a * alpha))
                else:
                    if d <= radius:
                        px(int(cx+dx), int(cy+dy), r, g, b, a)

    def filled_circle(cx, cy, radius, r, g, b, a=255):
        ir = int(math.ceil(radius)) + 1
        for dy in range(-ir, ir + 1):
            for dx in range(-ir, ir + 1):
                d = math.sqrt(dx*dx + dy*dy)
                alpha = max(0.0, min(1.0, radius - d + 0.5))
                if alpha > 0:
                    px(int(cx+dx), int(cy+dy), r, g, b, int(a * alpha))

    def line(x0, y0, x1, y1, r, g, b, a=255, width=1):
        """Bresenham + thickness."""
        dx = abs(x1 - x0); sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0); sy = 1 if y0 < y1 else -1
        err = dx + dy
        cx, cy = x0, y0
        pts = []
        while True:
            pts.append((cx, cy))
            if cx == x1 and cy == y1: break
            e2 = 2 * err
            if e2 >= dy: err += dy; cx += sx
            if e2 <= dx: err += dx; cy += sy
        hw = width / 2
        for (px_, py_) in pts:
            filled_circle(px_, py_, hw, r, g, b, a)

    s = size
    # Background circle (dark indigo)
    filled_circle(s//2, s//2, s//2 - 1, 31, 31, 55, 255)

    # Shield body
    # Scale factor
    f = s / 128.0
    cx = s // 2
    # Shield: polygon approximation
    # Top: wide, bottom: pointed
    sw = int(50 * f)   # half-width at top
    sh = int(60 * f)   # half-height
    ty = int(s * 0.18) # top y
    by = int(s * 0.88) # bottom y

    # Fill shield with indigo
    for row in range(ty, by + 1):
        t = (row - ty) / max(by - ty, 1)
        # Width tapers to 0 at bottom
        taper = 1.0 - max(0, t - 0.55) * 2.2
        taper = max(0, min(1, taper))
        w = int(sw * taper)
        for col in range(cx - w, cx + w + 1):
            # Soft edge
            edge = min(col - (cx - w), (cx + w) - col)
            aa_alpha = min(1.0, edge + 0.5) if edge < 1 else 1.0
            px(col, row, 99, 102, 241, int(220 * aa_alpha))

    # Shield outline
    outline_pts = []
    for row in range(ty, by + 1):
        t = (row - ty) / max(by - ty, 1)
        taper = 1.0 - max(0, t - 0.55) * 2.2
        taper = max(0, min(1, taper))
        w = int(sw * taper)
        outline_pts.append((cx - w, row))
        outline_pts.append((cx + w, row))

    # Draw outline by drawing the boundary lines
    stroke_w = max(1, int(2 * f))

    # Left side
    prev = None
    for row in range(ty, by + 1):
        t = (row - ty) / max(by - ty, 1)
        taper = 1.0 - max(0, t - 0.55) * 2.2
        taper = max(0, min(1, taper))
        w = int(sw * taper)
        lx = cx - w
        if prev:
            line(prev[0], prev[1], lx, row, 129, 140, 248, 255, stroke_w)
        prev = (lx, row)
    prev = None
    for row in range(ty, by + 1):
        t = (row - ty) / max(by - ty, 1)
        taper = 1.0 - max(0, t - 0.55) * 2.2
        taper = max(0, min(1, taper))
        w = int(sw * taper)
        rx = cx + w
        if prev:
            line(prev[0], prev[1], rx, row, 129, 140, 248, 255, stroke_w)
        prev = (rx, row)
    # Top bar
    line(cx - sw, ty, cx + sw, ty, 129, 140, 248, 255, stroke_w)

    # Checkmark (white)
    cw = max(1, int(1.8 * f))
    # left leg: (35%,55%) → (48%,70%)
    lx1 = int(s * 0.36); ly1 = int(s * 0.52)
    lx2 = int(s * 0.48); ly2 = int(s * 0.66)
    # right leg: (48%,70%) → (68%,42%)
    rx1 = lx2; ry1 = ly2
    rx2 = int(s * 0.67); ry2 = int(s * 0.40)
    line(lx1, ly1, lx2, ly2, 255, 255, 255, 245, cw)
    line(rx1, ry1, rx2, ry2, 255, 255, 255, 245, cw)

    # ── encode as PNG ─────────────────────────────────────────────────────────
    raw = b''
    for row in range(size):
        raw += b'\x00'  # filter type: None
        for col in range(size):
            i = (row * size + col) * 4
            raw += bytes(buf[i:i+4])

    def chunk(name, data):
        c = zlib.crc32(name + data) & 0xffffffff
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', c)

    ihdr_data = struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)
    idat_data = zlib.compress(raw, 9)

    png = (
        b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', ihdr_data)
        + chunk(b'IDAT', idat_data)
        + chunk(b'IEND', b'')
    )
    return png

if __name__ == '__main__':
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for size in (16, 48, 128):
        path = os.path.join(script_dir, f'icon{size}.png')
        with open(path, 'wb') as f:
            f.write(make_png(size))
        print(f'  ✓  icon{size}.png')
