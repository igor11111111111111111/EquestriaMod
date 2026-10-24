using System;
using System.Collections.Generic;
using System.Linq;
using SandBox;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Actions;
using TaleWorlds.CampaignSystem.GameState;
using TaleWorlds.CampaignSystem.MapEvents;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.CampaignSystem.Siege;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.MountAndBlade;
using TaleWorlds.SaveSystem.Load;

namespace EquestriaMod
{
    // A long campaign run without the player: checks that the world lives for months and does not crash
    // on wars, sieges, weddings, births and deaths.
    //
    //   /eqlongrun:100   after the quick start, run time up to day 100, then save the game
    //                    as eq_longrun. The log gets a summary every 10 days and all major events.
    //   /eqload:eq_longrun   load this save straight from the main menu (load check).
    //   /eqgoto:651,660  at the start of the run move the player's party to this map point and do not
    //                    move it (for screenshots of the right place: the camera looks at the player).
    //   /eqfightbandits  at the start of the run engage looters in battle (check of their voice lines)
    //   /eqtalklord      at the start of the run open a conversation with our clan leader (check of lines
    //                    in different languages; the log gets "text language"
    //                    with a sample string)
    //   /eqcompanions:100  recruit that many random companions into the party (equestria.companions)
    //   /eqkingdom:kingdom_friendship  join a kingdom as a vassal with the player's clan - to see it
    //                    from the inside (kingdom screen: strength, wars, alliances). Kingdom ids are
    //                    in equestria_kingdoms.xml
    //   /eqgoto:x,y;x,y;...  tour: move the party through the points every TourSeconds seconds,
    //                    the log gets "tour: point N" (screenshots are taken by
    //                    tools	our.ps1).
    //
    // Markers for tools\selftest.ps1:
    //   "long run: saved"   - the run finished and the save was written
    //   "load: map opened"    - the save loaded up to the map
    public static class EquestriaLongRun
    {
        private const string RunPrefix = "/eqlongrun:";
        private const string LoadPrefix = "/eqload:";
        private const string GotoPrefix = "/eqgoto:";
        private static Vec2? _gotoPoint;
        private static bool _fightBandits;
        // /eqtalklord - at the start of the run open a conversation with our clan leader (check of lord
        // lines in different languages; which language is active is logged together with a sample string)
        private static bool _talkLord;
        // /eqcompanions:N - at the start of the run execute equestria.companions N (command check)
        private static int _companions;
        // /eqheroinfo:name;name - at the start of the run log equestria.hero_info for each of them
        private static readonly List<string> _heroInfo = new List<string>();
        // /eqnobanner - remove banners (banner items) from all heroes: checks whether they are what
        // leaves the party screen empty
        private static bool _noBanner;
        // /eqkingdom:id - at the start of the run join a kingdom as a vassal with the player's clan (to see
        // the kingdom from the inside: strength, wars, alliances). Ids: kingdom_equestria, kingdom_friendship etc.
        private static string _kingdom;
        private static readonly List<Vec2> _tour = new List<Vec2>();
        private static int _tourIndex;
        private static DateTime _tourNext;
        private const double TourSeconds = 14;
        public const string SaveName = "eq_longrun";

        // How many times faster than normal fast-forward (the game's default is 4). Too large a time step
        // per frame makes parties "jump over" their targets, so no more than 32.
        private const float SpeedUp = 32f;
        private const int ReportEveryDays = 10;

        private static int _targetDays = -1;
        private static string _loadName;

        private static bool _started;
        private static bool _finished;
        private static double _startDay;
        private static int _lastReportedDay = -1;
        private static string _lastState = "";

        private static DateTime _fpsWindow = DateTime.MinValue;
        private static int _frames;
        private static double _lastFps;
        private static DateTime _startedAt;

        private static bool _loadDone;

        // How many battles happened during the run and whether parties move: without a navmesh on the map
        // parties stand still and wars happen only on paper.
        public static int Battles;
        private static readonly Dictionary<string, Vec2> LastSeen = new Dictionary<string, Vec2>();

        public static bool IsRunning => _targetDays > 0 && _started && !_finished;

        public static void CheckRequest()
        {
            foreach (string arg in Environment.GetCommandLineArgs())
            {
                if (arg.StartsWith(RunPrefix, StringComparison.OrdinalIgnoreCase)
                    && int.TryParse(arg.Substring(RunPrefix.Length), out int days) && days > 0)
                {
                    _targetDays = days;
                    EquestriaCrashLog.Log("долгий прогон: запрошено дней " + days);
                }
                if (string.Equals(arg, "/eqfightbandits", StringComparison.OrdinalIgnoreCase))
                {
                    _fightBandits = true;
                }
                if (string.Equals(arg, "/eqtalklord", StringComparison.OrdinalIgnoreCase))
                {
                    _talkLord = true;
                }
                if (arg.StartsWith("/eqcompanions:", StringComparison.OrdinalIgnoreCase)
                    && int.TryParse(arg.Substring("/eqcompanions:".Length), out int companions))
                {
                    _companions = companions;   // self-check of the equestria.companions command
                }
                if (arg.StartsWith("/eqheroinfo:", StringComparison.OrdinalIgnoreCase))
                {
                    _heroInfo.AddRange(arg.Substring("/eqheroinfo:".Length).Split(';'));
                }
                if (string.Equals(arg, "/eqnobanner", StringComparison.OrdinalIgnoreCase))
                {
                    _noBanner = true;
                }
                if (arg.StartsWith("/eqkingdom:", StringComparison.OrdinalIgnoreCase))
                {
                    _kingdom = arg.Substring("/eqkingdom:".Length);
                }
                if (arg.StartsWith(GotoPrefix, StringComparison.OrdinalIgnoreCase))
                {
                    foreach (string point in arg.Substring(GotoPrefix.Length).Split(';'))
                    {
                        string[] xy = point.Split(',');
                        if (xy.Length == 2
                            && float.TryParse(xy[0], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out float gx)
                            && float.TryParse(xy[1], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out float gy))
                        {
                            _tour.Add(new Vec2(gx, gy));
                        }
                    }
                    if (_tour.Count > 0)
                    {
                        _gotoPoint = _tour[0];
                        EquestriaCrashLog.Log($"перенос игрока: точек {_tour.Count}, первая {_tour[0]}");
                    }
                }
                if (arg.StartsWith(LoadPrefix, StringComparison.OrdinalIgnoreCase))
                {
                    _loadName = arg.Substring(LoadPrefix.Length);
                    EquestriaCrashLog.Log("загрузка: запрошено сохранение " + _loadName);
                }
            }
        }

        public static void Tick()
        {
            var state = GameStateManager.Current?.ActiveState;
            if (state == null)
            {
                return;
            }

            if (_loadName != null && state is InitialState)
            {
                string name = _loadName;
                _loadName = null;
                LoadSave(name);
                return;
            }

            if (_targetDays <= 0 && !_loadDone)
            {
                return;
            }

            // A state change during the run is the main hint of where it stalled: battle, menu, dialogue.
            string stateName = state.GetType().Name;
            if (stateName != _lastState)
            {
                EquestriaCrashLog.Log("состояние игры: " + stateName);
                _lastState = stateName;
            }

            if (!(state is MapState) || Campaign.Current == null)
            {
                return;
            }

            if (_loadDone)
            {
                _loadDone = false;
                EquestriaCrashLog.Try("загрузка: проверка мира", ReportAfterLoad);
                return;
            }

            if (_started && _tour.Count > 1 && _tourIndex < _tour.Count && DateTime.Now >= _tourNext)
            {
                EquestriaCrashLog.Try("обход", TourStep);
            }

            if (_finished || _targetDays <= 0)
            {
                return;
            }

            if (!_started)
            {
                EquestriaCrashLog.Try("долгий прогон: старт", Start);
                return;
            }

            CountFrames();
            KeepTimeRunning();

            int day = (int)(CampaignTime.Now.ToDays - _startDay);
            if (day >= _lastReportedDay + ReportEveryDays)
            {
                _lastReportedDay = day;
                EquestriaCrashLog.Try("долгий прогон: сводка", () => Summary(day));
            }
            if (day >= _targetDays)
            {
                _finished = true;
                EquestriaCrashLog.Try("долгий прогон: сохранение", Finish);
            }
        }

        private static void Start()
        {
            _started = true;
            _startedAt = DateTime.Now;
            _startDay = CampaignTime.Now.ToDays;
            // Nobody touches the player's party: otherwise the very first bandit opens the battle screen and time stops.
            MobileParty.MainParty.IgnoreByOtherPartiesTill(CampaignTime.Never);
            Campaign.Current.SpeedUpMultiplier = SpeedUp;
            // A check of the map itself: order the player's party to go to a foreign capital. If it does not
            // move, the problem is not AI decisions but that no path can be built on the map at all.
            // We go to a point next to the town, not into the town itself: entering a town opens a menu, and
            // while it is open the map stops moving parties - the whole run freezes.
            var target = Settlement.Find("town_empire_3");
            if (_gotoPoint.HasValue)
            {
                MobileParty.MainParty.Position = new CampaignVec2(_gotoPoint.Value, true);
                MobileParty.MainParty.SetMoveModeHold();
                EquestriaCrashLog.Log($"перенос игрока: отряд в {MobileParty.MainParty.GetPosition2D}");
            }
            else if (target != null)
            {
                var near = new CampaignVec2(target.GetPosition2D + new Vec2(-8f, -8f), true);
                MobileParty.MainParty.SetMoveGoToPoint(near, MobileParty.NavigationType.Default);
                EquestriaCrashLog.Log($"проверка пути: игроку приказано идти к {target.Name}, "
                    + $"от {MobileParty.MainParty.GetPosition2D} до {near.ToVec2()}");
            }
            if (_fightBandits || _talkLord)
            {
                // Which language is active and what the game sees for our keys: if the language file was not
                // picked up, this will be empty instead of a line - and that will show on a screenshot too.
                EquestriaCrashLog.Log("язык текста: " + TaleWorlds.Localization.MBTextManager.ActiveTextLanguage
                    + "; eq_lord_meet_1 = «" + new TaleWorlds.Localization.TextObject("{=eq_lord_meet_1}").ToString()
                    + "»; eq_surrender_1 = «" + new TaleWorlds.Localization.TextObject("{=eq_surrender_1}").ToString()
                    + "»; ji2eenPE = «" + new TaleWorlds.Localization.TextObject("{=ji2eenPE}").ToString() + "»");
            }
            if (_fightBandits)
            {
                EquestriaCrashLog.Log("бой с разбойниками: " + EquestriaDebugCommands.FightBandits(new List<string>()));
                _finished = true;   // do not run time any further: a dialogue is open
            }
            else if (_talkLord)
            {
                EquestriaCrashLog.Log("разговор с лордом: " + EquestriaDebugCommands.TalkToLord(new List<string>()));
                _finished = true;
            }
            if (!string.IsNullOrEmpty(_kingdom))
            {
                var kingdom = Kingdom.All.FirstOrDefault(k => k.StringId == _kingdom);
                if (kingdom == null)
                {
                    EquestriaCrashLog.Warn("держава игрока: нет державы с id " + _kingdom + "; есть: "
                        + string.Join(", ", Kingdom.All.Select(k => k.StringId)));
                }
                else
                {
                    TaleWorlds.CampaignSystem.Actions.ChangeKingdomAction.ApplyByJoinToKingdom(
                        Clan.PlayerClan, kingdom, CampaignTime.Never, false);
                    EquestriaCrashLog.Log($"держава игрока: клан вступил в «{kingdom.Name}» вассалом");
                }
            }
            if (_companions > 0)
            {
                EquestriaCrashLog.Log("спутники: " + EquestriaDebugCommands.Companions(
                    new List<string> { _companions.ToString() }));
            }
            if (_noBanner)
            {
                int stripped = 0;
                foreach (var hero in Hero.AllAliveHeroes)
                {
                    foreach (var equipment in new[] { hero.BattleEquipment, hero.CivilianEquipment })
                    {
                        for (int i = 0; i < 12 && equipment != null; i++)
                        {
                            if (equipment[i].Item != null && equipment[i].Item.ItemType == ItemObject.ItemTypeEnum.Banner)
                            {
                                equipment[i] = EquipmentElement.Invalid;
                                stripped++;
                            }
                        }
                    }
                }
                EquestriaCrashLog.Log("штандарты сняты: " + stripped);
            }
            foreach (string who in _heroInfo)
            {
                EquestriaCrashLog.Log("герой: " + EquestriaDebugCommands.HeroInfo(new List<string> { who }));
            }
            EquestriaCrashLog.Log("модель проходимости: " + Campaign.Current.Models.PartyNavigationModel.GetType().Name);
            EquestriaCrashLog.Note($"долгий прогон: старт, цель {_targetDays} дн., ускорение x{SpeedUp}, "
                + $"дата {CampaignTime.Now}");
            Summary(0);
            _lastReportedDay = 0;
        }

        private static void TourStep()
        {
            var point = _tour[_tourIndex];
            MobileParty.MainParty.Position = new CampaignVec2(point, true);
            MobileParty.MainParty.SetMoveModeHold();
            _tourIndex++;
            _tourNext = DateTime.Now.AddSeconds(TourSeconds);
            EquestriaCrashLog.Log($"обход: точка {_tourIndex} ({point.x:0}, {point.y:0})");
        }

        private static void KeepTimeRunning()
        {
            // The player opened another screen over the map themselves (save, inventory, encyclopedia…) -
            // do not interfere: otherwise the code below closed the name input window on "Save as"
            // ("Save as"), and the game stayed stuck on the save screen (noticed 10.10.2026 in -MixedBirths).
            var top = TaleWorlds.ScreenSystem.ScreenManager.TopScreen;
            if (top != null && top.GetType().Name != "MapScreen")
            {
                return;
            }
            // Question windows (offers to join, weddings etc.) pause time - close them.
            if (InformationManager.IsAnyInquiryActive())
            {
                EquestriaCrashLog.Log("долгий прогон: закрыто окно с вопросом");
                InformationManager.HideInquiry();
            }
            if (MBInformationManager.GetIsAnySceneNotificationActive() == true)
            {
                EquestriaCrashLog.Log("долгий прогон: закрыта сценка");
                MBInformationManager.HideSceneNotification();
            }
            var campaign = Campaign.Current;
            if (campaign.TimeControlMode != CampaignTimeControlMode.UnstoppableFastForward)
            {
                campaign.TimeControlMode = CampaignTimeControlMode.UnstoppableFastForward;
            }
            if (campaign.SpeedUpMultiplier != SpeedUp)
            {
                campaign.SpeedUpMultiplier = SpeedUp;
            }
        }

        private static void CountFrames()
        {
            _frames++;
            var now = DateTime.Now;
            if (_fpsWindow == DateTime.MinValue)
            {
                _fpsWindow = now;
            }
            double seconds = (now - _fpsWindow).TotalSeconds;
            if (seconds >= 5)
            {
                _lastFps = _frames / seconds;
                _frames = 0;
                _fpsWindow = now;
            }
        }

        private static void Summary(int day)
        {
            var kingdoms = Kingdom.All.Where(k => !k.IsEliminated).ToList();
            int clans = Clan.All.Count(c => !c.IsEliminated && !c.IsBanditFaction);
            int alive = Hero.AllAliveHeroes.Count;
            int dead = Hero.DeadOrDisabledHeroes.Count;
            int wars = 0;
            for (int i = 0; i < kingdoms.Count; i++)
            {
                for (int j = i + 1; j < kingdoms.Count; j++)
                {
                    if (kingdoms[i].IsAtWarWith(kingdoms[j]))
                    {
                        wars++;
                    }
                }
            }
            int nonPony = Hero.AllAliveHeroes.Count(h => h.CharacterObject != null
                && h.CharacterObject.Race != TaleWorlds.Core.FaceGen.GetRaceOrDefault(EquestriaMane.RaceId));
            EquestriaCrashLog.Note($"долгий прогон: день {day}, {CampaignTime.Now}, "
                + $"реальное время {(int)(DateTime.Now - _startedAt).TotalSeconds} с, кадров/с {_lastFps:0}");
            // Movement: compare lord party positions with the previous summary.
            int moved = 0, stood = 0;
            float maxStep = 0f;
            foreach (var party in MobileParty.All.Where(p => p.LeaderHero != null))
            {
                Vec2 now = party.GetPosition2D;
                if (LastSeen.TryGetValue(party.StringId, out Vec2 before))
                {
                    float step = before.Distance(now);
                    if (step > 0.5f)
                    {
                        moved++;
                        maxStep = Math.Max(maxStep, step);
                    }
                    else
                    {
                        stood++;
                    }
                }
                LastSeen[party.StringId] = now;
            }
            // What lords are doing: if they all sit in their towns and go nowhere, the problem is not the map
            // but AI decisions (no targets, no troops, no money).
            var lords = MobileParty.All.Where(p => p.LeaderHero != null).ToList();
            int inside = lords.Count(p => p.CurrentSettlement != null);
            int withTarget = lords.Count(p => p.TargetSettlement != null);
            int movingNow = lords.Count(p => p.IsMoving);
            var behaviours = lords.GroupBy(p => p.DefaultBehavior.ToString())
                .OrderByDescending(g => g.Count()).Select(g => g.Key + " " + g.Count());
            EquestriaCrashLog.Log($"  лорды: в поселениях {inside}, с целью {withTarget}, в движении {movingNow}; "
                + $"занятия: {string.Join(", ", behaviours)}");
            // Distances between settlements: the AI uses them to choose whom it can reach and whom not.
            var kanterlot = Settlement.Find("town_empire_0");
            var yak = Settlement.Find("town_empire_3");
            if (kanterlot != null && yak != null)
            {
                var distances = Campaign.Current.Models.MapDistanceModel;
                float far = distances.GetDistance(kanterlot, yak, false, false, MobileParty.NavigationType.Default);
                float near = distances.GetDistance(kanterlot, Settlement.Find("town_empire_1"), false, false,
                    MobileParty.NavigationType.Default);
                EquestriaCrashLog.Log($"  расстояния: Кантерлот–Лас-Пегасус {far:0.0}, Кантерлот–соседний город {near:0.0}, "
                    + $"среднее между ближайшими городами "
                    + $"{Campaign.Current.GetAverageDistanceBetweenClosestTwoTownsWithNavigationType(MobileParty.NavigationType.Default):0.0}, "
                    + $"предел связи {distances.GetMaximumDistanceBetweenTwoConnectedSettlements(MobileParty.NavigationType.Default):0.0}");
            }
            // Ask the game ourselves what the first lord has decided: that shows whether he has any behaviour
            // options at all. An empty list means no target passed the selection.
            var thinker = MobileParty.All.FirstOrDefault(p => p.LeaderHero != null && p != MobileParty.MainParty);
            if (thinker != null)
            {
                var think = new PartyThinkParams(thinker);
                think.Reset(thinker);
                CampaignEventDispatcher.Instance.AiHourlyTick(thinker, think);
                var best = think.AIBehaviorScores.OrderByDescending(s => s.Item2).Take(3)
                    .Select(s => $"{s.Item1.AiBehavior} → {s.Item1.Party?.Name} {s.Item2:0.000}");
                EquestriaCrashLog.Log($"  передвижение {thinker.LeaderHero?.Name}: способность {thinker.NavigationCapability}, "
                    + $"по суше {thinker.HasLandNavigationCapability}, грань под отрядом "
                    + $"{thinker.CurrentNavigationFace.FaceIndex} (годна {thinker.CurrentNavigationFace.IsValid()}), "
                    + $"в море {thinker.IsCurrentlyAtSea}, цель-порт {thinker.IsTargetingPort}");
                EquestriaCrashLog.Log($"  размышление {thinker.LeaderHero?.Name}: вариантов "
                    + $"{think.AIBehaviorScores.Count}, лучшие: {string.Join("; ", best)}");
            }
            var player = MobileParty.MainParty;
            EquestriaCrashLog.Log($"  проверка пути: игрок в {player.GetPosition2D}, "
                + $"меню {Campaign.Current.CurrentMenuContext?.GameMenu?.StringId ?? "нет"}, "
                + $"цель {player.TargetSettlement?.Name}, занятие {player.DefaultBehavior}, "
                + $"идёт {player.IsMoving}, скорость {player.Speed:0.00}");
            // Stuck at the gates: the target is a settlement, they stand still. Print the entry conditions.
            foreach (var stuck in lords.Where(p => p.TargetSettlement != null && !p.IsMoving
                         && p.CurrentSettlement == null).Take(3))
            {
                var target = stuck.TargetSettlement;
                EquestriaCrashLog.Log($"  застрял {stuck.Name}: цель {target.Name}, до ворот "
                    + $"{stuck.GetPosition2D.Distance(target.GatePosition.ToVec2()):0.000}, "
                    + $"кратко {stuck.ShortTermBehavior} → {stuck.ShortTermTargetSettlement?.Name}, "
                    + $"переход {stuck.IsTransitionInProgress}, "
                    + $"море {stuck.IsCurrentlyAtSea}, порт {stuck.IsTargetingPort}, бой {stuck.MapEvent != null}, "
                    + $"армия {stuck.Army != null}, взаимодействие {stuck.Ai.AiBehaviorInteractable?.GetType().Name}, "
                    + $"враги {target.MapFaction?.IsAtWarWith(stuck.MapFaction)}, осада {target.SiegeEvent != null}");
            }
            int inactive = lords.Count(p => !p.IsActive);
            int aiOff = lords.Count(p => p.Ai != null && p.Ai.IsDisabled);
            int noTroops = lords.Count(p => p.MemberRoster.TotalManCount <= 1);
            EquestriaCrashLog.Log($"  лорды: неактивных {inactive}, ИИ выключен у {aiOff}, "
                + $"без войска {noTroops}, всего {lords.Count}");
            var lord = lords.FirstOrDefault(p => p != MobileParty.MainParty);
            if (lord != null)
            {
                EquestriaCrashLog.Log($"  лорд {lord.LeaderHero?.Name} ({lord.LeaderHero?.Clan?.Name}): "
                    + $"воинов {lord.MemberRoster.TotalManCount}, деньги {lord.LeaderHero?.Gold}, "
                    + $"активен {lord.IsActive}, ИИ выключен {lord.Ai?.IsDisabled}, "
                    + $"решения запрещены {lord.Ai?.DoNotMakeNewDecisions}, "
                    + $"дом {lord.LeaderHero?.HomeSettlement?.Name}, положение {lord.GetPosition2D}");
            }
            var sample = lords.FirstOrDefault();
            if (sample != null)
            {
                EquestriaCrashLog.Log($"  пример: {sample.Name}, воинов {sample.MemberRoster.TotalManCount}, "
                    + $"в {sample.CurrentSettlement?.Name?.ToString() ?? "поле"}, цель {sample.TargetSettlement?.Name}, "
                    + $"занятие {sample.DefaultBehavior}, скорость {sample.Speed:0.00}");
            }
            EquestriaCrashLog.Log($"  отряды лордов: сдвинулись {moved}, стоят {stood}, "
                + $"самый длинный путь {maxStep:0.0}; боёв всего {Battles}, армий {kingdoms.Sum(k => k.Armies.Count)}");
            EquestriaCrashLog.Log($"  держав {kingdoms.Count}, войн между ними {wars}, кланов {clans}, "
                + $"героев живых {alive} (не пони {nonPony}), мёртвых {dead}, "
                + $"отрядов {MobileParty.All.Count}");
            foreach (var k in kingdoms)
            {
                int towns = k.Settlements.Count(s => s.IsTown);
                int castles = k.Settlements.Count(s => s.IsCastle);
                int villages = k.Settlements.Count(s => s.IsVillage);
                EquestriaCrashLog.Log($"  {k.StringId} «{k.Name}»: правитель {k.Leader?.Name}, кланов {k.Clans.Count}, "
                    + $"города {towns}, замки {castles}, деревни {villages}, сила {k.CurrentTotalStrength:0}");
            }
        }

        private static void Finish()
        {
            EquestriaCrashLog.Note($"долгий прогон: цель достигнута за {(int)(DateTime.Now - _startedAt).TotalSeconds} с, сохраняю");
            Campaign.Current.TimeControlMode = CampaignTimeControlMode.Stop;
            Campaign.Current.SaveHandler.SaveAs(SaveName);
        }

        // Called from the behaviour on the save-finished event.
        public static void OnSaveOver(bool ok, string name)
        {
            if (_finished)
            {
                EquestriaCrashLog.Note($"долгий прогон: сохранено ({(ok ? "успешно" : "ОШИБКА")}, {name})");
            }
        }

        private static void LoadSave(string name)
        {
            EquestriaCrashLog.Try("загрузка сохранения " + name, () =>
            {
                if (!MBSaveLoad.IsSaveGameFileExists(name))
                {
                    EquestriaCrashLog.Warn("загрузка: сохранения нет — " + name);
                    return;
                }
                LoadResult result = MBSaveLoad.LoadSaveGameData(name);
                if (result == null || !result.Successful)
                {
                    EquestriaCrashLog.Warn("загрузка: не прочиталось — "
                        + (result?.Errors == null ? "нет данных" : string.Join("; ", result.Errors.Select(e => e.ToString()))));
                    return;
                }
                EquestriaCrashLog.Note("загрузка: данные прочитаны, запускаю кампанию");
                _loadDone = true;
                MBGameManager.StartNewGame(new SandBoxGameManager(result));
            });
        }

        private static void ReportAfterLoad()
        {
            int pony = TaleWorlds.Core.FaceGen.GetRaceOrDefault(EquestriaMane.RaceId);
            var hero = Hero.MainHero;
            EquestriaCrashLog.Log($"загрузка: дата {CampaignTime.Now}, игрок {hero?.Name}, "
                + $"раса игрока {hero?.CharacterObject?.Race} (пони = {pony})");
            _startedAt = DateTime.Now;
            Summary((int)CampaignTime.Now.ToDays);
            EquestriaCrashLog.Note("загрузка: карта открыта");
        }
    }

    // Subscription to campaign events: everything major that happened during the run goes into the log.
    public class EquestriaLongRunBehavior : CampaignBehaviorBase
    {
        public override void RegisterEvents()
        {
            CampaignEvents.OnSaveOverEvent.AddNonSerializedListener(this, EquestriaLongRun.OnSaveOver);
            CampaignEvents.MapEventEnded.AddNonSerializedListener(this, mapEvent =>
            {
                EquestriaLongRun.Battles++;
                if (EquestriaLongRun.Battles <= 20)
                {
                    Event($"бой: {mapEvent.AttackerSide?.LeaderParty?.Name} против {mapEvent.DefenderSide?.LeaderParty?.Name}"
                        + $" у {mapEvent.MapEventSettlement?.Name}, тип {mapEvent.EventType}");
                }
            });
            CampaignEvents.WarDeclared.AddNonSerializedListener(this, (a, b, detail) =>
                Event($"война: {a.Name} против {b.Name} ({detail})"));
            CampaignEvents.MakePeace.AddNonSerializedListener(this, (a, b, detail) =>
                Event($"мир: {a.Name} и {b.Name} ({detail})"));
            CampaignEvents.HeroKilledEvent.AddNonSerializedListener(this, (victim, killer, detail, _) =>
                Event($"смерть: {victim.Name} ({victim.Clan?.Name}), причина {detail}, убийца {killer?.Name}"));
            CampaignEvents.OnGivenBirthEvent.AddNonSerializedListener(this, (mother, children, stillborn) =>
                Event($"рождение: у {mother.Name} детей {children.Count}"
                    + (children.Count > 0 ? $" ({string.Join(", ", children.Select(c => c.Name + " раса " + c.CharacterObject.Race))})" : "")
                    + (stillborn > 0 ? $", мертворождённых {stillborn}" : "")));
            CampaignEvents.BeforeHeroesMarried.AddNonSerializedListener(this, (a, b, _) =>
                Event($"свадьба: {a.Name} и {b.Name}"));
            CampaignEvents.OnSiegeEventStartedEvent.AddNonSerializedListener(this, siege =>
                Event($"осада: {siege.BesiegedSettlement?.Name} ({siege.BesiegerCamp?.LeaderParty?.Name})"));
            CampaignEvents.OnSettlementOwnerChangedEvent.AddNonSerializedListener(this,
                (settlement, openToClaim, newOwner, oldOwner, capturer, detail) =>
                    Event($"смена владельца: {settlement.Name} — {oldOwner?.Name} -> {newOwner?.Name} ({detail})"));
            CampaignEvents.OnClanDestroyedEvent.AddNonSerializedListener(this, clan =>
                Event($"клан исчез: {clan.Name}"));
            CampaignEvents.KingdomDestroyedEvent.AddNonSerializedListener(this, kingdom =>
                Event($"держава пала: {kingdom.Name}"));
            CampaignEvents.OnClanChangedKingdomEvent.AddNonSerializedListener(this, (clan, oldK, newK, detail, _) =>
                Event($"клан {clan.Name}: {oldK?.Name} -> {newK?.Name} ({detail})"));
            CampaignEvents.RebellionFinished.AddNonSerializedListener(this, (settlement, clan) =>
                Event($"восстание: {settlement.Name}, клан {clan?.Name}"));
        }

        public override void SyncData(IDataStore dataStore)
        {
        }

        private static void Event(string text)
        {
            if (Campaign.Current == null)
            {
                return;
            }
            EquestriaCrashLog.Log($"[{CampaignTime.Now}] {text}");
        }
    }
}
