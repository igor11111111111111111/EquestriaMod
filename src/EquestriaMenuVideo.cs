using System;
using System.IO;
using System.Reflection;
using HarmonyLib;
using TaleWorlds.Engine;
using Path = System.IO.Path;

namespace EquestriaMod
{
    // Видео на фоне главного меню — только наше.
    //
    // Игра сама просматривает Videos\initial_menu\<папка>\ у КАЖДОГО активного модуля, собирает
    // пары «*_pc.ivf + *.ogg» и на каждом показе меню берёт случайную (MBInitialScreenBase
    // .RefreshScene). Native — активный модуль всегда, так что его восемь ванильных роликов из
    // списка не убрать: наш выпадал бы раз из девяти. Поэтому подменяем путь в самом
    // VideoPlayerView.PlayVideo: что бы игра ни выбрала из initial_menu, играет наш файл.
    //
    // Наш ролик: Module\Videos\initial_menu\equestria\1440p_pc.ivf + *.ogg. Формат тот же, что у
    // ванили: IVF с VP8, звук отдельным OGG, 24 кадра/с (частота зашита в игре). Как собрать ролик
    // из mp4 — docs/menu_video.md. Пока файлов нет, патч ничего не подменяет, меню остаётся ванильным.
    public static class EquestriaMenuVideo
    {
        private const string Folder = "equestria";
        private const string Marker = "initial_menu";

        private static string _video;
        private static string _sound;
        private static bool _resolved;
        private static bool _logged;

        public static void Apply(Harmony harmony)
        {
            var play = AccessTools.Method(typeof(VideoPlayerView), "PlayVideo");
            if (play == null)
            {
                EquestriaCrashLog.Warn("видео меню: у VideoPlayerView нет PlayVideo — подмена не поставлена");
                return;
            }
            harmony.Patch(play, prefix: new HarmonyMethod(typeof(EquestriaMenuVideo), nameof(BeforePlay)));
            EquestriaCrashLog.Log("видео меню: PlayVideo перехвачен");
        }

        // Наши файлы ищем рядом с нашей DLL: <мод>\bin\Win64_Shipping_Client -> <мод>\Videos.
        private static void Resolve()
        {
            _resolved = true;
            try
            {
                string bin = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
                string root = Path.GetFullPath(Path.Combine(bin, "..", ".."));
                string folder = Path.Combine(root, "Videos", Marker, Folder);
                if (!Directory.Exists(folder))
                {
                    return;
                }
                var video = Directory.GetFiles(folder, "*_pc.ivf");
                var sound = Directory.GetFiles(folder, "*.ogg");
                if (video.Length > 0 && sound.Length > 0)
                {
                    _video = video[0];
                    _sound = sound[0];
                }
            }
            catch (Exception error)
            {
                EquestriaCrashLog.Warn("видео меню: не нашли свои файлы — " + error.Message);
            }
        }

        // Подменяем только ролики меню: заставка с логотипами и остальное идёт этим же методом.
        private static void BeforePlay(ref string videoFileName, ref string soundFileName)
        {
            if (videoFileName == null
                || videoFileName.IndexOf(Marker, StringComparison.OrdinalIgnoreCase) < 0)
            {
                return;
            }
            if (!_resolved)
            {
                Resolve();
            }
            if (_video == null)
            {
                return;
            }
            if (!_logged)
            {
                _logged = true;
                EquestriaCrashLog.Log("видео меню: вместо " + Path.GetFileName(Path.GetDirectoryName(videoFileName))
                    + " играет " + _video);
            }
            videoFileName = _video;
            soundFileName = _sound;
        }
    }
}
