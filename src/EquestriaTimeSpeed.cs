using SandBox.View.Map;
using TaleWorlds.CampaignSystem;
using TaleWorlds.InputSystem;

namespace EquestriaMod
{
    // Multiplier constants for the x5 button (see EquestriaTimePanel.cs - all the logic of the button,
    // built right into the native pause/play/fast-forward panel, is there).
    //
    // How fast-forward itself works (TaleWorlds.CampaignSystem.Campaign, decompiled 04.10.2026):
    // normal play is Campaign.SetTimeSpeed(1), x1. Fast-forward (their button) is SetTimeSpeed(2), and then
    // the engine computes time as CampaignDt * SpeedUpMultiplier, and SpeedUpMultiplier is a plain
    // public float on Campaign, 4 by default. There is no separate "second fast-forward speed" in the game:
    // both buttons use the same mode (TimeControlMode), differing only in the value of
    // SpeedUpMultiplier - the same trick as the Better Time mod (github.com/OrderWOPower/BetterTime).
    //
    // The first version set the multiplier to 5 (one more than their 4) - a 25% difference is not visible by eye,
    // especially when the party stands still (going nowhere - then "speed" is noticeable only by the clock).
    // 04.10.2026, after the complaint "I can't see a difference from their fast-forward", reworked: x5 is five times
    // FASTER than their fast-forward (4*5=20), not 1 more - the difference must be unambiguous.
    public static class EquestriaTimeSpeed
    {
        internal const float VanillaMultiplier = 4f;    // Campaign sets it in the constructor
        internal const float FastMultiplier = VanillaMultiplier * 5f;    // five times faster than their fast-forward

        // Keys 1/2/3 (pause/play/fast-forward) are the engine's native hotkeys, EquestriaTimePanel does not
        // touch them. Key 4 is ours: the same trick as in Better Time (Main.cs,
        // OnApplicationTick + IsKeyPressed(InputKey.D4)), not a click on the button - so it works even
        // when the cursor is not over the panel. The CurrentMenuContext condition is the same as theirs: do not
        // touch the speed while a menu is open (conversation, town, etc.), except during an active "wait"
        // (IsWaitActive) without a manual lock (TimeControlModeLock).
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
            // Bug (noticed 07.10.2026): pressed 4 (the multiplier stuck at 20), then 1/2, then 3 -
            // the native key 3 switches the fast-forward mode (SetTimeSpeed) but does not touch the multiplier
            // at all (in vanilla it is one for the whole game, there is no separate "second speed") - it
            // stayed at 20, and button 3 looked like button 4. A mouse click fixes this by itself
            // (EquestriaTimePanel.OnUpdate hooks a handler on FastForwardButton), but the key does not,
            // it has its own path bypassing our handler. We reset explicitly, the same trick as in Better
            // Time (Main.cs: IsKeyPressed(InputKey.D3) -> SpeedUpMultiplier = normal).
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
