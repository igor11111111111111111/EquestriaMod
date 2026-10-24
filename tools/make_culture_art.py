r"""Оформление народностей в окне выбора при старте кампании: карточка и параллакс-фон.

  py -3 tools/make_culture_art.py [папка Module]

Ванильный экран (Native/GUI/Prefabs/CharacterCreation/CharacterCreationCultureStage.xml) рисует
для выбранной культуры четыре слоя параллакса — кисти Culture.Banner.Layer.1..4 со стилем по id
культуры и спрайтами CharacterCreation\Culture\<id>_1..4 (952x876, показ 938x840), — а в списке
справа полосу-карточку CharacterCreation\Culture\<id> (541x94, слева прозрачная — там название).
Слой 1 сверху и двигается сильнее всего, слой 4 — задник, почти стоит.

Спрайты грузятся в словарь по имени, а файлы *SpriteData.xml читаются в порядке модулей, поэтому
спрайт мода с ванильным именем ПЕРЕКРЫВАЕТ ванильный — префабы и кисти трогать не нужно. Наша
категория ui_eq_culture подгружается кодом в начале создания персонажа (EquestriaCultureArt.cs).

Исходники: assets/culture/<id культуры>/
  card.*      — карточка (любой формы; берётся горизонтальная полоса вокруг точки CARD_FOCUS);
  layer_1.*   — верхний слой, layer_2.* — средний, layer_3.* — задник (три картинки);
                либо layer_1..layer_4 — тогда слои ложатся один к одному.
Фон вокруг рисунка снимается сам: его уровень берётся у рамки картинки (он не обязательно
чёрный), верхнюю границу скрипт подбирает по самой картинке, а прозрачным делается только то,
до чего удалось дойти от краёв, — иначе тени внутри рисунка стали бы дырами. Край рисунка можно
оборвать заранее в любом редакторе: рваная граница так и останется рваной. У сплошной картинки
во весь кадр края просто смягчаются, чтобы она не висела на экране прямоугольником.

Выход: Module/GUI/SpriteSheets/ui_eq_culture/ui_eq_culture_<N>.png — лист на культуру,
       Module/GUI/SpriteParts/ui_eq_culture/<id>_*.png — части для просмотра глазами,
       Module/GUI/EquestriaCultureSpriteData.xml — категория, части и спрайты.
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

LAYER = (952, 876)          # как у ванильных слоёв
CARD = (541, 94)            # как у ванильной полосы в списке
CARD_ART_WIDTH = 200        # рисунок занимает правую часть полосы, слева — место под название
CARD_FADE = (335, 440)      # от x0 до x1 прозрачность растёт от 0 до 1
WASH_FLOOR = 0.05           # остаток непрозрачности на сплошной заливке — в ноль
# Рамка карточки в полосу не идёт: внутренняя область (left, top, right, bottom) в пикселях исходника
CARD_INSET = {"aserai": (110, 120, 660, 1265)}
# Где на карточке главное (доля высоты внутренней области): вокруг этой точки вырезается полоса
CARD_FOCUS = {"aserai": 0.68}
CARD_FOCUS_DEFAULT = 0.5

# Слой, который берёт от своей картинки только то, чем она отличается от другого слоя: у пони
# «фон 1» — тот же замок, что и «фон 2», но с героями на балконах, и передним слоем должны уйти
# одни герои. {культура: {номер слоя: номер слоя-образца}}
LAYER_BASE = {"empire": {1: 2}}
DIFF_TOP = 50               # отличие ярче этого — уже не шум перерисовки, а герой
DIFF_SPECK = 300            # кусок меньше этого — крапина
DIFF_SMALL = 2000           # кусок меньше этого и вытянутый — обломок постройки, не герой

KEY_SOFT = 12               # ширина мягкого края: насколько ярче границы фона пиксель уже
                            # полностью непрозрачен (саму границу подбирает pick_top)
KEY_FLOOR = 0.10            # прозрачность ниже — в ноль: иначе пустая часть слоя мутит те, что под ней
KEY_BORDER = 60             # рамка темнее этого — рисунок вырезан на тёмном фоне
FEATHER = 70                # смягчение краёв у сплошного задника, пикселей
BLANK = (4, 4)              # прозрачная заглушка для слоя без картинки


def log(*a):
    print("[culture]", *a, flush=True)


def cover(img, size):
    """Кадр под размер без растяжения: масштаб по большему, лишнее срезается поровну."""
    scale = max(size[0] / img.width, size[1] / img.height)
    w, h = round(img.width * scale), round(img.height * scale)
    img = img.resize((w, h), Image.LANCZOS)
    left, top = (w - size[0]) // 2, (h - size[1]) // 2
    return img.crop((left, top, left + size[0], top + size[1]))


def background(img):
    """Фон вокруг рисунка: его цвет и яркость — медиана по рамке в 6 пикселей. Он не обязательно
    чёрный: у картинок с оборванным краем вокруг остаётся тёмно-серое поле."""
    a = np.asarray(img.convert("RGB"), dtype=np.int16)
    frame = np.concatenate([a[:6].reshape(-1, 3), a[-6:].reshape(-1, 3),
                            a[:, :6].reshape(-1, 3), a[:, -6:].reshape(-1, 3)])
    colour = np.median(frame, axis=0)
    return colour, float(np.median(frame.max(axis=1)))


def is_keyed(img):
    """Вырезан ли рисунок на тёмном фоне — смотрим рамку по краям картинки."""
    return background(img)[1] < KEY_BORDER


def flood(candidates):
    """Пиксели-кандидаты, до которых можно дойти от краёв картинки."""
    # .copy() обязателен: заливка Pillow на картинке поверх numpy-массива молча ничего не делает
    mask = Image.fromarray(np.where(candidates, 255, 0).astype(np.uint8), "L").copy()
    w, h = mask.size
    seeds = [(x, y) for x in range(0, w, 16) for y in (0, h - 1)]
    seeds += [(x, y) for y in range(0, h, 16) for x in (0, w - 1)]
    for x, y in seeds:
        if mask.getpixel((x, y)) == 255:
            ImageDraw.floodfill(mask, (x, y), 128)
    return np.asarray(mask) == 128


def pick_top(mx, level):
    """Верхняя граница фона: до какой яркости считать пиксель фоном, а не рисунком.

    Одним числом для всех картинок не обойтись: у выреза на чёрном пустое поле доходит до 20
    (фон впитывается скачком, а рисунок начинается много выше), а у задника с оборванным краем
    фон сам по себе 22 и переходит в рисунок плавно. Поэтому смотрим, как растёт заливка с
    порогом: самый большой прирост — это и есть впитывание фона, а дальше идём, пока прирост
    мал, и останавливаемся, когда заливка начинает откусывать рисунок.
    """
    small = mx[::2, ::2]
    tops = list(range(int(level) + 2, int(level) + 61, 4))
    areas = [float(flood(small < t).mean()) for t in tops]
    grow = [areas[0]] + [areas[i] - areas[i - 1] for i in range(1, len(areas))]
    i = int(np.argmax(grow))                       # скачок: впитался фон
    # дальше прирост спадает — это доедаются его светлые остатки по краю. Как только он снова
    # пошёл вверх, заливка взялась за рисунок; останавливаемся на предыдущем пороге.
    while i + 1 < len(tops) and grow[i + 1] <= grow[i] * 1.15 + 0.002:
        i += 1
    return tops[i]


def key_background(img):
    """Фон -> прозрачность. Уровень фона берётся у рамки, а не считается нулём: край рисунка
    оборван вручную и вокруг лежит тёмно-серое поле. Прозрачность назначается ТОЛЬКО там, куда
    удалось дойти от краёв картинки, иначе тёмные места внутри рисунка (щели в скалах, тени под
    телами) тоже стали бы дырами. Цвет на полупрозрачном крае восстанавливается: видно смесь
    рисунка с фоном, и без этого по контуру остаётся тёмная кайма."""
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32)
    colour, level = background(img)
    mx = rgb.max(axis=2)
    top = pick_top(mx, level)
    # Мягкий край отсчитывается ОТ границы фона, а не от яркости у рамки: пустое поле само по себе
    # неровное (у первой картинки оно темнеет от 2 у края до 20 в середине), и от рамки вся
    # середина слоя получала половинную непрозрачность и мутила то, что под ней.
    log("   фон %.0f, граница фона %d" % (level, top))
    ramp = np.clip((mx - top) / KEY_SOFT, 0, 1)
    ramp = ramp * ramp * (3 - 2 * ramp)                          # smoothstep
    # фон и вся переходная полоса вокруг рисунка: с запасом, чтобы мягкий край попал целиком
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
    """Сплошной задник: края уходят в прозрачность, как у нарисованных ванильных слоёв."""
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
    """Связные куски маски, по одному булеву массиву на кусок."""
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
        if len(out) >= 300:            # столько кусков бывает только от мусорной маски
            break
    return out


def only_difference(img, base):
    """Оставить от картинки только то, чем она отличается от картинки-образца.

    Обе нарисованы с одного замка, различаются героями на балконах. Разница по яркости даёт их
    силуэты, но вместе с ними — слабый контур самого замка (две отрисовки всё же не совпадают
    пиксель в пиксель). Поэтому маска размывается и берётся по большинству: тонкие линии и
    крапины пропадают, крупные силуэты остаются.
    """
    a = np.asarray(img.convert("RGB"), dtype=np.int16)
    b = np.asarray(base.convert("RGB"), dtype=np.int16)
    raw = np.abs(a - b).max(axis=2) > DIFF_TOP
    solid = Image.fromarray(np.where(raw, 255, 0).astype(np.uint8), "L")
    solid = np.asarray(solid.filter(ImageFilter.GaussianBlur(2))) > 140
    # Осколки самого замка (у пони это верхушка шпиля) отличаются от героев формой: они мелкие и
    # вытянутые, а герой — пятно, у которого ширина и высота одного порядка. По силе отличия их не
    # отсечь: шпиль отличается не слабее, чем Твайлайт.
    keep = np.zeros_like(solid)
    for piece in pieces(solid):
        ys, xs = np.nonzero(piece)
        side = sorted((int(ys.max() - ys.min()) + 1, int(xs.max() - xs.min()) + 1))
        area = int(piece.sum())
        if area < DIFF_SPECK or (area < DIFF_SMALL and side[1] > 2.2 * side[0]):
            continue
        keep |= piece
    solid = keep
    # Край маски держим резким. Мягкий край здесь не годится: движок домножает цвет на альфу
    # второй раз, и полупрозрачная кайма вокруг героя чернеет (проверено в игре 2026-09-22).
    # Расширять маску тоже нельзя — в кайму попадал бы замок.
    alpha = np.where(solid, 1.0, 0.0).astype(np.float32)
    log("   героев в кадре: %.1f%% площади" % (100 * float((alpha > 0.5).mean())))
    out = np.dstack([a.astype(np.float32), alpha * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def make_layer(path, base_path=None):
    """Картинка слоя и пояснение, как из неё сделали прозрачность."""
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
    """Сглаженный профиль по столбцам — скользящее среднее с опорой на края."""
    window = max(5, (width // part) | 1)
    return np.convolve(np.pad(values, window // 2, mode="edge"),
                       np.ones(window) / window, mode="valid")


def fade_dark(img):
    """Полоса-карточка на чёрном: слева пусто, справа зверь, между ними подсветка.

    Силуэт здесь вырезать не надо — нужна та же горизонтальная растяжка, что у остальных
    карточек. Поэтому прозрачность считается по столбцам: в пустом столбце нет ни одного светлого
    пикселя, у зверя они есть, а подсветка между ними даёт плавный переход. Рисунок слева направо
    только прибывает, отсюда накопленный максимум.
    """
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32)
    level = background(img)[1]
    # окно шире, чем у светлой заливки: чернота обрывается у зверя почти отвесно, и без этого
    # рисунок въезжал бы в карточку ступенькой
    art = np.maximum.accumulate(smooth_line(np.percentile(rgb.max(axis=2), 99, axis=0), img.width, 9))
    line = np.clip((art - level - 3) / 70, 0, 1)
    line = line * line * (3 - 2 * line)
    alpha = np.broadcast_to(line[None, :], rgb.shape[:2])
    return Image.fromarray(np.dstack([rgb, alpha * 255]).astype(np.uint8), "RGBA")


def drop_wash(img):
    """Белую заливку слева — в прозрачность, не трогая композицию.

    Карточка бывает уже собрана полосой: рисунок справа, а слева белое поле под название, и между
    ними плавный переход. На кнопке в игре это поле светилось бы прямоугольником, а нужно, чтобы
    оно просто исчезло, как у чейнджлингов. Порогом такое не убрать — переход идёт через все
    оттенки серого. Поэтому заливка считается по столбцам: в столбце сплошной заливки даже самый
    тёмный пиксель белый, а там, где начался рисунок, тёмные пиксели есть всегда. Доля заливки
    слева направо только убывает, отсюда и накопленный минимум. Дальше цвет восстанавливается из
    смеси с белым — и в переходе проступает тёмный фон самого рисунка.
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
    """Полоса 541x94: горизонтальный вырез вокруг точки focus, справа; слева растворяется.

    Если исходник уже полоса той же формы (его собрали руками), он берётся целиком, а светлая
    заливка слева переводится в прозрачность.
    """
    img = Image.open(path).convert("RGB")
    if inset:
        img = img.crop(inset)
    if abs(img.width / img.height - CARD[0] / CARD[1]) < 0.6:
        # Исходник уже полоса нужной формы. Заливка под название бывает и белой, и чёрной: белую
        # снимаем по столбцам, тёмную — так же, как фон у слоёв, заливкой от краёв.
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
    """Лист как его ждёт движок.

    Листы БЕЗ альфы (загрузочные экраны, tools/make_loading_screen.py) он раскладывает как BGR, и
    там каналы переставляются вручную. Листу С альфой перестановка не нужна: проверено в игре
    2026-09-22 — с перестановкой небо у пони выходило оранжевым, а Эплджек синей.
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
        # Лист размером с то, что на нём лежит: у народности с одной карточкой незачем держать в
        # памяти полотно под четыре слоя.
        sheet_w = LAYER[0] * 2 if present else CARD[0]
        sheet_h = LAYER[1] * 2 + CARD[1] if present else CARD[1]
        card_y = LAYER[1] * 2 if present else 0
        sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
        bases = LAYER_BASE.get(cid, {})
        base_paths = [layer_paths[bases[n] - 1] if n in bases else None for n in range(1, 5)]
        if len(present) == 3 and layer_paths[3] is None:
            # три картинки: верх, середина и задник; третий ванильный слой остаётся пустым
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
                    # Картинок слоёв у этой народности нет вовсе — своих спрайтов не пишем, и на
                    # экране остаются ванильные. Пустышка нужна только там, где часть слоёв наша:
                    # иначе ванильный слой проступил бы посреди наших.
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
