using HarmonyLib;
using TaleWorlds.CampaignSystem.Roster;
using TaleWorlds.Core;

namespace EquestriaMod
{
    // Свитки полёта в обозе — это «кони» для карты (10.10.2026): «пешие воины на конях» в скорости
    // отряда (DefaultPartySpeedCalculatingModel берёт ItemRoster.NumberOfMounts). Движок считает
    // NumberOfMounts сам и только по предметам с HorseComponent (ездовые, не вьючные), а у свитка
    // компонента нет — потому патчим оба места, где ведётся счётчик: пополнение/убыль ростера и
    // полный пересчёт после загрузки сохранения. Как у ванильного коня — только без модификатора.
    [HarmonyPatch(typeof(ItemRoster), "OnRosterUpdated")]
    internal static class EquestriaScrollMountsOnUpdate
    {
        private static void Postfix(ItemRoster __instance, ref ItemRosterElement itemRosterElement, int count)
        {
            EquipmentElement element = itemRosterElement.EquipmentElement;
            if (element.ItemModifier == null && EquestriaFlightScroll.IsScroll(element.Item))
            {
                EquestriaScrollMounts.Add(__instance, count);
            }
        }
    }

    [HarmonyPatch(typeof(ItemRoster), "CalculateCachedStats")]
    internal static class EquestriaScrollMountsOnLoad
    {
        private static void Postfix(ItemRoster __instance)
        {
            int scrolls = 0;
            for (int i = 0; i < __instance.Count; i++)
            {
                ItemRosterElement element = __instance.GetElementCopyAtIndex(i);
                if (element.EquipmentElement.ItemModifier == null && EquestriaFlightScroll.IsScroll(element.EquipmentElement.Item))
                {
                    scrolls += element.Amount;
                }
            }
            if (scrolls != 0)
            {
                EquestriaScrollMounts.Add(__instance, scrolls);
            }
        }
    }

    internal static class EquestriaScrollMounts
    {
        private static readonly AccessTools.FieldRef<ItemRoster, int> Mounts =
            AccessTools.FieldRefAccess<ItemRoster, int>("<NumberOfMounts>k__BackingField");

        internal static void Add(ItemRoster roster, int count)
        {
            Mounts(roster) += count;
        }
    }
}

namespace EquestriaMod
{
    // Забой в инвентаре (10.10.2026, нашёл пользователь): InventoryLogic.IsSlaughterable разрешает
    // забить ЛЮБОЙ предмет типа Horse — значит, и повозку (вьючная телега), и свиток полёта (а у него
    // нет HorseComponent, SlaughterItem читает MeatCount — краш). Запрещаем обоим. Патчим и
    // IsSlaughterable, и вызывающий CanSlaughterItem: первый маленький, JIT может его встроить.
    [HarmonyPatch(typeof(TaleWorlds.CampaignSystem.Inventory.InventoryLogic), "IsSlaughterable")]
    internal static class EquestriaNoSlaughterCarts
    {
        private static void Postfix(TaleWorlds.Core.ItemObject item, ref bool __result)
        {
            if (__result && (EquestriaFlightScroll.IsCart(item) || EquestriaFlightScroll.IsScroll(item)))
            {
                __result = false;
            }
        }
    }

    [HarmonyPatch(typeof(TaleWorlds.CampaignSystem.Inventory.InventoryLogic), "CanSlaughterItem")]
    internal static class EquestriaNoSlaughterCartsCheck
    {
        private static void Postfix(TaleWorlds.Core.ItemRosterElement element, ref bool __result)
        {
            var item = element.EquipmentElement.Item;
            if (__result && (EquestriaFlightScroll.IsCart(item) || EquestriaFlightScroll.IsScroll(item)))
            {
                __result = false;
            }
        }
    }
}
