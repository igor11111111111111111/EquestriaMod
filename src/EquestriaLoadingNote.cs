using System;
using HarmonyLib;
using TaleWorlds.Engine;
using TaleWorlds.Library;
using TaleWorlds.Localization;
using TaleWorlds.MountAndBlade.GauntletUI;

namespace EquestriaMod
{
    // Строка о сборке шейдеров прямо на загрузочном экране.
    //
    // У загрузочного окна есть готовое место для текста: LoadingWindowViewModel.DescriptionText —
    // та самая подпись под картинкой, где игра пишет советы. Окно обновляет себя методом Update,
    // и достаточно после него подставить свой текст. Так же это делает The Old Realms
    // (TOR_Core.HarmonyPatches.LoadingScreenPatches) — мод показывает «Shader compilation in
    // progress. Remaining shaders to compile: N».
    //
    // Число незаконченных сборок отдаёт сам движок: Utilities.GetNumberOfShaderCompilationsInProgress.
    // Оно общее на игру, а не только наше, но во время загрузки кампании собираются как раз наши
    // варианты — ванильные давно лежат в Shaders\D3D11\compressed_shader_cache.sack.
    public static class EquestriaLoadingNote
    {
        // Сколько сборок было в разгар: по нему считается, сколько уже сделано
        private static int _peak;
        private static string _extra;      // что ещё написать рядом (например, «прогрев начат»)

        // Тексты с переводом: английский по умолчанию, русский и остальные — из языковых файлов
        // (tools/make_world.py, HAND_WRITTEN). TextObject держим готовыми: подпись обновляется каждый кадр.
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

        // Постфикс окна загрузки: подменяем подпись, пока идёт сборка шейдеров.
        private static void AfterUpdate(LoadingWindowViewModel __instance)
        {
            try
            {
                var left = Utilities.GetNumberOfShaderCompilationsInProgress();
                if (left <= 0)
                {
                    // Сборка ещё не началась, но прогрев уже раздаёт меши — покажем и это,
                    // иначе окно молчит как раз в самое долгое время.
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
                // подпись — дело десятое, ронять из-за неё загрузку нельзя
            }
        }

        /// <summary>Приписка к строке загрузки (чем занят мод), например «греем броню улья».</summary>
        public static void Note(string text)
        {
            _extra = text;
        }

        /// <summary>Приписка «броня улья» на языке игрока.</summary>
        public static string HiveArmourNote()
        {
            return HiveNote.ToString();
        }

        /// <summary>Сообщение слева вверху: видно уже на карте, когда загрузка кончилась.</summary>
        public static void Show(string text)
        {
            try
            {
                InformationManager.DisplayMessage(new InformationMessage(text, Colors.Magenta));
            }
            catch (Exception)
            {
                // до создания кампании сообщений ещё нет — не беда
            }
        }
    }
}
