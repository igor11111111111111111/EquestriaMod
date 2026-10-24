using System;
using System.Linq;
using SandBox;
using TaleWorlds.SaveSystem.Load;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.CharacterCreationContent;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.Localization;
using TaleWorlds.MountAndBlade;

namespace EquestriaMod
{
    // A main menu button: starts a sandbox right away with a ready character, skipping the choice of
    // background, appearance and difficulty. Needed for quick mod checks — every test needs a new campaign.
    public static class EquestriaQuickStart
    {
        private const string OptionId = "EquestriaQuickStart";

        // Command line switch: with it the game presses the quick test button in the main menu by itself.
        private const string AutoStartFlag = "/eqautostart";

        // Switch for .\run.ps1 -DefaultStart (EquestriaDefaultStart) — the same auto-started new
        // campaign, but WITHOUT skipping the character creation wizard: the player goes through it fully
        // (choosing the race there via the ready culture list, EquestriaRaceSelector), and afterwards our
        // own choice of game start (mercenary/vassal/king).
        private const string DefaultStartFlag = "/eqdefaultstart";

        // The flag lives across scenes: it makes character creation finish automatically.
        public static bool SkipCharacterCreation;

        private static bool _autoStartPending;
        private static bool _defaultStartPending;

        // The intro video is cut once per campaign launch.
        private static bool _introSkipped;

        // Command line switch for the build with the editor (Modding Kit): open the editor right away,
        // without pressing "Editor" in the main menu. Launch — tools\editor.ps1.
        private const string EditorFlag = "/eqeditor";

        private static bool _editorPending;

        // Called when the main menu is shown: check whether a no-click launch was requested.
        public static void CheckAutoStartRequest()
        {
            foreach (string arg in Environment.GetCommandLineArgs())
            {
                if (string.Equals(arg, AutoStartFlag, StringComparison.OrdinalIgnoreCase))
                {
                    _autoStartPending = true;
                }
                if (string.Equals(arg, DefaultStartFlag, StringComparison.OrdinalIgnoreCase))
                {
                    _defaultStartPending = true;
                }
                if (string.Equals(arg, EditorFlag, StringComparison.OrdinalIgnoreCase))
                {
                    _editorPending = true;
                }
            }
        }

        // The main menu item «Editor» is added by Native (ViewSubModule) — and only in the build
        // with the editor, where Utilities.EditModeEnabled. We press it by name.
        private static void OpenEditor()
        {
            EquestriaCrashLog.Try("открытие редактора", () =>
            {
                if (Module.CurrentModule.GetInitialStateOptionWithId("Editor") == null)
                {
                    EquestriaCrashLog.Warn("редактор: пункта Editor в меню нет — это не сборка Modding Kit");
                    return;
                }
                EquestriaCrashLog.Note("редактор: пункт меню нажат");
                Module.CurrentModule.ExecuteInitialStateOptionWithId("Editor");
            });
        }

        // Both quick start steps are done per frame, not right on the event: both the menu button and
        // skipping character creation must run when the required game state is already active.
        public static void Tick()
        {
            if (GameStateManager.Current == null)
            {
                return;
            }
            var state = GameStateManager.Current.ActiveState;

            if (_editorPending && state is InitialState)
            {
                _editorPending = false;
                OpenEditor();
                return;
            }

            if (_autoStartPending && state is InitialState)
            {
                _autoStartPending = false;
                EquestriaCrashLog.Note("быстрый старт: создаём кампанию");
                StartQuickCampaign();
                return;
            }

            if (_defaultStartPending && state is InitialState)
            {
                _defaultStartPending = false;
                EquestriaCrashLog.Note("старт по умолчанию: создаём кампанию (полный мастер)");
                EquestriaDefaultStart.Begin();
                StartDefaultCampaign();
                return;
            }

            // Before character creation the game plays the intro video about Calradia. It runs as a
            // separate state, on top of which the culture choice opens later. We cut it the same way
            // the player's skip button does. With -DefaultStart the character creation wizard is NOT
            // skipped (SkipCharacterCreation=false), but the video itself is still not needed — at the
            // user's request 08.10.2026.
            if ((SkipCharacterCreation || EquestriaDefaultStart.Active) && !_introSkipped && state is VideoPlaybackState video)
            {
                _introSkipped = true;
                EquestriaCrashLog.Note("быстрый старт: обрываем вступительный ролик");
                EquestriaCrashLog.Try("пропуск вступительного ролика", video.OnVideoFinished);
                return;
            }

            if (SkipCharacterCreation && state is CharacterCreationState creation)
            {
                SkipCharacterCreation = false;
                SkipAllStages(creation);
            }
        }

        // Skipping all hero creation screens: culture, parents, childhood, youth and so on.
        //
        // This used to be done on the "character creation started" event, but then the state is not
        // active yet: the game finishes filling it and opens the first screen itself on top of our
        // finalisation. Here we wait for the frame where the creation screen is already active and close
        // it entirely — FinalizeCharacterCreationState switches the game to the map right away.
        private static void SkipAllStages(CharacterCreationState creation)
        {
            EquestriaCrashLog.Try("быстрый старт: пропуск создания персонажа", () =>
            {
                creation.FinalizeCharacterCreationState();
                GiveStartingPoints();
                MakePlayerPony();
                GiveCheapHelmet();
                InformationManager.DisplayMessage(
                    new InformationMessage(new TextObject("{=eq_note_quick_start}Equestria: quick start, default character").ToString(), Colors.Magenta));
            });
        }

        // The stages are skipped, and with them the choice of the "Pony" culture that normally makes
        // the hero a pony. So we assign the race and mane ourselves — otherwise the quick test would start as a human.
        private static void MakePlayerPony()
        {
            if (Hero.MainHero == null)
            {
                EquestriaCrashLog.Warn("быстрый старт: главного героя нет, раса не изменена");
                return;
            }
            // FaceGen is declared both in TaleWorlds.Core and in TaleWorlds.MountAndBlade — we need the first.
            int race = TaleWorlds.Core.FaceGen.GetRaceOrDefault(EquestriaMane.RaceId);
            EquestriaRaceSaveBehavior.SetRace(Hero.MainHero, race);
            EquestriaMane.EnsureForPonies();
            EquestriaCrashLog.Log($"быстрый старт: игрок стал пони (раса {race})");
        }

        // Any cheapest helmet in the game — handy for checking the helmet fit for the race
        // (EquestriaHelmetFit) right after the quick start, without going to the equipment screen.
        private static void GiveCheapHelmet()
        {
            var hero = Hero.MainHero;
            if (hero == null)
            {
                return;
            }
            var helmet = Game.Current.ObjectManager.GetObjectTypeList<ItemObject>()
                .Where(i => i.ItemType == ItemObject.ItemTypeEnum.HeadArmor && i.Value > 0)
                .OrderBy(i => i.Value)
                .FirstOrDefault();
            if (helmet == null)
            {
                EquestriaCrashLog.Warn("быстрый старт: дешёвый шлем не найден");
                return;
            }
            hero.BattleEquipment[EquipmentIndex.Head] = new EquipmentElement(helmet);
            EquestriaCrashLog.Log($"быстрый старт: надет шлем {helmet.StringId} (цена {helmet.Value})");
        }

        // Character creation is skipped, and with it the skill choice: without this the hero has not a
        // single focus or attribute point, and the "Skills" tab has nothing to start from.
        private const int StartFocusPoints = 10;
        private const int StartAttributePoints = 10;

        private static void GiveStartingPoints()
        {
            var developer = Hero.MainHero?.HeroDeveloper;
            if (developer == null)
            {
                EquestriaCrashLog.Warn("быстрый старт: у героя нет HeroDeveloper — очки не выданы");
                return;
            }
            developer.UnspentFocusPoints += StartFocusPoints;
            developer.UnspentAttributePoints += StartAttributePoints;
            EquestriaCrashLog.Log($"быстрый старт: выдано очков внимания {StartFocusPoints}, "
                + $"характеристик {StartAttributePoints} (теперь {developer.UnspentFocusPoints}/{developer.UnspentAttributePoints})");
        }

        // The "Start the adventure" button (10.10.2026): the same launch as
        // .\run.ps1 -DefaultStart — the full character creation wizard with race choice and then the game
        // start choice (beggar / mercenary / vassal / ruler). The quick test with a ready character stays
        // behind the /eqautostart switch (run.ps1 -QuickStart and other test launches).
        public static void AddMenuOption()
        {
            var option = new InitialStateOption(
                OptionId,
                new TextObject("{=eq_menu_start}Start the adventure"),
                2,
                StartAdventureFromMenu,
                () => (false, null),
                null,
                () => false);
            Module.CurrentModule.AddInitialStateOption(option);
        }

        private static void StartAdventureFromMenu()
        {
            EquestriaCrashLog.Note("главное меню: «Начать приключение» — полный мастер (как -DefaultStart)");
            EquestriaDefaultStart.Begin();
            StartDefaultCampaign();
        }

        // internal: the race review (EquestriaRaceParty) starts its campaign with this same button
        internal static void StartQuickCampaign()
        {
            SkipCharacterCreation = true;
            _introSkipped = false;
            // The constructor with LoadResult loads a save (the game crashed at "Initializing saved game").
            // A new game needs the constructor that creates the campaign itself.
            var manager = new SandBoxGameManager(
                new SandBoxGameManager.CampaignCreatorDelegate(() => new Campaign(CampaignGameMode.Campaign)));
            MBGameManager.StartNewGame(manager);
        }

        // The same new campaign, but WITHOUT skipping the character creation wizard — used by
        // EquestriaDefaultStart (.\run.ps1 -DefaultStart): the player goes through the whole wizard
        // (the culture choice is there too, EquestriaRaceSelector) instead of getting a ready pony
        // automatically. The "Culture" stage (the first) is skipped by EquestriaDefaultStart
        // itself, directly through the wizard data — see EquestriaDefaultStart.TrySkipCultureStage.
        internal static void StartDefaultCampaign()
        {
            SkipCharacterCreation = false;
            _introSkipped = false;
            var manager = new SandBoxGameManager(
                new SandBoxGameManager.CampaignCreatorDelegate(() => new Campaign(CampaignGameMode.Campaign)));
            MBGameManager.StartNewGame(manager);
        }

        // A log mark: shows whether the game reached the character creation screen.
        public static void NoteCharacterCreationStarted()
        {
            EquestriaCrashLog.Note("создание персонажа началось, пропуск="
                + SkipCharacterCreation);
        }
    }
}
