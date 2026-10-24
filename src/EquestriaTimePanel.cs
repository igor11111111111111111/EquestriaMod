using System.Linq;
using TaleWorlds.CampaignSystem;
using TaleWorlds.GauntletUI;
using TaleWorlds.GauntletUI.BaseTypes;
using TaleWorlds.MountAndBlade.GauntletUI.Widgets.Map.MapBar;

namespace EquestriaMod
{
    // Своя кнопка x5 прямо в нативной панели паузы/игры/ускорения — перенос приёма мода Better Time
    // (github.com/OrderWOPower/BetterTime, TimePanel.cs): он не трогает рендер самого числового
    // множителя (тот не нашёлся ни в одном префабе декомпилом 07.10.2026 — видимо, целиком в
    // движке, вне Gauntlet), а просто добавляет ВТОРУЮ кнопку ускорения рядом с первой внутри того
    // же виджета, программно вешает на обе кнопки обработчик клика, который меняет
    // Campaign.SpeedUpMultiplier, и подсвечивает нужную кнопку по текущему множителю.
    //
    // Раньше (EquestriaTimeSpeed.cs, до 07.10.2026) кнопка x5 была ОТДЕЛЬНЫМ плавающим GauntletLayer
    // поверх экрана — считалось, что клик до дочерней кнопки внутри самого MapCurrentTimeVisualWidget
    // не доходит. Better Time (установленный мод, с 1 млн загрузок) доказывает обратное — дочерняя
    // ButtonWidget внутри наследника этого же класса клики принимает нормально. Следуем за
    // проверенным рабочим способом, старый обходной путь убран.
    //
    // Регистрация типа — без сторонних библиотек (UIExtenderEx и т.п.): WidgetInfo.CollectWidgetTypes
    // (decompile TaleWorlds.GauntletUI.dll) при инициализации UI сканирует ВСЕ загруженные сборки,
    // которые ссылаются на сборку TaleWorlds.GauntletUI (наша EquestriaMod.dll уже ссылается —
    // GauntletLayer использовался и раньше в EquestriaHairStyleView), и регистрирует любой класс-
    // наследник Widget по имени класса = имени XML-тега. В префабе (Module/GUI/Prefabs/Map/
    // MapBar.xml) класс используется как тег <EquestriaTimePanel>.
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
