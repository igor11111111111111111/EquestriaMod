using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.CharacterCreationContent;
using TaleWorlds.Core;

namespace EquestriaMod
{
    // Makes the player hero a pony, whichever realm they pick during character creation.
    //
    // Previously a separate "Pony" culture was added here: the culture list on the selection screen
    // is hard-coded to six entries, and our own culture did not get into it without this handler.
    // Now the Equus cultures have taken the vanilla ids (Equestria = empire, Crystal
    // Empire = vlandia and so on), so the selection screen shows our realms by itself, and the story
    // stages — family, childhood, youth — run on vanilla data without substitutions.
    //
    // One task is left: the race. In XML it is set on characters, but the player hero is created in code.
    public class EquestriaCharacterCreationBehavior : CampaignBehaviorBase, ICharacterCreationContentHandler
    {
        public const string RaceId = "pony";

        // The vanilla handler is registered with priority 800; ours is called after it
        private const int HandlerPriority = 1000;

        private CharacterCreationManager _manager;

        public override void RegisterEvents()
        {
            CampaignEvents.OnCharacterCreationInitializedEvent.AddNonSerializedListener(this, OnCharacterCreationInitialized);
        }

        public override void SyncData(IDataStore dataStore)
        {
        }

        private void OnCharacterCreationInitialized(CharacterCreationManager manager)
        {
            _manager = manager;
            EquestriaCultureArt.Load();     // culture cards and backgrounds — before the screen is shown
            EquestriaCultureArt.ApplyTexts();
            EquestriaQuickStart.NoteCharacterCreationStarted();
            manager.RegisterCharacterCreationContentHandler(this, HandlerPriority);
            // Skipping stages in a quick test is done by EquestriaQuickStart itself, frame by frame:
            // here the character creation state is not active yet, and it is too early to finish it.
        }

        void ICharacterCreationContentHandler.InitializeContent(CharacterCreationManager manager)
        {
        }

        void ICharacterCreationContentHandler.AfterInitializeContent(CharacterCreationManager manager)
        {
        }

        void ICharacterCreationContentHandler.OnStageCompleted(CharacterCreationStageBase stage)
        {
            if (!(stage is CharacterCreationCultureStage) || _manager == null)
            {
                return;
            }
            var culture = _manager.CharacterCreationContent.SelectedCulture;
            EquestriaCrashLog.Log("выбрана держава " + (culture != null ? culture.StringId : "НЕТ")
                + " — делаем героя пони");
            SetPlayerRace(FaceGen.GetRaceOrDefault(RaceId));
        }

        void ICharacterCreationContentHandler.OnCharacterCreationFinalize(CharacterCreationManager manager)
        {
            // the pony hero gets a mane right away if the helmet slot is free
            EquestriaMane.EnsureForPonies();
            // the backstory equipment puts a pack animal into the horse slot — for us that is a cart,
            // it belongs in the baggage train
            EquestriaCrashLog.Try("конское снаряжение игрока", EquestriaFlightArmy.StripPlayerHorseGear);
            EquestriaCultureArt.Unload();
            // Fires both for the full wizard and for a skipped one (SkipCharacterCreation) —
            // EquestriaDefaultStart itself decides whether anything needs doing (the Active flag).
            EquestriaDefaultStart.OnCharacterCreationFinished();
        }

        private static void SetPlayerRace(int race)
        {
            var player = CharacterObject.PlayerCharacter;
            if (player.Race != race)
            {
                player.UpdatePlayerCharacterBodyProperties(player.GetBodyProperties(null), race, player.IsFemale);
            }
        }
    }
}
