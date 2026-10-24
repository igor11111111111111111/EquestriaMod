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
    // Краш 10.10.2026 (прогон -MixedBirths, 24-й день): отряд лорда заходит в город и продаёт
    // добычу (PartiesSellLootCampaignBehavior.OnSettlementEntered). Ванильное условие
    //   item.ItemType != Horse || !item.HorseComponent.IsRideable || …
    // считает, что у любого предмета типа «конь» есть HorseComponent. У свитков полёта
    // (eq_flight_scroll_*) тип Horse, а компонента нет — NullReferenceException, как только свиток
    // попал в обоз лорда (добыча после боя). Код повторён целиком, свиток считается ездовым и
    // не продаётся — как ванильные ездовые кони, которые лорды держат для своей конницы.
    // Остальные обращения к HorseComponent в кампании проверены (декомпиляция 10.10.2026):
    // защищены HasHorseComponent/IsMountable или уже закрыты патчами EquestriaFlightScroll.
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
                    // свиток полёта (компонента нет) — ездовой, как и целый ездовой конь
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

    // Краш 10.10.2026 (прогон -MixedBirths, сохранение на 45-м дне): снимок главного героя для
    // карточки сохранения (SandBox.View.MainHeroSaveVisualSupplier.GetMainHeroVisualCode) при
    // непустом слоте коня читает item.HorseComponent.Monster — у свитка его нет. Падало ЛЮБОЕ
    // сохранение героя со свитком полёта. На время снимка свиток и сбруя снимаются с героя
    // (на снимке он пеший, как и в игре — свиток не виден) и сразу возвращаются.
    //
    // ВНИМАНИЕ: ставится НЕ атрибутом (PatchAll при загрузке мода), а из Apply() на старте игры
    // (SubModule.OnGameStart). Метод обращается к ActionIndexCache.act_inventory_idle; при установке
    // патча Harmony компилирует оригинал, и движок заранее строит кэш индексов действий — до того, как
    // прочитаны анимации пони. Итог (10.10.2026): все персонажи в окнах, включая редактор внешности,
    // лежали горизонтально. См. память bannerlord-harmony-patch-timing.
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

    // Сценка-уведомление с персонажем верхом (единственная — присяга державе,
    // PledgeAllegianceSceneNotificationItem, useHorse: true): GauntletSceneNotification.OpenScene
    // берёт item.HorseComponent.Monster из слота коня — со свитком краш при вступлении в державу.
    // Персонаж со свитком в такой сценке стоит пешим.
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
