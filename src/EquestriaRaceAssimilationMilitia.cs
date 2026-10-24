using System.Reflection;
using HarmonyLib;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.Core;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Ополчение деревень/городов набирается строго из Settlement.Culture — на % рас ассимиляции
    // (EquestriaRaceAssimilation.cs) никак не смотрит (decompile TaleWorlds.CampaignSystem.dll,
    // Settlement.AddMilitiasToParty/AddTroopToMilitiaParty — приватные методы, напрямую читают
    // Culture.MeleeMilitiaTroop/RangedMilitiaTroop). По просьбе пользователя 07.10.2026 — раз уж
    // мы и так считаем доли рас, пусть ополчение набирается смешанно, пропорционально им.
    //
    // Патчим AddMilitiasToParty (НЕ AddTroopToMilitiaParty — тот зовётся дважды за вызов, melee и
    // ranged, терять которую из двух сложнее, чем перехватить на уровне выше): прогоняем ту же пару
    // вызовов AddTroopToMilitiaParty (через рефлексию — метод private), что и оригинал, но по разу
    // НА КАЖДУЮ расу с её долей, домножив ставку melee/ranged на долю расы. Внутренняя рандомизация
    // количества и шанс ветерана (MBRandom.RoundRandomized, CalculateVeteranMilitiaSpawnChance)
    // остаются ровно те же — переиспользуем исходный приватный метод, а не переписываем его логику.
    //
    // ОБЫЧНЫЙ [HarmonyPatch] (не лениво, как у RaceAssimilationTooltipPatch): этот метод не трогает
    // CampaignUIHelper/GameTexts, его JIT-пин на загрузке мода ничего не ломает (в отличие от того
    // краша — см. комментарий у RaceAssimilationTooltipPatch.Apply).
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
                // Нет данных (расселение ещё не инициализировано на этом поселении) или ровно одна
                // раса (ещё не размыто) — обычное поведение движка, трогать нечего.
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
