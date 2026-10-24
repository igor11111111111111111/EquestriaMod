using System.Collections.Generic;
using HarmonyLib;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.ViewModelCollection.Map.MapBar;
using TaleWorlds.Core.ViewModelCollection.Information;
using TaleWorlds.Library;
using TaleWorlds.Localization;

namespace EquestriaMod
{
    // Heroes' mana. It accumulates hourly on the world map and is spent on spells in battle - the
    // "winds of magic" in The Old Realms work the same way (analysis: docs/tor_reference/04_magic.md, section 5).
    //
    // Stored in the save as a separate dictionary: Hero has no field of its own for mana, and there is no
    // reason to meddle with other structures.
    public class EquestriaManaBehavior : CampaignBehaviorBase
    {
        public const float MaxMana = 60f;
        public const float PerHour = 3f;       // a full pool in about a day of travel

        private Dictionary<string, float> _mana = new Dictionary<string, float>();

        private static EquestriaManaBehavior _instance;

        public override void RegisterEvents()
        {
            _instance = this;
            CampaignEvents.HourlyTickEvent.AddNonSerializedListener(this, HourlyTick);
            // A new caster starts with a full pool: otherwise he spends the first battle without magic
            // until twenty hours of travel have passed.
            CampaignEvents.OnSessionLaunchedEvent.AddNonSerializedListener(this, _ =>
                EquestriaCrashLog.Try("первичная мана", FillNewCasters));
        }

        private void FillNewCasters()
        {
            Hero hero = Hero.MainHero;
            if (CanCast(hero) && !_mana.ContainsKey(hero.StringId))
            {
                Set(hero, Max(hero));
            }
        }

        public override void SyncData(IDataStore dataStore)
        {
            dataStore.SyncData("eq_hero_mana", ref _mana);
            if (_mana == null)
            {
                _mana = new Dictionary<string, float>();
            }
            _instance = this;
        }

        // Mana grows only while travelling on the map: in battle there is nowhere to get it. For now only the
        // player casts, so there is no one to iterate over; when lords get spells, a pass over
        // Hero.AllAliveHeroes with a CanCast check will go here.
        private void HourlyTick()
        {
            if (CanCast(Hero.MainHero))
            {
                Add(Hero.MainHero, PerHour);
            }
        }

        public static bool CanCast(Hero hero)
        {
            return hero != null && hero == Hero.MainHero && EquestriaSpells.All.Count > 0;
        }

        public static float Max(Hero hero)
        {
            return MaxMana;
        }

        public static float Get(Hero hero)
        {
            float value;
            return hero != null && _instance != null && _instance._mana.TryGetValue(hero.StringId, out value)
                ? value : 0f;
        }

        public static void Set(Hero hero, float value)
        {
            if (hero == null || _instance == null)
            {
                return;
            }
            _instance._mana[hero.StringId] = MBMath.ClampFloat(value, 0f, Max(hero));
        }

        public static void Add(Hero hero, float amount)
        {
            Set(hero, Get(hero) + amount);
        }

        // Whether there was enough mana; on success it is deducted at once.
        public static bool TrySpend(Hero hero, float amount)
        {
            if (hero == null || Get(hero) < amount)
            {
                return false;
            }
            Set(hero, Get(hero) - amount);
            return true;
        }

        // Console: equestria.mana  /  equestria.mana 60
        [CommandLineFunctionality.CommandLineArgumentFunction("mana", "equestria")]
        public static string ManaCommand(List<string> args)
        {
            if (Campaign.Current == null || Hero.MainHero == null)
            {
                return "Available only in a campaign.";
            }
            float value;
            if (args.Count == 1 && float.TryParse(args[0], out value))
            {
                Set(Hero.MainHero, value);
            }
            return $"Mana: {Get(Hero.MainHero):0} / {Max(Hero.MainHero):0} (+{PerHour:0.#} per hour on the map).";
        }
    }

    // Showing mana on the map panel. The vanilla MapInfoVM holds two lists of icons (speed, food,
    // morale...) - we add ours to the lower one. No need to draw our own panel: the game shows the
    // icon and the number itself. TOR does the same (ViewModelExtension on MapInfoVM).
    [HarmonyPatch(typeof(MapInfoVM), "Refresh")]
    public static class EquestriaManaMapInfoPatch
    {
        private static readonly Dictionary<MapInfoVM, MapInfoItemVM> Items =
            new Dictionary<MapInfoVM, MapInfoItemVM>();

        // Refresh is called many times per second: on failure we switch off so as not to flood the log.
        private static bool _broken;

        [HarmonyPostfix]
        public static void Postfix(MapInfoVM __instance)
        {
            if (_broken || Hero.MainHero == null || !EquestriaManaBehavior.CanCast(Hero.MainHero))
            {
                return;
            }
            try
            {
                MapInfoItemVM item;
                if (!Items.TryGetValue(__instance, out item))
                {
                    item = new MapInfoItemVM("eq_mana", Hint);
                    // the mod has no sprite of its own - use the vanilla influence icon
                    item.SetOverriddenVisualId("influence");
                    __instance.SecondaryInfoItems.Add(item);
                    Items[__instance] = item;
                }
                item.Value = $"{EquestriaMana.Value:0}/{EquestriaMana.Limit:0}";
            }
            catch (System.Exception e)
            {
                _broken = true;
                EquestriaCrashLog.Warn("мана на панели карты отключена: " + e.Message);
            }
        }

        private static List<TooltipProperty> Hint()
        {
            var lines = new List<TooltipProperty>
            {
                new TooltipProperty(new TextObject("{=eq_mana_label}Mana").ToString(), "", 0,
                    false, TooltipProperty.TooltipPropertyFlags.Title),
                new TooltipProperty($"{EquestriaMana.Value:0} / {EquestriaMana.Limit:0}",
                    $"+{EquestriaManaBehavior.PerHour:0.#}", 0),
                new TooltipProperty(new TextObject("{=eq_mana_hint}Mana builds up as you travel.").ToString(),
                    "", 0, false, TooltipProperty.TooltipPropertyFlags.MultiLine)
            };
            return lines;
        }
    }

    // Short wrappers for the UI: the player's mana.
    public static class EquestriaMana
    {
        public static float Value
        {
            get { return EquestriaManaBehavior.Get(Hero.MainHero); }
        }

        public static float Limit
        {
            get { return EquestriaManaBehavior.Max(Hero.MainHero); }
        }
    }
}
