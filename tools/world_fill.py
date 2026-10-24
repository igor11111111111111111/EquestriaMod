# -*- coding: utf-8 -*-
"""Дополнение держав до ванильной плотности: кланы, лорды и их семьи сверх написанных руками.

В ванили на державу приходится 8–11 знатных кланов и по 5 лордов на клан; у нас руками написано
по 3–7 кланов и по 3 лорда. Мало отрядов на карте, вялые войны, а гибель пары лордов стирает клан.
Здесь к каждой державе дописываются кланы и лорды с именами из пулов культуры:
  - кланов в державе становится max(MIN_CLANS, крепостей - 6): у 15 крепостей — 9 кланов;
  - в написанном руками клане взрослых доводится до ADULTS: добавляются родичи;
  - дописанный клан — глава, супруг(а), брат и сестра главы, один-два жеребёнка четы;
  - потом всем дописанным дают семьи: родителей (большей частью уже покойных — причина смерти
    в описании, как в ванили: «пал в бою», «умер от старости»), супругов и детей.
Канонные герои не трогаются: ни браков, ни детей им не выдумываем (у Селестии или Рэйнбоу Дэш
это спорило бы с лором), только родителей — и то не правителям и не старикам. Всё детерминировано
(seed), пересборка даёт тот же мир.

Описание героя здесь — пара (русский, английский): собирается из шаблона с именами, и словарю
tools/lang_words.py такое предложение не перевести, поэтому английский складывается тут же.
"""
import random

import lang
from world_data import NAMES

SEED = 20260919
MIN_CLANS = 8
ADULTS = 4            # взрослых лордов в клане, не меньше
ADULT_AGE = 18
DEAD_PARENT = 0.7     # доля покойных среди дописанных родителей
SPOUSE_CHANCE = 0.55  # у дописанного взрослого без пары

# Как называется клан у культуры: (слово перед именем, откуда имя)
CLAN_STYLE = {
    # У оленей имя — «имя + родовое прозвище», поэтому дом зовётся по прозвищу: Дом Йельцека
    "empire": ("Дом", "pair"), "battania": ("Дом", "pair"), "nord": ("Дом", "surname"),
    "vlandia": ("Род", "surname"), "sturgia": ("Клан", "given"), "khuzait": ("Клан", "given"),
    "aserai": ("Улей", "given"),
}

# Кто такие в этой культуре: (мужчина, женщина, дитя) — для описаний
FOLK = {
    "empire": ("пони", "пони", "жеребёнок", "pony", "mare", "foal"),
    "battania": ("гиппогриф", "гиппогрифка", "птенец", "hippogriff", "hippogriff", "fledgling"),
    "nord": ("олень", "олениха", "оленёнок", "stag", "doe", "fawn"),
    "vlandia": ("грифон", "грифонша", "птенец", "gryphon", "gryphon", "fledgling"),
    "sturgia": ("дракон", "драконица", "дракончик", "dragon", "dragoness", "young dragon"),
    "khuzait": ("як", "якесса", "ячонок", "yak", "yak", "yak calf"),
    "aserai": ("чейнджлинг", "чейнджлинг", "личинка", "changeling", "changeling", "grub"),
}

# Причины смерти: (для него, для неё, английский). {K} — название державы.
CAUSES = [
    ("Погиб в бою под знамёнами державы «{K}».", "Погибла в бою под знамёнами державы «{K}».",
     "Fell in battle under the banners of {K}."),
    ("Умер от лихорадки.", "Умерла от лихорадки.", "Died of a fever."),
    ("Убит разбойниками на дороге.", "Убита разбойниками на дороге.", "Killed by bandits on the road."),
    ("Погиб при осаде.", "Погибла при осаде.", "Died in a siege."),
]
OLD_AGE = ("Умер от старости.", "Умерла от старости.", "Died of old age.")
CHILDBIRTH = ("", "Умерла при родах.", "Died in childbirth.")
CULTURE_CAUSE = {
    "battania": ("Пропал в море во время шторма.", "Пропала в море во время шторма.", "Lost at sea in a storm."),
    "sturgia": ("Погиб в Состязании за Скипетр.", "Погибла в Состязании за Скипетр.",
                "Died in the Gauntlet of Fire for the Scepter."),
    "vlandia": ("Сорвался со скал Грифонстоуна.", "Сорвалась со скал Грифонстоуна.",
                "Fell from the cliffs of Griffonstone."),
    "khuzait": ("Погиб под лавиной.", "Погибла под лавиной.", "Died in an avalanche."),
    "aserai": ("Погиб при обороне улья.", "Погибла при обороне улья.", "Died defending the hive."),
    "nord": ("Замёрз в северных лесах.", "Замёрзла в северных лесах.",
             "Froze to death in the northern woods."),
}

GENERATED = set()     # id дописанных героев — только им выдумываем семьи


def _pool(culture, sex):
    spec = NAMES.get(culture, NAMES["empire"])[sex]
    extras = list(spec[3]) if len(spec) > 3 else []   # лорные имена целиком
    if spec[0] == "составное":
        return ["%s %s" % (a, b) for a in spec[1] for b in spec[2]] + extras
    return list(spec[1]) + extras


class _Names:
    """Выдаёт имена без повторов: ни с каноном, ни между дописанными."""

    def __init__(self, kingdoms, rng):
        self.used = set()
        for k in kingdoms:
            for clan in k["clans"]:
                for hero in clan["heroes"]:
                    self.used.add(hero[1])
        self.rng = rng
        self.pools = {}

    def take(self, culture, sex):
        key = (culture, sex)
        if key not in self.pools:
            pool = [n for n in _pool(culture, sex) if n not in self.used]
            self.rng.shuffle(pool)
            self.pools[key] = pool
        pool = self.pools[key]
        if not pool:
            # Пул исчерпан: берём имя повторно, но с прозвищем — «Санни Дэш Младший»
            base = self.rng.choice(_pool(culture, sex))
            suffixes = (("Младший", "Старший", "Второй", "Третий") if sex == "m"
                        else ("Младшая", "Старшая", "Вторая", "Третья"))
            for suffix in suffixes:
                name = "%s %s" % (base, suffix)
                if name not in self.used:
                    self.used.add(name)
                    return name
            raise RuntimeError("кончились имена: культура %s, пол %s — расширьте NAMES" % key)
        name = pool.pop()
        self.used.add(name)
        return name


def _clan_name(culture, taken, rng):
    word, style = CLAN_STYLE.get(culture, ("Дом", "pair"))
    spec = NAMES.get(culture, NAMES["empire"])["m"]
    for _ in range(200):
        if style == "surname":
            body = rng.choice(spec[2])
        elif style == "pair":
            body = "%s %s" % (rng.choice(spec[1]), rng.choice(spec[2]))
        else:
            body = rng.choice(spec[1])
        name = "%s %s" % (word, body)
        if name not in taken:
            taken.add(name)
            return name
    raise RuntimeError("не подобрать название клана для культуры " + culture)


def _alive_adults(clan):
    dead = set(clan.get("dead", []))
    return sum(1 for h in clan["heroes"] if h[3] >= ADULT_AGE and h[0] not in dead)


class _Kingdom:
    """Всё, что нужно для одной державы: имена, счётчик id, тексты."""

    def __init__(self, k, names, rng):
        self.k = k
        self.culture = k["culture"]
        self.tag = k["kingdom"].replace("kingdom_", "")
        self.names = names
        self.rng = rng
        self.serial = 0
        self.folk = FOLK.get(self.culture, FOLK["empire"])
        self.kingdom_en = lang.en(k["short"])

    def hero(self, clan, sex, age, ru, en, dead=False):
        self.serial += 1
        hid = "%s_%d" % (self.tag, self.serial)
        clan["heroes"].append((hid, self.names.take(self.culture, sex), sex, age, (ru, en)))
        GENERATED.add(hid)
        if dead:
            clan.setdefault("dead", []).append(hid)
        return hid

    # -- описания
    def noble(self, sex):
        m, f, c, em, ef, ec = self.folk
        return (("Знатный %s державы «%s»." if sex == "m" else "Знатная %s державы «%s».")
                % (m if sex == "m" else f, self.k["short"]),
                "A noble %s of %s." % (em if sex == "m" else ef, self.kingdom_en))

    def child(self, clan):
        m, f, c, em, ef, ec = self.folk
        return ("%s из рода «%s»." % (c.capitalize(), clan["name"]),
                "A %s of %s." % (ec, lang.en(clan["name"])))

    def relative(self, role_ru, role_en, of_ru, of_en, cause=None, kin=None):
        """kin — (слово, имя): «сын — Флэш Сентри». Так по-русски не нужен родительный падеж:
        имена вроде «Вильгельм» пришлось бы склонять, а «Спитфайр» — нет, и угадывать не будем."""
        ru = "%s %s." % (role_ru, of_ru) if kin is None else "%s; %s — %s." % (role_ru, kin[0], kin[1])
        en = "%s of %s." % (role_en, of_en)
        if cause:
            ru += " " + cause[0]
            en += " " + cause[1]
        return (ru, en)

    def cause(self, sex, age):
        if age >= 62:
            c = OLD_AGE
        elif sex == "f" and self.rng.random() < 0.3:
            c = CHILDBIRTH
        elif self.rng.random() < 0.35 and self.culture in CULTURE_CAUSE:
            c = CULTURE_CAUSE[self.culture]
        else:
            c = self.rng.choice(CAUSES)
        ru = (c[0] if sex == "m" else c[1]).replace("{K}", self.k["short"])
        return (ru, c[2].replace("{K}", self.kingdom_en))


def _parents(kd, clan, child_hid, child_name_ru, child_name_en, child_age, is_leader, child_sex):
    """Отец и мать героя; большей частью покойные. Возвращает (отец, мать)."""
    rng = kd.rng
    of_ru = "главы рода «%s»" % clan["name"] if is_leader else child_name_ru
    of_en = "the head of %s" % lang.en(clan["name"]) if is_leader else child_name_en
    kin = None if is_leader else ("сын" if child_sex == "m" else "дочь", child_name_ru)
    ids = []
    for sex, role_ru, role_en in (("m", "Отец", "Father"), ("f", "Мать", "Mother")):
        age = child_age + rng.randint(22, 34)
        dead = age >= 66 or rng.random() < DEAD_PARENT
        text = kd.relative(role_ru, role_en, of_ru, of_en, kd.cause(sex, age) if dead else None, kin)
        ids.append(kd.hero(clan, sex, age, text[0], text[1], dead))
    # родители — супруги, иначе живому из них ниже подберут новую пару
    clan.setdefault("marriages", []).append((ids[0], ids[1]))
    return ids[0], ids[1]


def _spouse_and_children(kd, clan, hid, name_ru, name_en, sex, age):
    rng = kd.rng
    spouse_sex = "f" if sex == "m" else "m"
    spouse_age = max(ADULT_AGE + 2, age + rng.randint(-6, 6))
    role = ("Супруга", "Wife") if spouse_sex == "f" else ("Супруг", "Husband")
    text = kd.relative(role[0], role[1], name_ru, lang.en(name_en),
                       kin=("муж" if sex == "m" else "жена", name_ru))
    spouse = kd.hero(clan, spouse_sex, spouse_age, text[0], text[1])
    clan.setdefault("marriages", []).append((hid, spouse))
    father, mother = (hid, spouse) if sex == "m" else (spouse, hid)
    oldest_parent = min(age, spouse_age)
    for _ in range(rng.choice([0, 1, 1, 2])):
        child_age = rng.randint(1, max(1, min(16, oldest_parent - 19)))
        text = kd.child(clan)
        child = kd.hero(clan, rng.choice("mf"), child_age, text[0], text[1])
        clan.setdefault("children", []).append((child, father, mother))


def _families(kingdoms, names, rng, log):
    """Родители, супруги и дети — дописанным героям; канонным — только родители."""
    added = dead = 0
    for k in kingdoms:
        kd = _Kingdom(k, names, rng)
        kd.serial = max([int(h[0].split("_")[-1]) for c in k["clans"] for h in c["heroes"]
                         if h[0].startswith(kd.tag + "_") and h[0].split("_")[-1].isdigit()] + [0])
        for clan in k["clans"]:
            has_parents = set(c[0] for c in clan.get("children", []))
            married = set(x for pair in clan.get("marriages", []) for x in pair)
            leader = clan["heroes"][0][0]
            ruling = clan.get("ruling", False)
            before = len(clan["heroes"])
            # Родители — группами: дописанные взрослые одного клана считаются братьями и сёстрами
            # главы (в дописанном клане) или друг друга (в канонном), у них одни родители.
            sibling_group = [h for h in list(clan["heroes"])
                             if h[0] in GENERATED and h[3] >= ADULT_AGE and h[0] not in has_parents
                             and h[0] not in married]
            if leader in GENERATED and leader not in has_parents:
                sibling_group = [clan["heroes"][0]] + [h for h in sibling_group if h[0] != leader]
            if sibling_group:
                head = sibling_group[0]
                parents = _parents(kd, clan, head[0], head[1], lang.en(head[1]), head[3],
                                   is_leader=(head[0] == leader), child_sex=head[2])
                for h in sibling_group:
                    clan.setdefault("children", []).append((h[0], parents[0], parents[1]))
                    has_parents.add(h[0])
            # Канонным героям — родители, кроме правителей и стариков
            for h in list(clan["heroes"]):
                if h[0] in GENERATED or h[0] in has_parents or h[3] >= 50:
                    continue
                if ruling and h[0] == leader:
                    continue
                parents = _parents(kd, clan, h[0], h[1], lang.en(h[1]), h[3], is_leader=False,
                                   child_sex=h[2])
                clan.setdefault("children", []).append((h[0], parents[0], parents[1]))
                has_parents.add(h[0])
            # Супруги и дети — дописанным взрослым без пары (родители выше уже женаты друг на друге)
            married = set(x for pair in clan.get("marriages", []) for x in pair)
            for h in list(clan["heroes"]):
                if h[0] not in GENERATED or h[0] in married or h[3] < ADULT_AGE + 2:
                    continue
                if h[0] in clan.get("dead", []):
                    continue
                if rng.random() < SPOUSE_CHANCE:
                    _spouse_and_children(kd, clan, h[0], h[1], h[1], h[2], h[3])
            added += len(clan["heroes"]) - before
            dead += len(clan.get("dead", []))
    log("семьи: дописано родичей %d, из них покойных %d" % (added, dead))


def fill(kingdoms, forts, log=print):
    """Дописывает кланы, лордов и семьи прямо в список держав. forts — {id державы: крепостей}."""
    rng = random.Random(SEED)
    names = _Names(kingdoms, rng)
    taken_clans = set(c["name"] for k in kingdoms for c in k["clans"])
    added_clans = added_lords = 0
    for k in kingdoms:
        kd = _Kingdom(k, names, rng)
        # 1. Написанные руками кланы доводим до ADULTS взрослых
        for clan in k["clans"]:
            while _alive_adults(clan) < ADULTS:
                sex = rng.choice("mf")
                kd.hero(clan, sex, rng.randint(24, 45), *kd.noble(sex))
                added_lords += 1
        # 2. Кланов в державе — до целевого числа
        target = max(MIN_CLANS, forts.get(k["kingdom"], 0) - 6)
        while len(k["clans"]) < target:
            clan = {"id": "clan_%s_g%d" % (kd.tag, len(k["clans"]) + 1),
                    "name": _clan_name(kd.culture, taken_clans, rng),
                    "tier": rng.choice([2, 3, 3, 4]), "heroes": [], "marriages": [], "children": []}
            leader_sex = rng.choice("mf")
            leader = kd.hero(clan, leader_sex, rng.randint(34, 50), *kd.noble(leader_sex))
            kd.hero(clan, "m", rng.randint(24, 40), *kd.noble("m"))
            kd.hero(clan, "f", rng.randint(22, 38), *kd.noble("f"))
            k["clans"].append(clan)
            added_clans += 1
            added_lords += 3
            # супруг(а) и дети главы — всегда, чтобы у клана было будущее
            _spouse_and_children(kd, clan, leader, clan["heroes"][0][1], clan["heroes"][0][1],
                                 leader_sex, clan["heroes"][0][3])
        log("%s: кланов %d, героев %d" % (k["short"], len(k["clans"]),
                                            sum(len(c["heroes"]) for c in k["clans"])))
    log("дописано кланов %d, лордов %d" % (added_clans, added_lords))
    _families(kingdoms, names, rng, log)
