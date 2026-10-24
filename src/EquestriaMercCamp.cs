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
    // Mercenary camps by the realms' capitals: a place where you can buy troops of mercenary companies.
    //
    // In vanilla, companies are hired only as a whole and only as a mercenary clan of a realm, and their troops
    // (jawwal_tier_1 and the other 42 entries, renamed in our mod, see MERC_NAMES in
    // tools/make_troops.py) are not available to the player at all. Here they are sold one by one.
    //
    // How it works:
    //   1. at the gates of every capital stands a camp party (CustomPartyComponent); it does not move and
    //      does not fight anyone; the tents next to it are placed by tools/map_props.py at the same points (CampSpots);
    //   2. on meeting it, the menu gets the line "Hire mercenaries", and the conversation gets
    //      its own answers instead of the vanilla stub;
    //   3. that line opens the regular troop transfer window: goods on the left, the player's party on the right,
    //      and the "You will pay" counter at the bottom.
    //
    // The camps are independent: each has its own stall and its own trust in the player, and thus its own discount.
    //
    // About money. The engine counts gold by itself only in two cases: ransoming prisoners and quest
    // wages (PartyScreenLogic, branches TransferableWithTrade and QuestTroopManage). The quest one
    // counts the other way round, a debt for those who were LEFT, so we keep the price ourselves: on every
    // transfer we recompute the cost of what was taken and put it into CurrentData.PartyGoldChangeAmount,
    // and raise the PartyGoldChange event via reflection (it is not exposed). After that the engine
    // itself shows the sum at the bottom of the window, does not let you take more troops than you have money for, and on the
    // "Done" button deducts the gold.
    public class EquestriaMercCampBehavior : CampaignBehaviorBase
    {
        // Where the camps are: realm capital -> a point by its gates. The spots were picked by gate_pos from
        // equestria_settlements.xml: on land and no closer than seven metres to any settlement.
        private static readonly Dictionary<string, Vec2> CampSpots = new Dictionary<string, Vec2>
        {
            { "town_empire_0", new Vec2(543.5f, 502.5f) },    // Canterlot, Solar Equestria
            { "town_empire_7", new Vec2(426.8f, 448.0f) },    // Las Pegasus, Lunar Equestria
            { "town_empire_14", new Vec2(533.7f, 454.1f) },   // Ponyville, Realm of Friendship
            { "town_empire_20", new Vec2(666.5f, 642.7f) },   // Crystal City, Crystal Empire
            { "town_vlandia_0", new Vec2(986.8f, 812.9f) },   // Griffonstone, Griffonia
            { "town_battania_0", new Vec2(182.7f, 564.5f) },  // Mount Aris, Hippogriffia
            { "town_nord_0", new Vec2(101.9f, 648.2f) },      // Deer Grove, Deerland
            { "town_sturgia_0", new Vec2(721.1f, 297.6f) },   // Lair of the Dragon Lord, Dragon Lands
            { "town_khuzait_0", new Vec2(555.7f, 772.2f) },   // Yaktown, Yak Lands
            { "town_aserai_0", new Vec2(285.3f, 800.8f) },    // Vesalipolis, Changeling Hives
        };

        // The camp party itself holds a single keeper: he is visible on the map and does not look like
        // an army in the list of battle sides. The goods are not in the party at all: they are a separate stall (see _stocks).
        private const int GuardCount = 1;
        private const float PriceFactor = 0.75f;    // a mercenary is cheaper than a militiaman of the same tier
        // The goods accumulate by themselves: at the start of the game the camp is empty, free fighters come every day, but
        // no more than the limit stay in the camp. Both the limit and the inflow grow with trust: where
        // the player is known, people are more willing to come and hire on.
        //   limit   = 30 + trust            (130 at full trust)
        //   inflow  = 4 + trust / 10        (14 a day at full)
        private const int StockLimitBase = 30;
        private const int ComeADayBase = 4;
        private const int RelationPerCome = 10;
        // And they leave: without this, the camp once filled up to the top with those nobody takes (expensive
        // third tiers), no room was left for new fighters, and the stall froze forever.
        // A share of the stall leaves, not just a couple of fighters: with a constant number, the outflow would equal
        // the inflow and the camp would hover around zero, while with a share it fills up to the limit and
        // refreshes there (at 10% a day, roughly a third of the roster per week).
        private const float LeaveShare = 0.1f;
        // Which ones arrive: 60% the company's junior tier, 30% middle, 10% senior. The tier is taken from
        // the vanilla troop id (clan_tier_N), which also determines the price.
        private static readonly float[] ComeShare = { 60f, 30f, 10f };
        // For your own fighters brought to the camp you get half the hiring price. Paying the full price is not possible:
        // a first-tier mercenary grows to the third, and the difference would make a money mill.
        // But cancelling your own purchase within this visit is possible without losses: it is just a rollback.
        private const float SellBackFactor = 0.5f;
        // The camp's trust in the player: 0 at the start of the game, 100 is the limit. Every three points give a percent
        // of discount, i.e. at full trust hiring is 33% cheaper. It grows from money spent: one point
        // per every four hundred coins, the remainder is not lost and accumulates towards the next. Each camp has
        // its own trust: where you buy, there you are valued.
        private const int RelationMax = 100;
        private const int RelationPerPercent = 3;
        private const int CoinsPerPoint = 400;

        // The camps are stored in the save as several lists, not as one list of our own objects:
        // an own class would have to be declared to the engine separately (SaveableTypeDefiner), while lists
        // and dictionaries of ready-made types it handles itself. The order is shared across all lists.
        // BUT not all: List<TroopRoster> is unknown to engine 1.4.8; saving failed with "Cannot
        // create save" (Cant find definition for List`1[TroopRoster], found 10.10.2026).
        // Declared below, in EquestriaMercCampTypeDefiner.
        private List<string> _townIds = new List<string>();
        private List<MobileParty> _parties = new List<MobileParty>();
        private List<TroopRoster> _stocks = new List<TroopRoster>();
        private List<int> _relations = new List<int>();
        private List<int> _spents = new List<int>();

        // Old fields of the single camp: kept for saves made before the other nine
        // appeared. On load their contents move into the lists (see Migrate).
        private MobileParty _camp;
        private TroopRoster _stock;
        private int _relation;
        private int _spent;

        private int _open = -1;                             // which camp the bargaining is with right now
        private Dictionary<CharacterObject, int> _onOpen;   // how many of what there was when the window was opened

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
            // A single camp from old saves
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

        // ---- camps on the map

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
                        _parties[at] = party;       // the party got lost (old save), place it again
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

        // A save from the times of the only camp near Canterlot: we move the party, the stall and
        // the trust into the lists, so that the player loses neither the purchases nor the earned discount.
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

        /// <summary>Is this one of our camps? Needed by the starvation model (see EquestriaCampFoodModel).</summary>
        internal static bool IsCampParty(MobileParty party)
        {
            var behaviour = Campaign.Current?.GetCampaignBehavior<EquestriaMercCampBehavior>();
            return behaviour != null && behaviour.IndexOfParty(party) >= 0;
        }

        // The camp keeper: exactly one and always healthy. Left unattended, the party starved (nobody
        // brings it food) and by morning all twelve "keepers" lay wounded; seen on the map 25.09.2026.
        // Food is disabled by EquestriaCampFoodModel, and the wounded are healed here: the same trick as the game's,
        // replace the roster with a healthy one.
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

        // The camp goes nowhere and chases no one: without this a party with regular AI goes
        // "home" to the capital and disappears from view.
        private static void Park(MobileParty party, Vec2 spot)
        {
            Keeper(party);
            party.Position = new CampaignVec2(spot, isOnLand: true);
            party.Ai.SetDoNotMakeNewDecisions(true);
            party.SetMoveModeHold();
            party.IgnoreByOtherPartiesTill(CampaignTime.Never);
            party.SetPartyUsedByQuest(true);      // so that lord parties do not consider it prey
            // The camp fights for no one. Three separate protections, because the game has three different ways
            // to get dragged into someone else's battle:
            //   ShouldJoinPlayerBattles: the game uses it to gather neighbours into the PLAYER's battle. Our party
            //     is not a lord's, not a bandit's and not a patrol, so it would not be called even without this, but
            //     we set it explicitly: the condition list in DefaultEncounterModel may change with a patch;
            //   Aggressiveness = 0: the camp does not attack anyone by itself (AiEngagePartyBehavior
            //     takes only parties with aggressiveness above 0.1);
            //   IgnoreByOtherPartiesTill (above): other AI does not pick it as a target at all.
            // Plus avoidHostileActions at creation: with it, an encounter with the camp is fully exempt
            // from hostile actions (DefaultEncounterModel.IsEncounterExemptFromHostileActions).
            party.ShouldJoinPlayerBattles = false;
            party.Aggressiveness = 0f;
        }

        // ---- a day in the camp

        // First someone leaves, then new ones arrive, and so in every camp separately. This keeps the stall
        // varied and mostly inexpensive, and the cheap ones that were bought out are quickly
        // replaced by similar ones.
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
                        Keeper(_parties[at]);   // the camp keeper is always one and healthy
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
                        // Just anyone leaves, regardless of tier. That is how it should be: with equal
                        // outflow and inflow by the ComeShare shares, the camp roster converges exactly to these
                        // shares by itself. If the expensive ones left more readily, the junior tier would pile up beyond
                        // its share (it would come out roughly 76/19/5 instead of 60/30/10).
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
                        // Shares by tier: recruits are the majority, veterans are few (ComeShare).
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

        // A stall from an old save could have filled up before the company list became strict:
        // we sweep out everyone who must not be there (see MercClans).
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

        /// <summary>Company tier from the vanilla id (jawwal_tier_2 -> 2); if not parsed, it counts as the first.</summary>
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

        /// <summary>A random fighter from "fighter: weight" pairs; the bigger the weight, the more often it comes up.</summary>
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

        // ---- menu and conversation

        private void OnSessionLaunched(CampaignGameStarter starter)
        {
            // We do not create our own menu: the camp is a regular party, and the player comes into the vanilla
            // encounter menu. The hiring line is added there, shown only at our camps.
            starter.AddGameMenuOption("encounter", "eq_hire_mercenaries",
                "{=eq_merc_camp_hire_option}Hire mercenaries",
                HireCondition, HireConsequence, false, 1);

            // The conversation on encounter. The engine always starts it with the "leader" of the encountered party, but
            // the camp has no hero leader, and the senior fighter answered with the vanilla stub "I am forbidden
            // to talk to you" (seen in game 25.09.2026). We override it with our own branch: it
            // has higher priority, so it is chosen first.
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
            // An empty camp shows the line, but greyed out: otherwise the player does not understand why there is no choice.
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

        // Numbers are substituted into the answer as variables: in the string itself they are written as {EQ_MERC_...}.
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

        // The window is opened not from the conversation itself but right after it: while the conversation is going on,
        // the party screen does not come up on top of it.
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

        // The conversation is over and no deal came out: we leave the encounter too, otherwise the player stays in the
        // battle menu with the camp (noticed in game 25.09.2026).
        private void LeaveAfterTalk()
        {
            var talk = Campaign.Current?.ConversationManager;
            if (talk == null)
            {
                return;
            }
            talk.ConversationEndOneShot += LeaveEncounter;
        }

        // ---- goods

        // Mercenary companies whose troops are sold. The list is the same as MERC_NAMES in tools/make_troops.py:
        // there they are given lore names, here they are the stall. We list them by name, because there are others
        // of the "clan_tier_N" form in the game: SandBoxCore/obsolete_characters.xml holds troops of
        // cut companies (guardians_tier_*, galloglass_tier_*). They have no clan, no upgrade tree
        // either, and the names stayed English: "Guardian Recruit", "Skene", "Kern" (noticed on the
        // stall 25.09.2026).
        private static readonly HashSet<string> MercClans = new HashSet<string>
        {
            "jawwal", "eleftheroi", "hidden_hand", "lakepike", "legion_of_the_betrayed", "ghilman",
            "skolderbrotva", "beni_zilal", "embers_of_flame", "karakhuzaits", "company_of_the_boar",
            "wolfskins", "brotherhood_of_woods", "forest_people",
        };

        /// <summary>Troops of mercenary companies in order: company after company, within a company by tier.</summary>
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

        // The price with the discount for the trust of THIS camp: where you spend more often, it is cheaper.
        private int Price(CharacterObject troop, int at)
        {
            var model = Campaign.Current?.Models?.PartyWageModel;
            int basic = model == null ? troop.TroopWage * 20
                : model.GetTroopRecruitmentCost(troop, Hero.MainHero).RoundedResultNumber;
            return Math.Max(1, (int)(basic * PriceFactor * (1f - DiscountPercent(at) / 100f)));
        }

        /// <summary>How many fighters fit in the camp: 30 plus one for each point of trust.</summary>
        private int StockLimitFor(int at)
        {
            return StockLimitBase + (at < 0 || at >= Count ? 0 : Math.Max(0, _relations[at]));
        }

        /// <summary>How many arrive per day: four plus one for every ten points of trust.</summary>
        private int ComeADayFor(int at)
        {
            return ComeADayBase + (at < 0 || at >= Count ? 0 : Math.Max(0, _relations[at]) / RelationPerCome);
        }

        /// <summary>How many leave per day: a tenth of the stall, but at least one.</summary>
        private static int LeavingToday(int stock)
        {
            return stock <= 0 ? 0 : Math.Max(1, (int)Math.Round(stock * LeaveShare));
        }

        /// <summary>Discount in percent: one per every three points of trust (33% at a hundred).</summary>
        private int DiscountPercent(int at)
        {
            if (at < 0 || at >= Count)
            {
                return 0;
            }
            return Math.Min(RelationMax, Math.Max(0, _relations[at])) / RelationPerPercent;
        }

        // Trust for a purchase: one point per every CoinsPerPoint coins, the remainder accumulates further.
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
                _spents[at] = 0;        // nothing more to accumulate, the trust limit is reached
            }
            EquestriaCrashLog.Log($"лагерь у {TownName(at)}: потрачено {coins}, доверие {_relations[at]}"
                + (grew > 0 ? $" (+{grew})" : "") + $", до следующей единицы {CoinsPerPoint - _spents[at]}");
        }

        // ---- testing without going to the camp

        // equestria.merc_camp              - open the hiring window of the nearest camp
        // equestria.merc_camp list         - show all camps: goods, trust, discount
        // equestria.merc_camp day [N]      - run N days in all camps
        // equestria.merc_camp relation [N] - set the trust of the nearest camp
        // equestria.merc_camp goto [N]     - move the player's party to a camp (without a number, to the first)
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

        /// <summary>The camp nearest to the player; -1 if there are none at all.</summary>
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

        // ---- hiring window

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
                // What and how much was on the stall at the moment of opening: the price is computed by the difference with this,
                // and when the window is cancelled the engine itself returns the roster back.
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
            // We do not take the player's own troops into the camp: there is no one to sell them to. Returning what was bought is possible:
            // these are the same mercenaries, and in the camp they go on sale again.
            return side == PartyScreenLogic.PartyRosterSide.Left
                || (_onOpen != null && _onOpen.ContainsKey(character));
        }

        // Money counter: on every transfer we recompute how much everything taken costs.
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
                    // Took them: pays the full price; brought their own: gets half (see SellBackFactor).
                    total += taken >= 0 ? taken * Price(troop, _open)
                        : (int)(taken * Price(troop, _open) * SellBackFactor);
                }
                logic.CurrentData.PartyGoldChangeAmount = -total;
                RaiseGoldChanged(logic);
            });
        }

        // The PartyGoldChange event is exposed only for subscription, so we raise it via the field:
        // for a field-like event in C# the field has the same name. Without this the label at the bottom of the window does not update.
        private static void RaiseGoldChanged(PartyScreenLogic logic)
        {
            var field = typeof(PartyScreenLogic).GetField("PartyGoldChange",
                System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic
                | System.Reflection.BindingFlags.Public);
            (field?.GetValue(logic) as Delegate)?.DynamicInvoke();
        }

        // After bargaining the player has nothing to do in the encounter menu: "Attack!" would be left there against the camp
        // from which he has just bought fighters. We close the encounter and return to the map.
        private static void LeaveEncounter()
        {
            EquestriaCrashLog.Try("лагерь наёмников: выход из встречи", () =>
            {
                if (PlayerEncounter.Current == null)
                {
                    return;             // the window was opened by a console command, there is no encounter
                }
                PlayerEncounter.LeaveEncounter = true;
                PlayerEncounter.Finish(true);
            });
        }

        /// <summary>Fighter price for the window row; 0 means no bargaining is going on now or the fighter is not ours.</summary>
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
            // The stall itself is not touched: the window worked directly with it, and what the player took has already been
            // subtracted from it (and on cancel returned by the engine).
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
            // Trust grows only from purchases: fighters sold to the camp do not add to it.
            PayRelation(at, paid);
            LeaveEncounter();
        }
    }

    // Camps do not eat: there is no one to bring them supplies, and the game wounds a starving party every day and
    // eventually disbands it. We override only one answer of the model, the rest is computed by the vanilla one.
    public class EquestriaCampFoodModel : DefaultMobilePartyFoodConsumptionModel
    {
        public override bool DoesPartyConsumeFood(MobileParty mobileParty)
        {
            return !EquestriaMercCampBehavior.IsCampParty(mobileParty)
                && base.DoesPartyConsumeFood(mobileParty);
        }
    }

    // The price next to the number of fighters. The party window has no column of its own, so we append the price to the
    // same line where the count is: «5 · 450». We write only in the left list and only while
    // bargaining with a camp is going on; in the regular party window the line stays vanilla.
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

    // Declaration for the save system: List<TroopRoster> (mercenary camp stocks) is declared in 1.4.8
    // neither by the engine nor by the sandbox. The engine itself finds SaveableTypeDefiner subclasses in all
    // loaded assemblies. The base number is our own, far from the vanilla ones (theirs are 10 000…~400 000).
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
