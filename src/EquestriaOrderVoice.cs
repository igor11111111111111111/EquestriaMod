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
    // Voice responses to orders in a battle scene. The lines are files (.wav/.ogg) in Module\Sounds\<folder>:
    //   order_voice: the order menu was opened (F1);
    //   order_move: the "move to position" order was given;
    //   order_charge: the "charge" order was given (F1, F3);
    //   order_retreat: the "retreat" order was given;
    //   order_follow: the "follow me" order was given;
    //   order_hold_fire: the "hold fire" order was given;
    //   the other 18 folders of their own (order_advance, order_stop, order_infantry, ...) each for
    //   its own command (see ShoutFolders below), voiced on 03.10.2026;
    //   order_other: whatever never got its own folder (for the future: new engine orders).
    // A random line from the folder plays. To replace the sounds, just change the files.
    //
    // The files are played by the programmable FMOD event "event:/Extra/voiceover"; that is how the game voices
    // dialogues, so no need to build our own sound bank.
    //
    // order_voice/_move/_charge/_retreat/_follow are still on temporary lines from Equestria at War
    // (see the SOURCE note .txt next to them); the rest are already voiced.
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

        // 18 commands without their own OrderType (weapon choice, formations, turning, transferring a troop):
        // the engine voices them only with a "shout" (Agent.MakeVoice); OnOrderIssued does not catch the order
        // as such. We play them from MuteVanillaOrderShouts.Prefix (see below), not
        // from here: that is where the right moment is already intercepted anyway, to mute vanilla.
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

        // Order -> folder with lines
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
        // Other orders (formation, stand, advance, fire and the rest) are voiced with the general lines.

        private static readonly Dictionary<string, string[]> Clips = new Dictionary<string, string[]>();
        private readonly Random _random = new Random();
        private SoundEvent _playing;
        private OrderController _listening;

        public override void OnMissionTick(float dt)
        {
            base.OnMissionTick(dt);
            // Any failure here would bring down the whole battle (OnMissionTick is called every frame without protection),
            // so everything inside is under Try.
            EquestriaCrashLog.Try("голос приказов", Tick);
        }

        private void Tick()
        {
            var team = Mission?.PlayerTeam;
            // Orders are given only by someone who has their own troops on the field.
            if (team == null || !team.IsPlayerGeneral && !team.IsPlayerSergeant)
            {
                return;
            }
            // The order controller does not appear right after the battle starts; we subscribe as soon as it exists.
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
                // While the previous line is playing, do not start a new one: frequent presses would merge into a mess.
                Play(MenuFolder, interrupt: false);
            }
        }

        private void OnOrderIssued(OrderType orderType, MBReadOnlyList<Formation> formations,
                                   OrderController controller, params object[] parameters)
        {
            // Orders without their own folder no longer get order_other here: many of them
            // (dismount, mount, fire at will, advance, fall back, stand, etc.) DO HAVE
            // their own OrderType, and it fires IN PARALLEL with the shout (Agent.MakeVoice), which already
            // starts the right line via MuteVanillaOrderShouts.PlayShoutReplacement. If
            // we still played order_other here, its interrupt=true would cut off the correctly
            // started line and replace it with a placeholder (noticed 03.10.2026). So we play
            // only what is explicitly listed in OrderFolders; the rest is left entirely to the shout.
            if (!OrderFolders.TryGetValue(orderType, out string folder))
            {
                return;
            }
            // The order comes right after the F1 menu, so its line interrupts the previous one.
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

        // Whether we have lines for this folder; then the commander's vanilla shout is not needed.
        internal static bool HasClips(string folder)
        {
            return ClipsIn(folder).Length > 0;
        }

        // Commander's vanilla voice -> our folder that replaces it.
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
                // troop selection in the order menu (infantry, cavalry, archers, all)
                { SkinVoiceManager.VoiceType.Infantry, InfantryFolder },
                { SkinVoiceManager.VoiceType.Cavalry, CavalryFolder },
                { SkinVoiceManager.VoiceType.Archers, ArchersFolder },
                { SkinVoiceManager.VoiceType.HorseArchers, HorseArchersFolder },
                { SkinVoiceManager.VoiceType.MixedFormation, MixedFormationFolder },
            };

        // Folders without their own OrderType: OnOrderIssued never fires for them (see the comment at the
        // constants above), so the line is played by MuteVanillaOrderShouts.Prefix itself when it mutes
        // the vanilla shout. Move/Charge/Retreat/Follow/HoldFire are NOT included: for them the line
        // is already played by OnOrderIssued; no need to call it a second time (that would give a double "once more").
        internal static readonly HashSet<string> ShoutOnlyFolders = new HashSet<string>
        {
            AdvanceFolder, FallBackFolder, StopFolder, MountFolder, DismountFolder, FireAtWillFolder,
            PickSpearsFolder, PickDefaultFolder, FaceEnemyFolder, FaceDirectionFolder,
            UseSiegeWeaponFolder, UseLaddersFolder, AttackGateFolder, CommandDelegateFolder,
            CommandUndelegateFolder, InfantryFolder, CavalryFolder, ArchersFolder, HorseArchersFolder,
            MixedFormationFolder,
        };

        // Called from MuteVanillaOrderShouts.Prefix (static context, no instance of its own),
        // hence not private.
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
            // The library lives in <mod>\bin\Win64_Shipping_Client; go up two levels.
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

    // Mute the commander's vanilla shout where our line plays: otherwise both sound at once.
    // The shout is made by OrderController via Agent.MakeVoice on the commander (the player).
    // Installed by hand from EquestriaPatches.ApplyLate, without the [HarmonyPatch] attribute, so that
    // PatchAll does not touch it at mod load.
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
                // Move/Charge/Retreat/Follow/HoldFire are already played by OnOrderIssued; here we only
                // mute them. The other 20 folders have no OrderType of their own; we play the line right here.
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

    // Also mute the troops' choral response to an order ("Aye!"): OrderController plays it with the sounds
    // event:/alerts/nods/move, /attack, /stop and /formation at the middle of each troop. It sounds quieter
    // than the hero's shout, as if a crowd answers. We mute all four: we have our own lines for any order.
    // Installed by hand from EquestriaPatches.ApplyLate (see there why not at mod load).
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
