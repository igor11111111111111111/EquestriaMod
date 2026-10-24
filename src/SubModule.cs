using System;
using TaleWorlds.Localization;
using System.Reflection;
using TaleWorlds.CampaignSystem;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.MountAndBlade;
// System.Reflection тоже объявляет тип Module, поэтому для игрового нужен свой псевдоним.
using MBModule = TaleWorlds.MountAndBlade.Module;

namespace EquestriaMod
{
    // Точка входа мода. Имя класса указано в SubModule.xml (SubModuleClassType).
    public class SubModule : MBSubModuleBase
    {
        // Самый ранний вызов мода: здесь ставим запись исключений, чтобы поймать всё дальнейшее.
        protected override void OnSubModuleLoad()
        {
            base.OnSubModuleLoad();
            EquestriaCrashLog.Install();
            // Наш override Module/GUI/Prefabs/FaceGen/FaceGenHair.xml (полосы у пони — переключатель
            // рядом с причёской) игра сама не читает: по умолчанию она берёт уже вкомпилированную
            // «сгенерированную» версию родных префабов вместо живого XML (проверено в игре 29.09.2026:
            // правка файла не действовала даже после полного перезапуска, помогла только консольная
            // команда ui.use_generated_prefabs 0). Это глобальный переключатель на ВЕСЬ интерфейс
            // игры, не только на наш файл — жаль, точечно выключить для одного префаба нельзя.
            TaleWorlds.Engine.GauntletUI.UIConfig.DoNotUseGeneratedPrefabs = true;
            EquestriaPatches.Apply();
        }

        // Вызывается один раз, когда показывается главное меню.
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

        // Каждый кадр; нужен быстрому тесту: он ждёт нужных состояний игры — сначала главного меню,
        // затем экрана создания персонажа, чтобы пропустить его целиком.
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

        // Пропуск заставки TaleWorlds при запуске игры — она только тратит время при каждом тесте.
        // Module.SetInitialModuleScreenAsRoot вызывает наш OnBeforeInitialModuleScreenSetAsRoot,
        // а сразу после него проверяет приватное поле _splashScreenPlayed. Ставим его заранее,
        // и ролик не запускается. Файлы игры при этом не трогаем.
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
                // Если в новой версии игры поле переименуют — просто посмотрим заставку.
            }
        }

        // Каждая сцена (бой, город, турнир): подключаем свои поведения миссии.
        public override void OnMissionBehaviorInitialize(Mission mission)
        {
            base.OnMissionBehaviorInitialize(mission);
            mission.AddMissionBehavior(new EquestriaOrderVoice());
            // Женский голос в бою всем народам, кроме грифонов и гиппогрифов (см. сам класс)
            mission.AddMissionBehavior(new EquestriaBattleVoice());
            mission.AddMissionBehavior(new EquestriaBodyParts());
            // Магия: ввод (удержание Q), полёт снарядов и урон. Колесо рисует EquestriaSpellWheelView,
            // он подключается сам по метке [DefaultView].
            mission.AddMissionBehavior(new EquestriaSpellMission());
            // Отрубание конечностей/головы — перенос механики DismembermentPlus (см. сам класс)
            mission.AddMissionBehavior(new EquestriaDismemberment());
            // Свиток полёта в слоте коня: держит нижнюю часть тела в позе покоя (см. сам класс)
            mission.AddMissionBehavior(new EquestriaFlightScroll());
            mission.AddMissionBehavior(new EquestriaWingsTest());
        }

        // Вызывается при запуске кампании (новой или загруженной): здесь подключаются поведения кампании.
        protected override void OnGameStart(Game game, IGameStarter gameStarter)
        {
            base.OnGameStart(game, gameStarter);
            EquestriaCrashLog.Note("OnGameStart: тип игры " + game.GameType.GetType().Name);
            // UI-патчи свитка (рынок/инвентарь) — только здесь, когда GameTexts уже есть (см. метод)
            EquestriaCrashLog.Try("патчи UI свитка", () => EquestriaFlightScroll.ApplyCampaignUi(EquestriaPatches.Instance));
            // Снимок героя для сохранения со свитком — только здесь, не при загрузке мода: иначе
            // кэш действий строится раньше анимаций пони и все лежат (см. EquestriaScrollSaveVisualFix)
            EquestriaCrashLog.Try("патч сохранения со свитком", () => EquestriaScrollSaveVisualFix.Apply(EquestriaPatches.Instance));
            // Фильтр «Народность» в энциклопедии: Оления (nord, is_main_culture=false) иначе не видна
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
                // Мана: копится по часам в пути по карте, тратится в бою
                campaignStarter.AddBehavior(new EquestriaManaBehavior());
                // Лагеря наёмников у столиц: поштучная покупка войск наёмных рот
                campaignStarter.AddBehavior(new EquestriaMercCampBehavior());
                // Полосатая/сплошная грива у пони — выбор игрока, хранится в сейве
                campaignStarter.AddBehavior(new EquestriaHairStyle());
                // Крылья вкл/выкл — временный переключатель, хранится в сейве
                campaignStarter.AddBehavior(new EquestriaPonyBody());
                // Ассимиляция расы захваченных поселений (перенос мода DynaCulture)
                campaignStarter.AddBehavior(new EquestriaRaceAssimilation());
                // Конница без коней: любой зверь в слоте коня у войск и героев → свиток полёта
                campaignStarter.AddBehavior(new EquestriaFlightArmy());
                // …и они не голодают: припасы им никто не возит (см. сам класс)
                campaignStarter.AddModel(new EquestriaCampFoodModel());
                // Своя модель проходимости: у граней нашей сетки тип местности 0 (см. сам класс).
                campaignStarter.AddModel(new EquestriaPartyNavigationModel());
                // Скорость по местности: горы, холмы, болота и снег. Лес и пустыню штрафует
                // сама игра, второй раз не наказываем (см. сам класс).
                campaignStarter.AddModel(new EquestriaPartySpeedModel());
                // Резерв найма нотаблей — раса добровольца по текущим долям ассимиляции поселения,
                // не по фиксированной культуре нотабля (см. сам класс).
                campaignStarter.AddModel(new EquestriaVolunteerModel());
                EquestriaCrashLog.Log("поведения кампании подключены: создание персонажа, раса, опись, долгий прогон, отношения");
            }
        }
    }
}
