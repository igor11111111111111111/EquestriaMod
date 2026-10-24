using System;
using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using TaleWorlds.CampaignSystem.GameState;
using TaleWorlds.Core;
using TaleWorlds.Engine;
using TaleWorlds.Library;
using TaleWorlds.MountAndBlade;

namespace EquestriaMod
{
    // A helmet on a dragon's head.
    //
    // A dragon's head is bigger than a human's, and any vanilla helmet sits on it like a little cap.
    // Helmet duplicates are not an option: there are hundreds of them in the game, and the same would have to be
    // repeated for every race; the user does not want to shrink the head.
    //
    // The engine ALREADY knows how to fit a helmet to the head size: when assembling a character, for every mesh
    // flagged UsingFacegenScaling it calls MetaMesh.UseHeadBoneFaceGenScaling with a matrix from
    // MBAgentVisuals.GetFacegenScalingMatrix (underneath is the native GetCurrentHelmetScalingFactor,
    // i.e. the matrix is exactly about helmets). We multiply that matrix. That way the scale is applied
    // IN HEAD BONE COORDINATES, and the helmet moves together with the head.
    //
    // Previously there was our own frame on the helmet meshes here (Mesh.SetLocalFrame). It changed the size, but
    // was applied in character coordinates: when the head turned, the helmet stayed in place
    // ("the helmet does not move from the head bone"). Do not bring it back.
    //
    // 28.09.2026: the comment above described the native path (UsingFacegenScaling/
    // GetFacegenScalingMatrix/UseHeadBoneFaceGenScaling) as already working; in fact there was never a patch
    // on it, the whole file always lived on the manual frame below. We tried to enable
    // the native path for real: the engine did call it (confirmed by the log), but
    // the helmet size fell apart: in battle it sat at the standard (unstretched) size, in the inventory it flew up
    // and swelled. Apparently GetFacegenScalingMatrix is not a simple diagonal scale
    // matrix, and naive per-component multiplication (.rotation.s/.f/.u by our multiplier) breaks
    // it. We rolled back to the manual frame: at least it keeps the size right everywhere, it just
    // does not rotate with the head. The native path can be tried again, but first
    // we need to understand the real format of this matrix (most likely not a diagonal), not guess.
    public static class EquestriaHelmetFit
    {
        // Tracing of the helmet rotation to the log: a line every battle frame, for debugging only
        private const bool TraceHelmet = false;

        // How many times to stretch the helmet on this race. A table, not one number: every race
        // has its own head, and the griffon and yak will need their own values.
        // Per axis, not one number: a race's head is elongated differently from a human's, and the helmet often
        // wants to be wider rather than taller. Order as in Vec3: sideways, front-back, up.
        // The race's hairstyle: it has to be restored by hand where we hide the helmet: the game does not
        // build a hairstyle under a worn helmet (HairCoverType), and the head stays bare.
        private static readonly Dictionary<string, string> HairByRace = new Dictionary<string, string>
        {
            { "dragon", "eq_dragon_hair" },
            { "griffon", "eq_griffon_hair" },
            { "hippogriff", "eq_hippogriff_hair" },
            // the yak's hairstyle also holds the horns: without this line under a helmet it is left both without
            // a mane and hornless
            { "yak", "eq_yak_hair" },
            // the doe's hairstyle is the whole antlers; without it she is antlerless under a helmet
            { "deer", "eq_deer_hair" },
            // the pony's hairstyle is the horn; the mane is built into the head
            { "pony", "eq_pony_hair" },
        };

        private static readonly Dictionary<string, Vec3> ScaleByRace = new Dictionary<string, Vec3>
        {
            // tuned in game: equestria.helmet_scale 2.25 2.25 1.9 (05.10.2026, after the blink fix)
            { "pony", new Vec3(2.25f, 2.25f, 1.9f) },
            // tuned in game: equestria.helmet_scale 2 2 1.85 (10.10.2026, corrected dragon model)
            { "dragon", new Vec3(2f, 2f, 1.85f) },
            // tuned in game: equestria.helmet_scale 2.1 1.9 1.75 (05.10.2026, after the blink fix)
            { "griffon", new Vec3(2.1f, 1.9f, 1.75f) },
            // tuned in game: equestria.helmet_scale 2 1.8 1.6 (05.10.2026, after the blink fix)
            { "changeling", new Vec3(2f, 1.8f, 1.6f) },
            // tuned in game: equestria.helmet_scale 1.8 1.8 1.4 (05.10.2026, after the blink fix)
            { "hippogriff", new Vec3(1.8f, 1.8f, 1.4f) },
            // tuned in game: equestria.helmet_scale 1.95 1.95 1.7 (04.10.2026, after the model rebuild)
            { "yak", new Vec3(1.95f, 1.95f, 1.7f) },
            // tuned in game: equestria.helmet_scale 1.85 1.85 1.55 (05.10.2026, after the blink fix)
            { "deer", new Vec3(1.85f, 1.85f, 1.55f) },
        };

        /// <summary>The race multiplier, so it can be tuned on the fly by a command, without a restart.</summary>
        public static Vec3 ScaleFor(string race)
        {
            return ScaleByRace.TryGetValue(race, out Vec3 scale) ? scale : new Vec3(1f, 1f, 1f);
        }

        public static void SetScale(string race, Vec3 scale)
        {
            ScaleByRace[race] = scale;
            _byRaceId = null;               // rebuild the table by race numbers
        }

        private static Dictionary<int, Vec3> _byRaceId;
        // The race of the character the engine is assembling RIGHT NOW. It asks for the matrix in the middle
        // of assembly, when the race is known only from its data, so we remember it for the duration of the call.
        [ThreadStatic]
        private static int _building;
        // Helmet meshes are remembered per soldier's visuals: otherwise every frame we would have to go through
        // all the skeleton's meshes (a soldier has several dozen) and compare names. In a battle of a thousand
        // soldiers this is noticeable. The visuals are rebuilt when the equipment changes: then a
        // new object appears, and the entry is created anew; just in case we also check the mesh name.
        //
        // That is not enough: mounting a horse (noticed 28.09.2026,
        // "the helmet rides with the body, not the head") rebuilds the skeleton INSIDE the same visuals object:
        // visuals itself does not change, and the old
        // cache entry would pass by mesh name, while its Meshes/Bone would remain from the PREVIOUS
        // skeleton: we would be moving meshes no longer shown, and the rider's real helmet would keep standing
        // in the pose of an ordinary armour skin (i.e. ride with the body). The same class of bug we already had
        // with CharacterTableau and the hairstyle colour: there too one could not rely on the owner object
        // staying the same. So we also check the skeleton itself.
        private sealed class Fitted
        {
            public string MeshName;
            public Mesh[] Meshes;
            public sbyte Bone;
            public int Race;              // for windows only: the battle path does not store race (see Fit(Agent))
            public Skeleton Skeleton;
        }

        private static readonly System.Runtime.CompilerServices.ConditionalWeakTable<object, Fitted> _cache =
            new System.Runtime.CompilerServices.ConditionalWeakTable<object, Fitted>();


        private static System.Reflection.MethodInfo _getData, _getEntity;
        private static System.Reflection.PropertyInfo _raceData, _equipmentData, _monsterData;
        // Previously there was one shared flag: success was logged ONCE for the whole process, and the very first
        // successful race (for example, the yak) forever hid all the others from the log: from such a log
        // one could not tell whether the griffon specifically was being fitted (noticed 25.09.2026). Now by
        // mesh name: one line per separate helmet, not one per session.
        private static readonly HashSet<string> _shiftLoggedMeshes = new HashSet<string>();

        private static Dictionary<int, Vec3> Scales()
        {
            if (_byRaceId == null)
            {
                _byRaceId = new Dictionary<int, Vec3>();
                foreach (var pair in ScaleByRace)
                {
                    int race = TaleWorlds.Core.FaceGen.GetRaceOrDefault(pair.Key);
                    if (race != 0)          // 0 is the human; races that were not found end up there too
                    {
                        _byRaceId[race] = pair.Value;
                    }
                }
            }
            return _byRaceId;
        }

        public static void Apply(Harmony harmony)
        {
            var visuals = AccessTools.TypeByName("TaleWorlds.MountAndBlade.View.AgentVisuals");
            var matrix = AccessTools.Method(typeof(MBAgentVisuals), "GetFacegenScalingMatrix");
            if (visuals == null || matrix == null)
            {
                EquestriaCrashLog.Warn("шлем под расу: не найден AgentVisuals или матрица подгонки");
                return;
            }
            int marked = 0;
            // Which assembly points were actually found: printed by name at the end: a single number
            // "points 5" did not say which of the six went missing (noticed 25.09.2026).
            var found = new List<string>();
            foreach (var method in AccessTools.GetDeclaredMethods(visuals))
            {
                // Armour is attached by a separate method, and it is called not only from visuals assembly:
                // without it the race stayed unknown at the right moment and the fitting was silent.
                if (method.Name == "AddArmorMultiMeshesToAgentEntity")
                {
                    // prefix: tell the engine the race (without it, it will not stretch the helmet),
                    // postfix: lower the already worn helmet into place
                    harmony.Patch(method,
                        prefix: new HarmonyMethod(typeof(EquestriaHelmetFit), nameof(BeforeArmour)),
                        postfix: new HarmonyMethod(typeof(EquestriaHelmetFit), nameof(AfterArmour)),
                        finalizer: new HarmonyMethod(typeof(EquestriaHelmetFit), nameof(AfterBuild)));
                    marked++;
                    found.Add("AgentVisuals.AddArmorMultiMeshesToAgentEntity");
                    continue;
                }
                // Window frame: only here does the character move without being rebuilt (encyclopedia,
                // party window). See Tick.
                if (method.Name == "TickVisuals")
                {
                    harmony.Patch(method,
                        postfix: new HarmonyMethod(typeof(EquestriaHelmetFit), nameof(AfterTick)));
                    marked++;
                    found.Add("AgentVisuals.TickVisuals");
                    continue;
                }
                if (method.Name != "Create" && method.Name != "Refresh")
                {
                    continue;
                }
                harmony.Patch(method,
                    prefix: new HarmonyMethod(typeof(EquestriaHelmetFit), nameof(BeforeBuild)),
                    finalizer: new HarmonyMethod(typeof(EquestriaHelmetFit), nameof(AfterBuild)));
                marked++;
                found.Add("AgentVisuals." + method.Name);
            }
            // The head bone of our monsters comes out as -1: the engine looks up a monster's bones through the skeleton of its
            // action set, and for the mod's races this link does not work (the skeleton is set in the sets,
            // and the number is still -1). The engine passes this same -1 into helmet fitting, and the helmet flies off.
            // We substitute the correct number: in the human skeleton the head is bone 13 (the bone order
            // is visible in the tpac_export bones dump: pelvis 0, spine 9, spine1 10, spine2 11, neck 12,
            // head 13; the same numbers are in the bone names of the pony blend: bip01_head_13).
            // Preset pictures: the character is assembled, posed and an animation is played, and only
            // then is the frame taken. The fitting at armour assembly falls on the rest pose, so
            // we repeat it at the end of the preset assembly (see FitStatic).
            // Both classes live in TaleWorlds.MountAndBlade.View.SCRIPTS, not directly in View: the type was
            // never found (AccessTools.TypeByName returned null), so the whole preset path
            // was silent from the very start (noticed 25.09.2026 from the detailed list of points below).
            foreach (var typeName in new[] { "TaleWorlds.MountAndBlade.View.Scripts.CharacterSpawner",
                                             "TaleWorlds.MountAndBlade.View.Scripts.CharacterDebugSpawner" })
            {
                var spawner = AccessTools.TypeByName(typeName);
                if (spawner == null)
                {
                    found.Add(typeName.Substring(typeName.LastIndexOf('.') + 1) + " — ТИП НЕ НАЙДЕН");
                    continue;
                }
                var init = AccessTools.GetDeclaredMethods(spawner).FirstOrDefault(m => m.Name == "InitWithCharacter");
                if (init == null)
                {
                    found.Add(spawner.Name + ".InitWithCharacter — МЕТОД НЕ НАЙДЕН");
                    continue;
                }
                harmony.Patch(init,
                    postfix: new HarmonyMethod(typeof(EquestriaHelmetFit), nameof(AfterSpawner)));
                marked++;
                found.Add(spawner.Name + ".InitWithCharacter");
            }

            // Meeting a lord's party on the map: SandBox.View.Map.MapConversationTableau holds a
            // LIST of visuals (the speaker first, then up to two bodyguards; I read the class
            // directly), but in its OnTick it ticks ONLY _agentVisuals[0], only the speaker.
            // The bodyguards get not a single frame after creation, and their pose (and with it
            // the head position) is set AFTER Create by the same TickAnimationsAndForceUpdate as for
            // the thumbnail presets, so they have the same trouble: the helmet stays on the rest pose and hangs
            // off to the side (noticed 25.09.2026, "Empress Celestia" fine, the escort not).
            // We tick the whole list ourselves with a postfix on OnTick.
            var mapConvType = AccessTools.TypeByName("SandBox.View.Map.MapConversationTableau");
            var mapConvTick = mapConvType == null ? null : AccessTools.Method(mapConvType, "OnTick");
            if (mapConvTick == null)
            {
                found.Add("MapConversationTableau.OnTick — "
                    + (mapConvType == null ? "ТИП НЕ НАЙДЕН" : "МЕТОД НЕ НАЙДЕН"));
            }
            else
            {
                harmony.Patch(mapConvTick,
                    postfix: new HarmonyMethod(typeof(EquestriaHelmetFit), nameof(AfterMapConversationTick)));
                marked++;
                found.Add("MapConversationTableau.OnTick");
            }

            var boneIndex = AccessTools.PropertyGetter(typeof(Monster), "HeadLookDirectionBoneIndex");
            if (boneIndex != null)
            {
                harmony.Patch(boneIndex, postfix: new HarmonyMethod(typeof(EquestriaHelmetFit), nameof(AfterBone)));
            }
            EquestriaCrashLog.Log($"шлем под расу: патч поставлен (точек сборки {marked}, "
                + $"подстраховка по кости: {(boneIndex != null ? "да" : "НЕ НАЙДЕНА")})\r\n  "
                + string.Join("\r\n  ", found));
        }

        // The race is taken from the visuals data: for Create they are the first argument, for Refresh the second.
        private static void BeforeBuild(object[] __args)
        {
            _building = 0;
            EquestriaCrashLog.Try("шлем под расу (начало сборки)", () =>
            {
                foreach (var arg in __args ?? new object[0])
                {
                    var race = arg == null ? null
                        : AccessTools.Property(arg.GetType(), "RaceData")?.GetValue(arg);
                    if (race is int id)
                    {
                        _building = id;
                        return;
                    }
                }
            });
        }

        // The race is on the visuals themselves: at this step its data is already assembled. We also compute around
        // which point to stretch: the engine applies the matrix in HEAD BONE coordinates, and that bone
        // sits at the base of the neck. Without a correction, at double scale the helmet moves up by its own
        // height above the head (checked in game). So we put into the matrix a shift that keeps
        // the middle of the helmet in place.
        // The head bone is taken NOT BY NAME but by the number from the monster data, the very one that
        // the engine itself passes to the fitting. By name it failed twice: neither the Blender name
        // «bip01_head_13» nor the short «head» is found by the skeleton, and the correction came out zero.
        private const float HelmetUp = 0.12f;        // how much higher the middle of the helmet is than the head bone

        // Where to shift the helmet after stretching: the race's skull does not sit where a human's does.
        // Order as in Vec3: sideways (+X is right, looking at the character from the front), forward
        // (the muzzle faces -Y, so forward is minus) and up. Tuned on the fly by the command
        // equestria.helmet_offset; the values here are the initial ones.
        private static readonly Dictionary<string, Vec3> ShiftByRace = new Dictionary<string, Vec3>
        {
            // tuned in game: equestria.helmet_offset 0.0 0.08 0.12 (05.10.2026, after the blink fix)
            // the helmet is shifted forward, hence minus on Y (the muzzle faces -Y)
            { "pony", new Vec3(0f, -0.08f, 0.12f) },
            // tuned in game: equestria.helmet_offset 0.0 0.13 0.07 (10.10.2026, corrected
            // dragon model); the helmet is shifted forward, hence minus on Y (the muzzle faces -Y)
            { "dragon", new Vec3(0f, -0.13f, 0.07f) },
            // tuned in game: equestria.helmet_offset 0.0 0.07 0.15 (05.10.2026, after the blink fix)
            { "griffon", new Vec3(0f, -0.07f, 0.15f) },
            // tuned in game: equestria.helmet_offset 0.0 0.04 0.12 (05.10.2026, after the blink fix)
            { "changeling", new Vec3(0f, -0.04f, 0.12f) },
            // tuned in game: equestria.helmet_offset 0.0 0.04 0.06 (05.10.2026, after the blink fix)
            { "hippogriff", new Vec3(0f, -0.04f, 0.06f) },
            // tuned in game: equestria.helmet_offset 0.0 0.0 0.06 (04.10.2026, after the model rebuild)
            { "yak", new Vec3(0f, 0f, 0.06f) },
            // tuned in game: equestria.helmet_offset 0.0 0.03 0.13 (05.10.2026, after the blink fix)
            { "deer", new Vec3(0f, -0.03f, 0.13f) },
        };

        public static Vec3 ShiftFor(string race)
        {
            return ShiftByRace.TryGetValue(race, out Vec3 shift) ? shift : Vec3.Zero;
        }

        public static void SetShift(string race, float right, float forward, float up)
        {
            ShiftByRace[race] = new Vec3(right, -forward, up);
        }

        private static Vec3 Shift(int raceId)
        {
            foreach (var pair in ShiftByRace)
            {
                if (TaleWorlds.Core.FaceGen.GetRaceOrDefault(pair.Key) == raceId)
                {
                    return pair.Value;
                }
            }
            return Vec3.Zero;
        }

        private static int _bone = -1;
        private static string _why = "не считали";
        private static string _monster = "?";

        // The race is on the visuals themselves: the engine will ask for the helmet scale in the middle of this assembly,
        // and there is nowhere else to learn it there.
        private static void BeforeArmour(object __instance)
        {
            _building = 0;
            EquestriaCrashLog.Try("шлем под расу (начало доспеха)", () =>
            {
                var data = AccessTools.Method(__instance.GetType(), "GetCopyAgentVisualsData")
                    ?.Invoke(__instance, null);
                var race = data == null ? null
                    : AccessTools.Property(data.GetType(), "RaceData")?.GetValue(data);
                if (race is int id)
                {
                    _building = id;
                }
            });
        }

        // The helmet mesh is already worn: lower it into place.
        //
        // Why not through the engine matrix: it takes only the scale from it and ignores the shift,
        // so the helmet always grows around the bone (which sits at the base of the neck) and moves up.
        // Our own frame sets the whole transformation.
        /// <summary>
        /// Stretches the worn helmet to the race's head. Called both at armour assembly and every frame
        /// from the same points as the body parts: the pivot must follow the head (see below).
        /// </summary>
        /// <summary>Fitting per soldier: the battle path. There the agent has a DIFFERENT visuals type
        /// (MBAgentVisuals, not the window AgentVisuals), and the data is taken straight from it.</summary>
        public static void Fit(Agent agent)
        {
            if (agent == null || agent.IsMount || agent.Character == null
                || !Scales().ContainsKey(agent.Character.Race))
            {
                return;
            }
            var visuals = agent.AgentVisuals;
            var skeleton = visuals?.GetEntity()?.Skeleton;
            string meshName = agent.SpawnEquipment[EquipmentIndex.Head].Item?.MultiMeshName;
            if (skeleton == null || string.IsNullOrEmpty(meshName))
            {
                return;
            }
            if (!_cache.TryGetValue(visuals, out Fitted kept) || kept.MeshName != meshName
                || kept.Skeleton != skeleton)
            {
                sbyte bone = agent.Monster?.HeadLookDirectionBoneIndex ?? HumanHeadBone;
                sbyte mapped = skeleton.GetSkeletonBoneMapping(bone);
                kept = new Fitted
                {
                    MeshName = meshName,
                    Bone = mapped >= 0 && mapped < skeleton.GetBoneCount() ? mapped : bone,
                    Meshes = HelmetMeshes(skeleton, meshName),
                    Skeleton = skeleton,
                };
                _cache.Remove(visuals);
                _cache.Add(visuals, kept);
                // The helmet is confirmed by the reliable agent.SpawnEquipment: if the spawn-time check
                // (EnsureHairNotBald, tied to a less reliable snapshot) managed to turn on the mane
                // by mistake, we turn it off here (see HideBaldHairUnderConfirmedHelmet). The same race
                // existed for the ears (HideEarsUnderConfirmedHelmet): visible under the helmet in battle, although in
                // the inventory window they hide correctly.
                EquestriaBodyParts.HideBaldHairUnderConfirmedHelmet(visuals, agent.Character.Race);
                EquestriaBodyParts.HideEarsUnderConfirmedHelmet(visuals, agent.Character.Race);
            }
            Fit(skeleton, kept.Meshes, kept.Bone, agent.Character.Race, meshName,
                // Helmet rotation tracing (28.09.2026) wrote a line EVERY battle frame; it is turned off;
                // to enable for debugging: TraceHelmet = true
                traceAgent: TraceHelmet && agent == Agent.Main ? agent : null);
        }

        // Debugging the "flying triangle" (30.09.2026): turns conversation participants on the
        // map (and the player in a mission) around the vertical axis, to look at them from any
        // side. Console: equestria.rotate_lord <degrees> (cumulative to the previous rotation).
        [CommandLineFunctionality.CommandLineArgumentFunction("rotate_lord", "equestria")]
        public static string RotateLordCommand(List<string> args)
        {
            if (args.Count != 1 || !float.TryParse(args[0], out float degrees))
            {
                return "Формат: equestria.rotate_lord <градусы>, например equestria.rotate_lord 90";
            }
            float rad = degrees * (float)Math.PI / 180f;
            int count = 0;
            if (Agent.Main?.AgentVisuals != null && RotateVisuals(Agent.Main.AgentVisuals, rad))
            {
                count++;
            }
            var conv = LastMapConversation;
            var list = conv == null ? null : AccessTools.Field(conv.GetType(), "_agentVisuals")
                ?.GetValue(conv) as System.Collections.IEnumerable;
            if (list != null)
            {
                foreach (var visuals in list)
                {
                    if (RotateVisuals(visuals, rad))
                    {
                        count++;
                    }
                }
            }
            return count > 0 ? $"Повёрнуто персонажей: {count}." : "Не нашёл ни игрока, ни разговора на карте.";
        }

        private static bool RotateVisuals(object visuals, float radians)
        {
            var entity = AccessTools.Method(visuals.GetType(), "GetEntity")?.Invoke(visuals, null) as GameEntity;
            if (entity == null)
            {
                return false;
            }
            var frame = entity.GetFrame();
            frame.Rotate(radians, new Vec3(0f, 0f, 1f));
            entity.SetFrame(ref frame);
            return true;
        }

        // Debugging the "flying triangle": hides the worn helmet on the player/conversation participants on the
        // map. Console: equestria.hide_helmet
        [CommandLineFunctionality.CommandLineArgumentFunction("hide_helmet", "equestria")]
        public static string HideHelmetCommand(List<string> args)
        {
            int count = 0;
            if (Agent.Main?.AgentVisuals != null && HideEquippedHelmet(Agent.Main.AgentVisuals))
            {
                count++;
            }
            var conv2 = LastMapConversation;
            var list2 = conv2 == null ? null : AccessTools.Field(conv2.GetType(), "_agentVisuals")
                ?.GetValue(conv2) as System.Collections.IEnumerable;
            if (list2 != null)
            {
                foreach (var visuals in list2)
                {
                    if (HideEquippedHelmet(visuals))
                    {
                        count++;
                    }
                }
            }
            return count > 0 ? $"Шлем скрыт у {count} персонажей (тест)." : "Не нашёл ни игрока, ни разговора на карте.";
        }

        private static bool HideEquippedHelmet(object visuals)
        {
            if (visuals == null)
            {
                return false;
            }
            var getData = AccessTools.Method(visuals.GetType(), "GetCopyAgentVisualsData");
            var getEntity = AccessTools.Method(visuals.GetType(), "GetEntity");
            var data = getData?.Invoke(visuals, null);
            var entity = getEntity?.Invoke(visuals, null) as GameEntity;
            var skeleton = entity?.Skeleton;
            if (data == null || skeleton == null)
            {
                return false;
            }
            var equipment = AccessTools.Property(data.GetType(), "EquipmentData")?.GetValue(data) as Equipment;
            string meshName = equipment?[EquipmentIndex.Head].Item?.MultiMeshName;
            if (string.IsNullOrEmpty(meshName))
            {
                return false;
            }
            foreach (var mesh in HelmetMeshes(skeleton, meshName))
            {
                mesh.SetVisibilityMask(0);
            }
            return true;
        }

        // Debugging the "flying triangle": prints all the skeleton's meshes to eq_exceptions.log
        // (name, visibility, material, bounding box); we are looking for an extra unhidden copy of the hairstyle.
        // Console: equestria.dump_meshes
        [CommandLineFunctionality.CommandLineArgumentFunction("dump_meshes", "equestria")]
        public static string DumpMeshesCommand(List<string> args)
        {
            int count = 0;
            if (Agent.Main?.AgentVisuals != null)
            {
                DumpVisualsMeshes(Agent.Main.AgentVisuals, "игрок");
                count++;
            }
            var conv = LastMapConversation;
            var list = conv == null ? null : AccessTools.Field(conv.GetType(), "_agentVisuals")
                ?.GetValue(conv) as System.Collections.IEnumerable;
            if (list != null)
            {
                int i = 0;
                foreach (var visuals in list)
                {
                    DumpVisualsMeshes(visuals, $"разговор #{i}");
                    count++;
                    i++;
                }
            }
            return count > 0 ? $"Мешей выгружено для {count} персонажей — смотри eq_exceptions.log."
                : "Не нашёл ни игрока, ни разговора на карте.";
        }

        private static void DumpVisualsMeshes(object visuals, string who)
        {
            if (visuals == null)
            {
                return;
            }
            var getEntity = AccessTools.Method(visuals.GetType(), "GetEntity");
            var entity = getEntity?.Invoke(visuals, null) as GameEntity;
            var skeleton = entity?.Skeleton;
            if (skeleton == null)
            {
                EquestriaCrashLog.Log($"меши[{who}]: скелета нет");
                return;
            }
            foreach (var mesh in skeleton.GetAllMeshes())
            {
                if (mesh == null)
                {
                    continue;
                }
                var min = mesh.GetBoundingBoxMin();
                var max = mesh.GetBoundingBoxMax();
                string mat = mesh.GetMaterial()?.Name ?? "(нет)";
                EquestriaCrashLog.Log($"меш[{who}]: {mesh.Name} видимость={mesh.VisibilityMask} материал={mat} "
                    + $"bbox=({min.x:0.###},{min.y:0.###},{min.z:0.###})-({max.x:0.###},{max.y:0.###},{max.z:0.###})");
            }
            int multiCount = entity?.MultiMeshComponentCount ?? 0;
            for (int i = 0; i < multiCount; i++)
            {
                var meta = entity.GetMetaMesh(i);
                if (meta == null)
                {
                    continue;
                }
                for (int j = 0; j < meta.MeshCount; j++)
                {
                    var mesh = meta.GetMeshAtIndex(j);
                    if (mesh == null)
                    {
                        continue;
                    }
                    EquestriaCrashLog.Log($"метамеш[{who}][{i}/{j}]: {mesh.Name} видимость={mesh.VisibilityMask}");
                }
            }
        }

        private static Mesh[] HelmetMeshes(Skeleton skeleton, string meshName)
        {
            var found = new List<Mesh>();
            foreach (var mesh in skeleton.GetAllMeshes())
            {
                if (mesh?.Name != null
                    && mesh.Name.StartsWith(meshName, StringComparison.OrdinalIgnoreCase))
                {
                    found.Add(mesh);
                }
            }
            return found.ToArray();
        }

        /// <summary>Fitting per visuals: the window path (inventory, party, barber).</summary>
        /// <param name="isMapIcon">
        /// The real tiny party figure on the map (not a window/encyclopedia over the map):
        /// we hide its helmet. Previously this was decided by ActiveState is MapState, but the encyclopedia and other
        /// windows are OVERLAYS over the map, they have THE SAME ActiveState. The check quietly hid
        /// the helmet in the encyclopedia too: EquestriaBodyParts.Attach calls Fit on EVERY CharacterTableau tick
        /// (once per frame), and onMap==true made it invisible again right after
        /// EquestriaHelmetFit.Tick had just placed it correctly in this same frame (noticed 25.09.2026,
        /// the log showed a successful fitting, but there was no helmet on screen). Now the flag comes
        /// explicitly from the caller, which already knows who it is: EquestriaBodyParts tells apart "PartyIcon"
        /// (the real map) and the window/Tableau/update callers by the name with which the engine itself labelled
        /// the visuals object at creation.
        /// </param>
        public static void Fit(object visuals, int race, bool isMapIcon)
        {
            if (visuals == null || !Scales().ContainsKey(race))
            {
                return;
            }
            // ON THE WORLD MAP WE SIMPLY HIDE THE HELMET. The game assembles the party figure once and never
            // touches it again, while the stretch pivot must follow the head: with a one-off fitting the helmet
            // moved up. Leaving it unstretched is bad too: a human helmet sinks into
            // a big dragon head. The figures there are fingernail-sized, the missing helmet is not visible.
            bool onMap = isMapIcon;
            // Method and property lookups are cached: called often, reflection would be expensive.
            if (_getData == null || _getData.DeclaringType != visuals.GetType())
            {
                _getData = AccessTools.Method(visuals.GetType(), "GetCopyAgentVisualsData");
                _getEntity = AccessTools.Method(visuals.GetType(), "GetEntity");
                _raceData = null;
            }
            var data = _getData?.Invoke(visuals, null);
            var entity = _getEntity?.Invoke(visuals, null) as GameEntity;
            if (data == null)
            {
                return;
            }
            if (_raceData == null)
            {
                _raceData = AccessTools.Property(data.GetType(), "RaceData");
                _equipmentData = AccessTools.Property(data.GetType(), "EquipmentData");
                _monsterData = AccessTools.Property(data.GetType(), "MonsterData");
            }
            var equipment = _equipmentData?.GetValue(data) as Equipment;
            var monster = _monsterData?.GetValue(data) as Monster;
            var skeleton = entity?.Skeleton;
            string meshName = equipment?[EquipmentIndex.Head].Item?.MultiMeshName;
            if (skeleton == null || string.IsNullOrEmpty(meshName))
            {
                return;
            }
            // In a window the character is rebuilt at every sneeze, a cache is pointless here: we look up the meshes right away
            sbyte bone = monster?.HeadLookDirectionBoneIndex ?? HumanHeadBone;
            sbyte mapped = skeleton.GetSkeletonBoneMapping(bone);
            var meshes = HelmetMeshes(skeleton, meshName);
            if (onMap)
            {
                foreach (var mesh in meshes)
                {
                    mesh.SetVisibilityMask(0);          // zero: do not draw at all
                }
                // Instead of the hidden helmet we restore the hairstyle: the game does not build it under a helmet,
                // and on the map the dragon was left bare-headed.
                foreach (var pair in HairByRace)
                {
                    if (TaleWorlds.Core.FaceGen.GetRaceOrDefault(pair.Key) == race)
                    {
                        EquestriaBodyParts.AttachPart(visuals, pair.Value, "карта");
                    }
                }
                return;
            }
            Fit(skeleton, meshes,
                mapped >= 0 && mapped < skeleton.GetBoneCount() ? mapped : bone, race, meshName);
        }

        private static void Fit(Skeleton skeleton, Mesh[] meshes, sbyte bone, int race, string meshName,
            Agent traceAgent = null)
        {
            if (meshes == null || meshes.Length == 0 || !Scales().TryGetValue(race, out Vec3 scale))
            {
                return;
            }
            // PIVOT: the CURRENT head bone position, not the rest pose. The mesh frame is applied
            // AFTER skinning, and stretching around the current bone gives exactly the same result
            // as correct stretching before skinning around the bone in the bind pose (both forms
            // reduce to b + s*B*(v - b_bind)). So the pivot is recomputed every frame: with a
            // one-off placement the helmet would drift as soon as the character moves.
            MatrixFrame now = skeleton.GetBoneEntitialFrameWithIndex(bone);
            if (traceAgent != null)
            {
                // Helmet rotation tracing (28.09.2026): we compare what our fitting actually reads
                // (the bone's "forward" vector in entity coordinates) with what the engine itself
                // considers the agent's look/body direction, to understand which bone the helmet
                // really follows.
                Vec3 f = now.rotation.f;
                // The units of LookDirectionAsAngle/MovementDirectionAsAngle are not verified: we write them as
                // is (raw number) and will sort it out from the log: radians will fit in ~[-3.14;3.14],
                // degrees in ~[-180;180] or [0;360].
                EquestriaCrashLog.Log($"шлем трассировка: кость={bone} вперёд=({f.x:0.00},{f.y:0.00},{f.z:0.00}) "
                    + $"взгляд(сырое)={traceAgent.LookDirectionAsAngle:0.000} "
                    + $"тело(сырое)={traceAgent.MovementDirectionAsAngle:0.000}");
            }
            Vec3 shift = Shift(race);

            // THE STRETCH AXES ROTATE TOGETHER WITH THE HEAD. The multiplier is non-uniform (the helmet is wider
            // than taller), and the frame sets it in the character's axes: when the head turned, the helmet
            // was stretched anew each time and "floated". So we take the head rotation RELATIVE to the rest
            // pose and rotate the scale itself by it: M = R * S * Rᵀ. At rest R is identity, and
            // the behaviour is exactly as before, so the tuned numbers keep their meaning.
            MatrixFrame rest = skeleton.GetBoneEntitialRestFrame(bone, false);
            Vec3 c1 = now.rotation.TransformToParent(rest.rotation.TransformToLocal(new Vec3(1f, 0f, 0f)));
            Vec3 c2 = now.rotation.TransformToParent(rest.rotation.TransformToLocal(new Vec3(0f, 1f, 0f)));
            Vec3 c3 = now.rotation.TransformToParent(rest.rotation.TransformToLocal(new Vec3(0f, 0f, 1f)));
            // LIFTING THE PIVOT (HelmetUp) IS ALSO ALONG c3, not along raw world Z. The bone sits at the base
            // of the neck, and the centre of the head is higher; previously this lift went straight up in the world, which is right
            // only when the head looks straight ahead. With a strong downward head tilt (battle,
            // looking at the ground) world up and head up diverge: the pivot drifted back/up from
            // the real centre of the head, and the back of the head stuck out from under the helmet (29.09.2026 fix,
            // the same class of bug as with shift just below).
            Vec3 pivot = now.origin + c3 * HelmetUp;
            // the columns of M are a sum of outer products, one per scale axis
            Vec3 mx = c1 * (scale.x * c1.x) + c2 * (scale.y * c2.x) + c3 * (scale.z * c3.x);
            Vec3 my = c1 * (scale.x * c1.y) + c2 * (scale.y * c2.y) + c3 * (scale.z * c3.y);
            Vec3 mz = c1 * (scale.x * c1.z) + c2 * (scale.y * c2.z) + c3 * (scale.z * c3.z);
            Vec3 moved = mx * pivot.x + my * pivot.y + mz * pivot.z;
            // SHIFT IS ALSO ROTATED TOGETHER WITH THE HEAD, by the same c1/c2/c3 rotation as the scale
            // axes above. Previously shift was added raw, in world/body axes: at rest (now.rotation
            // ≈ rest.rotation, c1/c2/c3 ≈ the identity basis) this cannot be told from the correct behaviour,
            // so in windows/menus, where the head barely deviates from the rest pose, the helmet sat straight.
            // In battle the head turns actively (looking at a target, strikes, dodges), c1/c2/c3
            // diverge from the identity basis, and the unrotated shift "drifted" sideways from the bone,
            // the more noticeably the bigger the shift itself and the race multiplier (for the pony both are big).
            // That is exactly the "helmet desync in battle", not the recompute frequency.
            Vec3 shiftRotated = c1 * shift.x + c2 * shift.y + c3 * shift.z;
            foreach (var mesh in meshes)
            {
                // The frame is set ABSOLUTELY, not accumulated: the original is always zero (the armour
                // vertices are written in body coordinates), so a repeated call spoils nothing.
                var frame = MatrixFrame.Identity;
                frame.rotation.s = mx;
                frame.rotation.f = my;
                frame.rotation.u = mz;
                frame.origin = pivot - moved + shiftRotated;
                mesh.SetLocalFrame(frame);
            }
            if (_shiftLoggedMeshes.Add(meshName))
            {
                EquestriaCrashLog.Log($"шлем под расу: {meshName} растянут в "
                    + $"({scale.x:0.00},{scale.y:0.00},{scale.z:0.00}) раза ({meshes.Length} мешей) "
                    + $"вокруг кости {bone} ({skeleton.GetBoneName(bone)}) на высоте {pivot.z:0.00}");
            }
        }

        /// <summary>
        /// Fitting every frame in windows: encyclopedia, party, equipment.
        ///
        /// A one-off fitting at assembly is not enough. The mesh frame is set IN CHARACTER COORDINATES and
        /// computed around the CURRENT head bone position; in a window the character is assembled in one
        /// pose, and then a stance is played: the head moves, and with a multiplier of about two the helmet
        /// ends up off to the side of it (in the encyclopedia it hung above and to the right of the head, noticed
        /// 25.09.2026). In battle this did not happen: there the fitting runs every frame anyway.
        /// </summary>
        public static void Tick(object visuals)
        {
            // The "ActiveState is MapState" check was kept here as a cutoff: "we are the tiny
            // party icon on the map, do not go there". We were wrong about the state itself: for the encyclopedia
            // window opened over the map, ActiveState is THE SAME MapState (it is an overlay,
            // not a separate game state). The check quietly turned off the fitting in the encyclopedia
            // too: the log had not a single line about it (noticed 25.09.2026). The tiny icon
            // is hidden separately by Fit(object, int) at assembly (mesh.SetVisibilityMask(0)); redrawing
            // its frame too does no harm, an invisible mesh just moves invisibly.
            if (visuals == null)
            {
                return;
            }
            Tick(visuals, "кадр окна");
        }

        /// <summary>
        /// One-off fitting for preset pictures: thumbnails in the troop tree, faces in lists.
        ///
        /// They are drawn like this: the character is assembled, posed and an animation is played once
        /// (CharacterSpawner.InitWithCharacter -> TickAnimationsAndForceUpdate), then the picture
        /// is taken. Our fitting at armour assembly happens BEFORE this animation, i.e. on the rest
        /// pose, and on the thumbnail the helmet hung off to the side of the head, although in the big window it sat right
        /// (noticed 25.09.2026). So we fit once more when the pose has already been played.
        ///
        /// The "we are on the map" check is deliberately not done here: the encyclopedia is opened from the world map too,
        /// and a thumbnail is static: one correct calculation is all it needs.
        /// </summary>
        public static void FitStatic(object visuals)
        {
            if (visuals != null)
            {
                Tick(visuals, "заготовка");
            }
        }

        // Previously there was a speed-up here: reusing remembered meshes for several frames
        // in a row, rereading the visuals every 15 frames. It broke both the big window and the presets: character
        // windows reuse one and the same visuals object when switching troops in the
        // tree (noticed 25.09.2026), and the stale cache held the meshes of the PREVIOUS character until
        // the frames ran out, so the helmet was not fitted at all. We reread the visuals on every call: this is
        // not a battle of a thousand soldiers but a window with one or two characters, extra garbage is no problem.
        private static void Tick(object visuals, string where)
        {
            EquestriaCrashLog.Try("шлем под расу (" + where + ")", () =>
            {
                if (_getEntity == null || _getEntity.DeclaringType != visuals.GetType())
                {
                    _getData = AccessTools.Method(visuals.GetType(), "GetCopyAgentVisualsData");
                    _getEntity = AccessTools.Method(visuals.GetType(), "GetEntity");
                    _raceData = null;
                }
                var skeleton = (_getEntity?.Invoke(visuals, null) as GameEntity)?.Skeleton;
                if (skeleton == null)
                {
                    return;
                }
                var kept = Read(visuals, skeleton);
                if (kept != null && kept.Meshes.Length > 0)
                {
                    Fit(skeleton, kept.Meshes, kept.Bone, kept.Race, kept.MeshName);
                }
                else if (kept != null && _shiftLoggedMeshes.Add("!missing:" + kept.MeshName))
                {
                    // The race is ours, there is a helmet in the equipment, but no meshes were found on the skeleton: just in
                    // case we watch for this, in case the fitting goes silent somewhere again. By mesh name, not
                    // once only: otherwise the very first miss would forever hide the rest.
                    EquestriaCrashLog.Warn($"шлем под расу ({where}): меш {kept.MeshName}"
                        + $" не найден на скелете (мешей всего {skeleton.GetAllMeshes().Count()})");
                }
            });
        }

        /// <summary>Parse the visuals: race, helmet meshes, head bone. null means there is no helmet.</summary>
        private static Fitted Read(object visuals, Skeleton skeleton)
        {
            var data = _getData?.Invoke(visuals, null);
            if (data == null)
            {
                return null;
            }
            if (_raceData == null)
            {
                _raceData = AccessTools.Property(data.GetType(), "RaceData");
                _equipmentData = AccessTools.Property(data.GetType(), "EquipmentData");
                _monsterData = AccessTools.Property(data.GetType(), "MonsterData");
            }
            if (!(_raceData?.GetValue(data) is int race) || !Scales().ContainsKey(race))
            {
                return null;
            }
            string meshName = (_equipmentData?.GetValue(data) as Equipment)?[EquipmentIndex.Head]
                .Item?.MultiMeshName;
            if (string.IsNullOrEmpty(meshName))
            {
                return null;
            }
            sbyte bone = (_monsterData?.GetValue(data) as Monster)?.HeadLookDirectionBoneIndex ?? HumanHeadBone;
            sbyte mapped = skeleton.GetSkeletonBoneMapping(bone);
            return new Fitted
            {
                MeshName = meshName,
                Meshes = HelmetMeshes(skeleton, meshName),
                Bone = mapped >= 0 && mapped < skeleton.GetBoneCount() ? mapped : bone,
                Race = race,
            };
        }

        private static void AfterArmour(object __instance)
        {
            EquestriaCrashLog.Try("шлем под расу (доспех)", () =>
            {
                var data = AccessTools.Method(__instance.GetType(), "GetCopyAgentVisualsData")
                    ?.Invoke(__instance, null);
                var race = data == null ? null
                    : AccessTools.Property(data.GetType(), "RaceData")?.GetValue(data);
                if (race is int id)
                {
                    // The real card icon is hidden by EquestriaBodyParts.Attach (it sees the name
                    // with which the engine labelled the visuals object); from here we never hide, so as
                    // not to hide a window's helmet by mistake before Attach works out who it is.
                    Fit(__instance, id, isMapIcon: false);
                }
            });
        }

        private static void AfterBuild()
        {
            _building = 0;
        }

        private static void AfterTick(object __instance)
        {
            Tick(__instance);
        }

        private static bool _spawnerLogged;

        private static void AfterSpawner(object __instance)
        {
            EquestriaCrashLog.Try("шлем под расу (заготовка собрана)", () =>
            {
                var field = AccessTools.Field(__instance.GetType(), "_agentVisuals");
                var visuals = field?.GetValue(__instance);
                if (!_spawnerLogged)
                {
                    _spawnerLogged = true;
                    EquestriaCrashLog.Log($"шлем под расу: заготовка {__instance.GetType().Name}"
                        + $" — поле _agentVisuals {(field == null ? "НЕ НАЙДЕНО" : "есть")},"
                        + $" значение {(visuals == null ? "пусто" : "есть")}");
                }
                FitStatic(visuals);
            });
        }

        private static bool _mapConvLogged;

        public static object LastMapConversation { get; private set; }

        // We tick the WHOLE list of conversation visuals, not only the speaker (see the comment at the
        // patch in Apply). The list is private (List<AgentVisuals>); we get it by reflection once
        // per class, as elsewhere in the file; the type is the same for all calls.
        private static void AfterMapConversationTick(object __instance)
        {
            LastMapConversation = __instance;
            EquestriaCrashLog.Try("шлем под расу (разговор на карте)", () =>
            {
                var list = AccessTools.Field(__instance.GetType(), "_agentVisuals")
                    ?.GetValue(__instance) as System.Collections.IEnumerable;
                if (list == null)
                {
                    return;
                }
                // A map conversation has no CharacterObjectStringIdData in the visuals (checked
                // by the log: null for all participants), but the tableau itself has _data with two
                // explicit characters (the player and the interlocutor). By INDEX in the list they cannot be told apart
                // reliably (the order turned out not to be "player, then interlocutor": the first test coloured the wrong
                // one), so we compare the BodyProperties of each visuals (AgentVisualsData.
                // BodyPropertiesData) with the BodyProperties of the player/interlocutor: this is the same data,
                // the key matches byte for byte for one and the same character, regardless of the position
                // in the list. A lord's escort has no Hero of its own: its BodyProperties will match
                // no one, and it stays uncoloured (these are not main characters).
                var conv = ConversationCharacterKeys(__instance);
                int count = 0;
                foreach (var visuals in list)
                {
                    Tick(visuals, "разговор");
                    // A map conversation assembles its participants ITS OWN way: EquestriaBodyParts.Attach
                    // is not hooked to its tick (tail/wings/horn come via AgentVisuals.Create/
                    // Refresh somewhere up the chain, and the lore colour sometimes does not get there, for example
                    // if CharacterObjectStringIdData is still empty at the moment of Create). We colour and attach
                    // the body parts ONCE MORE right here, by a path known to work; Attach is idempotent.
                    AttachAndColorConversationParticipant(visuals, conv);
                    count++;
                }
                if (!_mapConvLogged)
                {
                    _mapConvLogged = true;
                    EquestriaCrashLog.Log($"шлем под расу: разговор на карте — участников {count}");
                }
            });
        }

        // The character's race and BodyProperties, the same way as Read() above
        // (GetCopyAgentVisualsData), but with a separate method cache: the visuals type of conversation
        // participants is not necessarily the same as for _getData/_raceData (those are cached for
        // the last call of the ordinary Tick).
        private static System.Reflection.MethodInfo _convGetData;
        private static System.Reflection.PropertyInfo _convRaceData;
        private static System.Reflection.PropertyInfo _convBodyData;

        // Who is who in the conversation. Telling the player/interlocutor apart by INDEX in _agentVisuals
        // is unreliable (the first test coloured the wrong one: the order is not "player, then interlocutor", as
        // expected), so we compare BodyProperties: for one and the same character the key
        // matches byte for byte both on the Hero and on its visuals in the conversation, regardless of the
        // position in the list.
        private struct ConvKeys
        {
            public string PlayerKey, PlayerId, PartnerKey, PartnerId;
        }

        private static System.Reflection.FieldInfo _dataField;
        private static System.Reflection.PropertyInfo _playerCharData, _partnerCharData;
        private static System.Reflection.FieldInfo _charField;

        private static ConvKeys ConversationCharacterKeys(object tableau)
        {
            if (_dataField == null || _dataField.DeclaringType != tableau.GetType())
            {
                _dataField = AccessTools.Field(tableau.GetType(), "_data");
            }
            var data = _dataField?.GetValue(tableau);
            if (data == null)
            {
                return default;
            }
            if (_playerCharData == null || _playerCharData.DeclaringType != data.GetType())
            {
                _playerCharData = AccessTools.Property(data.GetType(), "PlayerCharacterData");
                _partnerCharData = AccessTools.Property(data.GetType(), "ConversationPartnerData");
            }
            CharacterIdAndKey(_playerCharData?.GetValue(data), out string playerId, out string playerKey);
            CharacterIdAndKey(_partnerCharData?.GetValue(data), out string partnerId, out string partnerKey);
            return new ConvKeys { PlayerKey = playerKey, PlayerId = playerId, PartnerKey = partnerKey, PartnerId = partnerId };
        }

        // ConversationCharacterData.Character (CharacterObject) is a public field, not a property.
        // BodyProperties are taken from HeroObject: the CharacterObject template itself has no unique
        // appearance of its own; only a specific living Hero has one.
        private static void CharacterIdAndKey(object conversationCharacterData, out string id, out string bodyKey)
        {
            id = null;
            bodyKey = null;
            if (conversationCharacterData == null)
            {
                return;
            }
            if (_charField == null || _charField.DeclaringType != conversationCharacterData.GetType())
            {
                _charField = AccessTools.Field(conversationCharacterData.GetType(), "Character");
            }
            var character = _charField?.GetValue(conversationCharacterData);
            if (character == null)
            {
                return;
            }
            id = AccessTools.Property(character.GetType(), "StringId")?.GetValue(character) as string;
            var hero = AccessTools.Property(character.GetType(), "HeroObject")?.GetValue(character);
            object bodyProps = hero == null
                ? null
                : AccessTools.Property(hero.GetType(), "BodyProperties")?.GetValue(hero);
            bodyKey = bodyProps?.ToString();
        }

        private static void AttachAndColorConversationParticipant(object visuals, ConvKeys conv)
        {
            EquestriaCrashLog.Try("части тела и цвет (разговор)", () =>
            {
                if (_convGetData == null || _convGetData.DeclaringType != visuals.GetType())
                {
                    _convGetData = AccessTools.Method(visuals.GetType(), "GetCopyAgentVisualsData");
                    _convRaceData = null;
                    _convBodyData = null;
                }
                var data = _convGetData?.Invoke(visuals, null);
                if (data == null)
                {
                    return;
                }
                if (_convRaceData == null)
                {
                    _convRaceData = AccessTools.Property(data.GetType(), "RaceData");
                    _convBodyData = AccessTools.Property(data.GetType(), "BodyPropertiesData");
                }
                if (!(_convRaceData?.GetValue(data) is int race))
                {
                    return;
                }
                string bodyKey = _convBodyData?.GetValue(data)?.ToString();
                string charStringId = bodyKey != null && bodyKey == conv.PartnerKey ? conv.PartnerId
                    : bodyKey != null && bodyKey == conv.PlayerKey ? conv.PlayerId
                    : null;
                EquestriaBodyParts.Attach(visuals, race, "разговор", cacheKey: visuals);
                EquestriaBodyParts.ApplyLoreColorIfPony(visuals, race, charStringId);
            });
        }

        private const sbyte HumanHeadBone = 13;
        private static bool _boneLogged;

        private static void AfterBone(Monster __instance, ref sbyte __result)
        {
            if (__result >= 0 || __instance == null || string.IsNullOrEmpty(__instance.StringId))
            {
                return;
            }
            // only our races: for vanilla monsters the number is already correct
            if (!Scales().Keys.Any() || !ScaleByRace.Keys.Any(r => __instance.StringId.StartsWith(r)))
            {
                return;
            }
            __result = HumanHeadBone;
            if (!_boneLogged)
            {
                _boneLogged = true;
                EquestriaCrashLog.Log($"шлем под расу: у монстра {__instance.StringId} кость головы "
                    + $"была -1, подставлена {HumanHeadBone}");
            }
        }


    }
}
