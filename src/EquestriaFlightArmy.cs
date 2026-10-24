using System.Collections.Generic;
using System.Linq;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.CampaignSystem.Roster;
using TaleWorlds.Core;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Конница без коней (10.10.2026): у ВСЕХ войск и героев кампании любой зверь в слоте коня
    // (конь, верблюд — всё, у чего есть HorseComponent) заменяется свитком полёта eq_flight_scroll_50,
    // сбруя снимается. Делается при старте сессии (новая игра и загрузка) прямо в наборах
    // снаряжения CharacterObject — они общие на всех бойцов этого войска, поэтому хватает одного
    // прохода. В бою такой боец — пеший с позой полёта (EquestriaFlightScroll).
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

        // Лавки городов (10.10.2026): рынок наполняется только тем, что производят деревни и
        // мастерские, а коневоден в Эквусе нет — свитки полёта и повозки сами в продаже не появятся.
        // Раз в день каждому городу докладываем до минимума: свитков 30/40/50 — 6/4/2, повозок
        // (sumpter_horse, mule) по 4, у чейнджлингов (Culture.aserai) ещё 3 больших повозки.
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

        // Пешие народы: ни коней, ни свитков (tools/replace_mounts.py FOOT_RACES)
        private static readonly HashSet<string> FootRaces = new HashSet<string> { "yak", "deer" };

        /// <summary>Повозки не ездовые (equestria_items.xslt, is_mountable="false"), но мастер
        /// создания персонажа (снаряжение предыстории) и старые сохранения кладут их герою в слот
        /// коня — герой «ехал» на телеге. Убираем повозку из слота в обоз отряда, сбрую — тоже.</summary>
        public static void CartsToInventory(Hero hero)
        {
            if (hero?.CharacterObject == null)
            {
                return;
            }
            var roster = hero.PartyBelongedTo?.ItemRoster;
            bool stored = false;   // боевой и гражданский наборы — одна и та же повозка, в обоз одну
            foreach (Equipment equipment in AllEquipmentsOf(hero.CharacterObject))
            {
                EquipmentElement mount = equipment[EquipmentIndex.Horse];
                // Повозка — только наши три (меш телеги); у ванили «вьючные» ещё ездовая лошадь и
                // кляча — это кони, их StripPlayerHorseGear меняет на свиток
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

        /// <summary>Конское снаряжение игрока — прочь: в Эквусе ездят только на свитках. Мастер
        /// создания персонажа (снаряжение предыстории) выдаёт ездового коня, сбрую и конскую броню
        /// (замечено 10.10.2026 при старте правителем). Повозки уходят в обоз (CartsToInventory),
        /// ездовой конь в слоте становится свитком, а кони, сбруя и конская броня из обоза
        /// убираются. Повозки в обозе остаются — они вьючные.</summary>
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

        /// <summary>Улучшение в конницу требует предмет категории «конь» или «боевой конь»
        /// (upgrade_requires), и движок сверяет категорию строго. Обычных коней в Эквусе нет, а свитки
        /// полёта — категории «боевой конь» (tools/make_items.py). Поэтому требование «конь» у всех
        /// войск заменяем на «боевой конь»: любой свиток в обозе годится для любой конницы, а движок
        /// сверяет и тратит предмет как обычно (10.10.2026).</summary>
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
            // Три свитка по рангу войска (10.10.2026): ранг 5+ — великий (+50%), 3–4 — обычный
            // (+40%), ниже — малый (+30%); герои — великий.
            var great = MBObjectManager.Instance.GetObject<ItemObject>("eq_flight_scroll_50");
            var normal = MBObjectManager.Instance.GetObject<ItemObject>("eq_flight_scroll_40");
            var lesser = MBObjectManager.Instance.GetObject<ItemObject>("eq_flight_scroll_30");
            if (great == null || normal == null || lesser == null)
            {
                EquestriaCrashLog.Warn("конница на свитках: нет предметов eq_flight_scroll* — пересобери equestria_items.xml");
                return;
            }
            // Повозка в слоте коня у игрока — сначала в обоз, иначе цикл ниже сделал бы из неё свиток
            CartsToInventory(Hero.MainHero);
            int troops = 0, sets = 0, unmounted = 0;
            // Пешие народы — яки и олени (10.10.2026): слот коня очищается, свитка не дают.
            // То же делает tools/replace_mounts.py в XML; здесь — страховка и старые сохранения.
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
            // У героев боевой и гражданский наборы — свои объекты, не из ростера войска.
            if (character.HeroObject != null)
            {
                if (character.HeroObject.BattleEquipment != null) result.Add(character.HeroObject.BattleEquipment);
                if (character.HeroObject.CivilianEquipment != null) result.Add(character.HeroObject.CivilianEquipment);
            }
            return result.Distinct();
        }
    }
}
