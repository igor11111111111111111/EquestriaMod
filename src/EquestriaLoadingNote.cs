using System;
using HarmonyLib;
using TaleWorlds.Engine;
using TaleWorlds.Library;
using TaleWorlds.Localization;
using TaleWorlds.MountAndBlade.GauntletUI;

namespace EquestriaMod
{
    // A line about shader compilation right on the loading screen.
    //
    // The loading window has a ready place for text: LoadingWindowViewModel.DescriptionText -
    // the very caption under the picture where the game writes tips. The window updates itself with the Update
    // method, and it is enough to substitute our own text after it. The Old Realms does the same
    // (TOR_Core.HarmonyPatches.LoadingScreenPatches) - the mod shows «Shader compilation in
    // progress. Remaining shaders to compile: N».
    //
    // The number of unfinished compilations comes from the engine itself: Utilities.GetNumberOfShaderCompilationsInProgress.
    // It is global for the game, not just ours, but during campaign loading it is exactly our
    // variants being compiled - the vanilla ones have long been in Shaders\D3D11\compressed_shader_cache.sack.
    public static class EquestriaLoadingNote
    {
        // How many compilations there were at the peak: used to compute how many are already done
        private static int _peak;
        private static string _extra;      // what else to write next to it (for example, "warm-up started")

        // Translated texts: English by default, Russian and the rest from the language files
        // (tools/make_world.py, HAND_WRITTEN). TextObjects are kept ready: the caption is updated every frame.
        private static readonly TextObject Preparing =
            new TextObject("{=eq_load_preparing}Equestria: preparing shaders - {NOTE}");
        private static readonly TextObject Compiling =
            new TextObject("{=eq_load_compiling}Equestria: compiling shaders - {LEFT} of {PEAK} left{NOTE}");
        private static readonly TextObject HiveNote = new TextObject("{=eq_load_hive}hive armour");

        public static void Apply(Harmony harmony)
        {
            var update = AccessTools.Method(typeof(LoadingWindowViewModel), "Update");
            if (update == null)
            {
                EquestriaCrashLog.Warn("надпись на загрузке: у окна нет метода Update — пропускаем");
                return;
            }
            harmony.Patch(update, postfix: new HarmonyMethod(
                AccessTools.Method(typeof(EquestriaLoadingNote), nameof(AfterUpdate))));
            EquestriaCrashLog.Log("надпись на загрузке: подпись окна перехвачена");
        }

        // Loading window postfix: replace the caption while shaders are being compiled.
        private static void AfterUpdate(LoadingWindowViewModel __instance)
        {
            try
            {
                var left = Utilities.GetNumberOfShaderCompilationsInProgress();
                if (left <= 0)
                {
                    // Compilation has not started yet, but the warm-up is already handing out meshes - show that too,
                    // otherwise the window is silent exactly during the longest time.
                    if (_extra != null)
                    {
                        __instance.DescriptionText = Preparing.SetTextVariable("NOTE", _extra).ToString();
                    }
                    return;
                }
                _peak = Math.Max(_peak, left);
                __instance.DescriptionText = Compiling
                    .SetTextVariable("LEFT", left).SetTextVariable("PEAK", _peak)
                    .SetTextVariable("NOTE", _extra == null ? "" : ". " + _extra).ToString();
            }
            catch (Exception)
            {
                // the caption is a minor matter, the loading must not crash because of it
            }
        }

        /// <summary>Addition to the loading line (what the mod is busy with), e.g. "warming up hive armour".</summary>
        public static void Note(string text)
        {
            _extra = text;
        }

        /// <summary>The "hive armour" addition in the player's language.</summary>
        public static string HiveArmourNote()
        {
            return HiveNote.ToString();
        }

        /// <summary>Message at the top left: visible already on the map once loading has finished.</summary>
        public static void Show(string text)
        {
            try
            {
                InformationManager.DisplayMessage(new InformationMessage(text, Colors.Magenta));
            }
            catch (Exception)
            {
                // before the campaign is created there are no messages yet - no problem
            }
        }
    }
}
