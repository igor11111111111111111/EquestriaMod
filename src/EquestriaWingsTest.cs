using System;
using System.Collections.Generic;
using System.Linq;
using TaleWorlds.Core;
using TaleWorlds.Engine;
using TaleWorlds.Library;
using TaleWorlds.MountAndBlade;

namespace EquestriaMod
{
    // Flapping wings of fliers (10.10.2026). human_skeleton has no wing bones, the pony wings are a rigid
    // mesh on spine2 (tools/creature_data.py). Solution: two RIGID meshes (left/right wing,
    // tools/make_wing_meshes.py, origin at the wing root by the spine) as separate
    // entities; every frame before rendering they are placed on the agent's spine2 bone with the root offset, and
    // the code itself rotates them around the root by a sine - the flap. The stock wings eq_pony_wings are hidden.
    //
    // Rejected approach (10.10.2026): a prop on the vanilla bird_skeleton with a skinned wing mesh and
    // the anim_bird_cycle clip (tools/make_wings_rig.py). The mechanism works (a hawk on the back flaps),
    // but the mesh-to-bird-bone binding cannot be measured in game, and after six reimports the wing still
    // rotated not around its root. The script and prefab eq_pony_wings_rig are kept for the future.
    public class EquestriaWingsTest : MissionBehavior
    {
        private const bool Enabled = true;
        private const sbyte SpineBone = 11; // spine2 in human_skeleton (tools/engine_rest_human_skeleton.txt)

        // Winged races: rigid wing prefabs, the stock mesh (hidden) and the wing roots in model
        // coordinates (Blender, printed by tools/make_wing_meshes.py -- <race>). The model in Blender faces -Y,
        // the agent in the engine faces +Y: agent space = Blender rotated 180° around Z.
        private sealed class RaceWings
        {
            public string PrefabLeft, PrefabRight, RigidMesh;
            public Vec3 RootLeft, RootRight;
            public float SweepDeg;   // forward turn of the wing tips around the vertical (request 10.10.2026)
        }

        private static readonly Dictionary<string, RaceWings> Races = new Dictionary<string, RaceWings>
        {
            { "pony", new RaceWings { PrefabLeft = "eq_pony_wing_l", PrefabRight = "eq_pony_wing_r", RigidMesh = "eq_pony_wings",
                RootLeft = new Vec3(0.0779f, 0.1012f, 1.3045f), RootRight = new Vec3(-0.0750f, 0.0998f, 1.3129f) } },
            { "dragon", new RaceWings { PrefabLeft = "eq_dragon_wing_l", PrefabRight = "eq_dragon_wing_r", RigidMesh = "eq_dragon_wings",
                RootLeft = new Vec3(0.0167f, 0.1109f, 1.2695f), RootRight = new Vec3(-0.0229f, 0.1160f, 1.2663f), SweepDeg = 15f } },
            { "griffon", new RaceWings { PrefabLeft = "eq_griffon_wing_l", PrefabRight = "eq_griffon_wing_r", RigidMesh = "eq_griffon_wings",
                RootLeft = new Vec3(0.0428f, 0.1287f, 1.2685f), RootRight = new Vec3(-0.0414f, 0.1246f, 1.2601f), SweepDeg = 15f } },
            { "hippogriff", new RaceWings { PrefabLeft = "eq_hippogriff_wing_l", PrefabRight = "eq_hippogriff_wing_r", RigidMesh = "eq_hippogriff_wings",
                RootLeft = new Vec3(0.0303f, 0.1695f, 1.2228f), RootRight = new Vec3(-0.0247f, 0.1723f, 1.2053f), SweepDeg = 15f } },
            { "changeling", new RaceWings { PrefabLeft = "eq_changeling_wing_l", PrefabRight = "eq_changeling_wing_r", RigidMesh = "eq_changeling_wings",
                RootLeft = new Vec3(0.0454f, 0.1324f, 1.3299f), RootRight = new Vec3(-0.0469f, 0.1326f, 1.3264f), SweepDeg = 15f } },
        };
        // Flap: angle around the longitudinal (forward) axis through the root; the sign is mirrored per side.
        private const float FlapAmplitudeDeg = 45f;
        private const float FlapPeriod = 1.6f;              // seconds per flap
        private const float FlapRestDeg = 10f;              // wings slightly raised in the middle position
        // Mesh rotation around the vertical relative to the agent: 180 - as for the skinned pony meshes
        // (Blender -Y -> agent +Y). If the wings end up with the edge backward, set 0.
        private const float MeshYawDeg = 180f;
        private const float WingScaleMin = 0.85f;           // flier wing size, deterministic per agent
        private const float WingScaleMax = 1.0f;

        public override MissionBehaviorType BehaviorType => MissionBehaviorType.Other;

        private sealed class Wings
        {
            public GameEntity Left;
            public GameEntity Right;
            public MatrixFrame LocalLeft;    // left wing root relative to the spine2 bone
            public MatrixFrame LocalRight;
            public float Phase;
            public float Period;     // each has its own period so a formation does not flap in sync
            public float Scale;      // wing size: 0.85..1.0 (user's request 10.10.2026)
            public float Sweep;      // radians, forward turn around the vertical
            public int ColorTries;   // color is copied from the stock wing for several frames in a row
            public string RigidMesh;
        }

        private readonly Dictionary<Agent, Wings> _wings = new Dictionary<Agent, Wings>();

        public override void OnPreDisplayMissionTick(float dt)
        {
            base.OnPreDisplayMissionTick(dt);
            if (!Enabled || Mission.Current == null)
            {
                return;
            }
            foreach (Agent agent in Mission.Current.Agents)
            {
                if (agent == null || agent.IsMount || !agent.IsActive() || !HasWings(agent))
                {
                    continue;
                }
                EquestriaCrashLog.Try("крылья", () => Tick(agent, dt));
            }
        }

        private static RaceWings WingsOf(Agent agent)
        {
            if (!EquestriaFlightScroll.HasScrollPublic(agent))
            {
                return null;
            }
            string[] races = TaleWorlds.Core.FaceGen.GetRaceNames();
            int race = agent.Character?.Race ?? -1;
            RaceWings cfg;
            return races != null && race >= 0 && race < races.Length && Races.TryGetValue(races[race], out cfg) ? cfg : null;
        }

        private static bool HasWings(Agent agent) => WingsOf(agent) != null;

        private static MatrixFrame RootFrame(Vec3 blender)
        {
            Mat3 rot = Mat3.Identity;
            rot.RotateAboutUp(MeshYawDeg * (float)Math.PI / 180f);
            return new MatrixFrame(rot, new Vec3(-blender.x, -blender.y, blender.z));
        }

        private void Tick(Agent agent, float dt)
        {
            MBAgentVisuals visuals = agent.AgentVisuals;
            Skeleton skeleton = visuals?.GetSkeleton();
            if (skeleton == null)
            {
                return;
            }
            Wings wings;
            if (!_wings.TryGetValue(agent, out wings))
            {
                RaceWings cfg = WingsOf(agent);
                GameEntity left = GameEntity.Instantiate(Mission.Current.Scene, cfg.PrefabLeft, true);
                GameEntity right = GameEntity.Instantiate(Mission.Current.Scene, cfg.PrefabRight, true);
                if (left == null || right == null)
                {
                    EquestriaCrashLog.Warn("крылья: нет заготовок " + cfg.PrefabLeft + "/" + cfg.PrefabRight);
                    _wings[agent] = new Wings();
                    return;
                }
                MatrixFrame boneRest = skeleton.GetBoneEntitialRestFrame(SpineBone, false);
                wings = new Wings
                {
                    Left = left,
                    Right = right,
                    LocalLeft = boneRest.TransformToLocal(RootFrame(cfg.RootLeft)),
                    LocalRight = boneRest.TransformToLocal(RootFrame(cfg.RootRight)),
                    // Out of sync: phase by agent index (golden angle - evenly around the circle) and
                    // period +-15% - otherwise all created in one tick flapped in sync.
                    Phase = agent.Index * 2.39996f,
                    Period = FlapPeriod * (0.85f + 0.3f * ((agent.Index * 7919) % 100) / 100f),
                    Sweep = cfg.SweepDeg * (float)Math.PI / 180f,
                    Scale = WingScaleMin + (WingScaleMax - WingScaleMin)
                        * (float)new Random(unchecked(agent.Index * 7919 + (Mission.Current?.GetHashCode() ?? 0))).NextDouble(),
                };
                _wings[agent] = wings;
                EquestriaBodyParts.SetPartVisible(visuals, cfg.RigidMesh, false);
                wings.RigidMesh = cfg.RigidMesh;
                EquestriaCrashLog.Log("крылья: #" + agent.Index + " два жёстких крыла созданы");
            }
            if (wings.Left == null)
            {
                return;
            }
            // Color - as on the stock (hidden) wing eq_pony_wings: EquestriaBodyParts paints it
            // by the pony's skin color (Mesh.Color/Color2). Repeat for the first frames - the painting may
            // arrive later than our first tick.
            if (wings.ColorTries < 30)
            {
                wings.ColorTries++;
                CopyWingColor(skeleton, wings, wings.RigidMesh);
            }
            wings.Phase += dt * 2f * (float)Math.PI / wings.Period;
            float angle = (FlapRestDeg + FlapAmplitudeDeg * (float)Math.Sin(wings.Phase)) * (float)Math.PI / 180f;
            MatrixFrame body = visuals.GetGlobalFrame();
            MatrixFrame bone = body.TransformToParent(skeleton.GetBoneEntitialFrameWithIndex(SpineBone));
            Place(wings.Left, bone, wings.LocalLeft, angle, wings.Scale, -wings.Sweep);
            Place(wings.Right, bone, wings.LocalRight, -angle, wings.Scale, wings.Sweep);
        }

        private static void CopyWingColor(Skeleton skeleton, Wings wings, string rigidMesh)
        {
            Mesh source = skeleton.GetAllMeshes().FirstOrDefault(m => m != null && m.Name != null
                && m.Name.StartsWith(rigidMesh ?? "eq_", StringComparison.OrdinalIgnoreCase));
            if (source == null)
            {
                return;
            }
            uint color = source.Color;
            uint color2 = source.Color2;
            foreach (GameEntity entity in new[] { wings.Left, wings.Right })
            {
                MetaMesh meta = entity != null && entity.GetComponentCount(GameEntity.ComponentType.MetaMesh) > 0 ? entity.GetMetaMesh(0) : null;
                if (meta == null)
                {
                    continue;
                }
                for (int i = 0; i < meta.MeshCount; i++)
                {
                    Mesh mesh = meta.GetMeshAtIndex(i);
                    if (mesh != null)
                    {
                        mesh.Color = color;
                        mesh.Color2 = color2;
                    }
                }
            }
        }

        // Flap - rotation around the root's longitudinal axis (f = forward): the left wing goes up at +angle,
        // the right one at -angle (mirrored).
        private static void Place(GameEntity entity, MatrixFrame bone, MatrixFrame local, float angle, float scale, float sweep)
        {
            MatrixFrame root = local;
            root.rotation.RotateAboutUp(sweep);        // tip forward (sign mirrored per side)
            root.rotation.RotateAboutForward(angle);
            MatrixFrame frame = bone.TransformToParent(root);
            frame.rotation.Orthonormalize();
            frame.rotation.ApplyScaleLocal(scale);
            entity.SetGlobalFrame(in frame);
        }

        public override void OnAgentRemoved(Agent affectedAgent, Agent affectorAgent, AgentState agentState, KillingBlow blow)
        {
            base.OnAgentRemoved(affectedAgent, affectorAgent, agentState, blow);
            Remove(affectedAgent);
        }

        private void Remove(Agent agent)
        {
            Wings wings;
            if (agent != null && _wings.TryGetValue(agent, out wings))
            {
                _wings.Remove(agent);
                wings.Left?.Remove(0);
                wings.Right?.Remove(0);
            }
        }

        public override void OnEndMissionInternal()
        {
            base.OnEndMissionInternal();
            foreach (Agent agent in new List<Agent>(_wings.Keys))
            {
                Remove(agent);
            }
        }
    }
}
