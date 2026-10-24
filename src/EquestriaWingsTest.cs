using System;
using System.Collections.Generic;
using System.Linq;
using TaleWorlds.Core;
using TaleWorlds.Engine;
using TaleWorlds.Library;
using TaleWorlds.MountAndBlade;

namespace EquestriaMod
{
    // Машущие крылья летунов (10.10.2026). В human_skeleton нет костей для крыльев, крылья пони — жёсткий
    // меш на spine2 (tools/creature_data.py). Решение: два ЖЁСТКИХ меша (левое/правое крыло,
    // tools/make_wing_meshes.py, начало координат — корень крыла у позвоночника) как отдельные
    // сущности, каждый кадр перед отрисовкой ставятся на кость spine2 агента со смещением корня, и
    // код сам поворачивает их вокруг корня по синусу — взмах. Штатные крылья eq_pony_wings прячутся.
    //
    // Отвергнутый путь (10.10.2026): проп на ванильном bird_skeleton со скинованным мешем крыльев и
    // клипом anim_bird_cycle (tools/make_wings_rig.py). Механизм работает (ястреб на спине машет),
    // но привязку меша к костям птицы в игре не измерить, и после шести реимпортов крыло всё равно
    // вращалось не вокруг корня. Скрипт и прафаб eq_pony_wings_rig оставлены на будущее.
    public class EquestriaWingsTest : MissionBehavior
    {
        private const bool Enabled = true;
        private const sbyte SpineBone = 11; // spine2 в human_skeleton (tools/engine_rest_human_skeleton.txt)

        // Крылатые расы: прафабы жёстких крыльев, штатный меш (прячем) и корни крыльев в координатах
        // модели (Blender, печать tools/make_wing_meshes.py -- <раса>). Модель в Blender смотрит в -Y,
        // агент в движке — в +Y: пространство агента = поворот Blender на 180° вокруг Z.
        private sealed class RaceWings
        {
            public string PrefabLeft, PrefabRight, RigidMesh;
            public Vec3 RootLeft, RootRight;
            public float SweepDeg;   // разворот кончиков крыльев вперёд вокруг вертикали (просьба 10.10.2026)
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
        // Взмах: угол вокруг продольной оси (вперёд) через корень; знак зеркальный у сторон.
        private const float FlapAmplitudeDeg = 45f;
        private const float FlapPeriod = 1.6f;              // секунд на один взмах
        private const float FlapRestDeg = 10f;              // крылья чуть приподняты в среднем положении
        // Разворот меша вокруг вертикали относительно агента: 180 — как у скинованных мешей пони
        // (Blender -Y → агент +Y). Если крылья окажутся кромкой назад — поставить 0.
        private const float MeshYawDeg = 180f;
        private const float WingScaleMin = 0.85f;           // размер крыльев летуна, детерминирован по агенту
        private const float WingScaleMax = 1.0f;

        public override MissionBehaviorType BehaviorType => MissionBehaviorType.Other;

        private sealed class Wings
        {
            public GameEntity Left;
            public GameEntity Right;
            public MatrixFrame LocalLeft;    // корень левого крыла относительно кости spine2
            public MatrixFrame LocalRight;
            public float Phase;
            public float Period;     // свой период у каждого — чтобы строй не махал синхронно
            public float Scale;      // размер крыльев: 0.85..1.0 (просьба пользователя 10.10.2026)
            public float Sweep;      // радианы, разворот вперёд вокруг вертикали
            public int ColorTries;   // цвет копируем со штатного крыла несколько кадров подряд
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
                    // Вразнобой: фаза по номеру агента (золотой угол — равномерно по кругу) и
                    // период ±15% — иначе все созданные в один тик махали синхронно.
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
            // Цвет — как у штатного (спрятанного) крыла eq_pony_wings: его красит EquestriaBodyParts
            // по цвету кожи пони (Mesh.Color/Color2). Повторяем первые кадры — покраска может
            // прийти позже нашего первого тика.
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

        // Взмах — поворот вокруг продольной оси корня (f = вперёд): левое крыло вверх при +angle,
        // правое — при -angle (зеркально).
        private static void Place(GameEntity entity, MatrixFrame bone, MatrixFrame local, float angle, float scale, float sweep)
        {
            MatrixFrame root = local;
            root.rotation.RotateAboutUp(sweep);        // кончик вперёд (знак зеркальный у сторон)
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
