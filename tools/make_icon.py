"""Draw the Climb Studio icon: a stopwatch ring around a climbing route of holds.

uv run --no-sync python tools/make_icon.py  →  viewer/assets/icon.png, packaging/icon.icns, packaging/icon.ico
"""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
S = 4096  # drawn large, then downsampled for smooth edges


def gradient(size, top, bottom):
    image = Image.new('RGB', (1, size))
    for y in range(size):
        t = y/(size-1);image.putpixel((0, y), tuple(round(a+(b-a)*t) for a, b in zip(top, bottom)))
    return image.resize((size, size))


def icon():
    canvas = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    inset = int(S*.09);radius = int(S*.2)
    mask = Image.new('L', (S, S), 0);ImageDraw.Draw(mask).rounded_rectangle((inset, inset, S-inset, S-inset), radius, fill=255)
    shadow = Image.new('RGBA', (S, S), (0, 0, 0, 0));ImageDraw.Draw(shadow).rounded_rectangle((inset, inset+S*.015, S-inset, S-inset+S*.015), radius, fill=(8, 20, 40, 110))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(S*.02)))
    canvas.paste(gradient(S, (34, 101, 216), (20, 168, 132)).convert('RGBA'), (0, 0), mask)
    draw = ImageDraw.Draw(canvas);cx, cy, r = S/2, S*.535, S*.285;w = int(S*.045)
    # Stopwatch: ring, crown on a stem and an angled side button, all joined to the ring.
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline='white', width=w)
    draw.rectangle((cx-S*.022, cy-r-S*.07, cx+S*.022, cy-r+w*.5), fill='white')
    draw.rounded_rectangle((cx-S*.075, cy-r-S*.125, cx+S*.075, cy-r-S*.055), int(S*.02), fill='white')
    angle = math.radians(-45);inner, outer = r-w*.5, r+S*.06
    start, end = (cx+math.cos(angle)*inner, cy+math.sin(angle)*inner), (cx+math.cos(angle)*outer, cy+math.sin(angle)*outer)
    draw.line((start, end), fill='white', width=int(w*.95));draw.ellipse((end[0]-w*.48, end[1]-w*.48, end[0]+w*.48, end[1]+w*.48), fill='white')
    # Route: zig-zag line climbing through four holds, last one highlighted.
    holds = [(cx-S*.13, cy+S*.17), (cx+S*.08, cy+S*.05), (cx-S*.07, cy-S*.07), (cx+S*.11, cy-S*.17)]
    draw.line(holds, fill=(255, 255, 255, 235), width=int(S*.022), joint='curve')
    for i, (x, y) in enumerate(holds):
        size = S*(.05 if i < 3 else .062);colour = (255, 183, 77) if i == 3 else (255, 255, 255)
        draw.ellipse((x-size, y-size*.8, x+size, y+size*.8), fill=colour, outline=(16, 60, 110), width=int(S*.008))
    return canvas.resize((1024, 1024), Image.LANCZOS)


if __name__ == '__main__':
    image = icon()
    image.save(ROOT/'viewer'/'assets'/'icon.png')
    image.save(ROOT/'packaging'/'icon.icns')
    image.save(ROOT/'packaging'/'icon.ico', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print('Icon written')
