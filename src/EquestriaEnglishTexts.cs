using System.Collections.Generic;
using System.IO;
using System.Xml;
using HarmonyLib;
using TaleWorlds.Localization;

namespace EquestriaMod
{
    // English dialogue text — from ModuleData\Languages\EN\*.xml, loaded by the mod itself.
    //
    // For English the game does not read language files at all and does not even look into the translation
    // dictionary: both LocalizedTextManager.LoadLanguage and MBTextManager.GetLocalizedText have a check
    // "language is English — take the default text from the string itself" (checked in IL 19.09.2026).
    // Our lines have no default text: the code builds TextObject("{=eq_surrender_1}") with just a
    // key, and vanilla strings (ji2eenPE and others) are switched to {EQV_...} variables only by the
    // language file. So in an English game the lines would be empty, and bandits would talk
    // in Calradian terms.
    //
    // We do for English what the game does for the other languages, only ourselves: read our
    // EN files into a table and intercept GetLocalizedText — if the language is English and the key is
    // ours, return the text from the table. This is a hot path (every string in the game), so the checks
    // are the cheapest possible: the first two characters "{=", a search for "}", one dictionary lookup.
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
