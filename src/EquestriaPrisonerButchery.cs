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
    // Butchering prisoners into meat (equestria_items.xml: eq_prisoner_meat).
    //
    // In the mod all troops are beasts (ponies, griffons, dragons, yaks, changelings, deer), some races
    // are clearly predators or omnivores — turning prisoners into supplies fits the lore just like the
    // orcs in The Old Realms. TOR was not found on disk (apparently deleted — the link in the project
    // memory already noted this), so comparing with their implementation directly was not possible —
    // made from scratch following general Bannerlord rules (TroopRoster/ItemRoster), not copied.
    //
    // Two interfaces: the console command (below) and a button right in the party screen, in the
    // prisoner's row — see ButtonPatch and the fork of SandBox\GUI\Prefabs\Party\PartyTroopTuple.xml.
    // The engine has a ready "Execute" button in the same row — but its Code
    // (PartyCommandCode.ExecuteTroop) strictly checks character.IsHero (PartyScreenLogic.IsExecutable,
    // decompiled 04.10.2026) and will not work for regular troops with any external patch — so instead
    // of reusing the command the butcher button intercepts the click itself
    // (PartyCharacterVM.ExecuteExecuteTroop) and for regular prisoners replaces it entirely, while hero
    // execution is left alone (return true — let the engine execute the hero as usual). Hero prisoners
    // are not touched at all — they have their own story fate (ransom, scripted execution).
    public static class EquestriaPrisonerButchery
    {
        public const string MeatItemId = "eq_prisoner_meat";

        // Meat per prisoner: less than the soldier would be worth as ransom or a recruit — otherwise
        // the butcher is always better than other ways to deal with a prisoner.
        private const int MeatPerPrisoner = 2;

        /// <summary>Butcher up to count regular prisoners of the party. Returns (how many butchered,
        /// how much meat obtained).</summary>
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

        // equestria.butcher_prisoners [how many] — butcher your own party's prisoners
        // (without a number — all regular ones at once)
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

        // ---- /eqprisoners:N — N prisoners of each race in the player's party on quick start
        // (tools/../run.ps1 -Prisoners) — ready material for equestria.butcher_prisoners without
        // going to battle for live prisoners.

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

        // The same pause after the map appears as in the race review (EquestriaRaceParty) — right after
        // the start the campaign is still playing out its beginning.
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

        /// <summary>The lowest-tier soldier of this race — the same one recruited by the cultures
        /// set up for this race (see src/EquestriaMercCamp.cs CampSpots — the kingdom-race mapping is
        /// there too). Heroes and templates are skipped — a regular rank-and-file character is needed.</summary>
        private static CharacterObject BasicTroopOfRace(int race)
        {
            var candidates = CharacterObject.All
                .Where(c => c != null && !c.IsHero && !c.IsTemplate && c.Race == race
                            && c.Occupation == Occupation.Soldier)
                .ToList();
            return candidates.FirstOrDefault(c => c.IsBasicTroop) ?? candidates.FirstOrDefault();
        }

        // ---- button in the party screen (prisoner row, next to "Recruit") ----

        // _partyScreenLogic/_partyVm — protected readonly on PartyCharacterVM, decompiled:
        // not public, reflection is needed.
        private static readonly FieldInfo PartyScreenLogicField =
            AccessTools.Field(typeof(PartyCharacterVM), "_partyScreenLogic");
        private static readonly FieldInfo PartyVmField =
            AccessTools.Field(typeof(PartyCharacterVM), "_partyVm");

        [HarmonyPatch(typeof(PartyCharacterVM), "ExecuteExecuteTroop")]
        private static class ButtonPatch
        {
            // false — skip the real method entirely (for a regular prisoner IsExecutable=false there
            // anyway, it has nothing to do); true — hero execution goes as in the game.
            //
            // Side==Right: in this screen (PartyVM) it literally means "ours" — IsPrisonerOfPlayer is
            // defined that way (decompiled), and MainPartyPrisoners/OtherPartyPrisoners are filled by
            // this same Side. The button is also visible on Left (in case some screen turns up where a
            // regular prisoner of the other side is also IsRecruitablePrisoner) — but there is nothing
            // to remove the row from there with (it is OtherPartyPrisoners, not MainPartyPrisoners),
            // so to be safe we leave it alone.
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

        // Our button's tooltip. ExecutePrisonerHint (their BasicTooltipViewModel, decompiled)
        // calls exactly this method with (Troop.Character, IsExecutable) — for a regular prisoner
        // IsExecutable is always false, and without the patch it would show their text "cannot execute
        // a non-hero". Heroes are left alone (return without replacing) —
        // their execution tooltip must stay their own.
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
            // The number is read from the roster again, NOT from vm.Troop.Number: that snapshot copy
            // (TroopRosterElement, decompiled) may be stale between frames — that caused the bug of
            // 04.10.2026 (infinite meat by clicking the row again before the number on screen updated).
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
                // A row of our own in the bottom money panel cannot be added without forking one more
                // native screen (the same risk we already had twice with the time panel and the prisoner
                // row) — so it is shown right away as a pop-up notification, like money/XP in battle.
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
                // prisoners of the same race are still left (not all were taken — this does not happen
                // when the whole stack is removed, but handled just in case): update the row to the new number.
                vm.Troop = roster.GetElementCopyAtIndex(index);
                // This row's RefreshValues() (decompiled) does not touch the number at all — only the
                // name and tooltips. The number on screen is the Number getter reading Troop.Number, but
                // without an explicit notification Gauntlet will not know (bug 04.10.2026: a "stuck" five).
                vm.OnPropertyChanged("Number");
                vm.OnPropertyChanged("WoundedCount");
                vm.RefreshValues();
            }
            else
            {
                // The stack ran out entirely. ExecuteRemoveZeroCounts() does not fit — it decides by
                // Number==0, but our Troop stayed old (everything was taken in one click, there was no
                // intermediate update), so it would never learn it became 0 (the same bug 04.10.2026,
                // another branch). We remove the row directly from the list the screen actually draws —
                // PartyVM.MainPartyPrisoners, a public field, no extra reflection.
                partyVm?.MainPartyPrisoners?.Remove(vm);
            }
            EquestriaCrashLog.Log($"переработка (кнопка): {vm.Character.StringId} x{take} -> мяса {meat}");
        }
    }
}
