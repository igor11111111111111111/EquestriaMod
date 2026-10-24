using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using HarmonyLib;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Actions;
using TaleWorlds.CampaignSystem.Conversation;
using TaleWorlds.CampaignSystem.Encounters;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.CampaignSystem.Party.PartyComponents;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Debug commands for checking Equestria's lords on the map. The vanilla console has neither a teleport
    // nor a way to start a conversation, so we make our own.
    public static class EquestriaDebugCommands
    {
        private const string ClanId = "clan_equestria_royal";

        private static IEnumerable<Hero> ClanHeroes()
        {
            return Hero.AllAliveHeroes.Where(h => h.Clan != null && h.Clan.StringId == ClanId);
        }

        private static Hero Find(List<string> args)
        {
            var name = args.Count > 0 ? string.Join(" ", args) : null;
            if (name == null)
            {
                // Without a name: the leader of our clan, and if this campaign has none (quick test),
                // any living lord with a party, as long as there is someone to talk to
                return ClanHeroes().FirstOrDefault()
                    ?? Hero.AllAliveHeroes.FirstOrDefault(h => h.IsLord && h.PartyBelongedTo != null
                        && h != Hero.MainHero && h.Clan != Clan.PlayerClan);
            }
            // With a name, search among ALL living lords, not only our clan: by name people often
            // check a specific character from another house (e.g. a lord's lore colour, see
            // EquestriaBodyParts.LoreColors), not necessarily someone from clan_equestria_royal.
            // The console accepts only Latin letters: a Russian name (localisation) cannot be typed into it,
            // so we also search by the character's StringId (id="eq_..." from equestria_lords.xml,
            // it is always Latin): equestria.talk_to_lord eq_posey_shy works even if
            // the game is in Russian and "Posey Shy" cannot be typed in the console.
            var needle = name.ToLower();
            return Hero.AllAliveHeroes.FirstOrDefault(h => h.IsLord
                && (h.Name.ToString().ToLower().Contains(needle)
                    || (h.CharacterObject?.StringId?.ToLower().Contains(needle) ?? false)));
        }

        // equestria.list_lords: who is in the clan, where they are and whether they have a party
        [CommandLineFunctionality.CommandLineArgumentFunction("list_lords", "equestria")]
        public static string ListLords(List<string> args)
        {
            if (Campaign.Current == null)
            {
                return "Available only in a campaign.";
            }
            var lines = new List<string>();
            foreach (var hero in ClanHeroes())
            {
                var party = hero.PartyBelongedTo;
                var where = party != null
                    ? $"party at {party.GetPosition2D.x:F1}, {party.GetPosition2D.y:F1}"
                    : (hero.CurrentSettlement != null ? "in " + hero.CurrentSettlement.Name : "no party");
                lines.Add($"{hero.Name} ({hero.CharacterObject.Race}) — {where}");
            }
            return lines.Count > 0 ? string.Join("\n", lines) : "Clan " + ClanId + " has no living heroes.";
        }

        // equestria.goto_lord [name]: move the player's party to a lord (by default to the clan leader)
        [CommandLineFunctionality.CommandLineArgumentFunction("goto_lord", "equestria")]
        public static string GotoLord(List<string> args)
        {
            if (Campaign.Current == null || MobileParty.MainParty == null)
            {
                return "Available only in a campaign.";
            }
            var hero = Find(args);
            if (hero == null)
            {
                return "Lord not found. Use equestria.list_lords.";
            }
            var target = hero.PartyBelongedTo;
            if (target == null)
            {
                return hero.Name + " has no party on the map.";
            }
            MobileParty.MainParty.Position = target.Position;  // CampaignVec2, there is no Position2D in 1.4.8
            return $"Teleported to {hero.Name} at {target.GetPosition2D.x:F1}, {target.GetPosition2D.y:F1}.";
        }

        // equestria.talk_to_lord [name]: open a conversation with a lord wherever he is
        [CommandLineFunctionality.CommandLineArgumentFunction("talk_to_lord", "equestria")]
        public static string TalkToLord(List<string> args)
        {
            if (Campaign.Current == null || Hero.MainHero == null)
            {
                return "Available only in a campaign.";
            }
            var hero = Find(args);
            if (hero == null)
            {
                return "Lord not found. Use equestria.list_lords.";
            }
            var player = new ConversationCharacterData(CharacterObject.PlayerCharacter, PartyBase.MainParty);
            var other = new ConversationCharacterData(hero.CharacterObject, hero.PartyBelongedTo?.Party);
            CampaignMapConversation.OpenConversation(player, other);
            return "Talking to " + hero.Name + ".";
        }

        // equestria.companions [count]: recruit random companions into the party (100 by default)
        // from all wanderer templates of all cultures; among them are also canon secondary
        // characters (spc_eq_* templates: Lyra, Ocellus, Gallus...), but each at most once.
        // The command does not touch the main canon heroes (Twilight, Applejack...): they are lords of their clans,
        // and a hero can be a companion only instead of that; the world would be left without them.
        // The party size limit is not checked: this is a test command.
        [CommandLineFunctionality.CommandLineArgumentFunction("companions", "equestria")]
        public static string Companions(List<string> args)
        {
            if (Campaign.Current == null || MobileParty.MainParty == null)
            {
                return "Доступно только в кампании.";
            }
            int wanted = args.Count > 0 && int.TryParse(args[0], out int n) ? n : 100;
            var templates = CharacterObject.All
                .Where(c => c.Occupation == Occupation.Wanderer && c.IsTemplate).ToList();
            var usedCanon = new HashSet<CharacterObject>();
            int added = 0;
            int canon = 0;
            while (added < wanted && templates.Count > 0)
            {
                var template = templates[MBRandom.RandomInt(templates.Count)];
                if (template.StringId.StartsWith("spc_eq_"))
                {
                    if (!usedCanon.Add(template))
                    {
                        continue;   // a canon one only once
                    }
                    canon++;
                }
                JoinParty(CreateWanderer(template), true);
                added++;
            }
            return $"В отряд добавлено спутников: {added}, из них канонных {canon}. "
                + $"Героев в отряде: {MobileParty.MainParty.MemberRoster.TotalHeroes}.";
        }

        // internal: the race showcase (EquestriaRaceParty) recruits companions the same way
        internal static Hero CreateWanderer(CharacterObject template)
        {
            Settlement home = Settlement.All.FirstOrDefault(s => s.IsTown && s.Culture == template.Culture)
                ?? Settlement.All.First(s => s.IsTown);
            int age = template.Age > 0 ? (int)template.Age : 25;
            return HeroCreator.CreateSpecialHero(template, home, null, null, age);
        }

        // Take a hero into the player's party. asCompanion makes him a companion of the player's clan (for wanderers);
        // lords stay in their clans and only travel with the player.
        internal static void JoinParty(Hero hero, bool asCompanion)
        {
            var own = hero.PartyBelongedTo;
            if (own != null && own != MobileParty.MainParty)
            {
                if (own.LeaderHero == hero)
                {
                    TaleWorlds.CampaignSystem.Actions.DestroyPartyAction.Apply(null, own);
                }
                else
                {
                    own.MemberRoster.RemoveTroop(hero.CharacterObject, 1);
                }
            }
            if (hero.CurrentSettlement != null)
            {
                TaleWorlds.CampaignSystem.Actions.LeaveSettlementAction.ApplyForCharacterOnly(hero);
            }
            if (asCompanion && hero.Clan != Clan.PlayerClan)
            {
                TaleWorlds.CampaignSystem.Actions.AddCompanionAction.Apply(Clan.PlayerClan, hero);
            }
            TaleWorlds.CampaignSystem.Actions.AddHeroToPartyAction.Apply(hero, MobileParty.MainParty, false);
        }

        // equestria.meet <part of a name or id> | all: "meet" a hero without an encounter: the
        // encyclopedia then shows the portrait, age, occupation and relations (Hero.SetHasMet). all: with
        // all living heroes at once. Vanilla has no such command (10.10.2026).
        [CommandLineFunctionality.CommandLineArgumentFunction("meet", "equestria")]
        public static string Meet(List<string> args)
        {
            if (Campaign.Current == null)
            {
                return "Нужна начатая кампания.";
            }
            string key = string.Join(" ", args ?? new List<string>()).Trim().ToLower();
            if (key.Length == 0)
            {
                return "Укажите часть имени или id героя, например equestria.meet найтшейд, или all — со всеми.";
            }
            var heroes = key == "all"
                ? Hero.AllAliveHeroes.ToList()
                : Hero.AllAliveHeroes.Concat(Hero.DeadOrDisabledHeroes)
                    .Where(h => h.StringId.ToLower() == key || h.Name.ToString().ToLower().Contains(key)).ToList();
            if (heroes.Count == 0)
            {
                return "Героев не найдено: " + key;
            }
            foreach (var hero in heroes)
            {
                hero.SetHasMet();
            }
            return heroes.Count <= 10
                ? "Знакомы теперь: " + string.Join(", ", heroes.Select(h => h.Name.ToString()))
                : $"Знакомы теперь со всеми: {heroes.Count} героев.";
        }

        // equestria.hero_info <part of a name or id>: what the game actually knows about a hero: race,
        // age, appearance key, battle and civilian equipment. For comparing those who are drawn in the
        // party screen with those whose screen is empty.
        [CommandLineFunctionality.CommandLineArgumentFunction("hero_info", "equestria")]
        public static string HeroInfo(List<string> args)
        {
            if (Campaign.Current == null || args.Count == 0)
            {
                return "equestria.hero_info <имя или id>";
            }
            string key = string.Join(" ", args).ToLower();
            var hero = Hero.AllAliveHeroes.FirstOrDefault(h => h.StringId.ToLower() == key || h.StringId.ToLower() == "eq_" + key)
                ?? Hero.AllAliveHeroes.FirstOrDefault(h => h.Name.ToString().ToLower().Contains(key));
            if (hero == null)
            {
                return "Не найден: " + key;
            }
            var c = hero.CharacterObject;
            string Items(Equipment e) => e == null ? "нет" : string.Join(", ",
                Enumerable.Range(0, 12).Select(i => e[i].Item).Where(it => it != null).Select(it => it.StringId));
            return $"{hero.Name} [{hero.StringId}] раса {c.Race}, возраст {(int)hero.Age}, пол {(hero.IsFemale ? "ж" : "м")}, "
                + $"культура {hero.Culture?.StringId}, клан {hero.Clan?.StringId}, {(hero.IsWanderer ? "спутник" : hero.Occupation.ToString())}\n"
                + $"  внешность: {hero.BodyProperties}\n"
                + $"  бой: {Items(hero.BattleEquipment)}\n"
                + $"  быт: {Items(hero.CivilianEquipment)}";
        }

        // equestria.fight_bandits [gang] [count]: spawn a bandit party nearby and immediately fight it.
        //   gang: looters (default), sea_raiders, mountain_bandits, forest_bandits,
        //          desert_bandits, steppe_bandits
        //   count: how many times to enlarge the party (1..10), 1 by default
        // The console opens with Alt+~ (requires launching with developer mode enabled).
        [CommandLineFunctionality.CommandLineArgumentFunction("fight_bandits", "equestria")]
        public static string FightBandits(List<string> args)
        {
            if (Campaign.Current == null || MobileParty.MainParty == null)
            {
                return "Доступно только в кампании.";
            }
            if (MobileParty.MainParty.MapEvent != null || PlayerEncounter.Current != null)
            {
                return "Игрок уже в бою или в диалоге.";
            }
            string clanId = args.Count > 0 ? args[0] : "looters";
            int scale = args.Count > 1 && int.TryParse(args[1], out int n) ? MathF.Max(1, MathF.Min(10, n)) : 1;

            Clan clan = Clan.BanditFactions.FirstOrDefault(c => c.StringId == clanId);
            if (clan == null)
            {
                return "Нет такой банды: " + clanId + ". Есть: "
                    + string.Join(", ", Clan.BanditFactions.Select(c => c.StringId));
            }
            if (clan.DefaultPartyTemplate == null)
            {
                return "У банды " + clanId + " нет шаблона отряда.";
            }

            // Next to the player, slightly to the side; otherwise the party appears right on top of him.
            var near = new CampaignVec2(MobileParty.MainParty.GetPosition2D + new Vec2(0.6f, 0.6f), true);
            Settlement home = Settlement.All.Where(s => s.IsTown || s.IsVillage)
                .OrderBy(s => s.GetPosition2D.DistanceSquared(near.ToVec2())).FirstOrDefault();
            string id = "eq_debug_bandits_" + MBRandom.RandomInt(100000);
            MobileParty bandits = BanditPartyComponent.CreateLooterParty(id, clan, home, false,
                clan.DefaultPartyTemplate, near);

            // The template gives a modest party; multiply it if requested.
            if (scale > 1)
            {
                foreach (var element in bandits.MemberRoster.GetTroopRoster().ToList())
                {
                    bandits.MemberRoster.AddToCounts(element.Character, element.Number * (scale - 1));
                }
            }
            int size = bandits.MemberRoster.TotalManCount;
            if (size == 0)
            {
                DestroyPartyAction.Apply(null, bandits);
                return "Отряд вышел пустым — у шаблона банды " + clanId + " нет бойцов.";
            }

            EncounterManager.StartPartyEncounter(PartyBase.MainParty, bandits.Party);
            EquestriaCrashLog.Log($"отладка: бой с разбойниками {clan.Name}, бойцов {size}");
            return $"Бой с «{clan.Name}»: {size} бойцов.";
        }

        // Two-handed swords (not axes: those can be blunt rather than cutting and do not fit
        // the severing detection, which requires DamageType.Cut). All six really exist
        // (checked: used by battania troops in equestria_troops.xml).
        private static readonly string[] TwoHandedSwords =
        {
            "battania_2hsword_1_t2", "battania_2hsword_2_t3", "battania_2hsword_3_t3",
            "battania_2hsword_4_t4", "battania_2hsword_5_t4", "battania_2hsword_6",
        };

        // Race -> troop for equestria.dismember_test: one tall Infantry fighter of tier 21-26
        // per race (checked against equestria_troops.xml), so there is someone to sever arms/legs from; for
        // that a race with gloves/legs already cut into _l/_r is needed (EquestriaDismemberment.RaceInfo).
        private static readonly Dictionary<string, string> DismemberTestTroopByRace = new Dictionary<string, string>
        {
            { "pony", "embers_of_flame_tier_3" },        // Golden Horseshoe Veteran
            { "changeling", "aserai_veteran_infantry" }, // Hive Veteran
            { "dragon", "vlandian_sergeant" },            // Dragon Warrior (Vlandian branch)
            { "griffon", "khuzait_darkhan" },             // Griffonstone Axebearer (Khuzait branch)
            { "hippogriff", "eq_hg_sturgian_veteran_warrior" }, // Surf Veteran (copies of the Sturgian branch)
            { "yak", "sturgian_veteran_warrior" },        // Yakyakistan Axebearer (Sturgian branch)
            { "deer", "battanian_oathsworn" },            // Guard of Deer Grove (Battanian branch)
        };

        // equestria.dismember_test [count per side] [race]: a "knee-deep in blood" battle for testing
        // severing (EquestriaDismemberment.cs): the same number of fighters of the chosen race (pony by
        // default) in your party and the enemy's. 100 per side by default. The race is a key from
        // DismemberTestTroopByRace (pony/changeling/dragon/griffon/hippogriff/yak/deer), at the
        // user's request 07.10.2026 (previously the battle was always pony-only).
        // The enemy party is a container of a bandit clan (guaranteed hostile to anyone), but the roster
        // is entirely our own, not a bandit template.
        //
        // Not one identical kit for everyone (as before): at the user's request 07.10.2026
        // the troop gets SEVERAL equipment variants (a different two-handed sword + random armour
        // per slot, the same pool as EquestriaRaceParty.Dress), and from there it is the engine's standard
        // behaviour: on spawn ordinary troops randomly get one of the
        // BattleEquipments variants (vanilla does the same for fighters with several EquipmentRoster in XML).
        // The public API has no way to add a variant, so we reach the private list
        // MBEquipmentRoster._equipments via reflection (the same trick already used in the project
        // for AgentVisuals.GetEntity etc.).
        [CommandLineFunctionality.CommandLineArgumentFunction("dismember_test", "equestria")]
        public static string DismembermentTestBattle(List<string> args)
        {
            if (Campaign.Current == null || MobileParty.MainParty == null)
            {
                return "Доступно только в кампании.";
            }
            if (MobileParty.MainParty.MapEvent != null || PlayerEncounter.Current != null)
            {
                return "Игрок уже в бою или в диалоге.";
            }
            int perSide = args != null && args.Count > 0 && int.TryParse(args[0], out int n)
                ? Math.Max(1, Math.Min(200, n)) : 100;
            string race = args != null && args.Count > 1 && !string.IsNullOrWhiteSpace(args[1])
                ? args[1].Trim().ToLowerInvariant() : "pony";
            if (!DismemberTestTroopByRace.TryGetValue(race, out string troopId))
            {
                return "Неизвестная раса \"" + race + "\". Доступные: "
                    + string.Join(", ", DismemberTestTroopByRace.Keys) + ".";
            }

            CharacterObject troop = MBObjectManager.Instance.GetObject<CharacterObject>(troopId);
            if (troop == null)
            {
                return $"Не нашлось войско {troopId} (раса {race}).";
            }
            string variantsResult = AddRandomEquipmentVariants(troop, 10);
            if (variantsResult != null)
            {
                return variantsResult;
            }

            MobileParty.MainParty.MemberRoster.AddToCounts(troop, perSide);

            // The hero gets a two-handed sword too (at the user's request 07.10.2026), so that his hits
            // also fall under the severing detection, not only the troops'.
            if (Hero.MainHero != null)
            {
                var swords = TwoHandedSwords.Select(id => MBObjectManager.Instance.GetObject<ItemObject>(id))
                    .Where(it => it != null).ToList();
                if (swords.Count > 0)
                {
                    var sword = new EquipmentElement(swords[MBRandom.RandomInt(swords.Count)]);
                    Hero.MainHero.BattleEquipment[EquipmentIndex.Weapon0] = sword;
                    Hero.MainHero.CivilianEquipment[EquipmentIndex.Weapon0] = sword;
                }
            }

            Clan clan = Clan.BanditFactions.FirstOrDefault();
            if (clan == null || clan.DefaultPartyTemplate == null)
            {
                return "Не нашлось шаблона отряда для вражеской стороны.";
            }
            var near = new CampaignVec2(MobileParty.MainParty.GetPosition2D + new Vec2(0.6f, 0.6f), true);
            Settlement home = Settlement.All.Where(s => s.IsTown || s.IsVillage)
                .OrderBy(s => s.GetPosition2D.DistanceSquared(near.ToVec2())).FirstOrDefault();
            string id = "eq_dismember_test_" + MBRandom.RandomInt(100000);
            MobileParty enemy = BanditPartyComponent.CreateLooterParty(id, clan, home, false,
                clan.DefaultPartyTemplate, near);
            enemy.MemberRoster.Clear();
            enemy.MemberRoster.AddToCounts(troop, perSide);

            EncounterManager.StartPartyEncounter(PartyBase.MainParty, enemy.Party);
            EquestriaCrashLog.Log($"тест отрубания: {perSide} vs {perSide} ({race}, {troopId}), "
                + "разные двуручные мечи и броня");
            return $"Бой начат: {perSide} vs {perSide}, раса {race} ({troop.Name}), у каждого свой двуручный меч и броня.";
        }

        private static readonly FieldInfo EquipmentRosterField =
            AccessTools.Field(typeof(BasicCharacterObject), "_equipmentRoster");
        private static readonly FieldInfo EquipmentsListField =
            AccessTools.Field(typeof(MBEquipmentRoster), "_equipments");

        /// <summary>Adds count random equipment variants (two-handed sword + armour per
        /// slot) to the troop; the engine then hands them out to fighters randomly on spawn, as
        /// for any vanilla troop with several EquipmentRoster. Returns an error message,
        /// or null on success.</summary>
        private static string AddRandomEquipmentVariants(CharacterObject troop, int count)
        {
            var swords = TwoHandedSwords.Select(id => MBObjectManager.Instance.GetObject<ItemObject>(id))
                .Where(it => it != null).ToList();
            if (swords.Count == 0)
            {
                return "Не нашлось ни одного двуручного меча из списка.";
            }
            object roster = EquipmentRosterField?.GetValue(troop);
            if (roster == null)
            {
                return "У войска embers_of_flame_tier_3 нет _equipmentRoster — не могу добавить варианты.";
            }
            if (!(EquipmentsListField?.GetValue(roster) is System.Collections.IList equipments))
            {
                return "Не нашёл список _equipments у MBEquipmentRoster.";
            }
            for (int i = 0; i < count; i++)
            {
                var equipment = new Equipment(Equipment.EquipmentType.Battle);
                equipment[EquipmentIndex.Weapon0] = new EquipmentElement(swords[MBRandom.RandomInt(swords.Count)]);
                // Half-naked in light armour (at the user's request 07.10.2026): only a light
                // torso (cloth/leather, not mail/plate), legs/arms/head bare: severing is easier to see
                // by eye, and the armour cut itself does not get in the way of the cut.
                SetRandomArmor(equipment, EquipmentIndex.Body, ItemObject.ItemTypeEnum.BodyArmor, lightOnly: true);
                equipments.Add(equipment);
            }
            return null;
        }

        private static void SetRandomArmor(Equipment equipment, EquipmentIndex slot, ItemObject.ItemTypeEnum type,
            bool lightOnly = false)
        {
            var pool = EquestriaRaceParty.Pool(type);
            if (lightOnly)
            {
                pool = pool.Where(it => it.ArmorComponent.MaterialType == ArmorComponent.ArmorMaterialTypes.Cloth
                    || it.ArmorComponent.MaterialType == ArmorComponent.ArmorMaterialTypes.Leather).ToList();
            }
            if (pool.Count == 0)
            {
                return;
            }
            equipment[slot] = new EquipmentElement(pool[MBRandom.RandomInt(pool.Count)]);
        }
    }
}
