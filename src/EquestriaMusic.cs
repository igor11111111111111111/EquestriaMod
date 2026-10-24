using System;
using System.Collections.Generic;
using HarmonyLib;
using TaleWorlds.MountAndBlade;

namespace EquestriaMod
{
    // Своя музыка вместо ванильной.
    //
    // Музыку игра собирает через psai из всех модулей, у которых в ModuleData/project.mbproj объявлен
    // soln_soundtrack. Но если наша тема повторяет НОМЕР ванильной (5 — меню, 1 — карта и т.д.),
    // игра падает при загрузке ещё до главного меню (проверено 2026-09-18: тема 5 — краш, тема 41 — норма).
    //
    // Поэтому наши темы в Module/Music/soundtrack.xml получили свободные номера (41..48, tools/make_music.py),
    // а здесь мы подменяем тему в момент запуска: игра просит ванильную — играет наша.
    // Ванильные файлы музыки остаются нетронутыми, править игру не нужно.
    public static class EquestriaMusic
    {
        // наши темы (см. tools/make_music.py)
        private const int Menu = 41;
        private const int MapCalm = 42;
        private const int MapDark = 43;
        private const int BattleSmall = 44;
        private const int BattleMedium = 45;
        private const int Siege = 46;
        private const int Victory = 47;
        private const int Defeat = 48;

        // ванильная тема -> наша. Номера ванильных — enum TaleWorlds.MountAndBlade.MusicTheme.
        private static readonly Dictionary<int, int> Map = new Dictionary<int, int>
        {
            { 5, Menu },                                                   // Main Theme
            { 1, MapCalm },                                                // Campaign Standard
            { 28, MapCalm }, { 29, MapCalm }, { 30, MapCalm }, { 31, MapCalm },  // карта по культурам
            { 32, MapCalm }, { 33, MapCalm }, { 34, MapCalm },
            { 10247, MapCalm }, { 10248, MapCalm }, { 10249, MapCalm },    // северная кампания и морские
            { 7, MapDark },                                                // Campaign Dark
            { 3, MapDark }, { 16, MapDark }, { 18, MapDark },              // «драматичная» карта по культурам
            { 20, MapDark }, { 22, MapDark }, { 24, MapDark },
            { 12, BattleSmall }, { 36, BattleSmall }, { 27, BattleSmall }, { 8, BattleSmall },
            { 10, BattleMedium }, { 35, BattleMedium }, { 6, BattleMedium },
            { 9, BattleMedium }, { 11, BattleMedium },                     // перелом боя
            { 14, BattleMedium }, { 15, BattleMedium },                    // резкий перелом
            { 39, BattleMedium }, { 40, BattleMedium }, { 10246, BattleMedium },
            { 10241, BattleMedium }, { 10242, BattleMedium }, { 10243, BattleMedium }, { 10244, Menu },
            { 13, Siege }, { 38, Siege },                                  // осада
            { 2, Victory }, { 4, Victory }, { 17, Victory }, { 19, Victory },
            { 21, Victory }, { 23, Victory }, { 25, Victory },
            { 26, Defeat },
        };

        private static readonly HashSet<int> Logged = new HashSet<int>();

        // Патчим сам psai (TaleWorlds.PSAI.dll): музыку меню игра запускает через MenuModeEnter,
        // а карту и бой — через TriggerMusicTheme, поэтому одного MBMusicManager.StartTheme мало.
        public static void Apply(Harmony harmony)
        {
            var core = AccessTools.TypeByName("psai.net.PsaiCore");
            if (core == null)
            {
                EquestriaCrashLog.Warn("музыка: класс psai.net.PsaiCore не найден — музыка останется ванильной");
                return;
            }
            var patched = 0;
            foreach (var method in AccessTools.GetDeclaredMethods(core))
            {
                if (method.Name != "TriggerMusicTheme" && method.Name != "MenuModeEnter")
                {
                    continue;
                }
                var first = method.GetParameters();
                if (first.Length == 0 || first[0].ParameterType != typeof(int))
                {
                    continue;
                }
                // Harmony сопоставляет параметры по имени: у TriggerMusicTheme это themeId, у MenuModeEnter — menuThemeId
                var prefix = first[0].Name == "menuThemeId" ? nameof(ReplaceMenuThemeId) : nameof(ReplaceThemeId);
                harmony.Patch(method, prefix: new HarmonyMethod(typeof(EquestriaMusic), prefix));
                patched++;
            }
            EquestriaCrashLog.Log($"музыка: подмена тем включена ({patched} методов psai, {Map.Count} ванильных тем ведут на наши)");
        }

        private static void ReplaceMenuThemeId(ref int menuThemeId)
        {
            ReplaceThemeId(ref menuThemeId);
        }

        private static void ReplaceThemeId(ref int themeId)
        {
            if (!Map.TryGetValue(themeId, out int ours))
            {
                return;
            }
            if (Logged.Add(themeId))
            {
                EquestriaCrashLog.Log($"музыка: тема {(MusicTheme)themeId} ({themeId}) заменена на нашу {ours}");
            }
            themeId = ours;
        }
    }
}
