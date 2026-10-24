using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using HarmonyLib;
using TaleWorlds.Engine;
using TaleWorlds.InputSystem;
using TaleWorlds.Library;
using TaleWorlds.MountAndBlade;
using Path = System.IO.Path;

namespace EquestriaMod
{
    // Голосовые отклики на приказы в сцене боя. Реплики — файлы (.wav/.ogg) в Module\Sounds\<папка>:
    //   order_voice — открыли меню приказов (F1);
    //   order_move  — отдали приказ «переместиться на позицию»;
    //   order_charge — отдали приказ «в атаку» (F1, F3);
    //   order_retreat — отдали приказ «отступать»;
    //   order_follow — отдали приказ «за мной»;
    //   order_hold_fire — отдали приказ «прекратить огонь»;
    //   остальные 18 своих папок (order_advance, order_stop, order_infantry, ...) — каждая под
    //   свою команду (см. ShoutFolders ниже), озвучены 03.10.2026;
    //   order_other — то, чему своей папки так и не завели (на будущее — новые приказы движка).
    // Играет случайная реплика из папки. Чтобы заменить звуки, достаточно поменять файлы.
    //
    // Файлы играет программируемое событие FMOD "event:/Extra/voiceover" — так игра озвучивает
    // диалоги, свой звуковой банк собирать не нужно.
    //
    // order_voice/_move/_charge/_retreat/_follow пока на временных репликах из Equestria at War
    // (см. ИСТОЧНИК.txt рядом с ними) — остальные уже озвучены.
    public class EquestriaOrderVoice : MissionLogic
    {
        private const string VoiceEvent = "event:/Extra/voiceover";
        private const string MenuFolder = "order_voice";
        private const string MoveFolder = "order_move";
        private const string ChargeFolder = "order_charge";
        private const string RetreatFolder = "order_retreat";
        private const string FollowFolder = "order_follow";
        private const string HoldFireFolder = "order_hold_fire";
        private const string OtherFolder = "order_other";

        // 18 команд без своего OrderType (выбор оружия, построения, разворот, передача отряда) —
        // движок озвучивает их только «выкриком» (Agent.MakeVoice), приказ как таковой
        // OnOrderIssued не ловит. Играем их из MuteVanillaOrderShouts.Prefix (см. ниже), не
        // отсюда — там и так уже перехватывается нужный момент, чтобы заглушить ваниль.
        private const string AdvanceFolder = "order_advance";
        private const string FallBackFolder = "order_fall_back";
        private const string StopFolder = "order_stop";
        private const string MountFolder = "order_mount";
        private const string DismountFolder = "order_dismount";
        private const string FireAtWillFolder = "order_fire_at_will";
        private const string PickSpearsFolder = "order_pick_spears";
        private const string PickDefaultFolder = "order_pick_default";
        private const string FaceEnemyFolder = "order_face_enemy";
        private const string FaceDirectionFolder = "order_face_direction";
        private const string UseSiegeWeaponFolder = "order_use_siege_weapon";
        private const string UseLaddersFolder = "order_use_ladders";
        private const string AttackGateFolder = "order_attack_gate";
        private const string CommandDelegateFolder = "order_command_delegate";
        private const string CommandUndelegateFolder = "order_command_undelegate";
        private const string InfantryFolder = "order_infantry";
        private const string CavalryFolder = "order_cavalry";
        private const string ArchersFolder = "order_archers";
        private const string HorseArchersFolder = "order_horse_archers";
        private const string MixedFormationFolder = "order_mixed_formation";

        // Приказ -> папка с репликами
        private static readonly Dictionary<OrderType, string> OrderFolders = new Dictionary<OrderType, string>
        {
            { OrderType.Move, MoveFolder },
            { OrderType.MoveToLineSegment, MoveFolder },
            { OrderType.MoveToLineSegmentWithHorizontalLayout, MoveFolder },
            { OrderType.Charge, ChargeFolder },
            { OrderType.ChargeWithTarget, ChargeFolder },
            { OrderType.Retreat, RetreatFolder },
            { OrderType.FollowMe, FollowFolder },
            { OrderType.HoldFire, HoldFireFolder },
        };
        // Остальные приказы (строй, стоять, вперёд, огонь и прочие) озвучиваются общими репликами.

        private static readonly Dictionary<string, string[]> Clips = new Dictionary<string, string[]>();
        private readonly Random _random = new Random();
        private SoundEvent _playing;
        private OrderController _listening;

        public override void OnMissionTick(float dt)
        {
            base.OnMissionTick(dt);
            // Любой сбой здесь уронил бы весь бой (OnMissionTick зовётся каждый кадр без защиты),
            // поэтому всё внутри — под Try.
            EquestriaCrashLog.Try("голос приказов", Tick);
        }

        private void Tick()
        {
            var team = Mission?.PlayerTeam;
            // Приказы отдаёт только тот, у кого есть свои войска на поле.
            if (team == null || !team.IsPlayerGeneral && !team.IsPlayerSergeant)
            {
                return;
            }
            // Контроллер приказов появляется не сразу после начала боя — подписываемся, как только он есть.
            var controller = team.PlayerOrderController;
            if (controller != null && controller != _listening)
            {
                if (_listening != null)
                {
                    _listening.OnOrderIssued -= OnOrderIssued;
                }
                controller.OnOrderIssued += OnOrderIssued;
                _listening = controller;
            }
            if (Input.IsKeyPressed(InputKey.F1))
            {
                // Пока звучит прошлая реплика, новую не начинаем — частые нажатия слились бы в кашу.
                Play(MenuFolder, interrupt: false);
            }
        }

        private void OnOrderIssued(OrderType orderType, MBReadOnlyList<Formation> formations,
                                   OrderController controller, params object[] parameters)
        {
            // Приказы без своей папки сюда больше не подставляют order_other: у многих из них
            // (спешиться, сесть на коня, огонь по усмотрению, вперёд, назад, стоять и т.д.) ЕСТЬ
            // свой OrderType, и он срабатывает ПАРАЛЛЕЛЬНО с выкриком (Agent.MakeVoice) — тот уже
            // включает нужную реплику через MuteVanillaOrderShouts.PlayShoutReplacement. Если бы
            // мы тут всё равно играли order_other, это interrupt=true обрывало бы уже верно
            // начатую реплику и подменяло её заглушкой (замечено 03.10.2026). Поэтому играем
            // только то, что явно прописано в OrderFolders — остальное отдано выкрику целиком.
            if (!OrderFolders.TryGetValue(orderType, out string folder))
            {
                return;
            }
            // Приказ идёт сразу за меню F1, поэтому его реплика перебивает прошлую.
            EquestriaCrashLog.Try("голос приказов: " + orderType, () => Play(folder, interrupt: true));
        }

        private void Play(string folder, bool interrupt)
        {
            string[] clips = ClipsIn(folder);
            if (clips.Length == 0 || Mission?.Scene == null)
            {
                return;
            }
            if (_playing != null && _playing.IsValid && _playing.IsPlaying())
            {
                if (!interrupt)
                {
                    return;
                }
                _playing.Stop();
            }
            _playing?.Release();
            string clip = clips[_random.Next(clips.Length)];
            _playing = SoundEvent.CreateEventFromExternalFile(VoiceEvent, clip, Mission.Scene, false, false);
            _playing?.Play();
        }

        // Есть ли у нас реплики для этой папки — тогда ванильный выкрик командира не нужен.
        internal static bool HasClips(string folder)
        {
            return ClipsIn(folder).Length > 0;
        }

        // Ванильный голос командира -> наша папка, которая его заменяет.
        internal static readonly Dictionary<SkinVoiceManager.SkinVoiceType, string> ReplacedShouts =
            new Dictionary<SkinVoiceManager.SkinVoiceType, string>
            {
                { SkinVoiceManager.VoiceType.Everyone, MenuFolder },
                { SkinVoiceManager.VoiceType.Move, MoveFolder },
                { SkinVoiceManager.VoiceType.Charge, ChargeFolder },
                { SkinVoiceManager.VoiceType.Retreat, RetreatFolder },
                { SkinVoiceManager.VoiceType.Follow, FollowFolder },
                { SkinVoiceManager.VoiceType.Advance, AdvanceFolder },
                { SkinVoiceManager.VoiceType.FallBack, FallBackFolder },
                { SkinVoiceManager.VoiceType.Stop, StopFolder },
                { SkinVoiceManager.VoiceType.Mount, MountFolder },
                { SkinVoiceManager.VoiceType.Dismount, DismountFolder },
                { SkinVoiceManager.VoiceType.FireAtWill, FireAtWillFolder },
                { SkinVoiceManager.VoiceType.HoldFire, HoldFireFolder },
                { SkinVoiceManager.VoiceType.PickSpears, PickSpearsFolder },
                { SkinVoiceManager.VoiceType.PickDefault, PickDefaultFolder },
                { SkinVoiceManager.VoiceType.FaceEnemy, FaceEnemyFolder },
                { SkinVoiceManager.VoiceType.FaceDirection, FaceDirectionFolder },
                { SkinVoiceManager.VoiceType.UseSiegeWeapon, UseSiegeWeaponFolder },
                { SkinVoiceManager.VoiceType.UseLadders, UseLaddersFolder },
                { SkinVoiceManager.VoiceType.AttackGate, AttackGateFolder },
                { SkinVoiceManager.VoiceType.CommandDelegate, CommandDelegateFolder },
                { SkinVoiceManager.VoiceType.CommandUndelegate, CommandUndelegateFolder },
                // выбор отряда в меню приказов (пехота, конница, стрелки, все)
                { SkinVoiceManager.VoiceType.Infantry, InfantryFolder },
                { SkinVoiceManager.VoiceType.Cavalry, CavalryFolder },
                { SkinVoiceManager.VoiceType.Archers, ArchersFolder },
                { SkinVoiceManager.VoiceType.HorseArchers, HorseArchersFolder },
                { SkinVoiceManager.VoiceType.MixedFormation, MixedFormationFolder },
            };

        // Папки без своего OrderType — у них OnOrderIssued никогда не стреляет (см. комментарий у
        // констант выше), поэтому реплику играет сам MuteVanillaOrderShouts.Prefix, когда глушит
        // ванильный выкрик. Move/Charge/Retreat/Follow/HoldFire сюда НЕ входят — для них реплику
        // уже играет OnOrderIssued, второй раз звать не нужно (получилось бы двойное «ещё раз»).
        internal static readonly HashSet<string> ShoutOnlyFolders = new HashSet<string>
        {
            AdvanceFolder, FallBackFolder, StopFolder, MountFolder, DismountFolder, FireAtWillFolder,
            PickSpearsFolder, PickDefaultFolder, FaceEnemyFolder, FaceDirectionFolder,
            UseSiegeWeaponFolder, UseLaddersFolder, AttackGateFolder, CommandDelegateFolder,
            CommandUndelegateFolder, InfantryFolder, CavalryFolder, ArchersFolder, HorseArchersFolder,
            MixedFormationFolder,
        };

        // Зовётся из MuteVanillaOrderShouts.Prefix (статический контекст, своего инстанса нет) —
        // поэтому не private.
        internal void PlayShoutReplacement(string folder)
        {
            EquestriaCrashLog.Try("голос приказов (выкрик): " + folder, () => Play(folder, interrupt: true));
        }

        protected override void OnEndMission()
        {
            EquestriaCrashLog.Try("голос приказов: завершение", () =>
            {
                if (_listening != null)
                {
                    _listening.OnOrderIssued -= OnOrderIssued;
                    _listening = null;
                }
                _playing?.Stop();
                _playing?.Release();
            });
            _playing = null;
            base.OnEndMission();
        }

        private static string[] ClipsIn(string folder)
        {
            if (Clips.TryGetValue(folder, out var cached))
            {
                return cached;
            }
            // Библиотека лежит в <мод>\bin\Win64_Shipping_Client — поднимаемся на два уровня.
            string bin = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
            string path = Path.GetFullPath(Path.Combine(bin, "..", "..", "Sounds", folder));
            string[] found = Directory.Exists(path)
                ? Directory.GetFiles(path)
                    .Where(f => f.EndsWith(".wav", StringComparison.OrdinalIgnoreCase)
                                || f.EndsWith(".ogg", StringComparison.OrdinalIgnoreCase))
                    .OrderBy(f => f)
                    .ToArray()
                : new string[0];
            Clips[folder] = found;
            EquestriaCrashLog.Log($"голос приказов: {folder} — реплик {found.Length}");
            return found;
        }
    }

    // Глушим ванильный выкрик командира там, где играет наша реплика: иначе оба звучат разом.
    // Выкрик делает OrderController через Agent.MakeVoice у командира (игрока).
    // Ставится вручную из EquestriaPatches.ApplyLate — без атрибута [HarmonyPatch], чтобы
    // PatchAll не трогал его при загрузке мода.
    public static class MuteVanillaOrderShouts
    {
        public static void Apply(Harmony harmony)
        {
            harmony.Patch(AccessTools.Method(typeof(Agent), nameof(Agent.MakeVoice)),
                prefix: new HarmonyMethod(typeof(MuteVanillaOrderShouts), nameof(Prefix)));
        }

        private static bool Prefix(Agent __instance, SkinVoiceManager.SkinVoiceType voiceType)
        {
            try
            {
                if (!__instance.IsMainAgent)
                {
                    return true;
                }
                if (!(EquestriaOrderVoice.ReplacedShouts.TryGetValue(voiceType, out string folder)
                      && EquestriaOrderVoice.HasClips(folder)))
                {
                    return true;
                }
                // Move/Charge/Retreat/Follow/HoldFire уже играет OnOrderIssued — тут их только
                // глушим. Остальные 20 папок своего OrderType не имеют, реплику играем прямо тут.
                if (EquestriaOrderVoice.ShoutOnlyFolders.Contains(folder))
                {
                    Mission.Current?.GetMissionBehavior<EquestriaOrderVoice>()?.PlayShoutReplacement(folder);
                }
                return false;
            }
            catch (Exception)
            {
                return true;
            }
        }
    }

    // Глушим и хоровой отклик войск на приказ («Есть!») — OrderController играет его звуками
    // event:/alerts/nods/move, /attack, /stop и /formation у середины каждого отряда. Слышен он тише
    // выкрика героя, как будто отвечает толпа. Глушим все четыре: свои реплики есть на любой приказ.
    // Ставится вручную из EquestriaPatches.ApplyLate (см. там же, почему не при загрузке мода).
    public static class MuteVanillaOrderNods
    {
        private static int[] _nods;

        public static void Apply(Harmony harmony)
        {
            foreach (var method in TargetMethods())
            {
                harmony.Patch(method, prefix: new HarmonyMethod(typeof(MuteVanillaOrderNods), nameof(Prefix)));
            }
        }

        private static IEnumerable<MethodBase> TargetMethods()
        {
            return typeof(MBSoundEvent).GetMethods(BindingFlags.Public | BindingFlags.Static)
                .Where(m => m.Name == nameof(MBSoundEvent.PlaySound)
                            && m.GetParameters().Length > 0
                            && m.GetParameters()[0].ParameterType == typeof(int));
        }

        private static bool Prefix(object[] __args)
        {
            try
            {
                if (_nods == null)
                {
                    _nods = new[]
                    {
                        SoundEvent.GetEventIdFromString("event:/alerts/nods/move"),
                        SoundEvent.GetEventIdFromString("event:/alerts/nods/attack"),
                        SoundEvent.GetEventIdFromString("event:/alerts/nods/stop"),
                        SoundEvent.GetEventIdFromString("event:/alerts/nods/formation"),
                    };
                }
                return !(__args.Length > 0 && __args[0] is int id && Array.IndexOf(_nods, id) >= 0);
            }
            catch (Exception)
            {
                return true;
            }
        }
    }
}
