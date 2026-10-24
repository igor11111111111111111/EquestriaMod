using System.Collections.Generic;
using HarmonyLib;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.ViewModelCollection.Map.MapBar;
using TaleWorlds.Core.ViewModelCollection.Information;
using TaleWorlds.Library;
using TaleWorlds.Localization;

namespace EquestriaMod
{
    // Мана героев. Копится на глобальной карте по часам, тратится в бою на заклинания — так же
    // устроены «ветра магии» в The Old Realms (разбор: docs/tor_reference/04_magic.md, раздел 5).
    //
    // Хранится в сейве отдельным словарём: у Hero своего поля под ману нет, а лезть в чужие
    // структуры незачем.
    public class EquestriaManaBehavior : CampaignBehaviorBase
    {
        public const float MaxMana = 60f;
        public const float PerHour = 3f;       // полный запас примерно за сутки пути

        private Dictionary<string, float> _mana = new Dictionary<string, float>();

        private static EquestriaManaBehavior _instance;

        public override void RegisterEvents()
        {
            _instance = this;
            CampaignEvents.HourlyTickEvent.AddNonSerializedListener(this, HourlyTick);
            // Новый заклинатель начинает с полным запасом: иначе первый бой он стоит без магии,
            // пока не пройдёт двадцать часов пути.
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

        // Мана растёт только в пути по карте: в бою её взять неоткуда. Пока колдует один игрок,
        // поэтому и перебирать никого не нужно; когда заклинания получат лорды — сюда придёт
        // обход Hero.AllAliveHeroes с проверкой CanCast.
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

        // Хватило ли маны; при успехе она сразу списывается.
        public static bool TrySpend(Hero hero, float amount)
        {
            if (hero == null || Get(hero) < amount)
            {
                return false;
            }
            Set(hero, Get(hero) - amount);
            return true;
        }

        // Консоль: equestria.mana  /  equestria.mana 60
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

    // Показ маны на панели карты. Ванильная MapInfoVM держит два списка значков (скорость, еда,
    // мораль…) — дописываем в нижний свой. Свою панель рисовать не нужно: игра сама покажет
    // иконку и число. Так же делает TOR (ViewModelExtension на MapInfoVM).
    [HarmonyPatch(typeof(MapInfoVM), "Refresh")]
    public static class EquestriaManaMapInfoPatch
    {
        private static readonly Dictionary<MapInfoVM, MapInfoItemVM> Items =
            new Dictionary<MapInfoVM, MapInfoItemVM>();

        // Refresh зовётся по многу раз в секунду: при поломке отключаемся, чтобы не залить журнал.
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
                    // своего спрайта у мода нет — берём ванильный значок влияния
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

    // Короткие обёртки для интерфейса: мана игрока.
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
