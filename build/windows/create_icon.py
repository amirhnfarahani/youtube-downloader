from PIL import Image, ImageDraw
from pathlib import Path

out = Path(__file__).resolve().parent / "youtube-purple.ico"
sizes = [256, 128, 64, 48, 32, 16]
frames = []
for size in sizes:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = max(1, size // 16)
    radius = max(3, size // 5)
    d.rounded_rectangle((pad, pad, size - pad - 1, size - pad - 1), radius=radius, fill=(124, 58, 237, 255))
    # White YouTube-style play symbol
    left = int(size * 0.39)
    top = int(size * 0.28)
    right = int(size * 0.39)
    bottom = int(size * 0.72)
    d.polygon([(left, top), (int(size * 0.70), size // 2), (right, bottom)], fill=(255, 255, 255, 255))
    frames.append(img)
frames[0].save(out, format="ICO", sizes=[(s, s) for s in sizes], append_images=frames[1:])
print(out)
