using System;
using System.Collections.Generic;
using System.Linq;
using TaleWorlds.Core;
using TaleWorlds.Engine;
using TaleWorlds.Library;
using TaleWorlds.MountAndBlade;

namespace EquestriaMod
{
    // Зоны костей — перенос DismembermentPlus.DataHelpers.HumanBoneHelper.cs без изменений
    // (те же индексы HumanBone).
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

    // Отрубание конечностей — перенос механики мода DismembermentPlus (nexusmods.com/
    // mountandblade2bannerlord/mods/2190, декомпилировано 07.10.2026) на наши расы. Хук
    // OnRegisterBlow и зоны костей (HumanBone) переносятся без изменений — индексы те же, что мы
    // используем в именах костей наших рас (bip01_l_thigh_1, bip01_l_clavicle_14 — цифра в конце и
    // есть индекс HumanBone), раса на человеческом скелете, зона удара не меняется в принципе.
    //
    // 07.10.2026: расширено с пони на все расы. Голова у каждой расы — отдельный объект
    // (eq_<раса>_head), новых ассетов не требовала ни для кого (сверено с tools/export_*.py —
    // голова отдельным мешем экспортирована у всех семи рас). Руки/ноги — другая история: у пони
    // eq_pony_gloves/eq_pony_legs разрезаны на _l/_r (tools/pony_edit_split_limbs.py), у остальных
    // рас эта половина всё ещё одним куском — пока не разрежем так же (Blender, по расе отдельно),
    // отрубание руки/ноги для них просто не срабатывает (RaceInfo.LimbsSplit=false, см. ниже).
    public class EquestriaDismemberment : MissionBehavior
    {
        public override MissionBehaviorType BehaviorType => MissionBehaviorType.Other;

        // Краш (0xc0000005) был не из-за самого ActivateRagdoll(), а из-за наших же добавленных
        // SetLinearVelocity/SetAngularVelocity/SetVelocityLimits сверху — в оригинальном
        // DismembermentPlus (декомпилирован, DismembermentPlusMissionLogic.GetDismemberedEntity)
        // таких вызовов нет вообще, и крашей там нет. Сверка с их кодом нашла реальное отличие:
        // перед включением физики они явно выставляют entity.BodyFlag = BodyFlags.None и особый
        // entity.EntityFlags (у нас оба стояли на дефолте после CreateEmptyDynamic). Повторяем их
        // конфигурацию в SpawnFlyingPart — настоящий рэгдолл, без собственной подмены физики.
        private static readonly EntityFlags DismemberedPartFlags =
            EntityFlags.Ignore | EntityFlags.NonModifiableFromEditor | EntityFlags.NotAffectedBySeason
            | EntityFlags.DontCheckHandness | EntityFlags.RecordToSceneReplay | EntityFlags.DontSaveToScene;

        // Включение физики откладываем на ActivateDelay секунд после создания сущности — см.
        // комментарий в SpawnFlyingPart. Пока сущность ждёт, она просто висит в правильной позе
        // без физики (не ничем не хуже застывшего кадра смерти).
        private const float ActivateDelay = 0.35f;
        private static readonly List<(GameEntity Entity, float TimeLeft)> _pendingRagdoll =
            new List<(GameEntity, float)>();

        // Отрубленная часть раньше жила вечно — ни разу не вызывали entity.Remove(), сущность со
        // своим скелетом и скопированными текстурами просто копилась в сцене. В бою 100 на 100 со
        // 100%-м шансом это десятки лишних полноразмерных сущностей за один бой — похоже, отсюда и
        // "Недостаточно ресурсов памяти для завершения операции" у видеокарты (замечено
        // пользователем 07.10.2026 после серии тестовых боёв). Убираем часть через FlyingLifetime
        // секунд после того, как она улеглась — глазом уже не видно, а раньше её и не было видно.
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

        // 07.10.2026: 100% в пределах тех же условий (добивающий рубящий свайп в нужную зону) —
        // чтобы эффект было хорошо видно в тестовом бою, не теряясь в случайности.
        private const float HeadChance = 1.0f;
        private const float ArmChance = 1.0f;
        private const float LegChance = 1.0f;

        /// <summary>Что лететь с головой/рукой/ногой у конкретной расы — сверено с
        /// EquestriaBodyParts.PartByRace/EarMeshByRace/HairReferenceByRace (та же разбивка на
        /// рог/уши/грива по расам), null — у расы такой части просто нет.</summary>
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
                    // GetRaceOrDefault отдаёт 0 (человек) для неизвестной расы — такую не путаем
                    // с людьми, им отрубание не нужно.
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
            // Руки/ноги разрезаны на _l/_r только у пони (tools/pony_edit_split_limbs.py) — у
            // остальных рас такого ассета пока нет, без него половину просто некому лететь.
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
            // Рог, уши и грива — отдельные меши, пристёгнутые к кости (как хвост/крылья), а не
            // часть меша головы (EquestriaBodyParts.cs PartByRace) — без этого оставались висеть на
            // обезглавленном теле (замечено пользователем 07.10.2026, грива — 07.10.2026 отдельно).
            // Прячем и уносим вместе с головой — всё анатомически её часть. Не у каждой расы есть
            // все три (griffon — только уши, hippogriff — вообще ничего), пропускаем то, чего нет.
            var extras = new List<string>();
            if (info.HornMesh != null) { extras.AddRange(HideWithVariants(skeleton, info.HornMesh)); }
            if (info.EarsMesh != null) { HideWholePart(skeleton, info.EarsMesh); extras.Add(info.EarsMesh); }
            if (info.HairMesh != null) { extras.AddRange(HideWithVariants(skeleton, info.HairMesh)); }
            SpawnFlyingPart(victim, headBone, info.HeadMesh, extraMeshNames: extras.ToArray());
            victim.CreateBloodBurstAtLimb((sbyte)headBone, 0.5f + MBRandom.RandomFloat * 0.5f);
        }

        /// <summary>Рука/нога: гасим целую исходную деталь (eq_pony_gloves/eq_pony_legs, обе
        /// стороны разом — уцелевшую половину отдельно на живом скелете НЕ показываем, см. ниже
        /// почему), отрубленную половину уносит отдельная сущность с рэгдоллом.</summary>
        private static void DismemberLimb(Agent victim, HumanBone bone, string wholeMeshName, bool severedIsLeft)
        {
            Skeleton skeleton = victim.AgentVisuals?.GetSkeleton();
            if (skeleton == null)
            {
                return;
            }
            // Раньше тут же добавляли "уцелевшую" половину (skeleton.AddComponent) прямо на живой,
            // активно анимируемый скелет жертвы — после первого же боя с этим кодом движок крашился
            // (0xc0000005 в TaleWorlds.Native.dll, тот же почерк, что и с каналом анимации крыльев).
            // Отрубание головы, которое только прячет меш и ничего не добавляет на живой скелет,
            // крашей не давало — значит дело именно в AddComponent на живом. Поэтому жертва теряет
            // обе стороны детали целиком; отрубленная половина всё равно летит отдельной сущностью
            // (это уже безопасный путь, как у головы).
            HideWholePart(skeleton, wholeMeshName);
            string flyName = wholeMeshName + (severedIsLeft ? "_l" : "_r");
            // Цвет берём с ЦЕЛОГО имени (eq_pony_gloves), а не с разрезанного (eq_pony_gloves_l) —
            // на живом скелете меш так и остаётся одним целым куском под целым именем (разрезан
            // только набор СТАТИЧЕСКИХ ассетов для отрубленной половины, не сама экипировка на
            // жертве), поэтому поиск по flyName ничего не находил и отрубленная рука/нога
            // оставалась дефолтного (белого) цвета — голова красилась верно, т.к. у неё имя без
            // суффикса совпадает буквально (замечено пользователем 08.10.2026).
            SpawnFlyingPart(victim, bone, flyName, wholeMeshName);
            victim.CreateBloodBurstAtLimb((sbyte)bone, 0.5f + MBRandom.RandomFloat * 0.5f);
        }

        /// <summary>Прячет меш(и), чьё имя ТОЧНО равно partName (без учёта суффикса копии вида
        /// ".001") — важно не задеть eq_pony_gloves_l/_r префиксным совпадением с eq_pony_gloves.
        /// internal — тем же приёмом прячет ноги EquestriaFlightScroll (свиток полёта).</summary>
        /// <summary>Прячет часть и её варианты <c>имя_2..имя_9</c> (рога и косы оленихи, 10.10.2026:
        /// видны только выбранные, см. EquestriaBodyParts.DeerAntlerVariant) и возвращает имена тех,
        /// что были видны, — их и уносит отрубленная голова. Если не было видно ни одного (под
        /// шлемом коса не строится) — пустой список; у частей без вариантов — само имя, как раньше.</summary>
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

        /// <summary>Переносит цвет (Mesh.Color/Color2 — например, тон гривы, который красится не
        /// в материале, а в самом экземпляре меша) с живого скелета на свежую копию. Без этого
        /// копия MetaMesh.GetCopy выходит дефолтного цвета — грива у отрубленной головы бледнеет
        /// (замечено пользователем 07.10.2026).</summary>
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

        /// <summary>Отдельная сущность с рэгдоллом для отрубленной части — meshName и любые
        /// extraMeshNames (например, рог вместе с головой) ставятся на один и тот же клон скелета,
        /// чтобы улетали вместе. colorSourceName — чьё имя искать на ЖИВОМ скелете жертвы при
        /// переносе цвета (CopyMeshColorIfAny), если оно отличается от meshName — у руки/ноги
        /// meshName это разрезанный ассет (eq_pony_gloves_l), а на живом скелете деталь остаётся
        /// целой под именем без суффикса (eq_pony_gloves); по умолчанию (null) берётся meshName —
        /// верно для головы, где имя совпадает буквально.</summary>
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
            // Скорость небольшая (0.3), не 1 и не 0. Со speed=1 все отрубленные части системно
            // летели в одну сторону — в сторону, куда боец был развёрнут в момент удара (в линейном
            // бою почти все бойцы с одной стороны смотрят на противника одинаково, поэтому снос
            // получался не случайным, а "в сторону другой площадки", замечено пользователем
            // 07.10.2026) — а полная заморозка (0) не давала вообще никакого видимого толчка
            // (по просьбе пользователя добавить немного импульса). За ActivateDelay секунд до
            // включения физики успевает чуть доиграть, рэгдолл подхватывает это небольшое движение.
            // Не трогаем entity.ApplyLocalImpulseToDynamicBody/SetLinearVelocity и т.п. намеренно —
            // вся эта группа функций (пишет/толкает "тело" сущности после ActivateRagdoll()) уже
            // дважды крашила движок на других вызовах (см. DismemberedPartFlags), рисковать третьим
            // не стали.
            MBSkeletonExtensions.SetAnimationAtChannel(entity.Skeleton,
                victim.AgentVisuals.GetSkeleton().GetAnimationAtChannel(0), 0, 0.3f, -1f, 0f);
            // Ставим корень новой сущности прямо в глобальный кадр жертвы (её собственное
            // положение/поворот), а НЕ в вычисленную мировую позицию кости. Раньше ставили именно
            // в позицию кости — а скелет новой сущности, получив ту же анимацию/позу, САМ заново
            // проходит всю цепочку кость-от-корня и прибавляет то же смещение ЕЩЁ РАЗ (корень уже
            // был в точке кости, а потом к ней добавился путь корень→кость снова) — отрубленная
            // часть оказывалась сдвинута на расстояние "корень-кость" сверх нужного. Для головы
            // (верх всей цепочки позвоночника) это смещение самое большое — отсюда и "сильно
            // смещается вверх" (замечено пользователем 07.10.2026). Если просто повторить
            // собственный кадр жертвы, скелет сам точно воспроизводит позу — без лишнего сложения.
            MatrixFrame globalFrame = victim.AgentVisuals.GetGlobalFrame();
            entity.SetGlobalFrame(ref globalFrame, true);
            Skeleton victimSkeleton = victim.AgentVisuals.GetSkeleton();
            entity.Skeleton.AddComponent(mesh);
            CopyMeshColorIfAny(victimSkeleton, colorSourceName ?? meshName, mesh);
            // Кровь прямо на срезе отрубленной части, в момент её создания (по просьбе
            // пользователя 08.10.2026) — тот же эффект, что и на культе жертвы (psys_game_blood_
            // sword_exit, уже усилен в 4 раза, см. equestria_more_blood.xml), но
            // CreateBloodBurstAtLimb зовётся только у Agent, а у отрубленной части его нет, своя
            // голая GameEntity со своим скелетом — поэтому цепляем частицу напрямую на кость её
            // собственного скелета (ParticleSystem.CreateParticleSystemAttachedToBone), а не через
            // Agent API. Индекс кости тот же HumanBone — оба скелета собраны из одной модели
            // "human_skeleton", нумерация совпадает (как и везде в этом файле, см. (sbyte)bone
            // выше).
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
            // SetMaxDepenetrationVelocity крашило так же, как SetLinearVelocity/SetVelocityLimits
            // раньше (0xc0000005, 07.10.2026) — подтверждает первоначальную догадку: ЛЮБАЯ функция
            // из GameEntityPhysicsExtensions, трогающая "тело" сущности после ActivateRagdoll(), не
            // годится для рэгдолла (там нет одного тела — только по костям). BodyFlag/EntityFlags
            // были настоящей причиной ОТДЕЛЬНОГО более раннего краша, но это не делает остальные
            // функции этой группы безопасными — больше их не трогаем.
            //
            // Позиция (см. лог выше) верна и сразу после ActivateRagdoll не меняется — разлёт
            // происходит позже, внутри самой симуляции. Похоже на "взрыв рэгдолла" от начального
            // перекрытия: новая часть появляется прямо там же, где труп бойца, который в этот
            // момент часто сам ещё рэгдоллится — капсулы костей накладываются друг на друга.
            // Без доступа к подрезке скорости откладываем включение физики на ActivateDelay секунд:
            // труп успевает разлететься/улечься, перекрытие в момент активации меньше.
            _pendingRagdoll.Add((entity, ActivateDelay));
        }
    }
}
