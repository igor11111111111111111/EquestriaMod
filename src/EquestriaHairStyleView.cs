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
    // Data for the "Solid / Striped" toggle panel.
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

        // Its own visibility, separate from IsVisible above: wings are not only about the hairstyle,
        // the button is needed on every tab, not just the hair tab.
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

        // Command.Click calls a public method by name — no attribute, the ViewModel finds it itself
        // (see TaleWorlds.MountAndBlade.ViewModelCollection.BannerBuilder.BannerBuilderLayerVM.
        // ExecuteCenterSigil — the same trick, without [DataSourceMethod]; this SDK version simply
        // has no such attribute).
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

    // Shows the "Solid / Striped" panel over the appearance screen (character
    // window, party, barber), only while the hero's race is pony.
    //
    // The first attempt — our own MissionView with [DefaultView] — did not work: the appearance
    // screen has no regular mission that the engine assembles via the general [DefaultView] scan
    // (noticed 29.09.2026: OnBehaviorInitialize was never called, the log was empty).
    //
    // The second attempt — a second movie on the EXISTING GauntletLayer of BodyGeneratorView (it
    // already has its own, with the native FaceGenVM). The movie appeared, labels updated, but clicks
    // on the buttons went nowhere (empty log — so the problem is not in C# but in the layer not
    // passing clicks to the second movie: apparently only the movie that was on the layer first holds
    // input focus). Now — OUR OWN SEPARATE GauntletLayer, added directly to the active screen
    // (ScreenManager.TopScreen, which has AddLayer — the same trick as in EquestriaSpellWheel, only
    // the layer's owner is not a MissionScreen but a regular ScreenBase).
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

            // Remove our layer explicitly when the appearance screen closes — without this it waits
            // for AddLayer/RemoveLayer only on the NEXT OnTick on another TopScreen, but the appearance
            // screen's OnTick simply stops being called when the character creation wizard moves to
            // the next stage (all stages share the same TopScreen, see AfterTick) — the wings/tail/
            // horn/stripe buttons kept hanging over "Family" and beyond (noticed 08.10.2026,
            // the first run of the full wizard via -DefaultStart: before this flag the wizard had
            // never been gone through fully, SkipCharacterCreation was always set).
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
                    // We do NOT set IsFocusLayer (it used to be true): GauntletLayer itself, in
                    // response to hovering a button, calls ScreenManager.TrySetFocus on itself
                    // (EventManagerOnFocusedWidgetChanged) — and with IsFocusLayer=true it then
                    // does not give focus back. The screen rotates the character with the mouse,
                    // reading its movement from ITS OWN SceneLayer, and that rotation depends on
                    // focus returning to it in time instead of getting stuck with us (noticed
                    // 29.09.2026: rotation became stiff exactly since this layer appeared). Button
                    // clicks do not depend on focus — they work through the normal widget hit test.
                    _layer = new GauntletLayer("EquestriaHairStyle", 200, false);
                    // Without this a fresh layer gets no clicks at all — but isMouseVisible=true
                    // (as on the native layer) conflicts with the screen hiding the cursor and
                    // locking its position itself while the character is rotated with the mouse
                    // (MBWindowManager.DontChangeCursorPos() + SetMouseVisibility(false) in
                    // TickInput, decompiled with ilspycmd) — hence the jitter (noticed 29.09.2026).
                    // For two buttons we do not need cursor visibility at all, only the clicks.
                    _layer.InputRestrictions.SetInputRestrictions(false, InputUsageMask.MouseButtons);
                    // The hit test got through even without this (confirmed by the log:
                    // FirstHitLayer=ours, IsHitThisFrame=true on hover), yet the click still did
                    // not fire — apparently the button's handling of the click itself requires a
                    // registered hotkey category, as on the native layer.
                    _layer.Input.RegisterHotKeyCategory(HotKeyManager.GetCategory("Generic"));
                    _layer.LoadMovie("EquestriaHairStyle", _vm);
                    // A separate movie, not a second root widget in the same .xml — see the comment
                    // in EquestriaPonyWings.xml for why.
                    _layer.LoadMovie("EquestriaPonyWings", _vm);
                    screen.AddLayer(_layer);
                    // There used to be ScreenManager.TrySetFocus(_layer) here too — I thought clicks
                    // would not get through without it. The real cause turned out to be the
                    // DoNotPassEventsToChildren/UpdateChildrenStates attributes on the buttons (see
                    // .xml), and TrySetFocus was left redundant and permanently pulled focus to
                    // itself — because of this, rotating the character with the mouse in the editor
                    // stopped working (it apparently depends on the native layer holding focus).
                    // Removed 29.09.2026.
                    _layerOwner = screen;
                    EquestriaCrashLog.Log("переключатель полосок: свой слой добавлен на " + screen.GetType().Name);
                }
                // The race is taken from the LIVE selection in the "Race" list
                // (FaceGenVM._selectedRace), not from Hero.MainHero.CharacterObject.Race: on this
                // screen the player can scroll the list as much as they like before pressing
                // "Done" — while the hero's race stays the old one (e.g. pony after a quick
                // start). Previously the hero's race was checked here, and because of that a dragon
                // got pony parts instead of its own tail/wings/horn (noticed 04.10.2026).
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
                // Only on the hair tab: the buttons showed up over the other tabs too
                // (noticed 29.09.2026, screenshot with the height/weight sliders). FaceGenTabs.Hair = 5.
                bool onHairTab = __instance.DataSource != null
                    && __instance.DataSource.Tab == (int)FaceGenVM.FaceGenTabs.Hair;
                _vm.IsVisible = isPony && onHairTab;
                bool striped = EquestriaHairStyle.Striped;
                _vm.PlainLabel = new TextObject("{=eq_hair_plain}Solid").ToString() + (striped ? "" : "  ✓");
                _vm.StripeLabel = new TextObject("{=eq_hair_stripe}Striped").ToString() + (striped ? "  ✓" : "");

                // Wings/tail/horn — wherever the race is pony, not only on the hair tab.
                _vm.IsWingsVisible = isPony;
                _vm.WingsLabel = PartLabel("{=eq_wings_label}Wings: {STATE}", EquestriaPonyBody.WingsEnabled);
                _vm.TailLabel = PartLabel("{=eq_tail_label}Tail: {STATE}", EquestriaPonyBody.TailEnabled);
                _vm.HornLabel = PartLabel("{=eq_horn_label}Horn: {STATE}", EquestriaPonyBody.HornEnabled);

                // The barber screen (unlike inventory/party) has its own AgentVisuals —
                // BodyGeneratorView._visualToShow, not via CharacterTableau, and our usual
                // per-tick hook (AfterTableauTick) does not reach it. Without a forced Attach here
                // the buttons were pressed (the click itself got through), but the tail/mane were
                // not recoloured — they would update only on the next equipment change (noticed
                // 29.09.2026). Not only for ponies: any race with body parts (dragon, griffon,
                // yak...) must get ITS OWN tail/wings/horn right here too — so we call it always,
                // passing the live previewRace (Attach does nothing by itself if the race has no
                // body parts, see RaceParts()).
                var visuals = _visualToShowField?.GetValue(__instance);
                if (visuals != null)
                {
                    // cacheKey and bodyCode are required right here: the "show clothes" button on
                    // this screen calls RefreshCharacterEntity, which destroys _visualToShow and
                    // builds a NEW one (decompiled BodyGeneratorView.RefreshCharacterEntity: Reset()
                    // + _visualToShow = null, then a rebuild). Without cacheKey Attach used visuals
                    // itself as the cache key (cacheKey ?? visuals) — but on that tick it is already
                    // a different object, and the hair colour got "lost" exactly when the button was
                    // pressed (noticed 29.09.2026: colour chosen, "show clothes" pressed — mane/tail
                    // turned white). __instance (the BodyGeneratorView itself) survives this
                    // rebuild, as CharacterTableau survives its own in the equipment windows — the
                    // same trick.
                    string bodyCode = __instance.BodyGen?.CurrentBodyProperties.ToString();
                    EquestriaBodyParts.Attach(visuals, previewRace, "барбер", __instance, bodyCode);
                }
            });
        }

        // _visualToShow — a private field of BodyGeneratorView, of type AgentVisuals.
        private static readonly System.Reflection.FieldInfo _visualToShowField =
            AccessTools.Field(typeof(BodyGeneratorView), "_visualToShow");

        // The toggle label "Wings/Tail/Horn: on/off" in the player's language — template holds
        // {=key}, and "on/off" has its own key, otherwise each part would need its own
        // separate pair "…: on"/"…: off".
        private static string PartLabel(string template, bool on)
        {
            var text = new TextObject(template);
            text.SetTextVariable("STATE", new TextObject(on ? "{=eq_state_on}on" : "{=eq_state_off}off"));
            return text.ToString();
        }
    }
}
