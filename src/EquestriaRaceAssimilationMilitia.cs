using System.Reflection;
using HarmonyLib;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.Core;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Village/town militia is recruited strictly from Settlement.Culture and ignores the assimilation race %
    // (EquestriaRaceAssimilation.cs) completely (decompile TaleWorlds.CampaignSystem.dll,
    // Settlement.AddMilitiasToParty/AddTroopToMilitiaParty are private methods that read
    // Culture.MeleeMilitiaTroop/RangedMilitiaTroop directly). At the user's request 07.10.2026: since
    // we compute race shares anyway, let the militia be recruited mixed, in proportion to them.
    //
    // We patch AddMilitiasToParty (NOT AddTroopToMilitiaParty: that one is called twice per call, melee and
    // ranged, and telling which of the two is harder than intercepting one level up): we run the same pair
    // of AddTroopToMilitiaParty calls (via reflection, the method is private) as the original, but once
    // FOR EACH race with its share, multiplying the melee/ranged rate by the race share. The internal randomisation
    // of the count and the veteran chance (MBRandom.RoundRandomized, CalculateVeteranMilitiaSpawnChance)
    // stay exactly the same: we reuse the original private method instead of rewriting its logic.
    //
    // A REGULAR [HarmonyPatch] (not lazy, unlike RaceAssimilationTooltipPatch): this method does not touch
    // CampaignUIHelper/GameTexts, its JIT pinning at mod load breaks nothing (unlike that
    // crash, see the comment at RaceAssimilationTooltipPatch.Apply).
    [HarmonyPatch(typeof(Settlement), "AddMilitiasToParty")]
    internal static class RaceAssimilationMilitiaPatch
    {
        private static readonly MethodInfo AddTroopToMilitiaParty =
            AccessTools.Method(typeof(Settlement), "AddTroopToMilitiaParty");

        private static bool Prefix(Settlement __instance, MobileParty militiaParty, int militiaNumberToAdd)
        {
            if (AddTroopToMilitiaParty == null)
            {
                return true;
            }
            if (!RaceAssimilationManager.Instance.InfluenceMap.TryGetValue(__instance.StringId, out RaceAssimilationStatus status)
                || status.CurrentInfluences.Count <= 1)
            {
                // No data (settlement population not initialised for this settlement yet) or exactly one
                // race (not blended yet): normal engine behaviour, nothing to touch.
                return true;
            }
            Campaign.Current.Models.SettlementMilitiaModel.CalculateMilitiaSpawnRate(
                __instance, out float meleeTroopRate, out float rangedTroopRate);
            foreach (var pair in status.CurrentInfluences)
            {
                if (pair.Value <= 0m)
                {
                    continue;
                }
                CultureObject culture = MBObjectManager.Instance.GetObject<CultureObject>(pair.Key);
                if (culture?.MeleeMilitiaTroop == null || culture.RangedMilitiaTroop == null)
                {
                    continue;
                }
                float share = (float)pair.Value;
                AddTroopToMilitiaParty.Invoke(__instance, new object[]
                    { militiaParty, culture.MeleeMilitiaTroop, culture.MeleeEliteMilitiaTroop, meleeTroopRate * share, militiaNumberToAdd });
                AddTroopToMilitiaParty.Invoke(__instance, new object[]
                    { militiaParty, culture.RangedMilitiaTroop, culture.RangedEliteMilitiaTroop, rangedTroopRate * share, militiaNumberToAdd });
            }
            return false;
        }
    }
}
