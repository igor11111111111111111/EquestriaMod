using System;
using System.Linq;
using System.Reflection;
using HarmonyLib;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Actions;
using TaleWorlds.CampaignSystem.CampaignBehaviors;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.Core;

namespace EquestriaMod
{
    // Crash 10.10.2026 (-MixedBirths run, day 24): a lord's party enters a town and sells
    // loot (PartiesSellLootCampaignBehavior.OnSettlementEntered). The vanilla condition
    //   item.ItemType != Horse || !item.HorseComponent.IsRideable || …
    // assumes that any item of type "horse" has a HorseComponent. Flight scrolls
    // (eq_flight_scroll_*) have type Horse but no component: a NullReferenceException as soon as a scroll
    // gets into a lord's baggage (loot after a battle). The code is repeated in full, the scroll counts
    // as a riding mount and is not sold, like the vanilla riding horses that lords keep for their cavalry.
    // The other HorseComponent accesses in the campaign were checked (decompilation 10.10.2026):
    // guarded by HasHorseComponent/IsMountable or already covered by EquestriaFlightScroll patches.
    [HarmonyPatch(typeof(PartiesSellLootCampaignBehavior), nameof(PartiesSellLootCampaignBehavior.OnSettlementEntered))]
    internal static class EquestriaScrollLootFix
    {
        private static bool Prefix(MobileParty mobileParty, Settlement settlement)
        {
            if (!Campaign.Current.GameStarted || mobileParty == null || settlement == null
                || FactionManager.IsAtWarAgainstFaction(mobileParty.MapFaction, settlement.MapFaction)
                || mobileParty.IsMainParty || !mobileParty.IsLordParty || mobileParty.IsDisbanding || !settlement.IsTown)
            {
                return false;
            }
            int gold = settlement.SettlementComponent.Gold;
            for (int i = 0; i < mobileParty.ItemRoster.Count; i++)
            {
                ItemRosterElement subject = mobileParty.ItemRoster[i];
                ItemObject item = subject.EquipmentElement.Item;
                if (item == null || item.IsFood)
                {
                    continue;
                }
                ItemModifier itemModifier = subject.EquipmentElement.ItemModifier;
                if (item.ItemType == ItemObject.ItemTypeEnum.Horse)
                {
                    HorseComponent horse = item.HorseComponent;
                    // a flight scroll (no component) is a riding mount, just like a whole riding horse
                    if (horse == null || (horse.IsRideable && itemModifier == null && !horse.IsPackAnimal))
                    {
                        continue;
                    }
                }
                int itemPrice = settlement.Town.GetItemPrice(subject.EquipmentElement, mobileParty, isSelling: true);
                if (itemPrice <= 0)
                {
                    continue;
                }
                int amount = subject.Amount;
                int num = itemPrice * amount < gold ? amount : gold / itemPrice;
                if (num > 0)
                {
                    SellItemsAction.Apply(mobileParty.Party, settlement.Party, subject, num, settlement);
                }
            }
            return false;
        }
    }

    // Crash 10.10.2026 (-MixedBirths run, save on day 45): the main hero snapshot for the
    // save card (SandBox.View.MainHeroSaveVisualSupplier.GetMainHeroVisualCode) with a
    // non-empty horse slot reads item.HorseComponent.Monster, which the scroll does not have. ANY
    // save of a hero with a flight scroll crashed. For the snapshot the scroll and harness are taken off the hero
    // (in the snapshot he is on foot, as in the game, the scroll is not visible) and put back right away.
    //
    // NOTE: it is applied NOT by an attribute (PatchAll when the mod loads) but from Apply() at game start
    // (SubModule.OnGameStart). The method accesses ActionIndexCache.act_inventory_idle; when the
    // patch is applied Harmony compiles the original, and the engine builds the action index cache early, before
    // the pony animations are read. Result (10.10.2026): all characters in screens, including the appearance editor,
    // lay horizontally. See the bannerlord-harmony-patch-timing memory.
    internal static class EquestriaScrollSaveVisualFix
    {
        private static bool _patched;

        public static void Apply(Harmony harmony)
        {
            if (_patched || harmony == null)
            {
                return;
            }
            _patched = true;
            var target = typeof(SandBox.View.MainHeroSaveVisualSupplier)
                .GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
                .FirstOrDefault(m => m.Name.EndsWith("GetMainHeroVisualCode", StringComparison.Ordinal));
            if (target == null)
            {
                EquestriaCrashLog.Warn("свиток полёта: MainHeroSaveVisualSupplier.GetMainHeroVisualCode НЕ НАЙДЕН — патч сохранения не поставлен");
                return;
            }
            harmony.Patch(target,
                prefix: new HarmonyMethod(typeof(EquestriaScrollSaveVisualFix), nameof(Prefix)),
                finalizer: new HarmonyMethod(typeof(EquestriaScrollSaveVisualFix), nameof(Finalizer)));
            EquestriaCrashLog.Log("свиток полёта: патч снимка героя для сохранения поставлен");
        }

        private static void Prefix(out EquipmentElement[] __state)
        {
            __state = null;
            Equipment equipment = Hero.MainHero?.BattleEquipment;
            if (equipment == null || !EquestriaFlightScroll.IsScroll(equipment[EquipmentIndex.Horse].Item))
            {
                return;
            }
            __state = new[] { equipment[EquipmentIndex.Horse], equipment[EquipmentIndex.HorseHarness] };
            equipment[EquipmentIndex.Horse] = default(EquipmentElement);
            equipment[EquipmentIndex.HorseHarness] = default(EquipmentElement);
        }

        private static void Finalizer(EquipmentElement[] __state)
        {
            Equipment equipment = Hero.MainHero?.BattleEquipment;
            if (__state == null || equipment == null)
            {
                return;
            }
            equipment[EquipmentIndex.Horse] = __state[0];
            equipment[EquipmentIndex.HorseHarness] = __state[1];
        }
    }

    // A notification scene with a mounted character (the only one is pledging allegiance to a realm,
    // PledgeAllegianceSceneNotificationItem, useHorse: true): GauntletSceneNotification.OpenScene
    // takes item.HorseComponent.Monster from the horse slot, so with a scroll it crashes when joining a realm.
    // A character with a scroll stands on foot in such a scene.
    [HarmonyPatch(typeof(SceneNotificationData.SceneNotificationCharacter), MethodType.Constructor,
        new[] { typeof(BasicCharacterObject), typeof(Equipment), typeof(BodyProperties), typeof(bool),
                typeof(uint), typeof(uint), typeof(bool) })]
    internal static class EquestriaScrollSceneNotificationFix
    {
        private static void Prefix(BasicCharacterObject character, Equipment overriddenEquipment, bool useCivilianEquipment,
            ref bool useHorse)
        {
            if (!useHorse)
            {
                return;
            }
            Equipment equipment = overriddenEquipment
                ?? (useCivilianEquipment ? character?.FirstCivilianEquipment : character?.Equipment);
            ItemObject mount = equipment?[EquipmentIndex.Horse].Item;
            if (mount != null && !mount.HasHorseComponent)
            {
                useHorse = false;
            }
        }
    }
}
