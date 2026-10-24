using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using HarmonyLib;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.CampaignSystem.ViewModelCollection;
using TaleWorlds.Core;
using TaleWorlds.Core.ViewModelCollection.Information;
using TaleWorlds.Library;
using TaleWorlds.Localization;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Настройка ассимиляции расы (см. EquestriaRaceAssimilation.cs) консольными командами — тот
    // же приём, что equestria.helmet_scale/helmet_offset у EquestriaHelmetTest: подбираем вживую,
    // финальные числа вписываем в дефолты EquestriaRaceAssimilation руками, без персистентной
    // настройки.
    public static class EquestriaRaceAssimilationCommands
    {
        // equestria.race_assim_range <km> — радиус, в котором соседние поселения давят своей расой.
        // Ответ на английском — кириллицу консоль Bannerlord не рендерит (только "?", замечено в
        // игре 07.10.2026), русские строки остаются только в логе (EquestriaCrashLog, файл) и в
        // родной подсказке карты (та рисуется шрифтом игры, не консоли).
        [CommandLineFunctionality.CommandLineArgumentFunction("race_assim_range", "equestria")]
        public static string SetRange(List<string> args)
        {
            if (args == null || args.Count != 1 || !float.TryParse(args[0], NumberStyles.Float,
                    CultureInfo.InvariantCulture, out float km) || km <= 0f || km > 500f)
            {
                return $"Give a radius in km (now {EquestriaRaceAssimilation.InfluenceRange:0.#}), "
                    + "e.g. equestria.race_assim_range 30";
            }
            EquestriaRaceAssimilation.InfluenceRange = km;
            EquestriaCrashLog.Log($"ассимиляция расы: radius -> {km:0.#}");
            return $"Assimilation influence radius: {km:0.#} km.";
        }

        // equestria.race_assim_delay <days> — за сколько дней доля расы проходит путь до цели
        // (экспоненциально, не линейно — см. комментарий в RaceAssimilationStatus.OnDailyTick)
        [CommandLineFunctionality.CommandLineArgumentFunction("race_assim_delay", "equestria")]
        public static string SetDelay(List<string> args)
        {
            if (args == null || args.Count != 1 || !int.TryParse(args[0], out int days) || days <= 0 || days > 3650)
            {
                return $"Give a number of days (now {EquestriaRaceAssimilation.AssimilationDelay}), "
                    + "e.g. equestria.race_assim_delay 45";
            }
            EquestriaRaceAssimilation.AssimilationDelay = days;
            EquestriaCrashLog.Log($"ассимиляция расы: delay -> {days}");
            return $"Assimilation delay: {days} days.";
        }

        // equestria.race_assim_owner <weight> — во сколько раз сильнее давит текущий владелец
        // поселения (его раса/культура) относительно базового веса соседней деревни
        [CommandLineFunctionality.CommandLineArgumentFunction("race_assim_owner", "equestria")]
        public static string SetOwnerWeight(List<string> args)
        {
            if (args == null || args.Count != 1 || !int.TryParse(args[0], out int weight) || weight < 0 || weight > 100)
            {
                return $"Give an owner weight (now {EquestriaRaceAssimilation.OwnerInfluenceStrength}), "
                    + "e.g. equestria.race_assim_owner 5";
            }
            EquestriaRaceAssimilation.OwnerInfluenceStrength = weight;
            EquestriaCrashLog.Log($"ассимиляция расы: owner weight -> {weight}");
            return $"Owner influence weight: {weight}.";
        }

        // equestria.race_assim_trade on|off — учитывать ли деревни города/замка как его соседей
        // независимо от расстояния (торговая связь)
        [CommandLineFunctionality.CommandLineArgumentFunction("race_assim_trade", "equestria")]
        public static string SetTradeLinked(List<string> args)
        {
            if (args == null || args.Count != 1 || (args[0] != "on" && args[0] != "off"))
            {
                return "Usage: equestria.race_assim_trade on|off (now "
                    + (EquestriaRaceAssimilation.TradeLinkedInfluence ? "on" : "off") + ")";
            }
            EquestriaRaceAssimilation.TradeLinkedInfluence = args[0] == "on";
            EquestriaCrashLog.Log("ассимиляция расы: trade-linked -> " + EquestriaRaceAssimilation.TradeLinkedInfluence);
            return "Trade link: " + (EquestriaRaceAssimilation.TradeLinkedInfluence ? "on" : "off") + ".";
        }

        // equestria.race_assim_cap <percent> — потолок доли доминирующей расы (1-99), остаток
        // размазывается поровну по всем остальным играбельным расам (см. RecalculateInfluencers)
        [CommandLineFunctionality.CommandLineArgumentFunction("race_assim_cap", "equestria")]
        public static string SetCap(List<string> args)
        {
            if (args == null || args.Count != 1 || !float.TryParse(args[0], NumberStyles.Float,
                    CultureInfo.InvariantCulture, out float pct) || pct < 1f || pct > 99f)
            {
                return $"Give a percent 1-99 (now {EquestriaRaceAssimilation.MaxDominantShare * 100m:0.#}), "
                    + "e.g. equestria.race_assim_cap 85";
            }
            EquestriaRaceAssimilation.MaxDominantShare = (decimal)pct / 100m;
            EquestriaCrashLog.Log($"ассимиляция расы: cap -> {pct:0.#}%");
            return $"Dominant race cap: {pct:0.#}%.";
        }

        // equestria.race_assim_report [settlement StringId] — без аргумента берёт то, где сейчас
        // стоит игрок (или ближайшее к нему); иначе ищет по подстроке StringId (англ. — его и
        // нужно вводить, см. race_assim_near) или по русскому имени (не наберёшь в консоли, но
        // работает, если скопировано из другого источника).
        [CommandLineFunctionality.CommandLineArgumentFunction("race_assim_report", "equestria")]
        public static string Report(List<string> args)
        {
            try
            {
                return ReportInner(args);
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Warn("ассимиляция расы: race_assim_report упал: " + e.GetType().Name
                    + ": " + e.Message + "\r\n" + e.StackTrace);
                return "Error, see eq_exceptions.log: " + e.Message;
            }
        }

        private static string ReportInner(List<string> args)
        {
            if (Campaign.Current == null)
            {
                return "Campaign only.";
            }
            Settlement settlement = FindSettlement(args != null && args.Count > 0 ? args[0] : null);
            if (settlement == null)
            {
                return "Settlement not found — try equestria.race_assim_near to list StringIds.";
            }
            if (RaceAssimilationManager.Instance.InfluenceMap.Count == 0)
            {
                RaceAssimilationManager.Instance.Initialize();
            }
            if (!RaceAssimilationManager.Instance.InfluenceMap.TryGetValue(settlement.StringId, out RaceAssimilationStatus status))
            {
                return $"{settlement.StringId}: no assimilation data.";
            }

            var lines = new List<string>
            {
                $"{settlement.StringId} ({settlement.Culture.StringId}) — current culture: "
                    + $"{RaceLabel(settlement.Culture.StringId)}, homeland: {RaceLabel(status.HomelandCultureId)}",
                $"Days since target changed: {status.DaysSinceTargetsChanged}",
                "Current share:",
            };
            foreach (var pair in status.CurrentInfluences.OrderByDescending(p => p.Value))
            {
                lines.Add($"  {RaceLabel(pair.Key)}: {pair.Value * 100:0.#}%");
            }
            lines.Add("Target:");
            foreach (var pair in status.TargetInfluences.OrderByDescending(p => p.Value))
            {
                lines.Add($"  {RaceLabel(pair.Key)}: {pair.Value * 100:0.#}%");
            }
            string report = string.Join("\n", lines);
            EquestriaCrashLog.Log("ассимиляция расы: " + settlement.Name + " | " + report.Replace("\n", " | "));
            return report;
        }

        // equestria.race_assim_set <settlement StringId> <race>=<percent> [...] — тестовая подмена
        // ТЕКУЩЕЙ доли расы поселения (для проверки подсказки/таблицы), race — английское имя
        // (Pony/Changeling/Griffon/Hippogriff/Dragon/Yak/Deer), не id культуры. Target не трогает —
        // на ближайшем дневном тике (или equestria.race_assim_report дёрнет Initialize, но не
        // пересчёт) Current снова поедет к настоящей цели как обычно, подмена разовая.
        [CommandLineFunctionality.CommandLineArgumentFunction("race_assim_set", "equestria")]
        public static string SetInfluences(List<string> args)
        {
            try
            {
                return SetInfluencesInner(args);
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Warn("ассимиляция расы: race_assim_set упал: " + e.GetType().Name
                    + ": " + e.Message + "\r\n" + e.StackTrace);
                return "Error, see eq_exceptions.log: " + e.Message;
            }
        }

        private static string SetInfluencesInner(List<string> args)
        {
            if (Campaign.Current == null)
            {
                return "Campaign only.";
            }
            if (args == null || args.Count < 2)
            {
                return "Usage: equestria.race_assim_set <settlement id> <race>=<percent> [...], "
                    + "e.g. equestria.race_assim_set village_empire_0 Pony=25 Yak=25 Changeling=25";
            }
            Settlement settlement = FindSettlement(args[0]);
            if (settlement == null)
            {
                return "Settlement not found — try equestria.race_assim_near to list StringIds.";
            }
            if (RaceAssimilationManager.Instance.InfluenceMap.Count == 0)
            {
                RaceAssimilationManager.Instance.Initialize();
            }
            if (!RaceAssimilationManager.Instance.InfluenceMap.TryGetValue(settlement.StringId, out RaceAssimilationStatus status))
            {
                return $"{settlement.StringId}: no assimilation data.";
            }
            var parsed = new Dictionary<string, decimal>();
            for (int i = 1; i < args.Count; i++)
            {
                string[] parts = args[i].Split('=');
                if (parts.Length != 2 || !decimal.TryParse(parts[1], NumberStyles.Float,
                        CultureInfo.InvariantCulture, out decimal pct))
                {
                    return $"Bad entry '{args[i]}', expected race=percent, e.g. Pony=25";
                }
                string cultureId = CultureIdForRace(parts[0]);
                if (cultureId == null)
                {
                    return $"Unknown race '{parts[0]}', known: {string.Join(", ", RaceByCulture.Values)}";
                }
                parsed[cultureId] = pct / 100m;
            }
            // Доли всегда должны складываться в 100% — так же, как и настоящую Target нормирует
            // RecalculateInfluencers делением на сумму влияния (EquestriaRaceAssimilation.cs).
            // Введённые числа — это ОТНОСИТЕЛЬНЫЕ веса, не обязаны сами по себе давать 100 (замечено
            // пользователем 07.10.2026: Pony=25 Yak=25 Changeling=25 давало в сумме только 75%,
            // остаток нигде не отображался и не существовал — состояние, недостижимое в реальной
            // игре). Нормируем к сумме 1 перед записью.
            decimal total = parsed.Values.Sum();
            if (total <= 0m)
            {
                return "Percentages must sum to more than 0.";
            }
            var normalized = parsed.ToDictionary(p => p.Key, p => p.Value / total);
            status.CurrentInfluences = normalized;
            EquestriaCrashLog.Log("ассимиляция расы (set): " + settlement.StringId + " -> "
                + string.Join(", ", normalized.Select(p => $"{p.Key}={p.Value * 100:0.#}%")));
            return $"{settlement.StringId}: current share set to "
                + string.Join(", ", normalized.Select(p => $"{RaceLabel(p.Key)}={p.Value * 100:0.#}%"))
                + " (normalized to 100%)";
        }

        private static string CultureIdForRace(string race)
        {
            foreach (var pair in RaceByCulture)
            {
                if (string.Equals(pair.Value, race, StringComparison.OrdinalIgnoreCase))
                {
                    return pair.Key;
                }
            }
            return null;
        }

        // equestria.race_assim_near [км] — список ближайших к партии поселений: англ. StringId (его
        // безопасно набирать — консоль Bannerlord плохо принимает кириллицу) + русское имя для
        // опознания + текущая раса. Дальше StringId можно передать в race_assim_report/_delay и
        // т.п. без единой русской буквы. По умолчанию радиус 20 км, без параметра.
        [CommandLineFunctionality.CommandLineArgumentFunction("race_assim_near", "equestria")]
        public static string Near(List<string> args)
        {
            try
            {
                return NearInner(args);
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Warn("ассимиляция расы: race_assim_near упал: " + e.GetType().Name
                    + ": " + e.Message + "\r\n" + e.StackTrace);
                return "Error, see eq_exceptions.log: " + e.Message;
            }
        }

        private static string NearInner(List<string> args)
        {
            if (Campaign.Current == null || MobileParty.MainParty == null)
            {
                return "Campaign only.";
            }
            float km = args != null && args.Count > 0
                && float.TryParse(args[0], NumberStyles.Float, CultureInfo.InvariantCulture, out float n)
                ? n : 20f;
            Vec2 pos = MobileParty.MainParty.GetPosition2D;
            var near = Settlement.All.Where(s => s.IsVillage || s.IsCastle || s.IsTown)
                .Select(s => (settlement: s, dist: s.GetPosition2D.Distance(pos)))
                .Where(t => t.dist <= km)
                .OrderBy(t => t.dist)
                .Take(25)
                .ToList();
            if (near.Count == 0)
            {
                return $"No settlements within {km:0.#} km.";
            }
            var lines = new List<string> { $"Settlements within {km:0.#} km ({near.Count}):" };
            foreach (var (settlement, dist) in near)
            {
                lines.Add($"  {settlement.StringId}  ({dist:0.#} km, {RaceLabel(settlement.Culture.StringId)})");
                // Русское имя — только в лог (консоль его не отрисует, см. комментарий выше), для
                // сверки с тем, что видно на карте.
                EquestriaCrashLog.Log("ассимиляция расы (near): " + settlement.StringId + " = " + settlement.Name);
            }
            return string.Join("\n", lines);
        }

        // Culture id в этом моде — ванильные английские id (empire/aserai/vlandia/battania/sturgia/
        // khuzait/nord), а раса рекрута жёстко запечена на культуру при сборке войск (tools/
        // make_troops.py, CULTURE_RACE) — тот же маппинг здесь, только английскими словами (консоль
        // не рендерит кириллицу, см. комментарии выше). Неизвестный id — отдаём как есть, тоже
        // латиницей.
        private static readonly Dictionary<string, string> RaceByCulture =
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            { "empire", "Pony" }, { "aserai", "Changeling" }, { "vlandia", "Griffon" },
            { "battania", "Hippogriff" }, { "sturgia", "Dragon" }, { "khuzait", "Yak" }, { "nord", "Deer" },
        };

        private static string RaceLabel(string cultureId)
        {
            return RaceByCulture.TryGetValue(cultureId ?? "", out string label) ? label : cultureId;
        }

        private static Settlement FindSettlement(string query)
        {
            if (!string.IsNullOrEmpty(query))
            {
                return Settlement.All.FirstOrDefault(s =>
                    s.StringId.IndexOf(query, StringComparison.OrdinalIgnoreCase) >= 0
                    || s.Name.ToString().IndexOf(query, StringComparison.OrdinalIgnoreCase) >= 0);
            }
            if (Settlement.CurrentSettlement != null)
            {
                return Settlement.CurrentSettlement;
            }
            if (MobileParty.MainParty == null)
            {
                return null;
            }
            Vec2 pos = MobileParty.MainParty.GetPosition2D;
            return Settlement.All.Where(s => s.IsVillage || s.IsCastle || s.IsTown)
                .OrderBy(s => s.GetPosition2D.DistanceSquared(pos)).FirstOrDefault();
        }
    }

    // Подсказка поселения: строка «Раса» + разбивка по расам с дневной динамикой — тот же приём,
    // что у UpdateTooltipPatch в оригинале DynaCulture, но патчим актуальный для этой версии игры
    // метод: в их коде был TooltipVM.OpenTooltip (устаревшее API), здесь подсказки строятся через
    // TooltipRefresherCollection.RefreshSettlementTooltip(PropertyBasedTooltipVM, object[] args) —
    // нашли через decompile SandBox.View.dll (SandBoxViewSubModule регистрирует этот рефрешер на
    // Settlement через InformationManager.RegisterTooltip).
    //
    // НЕ атрибутом [HarmonyPatch] (бланкетный PatchAll подхватил бы его сразу при загрузке мода) и
    // НЕ в EquestriaPatches.ApplyLate (там тоже рано — проверено на практике 06.10.2026, см. ниже).
    // Причина: RefreshSettlementTooltip сам, в своём теле, напрямую зовёт
    // CampaignUIHelper.IsSettlementInformationHidden(...) — а у CampaignUIHelper есть статическое
    // поле-инициализатор (_partyMoraleStr = GameTexts.FindText("str_party_morale")), которое
    // выполняется в статическом конструкторе типа РОВНО ТОГДА, когда Harmony впервые JIT-компилирует
    // (pin) метод для патча — не важно, когда вызвать Apply: при загрузке мода, на главном меню
    // (ApplyLate) — в обоих случаях таблица строк игры ещё не загружена, GameTexts.FindText
    // возвращает null, внутри бросается NullReferenceException, и CampaignUIHelper НАВСЕГДА
    // помечается неинициализированным (так работают статические конструкторы в .NET — не
    // перезапускаются). Дальше любое обращение к этому типу (а его трогает родной MapBarVM.
    // Initialize при каждом построении экрана карты) валит TypeInitializationException — экран
    // карты не строится, QuickStart не может пропустить создание персонажа.
    // Подтверждено экспериментально: с этим патчем, применённым в ApplyLate, — краш, без патча
    // вовсе — быстрый старт доходит до карты и ассимиляция расы инициализируется на 410
    // поселениях без единой ошибки (eq_exceptions.log, два тестовых запуска подряд).
    // РЕШЕНИЕ: патчим не раньше, чем кампания реально затикала (EquestriaRaceAssimilation.
    // OnDailyTickSettlement, лениво на первом тике) — к этому моменту движок уже сам успешно
    // построил карту и тронул CampaignUIHelper родным путём, повторный Harmony-JIT ничего не
    // триггерит заново.
    internal static class RaceAssimilationTooltipPatch
    {
        public static void Apply(Harmony harmony)
        {
            var method = AccessTools.Method(typeof(TooltipRefresherCollection),
                nameof(TooltipRefresherCollection.RefreshSettlementTooltip));
            if (method == null)
            {
                EquestriaCrashLog.Warn("ассимиляция расы: TooltipRefresherCollection.RefreshSettlementTooltip не найден — подсказка не будет показывать расу");
                return;
            }
            harmony.Patch(method, postfix: new HarmonyMethod(typeof(RaceAssimilationTooltipPatch), nameof(Postfix)));
            EquestriaCrashLog.Log("ассимиляция расы: патч подсказки поселения поставлен");
        }

        private static void Postfix(PropertyBasedTooltipVM propertyBasedTooltipVM, object[] args)
        {
            try
            {
                if (args == null || args.Length == 0 || !(args[0] is Settlement settlement))
                {
                    return;
                }
                if (!(settlement.IsVillage || settlement.IsCastle || settlement.IsTown))
                {
                    return;
                }
                if (RaceAssimilationManager.Instance.InfluenceMap.Count == 0)
                {
                    RaceAssimilationManager.Instance.Initialize();
                }
                if (!RaceAssimilationManager.Instance.InfluenceMap.TryGetValue(settlement.StringId, out RaceAssimilationStatus status)
                    || status.CurrentInfluences.Count == 0)
                {
                    return;
                }

                propertyBasedTooltipVM.AddProperty(string.Empty, string.Empty, -1, TooltipProperty.TooltipPropertyFlags.RundownSeperator);
                propertyBasedTooltipVM.AddProperty(new TextObject("{=eq_race_tooltip}Race").ToString(), " ", 0,
                    TooltipProperty.TooltipPropertyFlags.Title);
                // Скрываем так же, как игра сама прячет "Отряды ???" — тем же CampaignUIHelper.
                // IsSettlementInformationHidden, что и родные свойства поселения (по просьбе
                // пользователя 07.10.2026: раса не должна быть видна игроку раньше, чем остальная
                // подробная информация о чужом поселении). Метод тот самый, из-за которого раньше
                // был краш преждевременной инициализации (см. комментарий у Apply выше) — здесь он
                // уже безопасен: подсказка строится только после первого тика кампании.
                if (CampaignUIHelper.IsSettlementInformationHidden(settlement, out TextObject _))
                {
                    propertyBasedTooltipVM.AddProperty(" ", GameTexts.FindText("str_missing_info_indicator").ToString());
                    return;
                }
                // "сейчас -> цель" на каждую расу, а не крошечная дневная дельта — так сразу видно,
                // куда и насколько далеко едет доля, не только что она чуть шевельнулась за день
                // (по просьбе пользователя 07.10.2026: "будет понятно сколько имеем сейчас и к
                // какому числу стремится"). Объединяем ключи обоих словарей — расы, которых пока
                // совсем нет в Current, но уже наметились в Target (только начали давить соседи),
                // тоже должны быть видны.
                var cultureIds = status.CurrentInfluences.Keys.Union(status.TargetInfluences.Keys)
                    .OrderByDescending(id => status.CurrentInfluences.TryGetValue(id, out decimal c) ? c : 0m);
                foreach (string cultureId in cultureIds)
                {
                    CultureObject culture = MBObjectManager.Instance.GetObject<CultureObject>(cultureId);
                    string label = culture != null ? culture.Name.ToString() : cultureId;
                    decimal current = status.CurrentInfluences.TryGetValue(cultureId, out decimal c) ? c * 100m : 0m;
                    decimal target = status.TargetInfluences.TryGetValue(cultureId, out decimal t) ? t * 100m : 0m;
                    propertyBasedTooltipVM.AddProperty(label, $"{current:0.#}% -> {target:0.#}%");
                }
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Warn("подсказка ассимиляции расы: " + e.Message);
            }
        }
    }
}
