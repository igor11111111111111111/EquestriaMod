"""Loading screen images of the mod.

  py -3 tools/make_loading_screen.py [Module folder]

The game takes loading images from a sprite category: GauntletDefaultLoadingWindowManager loads the
category and picks a part by number from 1 to the number of sheets. Adding parts to the vanilla
category is pointless — the game takes the sheet count from it too, so the mod has ITS OWN category,
and the image name is substituted by src/EquestriaLoadingScreen.cs, which also picks a random one. Files:
  Module/GUI/EquestriaSpriteData.xml                          — category, sheets and parts;
  Module/GUI/SpriteSheets/ui_eq_loading/ui_eq_loading_<N>.png — sheets (one image per sheet);
  Module/GUI/SpriteParts/ui_eq_loading/<name>.png             — part sources.

To add an image — put the file into assets/loading (png, jpg or jpeg) and run the script again.
The order is by file name, so the names are numbered: screen_01, screen_02, ... The image is fitted
to 1920x1080 by frame: scaled by the smaller side with the excess cropped, so nothing is stretched.
If the folder is empty, a temporary placeholder is drawn.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

MOD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Module")
HERE = os.path.dirname(os.path.abspath(__file__))
READY = os.path.join(HERE, "..", "assets", "loading")
SIZE = (1920, 1080)
CATEGORY = "ui_eq_loading"
PART = "eq_loading_"       # a number is appended to the name: eq_loading_01, eq_loading_02, ...
SUFFIXES = (".png", ".jpg", ".jpeg")
FONT = r"C:\Windows\Fonts\georgiab.ttf"


def log(*a):
    print("[loading]", *a, flush=True)


def placeholder():
    """Temporary splash: dark blue background with rays, the mod name and a caption."""
    img = Image.new("RGB", SIZE, (10, 14, 22))
    draw = ImageDraw.Draw(img)
    for y in range(SIZE[1]):  # vertical gradient
        k = y / SIZE[1]
        draw.line([(0, y), (SIZE[0], y)], fill=(int(10 + 26 * k), int(14 + 30 * k), int(24 + 44 * k)))
    cx, cy = SIZE[0] // 2, int(SIZE[1] * 0.42)
    for i in range(36):  # soft glow in the centre
        r = 520 - i * 14
        c = int(26 + i * 1.6)
        draw.ellipse([cx - r, cy - r // 2, cx + r, cy + r // 2], outline=(c, c + 8, c + 18), width=3)
    title = ImageFont.truetype(FONT, 118)
    sub = ImageFont.truetype(FONT, 52)
    note = ImageFont.truetype(FONT, 34)
    for text, font, y, color in (("Equestria: Fall of Harmony", title, cy - 110, (236, 226, 246)),
                                 ("мод для Mount & Blade II: Bannerlord", sub, cy + 70, (150, 190, 215)),
                                 # below is only the game logo, so the caption is kept above it
                                 ("временная заставка — заменить своей картинкой", note, cy + 210, (110, 125, 145))):
        w = draw.textlength(text, font=font)
        draw.text(((SIZE[0] - w) / 2 + 3, y + 3), text, font=font, fill=(0, 0, 0))
        draw.text(((SIZE[0] - w) / 2, y), text, font=font, fill=color)
    return img


def fit(img):
    """Framing to 1920x1080: scale "to cover", the excess is cropped equally from the edges.

    No stretching — our images have a slightly wider aspect than the screen, and faces would distort.
    """
    scale = max(SIZE[0] / img.width, SIZE[1] / img.height)
    w, h = round(img.width * scale), round(img.height * scale)
    img = img.resize((w, h), Image.LANCZOS)
    left, top = (w - SIZE[0]) // 2, (h - SIZE[1]) // 2
    return img.crop((left, top, left + SIZE[0], top + SIZE[1]))


def sources():
    if not os.path.isdir(READY):
        return []
    return [os.path.join(READY, n) for n in sorted(os.listdir(READY))
            if n.lower().endswith(SUFFIXES)]


def main():
    gui = os.path.join(MOD, "GUI")
    sheets = os.path.join(gui, "SpriteSheets", CATEGORY)
    parts = os.path.join(gui, "SpriteParts", CATEGORY)
    os.makedirs(sheets, exist_ok=True)
    os.makedirs(parts, exist_ok=True)

    files = sources()
    images = [fit(Image.open(p).convert("RGB")) for p in files]
    if images:
        for p in files:
            log("взята картинка", os.path.basename(p))
    else:
        images = [placeholder()]
        log("картинок нет — нарисована временная заставка")

    # Remove old sheets and parts: otherwise after an image is deleted its sheet would stay around
    for folder in (sheets, parts):
        for name in os.listdir(folder):
            if name.lower().endswith(".png"):
                os.remove(os.path.join(folder, name))

    names = []
    for i, img in enumerate(images, 1):
        part = f"{PART}{i:02d}"
        names.append(part)
        img.save(os.path.join(parts, part + ".png"))
        # The sheet is read by the engine (Texture.LoadTextureFromPath), which lays the bytes out as BGR:
        # if a regular RGB is written, red and blue are swapped in game. So we write with the channels
        # swapped. Each image has its own sheet — that way their number is not limited.
        r, g, b = img.split()
        Image.merge("RGB", (b, g, r)).save(os.path.join(sheets, f"{CATEGORY}_{i}.png"))

    sizes = "\n".join(f'      <SpriteSheetSize ID="{i}" Width="{SIZE[0]}" Height="{SIZE[1]}" />'
                      for i in range(1, len(names) + 1))
    part_nodes = "\n".join(f"""    <SpritePart>
      <SheetID>{i}</SheetID>
      <Name>{name}</Name>
      <Width>{SIZE[0]}</Width>
      <Height>{SIZE[1]}</Height>
      <SheetX>0</SheetX>
      <SheetY>0</SheetY>
      <CategoryName>{CATEGORY}</CategoryName>
    </SpritePart>""" for i, name in enumerate(names, 1))
    sprite_nodes = "\n".join(f"""    <GenericSprite>
      <Name>{name}</Name>
      <SpritePartName>{name}</SpritePartName>
    </GenericSprite>""" for name in names)

    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<!-- Спрайты интерфейса мода. Собран tools/make_loading_screen.py — правьте скрипт, не этот файл. -->
<SpriteData>
  <SpriteCategories>
    <SpriteCategory>
      <Name>{CATEGORY}</Name>
      <SpriteSheetCount>{len(names)}</SpriteSheetCount>
{sizes}
    </SpriteCategory>
  </SpriteCategories>
  <SpriteParts>
{part_nodes}
  </SpriteParts>
  <!-- Без записи в <Sprites> движок не находит картинку по имени и показывает ванильную.
       Комментарии ВНУТРИ <Sprites> ставить нельзя: разбор идёт по всем узлам подряд и спотыкается
       о комментарий, теряя весь список спрайтов (проверено 2026-09-18). -->
  <Sprites>
{sprite_nodes}
  </Sprites>
</SpriteData>
"""
    path = os.path.join(gui, "EquestriaSpriteData.xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)
    log("записан", path, f"— картинок {len(names)}")


if __name__ == "__main__":
    main()
