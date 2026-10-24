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
    // Прогрев шейдеров: заранее просим движок собрать варианты шейдера для нашей брони, пока
    // игрок ждёт загрузочный экран.
    //
    // Зачем. Скомпилированные шейдеры игра держит одним файлом Shaders\D3D11\compressed_shader
    // _cache.sack и НИКОГДА его не дописывает: чего в нём нет, то собирается на лету из исходников
    // Shaders\Sources. У брони улья материал со свечением (self_illumination) на скиннингованном
    // меше — в ванили такого сочетания нет вовсе (светятся только неподвижные свечи и фонари),
    // поэтому его вариант приходится собирать первый раз прямо в игре. Без прогрева это случалось
    // в окне энциклопедии: портреты не появлялись, игра висела (замечено 24.09.2026).
    //
    // MetaMesh.PreloadShaders(useTableau, useTeamColor) делает ровно то, что нужно, и главное —
    // отдельно готовит вариант ДЛЯ ОКОН (tableau), где и случалось зависание.
    //
    // Второй запуск быстрее уже не из-за игры: собранные шейдеры складывает у себя драйвер
    // видеокарты. Прогрев только переносит ожидание в загрузочный экран, где оно терпимо и
    // подписано (см. EquestriaLoadingNote).
    public static class EquestriaShaderWarmup
    {
        // Греем ТОЛЬКО свою броню: у неё материалы с непривычным движку сочетанием флагов.
        // Части тела рас (eq_twilight_tail, eq_changeling_wings и прочие) сидят на обычных
        // материалах, их варианты давно собраны — на них прогрев тратить нечего. Первая версия
        // брала первые четыре меша подряд, ими оказались как раз части тела, и прогрев отчитался
        // «готово за 0.0 с», не собрав ничего нужного (замечено 24.09.2026).
        private const string MeshPrefix = "eq_ch_";
        private const double ReportEverySeconds = 2.0;
        // Сколько мешей брони греем. Все 43 дали 1327 сборок и слишком долгую загрузку
        // (замечено 24.09.2026). Десяти хватает, чтобы собрать сами варианты шейдера: они
        // считаются на СОЧЕТАНИЕ флагов материала и разметки вершин, а не на каждый меш.
        // Сколько сборок добавляет каждый меш, видно в журнале — по этим числам и подбираем.
        private const int MeshLimit = 10;

        private static bool _started;
        private static bool _finished;
        private static int _done;              // сколько мешей уже отправлено на сборку
        private static int _total;             // сколько их всего
        private static int _peak;              // сколько сборок было в самый разгар
        private static int _wasQueued;         // сколько сборок было до прошлого меша
        private static double _reportedAt;
        private static Stopwatch _clock;
        private static readonly Queue<string> _queue = new Queue<string>();

        /// <summary>Собирает очередь мешей. Возвращает false, если предметов ещё нет.</summary>
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
                return false;       // предметы разбираются при запуске кампании, ждём
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

        // Меши берём у предметов мода: их имена перечислены в equestria_items.xml, и в игре они
        // уже разобраны в ItemObject. Так список не приходится держать вторым экземпляром.
        private static IEnumerable<string> MeshNames()
        {
            var names = new HashSet<string>();
            // В главном меню опись объектов ещё не создана: MBObjectManager.Instance тут null,
            // и обращение к нему валило игру на первом же кадре (замечено 24.09.2026).
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

        /// <summary>Каждый кадр: по одному мешу в сборку, потом ждём, пока движок закончит.</summary>
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
            // По одному мешу за кадр: так загрузочное окно успевает перерисоваться и показать,
            // сколько осталось. Разом это отдавать нельзя — окно замирает.
            if (_queue.Count > 0)
            {
                var name = _queue.Dequeue();
                EquestriaCrashLog.Try("прогрев шейдеров: " + name, () =>
                {
                    // mayReturnNull: пакет может быть ещё не разобран — такой меш просто пропускаем
                    var mesh = MetaMesh.GetCopy(name, false, true);
                    // useTableau: вариант для окон (энциклопедия, инвентарь, отряд),
                    // useTeamColor: вариант с покраской в цвета клана.
                    // PreloadForRendering не зовём: это заливка текстур в память видеокарты
                    // (у брони улья их 138 МБ), к сборке шейдера она отношения не имеет.
                    mesh?.PreloadShaders(true, true);
                });
                _done++;
                // Сколько сборок прибавил именно этот меш: по этим числам видно, делят ли меши
                // один вариант шейдера (тогда прибавка падает до нуля) или каждому нужен свой.
                var queued = Compilations();
                EquestriaCrashLog.Log($"прогрев шейдеров: {_done} из {_total} — {name}, "
                    + $"сборок в очереди {queued} (+{queued - _wasQueued})");
                _wasQueued = queued;
                return;
            }
            var left = Compilations();
            if (left < 0)
            {
                _finished = true;   // в этой сборке движка счётчика нет — молча выходим
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

        // Сколько сборок шейдеров в очереди у движка; -1 — счётчика в этой сборке нет.
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
