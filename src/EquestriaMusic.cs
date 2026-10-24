using System;
using System.Collections.Generic;
using HarmonyLib;
using TaleWorlds.MountAndBlade;

namespace EquestriaMod
{
    // Our own music instead of the vanilla one.
    //
    // The game gathers music through psai from all modules that declare soln_soundtrack in
    // ModuleData/project.mbproj. But if our theme repeats the NUMBER of a vanilla one (5 = menu, 1 = map, etc.),
    // the game crashes while loading, before the main menu (checked 2026-09-18: theme 5 crashes, theme 41 is fine).
    //
    // So our themes in Module/Music/soundtrack.xml got free numbers (41..48, tools/make_music.py),
    // and here we swap the theme at the moment it starts: the game asks for the vanilla one, ours plays.
    // The vanilla music files stay untouched; the game does not need to be edited.
    public static class EquestriaMusic
    {
        // our themes (see tools/make_music.py)
        private const int Menu = 41;
        private const int MapCalm = 42;
        private const int MapDark = 43;
        private const int BattleSmall = 44;
        private const int BattleMedium = 45;
        private const int Siege = 46;
        private const int Victory = 47;
        private const int Defeat = 48;

        // vanilla theme -> ours. Vanilla numbers are enum TaleWorlds.MountAndBlade.MusicTheme.
        private static readonly Dictionary<int, int> Map = new Dictionary<int, int>
        {
            { 5, Menu },                                                   // Main Theme
            { 1, MapCalm },                                                // Campaign Standard
            { 28, MapCalm }, { 29, MapCalm }, { 30, MapCalm }, { 31, MapCalm },  // map per culture
            { 32, MapCalm }, { 33, MapCalm }, { 34, MapCalm },
            { 10247, MapCalm }, { 10248, MapCalm }, { 10249, MapCalm },    // northern campaign and naval
            { 7, MapDark },                                                // Campaign Dark
            { 3, MapDark }, { 16, MapDark }, { 18, MapDark },              // "dramatic" map per culture
            { 20, MapDark }, { 22, MapDark }, { 24, MapDark },
            { 12, BattleSmall }, { 36, BattleSmall }, { 27, BattleSmall }, { 8, BattleSmall },
            { 10, BattleMedium }, { 35, BattleMedium }, { 6, BattleMedium },
            { 9, BattleMedium }, { 11, BattleMedium },                     // battle turning point
            { 14, BattleMedium }, { 15, BattleMedium },                    // sharp turning point
            { 39, BattleMedium }, { 40, BattleMedium }, { 10246, BattleMedium },
            { 10241, BattleMedium }, { 10242, BattleMedium }, { 10243, BattleMedium }, { 10244, Menu },
            { 13, Siege }, { 38, Siege },                                  // siege
            { 2, Victory }, { 4, Victory }, { 17, Victory }, { 19, Victory },
            { 21, Victory }, { 23, Victory }, { 25, Victory },
            { 26, Defeat },
        };

        private static readonly HashSet<int> Logged = new HashSet<int>();

        // We patch psai itself (TaleWorlds.PSAI.dll): the game starts menu music through MenuModeEnter,
        // and the map and battle through TriggerMusicTheme, so MBMusicManager.StartTheme alone is not enough.
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
                // Harmony matches parameters by name: for TriggerMusicTheme it is themeId, for MenuModeEnter menuThemeId
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
