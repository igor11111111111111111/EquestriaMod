using System;
using System.Linq;
using TaleWorlds.Localization;
using TaleWorlds.MountAndBlade;

namespace EquestriaMod
{
    // Главное меню Эквестрии: «Новая кампания» (сюжет) и «Песочница» прячем. Сюжетная кампания в
    // Эквестрии не работает: StoryMode ведёт обучение и сюжетные квесты по ванильным героям и
    // поселениям, которых у нас нет, и падает уже при создании мира
    // (TutorialPhaseCampaignBehavior.CanHaveCampaignIssuesInfoIsRequested — NullReferenceException,
    // 2026-09-22). А новую игру начинает кнопка «Начать приключение» (EquestriaQuickStart), поэтому
    // ванильная «Песочница» рядом с ней лишняя.
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
