using HarmonyLib;
using TaleWorlds.CampaignSystem;
using TaleWorlds.Core;
using TaleWorlds.Engine.GauntletUI;
using TaleWorlds.InputSystem;
using TaleWorlds.Library;
using TaleWorlds.Localization;
using TaleWorlds.MountAndBlade.GauntletUI.BodyGenerator;
using TaleWorlds.MountAndBlade.ViewModelCollection.FaceGenerator;
using TaleWorlds.ScreenSystem;

namespace EquestriaMod
{
    // Данные для панели переключателя "Сплошная / Полосатая".
    public class EquestriaHairStyleVM : ViewModel
    {
        private bool _isVisible;
        private string _plainLabel = string.Empty;
        private string _stripeLabel = string.Empty;

        [DataSourceProperty]
        public bool IsVisible
        {
            get { return _isVisible; }
            set { if (value != _isVisible) { _isVisible = value; OnPropertyChangedWithValue(value, "IsVisible"); } }
        }

        [DataSourceProperty]
        public string PlainLabel
        {
            get { return _plainLabel; }
            set { if (value != _plainLabel) { _plainLabel = value; OnPropertyChangedWithValue(value, "PlainLabel"); } }
        }

        [DataSourceProperty]
        public string StripeLabel
        {
            get { return _stripeLabel; }
            set { if (value != _stripeLabel) { _stripeLabel = value; OnPropertyChangedWithValue(value, "StripeLabel"); } }
        }

        private bool _isWingsVisible;
        private string _wingsLabel = string.Empty;

        // Видимость своя, отдельная от IsVisible выше: крылья — не только про причёску,
        // кнопка нужна на любой вкладке, а не только на вкладке причёски.
        [DataSourceProperty]
        public bool IsWingsVisible
        {
            get { return _isWingsVisible; }
            set { if (value != _isWingsVisible) { _isWingsVisible = value; OnPropertyChangedWithValue(value, "IsWingsVisible"); } }
        }

        [DataSourceProperty]
        public string WingsLabel
        {
            get { return _wingsLabel; }
            set { if (value != _wingsLabel) { _wingsLabel = value; OnPropertyChangedWithValue(value, "WingsLabel"); } }
        }

        public void ExecuteToggleWings()
        {
            bool now = !EquestriaPonyBody.WingsEnabled;
            EquestriaCrashLog.Log("переключатель крыльев: нажата, теперь " + (now ? "вкл" : "выкл"));
            EquestriaPonyBody.SetWingsEnabled(now);
        }

        private string _tailLabel = string.Empty;
        private string _hornLabel = string.Empty;

        [DataSourceProperty]
        public string TailLabel
        {
            get { return _tailLabel; }
            set { if (value != _tailLabel) { _tailLabel = value; OnPropertyChangedWithValue(value, "TailLabel"); } }
        }

        [DataSourceProperty]
        public string HornLabel
        {
            get { return _hornLabel; }
            set { if (value != _hornLabel) { _hornLabel = value; OnPropertyChangedWithValue(value, "HornLabel"); } }
        }

        public void ExecuteToggleTail()
        {
            bool now = !EquestriaPonyBody.TailEnabled;
            EquestriaCrashLog.Log("переключатель хвоста: нажата, теперь " + (now ? "вкл" : "выкл"));
            EquestriaPonyBody.SetTailEnabled(now);
        }

        public void ExecuteToggleHorn()
        {
            bool now = !EquestriaPonyBody.HornEnabled;
            EquestriaCrashLog.Log("переключатель рога: нажата, теперь " + (now ? "вкл" : "выкл"));
            EquestriaPonyBody.SetHornEnabled(now);
        }

        // Command.Click зовёт публичный метод по имени — без атрибута, ViewModel сам его находит
        // (см. TaleWorlds.MountAndBlade.ViewModelCollection.BannerBuilder.BannerBuilderLayerVM.
        // ExecuteCenterSigil — тот же приём, без [DataSourceMethod], такого атрибута в этой версии
        // SDK просто нет).
        public void ExecutePlain()
        {
            EquestriaCrashLog.Log("переключатель полосок: нажата «Сплошная»");
            EquestriaHairStyle.SetStriped(false);
        }

        public void ExecuteStripe()
        {
            EquestriaCrashLog.Log("переключатель полосок: нажата «Полосатая»");
            EquestriaHairStyle.SetStriped(true);
        }
    }

    // Показывает панель "Сплошная / Полосатая" поверх экрана внешности (окно персонажа, отряд,
    // цирюльник), только пока раса героя — пони.
    //
    // Первая попытка — свой MissionView с [DefaultView] — не сработала: у экрана внешности нет
    // обычной миссии, которую движок собирает через общий перебор [DefaultView] (замечено
    // 29.09.2026: OnBehaviorInitialize не звался вовсе, в логе пусто).
    //
    // Вторая попытка — второй movie на ГОТОВЫЙ GauntletLayer от BodyGeneratorView (у него уже есть
    // свой, с родным FaceGenVM). Movie показался, подписи обновлялись, но клики по кнопкам никуда
    // не доходили (лог пустой — значит дело не в C#, а в том, что слой не отдаёт клики второму
    // movie: видимо, фокус на ввод держит только тот movie, что был на слое первым). Теперь —
    // СВОЙ ОТДЕЛЬНЫЙ GauntletLayer, добавленный прямо на активный экран (ScreenManager.TopScreen,
    // у него есть AddLayer — тот же приём, что и в EquestriaSpellWheel, только хозяин слоя не
    // MissionScreen, а обычный ScreenBase).
    public static class EquestriaHairStyleView
    {
        private static EquestriaHairStyleVM _vm;
        private static GauntletLayer _layer;
        private static ScreenBase _layerOwner;
        private static bool _loggedTick;

        public static void Apply(Harmony harmony)
        {
            var method = AccessTools.Method(typeof(BodyGeneratorView), "OnTick");
            if (method == null)
            {
                EquestriaCrashLog.Warn("переключатель полосок: BodyGeneratorView.OnTick не найден");
                return;
            }
            harmony.Patch(method, postfix: new HarmonyMethod(typeof(EquestriaHairStyleView), nameof(AfterTick)));
            EquestriaCrashLog.Log("переключатель полосок: патч на BodyGeneratorView.OnTick поставлен");

            // Снимаем свой слой явно при закрытии экрана внешности — без этого он пережидает
            // AddLayer/RemoveLayer только при СЛЕДУЮЩЕМ OnTick на другом TopScreen, а OnTick
            // экрана внешности просто перестаёт вызываться, когда мастер создания персонажа уходит
            // на следующий этап (тот же TopScreen у всех этапов, см. AfterTick) — кнопки крыльев/
            // хвоста/рога/полосок оставались висеть поверх «Семьи» и дальше (замечено 08.10.2026,
            // первый прогон полного мастера через -DefaultStart: раньше до этого флага мастер
            // нигде целиком не проходили, SkipCharacterCreation всегда стоял).
            var finalizeMethod = AccessTools.Method(typeof(BodyGeneratorView), "OnFinalize");
            if (finalizeMethod == null)
            {
                EquestriaCrashLog.Warn("переключатель полосок: BodyGeneratorView.OnFinalize не найден");
                return;
            }
            harmony.Patch(finalizeMethod, postfix: new HarmonyMethod(typeof(EquestriaHairStyleView), nameof(AfterFinalize)));
            EquestriaCrashLog.Log("переключатель полосок: патч на BodyGeneratorView.OnFinalize поставлен");
        }

        private static void AfterFinalize(BodyGeneratorView __instance)
        {
            EquestriaCrashLog.Try("переключатель полосок (закрытие экрана)", () =>
            {
                if (_layer != null && _layerOwner != null)
                {
                    _layerOwner.RemoveLayer(_layer);
                    EquestriaCrashLog.Log("переключатель полосок: свой слой снят с "
                        + _layerOwner.GetType().Name);
                }
                _layer = null;
                _layerOwner = null;
                _vm = null;
            });
        }

        private static void AfterTick(BodyGeneratorView __instance)
        {
            EquestriaCrashLog.Try("переключатель полосок (кадр)", () =>
            {
                if (!_loggedTick)
                {
                    _loggedTick = true;
                    EquestriaCrashLog.Log("переключатель полосок: BodyGeneratorView.OnTick сработал первый раз");
                }
                var screen = ScreenManager.TopScreen;
                if (screen == null)
                {
                    return;
                }
                if (_layer == null || _layerOwner != screen)
                {
                    if (_layer != null && _layerOwner != null)
                    {
                        _layerOwner.RemoveLayer(_layer);
                    }
                    _vm = new EquestriaHairStyleVM();
                    // IsFocusLayer НЕ ставим (раньше стоял true): GauntletLayer сам, в ответ на
                    // наведение на кнопку, зовёт ScreenManager.TrySetFocus на себя
                    // (EventManagerOnFocusedWidgetChanged) — а с IsFocusLayer=true потом сам же
                    // не отдаёт фокус назад. Экран крутит персонажа мышью, читая её движение у
                    // СВОЕГО SceneLayer, и это же вращение зависит от того, что фокус вовремя
                    // возвращается ему, а не застревает у нас (замечено 29.09.2026: вращение
                    // стало тугим ровно с тех пор, как этот слой появился). Клики по кнопкам от
                    // фокуса не зависят — они работают через обычный хит-тест виджета.
                    _layer = new GauntletLayer("EquestriaHairStyle", 200, false);
                    // Без этого свежий слой клики вообще не получает — но isMouseVisible=true
                    // (как у родного слоя) спорит с тем, что при вращении персонажа мышью экран
                    // сам прячет курсор и блокирует его позицию (MBWindowManager.
                    // DontChangeCursorPos() + SetMouseVisibility(false) в TickInput,
                    // декомпилировано ilspycmd) — оттого и дребезг (замечено 29.09.2026). Нам
                    // для двух кнопок видимость курсора не нужна вообще, только сами клики.
                    _layer.InputRestrictions.SetInputRestrictions(false, InputUsageMask.MouseButtons);
                    // Хит-тест доходил и без этого (подтверждено логом: FirstHitLayer=наш,
                    // IsHitThisFrame=true при наведении), а клик всё равно не срабатывал —
                    // видимо, обработка самого клика кнопкой требует зарегистрированной
                    // категории горячих клавиш, как у родного слоя.
                    _layer.Input.RegisterHotKeyCategory(HotKeyManager.GetCategory("Generic"));
                    _layer.LoadMovie("EquestriaHairStyle", _vm);
                    // Отдельный movie, не второй корневой виджет в том же .xml — см. комментарий
                    // в EquestriaPonyWings.xml, почему.
                    _layer.LoadMovie("EquestriaPonyWings", _vm);
                    screen.AddLayer(_layer);
                    // Раньше тут ещё стоял ScreenManager.TrySetFocus(_layer) — думал, что без
                    // него клики не идут. Настоящей причиной оказались атрибуты
                    // DoNotPassEventsToChildren/UpdateChildrenStates на кнопках (см. .xml), а
                    // TrySetFocus остался лишним и навсегда перетягивал фокус на себя — из-за
                    // этого перестало вращаться вращение персонажа мышью в редакторе (оно,
                    // видимо, само завязано на то, что фокус держит родной слой). Убрано
                    // 29.09.2026.
                    _layerOwner = screen;
                    EquestriaCrashLog.Log("переключатель полосок: свой слой добавлен на " + screen.GetType().Name);
                }
                // Расу берём из ЖИВОГО выбора в списке «Народность» (FaceGenVM._selectedRace), а
                // не из Hero.MainHero.CharacterObject.Race: на этом экране игрок может крутить
                // список сколько угодно, ещё не нажав «Готово» — а раса героя тем временем
                // остаётся прежней (например, пони после быстрого старта). Раньше тут проверялась
                // раса героя, и из-за этого дракону вместо своих хвоста/крыльев/рога цеплялись
                // пони (замечено 04.10.2026).
                int ponyRace = FaceGen.GetRaceOrDefault("pony");
                int previewRace = ponyRace;
                if (__instance.DataSource != null)
                {
                    object raceValue = EquestriaRaceSelector.SelectedRaceField.GetValue(__instance.DataSource);
                    if (raceValue is int r)
                    {
                        previewRace = r;
                    }
                }
                bool isPony = previewRace == ponyRace;
                // Только на вкладке причёски: кнопки лезли поверх остальных вкладок тоже
                // (замечено 29.09.2026, скриншот с ползунками роста/веса). FaceGenTabs.Hair = 5.
                bool onHairTab = __instance.DataSource != null
                    && __instance.DataSource.Tab == (int)FaceGenVM.FaceGenTabs.Hair;
                _vm.IsVisible = isPony && onHairTab;
                bool striped = EquestriaHairStyle.Striped;
                _vm.PlainLabel = new TextObject("{=eq_hair_plain}Solid").ToString() + (striped ? "" : "  ✓");
                _vm.StripeLabel = new TextObject("{=eq_hair_stripe}Striped").ToString() + (striped ? "  ✓" : "");

                // Крылья/хвост/рог — везде, где раса пони, не только на вкладке причёски.
                _vm.IsWingsVisible = isPony;
                _vm.WingsLabel = PartLabel("{=eq_wings_label}Wings: {STATE}", EquestriaPonyBody.WingsEnabled);
                _vm.TailLabel = PartLabel("{=eq_tail_label}Tail: {STATE}", EquestriaPonyBody.TailEnabled);
                _vm.HornLabel = PartLabel("{=eq_horn_label}Horn: {STATE}", EquestriaPonyBody.HornEnabled);

                // У экрана барбера (в отличие от инвентаря/отряда) свой AgentVisuals —
                // BodyGeneratorView._visualToShow, не через CharacterTableau, и наш обычный
                // per-tick хук (AfterTableauTick) сюда не достаёт. Без принудительного Attach
                // тут кнопки нажимались (сам клик доходил), а хвост/грива не перекрашивались —
                // они обновились бы только при следующей смене снаряжения (замечено 29.09.2026).
                // Не только для пони: любая раса с частями тела (дракон, грифон, як...) должна
                // получать СВОИ хвост/крылья/рог здесь же, а не только пони — поэтому вызываем
                // всегда, передавая живую previewRace (Attach сам ничего не делает, если для расы
                // нет частей тела, см. RaceParts()).
                var visuals = _visualToShowField?.GetValue(__instance);
                if (visuals != null)
                {
                    // cacheKey и bodyCode обязательны здесь же: кнопка "показать одежду" в этом
                    // экране зовёт RefreshCharacterEntity, а та уничтожает _visualToShow и
                    // строит НОВЫЙ (decompiled BodyGeneratorView.RefreshCharacterEntity: Reset()
                    // + _visualToShow = null, дальше пересборка). Без cacheKey Attach брал сам
                    // visuals как ключ кэша (cacheKey ?? visuals) — а он на этом такте уже другой
                    // объект, и цвет причёски "терялся" ровно в момент нажатия кнопки (замечено
                    // 29.09.2026: цвет выбран, нажата "показать одежду" — грива/хвост побелели).
                    // __instance (сам BodyGeneratorView) переживает эту пересборку, как
                    // CharacterTableau переживает свою в окнах снаряжения — тот же приём.
                    string bodyCode = __instance.BodyGen?.CurrentBodyProperties.ToString();
                    EquestriaBodyParts.Attach(visuals, previewRace, "барбер", __instance, bodyCode);
                }
            });
        }

        // _visualToShow — приватное поле BodyGeneratorView, тип AgentVisuals.
        private static readonly System.Reflection.FieldInfo _visualToShowField =
            AccessTools.Field(typeof(BodyGeneratorView), "_visualToShow");

        // Ярлык переключателя «Крылья/Хвост/Рог: вкл/выкл» на языке игрока — template держит
        // {=key}, а «вкл/выкл» своим ключом, иначе под каждую часть пришлось бы заводить
        // отдельную пару «…: on»/«…: off».
        private static string PartLabel(string template, bool on)
        {
            var text = new TextObject(template);
            text.SetTextVariable("STATE", new TextObject(on ? "{=eq_state_on}on" : "{=eq_state_off}off"));
            return text.ToString();
        }
    }
}
