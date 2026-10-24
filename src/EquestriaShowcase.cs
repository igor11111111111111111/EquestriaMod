using System;
using System.Collections.Generic;
using System.Linq;
using Helpers;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.CampaignBehaviors;
using TaleWorlds.CampaignSystem.Conversation;
using TaleWorlds.CampaignSystem.GameState;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Pony armour showcase: put one of five sets on the hero and open the inventory, where the model is visible.
    //
    // For self-checking: launching with the /eqset:N switch (N = 0..4) after a quick start dresses the hero
    // in set N and opens the inventory by itself; all that is left is to take a screenshot. Manually the
    // console command equestria.wear_set N does the same.
    public static class EquestriaShowcase
    {
        private const string ArgPrefix = "/eqset:";

        // Five sets, one item from each slot (order as in tools/make_world.py ARMOR_SETS)
        private static readonly string[] Helmets =
        {
            "empire_guarded_lord_helmet", "imperial_goggled_helmet",
            "heavy_nasalhelm_over_imperial_mail", "ironlame_nasalhelm_over_imperial_mail",
            "ironlame_nasalhelm_over_imperial_coif",
        };
        private static readonly string[] Bodies =
        {
            "empire_plate_vest_armor", "imperial_scale_armor",
            "lamellar_with_scale_skirt", "imperial_lamellar", "empire_legion_b",
        };
        private static readonly string[] Gloves =
        {
            "decorated_imperial_gauntlets", "lamellar_plate_gauntlets",
            "plated_strip_gauntlets", "reinforced_padded_mitten", "lordly_padded_mitten",
        };
        private static readonly string[] Boots =
        {
            "decorated_imperial_boots", "lamellar_plate_boots",
            "plated_strip_boots", "empire_horseman_boots", "strapped_leather_boots",
        };

        private static int _requestedSet = -1;
        private static bool _done;

        // Troop showcase: /eqtroops puts one fighter of every Equestria troop into the player's party and
        // opens the party screen. It also writes each one's name, race and armour to the log, so you see at once
        // whether our rewritten entry was picked up (tools/make_troops.py).
        private const string TroopsArg = "/eqtroops";
        private const string BanditsArg = "/eqbandits";
        private const string ChangelingsArg = "/eqchangelings";
        private static bool _troopsRequested;
        private static string[] _troopsToShow;
        private static readonly string[] BanditTroops =
        {
            "looter", "deserter", "mounted_pillager", "mounted_ransacker",
            "sea_raiders_bandit", "sea_raiders_raider", "sea_raiders_chief", "sea_raiders_boss",
            "mountain_bandits_bandit", "mountain_bandits_raider", "mountain_bandits_chief", "mountain_bandits_boss",
            "forest_bandits_bandit", "forest_bandits_raider", "forest_bandits_chief", "forest_bandits_boss",
            "desert_bandits_bandit", "desert_bandits_raider", "desert_bandits_chief", "desert_bandits_boss",
            "steppe_bandits_bandit", "steppe_bandits_raider", "steppe_bandits_chief", "steppe_bandits_boss",
        };
        private static readonly string[] EquestriaTroops =
        {
            "imperial_recruit", "imperial_infantryman", "imperial_trained_infantryman",
            "imperial_veteran_infantryman", "imperial_legionary", "imperial_menavliaton",
            "imperial_elite_menavliaton", "imperial_archer", "imperial_trained_archer",
            "imperial_veteran_archer", "imperial_palatine_guard", "bucellarii", "imperial_crossbowman",
            "imperial_sergeant_crossbowman", "imperial_vigla_recruit", "imperial_equite",
            "imperial_heavy_horseman", "imperial_cataphract", "imperial_elite_cataphract",
            "imperial_militia_spearman", "imperial_militia_archer",
            "imperial_militia_veteran_spearman", "imperial_militia_veteran_archer",
        };
        // The changeling swarm (Aserai tree, tools/make_troops.py); the recruit first, his only armour is boots.
        private static readonly string[] ChangelingTroops =
        {
            "aserai_recruit", "aserai_tribesman", "aserai_skirmisher", "aserai_archer", "aserai_master_archer",
            "aserai_footman", "aserai_infantry", "aserai_veteran_infantry", "aserai_mameluke_soldier",
            "aserai_mameluke_regular", "aserai_mameluke_cavalry", "aserai_mameluke_heavy_cavalry",
            "aserai_mameluke_axeman", "aserai_mameluke_guard", "mamluke_palace_guard", "aserai_youth",
            "aserai_tribal_horseman", "aserai_faris", "aserai_veteran_faris", "aserai_vanguard_faris",
            "aserai_militia_spearman", "aserai_militia_archer",
            "aserai_militia_veteran_spearman", "aserai_militia_veteran_archer",
        };
        // Hairstyle check: /eqbarber:changeling makes the player's hero this race and opens the
        // appearance editor (like the barber's, with all sections): the hair and its colour are visible there.
        private const string BarberPrefix = "/eqbarber:";
        // Trying on a lord's look: /eqhero:chrysalis transfers the race, face and hairstyle of the named
        // hero onto the player and opens the appearance editor; this shows unique characters
        // (Chrysalis has the queen's green eyes, a face variant from pony_skins.xml) without finding them on the map.
        private const string HeroPrefix = "/eqhero:";
        private static string _heroLook;
        // Talking to a lord: /eqmeet:chrysalis starts a conversation with the named hero; in a conversation
        // the character is shown in full, with equipment (the appearance editor does not draw headgear).
        private const string MeetPrefix = "/eqmeet:";
        private static string _meetHero;
        // A battle with bandits in one command: needed to check how characters look
        // in a mission (body parts are attached to the skeleton only there, see EquestriaBodyParts).
        private const string BattleArg = "/eqbattle";
        // A "knee-deep in blood" battle for testing limb severing (EquestriaDismemberment.cs):
        // equestria.dismember_test via EquestriaDebugCommands, [N] per side.
        private const string DismemberArgPrefix = "/eqdismember";
        private static bool _dismemberRequested;
        private static int _dismemberPerSide = 50;
        // The race of the test fighters is a suffix after the count (/eqdismember:100:yak), pony by default.
        // See EquestriaDebugCommands.DismemberTestTroopByRace for the list of supported races.
        private static string _dismemberRace = "pony";
        // Body part check: /eqnude strips all equipment from the hero (including the tail, which
        // still lies in the cape slot in the sets from equestria_equipment_sets.xml) and opens the
        // inventory. If the tail is visible, it is attached by our code, not by an item.
        private const string NudeArg = "/eqnude";
        private static bool _nudeRequested;
        private static bool _battleRequested;
        private static string _barberRace;
        private static DateTime _mapSeenAt = DateTime.MinValue;

        public static void CheckRequest()
        {
            foreach (string arg in Environment.GetCommandLineArgs())
            {
                if (arg.StartsWith(ArgPrefix, StringComparison.OrdinalIgnoreCase)
                    && int.TryParse(arg.Substring(ArgPrefix.Length), out int set))
                {
                    _requestedSet = set;
                    EquestriaCrashLog.Log("показ брони: запрошен комплект " + set);
                }
                if (string.Equals(arg, TroopsArg, StringComparison.OrdinalIgnoreCase))
                {
                    _troopsRequested = true;
                    _troopsToShow = EquestriaTroops;
                    EquestriaCrashLog.Log("показ войск: запрошена армия Эквестрии");
                }
                if (string.Equals(arg, BanditsArg, StringComparison.OrdinalIgnoreCase))
                {
                    _troopsRequested = true;
                    _troopsToShow = BanditTroops;
                    EquestriaCrashLog.Log("показ войск: запрошены разбойники");
                }
                if (string.Equals(arg, NudeArg, StringComparison.OrdinalIgnoreCase))
                {
                    _nudeRequested = true;
                    EquestriaCrashLog.Log("показ без снаряжения: запрошен голый герой");
                }
                if (string.Equals(arg, BattleArg, StringComparison.OrdinalIgnoreCase))
                {
                    _battleRequested = true;
                    EquestriaCrashLog.Log("показ боя: запрошен бой с разбойниками");
                }
                if (arg.StartsWith(DismemberArgPrefix, StringComparison.OrdinalIgnoreCase))
                {
                    _dismemberRequested = true;
                    string tail = arg.Substring(DismemberArgPrefix.Length).TrimStart(':');
                    // Format /eqdismember:<count>:<race>; the race is optional.
                    string[] parts = tail.Split(':');
                    _dismemberPerSide = int.TryParse(parts[0], out int n) ? Math.Max(1, Math.Min(200, n)) : 50;
                    if (parts.Length > 1 && !string.IsNullOrWhiteSpace(parts[1]))
                    {
                        _dismemberRace = parts[1];
                    }
                    EquestriaCrashLog.Log($"тест отрубания: запрошен бой по {_dismemberPerSide} на сторону, раса {_dismemberRace}");
                }
                if (arg.StartsWith(BarberPrefix, StringComparison.OrdinalIgnoreCase))
                {
                    _barberRace = arg.Substring(BarberPrefix.Length);
                    EquestriaCrashLog.Log("редактор внешности: запрошена раса " + _barberRace);
                }
                if (arg.StartsWith(HeroPrefix, StringComparison.OrdinalIgnoreCase))
                {
                    _heroLook = arg.Substring(HeroPrefix.Length);
                    EquestriaCrashLog.Log("примерка внешности: запрошен герой " + _heroLook);
                }
                if (arg.StartsWith(MeetPrefix, StringComparison.OrdinalIgnoreCase))
                {
                    _meetHero = arg.Substring(MeetPrefix.Length);
                    EquestriaCrashLog.Log("разговор: запрошен герой " + _meetHero);
                }
                if (string.Equals(arg, ChangelingsArg, StringComparison.OrdinalIgnoreCase))
                {
                    _troopsRequested = true;
                    _troopsToShow = ChangelingTroops;
                    EquestriaCrashLog.Log("показ войск: запрошен рой чейнджлингов");
                }
            }
        }

        // Called every frame. Wait until the map has been up for a couple of seconds, then dress and open the inventory.
        public static void Tick()
        {
            EquestriaCrashLog.Try("ключ внешности", WatchBodyProperties);
            if ((_requestedSet < 0 && !_troopsRequested && !_battleRequested && !_nudeRequested && !_dismemberRequested
                    && _barberRace == null && _heroLook == null && _meetHero == null) || _done)
            {
                return;
            }
            // The state first, and only then the hero: while the campaign is loading, merely accessing
            // Hero.MainHero throws an exception (the player has no character yet).
            if (!(GameStateManager.Current?.ActiveState is MapState) || Campaign.Current == null)
            {
                return;
            }
            if (_mapSeenAt == DateTime.MinValue)
            {
                _mapSeenAt = DateTime.Now;
                return;
            }
            if ((DateTime.Now - _mapSeenAt).TotalSeconds < 3)
            {
                return;
            }
            _done = true;
            if (_meetHero != null)
            {
                EquestriaCrashLog.Try("разговор с героем", MeetHero);
                return;
            }
            if (_heroLook != null)
            {
                EquestriaCrashLog.Try("примерка внешности", WearHeroLook);
                return;
            }
            if (_barberRace != null)
            {
                EquestriaCrashLog.Try("редактор внешности", () => OpenBarber());
                return;
            }
            if (_troopsRequested)
            {
                EquestriaCrashLog.Try("показ войск", ShowTroops);
                return;
            }
            if (_nudeRequested)
            {
                EquestriaCrashLog.Try("показ без снаряжения", ShowNude);
                return;
            }
            if (_battleRequested)
            {
                EquestriaCrashLog.Try("показ боя", () =>
                {
                    string result = EquestriaDebugCommands.FightBandits(new List<string> { "looters", "3" });
                    EquestriaCrashLog.Note("показ боя: " + result);
                });
                return;
            }
            if (_dismemberRequested)
            {
                EquestriaCrashLog.Try("тест отрубания", () =>
                {
                    string result = EquestriaDebugCommands.DismembermentTestBattle(
                        new List<string> { _dismemberPerSide.ToString(), _dismemberRace });
                    EquestriaCrashLog.Note("тест отрубания: " + result);
                });
                return;
            }
            EquestriaCrashLog.Try("показ брони", () =>
            {
                if (Hero.MainHero == null)
                {
                    EquestriaCrashLog.Warn("показ брони: героя игрока нет");
                    return;
                }
                string worn = Wear(Hero.MainHero, _requestedSet);
                EquestriaCrashLog.Log("показ брони: " + worn);
                InventoryScreenHelper.OpenScreenAsInventory();
                EquestriaCrashLog.Note("показ брони: инвентарь открыт");
            });
        }

        // Starts a conversation with the named hero: his model is visible in full, with equipment.
        private static void MeetHero()
        {
            var hero = FindHero(_meetHero);
            if (hero == null)
            {
                EquestriaCrashLog.Warn("разговор: героя " + _meetHero + " нет в мире");
                return;
            }
            var party = hero.PartyBelongedTo?.Party ?? hero.CurrentSettlement?.Party;
            CampaignMapConversation.OpenConversation(
                new ConversationCharacterData(CharacterObject.PlayerCharacter, PartyBase.MainParty),
                new ConversationCharacterData(hero.CharacterObject, party));
            EquestriaCrashLog.Note("разговор: " + hero.Name + ", шлем "
                + (hero.BattleEquipment[EquipmentIndex.Head].Item?.StringId ?? "нет"));
        }

        private static Hero FindHero(string id)
        {
            return Hero.AllAliveHeroes.Concat(Hero.DeadOrDisabledHeroes)
                .FirstOrDefault(h => h.StringId == id || h.StringId == "eq_" + id);
        }

        // Transfers the named hero's appearance onto the player and opens the appearance editor.
        private static void WearHeroLook()
        {
            var hero = FindHero(_heroLook);
            if (hero == null)
            {
                EquestriaCrashLog.Warn("примерка внешности: героя " + _heroLook + " нет в мире");
                return;
            }
            EquestriaRaceSaveBehavior.SetRace(Hero.MainHero, hero.CharacterObject.Race);
            Hero.MainHero.CharacterObject.UpdatePlayerCharacterBodyProperties(
                hero.BodyProperties, hero.CharacterObject.Race, hero.IsFemale);
            Hero.MainHero.StaticBodyProperties = hero.BodyProperties.StaticProperties;
            EquestriaCrashLog.Log("примерка внешности: " + hero.Name + " (раса " + hero.CharacterObject.Race
                + "), ключ " + hero.BodyProperties);
            _barberRace = FaceGen.GetRaceNames()[hero.CharacterObject.Race];
            // the hero's helmet is put on BEFORE opening the screen (for Chrysalis this slot holds her horn with a crown):
            // the model on the screen is assembled at the moment of opening, anything put on later does not get there
            var head = hero.BattleEquipment[EquipmentIndex.Head];
            Hero.MainHero.BattleEquipment[EquipmentIndex.Head] = head;
            Hero.MainHero.CivilianEquipment[EquipmentIndex.Head] = head;
            EquestriaCrashLog.Log("примерка внешности: шлем " + (head.Item?.StringId ?? "нет"));
            OpenBarber(keepHead: true);
        }

        private static void OpenBarber(bool keepHead = false)
        {
            var names = FaceGen.GetRaceNames();
            if (!names.Contains(_barberRace))
            {
                EquestriaCrashLog.Warn("редактор внешности: нет расы " + _barberRace + ", есть " + string.Join(", ", names));
                return;
            }
            EquestriaRaceSaveBehavior.SetRace(Hero.MainHero, FaceGen.GetRaceOrDefault(_barberRace));
            if (!keepHead)
            {
                // free the helmet slot: the hairstyle must be visible in full
                Hero.MainHero.BattleEquipment[EquipmentIndex.Head] = EquipmentElement.Invalid;
                Hero.MainHero.CivilianEquipment[EquipmentIndex.Head] = EquipmentElement.Invalid;
            }
            var facegen = Campaign.Current.GetCampaignBehavior<IFacegenCampaignBehavior>();
            var state = Game.Current.GameStateManager.CreateState<BarberState>(
                Hero.MainHero.CharacterObject, facegen?.GetFaceGenFilter());
            GameStateManager.Current.PushState(state);
            EquestriaCrashLog.Note("редактор внешности: открыт для расы " + _barberRace);
            _watchBodyProperties = true;
        }

        // The hero's appearance key to the log. The face variant index (face_textures in skins.xml; for
        // changelings this is the queen's green eyes) is not set in the character XML: it lies inside the
        // BodyProperties key. So the appearance is put together in the editor, and we take the finished key
        // from here and write it into the hero (tools/world_data.py).
        private static bool _watchBodyProperties;
        private static string _lastKey;

        private static void WatchBodyProperties()
        {
            if (!_watchBodyProperties || Hero.MainHero == null)
            {
                return;
            }
            string key = Hero.MainHero.BodyProperties.ToString();
            if (key != _lastKey)
            {
                _lastKey = key;
                EquestriaCrashLog.Log("ключ внешности игрока: " + key);
            }
        }

        // Strips everything from the hero and opens the inventory: a clean check of who draws the tail, an item
        // in the cape slot or our code (EquestriaBodyParts).
        private static void ShowNude()
        {
            if (Hero.MainHero == null)
            {
                EquestriaCrashLog.Warn("показ без снаряжения: героя игрока нет");
                return;
            }
            foreach (var equipment in new[] { Hero.MainHero.BattleEquipment, Hero.MainHero.CivilianEquipment })
            {
                for (int i = 0; i < (int)EquipmentIndex.NumEquipmentSetSlots; i++)
                {
                    equipment[(EquipmentIndex)i] = EquipmentElement.Invalid;
                }
            }
            InventoryScreenHelper.OpenScreenAsInventory();
            EquestriaCrashLog.Note("показ без снаряжения: инвентарь открыт, слоты пусты");
        }

        private static void ShowTroops()
        {
            var roster = MobileParty.MainParty.MemberRoster;
            int pony = TaleWorlds.Core.FaceGen.GetRaceOrDefault(EquestriaMane.RaceId);
            int changeling = TaleWorlds.Core.FaceGen.GetRaceOrDefault(EquestriaMane.ChangelingRaceId);
            foreach (string id in _troopsToShow)
            {
                var troop = MBObjectManager.Instance.GetObject<CharacterObject>(id);
                if (troop == null)
                {
                    EquestriaCrashLog.Warn("показ войск: нет войска " + id);
                    continue;
                }
                roster.AddToCounts(troop, 1);
                var equipment = troop.FirstBattleEquipment;
                var armor = new List<string>();
                foreach (var slot in new[] { EquipmentIndex.Head, EquipmentIndex.Body, EquipmentIndex.Leg,
                             EquipmentIndex.Gloves, EquipmentIndex.Cape })
                {
                    armor.Add(equipment[slot].Item?.StringId ?? "-");
                }
                EquestriaCrashLog.Log($"  {id}: «{troop.Name}», ступень {troop.Tier}, "
                    + $"{(troop.Race == pony ? "пони" : troop.Race == changeling && changeling != 0 ? "чейнджлинг" : "НЕ пони (" + troop.Race + ")")}, "
                    + $"улучшений {troop.UpgradeTargets?.Length ?? 0}, броня {string.Join(" / ", armor)}");
            }
            PartyScreenHelper.OpenScreenAsNormal();
            EquestriaCrashLog.Note("показ войск: экран отряда открыт");
        }

        // Puts a set on the hero (battle and civilian sets, so that the model in the inventory
        // shows the armour whichever set is selected). Returns a string for the log.
        public static string Wear(Hero hero, int set)
        {
            var slots = new List<(EquipmentIndex Slot, string Id)>
            {
                (EquipmentIndex.Head, Helmets[Wrap(set)]),
                (EquipmentIndex.Body, Bodies[Wrap(set)]),
                (EquipmentIndex.Gloves, Gloves[Wrap(set)]),
                (EquipmentIndex.Leg, Boots[Wrap(set)]),
            };
            var missing = new List<string>();
            foreach (var equipment in new[] { hero.BattleEquipment, hero.CivilianEquipment })
            {
                foreach (var (slot, id) in slots)
                {
                    var item = MBObjectManager.Instance.GetObject<ItemObject>(id);
                    if (item == null)
                    {
                        if (!missing.Contains(id))
                        {
                            missing.Add(id);
                        }
                        continue;
                    }
                    equipment[slot] = new EquipmentElement(item);
                }
            }
            string result = "комплект " + Wrap(set) + ": " + Helmets[Wrap(set)] + ", " + Bodies[Wrap(set)]
                + ", " + Gloves[Wrap(set)] + ", " + Boots[Wrap(set)];
            if (missing.Count > 0)
            {
                EquestriaCrashLog.Warn("показ брони: нет предметов " + string.Join(", ", missing));
            }
            return result;
        }

        private static int Wrap(int set)
        {
            return ((set % Helmets.Length) + Helmets.Length) % Helmets.Length;
        }

        // Console (Alt+~): equestria.wear_set 0..4
        [CommandLineFunctionality.CommandLineArgumentFunction("wear_set", "equestria")]
        public static string WearSetCommand(List<string> args)
        {
            if (Campaign.Current == null || Hero.MainHero == null)
            {
                return "Available only in a campaign.";
            }
            if (args.Count != 1 || !int.TryParse(args[0], out int set))
            {
                return "Format: equestria.wear_set <0..4>";
            }
            return Wear(Hero.MainHero, set);
        }
    }
}
