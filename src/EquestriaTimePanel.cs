using System.Linq;
using TaleWorlds.CampaignSystem;
using TaleWorlds.GauntletUI;
using TaleWorlds.GauntletUI.BaseTypes;
using TaleWorlds.MountAndBlade.GauntletUI.Widgets.Map.MapBar;

namespace EquestriaMod
{
    // Our own x5 button right inside the native pause/play/fast-forward panel — a port of the trick from
    // the Better Time mod (github.com/OrderWOPower/BetterTime, TimePanel.cs): it does not touch the
    // rendering of the numeric multiplier itself (that was not found in any prefab by decompiling on
    // 07.10.2026 — apparently it is entirely in the engine, outside Gauntlet), but simply adds a SECOND
    // fast-forward button next to the first one inside the same widget, attaches a click handler to both
    // buttons in code that changes Campaign.SpeedUpMultiplier, and highlights the right button by the
    // current multiplier.
    //
    // Previously (EquestriaTimeSpeed.cs, before 07.10.2026) the x5 button was a SEPARATE floating
    // GauntletLayer over the screen — it was believed that clicks do not reach a child button inside
    // MapCurrentTimeVisualWidget itself. Better Time (an installed mod with 1M downloads) proves
    // otherwise — a child ButtonWidget inside a subclass of this same class receives clicks fine. We
    // follow the proven working approach; the old workaround is removed.
    //
    // Type registration without third-party libraries (UIExtenderEx etc.): WidgetInfo.CollectWidgetTypes
    // (decompile TaleWorlds.GauntletUI.dll) scans, on UI initialisation, ALL loaded assemblies that
    // reference the TaleWorlds.GauntletUI assembly (our EquestriaMod.dll already does — GauntletLayer
    // was used before in EquestriaHairStyleView), and registers any Widget subclass by class name =
    // XML tag name. In the prefab (Module/GUI/Prefabs/Map/MapBar.xml) the class is used as the
    // <EquestriaTimePanel> tag.
    public class EquestriaTimePanel : MapCurrentTimeVisualWidget
    {
        private ButtonWidget _fastFastForwardButton;

        [Editor(false)]
        public ButtonWidget FastFastForwardButton
        {
            get => _fastFastForwardButton;
            set
            {
                if (_fastFastForwardButton == value)
                {
                    return;
                }
                _fastFastForwardButton = value;
                OnPropertyChanged(value, nameof(FastFastForwardButton));
            }
        }

        public EquestriaTimePanel(UIContext context) : base(context)
        {
            AddState("Disabled");
        }

        protected override void OnUpdate(float dt)
        {
            base.OnUpdate(dt);
            Campaign campaign = Campaign.Current;
            if (IsDisabled || campaign == null)
            {
                SetState("Disabled");
                return;
            }
            if (FastForwardButton == null || FastFastForwardButton == null || PlayButton == null || PauseButton == null)
            {
                return;
            }
            if (!FastForwardButton.ClickEventHandlers.Any())
            {
                FastForwardButton.ClickEventHandlers.Add(a => campaign.SpeedUpMultiplier = EquestriaTimeSpeed.VanillaMultiplier);
            }
            if (!FastFastForwardButton.ClickEventHandlers.Any())
            {
                FastFastForwardButton.ClickEventHandlers.Add(a => campaign.SpeedUpMultiplier = EquestriaTimeSpeed.FastMultiplier);
            }
            SetState("Default");
            PauseButton.IsSelected = false;
            PlayButton.IsSelected = false;
            FastForwardButton.IsSelected = false;
            FastFastForwardButton.IsSelected = false;
            switch (CurrentTimeState)
            {
                case 0:
                case 6:
                    PauseButton.IsSelected = true;
                    break;
                case 1:
                case 3:
                    PlayButton.IsSelected = true;
                    break;
                case 2:
                case 4:
                case 5:
                    if (campaign.SpeedUpMultiplier > EquestriaTimeSpeed.VanillaMultiplier)
                    {
                        FastFastForwardButton.IsSelected = true;
                    }
                    else
                    {
                        FastForwardButton.IsSelected = true;
                    }
                    break;
            }
        }
    }
}
