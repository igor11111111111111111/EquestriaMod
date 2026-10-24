using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Xml;
using TaleWorlds.CampaignSystem;
using TaleWorlds.Library;
using TaleWorlds.Localization;
using TaleWorlds.ModuleManager;

namespace EquestriaMod
{
    // Описание одного заклинания. Данные — ModuleData/equestria_spells.xml (собирается
    // tools/make_spells.py). Файл читаем сами: это не игровой тип объектов, игре о нём знать незачем,
    // и в SubModule.xml он не значится. Так же поступает The Old Realms со своими tor_custom_xmls
    // (см. docs/tor_reference/04_magic.md).
    public class EquestriaSpell
    {
        public string Id;
        public TextObject Name;
        public TextObject Description;
        public int Mana;
        public float Cooldown;      // секунды
        public float Damage;        // урон в центре взрыва
        public float Radius;        // радиус взрыва, метры
        public float Speed;         // скорость снаряда, м/с
        public float Life;          // сколько секунд летит (Speed * Life = дальность)
        public float CastTime;      // задержка перед вылетом
        public string Trail;        // частицы у снаряда
        public string Burst;        // частицы взрыва
        public Vec3 LightColor;     // цвет свечения снаряда (0,0,0 — без света)
        public float LightIntensity;
        public float LightRadius;

        public bool HasLight
        {
            get { return LightIntensity > 0f && LightRadius > 0f; }
        }
    }

    public static class EquestriaSpells
    {
        private const string FileName = "equestria_spells.xml";

        private static List<EquestriaSpell> _spells;

        // Все заклинания мода. Читаются один раз за запуск; при ошибке — пустой список,
        // мод продолжает работать без магии.
        public static List<EquestriaSpell> All
        {
            get
            {
                if (_spells == null)
                {
                    _spells = new List<EquestriaSpell>();
                    EquestriaCrashLog.Try("чтение " + FileName, Load);
                    EquestriaCrashLog.Log($"заклинаний прочитано: {_spells.Count}");
                }
                return _spells;
            }
        }

        private static void Load()
        {
            string path = Path.Combine(
                ModuleHelper.GetModuleFullPath("EquestriaMod"), "ModuleData", FileName);
            if (!File.Exists(path))
            {
                return;
            }
            var doc = new XmlDocument();
            doc.Load(path);
            foreach (XmlNode node in doc.DocumentElement.ChildNodes)
            {
                if (node.NodeType != XmlNodeType.Element)
                {
                    continue;
                }
                var spell = new EquestriaSpell
                {
                    Id = Attr(node, "id"),
                    Name = new TextObject(Attr(node, "name")),
                    Description = new TextObject(Attr(node, "text")),
                    Mana = (int)Number(node, "mana", 10f),
                    Cooldown = Number(node, "cooldown", 10f),
                    Damage = Number(node, "damage", 40f),
                    Radius = Number(node, "radius", 3f),
                    Speed = Number(node, "speed", 30f),
                    Life = Number(node, "life", 3f),
                    CastTime = Number(node, "cast", 0.5f),
                    Trail = Attr(node, "trail"),
                    Burst = Attr(node, "burst")
                };
                // light="r,g,b,интенсивность,радиус"
                string[] light = Attr(node, "light").Split(',');
                if (light.Length == 5)
                {
                    spell.LightColor = new Vec3(Parse(light[0]) / 255f, Parse(light[1]) / 255f,
                                                Parse(light[2]) / 255f);
                    spell.LightIntensity = Parse(light[3]);
                    spell.LightRadius = Parse(light[4]);
                }
                _spells.Add(spell);
            }
        }

        private static string Attr(XmlNode node, string name)
        {
            XmlAttribute a = node.Attributes[name];
            return a == null ? string.Empty : a.Value;
        }

        private static float Number(XmlNode node, string name, float fallback)
        {
            string text = Attr(node, name);
            return string.IsNullOrEmpty(text) ? fallback : Parse(text);
        }

        private static float Parse(string text)
        {
            float value;
            return float.TryParse(text.Trim(), NumberStyles.Float, CultureInfo.InvariantCulture, out value)
                ? value : 0f;
        }

        public static EquestriaSpell Find(string id)
        {
            return All.Find(s => string.Equals(s.Id, id, StringComparison.OrdinalIgnoreCase));
        }

        // Что умеет герой. Пока все заклинания доступны игроку: колдовать учимся на одном фаерболе,
        // ограничения по расе и обучение появятся, когда заклинаний станет больше.
        public static List<EquestriaSpell> KnownBy(Hero hero)
        {
            return hero != null && hero == Hero.MainHero ? All : new List<EquestriaSpell>();
        }
    }
}
