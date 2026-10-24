using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.GameState;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.Core;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Race assimilation of captured settlements — a port of the DynaCulture mod (github.com/Splintertx/
    // DynaCulture, open source, GPL) to this race system, without its weak spots.
    //
    // KEY FACT (confirmed in tools/make_troops.py, CULTURE_RACE): in this mod the recruit's race is
    // hard-baked into the CULTURE's troop tree at build time (sturgia=dragons, aserai=changelings,
    // vlandia=griffons, battania=hippogriffs, khuzait=yaks, nord=deer, empire=ponies by default) —
    // it is not chosen on the fly. So changing Settlement.Culture from code (the DynaCulture trick)
    // BY ITSELF already changes the race the settlement recruits — no extra race<->culture links
    // are needed in this file, we work directly with CultureObject, like the original.
    //
    // Differences from the original (fully analysed 06.10.2026):
    //  - One logic class, not two (DynaCulture had a dead prototype namespace
    //    ChangeSettlementCulture.Data next to the working DynaCulture.Data — we inherit only the working one).
    //  - Saving goes through the NATIVE IDataStore.SyncData (see below), not a custom file on disk keyed
    //    by the hero's name (in the original SyncData was empty and the state lived in a separate file —
    //    fragile: namesakes, not tied to the save slot).
    //  - No "corrupted troops/recruits" cleanup — it is a workaround for a VANILLA BUG relevant to their
    //    build tools, it did not reproduce for us.
    //  - Applies to ALL kingdoms on the map (both AI and the player's), like the original by default.
    //
    // A settlement holds not a one-off snapshot but a NETWORK of influences (CurrentInfluences moves
    // toward TargetInfluences exponentially, see RaceAssimilationStatus.OnDailyTick), so a change of
    // owner does not switch the race instantly — the settlement must actually stay under the new rule
    // for some time.
    //
    // Tuning — via the equestria.race_assim_* console commands (see
    // EquestriaRaceAssimilationCommands.cs), tuned live and then written into the defaults below
    // by hand, the same approach as equestria.helmet_scale/helmet_offset in EquestriaHelmetFit.
    public class EquestriaRaceAssimilation : CampaignBehaviorBase
    {
        // Picked by DynaCulture as working defaults (DefaultDynaCultureSettings.cs) — a starting
        // point, refined live with the commands below.
        public static float InfluenceRange = 30f;
        // Was 45 — at the user's request 07.10.2026 (
        // "a lot of % changes in literally a couple of days") made 10 times slower: rate = influenceSum /
        // AssimilationDelay (OnDailyTick), the multiplier here divides the speed at which Current
        // approaches Target directly, without changing the shape of the curve.
        public static int AssimilationDelay = 450;
        public static int OwnerInfluenceStrength = 5;
        public static bool TradeLinkedInfluence = true;

        // Cap on the dominant race's share (at the user's request 07.10.2026:
        // "in an ideal society 100% will never be of one
        // people" — 70-90%, the rest spread a little over all the other races). Our own addition on top
        // of DynaCulture — the original had no cap, Target could reach a pure 100%. See its use in
        // RecalculateInfluencers.
        public static decimal MaxDominantShare = 0.85m;

        // All playable cultures of the world — the recruit's race is baked into the culture for good
        // when the troops are built (tools/make_troops.py, CULTURE_RACE), so change/extend this list
        // only together with it. Needed to spread the remainder below MaxDominantShare over ALL races,
        // not only over current neighbours — even a settlement without a single neighbour of another
        // race should get a minimal admixture of all the others.
        internal static readonly string[] AllCultureIds =
            { "empire", "aserai", "vlandia", "battania", "sturgia", "khuzait", "nord" };

        public override void RegisterEvents()
        {
            CampaignEvents.DailyTickSettlementEvent.AddNonSerializedListener(this, OnDailyTickSettlement);
            CampaignEvents.HourlyTickEvent.AddNonSerializedListener(this, OnHourlyTick);
            EquestriaCrashLog.Note("ассимиляция расы: события зарегистрированы (range="
                + InfluenceRange + " delay=" + AssimilationDelay + " owner=" + OwnerInfluenceStrength
                + " trade=" + TradeLinkedInfluence + ")");
        }

        private static bool _tooltipPatchApplied;

        // The settlement tooltip patch — lazily, here, not in EquestriaPatches.Apply/ApplyLate.
        // FOUND 06.10.2026 (see memory equestria-race-assimilation): TooltipRefresherCollection
        // .RefreshSettlementTooltip calls CampaignUIHelper directly, whose static field
        // initializer (_partyMoraleStr = GameTexts.FindText("str_party_morale"))
        // reads the string table BEFORE it is loaded — if we patch (Harmony has to JIT-compile
        // the method, which runs the type's static constructor) at mod load or even at the main
        // menu, GameTexts.FindText returns null, a NullReferenceException is thrown inside
        // CampaignUIHelper, and the type is marked uninitialized FOREVER — the native map
        // screen (MapBarVM) is then never built at all. By the first campaign tick the engine
        // has already touched CampaignUIHelper successfully by itself (otherwise we would not
        // have got here), and patching is safe — the static constructor of an already
        // initialized type does not run again.
        //
        // Earlier (07.10.2026) this gate sat ONLY on DailyTickSettlementEvent — it fires once per
        // in-game DAY (and does not fire at all until time on the map is running), so the tooltip
        // was missing for almost the whole first game session (noticed by the user: hovered over
        // Canterlot right after .\run.ps1 -QuickStart — empty). HourlyTickEvent is a bit faster but
        // also waits for time to pass. The main path is now the per-frame poll Tick() (see below,
        // called from SubModule.OnApplicationTick): the same approach EquestriaRaceParty/
        // EquestriaShowcase already use — wait for an active MapState and 2 seconds for the campaign
        // to "settle", without depending on in-game time passing. Safety-wise it is no worse than the
        // tick gate: within those 2 seconds the native MapBarVM (which touches CampaignUIHelper via its
        // own normal path) has long been built — the same Equestria* classes have used this very
        // delay before their actions (opening windows etc.) for years without a single similar crash.
        // OnHourlyTick is kept as a fallback in case the per-frame poll somehow does not fire (the
        // patch will not be applied twice — both paths go through the shared _tooltipPatchApplied).
        private void OnHourlyTick()
        {
            TryApplyTooltipPatch();
            SeedTestVillage();
        }

        private static DateTime _mapSeenAt = DateTime.MinValue;

        /// <summary>Called every frame from SubModule.OnApplicationTick — catches the moment the
        /// campaign starts (incl. .\run.ps1 -QuickStart) without waiting for in-game time to pass.</summary>
        public static void Tick()
        {
            if (_tooltipPatchApplied)
            {
                return;
            }
            if (!(GameStateManager.Current?.ActiveState is MapState) || Campaign.Current == null
                || !Campaign.Current.GameStarted)
            {
                _mapSeenAt = DateTime.MinValue;
                return;
            }
            if (_mapSeenAt == DateTime.MinValue)
            {
                _mapSeenAt = DateTime.UtcNow;
                return;
            }
            if ((DateTime.UtcNow - _mapSeenAt).TotalSeconds < 2)
            {
                return;
            }
            TryApplyTooltipPatch();
            SeedTestVillage();
        }

        private static bool _testVillageSeeded;

        // Test seeding of village_empire_0 (Clover Dale) at campaign start — at the user's
        // request 07.10.2026: native race 70-90%, the remainder spread randomly over all the
        // other races, so that the table in the tooltip is visible right after .\run.ps1 -QuickStart
        // without typing equestria.race_assim_set by hand. One-off, like applying the tooltip patch —
        // after that the regular OnDailyTick moves Current toward the real Target as for any village.
        private static void SeedTestVillage()
        {
            if (_testVillageSeeded || Campaign.Current == null || !Campaign.Current.GameStarted)
            {
                return;
            }
            _testVillageSeeded = true;
            try
            {
                if (RaceAssimilationManager.Instance.InfluenceMap.Count == 0)
                {
                    RaceAssimilationManager.Instance.Initialize();
                }
                if (!RaceAssimilationManager.Instance.InfluenceMap.TryGetValue("village_empire_0", out RaceAssimilationStatus status))
                {
                    EquestriaCrashLog.Warn("ассимиляция расы: тестовая деревня village_empire_0 не найдена, засев пропущен");
                    return;
                }
                var rng = new Random();
                decimal homeland = 70m + (decimal)rng.NextDouble() * 20m;
                string[] others = AllCultureIds.Where(id => id != status.HomelandCultureId).ToArray();
                var weights = others.Select(id => (id, w: (decimal)rng.NextDouble() + 0.1m)).ToList();
                decimal weightSum = weights.Sum(w => w.w);
                decimal remainder = 100m - homeland;
                var seeded = new Dictionary<string, decimal> { [status.HomelandCultureId] = homeland / 100m };
                foreach (var (id, w) in weights)
                {
                    seeded[id] = w / weightSum * remainder / 100m;
                }
                status.CurrentInfluences = seeded;
                EquestriaCrashLog.Log("ассимиляция расы: тестовая деревня village_empire_0 засеяна — "
                    + string.Join(", ", seeded.OrderByDescending(p => p.Value).Select(p => $"{p.Key}={p.Value * 100:0.#}%")));
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Warn("ассимиляция расы: засев тестовой деревни упал: " + e.GetType().Name
                    + ": " + e.Message + "\r\n" + e.StackTrace);
            }
        }

        private static void TryApplyTooltipPatch()
        {
            try
            {
                if (_tooltipPatchApplied || Campaign.Current == null || !Campaign.Current.GameStarted)
                {
                    return;
                }
                _tooltipPatchApplied = true;
                if (EquestriaPatches.Instance != null)
                {
                    RaceAssimilationTooltipPatch.Apply(EquestriaPatches.Instance);
                }
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Warn("ассимиляция расы: применение патча подсказки упало: "
                    + e.GetType().Name + ": " + e.Message + "\r\n" + e.StackTrace);
            }
        }

        // The tick fires for EVERY settlement EVERY day — an exception here without try/catch would
        // bring down the tick for all settlements at once (one broken Settlement.Find — and the whole
        // campaign is done). Log only suspicious things: do not write here on every normal tick,
        // otherwise the log (8 MB limit, see EquestriaCrashLog) overflows within one game year on the full map.
        private void OnDailyTickSettlement(Settlement settlement)
        {
            try
            {
                if (Campaign.Current == null || !Campaign.Current.GameStarted || settlement == null)
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
                if (RaceAssimilationManager.Instance.InfluenceMap.TryGetValue(settlement.StringId, out RaceAssimilationStatus status))
                {
                    status.OnDailyTick();
                }
                else
                {
                    EquestriaCrashLog.Warn("ассимиляция расы: нет статуса для " + settlement.StringId
                        + " (" + settlement.Name + ") после инициализации");
                }
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Warn("ассимиляция расы: тик поселения " + (settlement != null ? settlement.StringId : "?")
                    + " упал: " + e.GetType().Name + ": " + e.Message + "\r\n" + e.StackTrace);
            }
        }

        // Flat serialization (the same approach as EquestriaBodyParts.SyncHairLookCache): settlement
        // -> one encoded string (RaceAssimilationStatus.Encode/Decode), stored as two parallel
        // List<string> — Dictionary<string,string> also syncs natively
        // (see EquestriaRaceSaveBehavior._heroRaces), but a pair of lists is easier to debug by hand.
        //
        // The static manager is reset HERE, in the load branch, not on OnGameLoadedEvent: that one
        // fires AFTER SyncData of all behaviours and would wipe the data this very call just loaded.
        // The reset is needed so data from the PREVIOUS game is not carried into the newly loaded one
        // (we play, exit to the menu, load another save in the same process — the static survives).
        public override void SyncData(IDataStore dataStore)
        {
            if (!dataStore.IsSaving)
            {
                RaceAssimilationManager.Reset();
            }

            List<string> keys = null;
            List<string> values = null;
            if (dataStore.IsSaving)
            {
                keys = RaceAssimilationManager.Instance.InfluenceMap.Keys.ToList();
                values = keys.Select(k => RaceAssimilationManager.Instance.InfluenceMap[k].Encode()).ToList();
            }

            dataStore.SyncData("eq_race_assim_keys", ref keys);
            dataStore.SyncData("eq_race_assim_values", ref values);

            if (dataStore.IsSaving)
            {
                EquestriaCrashLog.Log("ассимиляция расы: сохранено поселений " + (keys?.Count ?? 0));
            }
            else if (keys != null && values != null && keys.Count == values.Count)
            {
                int decoded = 0;
                int failed = 0;
                for (int i = 0; i < keys.Count; i++)
                {
                    RaceAssimilationStatus status = RaceAssimilationStatus.Decode(keys[i], values[i]);
                    if (status != null)
                    {
                        RaceAssimilationManager.Instance.InfluenceMap[keys[i]] = status;
                        decoded++;
                    }
                    else
                    {
                        failed++;
                    }
                }
                EquestriaCrashLog.Log("ассимиляция расы: загружено поселений " + decoded
                    + (failed > 0 ? ", не удалось раскодировать " + failed : ""));
            }
            else if (keys != null || values != null)
            {
                EquestriaCrashLog.Warn("ассимиляция расы: ключи/значения рассинхронизированы при загрузке "
                    + "(keys=" + (keys?.Count.ToString() ?? "null") + " values=" + (values?.Count.ToString() ?? "null") + ")");
            }
        }
    }

    // Static manager — access is needed both from CampaignBehaviorBase (tick/save) and from the
    // console commands/Harmony tooltip patch (EquestriaRaceAssimilationCommands.cs), which have
    // no reference to the behaviour instance. The same pattern as ChangeCultureManager/DynaCultureManager
    // in the original.
    internal sealed class RaceAssimilationManager
    {
        private static RaceAssimilationManager _instance;

        public static RaceAssimilationManager Instance => _instance ?? (_instance = new RaceAssimilationManager());

        public readonly Dictionary<string, RaceAssimilationStatus> InfluenceMap =
            new Dictionary<string, RaceAssimilationStatus>();

        internal static void Reset()
        {
            _instance = null;
        }

        // Robust to new settlements added later (the campaign was extended etc.) — same as
        // DynaCultureManager.Initialize().
        public void Initialize()
        {
            int before = InfluenceMap.Count;
            foreach (Settlement settlement in Settlement.All.Where(s => s.IsVillage || s.IsCastle || s.IsTown))
            {
                if (!InfluenceMap.ContainsKey(settlement.StringId))
                {
                    InfluenceMap[settlement.StringId] = new RaceAssimilationStatus(settlement);
                }
            }
            foreach (RaceAssimilationStatus status in InfluenceMap.Values)
            {
                status.OnCampaignLoad();
            }
            EquestriaCrashLog.Log("ассимиляция расы: инициализировано поселений " + InfluenceMap.Count
                + (before > 0 ? " (было " + before + " до вызова)" : ""));
        }
    }

    // Per settlement: the network of influences (CurrentInfluences moves toward TargetInfluences
    // exponentially) and applying the winning race. A port of DynaCultureStatus
    // (DynaCulture/Data/DynaCultureStatus.cs) — the comments below explain only what differs from the
    // original or is not obvious by itself; the mechanics itself is analysed and documented in
    // [[dynaculture-race-assimilation]] (memory).
    internal sealed class RaceAssimilationStatus
    {
        private const int BaseInfluence = 1;

        private readonly string _settlementId;

        // The race the settlement was born with — never changes, used for the resistance bonus
        // (see GetInfluenceFromSettlement) and to break ties in GetTopCultureId.
        public readonly string HomelandCultureId;

        public Dictionary<string, decimal> CurrentInfluences = new Dictionary<string, decimal>();
        public Dictionary<string, decimal> TargetInfluences = new Dictionary<string, decimal>();

        // Only for the daily delta in the tooltip (EquestriaRaceAssimilationCommands) — not
        // saved between sessions (as in the original, this does not break the mechanics: the first
        // tick after loading just shows a delta of 0, GetPreviousInfluenceForCulture falls back to Current).
        public Dictionary<string, decimal> PreviousInfluences;

        public int DaysSinceTargetsChanged;
        public int ExpectedIdKey;
        public int TargetInfluencesIdKey;

        public RaceAssimilationStatus(Settlement settlement)
        {
            _settlementId = settlement.StringId;
            HomelandCultureId = settlement.Culture.StringId;
        }

        private RaceAssimilationStatus(string settlementId, string homelandCultureId)
        {
            _settlementId = settlementId;
            HomelandCultureId = homelandCultureId;
        }

        public void OnCampaignLoad()
        {
            if (CurrentInfluences.Count == 0)
            {
                Settlement settlement = Settlement.Find(_settlementId);
                CurrentInfluences[settlement.Culture.StringId] = 1m;
            }
            if (TargetInfluences.Count == 0)
            {
                RecalculateInfluencers(firstTimeSetup: true);
            }
        }

        public void OnDailyTick()
        {
            int influenceSum = RecalculateInfluencers(firstTimeSetup: false);
            PreviousInfluences = new Dictionary<string, decimal>(CurrentInfluences);

            if (ExpectedIdKey != TargetInfluencesIdKey)
            {
                // a neighbour/owner changed since the last tick — restart the day count
                DaysSinceTargetsChanged = 0;
                ExpectedIdKey = TargetInfluencesIdKey;
            }
            else
            {
                DaysSinceTargetsChanged++;
            }

            // Exponential approach: each day we cover 1/AssimilationDelay of the difference.
            // Not linear — fast progress at first, slowly reaches the end, never quite gets there
            // (intentional, as in the original: imitates the inertia of population assimilation).
            //
            // BUG (found by the user 07.10.2026 via equestria.race_assim_set, but reproducible without
            // it too): the loop used to go only over the TargetInfluences keys — a race whose influence
            // vanished completely (that race's neighbour destroyed/changed owner, the target share became
            // exactly 0 and the key disappeared from Target) was never touched. Its Current froze forever
            // at the last value, while the other races kept growing toward their targets — the sum of
            // shares went above 100%. So we iterate over the UNION of both dictionaries' keys: for a race
            // missing from Target the target is 0, and it decays exponentially like the others.
            decimal rate = Math.Min((decimal)influenceSum / EquestriaRaceAssimilation.AssimilationDelay, 1m);
            foreach (string cultureId in CurrentInfluences.Keys.Union(TargetInfluences.Keys).ToList())
            {
                decimal current = CurrentInfluences.TryGetValue(cultureId, out decimal c) ? c : 0m;
                decimal target = TargetInfluences.TryGetValue(cultureId, out decimal t) ? t : 0m;
                CurrentInfluences[cultureId] = current + (target - current) * rate;
            }
            // Decay toward 0 never gives negative values — clean up by a threshold, otherwise long
            // faded races (a share like 0.0001%) stay in the dictionary forever.
            foreach (string key in CurrentInfluences.Where(p => p.Value < 0.0001m).Select(p => p.Key).ToList())
            {
                CurrentInfluences.Remove(key);
            }

            ApplyRace();
        }

        public decimal GetPreviousInfluenceForCulture(string cultureId)
        {
            if (PreviousInfluences != null && PreviousInfluences.TryGetValue(cultureId, out decimal previous))
            {
                return previous;
            }
            return CurrentInfluences.TryGetValue(cultureId, out decimal current) ? current : 0m;
        }

        /// <summary>Recomputes the target (TargetInfluences) from the current neighbours/owner. Returns
        /// the influence sum (the denominator of the shares) — also the approach speed in OnDailyTick.</summary>
        private int RecalculateInfluencers(bool firstTimeSetup)
        {
            Settlement settlement = Settlement.Find(_settlementId);
            TaleWorlds.Library.Vec2 position = settlement.GetPosition2D;

            List<Settlement> influencing = Settlement.All
                .Where(s => (s.IsVillage || s.IsCastle || s.IsTown)
                            && s.GetPosition2D.Distance(position) <= EquestriaRaceAssimilation.InfluenceRange)
                .ToList();

            if (EquestriaRaceAssimilation.TradeLinkedInfluence)
            {
                if (settlement.IsCastle || settlement.IsTown)
                {
                    influencing.AddRange(settlement.BoundVillages.Select(v => v.Settlement));
                }
                if (settlement.IsVillage)
                {
                    Settlement parent = Settlement.All.FirstOrDefault(s =>
                        s.BoundVillages != null && s.BoundVillages.Any(v => v.Settlement == settlement));
                    if (parent != null)
                    {
                        influencing.AddRange(parent.BoundVillages.Select(v => v.Settlement));
                    }
                }
            }

            int sum = 0;
            var influencers = new Dictionary<string, int>();
            foreach (Settlement other in influencing.Distinct())
            {
                int influence = GetInfluenceFromSettlement(other, settlement, firstTimeSetup);
                sum += influence;
                // The bucket is the neighbour's CURRENT race (not its owner's race): a half-assimilated
                // neighbour also pushes weaker (see GetInfluenceFromSettlement, the weight is multiplied
                // by its own GetTopCulturePercent).
                string cultureId = other.Culture.StringId;
                influencers[cultureId] = influencers.TryGetValue(cultureId, out int existing)
                    ? existing + influence : influence;
            }

            int ownerInfluence = BaseInfluence * EquestriaRaceAssimilation.OwnerInfluenceStrength;
            sum += ownerInfluence;
            if (ownerInfluence > 0)
            {
                string ownerCultureId = GetOwnerCulture(settlement).StringId;
                influencers[ownerCultureId] = influencers.TryGetValue(ownerCultureId, out int existingOwner)
                    ? existingOwner + ownerInfluence : ownerInfluence;
            }

            bool didTargetsChange = false;
            foreach (KeyValuePair<string, int> pair in influencers)
            {
                decimal percent = sum > 0 ? (decimal)pair.Value / sum : 0m;
                if (!TargetInfluences.TryGetValue(pair.Key, out decimal existing) || existing != percent)
                {
                    TargetInfluences[pair.Key] = percent;
                    didTargetsChange = true;
                }
            }
            foreach (string key in TargetInfluences.Keys.Where(k => !influencers.ContainsKey(k)).ToList())
            {
                if (TargetInfluences[key] != 0m)
                {
                    TargetInfluences[key] = 0m;
                    didTargetsChange = true;
                }
            }

            // Cap on the dominant race (EquestriaRaceAssimilation.MaxDominantShare) — the remainder is
            // spread over ALL playable races (not only the current neighbours), including those that
            // had no share at all yet: even a purely monocultural settlement (neighbour and owner of
            // one race, the capped share would have gone to 100%) gets a minimal admixture of every
            // race of the world.
            //
            // NOT evenly (at the user's request 07.10.2026:
            // "2.5% for each looks odd") — each race's weight comes from a STABLE pseudo-random number
            // (hash of settlement id + race id, not new Random()): different settlements spread the
            // remainder differently, but for ONE and the same settlement the weights are not reshuffled
            // on every daily tick for no reason.
            if (TargetInfluences.Count > 0)
            {
                var top = TargetInfluences.OrderByDescending(p => p.Value).First();
                if (top.Value > EquestriaRaceAssimilation.MaxDominantShare)
                {
                    decimal excess = top.Value - EquestriaRaceAssimilation.MaxDominantShare;
                    TargetInfluences[top.Key] = EquestriaRaceAssimilation.MaxDominantShare;
                    string[] others = EquestriaRaceAssimilation.AllCultureIds.Where(id => id != top.Key).ToArray();
                    if (others.Length > 0)
                    {
                        Dictionary<string, decimal> weights = others.ToDictionary(id => id,
                            id => 0.2m + StableWeight01(_settlementId + "|" + id) * 0.8m);
                        decimal weightSum = weights.Values.Sum();
                        foreach (string id in others)
                        {
                            decimal share = weights[id] / weightSum * excess;
                            TargetInfluences[id] = TargetInfluences.TryGetValue(id, out decimal existing)
                                ? existing + share : share;
                        }
                    }
                    didTargetsChange = true;
                }
            }

            if (didTargetsChange)
            {
                TargetInfluencesIdKey++;
            }
            return sum;
        }

        // A stable pseudo-random number in [0, 1) from a string — the same FNV-1a trick as
        // EquestriaBodyParts.LoreColor (there for the hero's color, here for a race's weight in the
        // cap remainder). Not System.Random: it cannot be seeded with a string directly, and
        // GetHashCode() in .NET is not deterministic between process runs.
        private static decimal StableWeight01(string s)
        {
            uint hash = 2166136261;
            unchecked
            {
                foreach (char c in s)
                {
                    hash ^= c;
                    hash *= 16777619;
                }
            }
            return hash / (decimal)uint.MaxValue;
        }

        /// <summary>Influence weight of settlement other on self. Town×3/castle×2/village×1, on itself
        /// ×2, and another ×2 if the OWNER of this (self) settlement is still of the race it was born
        /// with (resistance to change) — the bonus is by owner, not by the settlement's currently
        /// displayed race (that is exactly what we are gradually changing).</summary>
        private int GetInfluenceFromSettlement(Settlement other, Settlement self, bool firstTimeSetup)
        {
            int influence = BaseInfluence;
            if (other.IsTown)
            {
                influence *= 3;
            }
            else if (other.IsCastle)
            {
                influence *= 2;
            }

            bool isSelf = other.StringId == self.StringId;
            if (isSelf)
            {
                influence *= 2;
                if (GetOwnerCulture(other).StringId == HomelandCultureId)
                {
                    influence *= 2;
                }
            }

            if (!firstTimeSetup)
            {
                decimal otherTop = RaceAssimilationManager.Instance.InfluenceMap.TryGetValue(other.StringId, out RaceAssimilationStatus status)
                    ? status.GetTopCulturePercent() : 1m;
                influence = (int)Math.Round(influence * otherTop, MidpointRounding.AwayFromZero);
            }
            return influence;
        }

        /// <summary>The winning race: a tie is resolved in favour of the settlement's native race,
        /// otherwise alphabetically (same order as in the original, so the result is deterministic).</summary>
        public string GetTopCultureId()
        {
            KeyValuePair<string, decimal> top = CurrentInfluences.OrderByDescending(p => p.Value).First();
            List<KeyValuePair<string, decimal>> tied = CurrentInfluences.Where(p => p.Value == top.Value).ToList();
            if (tied.Count > 1)
            {
                return tied.Any(p => p.Key == HomelandCultureId)
                    ? HomelandCultureId
                    : tied.OrderBy(p => p.Key).First().Key;
            }
            return top.Key;
        }

        public decimal GetTopCulturePercent()
        {
            if (CurrentInfluences.Count == 0)
            {
                return 0m;
            }
            string topId = GetTopCultureId();
            return CurrentInfluences.TryGetValue(topId, out decimal value) ? value : 0m;
        }

        /// <summary>If the dominant race differs from the current Settlement.Culture — really switches
        /// it (and the bound villages too). The original's safeguard: never leave a race with no towns
        /// at all — otherwise that race's companions have nowhere to spawn (crash).</summary>
        private void ApplyRace()
        {
            if (CurrentInfluences.Count == 0)
            {
                return;
            }
            Settlement settlement = Settlement.Find(_settlementId);
            string topId = GetTopCultureId();
            if (settlement.Culture.StringId == topId)
            {
                return;
            }

            if (settlement.IsTown)
            {
                int remainingTowns = Settlement.All.Count(s => s.IsTown && s.Culture.StringId == settlement.Culture.StringId);
                if (remainingTowns <= 1)
                {
                    EquestriaCrashLog.Log("ассимиляция расы: " + settlement.Name + " — смена "
                        + settlement.Culture.StringId + "->" + topId + " ОТМЕНЕНА, последний город расы");
                    return;
                }
            }

            CultureObject topCulture = MBObjectManager.Instance.GetObject<CultureObject>(topId);
            if (topCulture == null)
            {
                EquestriaCrashLog.Warn("ассимиляция расы: культура " + topId + " не найдена в MBObjectManager, "
                    + settlement.Name + " не переключена");
                return;
            }

            EquestriaCrashLog.Log("ассимиляция расы: " + settlement.Name + " (" + _settlementId + ") сменила расу "
                + settlement.Culture.StringId + " -> " + topId + " (день " + DaysSinceTargetsChanged + ")");
            settlement.Culture = topCulture;
            if (settlement.BoundVillages != null)
            {
                foreach (Village attached in settlement.BoundVillages)
                {
                    if (attached.Settlement != null)
                    {
                        attached.Settlement.Culture = topCulture;
                    }
                }
            }
        }

        private static CultureObject GetOwnerCulture(Settlement settlement)
        {
            if (settlement.OwnerClan?.Kingdom != null)
            {
                return settlement.OwnerClan.Kingdom.Culture;
            }
            if (settlement.OwnerClan?.Culture != null)
            {
                return settlement.OwnerClan.Culture;
            }
            return settlement.Culture;
        }

        // ---- flat serialization for IDataStore (see EquestriaRaceAssimilation.SyncData) ----

        public string Encode()
        {
            return string.Join("|", new[]
            {
                HomelandCultureId,
                EncodeMap(CurrentInfluences),
                EncodeMap(TargetInfluences),
                DaysSinceTargetsChanged.ToString(CultureInfo.InvariantCulture),
                ExpectedIdKey.ToString(CultureInfo.InvariantCulture),
                TargetInfluencesIdKey.ToString(CultureInfo.InvariantCulture),
            });
        }

        public static RaceAssimilationStatus Decode(string settlementId, string encoded)
        {
            if (string.IsNullOrEmpty(encoded))
            {
                return null;
            }
            string[] parts = encoded.Split('|');
            if (parts.Length != 6)
            {
                return null;
            }
            var status = new RaceAssimilationStatus(settlementId, parts[0])
            {
                CurrentInfluences = DecodeMap(parts[1]),
                TargetInfluences = DecodeMap(parts[2]),
            };
            int.TryParse(parts[3], NumberStyles.Integer, CultureInfo.InvariantCulture, out int days);
            int.TryParse(parts[4], NumberStyles.Integer, CultureInfo.InvariantCulture, out int expected);
            int.TryParse(parts[5], NumberStyles.Integer, CultureInfo.InvariantCulture, out int targetKey);
            status.DaysSinceTargetsChanged = days;
            status.ExpectedIdKey = expected;
            status.TargetInfluencesIdKey = targetKey;
            return status;
        }

        private static string EncodeMap(Dictionary<string, decimal> map)
        {
            return string.Join(";", map.Select(p => p.Key + "=" + p.Value.ToString(CultureInfo.InvariantCulture)));
        }

        private static Dictionary<string, decimal> DecodeMap(string encoded)
        {
            var result = new Dictionary<string, decimal>();
            if (string.IsNullOrEmpty(encoded))
            {
                return result;
            }
            foreach (string entry in encoded.Split(';'))
            {
                int eq = entry.IndexOf('=');
                if (eq <= 0)
                {
                    continue;
                }
                string key = entry.Substring(0, eq);
                if (decimal.TryParse(entry.Substring(eq + 1), NumberStyles.Float, CultureInfo.InvariantCulture, out decimal value))
                {
                    result[key] = value;
                }
            }
            return result;
        }
    }
}
