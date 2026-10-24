using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using Helpers;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.GameState;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.Localization;
using TaleWorlds.MountAndBlade;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Race review: a start after which the player's party has three companions of EACH race, each
    // dressed in random armour. Needed to see in one launch how vanilla armour fits on all our
    // models - before this each race had to be checked in a separate campaign.
    //
    // Started in three ways:
    //   .\run.ps1 -Races          a new sandbox without a single click, companions already in the party;
    //   the "Equestria: race review" button in the main menu - the same by hand;
    //   equestria.race_party [how many] - recruit them in an already started campaign.
    public static class EquestriaRaceParty
    {
        private const string OptionId = "EquestriaRaceParty";
        private const string ArgPrefix = "/eqraces";     // /eqraces:5 is allowed
        private const int DefaultPerRace = 3;
        private const int MaxPerRace = 20;

        private static int _wanted;                      // 0 - review not requested
        private static bool _done;
        private static DateTime _mapSeenAt = DateTime.MinValue;

        public static void CheckRequest()
        {
            foreach (string arg in Environment.GetCommandLineArgs())
            {
                if (!arg.StartsWith(ArgPrefix, StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }
                string tail = arg.Substring(ArgPrefix.Length).TrimStart(':');
                _wanted = int.TryParse(tail, out int n) ? Math.Max(1, Math.Min(MaxPerRace, n)) : DefaultPerRace;
                EquestriaCrashLog.Log($"смотр рас: запрошен по ключу, по {_wanted} спутника на расу");
            }
        }

        public static void AddMenuOption()
        {
            var option = new InitialStateOption(
                OptionId,
                new TextObject("{=eq_race_party_menu}Equestria: race review"),
                9990,
                StartShowcaseCampaign,
                () => (false, null),
                null,
                () => false);
            Module.CurrentModule.AddInitialStateOption(option);
        }

        private static void StartShowcaseCampaign()
        {
            _wanted = DefaultPerRace;
            _done = false;
            _mapSeenAt = DateTime.MinValue;
            EquestriaQuickStart.StartQuickCampaign();
        }

        // Wait for the map: before it the player has neither a party nor a clan, and nowhere to put a companion.
        // The two-second pause is the same as in the helmet fitting room: right after the map appears
        // the campaign is still finishing its start.
        public static void Tick()
        {
            if (_wanted <= 0 || _done)
            {
                return;
            }
            if (!(GameStateManager.Current?.ActiveState is MapState) || Campaign.Current == null)
            {
                return;
            }
            if (_mapSeenAt == DateTime.MinValue)
            {
                _mapSeenAt = DateTime.UtcNow;
                return;
            }
            if ((DateTime.UtcNow - _mapSeenAt).TotalSeconds < 2)
            {
                return;
            }
            _done = true;
            EquestriaCrashLog.Try("смотр рас по ключу", () =>
            {
                string report = Run(new List<string> { _wanted.ToString() });
                EquestriaCrashLog.Log(report.Replace("\n", " "));
                InformationManager.DisplayMessage(new InformationMessage(report, Colors.Magenta));
                // If the same launch also asks for a battle (/eqbattle), do not open the party screen: it would
                // change the game state, and the battle (EquestriaShowcase, waits for the map just like we do)
                // would not start - the same trick as EquestriaHelmetTest uses with the inventory.
                bool toBattle = Environment.GetCommandLineArgs()
                    .Any(a => string.Equals(a, "/eqbattle", StringComparison.OrdinalIgnoreCase));
                if (!toBattle)
                {
                    PartyScreenHelper.OpenScreenAsNormal();
                }
            });
        }

        // Armour slots and the item types for them. No weapons: we are looking specifically at armour fit.
        private static readonly (EquipmentIndex Slot, ItemObject.ItemTypeEnum Type)[] Wear =
        {
            (EquipmentIndex.Head, ItemObject.ItemTypeEnum.HeadArmor),
            (EquipmentIndex.Body, ItemObject.ItemTypeEnum.BodyArmor),
            (EquipmentIndex.Leg, ItemObject.ItemTypeEnum.LegArmor),
            (EquipmentIndex.Gloves, ItemObject.ItemTypeEnum.HandArmor),
            (EquipmentIndex.Cape, ItemObject.ItemTypeEnum.Cape),
        };

        private static Dictionary<ItemObject.ItemTypeEnum, List<ItemObject>> _pool;

        // What can be worn at all. Filter out items without a mesh and race body parts (tails, wings,
        // crests): they also count as armour, but EquestriaBodyParts attaches them to the skeleton, and
        // they have no business in the cape slot - otherwise a deer would get someone else's tail.
        // internal - reused by EquestriaDebugCommands.DismembermentTestBattle (random
        // armour on the fighters of the test battle).
        internal static List<ItemObject> Pool(ItemObject.ItemTypeEnum type)
        {
            if (_pool == null)
            {
                _pool = MBObjectManager.Instance.GetObjectTypeList<ItemObject>()
                    .Where(i => i != null && i.ArmorComponent != null
                                && !string.IsNullOrEmpty(i.MultiMeshName)
                                && !EquestriaBodyParts.IsBodyPart(i.StringId))
                    .GroupBy(i => i.ItemType)
                    .ToDictionary(g => g.Key, g => g.ToList());
            }
            List<ItemObject> list;
            return _pool.TryGetValue(type, out list) ? list : new List<ItemObject>();
        }

        // Dress randomly: each slot gets its own random item, and the battle set matches the
        // civilian one so the armour is visible in any screen.
        private static string Dress(Hero hero)
        {
            var worn = new List<string>();
            foreach (var (slot, type) in Wear)
            {
                var pool = Pool(type);
                if (pool.Count == 0)
                {
                    continue;
                }
                var item = pool[MBRandom.RandomInt(pool.Count)];
                hero.BattleEquipment[slot] = new EquipmentElement(item);
                hero.CivilianEquipment[slot] = new EquipmentElement(item);
                worn.Add(item.StringId);
            }
            return string.Join(", ", worn);
        }

        // equestria.race_party [how many per race] - recruit companions of all races into the party
        [CommandLineFunctionality.CommandLineArgumentFunction("race_party", "equestria")]
        public static string Run(List<string> args)
        {
            if (Campaign.Current == null || MobileParty.MainParty == null || Clan.PlayerClan == null)
            {
                return "Доступно только в кампании.";
            }
            int per = args != null && args.Count > 0 && int.TryParse(args[0], out int n)
                ? Math.Max(1, Math.Min(MaxPerRace, n)) : DefaultPerRace;

            var names = TaleWorlds.Core.FaceGen.GetRaceNames();
            if (names == null || names.Length == 0)
            {
                return "Список рас пуст — skins не загрузились.";
            }
            // Wanderer templates: ordinary companions are made from them (see equestria.companions).
            // Canon ones (spc_eq_*) are skipped: they have their own looks and race, and we need
            // identical blanks to which we assign the race ourselves.
            var templates = CharacterObject.All
                .Where(c => c.Occupation == Occupation.Wanderer && c.IsTemplate
                            && !c.StringId.StartsWith("spc_eq_"))
                .ToList();
            if (templates.Count == 0)
            {
                return "Не нашлось ни одного шаблона странника.";
            }

            var report = new StringBuilder();
            int total = 0;
            for (int race = 0; race < names.Length; race++)
            {
                // Skip the vanilla human: nobody plays one in the mod, and it is not shown
                // in the appearance screen either (see EquestriaRaceSelector).
                if (names[race] == "human")
                {
                    continue;
                }
                for (int k = 0; k < per; k++)
                {
                    var template = templates[MBRandom.RandomInt(templates.Count)];
                    var hero = EquestriaDebugCommands.CreateWanderer(template);
                    EquestriaDebugCommands.JoinParty(hero, true);
                    EquestriaRaceSaveBehavior.SetRace(hero, race);
                    string worn = Dress(hero);
                    // Name by race with a number - otherwise you cannot tell who is which race in the party.
                    var title = EquestriaRaceSelector.TitleOf(names[race]).ToString();
                    var full = new TextObject("{=!}" + title + " " + (k + 1));
                    EquestriaCrashLog.Try("смотр рас: имя спутника", () => hero.SetName(full, full));
                    EquestriaCrashLog.Log($"смотр рас: {full} — раса {names[race]} ({race}), броня {worn}");
                    total++;
                }
                report.Append(report.Length > 0 ? ", " : "").Append(names[race]);
            }
            // Ponies get the mane and tail in free slots - for the other races EquestriaBodyParts
            // does this right in battle.
            EquestriaMane.EnsureForPonies();
            return $"Смотр рас: добавлено спутников {total} (по {per} на расу). Расы: {report}. "
                + $"Героев в отряде: {MobileParty.MainParty.MemberRoster.TotalHeroes}.";
        }
    }
}
