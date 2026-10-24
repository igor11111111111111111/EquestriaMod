using HarmonyLib;
using TaleWorlds.CampaignSystem.Actions;
using TaleWorlds.CampaignSystem.Settlements;

namespace EquestriaMod
{
    // Village recovery speed after being fully raided (SettlementHitPoints 0 -> 1; until it
    // reaches 1 the village is in the Looted state and cannot be entered or interacted with). Decompiled
    // 07.10.2026: VillageHealCampaignBehavior.DailyTickSettlement computes the rate
    // 0.06 + (7000 - clamp(owner realm strength, 1000, 7000)) / 100000 — i.e. 6%/day for a
    // strong realm, 12%/day for a weak one, and passes it to the only call of
    // IncreaseSettlementHealthAction.Apply (there are no other calls of this method in the game — checked).
    // At the user's request 07.10.2026 — twice as slow, villages only (town sieges are left
    // alone, that is a separate balance). We patch ApplyInternal (private) via a Harmony ref parameter —
    // simpler and safer than rewriting the formula itself inside someone else's CampaignBehaviorBase.
    [HarmonyPatch(typeof(IncreaseSettlementHealthAction), "ApplyInternal")]
    internal static class EquestriaVillageRecoverySlowdownPatch
    {
        private const float Factor = 0.5f;

        private static void Prefix(Settlement settlement, ref float percentage)
        {
            if (settlement != null && settlement.IsVillage)
            {
                percentage *= Factor;
            }
        }
    }
}
