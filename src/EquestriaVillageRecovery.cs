using HarmonyLib;
using TaleWorlds.CampaignSystem.Actions;
using TaleWorlds.CampaignSystem.Settlements;

namespace EquestriaMod
{
    // Скорость восстановления деревни после полного разорения (SettlementHitPoints 0 -> 1, пока
    // не дойдёт до 1 — деревня в состоянии Looted, войти и взаимодействовать нельзя). Декомпил
    // 07.10.2026: VillageHealCampaignBehavior.DailyTickSettlement считает ставку
    // 0.06 + (7000 - clamp(сила державы-владельца, 1000, 7000)) / 100000 — то есть 6%/день у
    // сильной державы, 12%/день у слабой, и передаёт её единственному вызову
    // IncreaseSettlementHealthAction.Apply (других вызовов этого метода в игре нет — проверено).
    // По просьбе пользователя 07.10.2026 — вдвое медленнее, только для деревень (осады городов не
    // трогаем, это отдельный баланс). Патчим ApplyInternal (приватный) через Harmony ref-параметр —
    // проще и safer, чем переписывать саму формулу внутри чужого CampaignBehaviorBase.
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
