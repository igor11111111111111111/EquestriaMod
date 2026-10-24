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
    // Tuning of race assimilation (see EquestriaRaceAssimilation.cs) via console commands - the
    // same trick as equestria.helmet_scale/helmet_offset in EquestriaHelmetTest: tune live,
    // then write the final numbers into the EquestriaRaceAssimilation defaults by hand, with no persistent
    // setting.
    public static class EquestriaRaceAssimilationCommands
    {
        // equestria.race_assim_range <km> - radius within which neighbouring settlements push their race.
        // The reply is in English - the Bannerlord console does not render Cyrillic (only "?", seen in
        // game 07.10.2026); Russian strings stay only in the log (EquestriaCrashLog, file) and in the
        // native map tooltip (that one is drawn with the game font, not the console's).
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

        // equestria.race_assim_delay <days> - how many days it takes a race share to travel to its target
        // (exponentially, not linearly - see the comment in RaceAssimilationStatus.OnDailyTick)
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

        // equestria.race_assim_owner <weight> - how many times stronger the current settlement owner
        // (their race/culture) pushes relative to the base weight of a neighbouring village
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

        // equestria.race_assim_trade on|off - whether a town's/castle's villages count as its neighbours
        // regardless of distance (trade link)
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

        // equestria.race_assim_cap <percent> - cap on the dominant race's share (1-99), the remainder
        // is spread evenly over all other playable races (see RecalculateInfluencers)
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

        // equestria.race_assim_report [settlement StringId] - with no argument takes the settlement where
        // the player stands now (or the nearest one); otherwise searches by a StringId substring (English - that
        // is what should be typed, see race_assim_near) or by the Russian name (cannot be typed in the console, but
        // works if copied from another source).
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

        // equestria.race_assim_set <settlement StringId> <race>=<percent> [...] - test override of the
        // CURRENT race share of a settlement (to check the tooltip/table), race is the English name
        // (Pony/Changeling/Griffon/Hippogriff/Dragon/Yak/Deer), not a culture id. Target is not touched -
        // on the next daily tick (or equestria.race_assim_report will call Initialize, but not a
        // recalculation) Current moves towards the real target again as usual, the override is one-off.
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
            // Shares must always sum to 100% - the same way RecalculateInfluencers normalises the real
            // Target by dividing by the total influence (EquestriaRaceAssimilation.cs).
            // The entered numbers are RELATIVE weights, they need not add up to 100 by themselves (noticed
            // by the user 07.10.2026: Pony=25 Yak=25 Changeling=25 summed to only 75%,
            // the remainder was shown nowhere and did not exist - a state unreachable in a real
            // game). Normalise to a sum of 1 before writing.
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

        // equestria.race_assim_near [km] - list of settlements nearest to the party: English StringId (it
        // is safe to type - the Bannerlord console handles Cyrillic badly) + Russian name for
        // identification + current race. The StringId can then be passed to race_assim_report/_delay and
        // so on without a single Russian letter. Default radius is 20 km, with no parameter.
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
                // Russian name - only to the log (the console will not draw it, see the comment above), for
                // matching against what is visible on the map.
                EquestriaCrashLog.Log("ассимиляция расы (near): " + settlement.StringId + " = " + settlement.Name);
            }
            return string.Join("\n", lines);
        }

        // Culture ids in this mod are the vanilla English ids (empire/aserai/vlandia/battania/sturgia/
        // khuzait/nord), and the recruit race is hard-baked per culture when troops are built (tools/
        // make_troops.py, CULTURE_RACE) - the same mapping here, only in English words (the console
        // does not render Cyrillic, see the comments above). An unknown id is returned as is, also
        // in Latin letters.
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

    // Settlement tooltip: a "Race" line + a per-race breakdown with daily dynamics - the same trick
    // as UpdateTooltipPatch in the original DynaCulture, but we patch the method current for this game version:
    // their code used TooltipVM.OpenTooltip (obsolete API), here tooltips are built via
    // TooltipRefresherCollection.RefreshSettlementTooltip(PropertyBasedTooltipVM, object[] args) -
    // found by decompiling SandBox.View.dll (SandBoxViewSubModule registers this refresher for
    // Settlement via InformationManager.RegisterTooltip).
    //
    // NOT via a [HarmonyPatch] attribute (a blanket PatchAll would pick it up right at mod load) and
    // NOT in EquestriaPatches.ApplyLate (that is also too early - verified in practice 06.10.2026, see below).
    // Reason: RefreshSettlementTooltip itself, in its own body, directly calls
    // CampaignUIHelper.IsSettlementInformationHidden(...) - and CampaignUIHelper has a static
    // field initialiser (_partyMoraleStr = GameTexts.FindText("str_party_morale")), which
    // runs in the type's static constructor EXACTLY WHEN Harmony first JIT-compiles
    // (pins) the method for the patch - no matter when Apply is called: at mod load or at the main menu
    // (ApplyLate) - in both cases the game's string table is not loaded yet, GameTexts.FindText
    // returns null, a NullReferenceException is thrown inside, and CampaignUIHelper is PERMANENTLY
    // marked uninitialised (that is how static constructors work in .NET - they are not
    // re-run). After that any access to this type (and the native MapBarVM.
    // Initialize touches it every time the map screen is built) throws TypeInitializationException - the map
    // screen is not built, and QuickStart cannot skip character creation.
    // Confirmed experimentally: with this patch applied in ApplyLate - a crash; without the patch
    // at all - quick start reaches the map and race assimilation initialises on 410
    // settlements without a single error (eq_exceptions.log, two test runs in a row).
    // SOLUTION: patch no earlier than the campaign has actually started ticking (EquestriaRaceAssimilation.
    // OnDailyTickSettlement, lazily on the first tick) - by then the engine has already successfully
    // built the map and touched CampaignUIHelper via the native path, so a repeated Harmony JIT does not
    // trigger anything again.
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
                // Hide it the same way the game itself hides "Troops ???" - with the same CampaignUIHelper.
                // IsSettlementInformationHidden as the native settlement properties (at the user's
                // request 07.10.2026: the race must not be visible to the player earlier than the rest of the
                // detailed information about a foreign settlement). This is the very method that previously
                // caused the premature-initialisation crash (see the comment at Apply above) - here it
                // is already safe: the tooltip is built only after the first campaign tick.
                if (CampaignUIHelper.IsSettlementInformationHidden(settlement, out TextObject _))
                {
                    propertyBasedTooltipVM.AddProperty(" ", GameTexts.FindText("str_missing_info_indicator").ToString());
                    return;
                }
                // "now -> target" for each race, not a tiny daily delta - so it is immediately clear
                // where and how far the share is heading, not just that it moved a bit over the day
                // (at the user's request 07.10.2026: "it will be clear how much we have now and
                // what number it is heading towards"). Merge the keys of both dictionaries - races that are
                // not in Current at all yet but already appear in Target (neighbours have just started pushing)
                // must be visible too.
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
