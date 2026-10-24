using System;
using System.Collections.Generic;
using System.Linq;
using TaleWorlds.Core;
using TaleWorlds.Engine;
using TaleWorlds.Library;
using TaleWorlds.MountAndBlade;

namespace EquestriaMod
{
    // Bone zones: a port of DismembermentPlus.DataHelpers.HumanBoneHelper.cs without changes
    // (the same HumanBone indices).
    internal static class EquestriaDismembermentBoneZones
    {
        internal static bool IsHeadZone(this HumanBone bone) => bone == HumanBone.Neck || bone == HumanBone.Head;
        internal static bool IsShoulderZoneL(this HumanBone bone) =>
            bone == HumanBone.ShoulderL || bone == HumanBone.UpperarmL || bone == HumanBone.UpperarmTwist1L;
        internal static bool IsShoulderZoneR(this HumanBone bone) =>
            bone == HumanBone.ShoulderR || bone == HumanBone.UpperarmR || bone == HumanBone.UpperarmTwist1R;
        internal static bool IsThighZoneL(this HumanBone bone) => bone == HumanBone.ThighL;
        internal static bool IsThighZoneR(this HumanBone bone) => bone == HumanBone.ThighR;
    }

    // Severing limbs: a port of the DismembermentPlus mod's mechanics (nexusmods.com/
    // mountandblade2bannerlord/mods/2190, decompiled 07.10.2026) to our races. The OnRegisterBlow
    // hook and the bone zones (HumanBone) are ported without changes: the indices are the same ones we
    // use in our races' bone names (bip01_l_thigh_1, bip01_l_clavicle_14: the trailing number is
    // the HumanBone index), the race is on the human skeleton, the hit zone does not change at all.
    //
    // 07.10.2026: extended from ponies to all races. Every race's head is a separate object
    // (eq_<race>_head), it needed no new assets for anyone (checked against tools/export_*.py:
    // the head is exported as a separate mesh for all seven races). Arms/legs are another story: for the pony
    // eq_pony_gloves/eq_pony_legs are cut into _l/_r (tools/pony_edit_split_limbs.py), for the other
    // races this half is still one piece; until we cut them the same way (Blender, per race),
    // severing an arm/leg simply does not trigger for them (RaceInfo.LimbsSplit=false, see below).
    public class EquestriaDismemberment : MissionBehavior
    {
        public override MissionBehaviorType BehaviorType => MissionBehaviorType.Other;

        // The crash (0xc0000005) was not caused by ActivateRagdoll() itself but by our own added
        // SetLinearVelocity/SetAngularVelocity/SetVelocityLimits on top: the original
        // DismembermentPlus (decompiled, DismembermentPlusMissionLogic.GetDismemberedEntity)
        // has no such calls at all, and no crashes. Comparing with their code found the real difference:
        // before enabling physics they explicitly set entity.BodyFlag = BodyFlags.None and a special
        // entity.EntityFlags (ours were both at the default after CreateEmptyDynamic). We repeat their
        // configuration in SpawnFlyingPart: a real ragdoll, without our own physics substitution.
        private static readonly EntityFlags DismemberedPartFlags =
            EntityFlags.Ignore | EntityFlags.NonModifiableFromEditor | EntityFlags.NotAffectedBySeason
            | EntityFlags.DontCheckHandness | EntityFlags.RecordToSceneReplay | EntityFlags.DontSaveToScene;

        // Enabling physics is delayed by ActivateDelay seconds after the entity is created: see the
        // comment in SpawnFlyingPart. While the entity waits, it just hangs in the correct pose
        // without physics (no worse than a frozen death frame).
        private const float ActivateDelay = 0.35f;
        private static readonly List<(GameEntity Entity, float TimeLeft)> _pendingRagdoll =
            new List<(GameEntity, float)>();

        // A severed part used to live forever: entity.Remove() was never called, the entity with
        // its skeleton and copied textures just piled up in the scene. In a 100 vs 100 battle with
        // a 100% chance that is dozens of extra full-size entities per battle; this is probably where
        // the GPU's ("Not enough memory resources
        // to complete the operation") came from (noticed by
        // the user 07.10.2026 after a series of test battles). The part is removed FlyingLifetime
        // seconds after it has settled: the eye no longer notices, and before that it was not visible anyway.
        private const float FlyingLifetime = 20f;
        private static readonly List<(GameEntity Entity, float TimeLeft)> _flyingLifetimes =
            new List<(GameEntity, float)>();

        public override void OnMissionTick(float dt)
        {
            for (int i = _pendingRagdoll.Count - 1; i >= 0; i--)
            {
                var (entity, timeLeft) = _pendingRagdoll[i];
                if (entity == null)
                {
                    _pendingRagdoll.RemoveAt(i);
                    continue;
                }
                timeLeft -= dt;
                if (timeLeft > 0f)
                {
                    _pendingRagdoll[i] = (entity, timeLeft);
                    continue;
                }
                _pendingRagdoll.RemoveAt(i);
                GameEntityPhysicsExtensions.SetPhysicsState(entity, true, false);
                GameEntityPhysicsExtensions.EnableDynamicBody(entity);
                entity.ActivateRagdoll();
                _flyingLifetimes.Add((entity, FlyingLifetime));
            }
            for (int i = _flyingLifetimes.Count - 1; i >= 0; i--)
            {
                var (entity, timeLeft) = _flyingLifetimes[i];
                if (entity == null)
                {
                    _flyingLifetimes.RemoveAt(i);
                    continue;
                }
                timeLeft -= dt;
                if (timeLeft > 0f)
                {
                    _flyingLifetimes[i] = (entity, timeLeft);
                    continue;
                }
                _flyingLifetimes.RemoveAt(i);
                entity.Remove(73);
            }
        }

        // 07.10.2026: 100% within the same conditions (a finishing cutting swing into the right zone),
        // so that the effect is clearly visible in a test battle and not lost to chance.
        private const float HeadChance = 1.0f;
        private const float ArmChance = 1.0f;
        private const float LegChance = 1.0f;

        /// <summary>What flies off with the head/arm/leg for a given race: checked against
        /// EquestriaBodyParts.PartByRace/EarMeshByRace/HairReferenceByRace (the same split into
        /// horn/ears/mane per race); null means the race simply has no such part.</summary>
        private sealed class RaceInfo
        {
            public string HeadMesh;
            public string HornMesh;
            public string EarsMesh;
            public string HairMesh;
            public string GlovesMesh;
            public string LegsMesh;
            public bool LimbsSplit;
        }

        private static readonly Dictionary<string, RaceInfo> InfoByRace = new Dictionary<string, RaceInfo>
        {
            { "pony", new RaceInfo { HeadMesh = "eq_pony_head", HornMesh = "eq_pony_horn",
                EarsMesh = "eq_pony_ears", HairMesh = "eq_pony_hair",
                GlovesMesh = "eq_pony_gloves", LegsMesh = "eq_pony_legs", LimbsSplit = true } },
            { "changeling", new RaceInfo { HeadMesh = "eq_changeling_head", HornMesh = "eq_changeling_horn",
                EarsMesh = "eq_changeling_ears", GlovesMesh = "eq_changeling_gloves", LegsMesh = "eq_changeling_legs",
                LimbsSplit = true } },
            { "deer", new RaceInfo { HeadMesh = "eq_deer_head", HornMesh = "eq_deer_horn",
                EarsMesh = "eq_deer_ears", HairMesh = "eq_deer_hair",
                GlovesMesh = "eq_deer_gloves", LegsMesh = "eq_deer_legs", LimbsSplit = true } },
            { "yak", new RaceInfo { HeadMesh = "eq_yak_head", HornMesh = "eq_yak_horn", HairMesh = "eq_yak_hair",
                GlovesMesh = "eq_yak_gloves", LegsMesh = "eq_yak_legs", LimbsSplit = true } },
            { "dragon", new RaceInfo { HeadMesh = "eq_dragon_head", HornMesh = "eq_dragon_horn",
                HairMesh = "eq_dragon_hair", GlovesMesh = "eq_dragon_gloves", LegsMesh = "eq_dragon_legs",
                LimbsSplit = true } },
            { "griffon", new RaceInfo { HeadMesh = "eq_griffon_head", EarsMesh = "eq_griffon_ear",
                GlovesMesh = "eq_griffon_gloves", LegsMesh = "eq_griffon_legs", LimbsSplit = true } },
            { "hippogriff", new RaceInfo { HeadMesh = "eq_hippogriff_head", LimbsSplit = true,
                GlovesMesh = "eq_hippogriff_gloves", LegsMesh = "eq_hippogriff_legs" } },
        };

        private static Dictionary<int, RaceInfo> _infoByRaceId;

        private static Dictionary<int, RaceInfo> InfoByRaceId()
        {
            if (_infoByRaceId == null)
            {
                _infoByRaceId = new Dictionary<int, RaceInfo>();
                foreach (var pair in InfoByRace)
                {
                    int race = TaleWorlds.Core.FaceGen.GetRaceOrDefault(pair.Key);
                    // GetRaceOrDefault returns 0 (human) for an unknown race; do not confuse it
                    // with humans, they do not need severing.
                    if (race != 0)
                    {
                        _infoByRaceId[race] = pair.Value;
                    }
                }
            }
            return _infoByRaceId;
        }

        public override void OnRegisterBlow(Agent attacker, Agent victim, WeakGameEntity realHitEntity, Blow b,
            ref AttackCollisionData collisionData, in MissionWeapon attackerWeapon)
        {
            AttackCollisionData data = collisionData;
            EquestriaCrashLog.Try("отрубание конечностей", () => RegisterBlow(attacker, victim, data));
        }

        private static void RegisterBlow(Agent attacker, Agent victim, AttackCollisionData collisionData)
        {
            if (attacker == null || victim == null || victim.Character == null
                || !InfoByRaceId().TryGetValue(victim.Character.Race, out RaceInfo info))
            {
                return;
            }
            HumanBone bone = (HumanBone)collisionData.CollisionBoneIndex;
            bool isCut = collisionData.DamageType == (int)DamageTypes.Cut;
            bool isSwing = collisionData.StrikeType == (int)StrikeType.Swing;
            if (!isCut || !isSwing)
            {
                return;
            }
            Agent.UsageDirection direction = attacker.AttackDirection;
            bool severableLR = direction == Agent.UsageDirection.AttackLeft || direction == Agent.UsageDirection.AttackRight;
            bool severableAny = direction == Agent.UsageDirection.AttackUp || direction == Agent.UsageDirection.AttackDown
                || severableLR;

            if (bone.IsHeadZone())
            {
                if (victim.State != AgentState.Killed || !severableLR)
                {
                    return;
                }
                if (MBRandom.RandomFloat > HeadChance)
                {
                    EquestriaCrashLog.Log($"отрубание: {victim.Name} — голова, не повезло с шансом");
                    return;
                }
                EquestriaCrashLog.Log($"отрубание: {victim.Name} — голова, сработало");
                Behead(victim, bone, info);
                return;
            }
            if (!severableAny || victim.State == AgentState.Active)
            {
                return;
            }
            // Arms/legs are cut into _l/_r only for the pony (tools/pony_edit_split_limbs.py): the
            // other races have no such asset yet, and without it there is no half to fly off.
            if (!info.LimbsSplit)
            {
                return;
            }
            if (bone.IsShoulderZoneL() || bone.IsShoulderZoneR())
            {
                string side = bone.IsShoulderZoneL() ? "л" : "п";
                if (MBRandom.RandomFloat > ArmChance)
                {
                    EquestriaCrashLog.Log($"отрубание: {victim.Name} — плечо-{side}, не повезло с шансом");
                    return;
                }
                EquestriaCrashLog.Log($"отрубание: {victim.Name} — плечо-{side}, сработало");
                DismemberLimb(victim, bone, info.GlovesMesh, bone.IsShoulderZoneL());
                return;
            }
            if (bone.IsThighZoneL() || bone.IsThighZoneR())
            {
                string side = bone.IsThighZoneL() ? "л" : "п";
                if (MBRandom.RandomFloat > LegChance)
                {
                    EquestriaCrashLog.Log($"отрубание: {victim.Name} — бедро-{side}, не повезло с шансом");
                    return;
                }
                EquestriaCrashLog.Log($"отрубание: {victim.Name} — бедро-{side}, сработало");
                DismemberLimb(victim, bone, info.LegsMesh, bone.IsThighZoneL());
            }
        }

        private static void Behead(Agent victim, HumanBone headBone, RaceInfo info)
        {
            Skeleton skeleton = victim.AgentVisuals?.GetSkeleton();
            if (skeleton == null)
            {
                return;
            }
            HideWholePart(skeleton, info.HeadMesh);
            // Horn, ears and mane are separate meshes attached to a bone (like the tail/wings), not
            // part of the head mesh (EquestriaBodyParts.cs PartByRace); without this they stayed hanging on
            // the beheaded body (noticed by the user 07.10.2026, the mane separately on 07.10.2026).
            // Hide them and carry them off with the head: anatomically they are all part of it. Not every
            // race has all three (griffon has only ears, hippogriff nothing at all); skip what is missing.
            var extras = new List<string>();
            if (info.HornMesh != null) { extras.AddRange(HideWithVariants(skeleton, info.HornMesh)); }
            if (info.EarsMesh != null) { HideWholePart(skeleton, info.EarsMesh); extras.Add(info.EarsMesh); }
            if (info.HairMesh != null) { extras.AddRange(HideWithVariants(skeleton, info.HairMesh)); }
            SpawnFlyingPart(victim, headBone, info.HeadMesh, extraMeshNames: extras.ToArray());
            victim.CreateBloodBurstAtLimb((sbyte)headBone, 0.5f + MBRandom.RandomFloat * 0.5f);
        }

        /// <summary>Arm/leg: hide the whole original part (eq_pony_gloves/eq_pony_legs, both
        /// sides at once; the surviving half is NOT shown separately on the live skeleton, see below
        /// why), the severed half is carried off by a separate entity with a ragdoll.</summary>
        private static void DismemberLimb(Agent victim, HumanBone bone, string wholeMeshName, bool severedIsLeft)
        {
            Skeleton skeleton = victim.AgentVisuals?.GetSkeleton();
            if (skeleton == null)
            {
                return;
            }
            // Previously the "surviving" half was added right here (skeleton.AddComponent) onto the live,
            // actively animated skeleton of the victim; after the very first battle with this code the engine crashed
            // (0xc0000005 in TaleWorlds.Native.dll, the same signature as with the wing animation channel).
            // Beheading, which only hides the mesh and adds nothing to the live skeleton,
            // caused no crashes, so the problem is exactly AddComponent on a live one. So the victim loses
            // both sides of the part entirely; the severed half still flies as a separate entity
            // (that is already the safe path, like the head's).
            HideWholePart(skeleton, wholeMeshName);
            string flyName = wholeMeshName + (severedIsLeft ? "_l" : "_r");
            // The colour is taken from the WHOLE name (eq_pony_gloves), not from the cut one (eq_pony_gloves_l):
            // on the live skeleton the mesh stays one whole piece under the whole name (only the set
            // of STATIC assets for the severed half is cut, not the equipment itself on the
            // victim), so searching by flyName found nothing and the severed arm/leg
            // stayed the default (white) colour; the head was tinted correctly because its name without
            // a suffix matches literally (noticed by the user 08.10.2026).
            SpawnFlyingPart(victim, bone, flyName, wholeMeshName);
            victim.CreateBloodBurstAtLimb((sbyte)bone, 0.5f + MBRandom.RandomFloat * 0.5f);
        }

        /// <summary>Hides the mesh(es) whose name is EXACTLY partName (ignoring a copy suffix like
        /// ".001"); it is important not to hit eq_pony_gloves_l/_r by a prefix match with eq_pony_gloves.
        /// internal: EquestriaFlightScroll (the flight scroll) hides the legs with the same trick.</summary>
        /// <summary>Hides a part and its variants <c>name_2..name_9</c> (the doe's antlers and braids, 10.10.2026:
        /// only the chosen ones are visible, see EquestriaBodyParts.DeerAntlerVariant) and returns the names of those
        /// that were visible: the severed head carries them off. If none was visible (under a
        /// helmet the braid is not built), an empty list; for parts without variants, the name itself, as before.</summary>
        private static List<string> HideWithVariants(Skeleton skeleton, string partName)
        {
            var names = new List<string> { partName };
            for (int i = 2; i <= 9; i++)
            {
                names.Add(partName + "_" + i);
            }
            var present = names.Where(n => skeleton.GetAllMeshes().Any(m => m != null && m.Name != null
                && (string.Equals(m.Name, n, StringComparison.OrdinalIgnoreCase)
                    || m.Name.StartsWith(n + ".", StringComparison.OrdinalIgnoreCase)))).ToList();
            if (present.Count <= 1)
            {
                HideWholePart(skeleton, partName);
                return new List<string> { partName };
            }
            var visible = present.Where(n => skeleton.GetAllMeshes().Any(m => m != null && m.Name != null
                && m.VisibilityMask != 0
                && (string.Equals(m.Name, n, StringComparison.OrdinalIgnoreCase)
                    || m.Name.StartsWith(n + ".", StringComparison.OrdinalIgnoreCase)))).ToList();
            foreach (string n in present)
            {
                HideWholePart(skeleton, n);
            }
            return visible;
        }

        internal static void HideWholePart(Skeleton skeleton, string partName)
        {
            foreach (var mesh in skeleton.GetAllMeshes())
            {
                if (mesh == null || mesh.Name == null)
                {
                    continue;
                }
                bool exact = string.Equals(mesh.Name, partName, StringComparison.OrdinalIgnoreCase);
                bool copySuffix = mesh.Name.StartsWith(partName + ".", StringComparison.OrdinalIgnoreCase);
                if (exact || copySuffix)
                {
                    mesh.SetVisibilityMask(0);
                }
            }
        }

        /// <summary>Copies the colour (Mesh.Color/Color2, e.g. the mane tone, which is tinted not
        /// in the material but in the mesh instance itself) from the live skeleton to the fresh copy. Without this
        /// the MetaMesh.GetCopy copy comes out in the default colour: the severed head's mane fades
        /// (noticed by the user 07.10.2026).</summary>
        private static void CopyMeshColorIfAny(Skeleton sourceSkeleton, string partName, MetaMesh target)
        {
            foreach (var mesh in sourceSkeleton.GetAllMeshes())
            {
                if (mesh == null || mesh.Name == null)
                {
                    continue;
                }
                bool exact = string.Equals(mesh.Name, partName, StringComparison.OrdinalIgnoreCase);
                bool copySuffix = mesh.Name.StartsWith(partName + ".", StringComparison.OrdinalIgnoreCase);
                if (!exact && !copySuffix)
                {
                    continue;
                }
                uint color = mesh.Color;
                uint color2 = mesh.Color2;
                for (int i = 0; i < target.MeshCount; i++)
                {
                    Mesh sub = target.GetMeshAtIndex(i);
                    sub.Color = color;
                    sub.Color2 = color2;
                }
                return;
            }
        }

        /// <summary>A separate entity with a ragdoll for the severed part: meshName and any
        /// extraMeshNames (e.g. the horn together with the head) are put on the same skeleton clone,
        /// so that they fly off together. colorSourceName is the name to look for on the victim's LIVE skeleton when
        /// copying the colour (CopyMeshColorIfAny), if it differs from meshName: for an arm/leg
        /// meshName is the cut asset (eq_pony_gloves_l), while on the live skeleton the part stays
        /// whole under the name without a suffix (eq_pony_gloves); by default (null) meshName is used,
        /// which is right for the head, where the name matches literally.</summary>
        private static void SpawnFlyingPart(Agent victim, HumanBone bone, string meshName,
            string colorSourceName = null, params string[] extraMeshNames)
        {
            MetaMesh mesh = MetaMesh.GetCopy(meshName, true, false);
            if (mesh == null)
            {
                EquestriaCrashLog.Warn("отрубание: не скопирован " + meshName);
                return;
            }
            GameEntity entity = GameEntity.CreateEmptyDynamic(Mission.Current.Scene, true);
            entity.Name = entity.GetGuid();
            entity.Skeleton = Skeleton.CreateFromModel("human_skeleton");
            // The speed is small (0.3), not 1 and not 0. With speed=1 all severed parts systematically
            // flew in one direction, the way the fighter was facing at the moment of the hit (in a line
            // battle almost all fighters on one side face the enemy the same way, so the drift
            // was not random but "towards the other side of the field", noticed by the user
            // 07.10.2026), while a full freeze (0) gave no visible push at all
            // (at the user's request to add a little impulse). Within ActivateDelay seconds before
            // physics is enabled it plays a little further, and the ragdoll picks up this small motion.
            // entity.ApplyLocalImpulseToDynamicBody/SetLinearVelocity etc. are left alone on purpose:
            // this whole group of functions (writes to/pushes the entity's "body" after ActivateRagdoll()) has already
            // crashed the engine twice on other calls (see DismemberedPartFlags), we did not risk
            // a third.
            MBSkeletonExtensions.SetAnimationAtChannel(entity.Skeleton,
                victim.AgentVisuals.GetSkeleton().GetAnimationAtChannel(0), 0, 0.3f, -1f, 0f);
            // Put the new entity's root right at the victim's global frame (its own
            // position/rotation), NOT at the computed world position of the bone. Previously it was put exactly
            // at the bone position, and the new entity's skeleton, given the same animation/pose, ITSELF
            // walks the whole bone-from-root chain again and adds the same offset ONCE MORE (the root was
            // already at the bone point, and then the root→bone path was added to it again): the severed
            // part ended up shifted by the "root-bone" distance beyond what is needed. For the head
            // (the top of the whole spine chain) this offset is the largest, hence "shifts far
            // upwards" (noticed by the user 07.10.2026). If you simply repeat the victim's
            // own frame, the skeleton reproduces the pose exactly by itself, without the extra addition.
            MatrixFrame globalFrame = victim.AgentVisuals.GetGlobalFrame();
            entity.SetGlobalFrame(ref globalFrame, true);
            Skeleton victimSkeleton = victim.AgentVisuals.GetSkeleton();
            entity.Skeleton.AddComponent(mesh);
            CopyMeshColorIfAny(victimSkeleton, colorSourceName ?? meshName, mesh);
            // Blood right on the cut of the severed part, at the moment it is created (at the user's
            // request 08.10.2026): the same effect as on the victim's stump (psys_game_blood_
            // sword_exit, already boosted 4 times, see equestria_more_blood.xml), but
            // CreateBloodBurstAtLimb exists only on Agent, and the severed part has none, it is its own
            // bare GameEntity with its own skeleton; so the particle is attached directly to a bone of its
            // own skeleton (ParticleSystem.CreateParticleSystemAttachedToBone), not through the
            // Agent API. The bone index is the same HumanBone: both skeletons are built from one model
            // "human_skeleton", the numbering matches (as everywhere in this file, see (sbyte)bone
            // above).
            MatrixFrame boneLocalFrame = MatrixFrame.Identity;
            ParticleSystem.CreateParticleSystemAttachedToBone(
                "psys_game_blood_sword_exit", entity.Skeleton, (sbyte)bone, ref boneLocalFrame);
            foreach (string extraName in extraMeshNames)
            {
                MetaMesh extraMesh = MetaMesh.GetCopy(extraName, true, false);
                if (extraMesh == null)
                {
                    EquestriaCrashLog.Warn("отрубание: не скопирован " + extraName);
                    continue;
                }
                entity.Skeleton.AddComponent(extraMesh);
                CopyMeshColorIfAny(victimSkeleton, extraName, extraMesh);
            }
            entity.BodyFlag = BodyFlags.None;
            entity.EntityFlags = DismemberedPartFlags;
            // SetMaxDepenetrationVelocity crashed the same way as SetLinearVelocity/SetVelocityLimits
            // before (0xc0000005, 07.10.2026), which confirms the original guess: ANY function
            // from GameEntityPhysicsExtensions that touches the entity's "body" after ActivateRagdoll() is not
            // fit for a ragdoll (there is no single body there, only per bone). BodyFlag/EntityFlags
            // were the real cause of a SEPARATE earlier crash, but that does not make the other
            // functions of this group safe; we do not touch them any more.
            //
            // The position (see the log above) is correct and does not change right after ActivateRagdoll: the scatter
            // happens later, inside the simulation itself. It looks like a "ragdoll explosion" from initial
            // overlap: the new part appears right where the fighter's corpse is, which at that
            // moment is often still ragdolling itself, and the bone capsules overlap each other.
            // Without access to velocity clamping, enabling physics is delayed by ActivateDelay seconds:
            // the corpse has time to fly apart/settle, and the overlap at activation is smaller.
            _pendingRagdoll.Add((entity, ActivateDelay));
        }
    }
}
