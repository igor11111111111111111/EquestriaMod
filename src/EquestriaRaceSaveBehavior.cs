using System.Collections.Generic;
using System.Linq;
using TaleWorlds.CampaignSystem;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.Localization;

namespace EquestriaMod
{
    // Saves heroes' race in the save file. In Bannerlord a character's Race property is not saved: ordinary
    // characters take their race from XML every time, and the player hero's race is reset to human after loading.
    // (The Old Realms solves the same with its own patches PreserveRace / RaceFixCampaignBehavior.)
    public class EquestriaRaceSaveBehavior : CampaignBehaviorBase
    {
        // hero id -> race name from skins.xml; only non-human races are stored
        private Dictionary<string, string> _heroRaces = new Dictionary<string, string>();

        public override void RegisterEvents()
        {
            CampaignEvents.OnGameLoadedEvent.AddNonSerializedListener(this,
                _ => EquestriaCrashLog.Try("восстановление рас после загрузки", RestoreRaces));
            // both in a new game and after loading: a pony with a free head slot gets a mane (see EquestriaMane)
            CampaignEvents.OnSessionLaunchedEvent.AddNonSerializedListener(this, _ =>
                EquestriaCrashLog.Try("выдача гривы и хвоста", () =>
                {
                    int worn = EquestriaMane.EnsureForPonies();
                    EquestriaCrashLog.Log($"грива/хвост надеты в {worn} слот(ов)");
                }));
        }

        public override void SyncData(IDataStore dataStore)
        {
            if (dataStore.IsSaving)
            {
                CollectRaces();
            }
            dataStore.SyncData("eq_hero_races", ref _heroRaces);
            if (_heroRaces == null)
            {
                _heroRaces = new Dictionary<string, string>();
            }
        }

        private void CollectRaces()
        {
            var names = FaceGen.GetRaceNames();
            _heroRaces = Hero.AllAliveHeroes.Concat(Hero.DeadOrDisabledHeroes)
                .Where(h => h.CharacterObject != null && h.CharacterObject.Race > 0 && h.CharacterObject.Race < names.Length)
                .GroupBy(h => h.StringId)
                .ToDictionary(g => g.Key, g => names[g.First().CharacterObject.Race]);
        }

        private void RestoreRaces()
        {
            var restored = 0;
            foreach (var hero in Hero.AllAliveHeroes.Concat(Hero.DeadOrDisabledHeroes))
            {
                if (hero.CharacterObject != null && _heroRaces.TryGetValue(hero.StringId, out var raceName))
                {
                    SetRace(hero, FaceGen.GetRaceOrDefault(raceName));
                    restored++;
                }
            }
            EquestriaMane.EnsureForPonies();
            EquestriaCrashLog.Log($"раса восстановлена у {restored} героев (в сейве записей {_heroRaces.Count})");
            if (restored > 0)
            {
                var note = new TextObject("{=eq_race_restored_note}Equestria: restored race for {COUNT} hero(es)");
                note.SetTextVariable("COUNT", restored);
                InformationManager.DisplayMessage(new InformationMessage(note.ToString()));
            }
        }

        public static void SetRace(Hero hero, int race)
        {
            var character = hero.CharacterObject;
            if (character.Race == race)
            {
                return;
            }
            if (hero == Hero.MainHero)
            {
                character.UpdatePlayerCharacterBodyProperties(character.GetBodyProperties(null), race, character.IsFemale);
            }
            else
            {
                character.Race = race;
            }
        }

        // Console (Alt+~): equestria.set_player_race pony   /   equestria.set_player_race human
        [CommandLineFunctionality.CommandLineArgumentFunction("set_player_race", "equestria")]
        public static string SetPlayerRaceCommand(List<string> args)
        {
            if (Campaign.Current == null || Hero.MainHero == null)
            {
                return "Available only in a campaign.";
            }
            var names = FaceGen.GetRaceNames();
            if (args.Count != 1 || !names.Contains(args[0]))
            {
                return "Format: equestria.set_player_race <race>. Races: " + string.Join(", ", names);
            }
            SetRace(Hero.MainHero, FaceGen.GetRaceOrDefault(args[0]));
            return $"Player race set to {args[0]}. Reopen the inventory or party screen to see the change.";
        }
    }
}
