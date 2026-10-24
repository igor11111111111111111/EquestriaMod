# Small UI strings written directly in C# (not in XML data): the mercenary camp
# (EquestriaMercCamp.cs), the wings/tail/horn and stripes toggle (EquestriaHairStyleView.cs),
# the "race review" button (EquestriaRaceParty.cs), the race restore notification
# (EquestriaRaceSaveBehavior.cs). The English text already lives in the code as {=key}English - this
# script only delivers the Russian (and a stub with the same English) to Languages/<language>.
#
#   python make_misc_ui.py <mod Module folder>
#
# Without this file a non-Russian player would see exactly what was written in the code - and until
# 04.10.2026 there was raw Russian text without a single {=key}, and it was shown to ALL languages,
# including English (see memory bannerlord-localization: for English the game takes the default text
# from the string itself, Languages does not touch it; for other languages without a key there is
# nothing to refer to at all).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lang  # noqa: E402

MOD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Module")
DATA = os.path.join(MOD, "ModuleData")

# key -> (Russian, English - must match word for word what follows {=key} in C#)
STRINGS = {
    # --- EquestriaMercCamp.cs: mercenary camp near the kingdoms' capitals ---
    "eq_merc_camp_name": ("Лагерь наёмников", "Mercenary camp"),
    "eq_merc_camp_hire_option": ("Нанять наёмников", "Hire mercenaries"),
    "eq_merc_camp_line_empty": (
        "Пусто у нас. Все клинки разобрали, подходи через день-другой.",
        "Nothing here. Every blade's been taken - come back in a day or two."),
    "eq_merc_camp_line_greet": (
        "Лагерь вольных рот. Клинки продаём поштучно — были бы деньги.",
        "Camp of the free companies. We sell blades one at a time - if you've got the coin."),
    "eq_merc_camp_line_show": ("Показать, кто у вас есть.", "Show me who you've got."),
    "eq_merc_camp_line_ask_discount": ("А скидка будет?", "Any chance of a discount?"),
    "eq_merc_camp_line_discount": (
        "Кому как. За каждые три единицы доверия — процент скидки с цены найма. "
        "Доверие у тебя {EQ_MERC_RELATION} из {EQ_MERC_RELATION_MAX} — это {EQ_MERC_DISCOUNT}% скидки. "
        "Растёт оно от денег: единица за каждые четыреста монет, оставленные в лагере. "
        "И считаем мы только своё: в других лагерях доверие своё.",
        "Depends who's asking. Every three points of trust is one percent off the hiring price. "
        "Your trust here is {EQ_MERC_RELATION} of {EQ_MERC_RELATION_MAX} - that's {EQ_MERC_DISCOUNT}% off. "
        "It grows with coin: one point for every four hundred spent here. "
        "And we only count our own - other camps keep their own trust."),
    "eq_merc_camp_line_ask_stock": ("Когда придут наёмники?", "When will more mercenaries show up?"),
    "eq_merc_camp_line_stock": (
        "Каждый день подходит примерно {EQ_MERC_COME} человек, а кто заждался — уходит "
        "искать нанимателя сам. Больше {EQ_MERC_LIMIT} у нас не помещается; сейчас "
        "стоит {EQ_MERC_STOCK}. Чем выше доверие, тем и мест больше, и народу приходит "
        "гуще: по одному лишнему месту за единицу доверия и по человеку за каждые десять.",
        "About {EQ_MERC_COME} show up each day, and those who wait too long go looking for work "
        "elsewhere. We can't fit more than {EQ_MERC_LIMIT}; right now we've got {EQ_MERC_STOCK}. "
        "The more trust, the more room and the more who come - one extra spot per point of trust, "
        "one more recruit for every ten."),
    "eq_merc_camp_line_leave": ("В другой раз.", "Some other time."),
    "eq_merc_camp_empty_tooltip": (
        "Сейчас в лагере никого нет — заходите через день-другой.",
        "Nobody's here right now - come back in a day or two."),
    "eq_merc_camp_title": ("Лагерь наёмников у {TOWN}", "Mercenary camp near {TOWN}"),

    # --- EquestriaPrisonerButchery.cs: hint of the prisoner processing button in the party screen ---
    "eq_prisoner_butcher_hint": ("Пустить на фарш", "Turn into mincemeat"),

    # --- EquestriaHairStyleView.cs: hair/wings/tail/horn toggles ---
    "eq_hair_plain": ("Сплошная", "Solid"),
    "eq_hair_stripe": ("Полосатая", "Striped"),
    "eq_wings_label": ("Крылья: {STATE}", "Wings: {STATE}"),
    "eq_tail_label": ("Хвост: {STATE}", "Tail: {STATE}"),
    "eq_horn_label": ("Рог: {STATE}", "Horn: {STATE}"),
    "eq_state_on": ("вкл", "on"),
    "eq_state_off": ("выкл", "off"),

    # --- EquestriaRaceParty.cs: race review button in the main menu ---
    "eq_race_party_menu": ("Эквестрия: смотр рас", "Equestria: race review"),

    # --- EquestriaRaceSaveBehavior.cs: notification after loading a save ---
    "eq_race_restored_note": (
        "Эквестрия: раса восстановлена у {COUNT} героев",
        "Equestria: restored race for {COUNT} hero(es)"),

    # --- EquestriaDefaultStart.cs: game start choice popup after the character creation wizard ---
    "eq_start_poor": ("Обычный нищий старт", "Ordinary humble start"),
    "eq_start_mercenary": (
        "Наёмник державы (тир клана 1)", "Mercenary of a kingdom (clan tier 1)"),
    "eq_start_vassal": (
        "Вассал державы (тир клана 3, одно владение)",
        "Vassal of a kingdom (clan tier 3, one fief)"),
    "eq_start_king": (
        "Правитель державы (тир клана 4, одно владение)",
        "Ruler of a kingdom (clan tier 4, one fief)"),
    "eq_start_title": ("Выберите начало игры", "Choose your start"),
    "eq_start_desc": (
        "С чего вы начинаете своё приключение в Эквестрии?",
        "How do you begin your adventure in Equestria?"),
    "eq_start_confirm": ("Подтвердить", "Confirm"),
    "eq_start_poor_note": (
        "Эквестрия: обычный нищий старт", "Equestria: an ordinary humble start"),
    "eq_start_kingdom_title": ("Выберите державу", "Choose a kingdom"),
    "eq_start_kingdom_desc": ("Какой державе вы будете служить?", "Which kingdom will you serve?"),
    "eq_start_done": (
        "Эквестрия: старт применён ({TYPE}, {KINGDOM})",
        "Equestria: start applied ({TYPE} of {KINGDOM})"),
    "eq_start_type_mercenary": ("наёмник", "mercenary"),
    "eq_start_type_vassal": ("вассал", "vassal"),
    "eq_start_type_king": ("правитель", "ruler"),
    # flight scroll tooltip in the inventory (src/EquestriaFlightScroll.cs, AfterRefreshItemTooltips)
    "eq_flight_speed": ("Скорость полёта", "Flight speed"),
    # settlement tooltip: header of the breakdown by race (src/EquestriaRaceAssimilationCommands.cs)
    "eq_race_tooltip": ("Раса", "Race"),
    # notification when processing prisoners (src/EquestriaPrisonerButchery.cs)
    "eq_butcher_meat": ("+{MEAT} мяса (всего в отряде: {TOTAL})", "+{MEAT} meat (party total: {TOTAL})"),
    # our own icon group in the banner editor (Module/ModuleData/equestria_banner_icons.xml)
    "eq_banner_group": ("Эквестрия", "Equestria"),
}

for _key, (_ru, _en) in STRINGS.items():
    lang.loc(_key, _ru, _en)

lang.write(DATA, "eq_misc_ui", log=lambda m: print("[misc_ui] " + m))
lang.report(log=lambda m: print("[misc_ui] " + m))
