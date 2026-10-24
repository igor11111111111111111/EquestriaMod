using System;
using System.IO;
using System.Reflection;
using System.Xml;
using TaleWorlds.CampaignSystem;

namespace EquestriaMod
{
    // Дружба и вражда между героями Эквестрии.
    //
    // Отношения между героями игра из XML не читает: в heroes.xml есть только родство. Поэтому
    // tools/make_world.py пишет свой файл ModuleData/equestria_relations.xml, а это поведение
    // применяет его один раз — при создании новой кампании. В сохранении отношения хранит сама игра.
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
            // Библиотека лежит в <мод>\bin\Win64_Shipping_Client — поднимаемся на два уровня.
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
