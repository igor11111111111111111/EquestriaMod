using System;
using System.Collections.Generic;
using System.Reflection;
using HarmonyLib;
using TaleWorlds.Core;
using TaleWorlds.Core.ViewModelCollection.Selector;
using TaleWorlds.Localization;
using TaleWorlds.MountAndBlade.ViewModelCollection.FaceGenerator;

namespace EquestriaMod
{
    // The list of races in the appearance screen (hero creation, barber).
    //
    // The engine takes races from skins: first the vanilla Native\skins.xml, then our
    // pony_skins.xml. The Native human race always comes first — it cannot be removed from the data,
    // we do not touch the game files. So we hide it in the screen.
    //
    // Subtlety: the row number in the list IS the race number (FaceGenVM: _selectedRace =
    // RaceSelector.SelectedIndex). Drop a row — and all the numbers shift. So we keep a
    // "row -> race" table (Shown) and rewrite the places in the game where the numbers appear:
    // selection in the list (OnSelectRace) and reset (Reset/ResetAll, the number is in _initialRace there).
    //
    // At the same time we give the races Russian names: the engine shows raw ids from skins in the
    // list (pony, changeling…), there is no translation for them anywhere.
    public static class EquestriaRaceSelector
    {
        // The vanilla human race: not needed in the mod, but it stays race number 0
        private static readonly HashSet<string> Hidden = new HashSet<string> { "human" };

        // The text is English, as everywhere in the mod: the translation lives in language files
        // (ModuleData/Languages, built by tools/make_world.py).
        private static readonly Dictionary<string, string> Titles = new Dictionary<string, string>
        {
            { "pony", "{=eq_race_pony}Pony" },
            { "changeling", "{=eq_race_changeling}Changeling" },
            { "deer", "{=eq_race_deer}Deer" },
            { "griffon", "{=eq_race_griffon}Gryphon" },
            { "yak", "{=eq_race_yak}Yak" },
            { "dragon", "{=eq_race_dragon}Dragon" },
            { "hippogriff", "{=eq_race_hippogriff}Hippogriff" },
        };

        // internal: EquestriaHairStyleView also reads the current race from FaceGenVM via this field —
        // in the appearance screen it may differ from Hero.MainHero.CharacterObject.Race while the
        // player is just scrolling the "Culture" list, not yet having pressed "Done".
        internal static readonly FieldInfo SelectedRaceField = AccessTools.Field(typeof(FaceGenVM), "_selectedRace");
        private static readonly FieldInfo InitialRaceField = AccessTools.Field(typeof(FaceGenVM), "_initialRace");
        private static readonly FieldInfo OnChangeField =
            AccessTools.Field(typeof(SelectorVM<SelectorItemVM>), "_onChange");
        private static readonly MethodInfo AddCommandMethod = AccessTools.Method(typeof(FaceGenVM), "AddCommand");
        private static readonly MethodInfo UpdateResourcesMethod =
            AccessTools.Method(typeof(FaceGenVM), "UpdateRaceAndGenderBasedResources");
        private static readonly MethodInfo RefreshMethod =
            AccessTools.Method(typeof(FaceGenVM), "Refresh", new[] { typeof(bool) });
        private static readonly MethodInfo TryGetInitialValueMethod = AccessTools.Method(
            typeof(FaceGenVM), "TryGetInitialValue", new[] { typeof(string), typeof(int).MakeByRefType() });
        private static readonly MethodInfo SetOrAddInitialValueMethod = AccessTools.Method(
            typeof(FaceGenVM), "SetOrAddInitialValue", new[] { typeof(string), typeof(float) });

        private static string[] _names;
        private static int[] _shown;

        // Numbers of the races we show, in list row order
        private static int[] Shown()
        {
            var names = FaceGen.GetRaceNames();
            if (names == null)
            {
                return new int[0];
            }
            if (_shown != null && _names != null && _names.Length == names.Length)
            {
                return _shown;
            }
            var shown = new List<int>(names.Length);
            for (int i = 0; i < names.Length; i++)
            {
                if (!Hidden.Contains(names[i]))
                {
                    shown.Add(i);
                }
            }
            // Hiding everything is not allowed: if our races somehow did not load, leave the list as is
            if (shown.Count == 0)
            {
                for (int i = 0; i < names.Length; i++)
                {
                    shown.Add(i);
                }
            }
            _names = names;
            _shown = shown.ToArray();
            EquestriaCrashLog.Log("народности в окне внешности: "
                + string.Join(", ", Array.ConvertAll(_shown, i => names[i])));
            return _shown;
        }

        private static TextObject Title(string race)
        {
            string title;
            return Titles.TryGetValue(race, out title) ? new TextObject(title) : new TextObject("{=!}" + race);
        }

        // The same race name, but for others: the race review (EquestriaRaceParty) names companions with it.
        internal static TextObject TitleOf(string race)
        {
            return Title(race);
        }

        private static int PositionOf(int race)
        {
            return Array.IndexOf(Shown(), race);
        }

        // Rewrites the list: removes hidden races and substitutes Russian names.
        //
        // This is done before the list reaches the screen (a hook on the RaceSelector setter). If an
        // already shown list is edited, the screen manages to remember the previous row number and
        // puts it back — the race shifted one down on every selection.
        internal static void Rebuild(FaceGenVM vm, SelectorVM<SelectorItemVM> selector)
        {
            var shown = Shown();
            var names = FaceGen.GetRaceNames();
            if (selector == null || shown.Length == 0 || names == null || shown.Length == names.Length)
            {
                return;
            }
            int position = PositionOf((int)SelectedRaceField.GetValue(vm));
            if (position < 0)
            {
                // A hidden race is selected (on the first visit it is the human) — switch to our first one.
                // The game itself rebuilds the appearance for the new race: right after the list is set
                // it calls UpdateRaceAndGenderBasedResources.
                position = 0;
                SelectedRaceField.SetValue(vm, shown[0]);
            }
            // Changing the list row fires the selection handler; we remove it while rebuilding
            var onChange = OnChangeField.GetValue(selector);
            OnChangeField.SetValue(selector, null);
            try
            {
                selector.ItemList.Clear();
                foreach (var race in shown)
                {
                    selector.ItemList.Add(new SelectorItemVM(Title(names[race])));
                }
                selector.SelectedIndex = position;
            }
            finally
            {
                OnChangeField.SetValue(selector, onChange);
            }
            EquestriaCrashLog.Log("список народностей: строка " + position
                + " — " + names[shown[position]]);
        }

        // Reset/ResetAll put the race number from _initialRace into the list, treating it as a row number.
        // While they run we keep the row number in _initialRace, then put the race number back.
        internal static void InitialRaceToPosition(FaceGenVM vm)
        {
            int race = (int)InitialRaceField.GetValue(vm);
            int position = race < 0 ? -1 : PositionOf(race);
            InitialRaceField.SetValue(vm, position < 0 ? race : position);
        }

        internal static void InitialRaceFromPosition(FaceGenVM vm)
        {
            int position = (int)InitialRaceField.GetValue(vm);
            var shown = Shown();
            if (position >= 0 && position < shown.Length)
            {
                InitialRaceField.SetValue(vm, shown[position]);
            }
        }

        // Selecting a row in the list: the row number is converted to the race number. Then we repeat
        // what the game does in OnSelectRace.
        internal static bool Select(FaceGenVM vm, SelectorVM<SelectorItemVM> selector)
        {
            var shown = Shown();
            var names = FaceGen.GetRaceNames();
            if (selector == null || names == null || shown.Length == names.Length)
            {
                return true;
            }
            // The list is still being built. The game creates it on the race number (SelectorVM(names,
            // _selectedRace, handler)), and the list object fires the handler right away — with the race
            // number instead of the row number. We recognise this call by the list not yet being set
            // in the screen, and skip it: it was not a person choosing.
            if (!ReferenceEquals(vm.RaceSelector, selector))
            {
                return false;
            }
            int position = selector.SelectedIndex;
            if (position < 0 || position >= shown.Length)
            {
                return true;
            }
            AddCommandMethod.Invoke(vm, null);
            SelectedRaceField.SetValue(vm, shown[position]);
            if ((int)InitialRaceField.GetValue(vm) == -1)
            {
                var args = new object[] { "SelectedRace", 0 };
                if ((bool)TryGetInitialValueMethod.Invoke(vm, args))
                {
                    InitialRaceField.SetValue(vm, args[1]);
                }
                else
                {
                    SetOrAddInitialValueMethod.Invoke(vm, new object[] { "SelectedRace", (float)shown[position] });
                }
            }
            EquestriaCrashLog.Log("выбрана народность: строка " + position
                + " — " + names[shown[position]]);
            UpdateResourcesMethod.Invoke(vm, null);
            RefreshMethod.Invoke(vm, new object[] { true });
            return false;
        }
    }

    // The list is edited the moment the game sets it — before it reaches the screen
    [HarmonyPatch(typeof(FaceGenVM), "RaceSelector", MethodType.Setter)]
    public static class RaceListWithoutHumans
    {
        public static void Prefix(FaceGenVM __instance, SelectorVM<SelectorItemVM> value)
        {
            EquestriaCrashLog.Try("список народностей",
                () => EquestriaRaceSelector.Rebuild(__instance, value));
        }
    }

    [HarmonyPatch(typeof(FaceGenVM), "OnSelectRace")]
    public static class RaceListChoice
    {
        public static bool Prefix(FaceGenVM __instance, SelectorVM<SelectorItemVM> s)
        {
            bool original = true;
            EquestriaCrashLog.Try("выбор народности",
                () => original = EquestriaRaceSelector.Select(__instance, s));
            return original;
        }
    }

    [HarmonyPatch(typeof(FaceGenVM), "Reset")]
    public static class RaceListReset
    {
        public static void Prefix(FaceGenVM __instance)
        {
            EquestriaCrashLog.Try("сброс внешности", () => EquestriaRaceSelector.InitialRaceToPosition(__instance));
        }

        public static void Postfix(FaceGenVM __instance)
        {
            EquestriaCrashLog.Try("сброс внешности", () => EquestriaRaceSelector.InitialRaceFromPosition(__instance));
        }
    }

    [HarmonyPatch(typeof(FaceGenVM), "ResetAll")]
    public static class RaceListResetAll
    {
        public static void Prefix(FaceGenVM __instance)
        {
            EquestriaCrashLog.Try("полный сброс внешности",
                () => EquestriaRaceSelector.InitialRaceToPosition(__instance));
        }

        public static void Postfix(FaceGenVM __instance)
        {
            EquestriaCrashLog.Try("полный сброс внешности",
                () => EquestriaRaceSelector.InitialRaceFromPosition(__instance));
        }
    }
}
