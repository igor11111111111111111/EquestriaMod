using System.Collections.Generic;
using System.IO;
using System.Xml;
using HarmonyLib;
using TaleWorlds.Localization;

namespace EquestriaMod
{
    // Английский текст реплик — из ModuleData\Languages\EN\*.xml, руками мода.
    //
    // Для английского игра не читает языковые файлы вовсе и даже не заглядывает в словарь переводов:
    // и в LocalizedTextManager.LoadLanguage, и в MBTextManager.GetLocalizedText стоит проверка
    // «язык English — берём текст по умолчанию из самой строки» (проверено по IL 19.09.2026).
    // У наших реплик текста по умолчанию нет: код строит TextObject("{=eq_surrender_1}") с одним
    // ключом, а ванильные строки (ji2eenPE и прочие) переводятся на переменные {EQV_...} только
    // языковым файлом. Поэтому в английской игре реплики были бы пусты, а разбойники говорили бы
    // по-кальрадийски.
    //
    // Делаем для английского то же, что игра делает для остальных языков, только сами: читаем наши
    // EN-файлы в таблицу и перехватываем GetLocalizedText — если язык английский и ключ наш, отдаём
    // текст из таблицы. Это горячий путь (каждая строка игры), поэтому проверки самые дешёвые: первые
    // два символа «{=», поиск «}», один поиск в словаре.
    public static class EquestriaEnglishTexts
    {
        private const string English = "English";

        private static readonly Dictionary<string, string> Table = new Dictionary<string, string>();

        public static void Apply(Harmony harmony)
        {
            Load();
            var target = AccessTools.Method(typeof(MBTextManager), "GetLocalizedText", new[] { typeof(string) });
            if (target == null)
            {
                EquestriaCrashLog.Warn("английские реплики: MBTextManager.GetLocalizedText не найден — "
                    + "в английской игре реплики будут пустыми");
                return;
            }
            harmony.Patch(target, prefix: new HarmonyMethod(typeof(EquestriaEnglishTexts), nameof(OurEnglish)));
        }

        private static void Load()
        {
            EquestriaCrashLog.Try("английские реплики", () =>
            {
                string folder = Path.Combine(
                    TaleWorlds.ModuleManager.ModuleHelper.GetModuleFullPath("EquestriaMod"),
                    "ModuleData", "Languages", "EN");
                if (!Directory.Exists(folder))
                {
                    EquestriaCrashLog.Warn("английские реплики: нет папки Languages\\EN");
                    return;
                }
                foreach (string file in Directory.GetFiles(folder, "*.xml"))
                {
                    var xml = new XmlDocument();
                    xml.Load(file);
                    foreach (XmlNode node in xml.SelectNodes("//strings/string"))
                    {
                        string id = node.Attributes?["id"]?.Value;
                        string text = node.Attributes?["text"]?.Value;
                        if (!string.IsNullOrEmpty(id) && text != null)
                        {
                            Table[id] = text;
                        }
                    }
                }
                EquestriaCrashLog.Log("английские реплики: строк в таблице " + Table.Count);
            });
        }

        private static bool OurEnglish(string text, ref string __result)
        {
            if (Table.Count == 0 || text == null || text.Length < 4 || text[0] != '{' || text[1] != '=')
            {
                return true;
            }
            int end = text.IndexOf('}', 2);
            if (end < 0 || MBTextManager.ActiveTextLanguage != English)
            {
                return true;
            }
            string ours;
            if (Table.TryGetValue(text.Substring(2, end - 2), out ours))
            {
                __result = ours;
                return false;
            }
            return true;
        }
    }
}
