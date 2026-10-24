using System;
using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using Helpers;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Encounters;
using TaleWorlds.CampaignSystem.GameComponents;
using TaleWorlds.CampaignSystem.GameMenus;
using TaleWorlds.CampaignSystem.GameState;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.CampaignSystem.Party.PartyComponents;
using TaleWorlds.CampaignSystem.Roster;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.CampaignSystem.ViewModelCollection.Party;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.Localization;
using TaleWorlds.ObjectSystem;
using TaleWorlds.SaveSystem;

namespace EquestriaMod
{
    // Лагеря наёмников у столиц держав: место, где можно купить войска наёмных рот.
    //
    // В ванили роты нанимаются только целиком и только как клан-наёмник державы, а их войска
    // (jawwal_tier_1 и прочие 42 записи, у нас переименованные — см. MERC_NAMES в
    // tools/make_troops.py) игроку недоступны вовсе. Здесь они продаются поштучно.
    //
    // Как устроено:
    //   1. у ворот каждой столицы стоит отряд-лагерь (CustomPartyComponent), он не ходит и ни с кем
    //      не воюет; палатки рядом с ним ставит tools/map_props.py по тем же точкам (CampSpots);
    //   2. при встрече с ним в меню появляется строка «Нанять наёмников», а в разговоре — свои
    //      ответы вместо ванильной заглушки;
    //   3. она открывает обычное окно передачи войск: слева товар, справа отряд игрока, внизу
    //      счётчик «Вы заплатите».
    //
    // Лагеря независимы: у каждого свой прилавок и своё доверие к игроку, то есть и своя скидка.
    //
    // Про деньги. Движок сам считает золото только в двух случаях: выкуп пленных и квестовое
    // жалованье (PartyScreenLogic, ветки TransferableWithTrade и QuestTroopManage). Квестовая
    // считает наоборот — долг за тех, кого ОСТАВИЛИ, — поэтому цену ведём сами: на каждую
    // передачу пересчитываем стоимость набранного и кладём её в CurrentData.PartyGoldChangeAmount,
    // а событие PartyGoldChange дёргаем через отражение (наружу оно не открыто). Дальше движок
    // сам показывает сумму внизу окна, не даёт увести войск больше, чем есть денег, и по кнопке
    // «Готово» списывает золото.
    public class EquestriaMercCampBehavior : CampaignBehaviorBase
    {
        // Где стоят лагеря: столица державы -> точка у её ворот. Места подобраны по gate_pos из
        // equestria_settlements.xml — на суше и не ближе семи метров к любому поселению.
        private static readonly Dictionary<string, Vec2> CampSpots = new Dictionary<string, Vec2>
        {
            { "town_empire_0", new Vec2(543.5f, 502.5f) },    // Кантерлот, Солнечная Эквестрия
            { "town_empire_7", new Vec2(426.8f, 448.0f) },    // Лас-Пегасус, Лунная Эквестрия
            { "town_empire_14", new Vec2(533.7f, 454.1f) },   // Понивилль, Держава Дружбы
            { "town_empire_20", new Vec2(666.5f, 642.7f) },   // Кристальный Город, Кристальная империя
            { "town_vlandia_0", new Vec2(986.8f, 812.9f) },   // Грифонстоун, Грифония
            { "town_battania_0", new Vec2(182.7f, 564.5f) },  // Гора Арис, Гиппогриффия
            { "town_nord_0", new Vec2(101.9f, 648.2f) },      // Оленья Роща, Оления
            { "town_sturgia_0", new Vec2(721.1f, 297.6f) },   // Логово Лорда Драконов, Драконьи земли
            { "town_khuzait_0", new Vec2(555.7f, 772.2f) },   // Яктаун, Яководье
            { "town_aserai_0", new Vec2(285.3f, 800.8f) },    // Весалиполис, Ульи чейнджлингов
        };

        // В самом отряде-лагере стоит один хозяин: он и на карте виден, и в списке сторон боя не
        // выглядит войском. Товар в отряде не лежит вовсе — он отдельным прилавком (см. _stocks).
        private const int GuardCount = 1;
        private const float PriceFactor = 0.75f;    // наёмник дешевле ополченца своей ступени
        // Товар копится сам: в начале игры лагерь пуст, каждый день приходят вольные бойцы, но
        // больше предела в лагере не задерживается. И предел, и приход растут с доверием: где
        // игрока знают, туда охотнее идут наниматься.
        //   предел  = 30 + доверие          (130 при полном доверии)
        //   приход  = 4 + доверие / 10      (14 в день при полном)
        private const int StockLimitBase = 30;
        private const int ComeADayBase = 4;
        private const int RelationPerCome = 10;
        // И уходит: без этого лагерь однажды забивался доверху теми, кого никто не берёт (дорогими
        // третьими ступенями), новым бойцам не оставалось места, и прилавок замирал навсегда.
        // Уходит доля прилавка, а не просто пара бойцов: при постоянном числе уход сравнялся бы с
        // приходом и лагерь бы топтался около нуля, а долей он наполняется до предела и там
        // обновляется (при 10% в день — примерно треть состава за неделю).
        private const float LeaveShare = 0.1f;
        // Каким приходить: 60% младшая ступень роты, 30% средняя, 10% старшая. Ступень берётся из
        // ванильного id войска (клан_tier_N), он же определяет и цену.
        private static readonly float[] ComeShare = { 60f, 30f, 10f };
        // За своих бойцов, приведённых в лагерь, дают половину цены найма. Полную платить нельзя:
        // наёмник первой ступени растёт до третьей, и на разнице получалась бы денежная мельница.
        // А вот отменить свою же покупку в этом заходе можно без потерь — это просто откат.
        private const float SellBackFactor = 0.5f;
        // Доверие лагеря к игроку: 0 в начале игры, 100 предел. Каждые три единицы дают процент
        // скидки, то есть при полном доверии наём дешевле на 33%. Растёт от потраченного: единица
        // за каждые четыреста монет, остаток не пропадает и копится до следующей. У каждого лагеря
        // доверие своё: где покупаешь, там и ценят.
        private const int RelationMax = 100;
        private const int RelationPerPercent = 3;
        private const int CoinsPerPoint = 400;

        // Лагеря лежат в сохранении несколькими списками, а не одним списком своих объектов:
        // собственный класс движку пришлось бы объявлять отдельно (SaveableTypeDefiner), а списки
        // и словари готовых типов он везёт сам. Порядок во всех списках общий.
        // НО не все: List<TroopRoster> движок 1.4.8 не знает — сохранение падало с «Невозможно
        // создать сохранение» (Cant find definition for List`1[TroopRoster], найдено 10.10.2026).
        // Объявлен ниже, в EquestriaMercCampTypeDefiner.
        private List<string> _townIds = new List<string>();
        private List<MobileParty> _parties = new List<MobileParty>();
        private List<TroopRoster> _stocks = new List<TroopRoster>();
        private List<int> _relations = new List<int>();
        private List<int> _spents = new List<int>();

        // Старые поля одиночного лагеря: остались ради сохранений, сделанных до появления
        // остальных девяти. При загрузке их содержимое переезжает в списки (см. Migrate).
        private MobileParty _camp;
        private TroopRoster _stock;
        private int _relation;
        private int _spent;

        private int _open = -1;                             // с каким лагерем сейчас идёт торг
        private Dictionary<CharacterObject, int> _onOpen;   // сколько чего было, когда открыли окно

        public override void RegisterEvents()
        {
            CampaignEvents.OnSessionLaunchedEvent.AddNonSerializedListener(this, OnSessionLaunched);
            CampaignEvents.OnNewGameCreatedEvent.AddNonSerializedListener(this, OnNewGameCreated);
            CampaignEvents.OnGameLoadFinishedEvent.AddNonSerializedListener(this, EnsureCamps);
            CampaignEvents.DailyTickEvent.AddNonSerializedListener(this, OnDailyTick);
        }

        public override void SyncData(IDataStore dataStore)
        {
            dataStore.SyncData("_eqMercTowns", ref _townIds);
            dataStore.SyncData("_eqMercParties", ref _parties);
            dataStore.SyncData("_eqMercStocks", ref _stocks);
            dataStore.SyncData("_eqMercRelations", ref _relations);
            dataStore.SyncData("_eqMercSpents", ref _spents);
            // Одиночный лагерь из старых сохранений
            dataStore.SyncData("_eqMercCamp", ref _camp);
            dataStore.SyncData("_eqMercStock", ref _stock);
            dataStore.SyncData("_eqMercRelation", ref _relation);
            dataStore.SyncData("_eqMercSpent", ref _spent);
            _townIds = _townIds ?? new List<string>();
            _parties = _parties ?? new List<MobileParty>();
            _stocks = _stocks ?? new List<TroopRoster>();
            _relations = _relations ?? new List<int>();
            _spents = _spents ?? new List<int>();
        }

        // ---- лагеря на карте

        private int Count => _townIds.Count;

        private int IndexOfTown(string townId)
        {
            return _townIds.IndexOf(townId);
        }

        private int IndexOfParty(MobileParty party)
        {
            return party == null ? -1 : _parties.IndexOf(party);
        }

        private void OnNewGameCreated(CampaignGameStarter starter)
        {
            EnsureCamps();
        }

        private void EnsureCamps()
        {
            EquestriaCrashLog.Try("лагеря наёмников", () =>
            {
                Migrate();
                foreach (var spot in CampSpots)
                {
                    int at = IndexOfTown(spot.Key);
                    if (at >= 0 && _parties[at] != null && _parties[at].IsActive)
                    {
                        Park(_parties[at], spot.Value);
                        continue;
                    }
                    var home = Settlement.Find(spot.Key);
                    if (home == null)
                    {
                        EquestriaCrashLog.Warn("лагерь наёмников: нет поселения " + spot.Key);
                        continue;
                    }
                    var party = Create(home, spot.Value);
                    if (at >= 0)
                    {
                        _parties[at] = party;       // отряд потерялся (старое сохранение), ставим заново
                    }
                    else
                    {
                        _townIds.Add(spot.Key);
                        _parties.Add(party);
                        _stocks.Add(TroopRoster.CreateDummyTroopRoster());
                        _relations.Add(0);
                        _spents.Add(0);
                    }
                    EquestriaCrashLog.Log($"лагерь наёмников: поставлен у {home.Name}"
                        + $" ({spot.Value.x:0.0}, {spot.Value.y:0.0})");
                }
                DropStrangers();
            });
        }

        // Сохранение из времён единственного лагеря под Кантерлотом: переносим отряд, прилавок и
        // доверие в списки, чтобы игрок не потерял ни закупленное, ни заработанную скидку.
        private void Migrate()
        {
            if (_camp == null && _stock == null)
            {
                return;
            }
            const string canterlot = "town_empire_0";
            if (IndexOfTown(canterlot) < 0)
            {
                _townIds.Add(canterlot);
                _parties.Add(_camp);
                _stocks.Add(_stock ?? TroopRoster.CreateDummyTroopRoster());
                _relations.Add(_relation);
                _spents.Add(_spent);
                EquestriaCrashLog.Log($"лагерь наёмников: старый лагерь перенесён, доверие {_relation}");
            }
            _camp = null;
            _stock = null;
            _relation = 0;
            _spent = 0;
        }

        private MobileParty Create(Settlement home, Vec2 spot)
        {
            var guards = TroopRoster.CreateDummyTroopRoster();
            var keeper = Kinds().FirstOrDefault();
            if (keeper != null)
            {
                guards.AddToCounts(keeper, GuardCount);
            }
            var party = CustomPartyComponent.CreateCustomPartyWithTroopRoster(
                new CampaignVec2(spot, isOnLand: true), 0f, home,
                new TextObject("{=eq_merc_camp_name}Mercenary camp"), null, guards,
                TroopRoster.CreateDummyTroopRoster(), null, "", "", 0f, avoidHostileActions: true);
            Park(party, spot);
            return party;
        }

        /// <summary>Это один из наших лагерей? Нужно модели голода (см. EquestriaCampFoodModel).</summary>
        internal static bool IsCampParty(MobileParty party)
        {
            var behaviour = Campaign.Current?.GetCampaignBehavior<EquestriaMercCampBehavior>();
            return behaviour != null && behaviour.IndexOfParty(party) >= 0;
        }

        // Хозяин лагеря: ровно один и всегда здоровый. Без присмотра отряд голодал (еды ему никто
        // не возит) и к утру все двенадцать «хозяев» лежали ранеными — видно на карте 25.09.2026.
        // Еду отключает EquestriaCampFoodModel, а раненых лечим здесь: тот же приём, что у игры,
        // — заменить роспись на здоровую.
        private static void Keeper(MobileParty party)
        {
            var roster = party.MemberRoster;
            var keeper = roster.GetTroopRoster().FirstOrDefault().Character ?? Kinds().FirstOrDefault();
            if (keeper == null)
            {
                return;
            }
            if (roster.TotalManCount == GuardCount && roster.TotalWoundedRegulars == 0)
            {
                return;
            }
            roster.Clear();
            roster.AddToCounts(keeper, GuardCount);
        }

        // Лагерь никуда не идёт и никого не преследует: без этого отряд с обычным ИИ уходит
        // «домой» в столицу и исчезает из виду.
        private static void Park(MobileParty party, Vec2 spot)
        {
            Keeper(party);
            party.Position = new CampaignVec2(spot, isOnLand: true);
            party.Ai.SetDoNotMakeNewDecisions(true);
            party.SetMoveModeHold();
            party.IgnoreByOtherPartiesTill(CampaignTime.Never);
            party.SetPartyUsedByQuest(true);      // чтобы лордские отряды не считали его добычей
            // Лагерь ни за кого не воюет. Три отдельные защиты, потому что в игре три разных пути
            // угодить в чужой бой:
            //   ShouldJoinPlayerBattles — по нему игра набирает соседей в бой ИГРОКА. Наш отряд
            //     не лордский, не разбойничий и не дозорный, так что и без этого не позовут, но
            //     ставим явно: список условий в DefaultEncounterModel может поменяться с патчем;
            //   Aggressiveness = 0 — лагерь сам ни на кого не бросается (AiEngagePartyBehavior
            //     берёт только отряды с задиристостью выше 0.1);
            //   IgnoreByOtherPartiesTill (выше) — чужой ИИ не выбирает его целью вовсе.
            // Плюс avoidHostileActions при создании: с ним встреча с лагерем вообще освобождена
            // от враждебных действий (DefaultEncounterModel.IsEncounterExemptFromHostileActions).
            party.ShouldJoinPlayerBattles = false;
            party.Aggressiveness = 0f;
        }

        // ---- день в лагере

        // Сперва кто-то уходит, потом приходят новые — и так в каждом лагере отдельно. Прилавок
        // от этого держится пёстрым и по большей части недорогим, а выкупленные дешёвые быстро
        // замещаются такими же.
        private void OnDailyTick()
        {
            EquestriaCrashLog.Try("лагеря наёмников: день", () =>
            {
                var kinds = Kinds();
                if (kinds.Count == 0)
                {
                    return;
                }
                for (int at = 0; at < Count; at++)
                {
                    if (_parties[at] != null)
                    {
                        Keeper(_parties[at]);   // хозяин лагеря всегда один и здоровый
                    }
                    var stock = _stocks[at];
                    if (stock == null)
                    {
                        stock = _stocks[at] = TroopRoster.CreateDummyTroopRoster();
                    }
                    int left = 0;
                    int leaving = LeavingToday(stock.TotalManCount);
                    for (int i = 0; i < leaving; i++)
                    {
                        // Уходит просто кто попало, без оглядки на ступень. Так и надо: при равном
                        // уходе и приходе по долям ComeShare состав лагеря сам сходится ровно к этим
                        // долям. Если бы уходили охотнее дорогие, младшая ступень копилась бы сверх
                        // своей доли (вышло бы примерно 76/19/5 вместо 60/30/10).
                        var who = PickWeighted(stock.GetTroopRoster()
                            .Select(e => new KeyValuePair<CharacterObject, float>(e.Character, e.Number)));
                        if (who == null)
                        {
                            break;
                        }
                        stock.AddToCounts(who, -1);
                        left++;
                    }

                    int room = StockLimitFor(at) - stock.TotalManCount;
                    int came = Math.Max(0, Math.Min(room, ComeADayFor(at)));
                    for (int i = 0; i < came; i++)
                    {
                        // Доли по ступеням: новобранцев большинство, ветеранов единицы (ComeShare).
                        var who = PickWeighted(kinds.Select(troop => new KeyValuePair<CharacterObject, float>(
                            troop, ComeShare[Math.Min(ComeShare.Length, TierOf(troop)) - 1])));
                        stock.AddToCounts(who ?? kinds[0], 1);
                    }
                    if (came > 0 || left > 0)
                    {
                        EquestriaCrashLog.Log($"лагерь у {TownName(at)}: ушло {left}, пришло {came},"
                            + $" всего {stock.TotalManCount} из {StockLimitFor(at)}");
                    }
                }
            });
        }

        // Прилавок из старого сохранения мог набраться до того, как список рот стал строгим:
        // выметаем всех, кого там быть не должно (см. MercClans).
        private void DropStrangers()
        {
            EquestriaCrashLog.Try("лагеря наёмников: чистка прилавка", () =>
            {
                var ours = new HashSet<CharacterObject>(Kinds());
                if (ours.Count == 0)
                {
                    return;
                }
                for (int at = 0; at < Count; at++)
                {
                    var stock = _stocks[at];
                    if (stock == null)
                    {
                        continue;
                    }
                    foreach (var element in stock.GetTroopRoster().ToList())
                    {
                        if (!ours.Contains(element.Character))
                        {
                            stock.AddToCounts(element.Character, -element.Number);
                            EquestriaCrashLog.Log($"лагерь у {TownName(at)}: убран с прилавка "
                                + element.Character.StringId);
                        }
                    }
                }
            });
        }

        private string TownName(int at)
        {
            var town = at >= 0 && at < Count ? Settlement.Find(_townIds[at]) : null;
            return town == null ? (at >= 0 && at < Count ? _townIds[at] : "?") : town.Name.ToString();
        }

        /// <summary>Ступень роты по ванильному id (jawwal_tier_2 -> 2); не разобрали — считаем первой.</summary>
        private static int TierOf(CharacterObject troop)
        {
            var id = troop?.StringId;
            int at = id == null ? -1 : id.LastIndexOf("_tier_", StringComparison.Ordinal);
            if (at >= 0 && int.TryParse(id.Substring(at + "_tier_".Length), out int tier) && tier > 0)
            {
                return tier;
            }
            return 1;
        }

        /// <summary>Случайный боец из пар «боец: вес»; чем больше вес, тем чаще выпадает.</summary>
        private static CharacterObject PickWeighted(IEnumerable<KeyValuePair<CharacterObject, float>> rows)
        {
            var list = rows.Where(p => p.Key != null && p.Value > 0f).ToList();
            float total = list.Sum(p => p.Value);
            if (total <= 0f)
            {
                return null;
            }
            float point = MBRandom.RandomFloat * total;
            foreach (var row in list)
            {
                point -= row.Value;
                if (point <= 0f)
                {
                    return row.Key;
                }
            }
            return list[list.Count - 1].Key;
        }

        // ---- меню и разговор

        private void OnSessionLaunched(CampaignGameStarter starter)
        {
            // Своего меню не заводим: лагерь — обычный отряд, и игрок приходит в ванильное меню
            // встречи. Строку найма добавляем туда же, показывая её только у наших лагерей.
            starter.AddGameMenuOption("encounter", "eq_hire_mercenaries",
                "{=eq_merc_camp_hire_option}Hire mercenaries",
                HireCondition, HireConsequence, false, 1);

            // Разговор при встрече. Движок всегда заводит его с «вожаком» встреченного отряда, а у
            // лагеря вожака-героя нет, и старший боец отвечал ванильной заглушкой «Мне запрещено
            // разговаривать с вами» (видно в игре 25.09.2026). Перебиваем её своей веткой: она
            // старше по приоритету, поэтому выбирается первой.
            starter.AddDialogLine("eq_merc_camp_empty", "start", "close_window",
                "{=eq_merc_camp_line_empty}Nothing here. Every blade's been taken — come back in a day or two.",
                () => TalkIndex() >= 0 && StockCount(TalkIndex()) == 0, LeaveAfterTalk, 201);
            starter.AddDialogLine("eq_merc_camp_greet", "start", "eq_merc_camp_talk",
                "{=eq_merc_camp_line_greet}Camp of the free companies. We sell blades one at a time"
                + " - if you've got the coin.",
                () => TalkIndex() >= 0, null, 200);
            starter.AddPlayerLine("eq_merc_camp_show", "eq_merc_camp_talk", "close_window",
                "{=eq_merc_camp_line_show}Show me who you've got.", null, ShowStockAfterTalk);
            starter.AddPlayerLine("eq_merc_camp_ask_discount", "eq_merc_camp_talk",
                "eq_merc_camp_discount", "{=eq_merc_camp_line_ask_discount}Any chance of a discount?",
                null, null);
            starter.AddDialogLine("eq_merc_camp_discount_answer", "eq_merc_camp_discount",
                "eq_merc_camp_talk",
                "{=eq_merc_camp_line_discount}Depends who's asking. Every three points of trust is"
                + " one percent off the hiring price. Your trust here is {EQ_MERC_RELATION} of"
                + " {EQ_MERC_RELATION_MAX} - that's {EQ_MERC_DISCOUNT}% off. It grows with coin:"
                + " one point for every four hundred spent here. And we only count our own"
                + " - other camps keep their own trust.",
                DiscountAnswer, null);
            starter.AddPlayerLine("eq_merc_camp_ask_stock", "eq_merc_camp_talk",
                "eq_merc_camp_stock", "{=eq_merc_camp_line_ask_stock}When will more mercenaries show up?",
                null, null);
            starter.AddDialogLine("eq_merc_camp_stock_answer", "eq_merc_camp_stock",
                "eq_merc_camp_talk",
                "{=eq_merc_camp_line_stock}About {EQ_MERC_COME} show up each day, and those who wait"
                + " too long go looking for work elsewhere. We can't fit more than {EQ_MERC_LIMIT};"
                + " right now we've got {EQ_MERC_STOCK}. The more trust, the more room and the more"
                + " who come - one extra spot per point of trust, one more recruit for every ten.",
                StockAnswer, null);
            starter.AddPlayerLine("eq_merc_camp_leave", "eq_merc_camp_talk", "close_window",
                "{=eq_merc_camp_line_leave}Some other time.", null, LeaveAfterTalk);
            EquestriaCrashLog.Log($"лагеря наёмников: точек на карте {CampSpots.Count},"
                + " строка найма и разговор добавлены");
        }

        private bool HireCondition(MenuCallbackArgs args)
        {
            args.optionLeaveType = GameMenuOption.LeaveType.Recruit;
            int at = IndexOfParty(PlayerEncounter.EncounteredMobileParty);
            if (at < 0)
            {
                return false;
            }
            // Пустой лагерь строку показывает, но серой: иначе игрок не понимает, почему выбора нет.
            if (StockCount(at) == 0)
            {
                args.IsEnabled = false;
                args.Tooltip = new TextObject("{=eq_merc_camp_empty_tooltip}Nobody's here right now"
                    + " - come back in a day or two.");
            }
            return true;
        }

        private void HireConsequence(MenuCallbackArgs args)
        {
            OpenHireScreen(IndexOfParty(PlayerEncounter.EncounteredMobileParty));
        }

        private int StockCount(int at)
        {
            return at < 0 || at >= Count || _stocks[at] == null ? 0 : _stocks[at].TotalManCount;
        }

        private int TalkIndex()
        {
            return IndexOfParty(MobileParty.ConversationParty);
        }

        // Числа в ответ подставляем переменными: в самой строке они записаны как {EQ_MERC_...}.
        private bool DiscountAnswer()
        {
            int at = TalkIndex();
            MBTextManager.SetTextVariable("EQ_MERC_RELATION", at < 0 ? 0 : _relations[at]);
            MBTextManager.SetTextVariable("EQ_MERC_RELATION_MAX", RelationMax);
            MBTextManager.SetTextVariable("EQ_MERC_DISCOUNT", DiscountPercent(at));
            return true;
        }

        private bool StockAnswer()
        {
            int at = TalkIndex();
            MBTextManager.SetTextVariable("EQ_MERC_COME", ComeADayFor(at));
            MBTextManager.SetTextVariable("EQ_MERC_LIMIT", StockLimitFor(at));
            MBTextManager.SetTextVariable("EQ_MERC_STOCK", StockCount(at));
            return true;
        }

        // Окно открываем не из самого разговора, а сразу после него: пока идёт беседа, поверх неё
        // экран отряда не встаёт.
        private void ShowStockAfterTalk()
        {
            var talk = Campaign.Current?.ConversationManager;
            if (talk == null)
            {
                return;
            }
            int at = TalkIndex();
            talk.ConversationEndOneShot += () => OpenHireScreen(at);
        }

        // Разговор кончился, торга не вышло — из встречи тоже уходим, иначе игрок остаётся в меню
        // боя с лагерем (замечено в игре 25.09.2026).
        private void LeaveAfterTalk()
        {
            var talk = Campaign.Current?.ConversationManager;
            if (talk == null)
            {
                return;
            }
            talk.ConversationEndOneShot += LeaveEncounter;
        }

        // ---- товар

        // Наёмные роты, чьи войска продаются. Список тот же, что MERC_NAMES в tools/make_troops.py:
        // там им даны лорные имена, здесь — прилавок. Перечисляем поимённо, потому что вида
        // «клан_tier_N» в игре не только они: в SandBoxCore/obsolete_characters.xml лежат войска
        // вырезанных рот (guardians_tier_*, galloglass_tier_*). Клана у них нет, дерева улучшений
        // тоже, и имена остались английскими — «Guardian Recruit», «Skene», «Kern» (замечено на
        // прилавке 25.09.2026).
        private static readonly HashSet<string> MercClans = new HashSet<string>
        {
            "jawwal", "eleftheroi", "hidden_hand", "lakepike", "legion_of_the_betrayed", "ghilman",
            "skolderbrotva", "beni_zilal", "embers_of_flame", "karakhuzaits", "company_of_the_boar",
            "wolfskins", "brotherhood_of_woods", "forest_people",
        };

        /// <summary>Войска наёмных рот по порядку: рота за ротой, внутри роты по ступеням.</summary>
        private static List<CharacterObject> Kinds()
        {
            var result = new List<CharacterObject>();
            var all = MBObjectManager.Instance?.GetObjectTypeList<CharacterObject>();
            if (all == null)
            {
                return result;
            }
            foreach (var troop in all)
            {
                if (troop == null || troop.IsHero || troop.StringId == null)
                {
                    continue;
                }
                int at = troop.StringId.IndexOf("_tier_", StringComparison.Ordinal);
                if (at < 0 || !MercClans.Contains(troop.StringId.Substring(0, at)))
                {
                    continue;
                }
                result.Add(troop);
            }
            result.Sort((a, b) => string.CompareOrdinal(a.StringId, b.StringId));
            return result;
        }

        // Цена со скидкой за доверие ЭТОГО лагеря: где чаще тратишь, там и дешевле.
        private int Price(CharacterObject troop, int at)
        {
            var model = Campaign.Current?.Models?.PartyWageModel;
            int basic = model == null ? troop.TroopWage * 20
                : model.GetTroopRecruitmentCost(troop, Hero.MainHero).RoundedResultNumber;
            return Math.Max(1, (int)(basic * PriceFactor * (1f - DiscountPercent(at) / 100f)));
        }

        /// <summary>Сколько бойцов помещается в лагере: 30 плюс единица за каждую единицу доверия.</summary>
        private int StockLimitFor(int at)
        {
            return StockLimitBase + (at < 0 || at >= Count ? 0 : Math.Max(0, _relations[at]));
        }

        /// <summary>Сколько приходит за день: четверо плюс один за каждые десять единиц доверия.</summary>
        private int ComeADayFor(int at)
        {
            return ComeADayBase + (at < 0 || at >= Count ? 0 : Math.Max(0, _relations[at]) / RelationPerCome);
        }

        /// <summary>Сколько уходит за день: десятая часть прилавка, но хотя бы один.</summary>
        private static int LeavingToday(int stock)
        {
            return stock <= 0 ? 0 : Math.Max(1, (int)Math.Round(stock * LeaveShare));
        }

        /// <summary>Скидка в процентах: по одному за каждые три единицы доверия (33% при сотне).</summary>
        private int DiscountPercent(int at)
        {
            if (at < 0 || at >= Count)
            {
                return 0;
            }
            return Math.Min(RelationMax, Math.Max(0, _relations[at])) / RelationPerPercent;
        }

        // Доверие за покупку: единица за каждые CoinsPerPoint монет, остаток копится дальше.
        private void PayRelation(int at, int coins)
        {
            if (coins <= 0 || at < 0 || at >= Count)
            {
                return;
            }
            _spents[at] += coins;
            int grew = 0;
            while (_spents[at] >= CoinsPerPoint && _relations[at] < RelationMax)
            {
                _spents[at] -= CoinsPerPoint;
                _relations[at]++;
                grew++;
            }
            if (_relations[at] >= RelationMax)
            {
                _spents[at] = 0;        // дальше копить нечего, предел доверия взят
            }
            EquestriaCrashLog.Log($"лагерь у {TownName(at)}: потрачено {coins}, доверие {_relations[at]}"
                + (grew > 0 ? $" (+{grew})" : "") + $", до следующей единицы {CoinsPerPoint - _spents[at]}");
        }

        // ---- проверка без похода к лагерю

        // equestria.merc_camp              — открыть окно найма ближайшего лагеря
        // equestria.merc_camp list         — показать все лагеря: товар, доверие, скидка
        // equestria.merc_camp day [N]      — прогнать N дней во всех лагерях
        // equestria.merc_camp relation [N] — выставить доверие ближайшему лагерю
        // equestria.merc_camp goto [N]     — перенести отряд игрока к лагерю (без числа — к первому)
        [CommandLineFunctionality.CommandLineArgumentFunction("merc_camp", "equestria")]
        public static string Console(List<string> args)
        {
            var behaviour = Campaign.Current?.GetCampaignBehavior<EquestriaMercCampBehavior>();
            if (behaviour == null)
            {
                return "лагерь наёмников: поведение не подключено";
            }
            if (args.Count > 0 && args[0] == "list")
            {
                var rows = new List<string>();
                for (int at = 0; at < behaviour.Count; at++)
                {
                    rows.Add($"{behaviour.TownName(at)}: бойцов {behaviour.StockCount(at)}"
                        + $" из {behaviour.StockLimitFor(at)}, приход {behaviour.ComeADayFor(at)}/день,"
                        + $" доверие {behaviour._relations[at]}, скидка {behaviour.DiscountPercent(at)}%");
                }
                return rows.Count == 0 ? "лагерей нет" : string.Join("\n", rows);
            }
            if (args.Count > 0 && args[0] == "day")
            {
                int days = args.Count > 1 && int.TryParse(args[1], out int n) ? Math.Max(1, n) : 1;
                for (int i = 0; i < days; i++)
                {
                    behaviour.OnDailyTick();
                }
                return $"прошло дней: {days}, лагерей: {behaviour.Count}";
            }
            int near = behaviour.Nearest();
            if (near < 0)
            {
                return "лагерей на карте нет";
            }
            if (args.Count > 0 && args[0] == "relation")
            {
                if (args.Count > 1 && int.TryParse(args[1], out int set))
                {
                    behaviour._relations[near] = Math.Max(0, Math.Min(RelationMax, set));
                    behaviour._spents[near] = 0;
                }
                return $"лагерь у {behaviour.TownName(near)}: доверие {behaviour._relations[near]}"
                    + $" из {RelationMax}, скидка {behaviour.DiscountPercent(near)}%,"
                    + $" до следующей единицы {CoinsPerPoint - behaviour._spents[near]} монет";
            }
            if (args.Count > 0 && args[0] == "goto")
            {
                int at = args.Count > 1 && int.TryParse(args[1], out int n)
                    ? Math.Max(0, Math.Min(behaviour.Count - 1, n)) : 0;
                if (behaviour._parties[at] == null)
                {
                    return "лагерь наёмников: отряда нет на карте";
                }
                MobileParty.MainParty.Position = behaviour._parties[at].Position;
                return $"отряд перенесён к лагерю у {behaviour.TownName(at)}";
            }
            behaviour.OpenHireScreen(near);
            return $"окно найма открыто: лагерь у {behaviour.TownName(near)}";
        }

        /// <summary>Ближайший к игроку лагерь; -1, если их нет вовсе.</summary>
        private int Nearest()
        {
            int best = -1;
            float bestDistance = float.MaxValue;
            var me = MobileParty.MainParty?.Position.ToVec2() ?? Vec2.Zero;
            for (int at = 0; at < Count; at++)
            {
                if (_parties[at] == null)
                {
                    continue;
                }
                float distance = me.Distance(_parties[at].Position.ToVec2());
                if (distance < bestDistance)
                {
                    bestDistance = distance;
                    best = at;
                }
            }
            return best;
        }

        // ---- окно найма

        private void OpenHireScreen(int at)
        {
            EquestriaCrashLog.Try("окно найма", () =>
            {
                if (at < 0 || at >= Count)
                {
                    return;
                }
                if (_stocks[at] == null)
                {
                    _stocks[at] = TroopRoster.CreateDummyTroopRoster();
                }
                _open = at;
                // Что и сколько лежало на прилавке к моменту открытия: по разнице с этим считается
                // цена, а при отмене окна движок сам вернёт роспись обратно.
                _onOpen = new Dictionary<CharacterObject, int>();
                foreach (var element in _stocks[at].GetTroopRoster())
                {
                    _onOpen[element.Character] = element.Number;
                }
                EquestriaCrashLog.Log($"окно найма: лагерь у {TownName(at)}, бойцов"
                    + $" {_stocks[at].TotalManCount}, видов {_onOpen.Count},"
                    + $" скидка {DiscountPercent(at)}%");
                var title = new TextObject("{=eq_merc_camp_title}Mercenary camp near {TOWN}");
                title.SetTextVariable("TOWN", TownName(at));
                PartyScreenHelper.OpenScreenWithDummyRosterWithMainParty(
                    _stocks[at], TroopRoster.CreateDummyTroopRoster(),
                    title, StockLimitFor(at),
                    null, OnScreenClosed, IsTransferable, null);
                HookGold();
            });
        }

        private bool IsTransferable(CharacterObject character, PartyScreenLogic.TroopType type,
            PartyScreenLogic.PartyRosterSide side, PartyBase leftOwnerParty)
        {
            // Своих войск в лагерь не отдаём: продавать некому. Обратно вернуть купленное можно —
            // это те же наёмники, и в лагере они снова оказываются на продаже.
            return side == PartyScreenLogic.PartyRosterSide.Left
                || (_onOpen != null && _onOpen.ContainsKey(character));
        }

        // Счётчик денег: на каждую передачу пересчитываем, сколько стоит всё унесённое.
        private void HookGold()
        {
            var logic = (Game.Current?.GameStateManager?.ActiveState as PartyState)?.PartyScreenLogic;
            if (logic == null)
            {
                EquestriaCrashLog.Warn("окно найма: не нашёл логику окна, цена считаться не будет");
                return;
            }
            logic.Update += command => UpdateGold(logic);
            UpdateGold(logic);
        }

        private void UpdateGold(PartyScreenLogic logic)
        {
            EquestriaCrashLog.Try("цена найма", () =>
            {
                int total = 0;
                var left = logic.MemberRosters[(int)PartyScreenLogic.PartyRosterSide.Left];
                var kinds = new HashSet<CharacterObject>(_onOpen.Keys);
                foreach (var element in left.GetTroopRoster())
                {
                    kinds.Add(element.Character);
                }
                foreach (var troop in kinds)
                {
                    _onOpen.TryGetValue(troop, out int was);
                    int taken = was - left.GetTroopCount(troop);
                    // Унёс — платит полную цену; привёл своих — получает половину (см. SellBackFactor).
                    total += taken >= 0 ? taken * Price(troop, _open)
                        : (int)(taken * Price(troop, _open) * SellBackFactor);
                }
                logic.CurrentData.PartyGoldChangeAmount = -total;
                RaiseGoldChanged(logic);
            });
        }

        // Событие PartyGoldChange открыто только на подписку, поэтому дёргаем его через поле:
        // у события-поля в C# оно называется так же. Без этого надпись внизу окна не обновляется.
        private static void RaiseGoldChanged(PartyScreenLogic logic)
        {
            var field = typeof(PartyScreenLogic).GetField("PartyGoldChange",
                System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic
                | System.Reflection.BindingFlags.Public);
            (field?.GetValue(logic) as Delegate)?.DynamicInvoke();
        }

        // После торга игроку нечего делать в меню встречи: там осталась бы «Атака!» по лагерю,
        // у которого он только что купил бойцов. Закрываем встречу и возвращаем на карту.
        private static void LeaveEncounter()
        {
            EquestriaCrashLog.Try("лагерь наёмников: выход из встречи", () =>
            {
                if (PlayerEncounter.Current == null)
                {
                    return;             // окно открывали командой из консоли, встречи нет
                }
                PlayerEncounter.LeaveEncounter = true;
                PlayerEncounter.Finish(true);
            });
        }

        /// <summary>Цена бойца для строки окна; 0 — торг сейчас не идёт или боец не наш.</summary>
        internal static int PriceInList(CharacterObject troop)
        {
            var behaviour = Campaign.Current?.GetCampaignBehavior<EquestriaMercCampBehavior>();
            if (behaviour?._onOpen == null || troop == null || troop.IsHero)
            {
                return 0;
            }
            return behaviour._onOpen.ContainsKey(troop) ? behaviour.Price(troop, behaviour._open) : 0;
        }

        private void OnScreenClosed(PartyBase leftOwnerParty, TroopRoster leftMemberRoster,
            TroopRoster leftPrisonRoster, PartyBase rightOwnerParty, TroopRoster rightMemberRoster,
            TroopRoster rightPrisonRoster, bool fromCancel)
        {
            // Сам прилавок не трогаем: окно работало прямо с ним, и то, что игрок унёс, из него уже
            // вычтено (а при отмене возвращено движком).
            int at = _open;
            int hired = 0;
            int paid = 0;
            if (_onOpen != null && at >= 0 && at < Count)
            {
                foreach (var pair in _onOpen)
                {
                    int taken = Math.Max(0, pair.Value - _stocks[at].GetTroopCount(pair.Key));
                    hired += taken;
                    paid += taken * Price(pair.Key, at);
                }
            }
            EquestriaCrashLog.Log($"окно найма: закрыто, нанято {hired} за {paid}, осталось в лагере"
                + $" {StockCount(at)}" + (fromCancel ? " (отменено)" : ""));
            _onOpen = null;
            _open = -1;
            // Доверие растёт только за покупки: проданные лагерю бойцы его не прибавляют.
            PayRelation(at, paid);
            LeaveEncounter();
        }
    }

    // Лагеря не едят: возить им припасы некому, а голодный отряд игра каждый день ранит и в конце
    // концов распускает. Перекрываем только один ответ модели, остальное считает ванильная.
    public class EquestriaCampFoodModel : DefaultMobilePartyFoodConsumptionModel
    {
        public override bool DoesPartyConsumeFood(MobileParty mobileParty)
        {
            return !EquestriaMercCampBehavior.IsCampParty(mobileParty)
                && base.DoesPartyConsumeFood(mobileParty);
        }
    }

    // Цена рядом с числом бойцов. Своей колонки у окна отряда нет, поэтому дописываем цену в ту
    // же строку, где стоит количество: «5 · 450». Пишем только в левом списке и только когда идёт
    // торг с лагерем — в обычном окне отряда строка остаётся ванильной.
    [HarmonyPatch(typeof(PartyCharacterVM), "get_TroopNum")]
    public static class EquestriaMercPriceTag
    {
        private static void Postfix(PartyCharacterVM __instance, ref string __result)
        {
            if (__instance.Side != PartyScreenLogic.PartyRosterSide.Left)
            {
                return;
            }
            int price = EquestriaMercCampBehavior.PriceInList(__instance.Character);
            if (price > 0)
            {
                __result = __result + " · " + price;
            }
        }
    }

    // Объявление для системы сохранений: List<TroopRoster> (запасы лагерей наёмников) в 1.4.8 не
    // объявлен ни движком, ни песочницей. Движок сам находит наследников SaveableTypeDefiner во всех
    // загруженных сборках. Базовый номер — свой, далёкий от ванильных (у тех 10 000…~400 000).
    public class EquestriaMercCampTypeDefiner : SaveableTypeDefiner
    {
        public EquestriaMercCampTypeDefiner() : base(4_217_000)
        {
        }

        protected override void DefineContainerDefinitions()
        {
            ConstructContainerDefinition(typeof(List<TroopRoster>));
        }
    }
}
