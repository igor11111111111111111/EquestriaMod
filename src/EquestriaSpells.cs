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
    // Description of one spell. Data - ModuleData/equestria_spells.xml (built by
    // tools/make_spells.py). We read the file ourselves: it is not a game object type, the game has no need
    // to know about it, and it is not listed in SubModule.xml. The Old Realms does the same with its tor_custom_xmls
    // (see docs/tor_reference/04_magic.md).
    public class EquestriaSpell
    {
        public string Id;
        public TextObject Name;
        public TextObject Description;
        public int Mana;
        public float Cooldown;      // seconds
        public float Damage;        // damage at the center of the explosion
        public float Radius;        // explosion radius, meters
        public float Speed;         // projectile speed, m/s
        public float Life;          // how many seconds it flies (Speed * Life = range)
        public float CastTime;      // delay before launch
        public string Trail;        // particles on the projectile
        public string Burst;        // explosion particles
        public Vec3 LightColor;     // projectile glow color (0,0,0 - no light)
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

        // All spells of the mod. Read once per launch; on error - an empty list,
        // the mod keeps working without magic.
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
                // light="r,g,b,intensity,radius"
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

        // What a hero can do. For now all spells are available to the player: we learn casting on a single fireball,
        // race restrictions and learning will appear when there are more spells.
        public static List<EquestriaSpell> KnownBy(Hero hero)
        {
            return hero != null && hero == Hero.MainHero ? All : new List<EquestriaSpell>();
        }
    }
}
