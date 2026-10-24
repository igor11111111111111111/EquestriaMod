# Заклинания мода: Module/ModuleData/equestria_spells.xml + переводы.
#
#   python make_spells.py <папка Module мода>
#
# Файл читает сама DLL (EquestriaSpells.cs), а не игра: это не игровой тип объектов, в SubModule.xml
# его регистрировать не нужно. Названия и описания — через {=ключ}, русский текст кладётся
# в ModuleData/Languages/<язык>/eq_spells_*.xml (см. tools/lang.py).
#
# Частицы берём ванильные: их имена лежат строками в
# Native\AssetPackages\particles.tpac (psys_*). Своих частиц у мода пока нет.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lang  # noqa: E402

MOD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Module")
DATA = os.path.join(MOD, "ModuleData")

# id, название, описание, и числа:
#   mana      — сколько маны стоит
#   cooldown  — откат в секундах
#   damage    — урон в центре взрыва (к краю радиуса падает вдвое)
#   radius    — радиус взрыва, метры
#   speed     — скорость снаряда, м/с
#   life      — сколько секунд летит (speed * life = дальность)
#   cast      — задержка перед вылетом, секунды (под анимацию броска)
#   trail     — частицы у летящего снаряда; "prefab:имя" — заготовка из Module/Prefabs
#   burst     — частицы взрыва
#   light     — цвет и сила свечения снаряда: r,g,b,интенсивность,радиус (0 = без света)
SPELLS = [
    dict(id="fireball",
         name="Огненный шар",
         text="Сгусток пламени: взрывается там, куда попал, и обжигает всех вокруг. "
              "Драконы плюются им от рождения, единороги учатся годами.",
         mana=15, cooldown=12, damage=60, radius=4.0, speed=35, life=3.0, cast=0.5,
         # ВРЕМЕННО, как в The Old Realms: хвост — ванильная psys_game_burning_agent с их
         # настройкой излучателей (Module/Prefabs/eq_spell_fx.xml), взрыв — их частица
         # psys_fireball_explosion_1 (перенесена в Module/Assets/spells/eq_spell_fx.tpac).
         # Заменить на свои, сделанные в редакторе.
         trail="prefab:eq_fireball_trail", burst="psys_fireball_explosion_1",
         light="255,170,0,50,10"),
]


def build():
    rows = []
    for s in SPELLS:
        rows.append(
            '\t<Spell\n'
            '\t\tid="%(id)s"\n'
            '\t\tname="%(name)s"\n'
            '\t\ttext="%(text)s"\n'
            '\t\tmana="%(mana)d"\n'
            '\t\tcooldown="%(cooldown)g"\n'
            '\t\tdamage="%(damage)g"\n'
            '\t\tradius="%(radius)g"\n'
            '\t\tspeed="%(speed)g"\n'
            '\t\tlife="%(life)g"\n'
            '\t\tcast="%(cast)g"\n'
            '\t\ttrail="%(trail)s"\n'
            '\t\tburst="%(burst)s"\n'
            '\t\tlight="%(light)s" />'
            % dict(s,
                   name=lang.loc("eq_spell_%s_name" % s["id"], s["name"]),
                   text=lang.loc("eq_spell_%s_text" % s["id"], s["text"])))
    # Строки самого интерфейса магии (их берёт C# по ключу; в XML заклинаний они не нужны)
    for key, text in [("eq_mana_label", "Мана"),
                      ("eq_mana_hint", "Мана копится в пути по карте и тратится на заклинания."),
                      ("eq_spell_no_mana", "Не хватает маны"),
                      ("eq_spell_cooldown", "Заклинание ещё не готово"),
                      ("eq_spell_none", "Заклинаний нет"),
                      ("eq_spell_aim_hint", "ЛКМ — пустить, ПКМ — отмена")]:
        lang.loc(key, text)
    body = "<Spells>\n%s\n</Spells>\n" % "\n".join(rows)
    path = os.path.join(DATA, "equestria_spells.xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write("<!-- Заклинания. Файл собран tools/make_spells.py — правьте таблицу SPELLS в нём.\n"
                "     Читается модом напрямую (EquestriaSpells.cs), в SubModule.xml не значится. -->\n")
        f.write(body)
    print("[spells] записан equestria_spells.xml, заклинаний: %d" % len(SPELLS))
    lang.write(DATA, "eq_spells", log=lambda m: print("[spells] " + m))
    lang.report(log=lambda m: print("[spells] " + m))


if __name__ == "__main__":
    build()
