using System;
using System.Collections.Generic;
using System.Linq;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // A full inventory of the mod's data at campaign start: what was found, what was not, what is misplaced.
    //
    // Why: almost every crash so far has been a "reference to nothing" - the game takes our object by
    // name and does not check whether it was found. The game log does not show this at all. Here we
    // name in advance everything the mod promises to provide and flag what is missing before anyone trips on it.
    //
    // The result goes to <mod>\eq_exceptions.log.
    public class EquestriaDiagnosticsBehavior : CampaignBehaviorBase
    {
        // Bounds of our world map - the same as set in scene.xscene (border_min / border_max).
        private const float MapSize = 400f;

        private static readonly string[] OurItems = { };

        // Equestria's main settlements - they show that the world was assembled in full (see tools/world_data.py).
        private static readonly string[] OurSettlements =
        {
            "town_empire_0", "town_empire_1", "town_empire_2", "castle_empire_0",
        };

        // The Equus cultures took over vanilla ids: Equestria = empire and so on.
        private static readonly string[] OurCultures =
        {
            "empire", "vlandia", "sturgia", "khuzait", "aserai",
        };

        public override void RegisterEvents()
        {
            CampaignEvents.OnSessionLaunchedEvent.AddNonSerializedListener(this, _ => Report("запуск сессии"));
            CampaignEvents.OnNewGameCreatedEvent.AddNonSerializedListener(this, _ => Report("новая игра создана"));
        }

        public override void SyncData(IDataStore dataStore)
        {
        }

        public static void Report(string moment)
        {
            EquestriaCrashLog.Try("опись данных мода (" + moment + ")", () =>
            {
                EquestriaCrashLog.Note("опись данных мода: " + moment);
                // The inventory itself (all settlements, clans, heroes) is only in verbose mode: for a player
                // it would walk the whole world on every campaign launch for lines they never read.
                // The note above stays: tools\selftest.ps1 uses it to tell that the map is ready.
                if (!EquestriaCrashLog.Verbose)
                {
                    return;
                }
                ReportRace();
                ReportItems();
                ReportCulture();
                ReportKingdomsAndClans();
                ReportHeroes();
                ReportWeather();
                ReportSettlements();
            });
        }

        private static void ReportRace()
        {
            string[] names = FaceGen.GetRaceNames();
            int race = FaceGen.GetRaceOrDefault(EquestriaMane.RaceId);
            EquestriaCrashLog.Log($"расы в игре ({names.Length}): {string.Join(", ", names)}");
            if (race <= 0)
            {
                EquestriaCrashLog.Warn($"раса «{EquestriaMane.RaceId}» не зарегистрирована — пони будут людьми");
            }
            else
            {
                EquestriaCrashLog.Log($"раса «{EquestriaMane.RaceId}» = номер {race}");
            }
        }

        private static void ReportItems()
        {
            foreach (string id in OurItems)
            {
                var item = MBObjectManager.Instance.GetObject<ItemObject>(id);
                if (item == null)
                {
                    EquestriaCrashLog.Warn($"предмет {id} не найден — надеть его не получится");
                }
                else
                {
                    EquestriaCrashLog.Log($"предмет {id}: «{item.Name}», слот {item.ItemType}, модель {item.MultiMeshName}");
                }
            }
        }

        private static void ReportCulture()
        {
            var rosters = MBObjectManager.Instance.GetObjectTypeList<MBEquipmentRoster>().ToList();
            foreach (string id in OurCultures)
            {
                var culture = MBObjectManager.Instance.GetObject<CultureObject>(id);
                if (culture == null)
                {
                    EquestriaCrashLog.Warn($"культура {id} не найдена");
                    continue;
                }

                // Equipment templates per culture: the game looks them up by an exact match of culture and
                // flags and does not check the result for null. All eight combinations are needed.
                var mine = rosters.Where(r => r.EquipmentCulture == culture).ToList();
                var present = new HashSet<string>(
                    mine.Select(r => Normalize(r.EquipmentCategories.ToString())));
                var missing = RequiredTemplates.Where(t => !present.Contains(Normalize(t))).ToList();
                EquestriaCrashLog.Log($"культура {id}: «{culture.Name}», основная={culture.IsMainCulture}, "
                    + $"шаблонов снаряжения {mine.Count}");
                foreach (string required in missing)
                {
                    EquestriaCrashLog.Warn($"культура {id}: нет шаблона снаряжения с флагами «{required}»");
                }
            }
        }

        // All combinations DefaultEquipmentSelectionModel can request: lord, ruler,
        // teenager, child - each also in a female variant. Missing any of them crashes the game the
        // moment it decides to dress someone.
        private static readonly string[] RequiredTemplates =
        {
            "IsLordTemplate",
            "IsLordTemplate, IsFemaleTemplate",
            "IsKingdomRulerTemplate",
            "IsKingdomRulerTemplate, IsFemaleTemplate",
            "IsLordTemplate, IsChildEquipmentTemplate",
            "IsLordTemplate, IsChildEquipmentTemplate, IsFemaleTemplate",
            "IsLordTemplate, IsTeenagerEquipmentTemplate",
            "IsLordTemplate, IsTeenagerEquipmentTemplate, IsFemaleTemplate",
        };

        // The flag order in the string depends on their numeric values, so we compare by content.
        private static string Normalize(string flags)
        {
            var parts = flags.Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries)
                .Select(p => p.Trim()).OrderBy(p => p, StringComparer.Ordinal);
            return string.Join("|", parts);
        }

        private static void ReportKingdomsAndClans()
        {
            EquestriaCrashLog.Log($"королевств в игре: {Kingdom.All.Count}, кланов: {Clan.All.Count}");
            foreach (var kingdom in Kingdom.All.Where(k => k.StringId.StartsWith("kingdom_")))
            {
                string ruler = kingdom.Leader != null ? kingdom.Leader.Name.ToString() : "НЕТ ПРАВИТЕЛЯ";
                EquestriaCrashLog.Log($"королевство {kingdom.StringId}: «{kingdom.Name}», правитель {ruler}, "
                    + $"кланов {kingdom.Clans.Count}, владений {kingdom.Settlements.Count}");
                if (kingdom.Settlements.Count == 0)
                {
                    EquestriaCrashLog.Warn($"у королевства {kingdom.StringId} нет владений — это роняет старт кампании");
                }
            }
            foreach (var clan in Clan.All.Where(c => c.StringId.StartsWith("clan_eq_")
                || c.StringId.StartsWith("clan_cr_") || c.StringId.StartsWith("clan_st_")
                || c.StringId.StartsWith("clan_yk_") || c.StringId.StartsWith("clan_ch_")))
            {
                string home = clan.HomeSettlement != null ? clan.HomeSettlement.StringId : "НЕТ";
                EquestriaCrashLog.Log($"клан {clan.StringId}: «{clan.Name}», лидер "
                    + (clan.Leader != null ? clan.Leader.Name.ToString() : "НЕТ")
                    + $", героев {clan.Heroes.Count}, столица {home}, королевство "
                    + (clan.Kingdom != null ? clan.Kingdom.StringId : "нет"));
                if (clan.Leader == null)
                {
                    EquestriaCrashLog.Warn($"у клана {clan.StringId} нет лидера");
                }
            }
            ReportMidSettlements();
        }

        // The faction's "mid settlement". DefaultSettlementValueModel accesses it without a check
        // (clan.MapFaction.FactionMidSettlement.HasPort), so any faction with holdings but an
        // empty centre crashes the calculation of a clan's home settlement.
        private static void ReportMidSettlements()
        {
            var broken = new List<string>();
            foreach (var clan in Clan.All)
            {
                var faction = clan.MapFaction;
                if (faction == null)
                {
                    broken.Add(clan.StringId + " (нет MapFaction)");
                    continue;
                }
                if (faction.Settlements.Count > 0 && faction.FactionMidSettlement == null)
                {
                    broken.Add($"{clan.StringId} -> фракция {faction.StringId}, владений {faction.Settlements.Count}");
                }
            }
            // At this stage the centres are not computed yet for vanilla factions either - that is normal,
            // the game computes them later. We only worry about our own.
            var ours = broken.Where(s => s.StartsWith("clan_eq_") || s.StartsWith("clan_cr_")
                || s.StartsWith("clan_st_") || s.StartsWith("clan_yk_")
                || s.StartsWith("clan_ch_")).ToList();
            EquestriaCrashLog.Log($"фракций без центрального поселения: {broken.Count} из {Clan.All.Count} "
                + "(на этом этапе это обычное дело)");
            if (ours.Count > 0)
            {
                EquestriaCrashLog.Warn("наши кланы без центрального поселения: " + string.Join("; ", ours));
            }
        }

        private static void ReportHeroes()
        {
            // We now have eight races (one per culture), so the log records the race name,
            // and we worry about only one thing: a hero must not remain a vanilla human.
            string[] raceNames = FaceGen.GetRaceNames() ?? new string[0];
            var ours = Hero.AllAliveHeroes.Where(h => h.StringId.StartsWith("eq_")).ToList();
            EquestriaCrashLog.Log($"наших героев живо: {ours.Count} (всего в игре {Hero.AllAliveHeroes.Count})");
            // Companions in taverns: canon ones (spc_eq_* templates) must carry their own names
            var wanderers = Hero.AllAliveHeroes.Where(h => h.IsWanderer).ToList();
            var canon = wanderers.Where(h => h.CharacterObject?.OriginalCharacter?.StringId?.StartsWith("spc_eq_") == true
                || h.Template?.StringId?.StartsWith("spc_eq_") == true).ToList();
            EquestriaCrashLog.Log($"спутников в тавернах: {wanderers.Count}, канонных {canon.Count}"
                + (canon.Count > 0 ? " — " + string.Join(", ", canon.Take(12).Select(h => h.Name.ToString())) : ""));
            foreach (var hero in ours)
            {
                var character = hero.CharacterObject;
                string raceNote = character == null ? "НЕТ ПЕРСОНАЖА"
                    : (character.Race >= 0 && character.Race < raceNames.Length
                        ? raceNames[character.Race] : "раса номер " + character.Race);
                EquestriaCrashLog.Log($"  {hero.StringId}: «{hero.Name}», {raceNote}, клан "
                    + (hero.Clan != null ? hero.Clan.StringId : "НЕТ")
                    + ", отряд " + (hero.PartyBelongedTo != null ? "есть" : "нет")
                    + ", жив=" + hero.IsAlive);
                if (hero.Clan == null)
                {
                    EquestriaCrashLog.Warn($"герой {hero.StringId} без клана — он не появится на карте");
                }
                // Battle and civilian sets are mandatory: EquipmentHelper takes them without a check.
                if (character != null)
                {
                    if (character.FirstBattleEquipment == null)
                    {
                        EquestriaCrashLog.Warn($"у {hero.StringId} нет боевого снаряжения в XML");
                    }
                    if (character.FirstCivilianEquipment == null)
                    {
                        EquestriaCrashLog.Warn($"у {hero.StringId} нет гражданского снаряжения "
                            + "(<EquipmentRoster civilian=\"true\">) — выдача снаряжения упадёт");
                    }
                }
                // Race 0 is the vanilla human: so the race was not set in XML or was not found
                if (character != null && character.Race == 0)
                {
                    EquestriaCrashLog.Warn($"герой {hero.StringId} остался человеком");
                }
            }
        }

        // The weather grid size is set by the MapSnowAndRainDefiner object in the map scene. Without it
        // the size stays zero, the weather array is empty, and any weather lookup by coordinates
        // goes out of the array bounds (DefaultMapWeatherModel.GetWeatherEventInPosition).
        private static void ReportWeather()
        {
            int dimension = Campaign.Current.DefaultWeatherNodeDimension;
            if (dimension <= 0)
            {
                EquestriaCrashLog.Warn("погодная сетка нулевого размера — в сцене карты нет объекта "
                    + "MapSnowAndRainDefiner; обращение к погоде уронит игру");
            }
            else
            {
                EquestriaCrashLog.Log($"погодная сетка: {dimension}x{dimension}");
            }
        }

        private static void ReportSettlements()
        {
            var all = Settlement.All;
            EquestriaCrashLog.Log($"поселений всего: {all.Count}");

            var outside = new List<string>();
            foreach (var settlement in all)
            {
                // Position is a CampaignVec2 (with a navmesh face); flat coordinates are taken like this.
                var p = settlement.GetPosition2D;
                if (p.x < 0f || p.y < 0f || p.x > MapSize || p.y > MapSize)
                {
                    outside.Add($"{settlement.StringId} ({p.x:F0}, {p.y:F0})");
                }
            }
            if (outside.Count > 0)
            {
                EquestriaCrashLog.Warn($"за границами карты 0..{MapSize:F0}: {outside.Count} шт. — "
                    + string.Join("; ", outside.Take(10))
                    + (outside.Count > 10 ? " …" : ""));
            }
            else
            {
                EquestriaCrashLog.Log($"все поселения внутри карты 0..{MapSize:F0}");
            }

            foreach (string id in OurSettlements)
            {
                var settlement = Settlement.Find(id);
                if (settlement == null)
                {
                    EquestriaCrashLog.Warn($"поселение {id} не найдено");
                    continue;
                }
                string owner = settlement.OwnerClan != null ? settlement.OwnerClan.StringId : "НЕТ ВЛАДЕЛЬЦА";
                EquestriaCrashLog.Log($"поселение {id}: «{settlement.Name}», "
                    + $"({settlement.GetPosition2D.x:F1}, {settlement.GetPosition2D.y:F1}), "
                    + $"культура {(settlement.Culture != null ? settlement.Culture.StringId : "НЕТ")}, "
                    + $"владелец {owner}, деревень рядом {settlement.BoundVillages?.Count ?? 0}");
                if (settlement.OwnerClan == null)
                {
                    EquestriaCrashLog.Warn($"у поселения {id} нет владельца");
                }
            }
        }

        // Console (Alt+~): equestria.report - redo the inventory at any point in the game
        [CommandLineFunctionality.CommandLineArgumentFunction("report", "equestria")]
        public static string ReportCommand(List<string> args)
        {
            if (Campaign.Current == null)
            {
                return "Available only in a campaign.";
            }
            Report("по команде из консоли");
            return "Report written to eq_exceptions.log";
        }
    }
}
