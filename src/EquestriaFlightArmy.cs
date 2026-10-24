using System.Collections.Generic;
using System.Linq;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.CampaignSystem.Roster;
using TaleWorlds.Core;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Cavalry without horses (10.10.2026): for ALL troops and heroes of the campaign any beast in the horse slot
    // (horse, camel - anything with a HorseComponent) is replaced by the flight scroll eq_flight_scroll_50,
    // the harness is removed. Done at session start (new game and load) right in the CharacterObject
    // equipment sets - they are shared by all soldiers of that troop, so a single pass is enough.
    // In battle such a soldier is on foot with the flight pose (EquestriaFlightScroll).
    public class EquestriaFlightArmy : CampaignBehaviorBase
    {
        public override void RegisterEvents()
        {
            CampaignEvents.OnSessionLaunchedEvent.AddNonSerializedListener(this, _ =>
            {
                EquestriaCrashLog.Try("конница на свитках", ReplaceMounts);
                EquestriaCrashLog.Try("улучшение в конницу — за свиток", UpgradesNeedWarHorse);
                EquestriaCrashLog.Try("свитки и повозки в лавках", StockAllTowns);
            });
            CampaignEvents.DailyTickSettlementEvent.AddNonSerializedListener(this, settlement =>
                EquestriaCrashLog.Try("свитки и повозки в лавке", () => StockTown(settlement)));
        }

        public override void SyncData(IDataStore dataStore)
        {
        }

        // Town shops (10.10.2026): the market is filled only with what villages and workshops
        // produce, and Equus has no horse breeders - flight scrolls and carts will not go on sale by themselves.
        // Once a day every town is topped up to a minimum: scrolls 30/40/50 - 6/4/2, carts
        // (sumpter_horse, mule) 4 each, changelings (Culture.aserai) also get 3 large carts.
        private static readonly (string Id, int Min)[] TownStock =
        {
            ("eq_flight_scroll_30", 6), ("eq_flight_scroll_40", 4), ("eq_flight_scroll_50", 2),
            ("sumpter_horse", 4), ("mule", 4),
        };

        private static void StockAllTowns()
        {
            foreach (Town town in Town.AllTowns)
            {
                StockTown(town.Settlement);
            }
        }

        private static void StockTown(Settlement settlement)
        {
            if (settlement == null || !settlement.IsTown)
            {
                return;
            }
            ItemRoster roster = settlement.ItemRoster;
            foreach (var (id, min) in TownStock)
            {
                TopUp(roster, id, min);
            }
            if (settlement.Culture?.StringId == "aserai")
            {
                TopUp(roster, "pack_camel", 3);
            }
        }

        private static void TopUp(ItemRoster roster, string itemId, int min)
        {
            ItemObject item = MBObjectManager.Instance.GetObject<ItemObject>(itemId);
            if (item == null)
            {
                return;
            }
            int have = roster.GetItemNumber(item);
            if (have < min)
            {
                roster.AddToCounts(item, min - have);
            }
        }

        // Foot races: neither horses nor scrolls (tools/replace_mounts.py FOOT_RACES)
        private static readonly HashSet<string> FootRaces = new HashSet<string> { "yak", "deer" };

        /// <summary>Carts are not rideable (equestria_items.xslt, is_mountable="false"), but the character
        /// creation wizard (background equipment) and old saves put them into the hero's horse
        /// slot - the hero "rode" a cart. We move the cart from the slot to the party's inventory, the harness too.</summary>
        public static void CartsToInventory(Hero hero)
        {
            if (hero?.CharacterObject == null)
            {
                return;
            }
            var roster = hero.PartyBelongedTo?.ItemRoster;
            bool stored = false;   // battle and civilian sets hold the same cart, put only one into the inventory
            foreach (Equipment equipment in AllEquipmentsOf(hero.CharacterObject))
            {
                EquipmentElement mount = equipment[EquipmentIndex.Horse];
                // A cart is only our three (cart mesh); in vanilla the "pack" ones also include a riding horse and
                // a nag - those are horses, StripPlayerHorseGear turns them into a scroll
                if (!EquestriaFlightScroll.IsCart(mount.Item))
                {
                    continue;
                }
                EquipmentElement harness = equipment[EquipmentIndex.HorseHarness];
                if (!stored)
                {
                    roster?.AddToCounts(mount, 1);
                    if (harness.Item != null)
                    {
                        roster?.AddToCounts(harness, 1);
                    }
                    stored = true;
                }
                equipment[EquipmentIndex.Horse] = default(EquipmentElement);
                equipment[EquipmentIndex.HorseHarness] = default(EquipmentElement);
                EquestriaCrashLog.Log($"повозка {mount.Item.StringId} у {hero.Name} убрана из слота коня "
                    + (roster != null ? "в обоз" : "(отряда нет — просто снята)"));
            }
        }

        /// <summary>The player's horse gear goes away: in Equus people ride only scrolls. The character
        /// creation wizard (background equipment) hands out a riding horse, harness and horse armor
        /// (noticed 10.10.2026 when starting as a ruler). Carts go to the inventory (CartsToInventory),
        /// a riding horse in the slot becomes a scroll, and horses, harness and horse armor are removed
        /// from the inventory. Carts stay in the inventory - they are pack animals.</summary>
        public static void StripPlayerHorseGear()
        {
            Hero hero = Hero.MainHero;
            if (hero?.CharacterObject == null)
            {
                return;
            }
            CartsToInventory(hero);
            var scroll = MBObjectManager.Instance.GetObject<ItemObject>("eq_flight_scroll_50");
            foreach (Equipment equipment in AllEquipmentsOf(hero.CharacterObject))
            {
                ItemObject mount = equipment[EquipmentIndex.Horse].Item;
                if (mount != null && mount.HasHorseComponent && scroll != null)
                {
                    equipment[EquipmentIndex.Horse] = new EquipmentElement(scroll);
                    EquestriaCrashLog.Log($"игрок: конь {mount.StringId} в слоте заменён свитком");
                }
                if (equipment[EquipmentIndex.HorseHarness].Item != null)
                {
                    equipment[EquipmentIndex.HorseHarness] = default(EquipmentElement);
                }
            }
            var roster = hero.PartyBelongedTo?.ItemRoster;
            if (roster == null)
            {
                return;
            }
            var removed = new List<string>();
            for (int i = roster.Count - 1; i >= 0; i--)
            {
                ItemRosterElement element = roster.GetElementCopyAtIndex(i);
                ItemObject item = element.EquipmentElement.Item;
                if (item == null)
                {
                    continue;
                }
                bool horse = item.HasHorseComponent && !EquestriaFlightScroll.IsCart(item);
                bool harness = item.ItemType == ItemObject.ItemTypeEnum.HorseHarness;
                if (horse || harness)
                {
                    roster.AddToCounts(element.EquipmentElement, -element.Amount);
                    removed.Add($"{item.StringId}×{element.Amount}");
                }
            }
            if (removed.Count > 0)
            {
                EquestriaCrashLog.Log("игрок: из обоза убрано конское снаряжение — " + string.Join(", ", removed));
            }
        }

        /// <summary>Upgrading to cavalry requires an item of category "horse" or "war horse"
        /// (upgrade_requires), and the engine checks the category strictly. Equus has no ordinary horses, and flight
        /// scrolls are of category "war horse" (tools/make_items.py). So the "horse" requirement of all
        /// troops is replaced with "war horse": any scroll in the inventory works for any cavalry, and the engine
        /// checks and consumes the item as usual (10.10.2026).</summary>
        public static void UpgradesNeedWarHorse()
        {
            var horse = MBObjectManager.Instance.GetObject<ItemCategory>("horse");
            var warHorse = MBObjectManager.Instance.GetObject<ItemCategory>("war_horse");
            var property = HarmonyLib.AccessTools.Property(typeof(CharacterObject), "UpgradeRequiresItemFromCategory");
            if (horse == null || warHorse == null || property == null)
            {
                EquestriaCrashLog.Warn("улучшение в конницу: нет категорий horse/war_horse или свойства требования");
                return;
            }
            int changed = 0;
            foreach (CharacterObject character in MBObjectManager.Instance.GetObjectTypeList<CharacterObject>())
            {
                if (character.UpgradeRequiresItemFromCategory == horse)
                {
                    property.SetValue(character, warHorse);
                    changed++;
                }
            }
            EquestriaCrashLog.Log($"улучшение в конницу: требование «конь» → «боевой конь» у {changed} войск");
        }

        public static void ReplaceMounts()
        {
            // Three scrolls by troop tier (10.10.2026): tier 5+ - great (+50%), 3-4 - normal
            // (+40%), lower - lesser (+30%); heroes - great.
            var great = MBObjectManager.Instance.GetObject<ItemObject>("eq_flight_scroll_50");
            var normal = MBObjectManager.Instance.GetObject<ItemObject>("eq_flight_scroll_40");
            var lesser = MBObjectManager.Instance.GetObject<ItemObject>("eq_flight_scroll_30");
            if (great == null || normal == null || lesser == null)
            {
                EquestriaCrashLog.Warn("конница на свитках: нет предметов eq_flight_scroll* — пересобери equestria_items.xml");
                return;
            }
            // A cart in the player's horse slot goes to the inventory first, otherwise the loop below would turn it into a scroll
            CartsToInventory(Hero.MainHero);
            int troops = 0, sets = 0, unmounted = 0;
            // Foot races - yaks and deer (10.10.2026): the horse slot is cleared, no scroll is given.
            // tools/replace_mounts.py does the same in XML; this is a safety net plus old saves.
            string[] raceNames = FaceGen.GetRaceNames();
            foreach (CharacterObject character in MBObjectManager.Instance.GetObjectTypeList<CharacterObject>())
            {
                bool touched = false;
                bool foot = character.Race >= 0 && character.Race < raceNames.Length
                            && FootRaces.Contains(raceNames[character.Race]);
                ItemObject scroll = character.IsHero || character.Tier >= 5 ? great : character.Tier >= 3 ? normal : lesser;
                foreach (Equipment equipment in AllEquipmentsOf(character))
                {
                    ItemObject mount = equipment[EquipmentIndex.Horse].Item;
                    if (mount == null || (!mount.HasHorseComponent && !EquestriaFlightScroll.IsScroll(mount)))
                    {
                        continue;
                    }
                    equipment[EquipmentIndex.Horse] = foot ? default(EquipmentElement) : new EquipmentElement(scroll);
                    equipment[EquipmentIndex.HorseHarness] = default(EquipmentElement);
                    if (foot)
                    {
                        unmounted++;
                    }
                    sets++;
                    touched = true;
                }
                if (touched)
                {
                    troops++;
                }
            }
            EquestriaCrashLog.Log($"конница на свитках: заменено наборов {sets} у войск/героев {troops}, у пеших народов спешено {unmounted}");
        }

        private static IEnumerable<Equipment> AllEquipmentsOf(CharacterObject character)
        {
            var result = new List<Equipment>();
            if (character.BattleEquipments != null)
            {
                result.AddRange(character.BattleEquipments.Where(e => e != null));
            }
            if (character.CivilianEquipments != null)
            {
                result.AddRange(character.CivilianEquipments.Where(e => e != null));
            }
            // Heroes have their own battle and civilian set objects, not from the troop roster.
            if (character.HeroObject != null)
            {
                if (character.HeroObject.BattleEquipment != null) result.Add(character.HeroObject.BattleEquipment);
                if (character.HeroObject.CivilianEquipment != null) result.Add(character.HeroObject.CivilianEquipment);
            }
            return result.Distinct();
        }
    }
}
