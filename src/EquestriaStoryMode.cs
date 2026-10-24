using System;
using System.Linq;
using TaleWorlds.Localization;
using TaleWorlds.MountAndBlade;

namespace EquestriaMod
{
    // Equestria main menu: we hide "New Campaign, the story" and "Sandbox".
    // The story campaign does not work in Equestria: StoryMode runs the tutorial and story quests on
    // vanilla heroes and settlements that we do not have, and crashes as early as world creation
    // (TutorialPhaseCampaignBehavior.CanHaveCampaignIssuesInfoIsRequested - NullReferenceException,
    // 2026-09-22). A new game is started by the "Start Adventure" button
    // (EquestriaQuickStart), so the vanilla "Sandbox" next to it is redundant.
    public static class EquestriaStoryMode
    {
        private static readonly string[] HiddenIds = { "StoryModeNewGame", "SandBoxNewGame" };

        public static void DisableStoryCampaign()
        {
            var module = Module.CurrentModule;
            if (module == null)
            {
                return;
            }
            EquestriaCrashLog.Log("кнопки главного меню: " + string.Join(", ",
                module.GetInitialStateOptions().Select(o => o.Id + "#" + o.OrderIndex)));
            foreach (var id in HiddenIds)
            {
                var option = module.GetInitialStateOptionWithId(id);
                if (option == null)
                {
                    EquestriaCrashLog.Log("кнопки главного меню: " + id + " нет — прятать нечего");
                    continue;
                }
                module.OverrideInitialStateOption(id, new InitialStateOption(
                    id, option.Name, option.OrderIndex,
                    () => { },
                    () => (false, null),
                    null,
                    () => true));
                EquestriaCrashLog.Log("кнопки главного меню: " + id + " скрыта");
            }
        }
    }
}
