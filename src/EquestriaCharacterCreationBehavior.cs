using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.CharacterCreationContent;
using TaleWorlds.Core;

namespace EquestriaMod
{
    // Делает героя игрока пони, какую бы державу он ни выбрал при создании персонажа.
    //
    // Раньше здесь добавлялась отдельная культура «Пони»: список культур на экране выбора жёстко
    // прописан на шесть штук, и своя культура в него не попадала без этого обработчика.
    // Теперь культуры Equus заняли ванильные идентификаторы (Эквестрия = empire, Кристальная
    // Империя = vlandia и так далее), поэтому экран выбора показывает наши державы сам, а сюжетные
    // этапы — семья, детство, юность — работают на ванильных данных без подмен.
    //
    // Осталась одна задача: раса. В XML её задают персонажам, а герой игрока создаётся в коде.
    public class EquestriaCharacterCreationBehavior : CampaignBehaviorBase, ICharacterCreationContentHandler
    {
        public const string RaceId = "pony";

        // Ванильный обработчик зарегистрирован с приоритетом 800; наш вызывается после него
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
            EquestriaCultureArt.Load();     // карточки и фоны народностей — до показа экрана
            EquestriaCultureArt.ApplyTexts();
            EquestriaQuickStart.NoteCharacterCreationStarted();
            manager.RegisterCharacterCreationContentHandler(this, HandlerPriority);
            // Пропуск этапов при быстром тесте делает сам EquestriaQuickStart по кадрам:
            // здесь состояние создания персонажа ещё не активно, и завершать его рано.
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
            // герою-пони сразу надевается грива, если слот шлема свободен
            EquestriaMane.EnsureForPonies();
            // снаряжение предыстории кладёт в слот коня вьючного — у нас это повозка, ей место в обозе
            EquestriaCrashLog.Try("конское снаряжение игрока", EquestriaFlightArmy.StripPlayerHorseGear);
            EquestriaCultureArt.Unload();
            // Срабатывает и у полного мастера, и у пропущенного (SkipCharacterCreation) — сам
            // EquestriaDefaultStart решает, нужно ли что-то делать (флаг Active).
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
