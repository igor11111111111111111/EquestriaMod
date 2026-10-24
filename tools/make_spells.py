# The mod's spells: Module/ModuleData/equestria_spells.xml + translations.
#
#   python make_spells.py <the mod's Module folder>
#
# The file is read by the DLL itself (EquestriaSpells.cs), not by the game: it is not a game object type,
# so it need not be registered in SubModule.xml. Names and descriptions go through {=key}; the Russian text
# goes to ModuleData/Languages/<language>/eq_spells_*.xml (see tools/lang.py).
#
# Particles are vanilla: their names are stored as strings in
# Native\AssetPackages\particles.tpac (psys_*). The mod has no particles of its own yet.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lang  # noqa: E402

MOD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Module")
DATA = os.path.join(MOD, "ModuleData")

# id, name, description, and numbers:
#   mana      - how much mana it costs
#   cooldown  - cooldown in seconds
#   damage    - damage at the centre of the explosion (halves toward the edge of the radius)
#   radius    - explosion radius, metres
#   speed     - projectile speed, m/s
#   life      - how many seconds it flies (speed * life = range)
#   cast      - delay before launch, seconds (for the throw animation)
#   trail     - particles on the flying projectile; "prefab:name" is a prefab from Module/Prefabs
#   burst     - explosion particles
#   light     - projectile glow colour and strength: r,g,b,intensity,radius (0 = no light)
SPELLS = [
    dict(id="fireball",
         name="Огненный шар",
         text="Сгусток пламени: взрывается там, куда попал, и обжигает всех вокруг. "
              "Драконы плюются им от рождения, единороги учатся годами.",
         mana=15, cooldown=12, damage=60, radius=4.0, speed=35, life=3.0, cast=0.5,
         # TEMPORARY, as in The Old Realms: the trail is vanilla psys_game_burning_agent with their
         # emitter settings (Module/Prefabs/eq_spell_fx.xml), the explosion is their particle
         # psys_fireball_explosion_1 (moved to Module/Assets/spells/eq_spell_fx.tpac).
         # Replace with our own, made in the editor.
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
    # Strings of the magic UI itself (C# takes them by key; they are not needed in the spells XML)
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
