using System;
using TaleWorlds.Localization;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using TaleWorlds.CampaignSystem;
using TaleWorlds.Core;
using TaleWorlds.Engine;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Shader warm-up: ask the engine in advance to build the shader variants for our armour while
    // the player is waiting on the loading screen.
    //
    // Why. The game keeps compiled shaders in a single file Shaders\D3D11\compressed_shader
    // _cache.sack and NEVER appends to it: whatever is missing is built on the fly from the sources in
    // Shaders\Sources. The hive armour has a glowing material (self_illumination) on a skinned
    // mesh - vanilla has no such combination at all (only static candles and lanterns glow),
    // so its variant has to be built the first time right in the game. Without the warm-up this happened
    // in the encyclopedia screen: portraits did not appear and the game hung (noticed 24.09.2026).
    //
    // MetaMesh.PreloadShaders(useTableau, useTeamColor) does exactly what is needed and, most importantly,
    // separately prepares the variant FOR SCREENS (tableau), where the hang used to happen.
    //
    // The second launch is faster not because of the game: the graphics driver stores the built
    // shaders on its side. The warm-up only moves the wait to the loading screen, where it is tolerable
    // and labelled (see EquestriaLoadingNote).
    public static class EquestriaShaderWarmup
    {
        // Warm up ONLY our own armour: its materials have a flag combination unusual for the engine.
        // Race body parts (eq_twilight_tail, eq_changeling_wings and others) use ordinary
        // materials whose variants were built long ago - no point spending the warm-up on them. The first
        // version took the first four meshes in a row, those turned out to be body parts, and the warm-up
        // reported "done in 0.0 s" without building anything useful (noticed 24.09.2026).
        private const string MeshPrefix = "eq_ch_";
        private const double ReportEverySeconds = 2.0;
        // How many armour meshes to warm up. All 43 gave 1327 builds and too long a load
        // (noticed 24.09.2026). Ten are enough to build the shader variants themselves: they
        // are counted per COMBINATION of material flags and vertex layout, not per mesh.
        // How many builds each mesh adds is visible in the log - we tune by those numbers.
        private const int MeshLimit = 10;

        private static bool _started;
        private static bool _finished;
        private static int _done;              // how many meshes have been sent for building
        private static int _total;             // how many there are in total
        private static int _peak;              // how many builds there were at the peak
        private static int _wasQueued;         // how many builds there were before the previous mesh
        private static double _reportedAt;
        private static Stopwatch _clock;
        private static readonly Queue<string> _queue = new Queue<string>();

        /// <summary>Builds the mesh queue. Returns false if there are no items yet.</summary>
        private static bool Start()
        {
            if (_started)
            {
                return true;
            }
            List<string> names;
            try
            {
                names = MeshNames().ToList();
            }
            catch (Exception error)
            {
                _finished = true;
                EquestriaCrashLog.Warn("прогрев шейдеров отменён: " + error.Message);
                return true;
            }
            if (names.Count == 0)
            {
                return false;       // items are parsed at campaign launch, wait
            }
            _started = true;
            _clock = Stopwatch.StartNew();
            names.Sort(StringComparer.Ordinal);
            foreach (var name in names.Take(MeshLimit))
            {
                _queue.Enqueue(name);
            }
            _total = _queue.Count;
            EquestriaCrashLog.Log($"прогрев шейдеров: в очереди мешей {_total} из {names.Count}");
            EquestriaLoadingNote.Note(EquestriaLoadingNote.HiveArmourNote());
            return true;
        }

        // Meshes are taken from the mod's items: their names are listed in equestria_items.xml, and in game
        // they are already parsed into ItemObject. That way the list does not have to be kept in a second copy.
        private static IEnumerable<string> MeshNames()
        {
            var names = new HashSet<string>();
            // In the main menu the object registry is not created yet: MBObjectManager.Instance is null here,
            // and accessing it crashed the game on the very first frame (noticed 24.09.2026).
            var manager = MBObjectManager.Instance;
            var items = manager?.GetObjectTypeList<ItemObject>();
            if (items == null)
            {
                return names;
            }
            foreach (var item in items)
            {
                var mesh = item?.MultiMeshName;
                if (!string.IsNullOrEmpty(mesh) && mesh.StartsWith(MeshPrefix, StringComparison.Ordinal))
                {
                    names.Add(mesh);
                }
            }
            return names;
        }

        /// <summary>Every frame: one mesh into the build, then wait for the engine to finish.</summary>
        public static void Tick()
        {
            if (_finished)
            {
                return;
            }
            if (!_started && !Start())
            {
                return;
            }
            // One mesh per frame: that way the loading screen has time to redraw and show
            // how much is left. Handing it all over at once is not allowed - the screen freezes.
            if (_queue.Count > 0)
            {
                var name = _queue.Dequeue();
                EquestriaCrashLog.Try("прогрев шейдеров: " + name, () =>
                {
                    // mayReturnNull: the package may not be parsed yet - such a mesh is simply skipped
                    var mesh = MetaMesh.GetCopy(name, false, true);
                    // useTableau: the variant for screens (encyclopedia, inventory, party),
                    // useTeamColor: the variant tinted in clan colours.
                    // PreloadForRendering is not called: it uploads textures into video memory
                    // (138 MB for the hive armour) and has nothing to do with building shaders.
                    mesh?.PreloadShaders(true, true);
                });
                _done++;
                // How many builds this particular mesh added: these numbers show whether meshes share
                // one shader variant (then the increment drops to zero) or each needs its own.
                var queued = Compilations();
                EquestriaCrashLog.Log($"прогрев шейдеров: {_done} из {_total} — {name}, "
                    + $"сборок в очереди {queued} (+{queued - _wasQueued})");
                _wasQueued = queued;
                return;
            }
            var left = Compilations();
            if (left < 0)
            {
                _finished = true;   // this engine build has no counter - exit silently
                return;
            }
            if (left > 0)
            {
                Report(left);
                return;
            }
            _finished = true;
            EquestriaCrashLog.Log($"прогрев шейдеров: готово, мешей {_done}, "
                + $"{_clock.Elapsed.TotalSeconds:0.0} с");
            EquestriaLoadingNote.Show(new TextObject("{=eq_note_shaders}Equestria: hive armour shaders built in {SECONDS} s")
                .SetTextVariable("SECONDS", _clock.Elapsed.TotalSeconds.ToString("0")).ToString());
        }

        // How many shader builds the engine has queued; -1 means this build has no counter.
        private static int Compilations()
        {
            try
            {
                return Utilities.GetNumberOfShaderCompilationsInProgress();
            }
            catch (Exception)
            {
                return -1;
            }
        }

        private static void Report(int left = -1)
        {
            if (_clock.Elapsed.TotalSeconds - _reportedAt < ReportEverySeconds)
            {
                return;
            }
            _reportedAt = _clock.Elapsed.TotalSeconds;
            if (left < 0)
            {
                EquestriaCrashLog.Log($"прогрев шейдеров: отправлено {_done} из {_total}, "
                    + $"прошло {_clock.Elapsed.TotalSeconds:0} с");
                return;
            }
            _peak = Math.Max(_peak, left);
            EquestriaCrashLog.Log($"прогрев шейдеров: собирается {left} из {_peak}, "
                + $"прошло {_clock.Elapsed.TotalSeconds:0} с");
        }
    }
}
