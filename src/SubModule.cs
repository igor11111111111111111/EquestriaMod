using System;
using TaleWorlds.Localization;
using System.Reflection;
using TaleWorlds.CampaignSystem;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.MountAndBlade;
// System.Reflection also declares a Module type, so the game's one needs its own alias.
using MBModule = TaleWorlds.MountAndBlade.Module;

namespace EquestriaMod
{
    // The mod's entry point. The class name is given in SubModule.xml (SubModuleClassType).
    public class SubModule : MBSubModuleBase
    {
        // The mod's earliest call: here we install exception logging to catch everything that follows.
        protected override void OnSubModuleLoad()
        {
            base.OnSubModuleLoad();
            EquestriaCrashLog.Install();
            // Our override Module/GUI/Prefabs/FaceGen/FaceGenHair.xml (stripes on ponies: a toggle
            // next to the hairstyle) is not read by the game on its own: by default it takes the already compiled
            // "generated" version of the native prefabs instead of the live XML (checked in game 29.09.2026:
            // editing the file had no effect even after a full restart; only the console
            // command ui.use_generated_prefabs 0 helped). This is a global switch for the WHOLE game
            // UI, not just our file; sadly it cannot be turned off selectively for one prefab.
            TaleWorlds.Engine.GauntletUI.UIConfig.DoNotUseGeneratedPrefabs = true;
            EquestriaPatches.Apply();
        }

        // Called once, when the main menu is shown.
        protected override void OnBeforeInitialModuleScreenSetAsRoot()
        {
            base.OnBeforeInitialModuleScreenSetAsRoot();
            EquestriaCrashLog.Note("главное меню");
            EquestriaPatches.ApplyLate();
            EquestriaCrashLog.Try("пропуск заставки", SkipSplashVideo);
            InformationManager.DisplayMessage(
                new InformationMessage(new TextObject("{=eq_note_loaded}Equestria mod loaded!").ToString(), Colors.Magenta));
            EquestriaCrashLog.Try("кнопка быстрого теста", EquestriaQuickStart.AddMenuOption);
            EquestriaCrashLog.Try("сюжетная кампания", EquestriaStoryMode.DisableStoryCampaign);
            EquestriaQuickStart.CheckAutoStartRequest();
            EquestriaShowcase.CheckRequest();
            EquestriaHelmetTest.CheckRequest();
            EquestriaFlightTest.CheckRequest();
            EquestriaMixedBirthTest.CheckRequest();
            EquestriaHideoutTest.CheckRequest();
            EquestriaRaceParty.CheckRequest();
            EquestriaPrisonerButchery.CheckRequest();
            EquestriaLongRun.CheckRequest();
        }

        // Every frame; needed by the quick test: it waits for the right game states, first the main menu,
        // then the character creation screen, to skip it entirely.
        protected override void OnApplicationTick(float dt)
        {
            base.OnApplicationTick(dt);
            EquestriaShaderWarmup.Tick();
            EquestriaQuickStart.Tick();
            EquestriaDefaultStart.Tick();
            EquestriaShowcase.Tick();
            EquestriaHelmetTest.Tick();
            EquestriaFlightTest.Tick();
            EquestriaMixedBirthTest.Tick();
            EquestriaHideoutTest.Tick();
            EquestriaRaceParty.Tick();
            EquestriaPrisonerButchery.Tick();
            EquestriaLongRun.Tick();
            EquestriaRaceAssimilation.Tick();
            EquestriaMapPropsLod.Tick();
            EquestriaTimeSpeed.Tick();
        }

        // Skip the TaleWorlds splash video at game start; it only wastes time on every test.
        // Module.SetInitialModuleScreenAsRoot calls our OnBeforeInitialModuleScreenSetAsRoot,
        // and right after it checks the private field _splashScreenPlayed. We set it in advance,
        // and the video does not start. The game files are not touched.
        private static void SkipSplashVideo()
        {
            try
            {
                FieldInfo field = typeof(MBModule).GetField(
                    "_splashScreenPlayed", BindingFlags.Instance | BindingFlags.NonPublic);
                if (field != null && MBModule.CurrentModule != null)
                {
                    field.SetValue(MBModule.CurrentModule, true);
                }
            }
            catch (Exception)
            {
                // If a new game version renames the field, we simply watch the splash video.
            }
        }

        // Every scene (battle, town, tournament): attach our mission behaviours.
        public override void OnMissionBehaviorInitialize(Mission mission)
        {
            base.OnMissionBehaviorInitialize(mission);
            mission.AddMissionBehavior(new EquestriaOrderVoice());
            // Female voice in battle for all peoples except griffons and hippogriffs (see the class itself)
            mission.AddMissionBehavior(new EquestriaBattleVoice());
            mission.AddMissionBehavior(new EquestriaBodyParts());
            // Magic: input (holding Q), projectile flight and damage. The wheel is drawn by EquestriaSpellWheelView,
            // which attaches itself via the [DefaultView] attribute.
            mission.AddMissionBehavior(new EquestriaSpellMission());
            // Severing limbs/head: a port of the DismembermentPlus mechanics (see the class itself)
            mission.AddMissionBehavior(new EquestriaDismemberment());
            // Flight scroll in the horse slot: keeps the lower body in the idle pose (see the class itself)
            mission.AddMissionBehavior(new EquestriaFlightScroll());
            mission.AddMissionBehavior(new EquestriaWingsTest());
        }

        // Called when a campaign starts (new or loaded): campaign behaviours are attached here.
        protected override void OnGameStart(Game game, IGameStarter gameStarter)
        {
            base.OnGameStart(game, gameStarter);
            EquestriaCrashLog.Note("OnGameStart: тип игры " + game.GameType.GetType().Name);
            // Scroll UI patches (market/inventory): only here, when GameTexts already exist (see the method)
            EquestriaCrashLog.Try("патчи UI свитка", () => EquestriaFlightScroll.ApplyCampaignUi(EquestriaPatches.Instance));
            // Hero snapshot for saving with the scroll: only here, not at mod load, otherwise
            // the action cache is built before the pony animations and everyone lies down (see EquestriaScrollSaveVisualFix)
            EquestriaCrashLog.Try("патч сохранения со свитком", () => EquestriaScrollSaveVisualFix.Apply(EquestriaPatches.Instance));
            // The "Culture" filter in the encyclopedia: otherwise Olenia (nord, is_main_culture=false) is not visible
            EquestriaCrashLog.Try("фильтр народностей энциклопедии", () => EquestriaEncyclopediaCultures.Apply(EquestriaPatches.Instance));
            if (game.GameType is Campaign && gameStarter is CampaignGameStarter campaignStarter)
            {
                campaignStarter.AddBehavior(new EquestriaCharacterCreationBehavior());
                campaignStarter.AddBehavior(new EquestriaRaceSaveBehavior());
                campaignStarter.AddBehavior(new EquestriaDiagnosticsBehavior());
                campaignStarter.AddBehavior(new EquestriaLongRunBehavior());
                campaignStarter.AddBehavior(new EquestriaRelationsBehavior());
                campaignStarter.AddBehavior(new EquestriaDiplomacyBehavior());
                campaignStarter.AddBehavior(new EquestriaGreetingsBehavior());
                // Mana: accumulates by the hour while travelling on the map, spent in battle
                campaignStarter.AddBehavior(new EquestriaManaBehavior());
                // Mercenary camps near capitals: buying mercenary company troops one at a time
                campaignStarter.AddBehavior(new EquestriaMercCampBehavior());
                // Striped/solid mane on ponies: the player's choice, stored in the save
                campaignStarter.AddBehavior(new EquestriaHairStyle());
                // Wings on/off: a temporary toggle, stored in the save
                campaignStarter.AddBehavior(new EquestriaPonyBody());
                // Race assimilation of captured settlements (a port of the DynaCulture mod)
                campaignStarter.AddBehavior(new EquestriaRaceAssimilation());
                // Cavalry without horses: any beast in the horse slot of troops and heroes → flight scroll
                campaignStarter.AddBehavior(new EquestriaFlightArmy());
                // …and they do not starve: nobody carries supplies for them (see the class itself)
                campaignStarter.AddModel(new EquestriaCampFoodModel());
                // Our own navigation model: the faces of our mesh have terrain type 0 (see the class itself).
                campaignStarter.AddModel(new EquestriaPartyNavigationModel());
                // Speed by terrain: mountains, hills, swamps and snow. Forest and desert are penalised
                // by the game itself; we do not punish a second time (see the class itself).
                campaignStarter.AddModel(new EquestriaPartySpeedModel());
                // Notable recruitment pool: the volunteer's race follows the settlement's current assimilation shares,
                // not the notable's fixed culture (see the class itself).
                campaignStarter.AddModel(new EquestriaVolunteerModel());
                EquestriaCrashLog.Log("поведения кампании подключены: создание персонажа, раса, опись, долгий прогон, отношения");
            }
        }
    }
}
