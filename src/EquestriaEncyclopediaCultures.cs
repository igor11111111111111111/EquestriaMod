using System;
using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Encyclopedia;
using TaleWorlds.CampaignSystem.Encyclopedia.Pages;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.Core;
using TaleWorlds.Localization;

namespace EquestriaMod
{
    // The "Culture" filter in the encyclopedia (10.10.2026): the troop, hero, settlement and clan
    // pages list only cultures with is_main_culture="true" (DefaultEncyclopedia*Page.
    // InitializeFilterItems). Deerland sits on the vanilla id nord, and the Nords have this flag false,
    // so deer did not appear in the filter, although they have their own realm and troops. We do not enable
    // the flag: the culture list on the character creation screen is built from it too, and Deerland has
    // neither a card nor story branches there. Instead we add to the "Culture" group every
    // culture that has a realm on the map but is not in the list yet.
    public static class EquestriaEncyclopediaCultures
    {
        private static bool _patched;

        public static void Apply(Harmony harmony)
        {
            if (_patched || harmony == null)
            {
                return;
            }
            _patched = true;
            var postfix = new HarmonyMethod(typeof(EquestriaEncyclopediaCultures), nameof(AfterInitializeFilterItems));
            foreach (Type page in new[]
                     {
                         typeof(DefaultEncyclopediaUnitPage), typeof(DefaultEncyclopediaHeroPage),
                         typeof(DefaultEncyclopediaSettlementPage), typeof(DefaultEncyclopediaClanPage),
                     })
            {
                var method = AccessTools.Method(page, "InitializeFilterItems");
                if (method == null)
                {
                    EquestriaCrashLog.Warn("энциклопедия: нет InitializeFilterItems у " + page.Name);
                    continue;
                }
                harmony.Patch(method, postfix: postfix);
            }
            EquestriaCrashLog.Note("энциклопедия: фильтр народностей дополняется культурами держав");
        }

        private static void AfterInitializeFilterItems(ref IEnumerable<EncyclopediaFilterGroup> __result)
        {
            try
            {
                if (__result == null)
                {
                    return;
                }
                var groups = __result as List<EncyclopediaFilterGroup> ?? __result.ToList();
                __result = groups;
                string cultureTitle = GameTexts.FindText("str_culture").ToString();
                EncyclopediaFilterGroup group = groups.FirstOrDefault(
                    g => g != null && g.Name != null && g.Name.ToString() == cultureTitle);
                if (group == null || group.Filters == null)
                {
                    return;
                }
                var present = new HashSet<string>(group.Filters.Where(f => f.Name != null).Select(f => f.Name.ToString()));
                int added = 0;
                foreach (CultureObject culture in Kingdom.All
                             .Where(k => k != null && k.Culture != null)
                             .Select(k => k.Culture)
                             .Distinct()
                             .OrderBy(c => c.Name.ToString()))
                {
                    if (culture.IsBandit || culture.StringId == "neutral_culture"
                        || culture.Name == null || present.Contains(culture.Name.ToString()))
                    {
                        continue;
                    }
                    CultureObject wanted = culture;
                    group.Filters.Add(new EncyclopediaFilterItem(culture.Name, o => CultureOf(o) == wanted));
                    present.Add(culture.Name.ToString());
                    added++;
                }
                if (added > 0)
                {
                    EquestriaCrashLog.Log("энциклопедия: в фильтр народностей добавлено культур — " + added);
                }
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Warn("энциклопедия: фильтр народностей — " + e.GetType().Name + ": " + e.Message);
            }
        }

        private static CultureObject CultureOf(object item)
        {
            switch (item)
            {
                case CharacterObject character: return character.Culture;
                case Hero hero: return hero.Culture;
                case Settlement settlement: return settlement.Culture;
                case IFaction faction: return faction.Culture;
                default: return null;
            }
        }
    }
}
