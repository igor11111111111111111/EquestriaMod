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
    // Список народностей в окне внешности (создание героя, цирюльник).
    //
    // Движок берёт народности из skins: сначала ванильный Native\skins.xml, потом наш
    // pony_skins.xml. Первой всегда идёт человеческая раса Native — убрать её из данных нельзя,
    // файлы игры мы не трогаем. Поэтому прячем её в окне.
    //
    // Тонкость: номер строки в списке — это и есть номер расы (FaceGenVM: _selectedRace =
    // RaceSelector.SelectedIndex). Стоит выкинуть строку — и все номера съедут. Поэтому держим
    // таблицу «строка → раса» (Shown) и переписываем те места игры, где номера встречаются:
    // выбор в списке (OnSelectRace) и сброс (Reset/ResetAll, там номер лежит в _initialRace).
    //
    // Заодно даём народностям русские имена: в списке движок показывает сырые идентификаторы
    // из skins (pony, changeling…), перевода для них нигде нет.
    public static class EquestriaRaceSelector
    {
        // Ванильная человеческая раса: в моде она не нужна, но остаётся расой номер 0
        private static readonly HashSet<string> Hidden = new HashSet<string> { "human" };

        // Текст английский, как и везде в моде: перевод лежит языковыми файлами
        // (ModuleData/Languages, собираются tools/make_world.py).
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

        // internal: EquestriaHairStyleView тоже читает текущую расу из FaceGenVM этим же полем —
        // в экране внешности она может отличаться от Hero.MainHero.CharacterObject.Race, пока
        // игрок просто крутит список «Народность», ещё не нажав «Готово».
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

        // Номера рас, которые показываем, по порядку строк списка
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
            // Прятать всё нельзя: если наши расы почему-то не загрузились, оставляем список как есть
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

        // То же название расы, но для остальных: им зовёт спутников смотр рас (EquestriaRaceParty).
        internal static TextObject TitleOf(string race)
        {
            return Title(race);
        }

        private static int PositionOf(int race)
        {
            return Array.IndexOf(Shown(), race);
        }

        // Переписывает список: убирает спрятанные расы и подставляет русские названия.
        //
        // Делается это до того, как список попадёт в окно (крючок на записи RaceSelector). Если
        // править уже показанный список, окно успевает запомнить прежний номер строки и возвращает
        // его обратно — расу сдвигало на одну вниз при каждом выборе.
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
                // Выбрана спрятанная раса (при первом заходе это человек) — переводим на первую нашу.
                // Внешность под новую расу пересоберёт сама игра: сразу после записи списка она
                // вызывает UpdateRaceAndGenderBasedResources.
                position = 0;
                SelectedRaceField.SetValue(vm, shown[0]);
            }
            // Смена строки в списке дёргает обработчик выбора; на время пересборки его снимаем
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

        // Reset/ResetAll кладут в список номер расы из _initialRace, считая его номером строки.
        // На время их работы держим в _initialRace номер строки, потом возвращаем номер расы.
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

        // Выбор строки в списке: номер строки переводим в номер расы. Дальше повторяем то, что
        // делает игра в OnSelectRace.
        internal static bool Select(FaceGenVM vm, SelectorVM<SelectorItemVM> selector)
        {
            var shown = Shown();
            var names = FaceGen.GetRaceNames();
            if (selector == null || names == null || shown.Length == names.Length)
            {
                return true;
            }
            // Список ещё строится. Игра создаёт его на номере расы (SelectorVM(имена, _selectedRace,
            // обработчик)), и объект списка сразу дёргает обработчик — с номером расы вместо номера
            // строки. Узнаём этот вызов по тому, что список ещё не записан в окно, и пропускаем:
            // выбирал не человек.
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

    // Список правим в тот миг, когда игра его записывает, — раньше, чем он попадёт в окно
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
