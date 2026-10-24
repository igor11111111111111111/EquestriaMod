using System;
using System.Collections.Generic;
using System.Linq;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.GameState;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Fitting room for the flight scroll (a replacement for riding horses: a beast riding a beast is absurd, see
    // tools/make_items.py: eq_flight_scroll_50). The same trick as EquestriaHelmetTest: wait for the map,
    // give and equip the item ourselves, without a single click. /eqflight from the console/run.ps1 -Flight.
    public static class EquestriaFlightTest
    {
        private const string Arg = "/eqflight";
        private static bool _requested;
        private static bool _done;
        private static DateTime _mapSeenAt = DateTime.MinValue;

        public static void CheckRequest()
        {
            if (Environment.GetCommandLineArgs().Any(a => string.Equals(a, Arg, StringComparison.OrdinalIgnoreCase)))
            {
                _requested = true;
                EquestriaCrashLog.Log("свиток полёта: запрошен по ключу");
            }
        }

        public static void Tick()
        {
            if (!_requested || _done)
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
            EquestriaCrashLog.Try("свиток полёта по ключу", () => EquestriaCrashLog.Log(Run(null)));
            // Straight into battle: 100 vs 100 former cavalrymen (horses of all troops are replaced with scrolls,
            // EquestriaFlightArmy), to watch flight en masse, not on a single hero.
            EquestriaCrashLog.Try("свиток полёта: бой по ключу", () => EquestriaCrashLog.Log(
                EquestriaHelmetTest.BigBattle(new List<string> { BattleSide.ToString(), BattleTroop })));
        }

        private const int BattleSide = 100;
        private const string BattleTroop = "battanian_oathsworn"; // Guard of Deer Grove: deer (on foot, no scroll; Battanian branch); changelings: aserai_faris, hippogriffs: eq_hg_sturgian_horse_raider, griffons: khuzait_heavy_lancer, dragons: vlandian_knight

        // equestria.flight_test: give and equip the flight scroll on the hero
        [CommandLineFunctionality.CommandLineArgumentFunction("flight_test", "equestria")]
        public static string Run(List<string> args)
        {
            if (Campaign.Current == null || Hero.MainHero == null)
            {
                return "Нужна начатая кампания.";
            }
            var scroll = MBObjectManager.Instance.GetObject<ItemObject>("eq_flight_scroll_50");
            if (scroll == null)
            {
                return "Нет предмета eq_flight_scroll_50 — пересобери equestria_items.xml (tools/make_items.py).";
            }
            var party = PartyBase.MainParty;
            if (party.ItemRoster.GetItemNumber(scroll) == 0)
            {
                party.ItemRoster.AddToCounts(scroll, 1);
            }
            Hero.MainHero.BattleEquipment[EquipmentIndex.Horse] = new EquipmentElement(scroll);
            Hero.MainHero.CivilianEquipment[EquipmentIndex.Horse] = new EquipmentElement(scroll);
            string report = "Свиток полёта выдан и надет в слот коня.";
            EquestriaCrashLog.Log("свиток полёта: " + report);
            return report;
        }
    }
}
