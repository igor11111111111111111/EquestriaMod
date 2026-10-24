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
    // Кнопка в главном меню: сразу начинает песочницу с готовым персонажем, минуя выбор предыстории,
    // внешности и сложности. Нужна для быстрой проверки мода — каждый тест требует новой кампании.
    public static class EquestriaQuickStart
    {
        private const string OptionId = "EquestriaQuickStart";

        // Ключ командной строки: с ним игра сама нажимает кнопку быстрого теста в главном меню.
        private const string AutoStartFlag = "/eqautostart";

        // Ключ для .\run.ps1 -DefaultStart (EquestriaDefaultStart) — та же автозапускаемая новая
        // кампания, но БЕЗ пропуска мастера создания персонажа: игрок проходит его целиком (там же
        // выбирает расу через готовый список народностей, EquestriaRaceSelector), а после — свой
        // выбор начала игры (наёмник/вассал/король).
        private const string DefaultStartFlag = "/eqdefaultstart";

        // Флаг живёт между сценами: по нему создание персонажа завершается автоматически.
        public static bool SkipCharacterCreation;

        private static bool _autoStartPending;
        private static bool _defaultStartPending;

        // Вступительный ролик обрываем один раз за запуск кампании.
        private static bool _introSkipped;

        // Ключ командной строки для сборки с редактором (Modding Kit): сразу открыть редактор,
        // не нажимая «Редактор» в главном меню. Запуск — tools\editor.ps1.
        private const string EditorFlag = "/eqeditor";

        private static bool _editorPending;

        // Вызывается при показе главного меню: смотрим, просили ли запуск без единого клика.
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

        // Пункт «Editor» главного меню добавляет Native (ViewSubModule) — и только в сборке
        // с редактором, где Utilities.EditModeEnabled. Нажимаем его по имени.
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

        // Оба шага быстрого старта делаются по кадрам, а не сразу по событию: и кнопку в меню, и
        // пропуск создания персонажа нужно выполнять, когда нужное состояние игры уже стало активным.
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

            // Перед созданием персонажа игра крутит вступительный ролик про Кальрадию. Он идёт
            // отдельным состоянием, поверх которого потом открывается выбор народности. Обрываем
            // его так же, как это делает кнопка пропуска у игрока. При -DefaultStart мастер
            // создания персонажа НЕ пропускается (SkipCharacterCreation=false), но сам ролик всё
            // равно не нужен — по просьбе пользователя 08.10.2026.
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

        // Пропуск всех экранов создания героя: народность, родители, детство, юность и прочее.
        //
        // Раньше это делалось по событию «создание персонажа началось», но тогда состояние ещё не
        // активно: игра дозаполняет его и сама открывает первый экран поверх нашего завершения.
        // Здесь мы дожидаемся кадра, где экран создания уже активен, и закрываем его целиком —
        // FinalizeCharacterCreationState сразу переключает игру на карту.
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

        // Этапы пропущены, а вместе с ними и выбор культуры «Пони», который обычно делает героя пони.
        // Поэтому расу и гриву выдаём сами — иначе быстрый тест начинался бы за человека.
        private static void MakePlayerPony()
        {
            if (Hero.MainHero == null)
            {
                EquestriaCrashLog.Warn("быстрый старт: главного героя нет, раса не изменена");
                return;
            }
            // FaceGen объявлен и в TaleWorlds.Core, и в TaleWorlds.MountAndBlade — нужен первый.
            int race = TaleWorlds.Core.FaceGen.GetRaceOrDefault(EquestriaMane.RaceId);
            EquestriaRaceSaveBehavior.SetRace(Hero.MainHero, race);
            EquestriaMane.EnsureForPonies();
            EquestriaCrashLog.Log($"быстрый старт: игрок стал пони (раса {race})");
        }

        // Любой самый дешёвый шлем из игры — пригодится проверять подгонку шлема под расу
        // (EquestriaHelmetFit) сразу после быстрого старта, без похода в снаряжение.
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

        // Создание персонажа пропущено, а вместе с ним и выбор навыков: без этого у героя нет ни
        // одного очка внимания и характеристик, и вкладку «Навыки» не с чего начинать.
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

        // Кнопка «Начать приключение» (10.10.2026): тот же запуск, что .\run.ps1 -DefaultStart —
        // полный мастер создания персонажа с выбором расы и затем выбор начала игры (нищий /
        // наёмник / вассал / правитель). Быстрый тест с готовым персонажем остался за ключом
        // /eqautostart (run.ps1 -QuickStart и прочие тестовые запуски).
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

        // internal: этой же кнопкой начинает кампанию смотр рас (EquestriaRaceParty)
        internal static void StartQuickCampaign()
        {
            SkipCharacterCreation = true;
            _introSkipped = false;
            // Конструктор с LoadResult — это загрузка сохранения (игра падала на "Initializing saved game").
            // Для новой игры нужен конструктор, который сам создаёт кампанию.
            var manager = new SandBoxGameManager(
                new SandBoxGameManager.CampaignCreatorDelegate(() => new Campaign(CampaignGameMode.Campaign)));
            MBGameManager.StartNewGame(manager);
        }

        // Та же новая кампания, но БЕЗ пропуска мастера создания персонажа — используется
        // EquestriaDefaultStart (.\run.ps1 -DefaultStart): игрок проходит весь мастер сам (там же
        // стоит выбор народности, EquestriaRaceSelector), а не получает готового пони автоматом.
        // Этап «Народность» (первый) EquestriaDefaultStart пропускает сам, напрямую через данные
        // мастера — см. EquestriaDefaultStart.TrySkipCultureStage.
        internal static void StartDefaultCampaign()
        {
            SkipCharacterCreation = false;
            _introSkipped = false;
            var manager = new SandBoxGameManager(
                new SandBoxGameManager.CampaignCreatorDelegate(() => new Campaign(CampaignGameMode.Campaign)));
            MBGameManager.StartNewGame(manager);
        }

        // Отметка в журнале: видно, дошла ли игра до экрана создания персонажа.
        public static void NoteCharacterCreationStarted()
        {
            EquestriaCrashLog.Note("создание персонажа началось, пропуск="
                + SkipCharacterCreation);
        }
    }
}
