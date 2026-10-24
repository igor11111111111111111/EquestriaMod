using System.Collections.Generic;
using TaleWorlds.Engine.GauntletUI;
using TaleWorlds.GauntletUI;
using TaleWorlds.GauntletUI.BaseTypes;
using TaleWorlds.Library;
using TaleWorlds.MountAndBlade;
using TaleWorlds.MountAndBlade.View;
using TaleWorlds.MountAndBlade.View.MissionViews;
using TaleWorlds.ScreenSystem;

namespace EquestriaMod
{
    // Data for the wheel. Gauntlet reads only these properties - all the logic is in EquestriaSpellMission.
    public class EquestriaSpellWheelVM : ViewModel
    {
        private bool _isVisible;
        private bool _crosshairVisible;
        private bool _hudVisible;
        private bool _messageVisible;
        private string _hudText = string.Empty;
        private string _currentName = string.Empty;
        private string _currentCost = string.Empty;
        private string _currentProblem = string.Empty;
        private string _messageText = string.Empty;
        private MBBindingList<EquestriaSpellItemVM> _items = new MBBindingList<EquestriaSpellItemVM>();

        [DataSourceProperty]
        public bool IsVisible
        {
            get { return _isVisible; }
            set { if (value != _isVisible) { _isVisible = value; OnPropertyChangedWithValue(value, "IsVisible"); } }
        }

        [DataSourceProperty]
        public bool CrosshairVisible
        {
            get { return _crosshairVisible; }
            set { if (value != _crosshairVisible) { _crosshairVisible = value; OnPropertyChangedWithValue(value, "CrosshairVisible"); } }
        }

        [DataSourceProperty]
        public bool HudVisible
        {
            get { return _hudVisible; }
            set { if (value != _hudVisible) { _hudVisible = value; OnPropertyChangedWithValue(value, "HudVisible"); } }
        }

        [DataSourceProperty]
        public bool MessageVisible
        {
            get { return _messageVisible; }
            set { if (value != _messageVisible) { _messageVisible = value; OnPropertyChangedWithValue(value, "MessageVisible"); } }
        }

        [DataSourceProperty]
        public string HudText
        {
            get { return _hudText; }
            set { if (value != _hudText) { _hudText = value; OnPropertyChangedWithValue(value, "HudText"); } }
        }

        [DataSourceProperty]
        public string CurrentName
        {
            get { return _currentName; }
            set { if (value != _currentName) { _currentName = value; OnPropertyChangedWithValue(value, "CurrentName"); } }
        }

        [DataSourceProperty]
        public string CurrentCost
        {
            get { return _currentCost; }
            set { if (value != _currentCost) { _currentCost = value; OnPropertyChangedWithValue(value, "CurrentCost"); } }
        }

        [DataSourceProperty]
        public string CurrentProblem
        {
            get { return _currentProblem; }
            set { if (value != _currentProblem) { _currentProblem = value; OnPropertyChangedWithValue(value, "CurrentProblem"); } }
        }

        [DataSourceProperty]
        public string MessageText
        {
            get { return _messageText; }
            set { if (value != _messageText) { _messageText = value; OnPropertyChangedWithValue(value, "MessageText"); } }
        }

        [DataSourceProperty]
        public MBBindingList<EquestriaSpellItemVM> Items
        {
            get { return _items; }
            set { if (value != _items) { _items = value; OnPropertyChangedWithValue(value, "Items"); } }
        }
    }

    public class EquestriaSpellItemVM : ViewModel
    {
        private string _name;

        public EquestriaSpellItemVM(string name)
        {
            _name = name;
        }

        [DataSourceProperty]
        public string Name
        {
            get { return _name; }
            set { if (value != _name) { _name = value; OnPropertyChangedWithValue(value, "Name"); } }
        }
    }

    // Showing the wheel. The selected item does not come from the widget as an event: we check ourselves which
    // button the vanilla CircleActionSelectorWidget has set IsSelected on. That way no custom widget class is
    // needed (TOR made AbilityRadialSelectionItemWidget for this).
    [DefaultView]
    public class EquestriaSpellWheelView : MissionView
    {
        private EquestriaSpellWheelVM _vm;
        private GauntletLayer _layer;
        private GauntletMovieIdentifier _movie;
        private EquestriaSpellMission _magic;
        private CircleActionSelectorWidget _wheel;
        private int _shownCount = -1;
        private bool _registered;
        private bool _broken;

        public override void OnBehaviorInitialize()
        {
            base.OnBehaviorInitialize();
            EquestriaCrashLog.Try("колесо заклинаний: создание", () =>
            {
                _vm = new EquestriaSpellWheelVM();
                _layer = new GauntletLayer("GauntletLayer", 100);
                _movie = _layer.LoadMovie("EquestriaSpellWheel", _vm);
                MissionScreen.AddLayer(_layer);
            });
        }

        public override void OnMissionScreenTick(float dt)
        {
            base.OnMissionScreenTick(dt);
            if (_broken || _vm == null)
            {
                return;
            }
            try
            {
                Refresh();
            }
            catch (System.Exception e)
            {
                _broken = true;
                EquestriaCrashLog.Warn("колесо заклинаний отключено: " + e.Message);
            }
        }

        private void Refresh()
        {
            if (_magic == null)
            {
                _magic = Mission.Current?.GetMissionBehavior<EquestriaSpellMission>();
                if (_magic == null)
                {
                    return;
                }
            }
            FillItems();

            bool open = _magic.WheelOpen;
            _vm.IsVisible = open;
            _vm.CrosshairVisible = _magic.Aiming;
            _vm.HudVisible = !open && _magic.Spells.Count > 0 && Agent.Main != null && Agent.Main.IsActive()
                && !TaleWorlds.ScreenSystem.ScreenManager.GetMouseVisibility();
            _vm.MessageText = _magic.Message;
            _vm.MessageVisible = !string.IsNullOrEmpty(_vm.MessageText);

            if (open)
            {
                ReadSelection();
            }
            RegisterRadialMenu(open);

            EquestriaSpell current = _magic.Current;
            if (current != null)
            {
                string mana = $"{_magic.Mana:0}/{_magic.ManaLimit:0}";
                _vm.CurrentName = current.Name.ToString();
                _vm.CurrentCost = $"{current.Mana} • {mana}";
                _vm.HudText = _magic.Aiming
                    ? current.Name + " — " + new TaleWorlds.Localization.TextObject(
                        "{=eq_spell_aim_hint}Left click to cast, right click to cancel").ToString()
                    : $"{current.Name} — {current.Mana} • {mana}";
                float left = _magic.CooldownLeft(current);
                _vm.CurrentProblem = left > 0f
                    ? new TaleWorlds.Localization.TextObject("{=eq_spell_cooldown}Spell is not ready yet").ToString()
                      + $" ({left:0})"
                    : (_magic.Mana < current.Mana
                        ? new TaleWorlds.Localization.TextObject("{=eq_spell_no_mana}Not enough mana").ToString()
                        : string.Empty);
            }
            else
            {
                _vm.CurrentName = new TaleWorlds.Localization.TextObject("{=eq_spell_none}No spells known").ToString();
                _vm.CurrentCost = string.Empty;
                _vm.CurrentProblem = string.Empty;
                _vm.HudText = string.Empty;
            }
        }

        private void FillItems()
        {
            if (_shownCount == _magic.Spells.Count)
            {
                return;
            }
            _shownCount = _magic.Spells.Count;
            _vm.Items.Clear();
            foreach (EquestriaSpell spell in _magic.Spells)
            {
                _vm.Items.Add(new EquestriaSpellItemVM(spell.Name.ToString()));
            }
            _wheel = null;   // the widgets will be rebuilt, the old reference is no longer valid
        }

        private void ReadSelection()
        {
            if (_wheel == null)
            {
                List<CircleActionSelectorWidget> found = _movie.Movie.RootWidget
                    .GetAllChildrenOfTypeRecursive<CircleActionSelectorWidget>();
                if (found.Count == 0)
                {
                    return;
                }
                _wheel = found[0];
            }
            for (int i = 0; i < _wheel.ChildCount; i++)
            {
                var button = _wheel.GetChild(i) as ButtonWidget;
                if (button != null && button.IsSelected)
                {
                    _magic.SetSelected(i);
                    return;
                }
            }
        }

        // While the wheel is open the game must not rotate the camera with mouse movement - vanilla radial
        // menus and TOR take the mouse away the same way.
        private void RegisterRadialMenu(bool open)
        {
            if (open == _registered || MissionScreen == null)
            {
                return;
            }
            _registered = open;
            if (open)
            {
                MissionScreen.RegisterRadialMenuObject(this);
            }
            else
            {
                MissionScreen.UnregisterRadialMenuObject(this);
            }
        }

        public override void OnMissionScreenFinalize()
        {
            RegisterRadialMenu(false);
            if (_layer != null)
            {
                if (_movie != null)
                {
                    _layer.ReleaseMovie(_movie);
                }
                MissionScreen.RemoveLayer(_layer);
            }
            _movie = null;
            _layer = null;
            _vm = null;
            _wheel = null;
            base.OnMissionScreenFinalize();
        }
    }
}
