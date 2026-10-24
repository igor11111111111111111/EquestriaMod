using System;
using System.IO;
using System.Reflection;
using System.Xml;
using TaleWorlds.CampaignSystem;

namespace EquestriaMod
{
    // Friendship and enmity between the heroes of Equestria.
    //
    // The game does not read relations between heroes from XML: heroes.xml only has kinship. So
    // tools/make_world.py writes its own file ModuleData/equestria_relations.xml, and this behavior
    // applies it once - when a new campaign is created. In a save the game stores the relations itself.
    public class EquestriaRelationsBehavior : CampaignBehaviorBase
    {
        private const string FileName = "equestria_relations.xml";

        public override void RegisterEvents()
        {
            CampaignEvents.OnNewGameCreatedEvent.AddNonSerializedListener(this, _ =>
                EquestriaCrashLog.Try("отношения между героями", Apply));
        }

        public override void SyncData(IDataStore dataStore)
        {
        }

        private static void Apply()
        {
            // The library lives in <mod>\bin\Win64_Shipping_Client - go up two levels.
            string bin = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
            string path = Path.GetFullPath(Path.Combine(bin, "..", "..", "ModuleData", FileName));
            if (!File.Exists(path))
            {
                EquestriaCrashLog.Warn("отношения: нет файла " + path);
                return;
            }

            var document = new XmlDocument();
            document.Load(path);
            int applied = 0;
            foreach (XmlElement node in document.GetElementsByTagName("Relation"))
            {
                Hero first = Hero.Find(node.GetAttribute("hero1"));
                Hero second = Hero.Find(node.GetAttribute("hero2"));
                if (first == null || second == null)
                {
                    EquestriaCrashLog.Warn($"отношения: нет героя {node.GetAttribute("hero1")} "
                        + $"или {node.GetAttribute("hero2")}");
                    continue;
                }
                int value = int.Parse(node.GetAttribute("value"));
                CharacterRelationManager.SetHeroRelation(first, second, value);
                applied++;
            }
            EquestriaCrashLog.Log($"отношения между героями заданы: {applied}");
        }
    }
}
