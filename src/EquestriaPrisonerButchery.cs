using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using HarmonyLib;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.GameState;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.CampaignSystem.ViewModelCollection.Party;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.Localization;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Переработка пленных в мясо (equestria_items.xml: eq_prisoner_meat).
    //
    // В моде все войска — звери (пони, грифоны, драконы, яки, чейнджлинги, олени), часть рас явно
    // хищники или всеядные — переработка пленных в припасы вписывается в лор так же, как у орков в
    // The Old Realms. TOR на диске не нашёлся (видимо, удалён — ссылка в памяти проекта это уже
    // отмечала), свериться с их реализацией напрямую не вышло — сделано с нуля по общим правилам
    // Bannerlord (TroopRoster/ItemRoster), не скопировано.
    //
    // Два интерфейса: консольная команда (ниже) и кнопка прямо в окне отряда, в строке пленного —
    // см. ButtonPatch и форк SandBox\GUI\Prefabs\Party\PartyTroopTuple.xml. У движка готовая кнопка
    // "Казнить" в той же строке — но её Code (PartyCommandCode.ExecuteTroop) жёстко проверяет
    // character.IsHero (PartyScreenLogic.IsExecutable, декомпилировано 04.10.2026) и для рядовых
    // не сработает ни при каком патче снаружи — поэтому вместо переиспользования команды кнопка
    // переработки перехватывает сам клик (PartyCharacterVM.ExecuteExecuteTroop) и для рядовых
    // пленных подменяет его целиком, а геройскую казнь не трогает (return true — пусть движок
    // казнит героя как обычно). Пленных героев не трогаем вообще — у них своя сюжетная судьба
    // (выкуп, казнь по сюжету).
    public static class EquestriaPrisonerButchery
    {
        public const string MeatItemId = "eq_prisoner_meat";

        // Мяса с одного пленного: меньше, чем боец стоил бы выкупом или вербовкой — иначе мясник
        // всегда выгоднее остальных вариантов распорядиться пленным.
        private const int MeatPerPrisoner = 2;

        /// <summary>Переработать до count рядовых пленных отряда. Возвращает (сколько переработано,
        /// сколько получено мяса).</summary>
        internal static (int butchered, int meat) Butcher(MobileParty party, int count)
        {
            if (party == null || count <= 0)
            {
                return (0, 0);
            }
            var roster = party.PrisonRoster;
            int left = count;
            int butchered = 0;
            foreach (var element in roster.GetTroopRoster()
                         .Where(e => e.Character != null && !e.Character.IsHero).ToList())
            {
                if (left <= 0)
                {
                    break;
                }
                int take = Math.Min(left, element.Number);
                roster.AddToCounts(element.Character, -take);
                left -= take;
                butchered += take;
            }
            if (butchered <= 0)
            {
                return (0, 0);
            }
            int meat = butchered * MeatPerPrisoner;
            var meatItem = MBObjectManager.Instance.GetObject<ItemObject>(MeatItemId);
            if (meatItem == null)
            {
                EquestriaCrashLog.Warn("переработка пленных: предмет " + MeatItemId + " не найден");
                return (butchered, 0);
            }
            party.ItemRoster.AddToCounts(meatItem, meat);
            return (butchered, meat);
        }

        // equestria.butcher_prisoners [сколько] — переработать пленных своего отряда
        // (без числа — всех рядовых разом)
        [CommandLineFunctionality.CommandLineArgumentFunction("butcher_prisoners", "equestria")]
        public static string Console(List<string> args)
        {
            if (Campaign.Current == null || MobileParty.MainParty == null)
            {
                return "доступно только в кампании";
            }
            int total = MobileParty.MainParty.PrisonRoster.TotalManCount;
            int want = args != null && args.Count > 0 && int.TryParse(args[0], out int n) ? Math.Max(1, n) : total;
            var (butchered, meat) = Butcher(MobileParty.MainParty, want);
            if (butchered == 0)
            {
                return "перерабатывать некого (пленных рядовых нет — герои не считаются)";
            }
            return $"переработано пленных: {butchered}, получено мяса: {meat}"
                + $" (осталось пленных {MobileParty.MainParty.PrisonRoster.TotalManCount})";
        }

        // ---- /eqprisoners:N — по N пленных каждой расы в отряде игрока при быстром старте
        // (tools/../run.ps1 -Prisoners) — готовый материал для equestria.butcher_prisoners без
        // похода в бой за живыми пленными.

        private const string ArgPrefix = "/eqprisoners:";
        private static int _perRace;
        private static bool _done;
        private static DateTime _mapSeenAt = DateTime.MinValue;

        public static void CheckRequest()
        {
            foreach (string arg in Environment.GetCommandLineArgs())
            {
                if (arg.StartsWith(ArgPrefix, StringComparison.OrdinalIgnoreCase)
                    && int.TryParse(arg.Substring(ArgPrefix.Length), out int n) && n > 0)
                {
                    _perRace = n;
                    EquestriaCrashLog.Log("пленные по расам: запрошено по " + n + " на расу");
                }
            }
        }

        // Та же пауза после появления карты, что у смотра рас (EquestriaRaceParty) — сразу после
        // старта кампания ещё доигрывает своё начало.
        public static void Tick()
        {
            if (_perRace <= 0 || _done)
            {
                return;
            }
            if (!(GameStateManager.Current?.ActiveState is MapState) || Campaign.Current == null
                || MobileParty.MainParty == null)
            {
                return;
            }
            if (_mapSeenAt == DateTime.MinValue)
            {
                _mapSeenAt = DateTime.UtcNow;
                return;
            }
            if ((DateTime.UtcNow - _mapSeenAt).TotalSeconds < 2)
            {
                return;
            }
            _done = true;
            EquestriaCrashLog.Try("пленные по расам: заселение", Populate);
        }

        private static void Populate()
        {
            var names = TaleWorlds.Core.FaceGen.GetRaceNames();
            if (names == null || names.Length == 0)
            {
                EquestriaCrashLog.Warn("пленные по расам: список рас пуст — skins не загрузились");
                return;
            }
            int total = 0;
            var report = new List<string>();
            for (int race = 0; race < names.Length; race++)
            {
                if (names[race] == "human")
                {
                    continue;
                }
                var troop = BasicTroopOfRace(race);
                if (troop == null)
                {
                    EquestriaCrashLog.Warn("пленные по расам: нет рядового бойца расы " + names[race]);
                    continue;
                }
                MobileParty.MainParty.PrisonRoster.AddToCounts(troop, _perRace);
                report.Add(names[race] + "=" + troop.StringId);
                total += _perRace;
            }
            EquestriaCrashLog.Note($"пленные по расам: добавлено {total} ({string.Join(", ", report)})");
        }

        /// <summary>Самый младший небольшой боец этой расы — тот же, кого набирают культуры,
        /// заведённые под эту расу (см. src/EquestriaMercCamp.cs CampSpots — там же соответствие
        /// держава-раса). Героев и шаблоны не берём — нужен обычный рядовой персонаж.</summary>
        private static CharacterObject BasicTroopOfRace(int race)
        {
            var candidates = CharacterObject.All
                .Where(c => c != null && !c.IsHero && !c.IsTemplate && c.Race == race
                            && c.Occupation == Occupation.Soldier)
                .ToList();
            return candidates.FirstOrDefault(c => c.IsBasicTroop) ?? candidates.FirstOrDefault();
        }

        // ---- кнопка в окне отряда (строка пленного, рядом с "Нанять") ----

        // _partyScreenLogic/_partyVm — protected readonly на PartyCharacterVM, декомпилировано:
        // не публичные, нужна рефлексия.
        private static readonly FieldInfo PartyScreenLogicField =
            AccessTools.Field(typeof(PartyCharacterVM), "_partyScreenLogic");
        private static readonly FieldInfo PartyVmField =
            AccessTools.Field(typeof(PartyCharacterVM), "_partyVm");

        [HarmonyPatch(typeof(PartyCharacterVM), "ExecuteExecuteTroop")]
        private static class ButtonPatch
        {
            // false — пропускаем настоящий метод целиком (для рядового пленного там и так
            // IsExecutable=false, делать ему нечего); true — геройская казнь идёт как в игре.
            //
            // Side==Right: в этом экране (PartyVM) это буквально "свой" — IsPrisonerOfPlayer так и
            // определён (декомпилировано), а MainPartyPrisoners/OtherPartyPrisoners заполняются по
            // этому же Side. Кнопка видна и у Left (если когда-то найдётся экран, где рядовой
            // пленный чужой стороны тоже IsRecruitablePrisoner) — но убирать строку оттуда нечем
            // (там OtherPartyPrisoners, не MainPartyPrisoners), поэтому на всякий случай не трогаем.
            private static bool Prefix(PartyCharacterVM __instance)
            {
                if (__instance?.Character == null || __instance.Character.IsHero
                    || __instance.Type != PartyScreenLogic.TroopType.Prisoner
                    || __instance.Side != PartyScreenLogic.PartyRosterSide.Right)
                {
                    return true;
                }
                EquestriaCrashLog.Try("переработка пленных (кнопка)", () => ButcherFromScreen(__instance));
                return false;
            }
        }

        // Подсказка нашей кнопки. ExecutePrisonerHint (их BasicTooltipViewModel, декомпилировано)
        // зовёт как раз этот метод с (Troop.Character, IsExecutable) — для рядового пленного
        // IsExecutable всегда false, и без патча там был бы их текст "нельзя казнить не-героя".
        // Героев не трогаем (return без подмены) — у них подсказка про казнь должна остаться своя.
        [HarmonyPatch(typeof(PartyScreenLogic), "GetExecutableReasonString")]
        private static class HintPatch
        {
            private static void Postfix(CharacterObject character, ref string __result)
            {
                if (character != null && !character.IsHero)
                {
                    __result = new TextObject("{=eq_prisoner_butcher_hint}Turn into mincemeat").ToString();
                }
            }
        }

        private static void ButcherFromScreen(PartyCharacterVM vm)
        {
            var logic = PartyScreenLogicField?.GetValue(vm) as PartyScreenLogic;
            var roster = logic?.PrisonerRosters?[(int)vm.Side];
            if (roster == null)
            {
                EquestriaCrashLog.Warn("переработка (кнопка): не нашёл ростер пленных экрана");
                return;
            }
            // Число берём из ростера заново, а НЕ из vm.Troop.Number: та снятая копия (TroopRosterElement,
            // декомпилировано) может быть устаревшей между кадрами — на этом держался баг 04.10.2026
            // (бесконечное мясо повторным кликом по строке, пока число на экране не обновилось).
            int index = roster.FindIndexOfTroop(vm.Character);
            int take = index >= 0 ? roster.GetElementNumber(index) : 0;
            if (take <= 0)
            {
                return;
            }
            roster.AddToCounts(vm.Character, -take);
            int meat = take * MeatPerPrisoner;
            var meatItem = MBObjectManager.Instance.GetObject<ItemObject>(MeatItemId);
            if (meatItem != null)
            {
                MobileParty.MainParty.ItemRoster.AddToCounts(meatItem, meat);
                int totalMeat = MobileParty.MainParty.ItemRoster.GetItemNumber(meatItem);
                // Своей строки в нижней панели денег не завести без форка ещё одного нативного
                // экрана (тот же риск, что уже дважды был с панелью времени и строкой пленного) —
                // поэтому сразу видно всплывающим уведомлением, как деньги/опыт в бою.
                InformationManager.DisplayMessage(new InformationMessage(
                    new TextObject("{=eq_butcher_meat}+{MEAT} meat (party total: {TOTAL})")
                        .SetTextVariable("MEAT", meat)
                        .SetTextVariable("TOTAL", totalMeat)
                        .ToString(), Colors.Yellow));
            }
            index = roster.FindIndexOfTroop(vm.Character);
            var partyVm = PartyVmField?.GetValue(vm) as PartyVM;
            if (index >= 0)
            {
                // пленные той же расы ещё остались (взяли не всех — такого при полном снятии пачки
                // не бывает, но на всякий случай обрабатываем): обновляем строку на новое число.
                vm.Troop = roster.GetElementCopyAtIndex(index);
                // RefreshValues() у этой строки (декомпилировано) число вообще не трогает — только
                // имя и подсказки. Число на экране — геттер Number, читающий Troop.Number, но без
                // явного уведомления Gauntlet об этом не узнает (баг 04.10.2026: "залипшая" пятёрка).
                vm.OnPropertyChanged("Number");
                vm.OnPropertyChanged("WoundedCount");
                vm.RefreshValues();
            }
            else
            {
                // Пачка кончилась целиком. ExecuteRemoveZeroCounts() не подходит — он решает по
                // Number==0, а Troop у нас остался старым (взяли всё за один клик, промежуточного
                // обновления не было), так и не узнал бы, что стало 0 (тот же баг 04.10.2026, другая
                // ветка). Убираем строку напрямую из списка, который реально рисует экран —
                // PartyVM.MainPartyPrisoners, публичное поле, без лишней рефлексии.
                partyVm?.MainPartyPrisoners?.Remove(vm);
            }
            EquestriaCrashLog.Log($"переработка (кнопка): {vm.Character.StringId} x{take} -> мяса {meat}");
        }
    }
}
