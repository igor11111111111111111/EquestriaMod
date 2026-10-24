r"""Culture art in the selection screen at campaign start: the card and the parallax background.

  py -3 tools/make_culture_art.py [Module folder]

The vanilla screen (Native/GUI/Prefabs/CharacterCreation/CharacterCreationCultureStage.xml) draws
four parallax layers for the selected culture — brushes Culture.Banner.Layer.1..4 with a style per
culture id and sprites CharacterCreation\Culture\<id>_1..4 (952x876, shown at 938x840) — and, in
the list on the right, a card strip CharacterCreation\Culture\<id> (541x94, transparent on the
left, where the name goes). Layer 1 is on top and moves the most; layer 4 is the backdrop and
barely moves.

Sprites are loaded into a dictionary by name, and the *SpriteData.xml files are read in module
order, so a mod sprite with a vanilla name OVERRIDES the vanilla one — prefabs and brushes need no
changes. Our category ui_eq_culture is loaded by code at the start of character creation
(EquestriaCultureArt.cs).

Sources: assets/culture/<culture id>/
  card.*      — the card (any shape; a horizontal strip around the point CARD_FOCUS is taken);
  layer_1.*   — top layer, layer_2.* — middle, layer_3.* — backdrop (three pictures);
                or layer_1..layer_4 — then the layers map one to one.
The background around the artwork is removed automatically: its level is taken from the picture's
border (it is not necessarily black), the script picks the upper bound from the picture itself, and
only what could be reached from the edges is made transparent — otherwise shadows inside the
artwork would become holes. The artwork's edge can be torn beforehand in any editor: a ragged
border stays ragged. A solid full-frame picture just gets softened edges so it does not hang on
the screen as a rectangle.

Output: Module/GUI/SpriteSheets/ui_eq_culture/ui_eq_culture_<N>.png — one sheet per culture,
        Module/GUI/SpriteParts/ui_eq_culture/<id>_*.png — parts for eyeballing,
        Module/GUI/EquestriaCultureSpriteData.xml — category, parts and sprites.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

MOD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Module")
HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.path.join(HERE, "..", "assets", "culture")
CATEGORY = "ui_eq_culture"
SUFFIXES = (".png", ".jpg", ".jpeg")

LAYER = (952, 876)          # same as the vanilla layers
CARD = (541, 94)            # same as the vanilla strip in the list
CARD_ART_WIDTH = 200        # the artwork takes the right part of the strip; the left is room for the name
CARD_FADE = (335, 440)      # from x0 to x1 opacity grows from 0 to 1
WASH_FLOOR = 0.05           # residual opacity on a solid fill — to zero
# The card's frame does not go into the strip: inner area (left, top, right, bottom) in source pixels
CARD_INSET = {"aserai": (110, 120, 660, 1265)}
# Where the main subject is on the card (fraction of the inner area's height): the strip is cut around it
CARD_FOCUS = {"aserai": 0.68}
CARD_FOCUS_DEFAULT = 0.5

# A layer that takes from its picture only what differs from another layer: for the ponies
# "background 1" is the same castle as "background 2", but with heroes on the
# balconies, and only the heroes should go to the front layer. {culture: {layer no.: sample layer no.}}
LAYER_BASE = {"empire": {1: 2}}
DIFF_TOP = 50               # a difference brighter than this is no longer redraw noise but a hero
DIFF_SPECK = 300            # a piece smaller than this is a speck
DIFF_SMALL = 2000           # a piece smaller than this and elongated is a building fragment, not a hero

KEY_SOFT = 12               # soft edge width: how much brighter than the background bound a pixel is
                            # already fully opaque (the bound itself is picked by pick_top)
KEY_FLOOR = 0.10            # opacity below this — to zero: otherwise the empty part clouds the layers below
KEY_BORDER = 60             # a border darker than this means the artwork is cut out on a dark background
FEATHER = 70                # edge softening of a solid backdrop, pixels
BLANK = (4, 4)              # transparent placeholder for a layer without a picture


def log(*a):
    print("[culture]", *a, flush=True)


def cover(img, size):
    """Fit the frame to the size without stretching: scale by the larger ratio, crop the excess evenly."""
    scale = max(size[0] / img.width, size[1] / img.height)
    w, h = round(img.width * scale), round(img.height * scale)
    img = img.resize((w, h), Image.LANCZOS)
    left, top = (w - size[0]) // 2, (h - size[1]) // 2
    return img.crop((left, top, left + size[0], top + size[1]))


def background(img):
    """Background around the artwork: its colour and brightness — the median over a 6-pixel border. It is
    not necessarily black: pictures with a torn edge are surrounded by a dark grey field."""
    a = np.asarray(img.convert("RGB"), dtype=np.int16)
    frame = np.concatenate([a[:6].reshape(-1, 3), a[-6:].reshape(-1, 3),
                            a[:, :6].reshape(-1, 3), a[:, -6:].reshape(-1, 3)])
    colour = np.median(frame, axis=0)
    return colour, float(np.median(frame.max(axis=1)))


def is_keyed(img):
    """Whether the artwork is cut out on a dark background — judged by the border along the edges."""
    return background(img)[1] < KEY_BORDER


def flood(candidates):
    """Candidate pixels reachable from the picture's edges."""
    # .copy() is required: Pillow's floodfill on an image over a numpy array silently does nothing
    mask = Image.fromarray(np.where(candidates, 255, 0).astype(np.uint8), "L").copy()
    w, h = mask.size
    seeds = [(x, y) for x in range(0, w, 16) for y in (0, h - 1)]
    seeds += [(x, y) for y in range(0, h, 16) for x in (0, w - 1)]
    for x, y in seeds:
        if mask.getpixel((x, y)) == 255:
            ImageDraw.floodfill(mask, (x, y), 128)
    return np.asarray(mask) == 128


def pick_top(mx, level):
    """Upper bound of the background: up to what brightness a pixel counts as background, not artwork.

    One number for all pictures will not do: for a cut-out on black the empty field reaches 20
    (the background is absorbed in a jump, and the artwork starts much higher), while for a backdrop
    with a torn edge the background itself is 22 and blends into the artwork smoothly. So we watch
    how the fill grows with the threshold: the largest increase is the background being absorbed;
    then we keep going while the increase is small and stop when the fill starts biting the artwork.
    """
    small = mx[::2, ::2]
    tops = list(range(int(level) + 2, int(level) + 61, 4))
    areas = [float(flood(small < t).mean()) for t in tops]
    grow = [areas[0]] + [areas[i] - areas[i - 1] for i in range(1, len(areas))]
    i = int(np.argmax(grow))                       # jump: the background got absorbed
    # after that the increase falls off — its light remnants along the edge are being eaten. As soon as
    # it goes up again, the fill has started on the artwork; stop at the previous threshold.
    while i + 1 < len(tops) and grow[i + 1] <= grow[i] * 1.15 + 0.002:
        i += 1
    return tops[i]


def key_background(img):
    """Background -> transparency. The background level is taken from the border rather than assumed
    zero: the artwork's edge was torn by hand and a dark grey field lies around it. Transparency is
    assigned ONLY where the edges could be reached from, otherwise dark spots inside the artwork
    (cracks in rocks, shadows under bodies) would become holes too. Colour on the semi-transparent
    edge is restored: it shows a mix of artwork and background, and without this a dark fringe
    remains along the outline."""
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32)
    colour, level = background(img)
    mx = rgb.max(axis=2)
    top = pick_top(mx, level)
    # The soft edge is measured FROM the background bound, not from the brightness at the border: the
    # empty field itself is uneven (in the first picture it darkens from 2 at the edge to 20 in the
    # middle), and measured from the border the whole middle of the layer got half opacity and
    # clouded what lies below it.
    log("   фон %.0f, граница фона %d" % (level, top))
    ramp = np.clip((mx - top) / KEY_SOFT, 0, 1)
    ramp = ramp * ramp * (3 - 2 * ramp)                          # smoothstep
    # the background and the whole transition band around the artwork: with margin so the soft edge fits
    zone = flood(mx < top)
    zone = np.asarray(Image.fromarray(np.where(zone, 255, 0).astype(np.uint8), "L")
                      .filter(ImageFilter.MaxFilter(9))) > 0
    alpha = np.where(zone, ramp, 1.0)
    alpha_img = Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7))
    alpha = np.asarray(alpha_img, dtype=np.float32) / 255
    alpha = np.clip((alpha - KEY_FLOOR) / (1 - KEY_FLOOR), 0, 1)
    safe = np.maximum(alpha, 0.05)[..., None]
    mix = (rgb - colour * (1 - alpha[..., None])) / safe
    rgb = np.where(alpha[..., None] < 1, np.clip(mix, 0, 255), rgb)
    rgb[alpha < 0.02] = 0
    out = np.dstack([rgb, alpha * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def feather(img):
    """Solid backdrop: the edges fade into transparency, like the painted vanilla layers."""
    w, h = img.size
    x = np.arange(w, dtype=np.float32)
    y = np.arange(h, dtype=np.float32)
    fx = np.clip(np.minimum(x, w - 1 - x) / FEATHER, 0, 1)
    fy = np.clip(np.minimum(y, h - 1 - y) / FEATHER, 0, 1)
    alpha = np.minimum(fy[:, None], fx[None, :])
    alpha = alpha * alpha * (3 - 2 * alpha)
    rgba = np.dstack([np.asarray(img.convert("RGB"), dtype=np.uint8), (alpha * 255).astype(np.uint8)])
    return Image.fromarray(rgba, "RGBA")


def pieces(mask):
    """Connected pieces of the mask, one boolean array per piece."""
    work = Image.fromarray(np.where(mask, 255, 0).astype(np.uint8), "L").copy()
    arr = np.asarray(work)
    seen = np.zeros_like(mask)
    out = []
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x] or arr[y, x] != 255:
            continue
        ImageDraw.floodfill(work, (int(x), int(y)), 128)
        arr = np.asarray(work)
        piece = arr == 128
        seen |= piece
        work = Image.fromarray(np.where(piece, 64, arr).astype(np.uint8), "L").copy()
        arr = np.asarray(work)
        out.append(piece)
        if len(out) >= 300:            # this many pieces only come from a garbage mask
            break
    return out


def only_difference(img, base):
    """Keep only what differs in the picture from the sample picture.

    Both are painted from the same castle and differ by the heroes on the balconies. The brightness
    difference gives their silhouettes, but along with them a faint outline of the castle itself
    (the two renderings still do not match pixel for pixel). So the mask is blurred and taken by
    majority: thin lines and specks disappear, large silhouettes remain.
    """
    a = np.asarray(img.convert("RGB"), dtype=np.int16)
    b = np.asarray(base.convert("RGB"), dtype=np.int16)
    raw = np.abs(a - b).max(axis=2) > DIFF_TOP
    solid = Image.fromarray(np.where(raw, 255, 0).astype(np.uint8), "L")
    solid = np.asarray(solid.filter(ImageFilter.GaussianBlur(2))) > 140
    # Fragments of the castle itself (for the ponies, the tip of the spire) differ from heroes by shape:
    # they are small and elongated, while a hero is a blob with width and height of the same order. They
    # cannot be cut off by strength of difference: the spire differs no less than Twilight does.
    keep = np.zeros_like(solid)
    for piece in pieces(solid):
        ys, xs = np.nonzero(piece)
        side = sorted((int(ys.max() - ys.min()) + 1, int(xs.max() - xs.min()) + 1))
        area = int(piece.sum())
        if area < DIFF_SPECK or (area < DIFF_SMALL and side[1] > 2.2 * side[0]):
            continue
        keep |= piece
    solid = keep
    # Keep the mask edge sharp. A soft edge does not work here: the engine multiplies colour by alpha
    # a second time, and the semi-transparent fringe around a hero turns black (checked in game
    # 2026-09-22). Dilating the mask is not allowed either — the castle would get into the fringe.
    alpha = np.where(solid, 1.0, 0.0).astype(np.float32)
    log("   героев в кадре: %.1f%% площади" % (100 * float((alpha > 0.5).mean())))
    out = np.dstack([a.astype(np.float32), alpha * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def make_layer(path, base_path=None):
    """The layer picture and a note on how its transparency was made."""
    img = Image.open(path)
    if base_path:
        base = cover(Image.open(base_path), LAYER)
        return only_difference(cover(img, LAYER), base), "только герои"
    keyed = is_keyed(img)
    img = cover(img, LAYER)
    if keyed:
        return key_background(img), "фон снят"
    return feather(img), "задник, края смягчены"


def smooth_line(values, width, part=80):
    """Smoothed per-column profile — a moving average padded with the edge values."""
    window = max(5, (width // part) | 1)
    return np.convolve(np.pad(values, window // 2, mode="edge"),
                       np.ones(window) / window, mode="valid")


def fade_dark(img):
    """A card strip on black: empty on the left, the beast on the right, a glow in between.

    No silhouette needs cutting here — the same horizontal gradient as on the other cards is wanted.
    So opacity is computed per column: an empty column has no bright pixel at all, the beast's
    columns do, and the glow between them gives a smooth transition. The artwork only increases from
    left to right, hence the running maximum.
    """
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32)
    level = background(img)[1]
    # a wider window than for the light fill: the blackness ends almost vertically at the beast, and
    # without this the artwork would enter the card as a step
    art = np.maximum.accumulate(smooth_line(np.percentile(rgb.max(axis=2), 99, axis=0), img.width, 9))
    line = np.clip((art - level - 3) / 70, 0, 1)
    line = line * line * (3 - 2 * line)
    alpha = np.broadcast_to(line[None, :], rgb.shape[:2])
    return Image.fromarray(np.dstack([rgb, alpha * 255]).astype(np.uint8), "RGBA")


def drop_wash(img):
    """Turn the white fill on the left into transparency without touching the composition.

    A card sometimes comes already assembled as a strip: the artwork on the right, a white field for
    the name on the left, and a smooth transition between them. On the in-game button that field
    would glow as a rectangle, but it should simply vanish, as with the changelings. A threshold
    cannot remove it — the transition passes through every shade of grey. So the fill is computed per
    column: in a solid-fill column even the darkest pixel is white, while where the artwork begins
    there are always dark pixels. The fill fraction only decreases from left to right, hence the
    running minimum. Then colour is restored from the mix with white — and the artwork's own dark
    background shows through in the transition.
    """
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32)
    wash = np.minimum.accumulate(smooth_line(rgb.min(axis=2).min(axis=0), img.width)) / 255
    line = np.clip((1 - wash - WASH_FLOOR) / (1 - WASH_FLOOR), 0, 1)
    alpha = np.broadcast_to(line[None, :], rgb.shape[:2])
    safe = np.maximum(alpha, 0.05)[..., None]
    mix = np.clip((rgb - 255 * (1 - alpha[..., None])) / safe, 0, 255)
    out = np.dstack([np.where(alpha[..., None] < 1, mix, rgb), alpha * 255])
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def make_card(path, focus, inset):
    """A 541x94 strip: a horizontal cut around the focus point, on the right; fades out on the left.

    If the source is already a strip of the same shape (assembled by hand), it is taken whole, and the
    light fill on the left is turned into transparency.
    """
    img = Image.open(path).convert("RGB")
    if inset:
        img = img.crop(inset)
    if abs(img.width / img.height - CARD[0] / CARD[1]) < 0.6:
        # The source is already a strip of the right shape. The fill under the name may be white or
        # black: white is removed per column, dark — like the layers' background, by a fill from the edges.
        strip = cover(img, CARD)
        return fade_dark(strip) if is_keyed(strip) else drop_wash(strip)
    scale = CARD_ART_WIDTH / img.width
    band_h = int(round(CARD[1] / scale))
    cy = int(img.height * focus)
    top = min(max(cy - band_h // 2, 0), img.height - band_h)
    band = img.crop((0, top, img.width, top + band_h)).resize((CARD_ART_WIDTH, CARD[1]), Image.LANCZOS)
    card = Image.new("RGBA", CARD, (0, 0, 0, 0))
    x0 = CARD[0] - CARD_ART_WIDTH
    card.paste(band, (x0, 0))
    a = np.asarray(card.getchannel("A"), dtype=np.float32)
    x = np.arange(CARD[0], dtype=np.float32)
    fade = np.clip((x - CARD_FADE[0]) / (CARD_FADE[1] - CARD_FADE[0]), 0, 1)
    fade = fade * fade * (3 - 2 * fade)
    card.putalpha(Image.fromarray((a * fade[None, :]).astype(np.uint8)))
    return card


def find(folder, stem):
    for s in SUFFIXES:
        p = os.path.join(folder, stem + s)
        if os.path.isfile(p):
            return p
    return None


def cultures():
    if not os.path.isdir(SOURCES):
        return []
    out = []
    for cid in sorted(os.listdir(SOURCES)):
        folder = os.path.join(SOURCES, cid)
        if not os.path.isdir(folder):
            continue
        layers = [find(folder, f"layer_{i}") for i in range(1, 5)]
        card = find(folder, "card")
        if card is None and not any(layers):
            continue
        out.append((cid, folder, card, layers))
    return out


def sheet_image(img):
    """The sheet as the engine expects it.

    Sheets WITHOUT alpha (loading screens, tools/make_loading_screen.py) are laid out by it as BGR,
    and there the channels are swapped by hand. A sheet WITH alpha needs no swap: checked in game
    2026-09-22 — with the swap the ponies' sky came out orange and Applejack blue.
    """
    return img.convert("RGBA")


def main():
    gui = os.path.join(MOD, "GUI")
    sheets = os.path.join(gui, "SpriteSheets", CATEGORY)
    parts = os.path.join(gui, "SpriteParts", CATEGORY)
    os.makedirs(sheets, exist_ok=True)
    os.makedirs(parts, exist_ok=True)
    for folder in (sheets, parts):
        for name in os.listdir(folder):
            if name.lower().endswith(".png"):
                os.remove(os.path.join(folder, name))

    sizes, part_nodes, sprite_nodes = [], [], []

    def add_part(sheet_id, name, box):
        part_nodes.append(f"""    <SpritePart>
      <SheetID>{sheet_id}</SheetID>
      <Name>{name}</Name>
      <Width>{box[2]}</Width>
      <Height>{box[3]}</Height>
      <SheetX>{box[0]}</SheetX>
      <SheetY>{box[1]}</SheetY>
      <CategoryName>{CATEGORY}</CategoryName>
    </SpritePart>""")
        sprite_nodes.append(f"""    <GenericSprite>
      <Name>{name}</Name>
      <SpritePartName>{name}</SpritePartName>
    </GenericSprite>""")

    found = cultures()
    for sheet_id, (cid, folder, card_path, layer_paths) in enumerate(found, 1):
        present = [p for p in layer_paths if p]
        # The sheet is as large as what lies on it: a culture with only a card has no reason to keep a
        # canvas for four layers in memory.
        sheet_w = LAYER[0] * 2 if present else CARD[0]
        sheet_h = LAYER[1] * 2 + CARD[1] if present else CARD[1]
        card_y = LAYER[1] * 2 if present else 0
        sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
        bases = LAYER_BASE.get(cid, {})
        base_paths = [layer_paths[bases[n] - 1] if n in bases else None for n in range(1, 5)]
        if len(present) == 3 and layer_paths[3] is None:
            # three pictures: top, middle and backdrop; the third vanilla layer stays empty
            slots = [layer_paths[0], layer_paths[1], None, layer_paths[2]]
            slot_bases = [base_paths[0], base_paths[1], None, base_paths[2]]
        else:
            slots, slot_bases = layer_paths, base_paths
        blank_box = None
        for i, (path, base_path) in enumerate(zip(slots, slot_bases), 1):
            name = f"CharacterCreation\\Culture\\{cid}_{i}"
            x, y = LAYER[0] * ((i - 1) % 2), LAYER[1] * ((i - 1) // 2)
            if path is None:
                if not present:
                    # This culture has no layer pictures at all — we write no sprites of our own, and
                    # the vanilla ones stay on screen. A blank is needed only where some layers are
                    # ours: otherwise a vanilla layer would show through in the middle of ours.
                    continue
                if blank_box is None:
                    blank_box = (CARD[0] + 8, LAYER[1] * 2, BLANK[0], BLANK[1])
                add_part(sheet_id, name, blank_box)
                log(cid, f"слой {i}: пусто")
                continue
            layer, note = make_layer(path, base_path)
            sheet.paste(layer, (x, y))
            layer.save(os.path.join(parts, f"{cid}_{i}.png"))
            add_part(sheet_id, name, (x, y, LAYER[0], LAYER[1]))
            log(cid, f"слой {i}: {os.path.basename(path)} ({note})")
        if card_path:
            card = make_card(card_path, CARD_FOCUS.get(cid, CARD_FOCUS_DEFAULT), CARD_INSET.get(cid))
            sheet.paste(card, (0, card_y))
            card.save(os.path.join(parts, f"{cid}_card.png"))
            add_part(sheet_id, f"CharacterCreation\\Culture\\{cid}", (0, card_y, CARD[0], CARD[1]))
            log(cid, "карточка:", os.path.basename(card_path))
        sheet_image(sheet).save(os.path.join(sheets, f"{CATEGORY}_{sheet_id}.png"))
        sizes.append(f'      <SpriteSheetSize ID="{sheet_id}" Width="{sheet_w}" Height="{sheet_h}" />')

    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<!-- Карточки и параллакс-фоны народностей. Собран tools/make_culture_art.py — правьте скрипт,
     не этот файл. Имена спрайтов ванильные: так они перекрывают ванильные картинки. -->
<SpriteData>
  <SpriteCategories>
    <SpriteCategory>
      <Name>{CATEGORY}</Name>
      <SpriteSheetCount>{len(found)}</SpriteSheetCount>
{chr(10).join(sizes)}
    </SpriteCategory>
  </SpriteCategories>
  <SpriteParts>
{chr(10).join(part_nodes)}
  </SpriteParts>
  <Sprites>
{chr(10).join(sprite_nodes)}
  </Sprites>
</SpriteData>
"""
    path = os.path.join(gui, "EquestriaCultureSpriteData.xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)
    log("записан", path, "— народностей", len(found), ":", ", ".join(c[0] for c in found))


if __name__ == "__main__":
    main()
