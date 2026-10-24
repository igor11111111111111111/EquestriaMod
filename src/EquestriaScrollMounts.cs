using HarmonyLib;
using TaleWorlds.CampaignSystem.Roster;
using TaleWorlds.Core;

namespace EquestriaMod
{
    // Flight scrolls in the baggage are "horses" for the map (10.10.2026): "foot soldiers on horses" in party
    // speed (DefaultPartySpeedCalculatingModel uses ItemRoster.NumberOfMounts). The engine computes
    // NumberOfMounts itself and only from items with a HorseComponent (riding, not pack animals), while the
    // scroll has no component - so we patch both places where the counter is kept: roster additions/removals and
    // the full recount after a save is loaded. Like a vanilla horse - only without a modifier.
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
    // Slaughter in the inventory (10.10.2026, found by the user): InventoryLogic.IsSlaughterable allows
    // slaughtering ANY item of type Horse - so both the cart (pack wagon) and the flight scroll (which has
    // no HorseComponent; SlaughterItem reads MeatCount - crash). We forbid both. We patch both
    // IsSlaughterable and its caller CanSlaughterItem: the former is small, the JIT may inline it.
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
