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
    // Полная опись данных мода в момент старта кампании: что нашлось, что нет, что стоит не там.
    //
    // Зачем: почти каждое падение до сих пор было «ссылка на пустоту» — игра берёт наш объект по
    // имени и не проверяет, нашёлся ли он. В журнале игры этого не видно вообще. Здесь мы заранее
    // называем всё, что мод обещает предоставить, и отмечаем пропажи до того, как на них наступят.
    //
    // Результат уходит в <мод>\eq_exceptions.log.
    public class EquestriaDiagnosticsBehavior : CampaignBehaviorBase
    {
        // Границы нашей карты мира — те же, что прописаны в scene.xscene (border_min / border_max).
        private const float MapSize = 400f;

        private static readonly string[] OurItems = { };

        // Главные поселения Эквестрии — по ним видно, что мир собрался целиком (см. tools/world_data.py).
        private static readonly string[] OurSettlements =
        {
            "town_empire_0", "town_empire_1", "town_empire_2", "castle_empire_0",
        };

        // Культуры Equus заняли ванильные идентификаторы: Эквестрия = empire и так далее.
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
                // Сама опись (все поселения, кланы, герои) — только в подробном режиме: у игрока она
                // перебирала бы весь мир при каждом запуске кампании ради строк, которых он не читает.
                // Отметку выше оставляем: по ней tools\selftest.ps1 понимает, что карта готова.
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

                // Шаблоны снаряжения по культуре: игра ищет их по точному совпадению культуры и
                // флагов и не проверяет результат на пустоту. Нужны все восемь сочетаний.
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

        // Все сочетания, которые умеет запрашивать DefaultEquipmentSelectionModel: лорд, правитель,
        // подросток, ребёнок — каждое ещё и в женском варианте. Отсутствие любого роняет игру в тот
        // момент, когда она решит кого-то одеть.
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

        // Порядок флагов в строке зависит от их числовых значений, поэтому сравниваем по составу.
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

        // «Центральное поселение» фракции. DefaultSettlementValueModel обращается к нему без проверки
        // (clan.MapFaction.FactionMidSettlement.HasPort), поэтому любая фракция с владениями, но с
        // пустым центром, роняет расчёт родного поселения клана.
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
            // На этом этапе центры ещё не посчитаны и у ванильных фракций — это нормально, игра
            // считает их позже. Тревожимся только за свои.
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
            // Рас у нас теперь восемь (по расе на культуру), поэтому в журнале пишем имя расы,
            // а тревожимся только за одно: герой не должен остаться ванильным человеком.
            string[] raceNames = FaceGen.GetRaceNames() ?? new string[0];
            var ours = Hero.AllAliveHeroes.Where(h => h.StringId.StartsWith("eq_")).ToList();
            EquestriaCrashLog.Log($"наших героев живо: {ours.Count} (всего в игре {Hero.AllAliveHeroes.Count})");
            // Спутники в тавернах: канонные (шаблоны spc_eq_*) должны носить свои имена
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
                // Боевой и гражданский наборы обязательны: EquipmentHelper берёт их без проверки.
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
                // Раса 0 — ванильный человек: значит, в XML расу не проставили или её не нашли
                if (character != null && character.Race == 0)
                {
                    EquestriaCrashLog.Warn($"герой {hero.StringId} остался человеком");
                }
            }
        }

        // Размер погодной сетки задаёт объект MapSnowAndRainDefiner в сцене карты. Если его нет,
        // размер остаётся нулевым, массив погоды пустой, и любое обращение к погоде по координатам
        // вылетает за границы массива (DefaultMapWeatherModel.GetWeatherEventInPosition).
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
                // Position — это CampaignVec2 (с гранью навигации); плоские координаты берутся так.
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

        // Консоль (Alt+~): equestria.report — перечитать опись в любой момент игры
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
