using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using Helpers;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Encounters;
using TaleWorlds.CampaignSystem.GameState;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.CampaignSystem.Party.PartyComponents;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Helmet fitting room: with one command get into the inventory wearing a helmet and with a set of others
    // at hand. Needed for fitting a helmet to a race's large head (src/EquestriaHelmetFit.cs):
    // it is important to look at both closed and open helmets; the engine fits them differently.
    public static class EquestriaHelmetTest
    {
        private const int PerKind = 8;      // how many open ones and how many closed ones to take

        // Launch key: /eqhelmets or /eqhelmets:open, all the same, but without the console.
        // Once the map is reached, it hands out the helmets itself, puts one on and opens the inventory.
        private const string ArgPrefix = "/eqhelmets";
        private const string BigBattleArg = "/eqbigbattle";
        private static bool _bigBattle;
        private static string _requested;
        private static bool _done;
        private static DateTime _mapSeenAt = DateTime.MinValue;

        public static void CheckRequest()
        {
            foreach (string arg in Environment.GetCommandLineArgs())
            {
                if (string.Equals(arg, BigBattleArg, StringComparison.OrdinalIgnoreCase))
                {
                    _bigBattle = true;
                    _requested = _requested ?? "open";
                    EquestriaCrashLog.Log("примерочная шлемов: запрошен крупный бой драконов");
                }
                if (!arg.StartsWith(ArgPrefix, StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }
                string tail = arg.Substring(ArgPrefix.Length).TrimStart(':');
                _requested = string.IsNullOrEmpty(tail) ? "closed" : tail.ToLower();
                EquestriaCrashLog.Log("примерочная шлемов: запрошена по ключу, шлем " + _requested);
            }
        }

        // Wait until the campaign is on the map: before that the player has no character yet.
        public static void Tick()
        {
            if (_requested == null || _done)
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
            EquestriaCrashLog.Try("примерочная шлемов по ключу",
                () => EquestriaCrashLog.Log(Run(new List<string> { _requested }).Replace("\n", " ")));
        }

        private static bool IsOpen(ItemObject item)
        {
            // "Open" is one that leaves the head visible; by the same sign the engine decides
            // whether to fit the helmet to the head size (ItemObject.UsingFacegenScaling)
            return item.ArmorComponent != null
                   && item.ArmorComponent.MeshesMask.HasAnyFlag(SkinMask.HeadVisible);
        }

        private static List<ItemObject> Pick(bool open)
        {
            // Vanilla helmets only: our items (eq_*) are the races' horns and manes, they also
            // count as "helmets", and last time the fitting room handed out exactly those.
            var all = MBObjectManager.Instance.GetObjectTypeList<ItemObject>()
                .Where(i => i != null && i.ItemType == ItemObject.ItemTypeEnum.HeadArmor
                            && i.ArmorComponent != null && IsOpen(i) == open
                            && !string.IsNullOrEmpty(i.MultiMeshName)
                            && !(i.StringId ?? "").StartsWith("eq_"))
                .OrderBy(i => i.Value)
                .ToList();
            if (all.Count <= PerKind)
            {
                return all;
            }
            // take them spread over the whole price range, from a cap to a commander's helmet
            var step = (double)(all.Count - 1) / (PerKind - 1);
            return Enumerable.Range(0, PerKind).Select(k => all[(int)(k * step)]).Distinct().ToList();
        }

        // equestria.helmet_test [open|closed]: hand out helmets, put one on and open the inventory
        [CommandLineFunctionality.CommandLineArgumentFunction("helmet_test", "equestria")]
        public static string Run(List<string> args)
        {
            if (Campaign.Current == null || Hero.MainHero == null)
            {
                return "Нужна начатая кампания.";
            }
            string want = args != null && args.Count > 0 ? args[0].ToLower() : "closed";
            // The fitting is needed specifically on a dragon: set the hero's race if he is not a dragon yet
            int dragon = TaleWorlds.Core.FaceGen.GetRaceOrDefault("dragon");
            if (dragon != 0 && Hero.MainHero.CharacterObject.Race != dragon)
            {
                EquestriaRaceSaveBehavior.SetRace(Hero.MainHero, dragon);
            }
            var open = Pick(true);
            var closed = Pick(false);
            var party = PartyBase.MainParty;
            foreach (var item in open.Concat(closed))
            {
                if (party.ItemRoster.GetItemNumber(item) == 0)
                {
                    party.ItemRoster.AddToCounts(item, 1);
                }
            }

            // Put it on right away: that way the window opens with the helmet already on, and the fit is visible
            var wear = (want == "open" ? open : closed).FirstOrDefault()
                       ?? open.Concat(closed).FirstOrDefault();
            if (wear != null)
            {
                Hero.MainHero.BattleEquipment[EquipmentIndex.Head] = new EquipmentElement(wear);
                Hero.MainHero.CivilianEquipment[EquipmentIndex.Head] = new EquipmentElement(wear);
            }

            var report = new StringBuilder();
            report.AppendLine($"Раса героя: {Hero.MainHero.CharacterObject.Race} "
                + $"({TaleWorlds.Core.FaceGen.GetRaceOrDefault("dragon")} — дракон)");
            report.AppendLine($"Выдано шлемов: открытых {open.Count}, закрытых {closed.Count}.");
            report.AppendLine($"Надет: {(wear != null ? wear.Name.ToString() : "нет")} "
                + $"({(wear != null && IsOpen(wear) ? "открытый" : "закрытый")}).");
            // If the same launch asks for a battle, do not open the inventory: it would change the game
            // state, and the battle would not start; showing the battle waits for the map.
            bool toBattle = _bigBattle || Environment.GetCommandLineArgs()
                .Any(a => string.Equals(a, "/eqbattle", StringComparison.OrdinalIgnoreCase));
            report.Append(toBattle
                ? "Шлем надет, инвентарь не открываю — сейчас бой."
                : "Открываю инвентарь — шлемы в списке справа, примеряйте по очереди.");
            EquestriaCrashLog.Log("примерочная шлемов: " + report.ToString().Replace("\n", " "));
            if (_bigBattle)
            {
                EquestriaCrashLog.Log("примерочная шлемов: " + BigBattle(null));
            }
            else if (!toBattle)
            {
                InventoryScreenHelper.OpenScreenAsInventory();
            }
            return report.ToString();
        }

        // Big dragon battle: both sides are Sturgian veterans (in the mod this culture is the
        // dragons), they are in full armour with helmets. Needed to look at the helmet in a crowd and at the same
        // time measure what the fitting costs on a thousand soldiers.
        private const string BigTroop = "sturgian_veteran_warrior";

        // equestria.big_battle [how many per side] [troop id]
        [CommandLineFunctionality.CommandLineArgumentFunction("big_battle", "equestria")]
        public static string BigBattle(List<string> args)
        {
            if (Campaign.Current == null || MobileParty.MainParty == null)
            {
                return "Доступно только в кампании.";
            }
            if (MobileParty.MainParty.MapEvent != null || PlayerEncounter.Current != null)
            {
                return "Игрок уже в бою или в разговоре.";
            }
            int side = args != null && args.Count > 0 && int.TryParse(args[0], out int n)
                ? Math.Max(1, Math.Min(2000, n)) : 500;
            string troopId = args != null && args.Count > 1 ? args[1] : BigTroop;
            var troop = MBObjectManager.Instance.GetObject<CharacterObject>(troopId);
            if (troop == null)
            {
                return "Нет такого войска: " + troopId;
            }

            // The enemy is made a bandit party: that is the shortest way to create a party on the map,
            // but its roster is replaced entirely: in battle the soldiers themselves matter, not the gang's sign.
            var clan = Clan.BanditFactions.FirstOrDefault(c => c.StringId == "looters");
            if (clan?.DefaultPartyTemplate == null)
            {
                return "В этой кампании нет разбойников, не из чего сделать врага.";
            }
            var near = new CampaignVec2(MobileParty.MainParty.GetPosition2D + new Vec2(0.6f, 0.6f), true);
            var home = Settlement.All.Where(x => x.IsTown || x.IsVillage)
                .OrderBy(x => x.GetPosition2D.DistanceSquared(near.ToVec2())).FirstOrDefault();
            var enemy = BanditPartyComponent.CreateLooterParty(
                "eq_big_battle_" + MBRandom.RandomInt(100000), clan, home, false,
                clan.DefaultPartyTemplate, near);
            enemy.MemberRoster.Clear();
            enemy.MemberRoster.AddToCounts(troop, side);
            MobileParty.MainParty.MemberRoster.AddToCounts(troop, side);

            EncounterManager.StartPartyEncounter(PartyBase.MainParty, enemy.Party);
            // Straight to the field, without the encounter menu: otherwise the game waits for "Attack"
            EquestriaCrashLog.Try("крупный бой: вход в сражение", PlayerEncounter.StartAttackMission);
            string report = $"Бой {side} на {side}: обе стороны — {troop.Name} ({troopId}).";
            EquestriaCrashLog.Log("крупный бой: " + report);
            return report;
        }

        // Whose helmet fit the commands tune: the PLAYER's race. Previously both commands edited the dragon
        // hard-coded, and there was no way to pick the numbers for a griffon. Outside a campaign (and for a human) it stays
        // the dragon: everything started with it, and in a custom battle there is nothing else to tune.
        private static string TunedRace()
        {
            if (Campaign.Current != null && Hero.MainHero != null && Hero.MainHero.CharacterObject != null)
            {
                string[] names = TaleWorlds.Core.FaceGen.GetRaceNames();
                int race = Hero.MainHero.CharacterObject.Race;
                if (race > 0 && race < names.Length)
                {
                    return names[race];
                }
            }
            return "dragon";
        }

        // equestria.helmet_offset <right> <forward> <up>: helmet shift in metres, on the fly
        [CommandLineFunctionality.CommandLineArgumentFunction("helmet_offset", "equestria")]
        public static string SetOffset(List<string> args)
        {
            string race = TunedRace();
            var was = EquestriaHelmetFit.ShiftFor(race);
            string now = $"(сейчас вправо {was.x:0.00}, вперёд {-was.y:0.00}, вверх {was.z:0.00})";
            if (args == null || args.Count < 3
                || !float.TryParse(args[0], out float right) || !float.TryParse(args[1], out float forward)
                || !float.TryParse(args[2], out float up)
                || Math.Abs(right) > 1f || Math.Abs(forward) > 1f || Math.Abs(up) > 1f)
            {
                return "Укажите три числа в метрах: вправо, вперёд и вверх, например "
                    + $"equestria.helmet_offset 0.02 0 0.03 {now}";
            }
            EquestriaHelmetFit.SetShift(race, right, forward, up);
            return $"Сдвиг шлема у расы «{race}»: вправо {right:0.00}, вперёд {forward:0.00}, вверх {up:0.00}. "
                + "Сдвиг применяется сразу, в окне снаряжения — на следующем кадре.";
        }

        // equestria.helmet_scale <number> | <side> <forward> <up>: helmet size on the fly
        [CommandLineFunctionality.CommandLineArgumentFunction("helmet_scale", "equestria")]
        public static string SetScale(List<string> args)
        {
            string race = TunedRace();
            var was = EquestriaHelmetFit.ScaleFor(race);
            string now = $"(сейчас {was.x:0.00} {was.y:0.00} {was.z:0.00})";
            var numbers = new List<float>();
            foreach (var arg in args ?? new List<string>())
            {
                if (float.TryParse(arg, out float value) && value > 0.1f && value <= 6f)
                {
                    numbers.Add(value);
                }
            }
            // one number: equal on all axes; three: per axis separately
            if (numbers.Count != 1 && numbers.Count != 3)
            {
                return "Укажите один множитель или три — вбок, вперёд и вверх, например "
                    + $"equestria.helmet_scale 2.2 или equestria.helmet_scale 2.4 2.2 2 {now}";
            }
            var scale = numbers.Count == 1
                ? new Vec3(numbers[0], numbers[0], numbers[0])
                : new Vec3(numbers[0], numbers[1], numbers[2]);
            EquestriaHelmetFit.SetScale(race, scale);
            return $"Размер шлема у расы «{race}»: вбок {scale.x:0.00}, вперёд {scale.y:0.00}, "
                + $"вверх {scale.z:0.00}. Видно сразу, в окне снаряжения — на следующем кадре.";
        }
    }
}
