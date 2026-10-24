using SandBox.View.Map;
using TaleWorlds.CampaignSystem;
using TaleWorlds.InputSystem;

namespace EquestriaMod
{
    // Константы множителя для кнопки x5 (см. EquestriaTimePanel.cs — там же вся логика кнопки,
    // встроенной прямо в нативную панель паузы/игры/ускорения).
    //
    // Как устроена сама перемотка (TaleWorlds.CampaignSystem.Campaign, декомпилировано 04.10.2026):
    // обычная игра — Campaign.SetTimeSpeed(1), x1. Ускорение (их кнопка) — SetTimeSpeed(2), и дальше
    // движок считает время как CampaignDt * SpeedUpMultiplier, а SpeedUpMultiplier — обычный
    // public float на Campaign, по умолчанию 4. Отдельной "второй скорости ускорения" в игре нет:
    // обе кнопки используют один и тот же режим (TimeControlMode), отличаясь только значением
    // SpeedUpMultiplier — тот же приём, что у мода Better Time (github.com/OrderWOPower/BetterTime).
    //
    // Первая версия ставила множитель 5 (на единицу больше их 4) — разница 25% на глаз не видна,
    // особенно когда отряд стоит (не идёт никуда — тогда "скорость" заметна только по часам).
    // 04.10.2026 по жалобе "не вижу разницы с их ускорением" переделано: x5 — это впятеро БЫСТРЕЕ
    // их ускорения (4*5=20), а не на 1 больше — разница должна быть однозначной.
    public static class EquestriaTimeSpeed
    {
        internal const float VanillaMultiplier = 4f;    // Campaign задаёт его в конструкторе
        internal const float FastMultiplier = VanillaMultiplier * 5f;    // впятеро быстрее их ускорения

        // Клавиши 1/2/3 (пауза/игра/ускорение) — родные хоткеи движка, EquestriaTimePanel их не
        // трогает. Клавиша 4 — наша: тот же приём, что у Better Time (Main.cs,
        // OnApplicationTick + IsKeyPressed(InputKey.D4)), не клик по кнопке — так работает даже
        // когда курсор не над панелью. Условие с CurrentMenuContext — то же, что у них: не дёргать
        // скорость, пока открыто меню (разговор, город и т.п.), кроме как в активном "ожидании"
        // (IsWaitActive) без ручной блокировки (TimeControlModeLock).
        public static void Tick()
        {
            Campaign campaign = Campaign.Current;
            if (campaign == null)
            {
                return;
            }
            IInputContext input = MapScreen.Instance?.Input;
            if (input == null)
            {
                return;
            }
            bool allowed = campaign.CurrentMenuContext == null
                || (campaign.CurrentMenuContext.GameMenu.IsWaitActive && !campaign.TimeControlModeLock);
            if (!allowed)
            {
                return;
            }
            // Баг (замечено 07.10.2026): нажали 4 (множитель прилип к 20), потом 1/2, потом 3 —
            // родная клавиша 3 переключает режим перемотки (SetTimeSpeed), но множитель не трогает
            // вообще (в ваниле он один на всю игру, отдельной "второй скорости" там нет) — он так и
            // оставался 20, и кнопка 3 выглядела как кнопка 4. Клик мышью чинит это сам
            // (EquestriaTimePanel.OnUpdate вешает обработчик на FastForwardButton), а клавиша — нет,
            // у неё свой путь мимо нашего обработчика. Сбрасываем явно, тот же приём, что у Better
            // Time (Main.cs: IsKeyPressed(InputKey.D3) -> SpeedUpMultiplier = обычный).
            if (input.IsKeyPressed(InputKey.D3))
            {
                campaign.SpeedUpMultiplier = VanillaMultiplier;
            }
            if (input.IsKeyPressed(InputKey.D4))
            {
                campaign.SpeedUpMultiplier = FastMultiplier;
                campaign.SetTimeSpeed(2);
            }
        }
    }
}
