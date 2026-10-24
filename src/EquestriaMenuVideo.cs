using System;
using System.IO;
using System.Reflection;
using HarmonyLib;
using TaleWorlds.Engine;
using Path = System.IO.Path;

namespace EquestriaMod
{
    // The video in the main menu background: only ours.
    //
    // The game itself scans Videos\initial_menu\<folder>\ of EVERY active module, collects
    // "*_pc.ivf + *.ogg" pairs and on every menu display picks a random one (MBInitialScreenBase
    // .RefreshScene). Native is always an active module, so its eight vanilla videos cannot be removed
    // from the list: ours would come up once in nine. So we replace the path in
    // VideoPlayerView.PlayVideo itself: whatever the game picks from initial_menu, our file plays.
    //
    // Our video: Module\Videos\initial_menu\equestria\1440p_pc.ivf + *.ogg. The format is the same as
    // vanilla's: IVF with VP8, sound as a separate OGG, 24 fps (the rate is hardcoded in the game). How to build the video
    // from mp4: docs/menu_video.md. While there are no files, the patch replaces nothing and the menu stays vanilla.
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

        // Our files are searched for next to our DLL: <mod>\bin\Win64_Shipping_Client -> <mod>\Videos.
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

        // We replace only the menu videos: the logo intro and the rest go through this same method.
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
