using System.Collections.Generic;
using TaleWorlds.CampaignSystem;
using TaleWorlds.Core;
using TaleWorlds.Engine;
using TaleWorlds.InputSystem;
using TaleWorlds.Library;
using TaleWorlds.Localization;
using TaleWorlds.MountAndBlade;

namespace EquestriaMod
{
    // Магия в бою: удержание Q открывает колесо, отпускание запускает выбранное заклинание.
    //
    // В The Old Realms на каждый снаряд вешается свой ScriptComponentBehavior; у нас все снаряды
    // ведёт одно поведение миссии — их единицы, а отлаживать и считать так проще
    // (разбор устройства TOR: docs/tor_reference/04_magic.md).
    public class EquestriaSpellMission : MissionBehavior
    {
        public const InputKey WheelKey = InputKey.Q;

        private const float SlowedTime = 0.3f;     // как в TOR: колесо замедляет бой
        private const int TimeRequestId = 0x4551;  // «EQ»: свой номер запроса скорости времени
        private const float MinArmingTime = 0.1f;  // до этого снаряд не взрывается — иначе о самого мага
        private const float HitHeight = 2.0f;      // насколько снаряд «высокий» при проверке попадания

        // Off — обычный бой; Wheel — открыто колесо; Aim — оружие убрано, висит прицел,
        // ждём ЛКМ; Cast — замах пошёл, снаряд вот-вот вылетит.
        public enum Mode { Off, Wheel, Aim, Cast }

        private class Flying
        {
            public EquestriaSpell Spell;
            public Agent Caster;
            public GameEntity Entity;
            public Vec3 Position;
            public Vec3 Direction;
            public float Life;
        }

        private readonly List<Flying> _flying = new List<Flying>();
        private readonly Dictionary<string, float> _readyAt = new Dictionary<string, float>();
        private readonly List<EquestriaSpell> _spells = new List<EquestriaSpell>();

        private int _selected;
        private Mode _mode = Mode.Off;
        private bool _slowed;
        private float _castLeft = -1f;
        private EquestriaSpell _casting;
        private float _messageUntil;
        private string _message = string.Empty;

        // Оружие, убранное на время колдовства: после каста возвращаем в руки то же самое
        private EquipmentIndex _mainHand = EquipmentIndex.None;
        private EquipmentIndex _offHand = EquipmentIndex.None;
        private bool _rewield;
        private float _suppressUntil;   // ещё чуть-чуть не даём бить: ЛКМ отпускают уже после каста

        // Мана вне кампании (пользовательский бой): считаем свою, герою её взять неоткуда.
        private float _localMana = EquestriaManaBehavior.MaxMana;

        public override MissionBehaviorType BehaviorType
        {
            get { return MissionBehaviorType.Other; }
        }

        // ---- что показывает колесо -------------------------------------------------------------

        public List<EquestriaSpell> Spells { get { return _spells; } }

        public Mode State { get { return _mode; } }

        public bool WheelOpen { get { return _mode == Mode.Wheel; } }

        public bool Aiming { get { return _mode == Mode.Aim || _mode == Mode.Cast; } }

        // Пока целимся и колдуем, игра не должна бить рукой по ЛКМ (см. EquestriaSpellCombatPatch)
        public bool SuppressCombat
        {
            get
            {
                return Aiming || (Mission.Current != null && Mission.Current.CurrentTime < _suppressUntil);
            }
        }

        public int Selected { get { return _selected; } }

        public EquestriaSpell Current
        {
            get { return _selected >= 0 && _selected < _spells.Count ? _spells[_selected] : null; }
        }

        public float Mana
        {
            get
            {
                return Campaign.Current != null ? EquestriaMana.Value : _localMana;
            }
        }

        public float ManaLimit
        {
            get
            {
                return Campaign.Current != null ? EquestriaMana.Limit : EquestriaManaBehavior.MaxMana;
            }
        }

        public string Message
        {
            get { return Mission.Current != null && Mission.Current.CurrentTime < _messageUntil ? _message : string.Empty; }
        }

        public void SetSelected(int index)
        {
            if (index >= 0 && index < _spells.Count)
            {
                _selected = index;
            }
        }

        public float CooldownLeft(EquestriaSpell spell)
        {
            float at;
            if (spell == null || Mission.Current == null || !_readyAt.TryGetValue(spell.Id, out at))
            {
                return 0f;
            }
            return MathF.Max(0f, at - Mission.Current.CurrentTime);
        }

        public bool IsReady(EquestriaSpell spell)
        {
            return spell != null && CooldownLeft(spell) <= 0f && Mana >= spell.Mana;
        }

        // ---- жизнь поведения -------------------------------------------------------------------

        public override void AfterStart()
        {
            base.AfterStart();
            _spells.Clear();
            if (Campaign.Current != null)
            {
                _spells.AddRange(EquestriaSpells.KnownBy(Hero.MainHero));
            }
            else
            {
                _spells.AddRange(EquestriaSpells.All);   // пользовательский бой: даём всё, что есть
            }
            EquestriaCrashLog.Log($"магия в бою: заклинаний у игрока {_spells.Count}");
        }

        public override void OnMissionTick(float dt)
        {
            base.OnMissionTick(dt);
            EquestriaCrashLog.Try("магия: такт боя", () =>
            {
                TickProjectiles(dt);
                TickCast(dt);
                HandleInput();
                UpdateWieldedItems();
            });
        }

        private bool CanUseMagic()
        {
            Mission mission = Mission.Current;
            return _spells.Count > 0 && mission != null && Agent.Main != null && Agent.Main.IsActive()
                && Agent.Main.Health > 0f
                && (mission.Mode == MissionMode.Battle || mission.Mode == MissionMode.Stealth)
                && !TaleWorlds.ScreenSystem.ScreenManager.GetMouseVisibility();
        }

        // Порядок как в The Old Realms: удержание Q — выбор, отпускание — переход в прицеливание
        // (оружие убирается, появляется прицел), выстрел — по ЛКМ, отмена — по ПКМ.
        private void HandleInput()
        {
            if (!CanUseMagic())
            {
                Cancel();
                return;
            }
            bool held = Input.IsKeyDown(WheelKey);
            switch (_mode)
            {
                case Mode.Off:
                    if (held)
                    {
                        SetMode(Mode.Wheel);
                    }
                    break;

                case Mode.Wheel:
                    if (!held)
                    {
                        StartAiming();
                    }
                    break;

                case Mode.Aim:
                    if (held)
                    {
                        SetMode(Mode.Wheel);      // передумал — снова колесо
                    }
                    else if (Input.IsKeyPressed(InputKey.RightMouseButton))
                    {
                        Cancel();
                    }
                    else if (Input.IsKeyPressed(InputKey.LeftMouseButton))
                    {
                        StartCast(Current);
                    }
                    break;
            }
        }

        private void StartAiming()
        {
            EquestriaSpell spell = Current;
            if (spell == null)
            {
                Cancel();
                return;
            }
            if (CooldownLeft(spell) > 0f)
            {
                Say("eq_spell_cooldown", "Spell is not ready yet");
                Cancel();
                return;
            }
            if (Mana < spell.Mana)
            {
                Say("eq_spell_no_mana", "Not enough mana");
                Cancel();
                return;
            }
            // Что было в руках, вернём после каста
            if (_mainHand == EquipmentIndex.None && _offHand == EquipmentIndex.None)
            {
                _mainHand = Agent.Main.GetPrimaryWieldedItemIndex();
                _offHand = Agent.Main.GetOffhandWieldedItemIndex();
            }
            SetMode(Mode.Aim);
        }

        private void Cancel()
        {
            if (_mode == Mode.Off)
            {
                return;
            }
            SetMode(Mode.Off);
            _casting = null;
            _castLeft = -1f;
        }

        private void SetMode(Mode mode)
        {
            if (_mode == mode)
            {
                return;
            }
            _mode = mode;
            // Колесо и прицеливание идут в замедленном времени — как в TOR
            SlowTime(mode == Mode.Wheel || mode == Mode.Aim);
            if (mode == Mode.Off)
            {
                _rewield = _mainHand != EquipmentIndex.None || _offHand != EquipmentIndex.None;
            }
        }

        // Убрать оружие на время колдовства и вернуть его после. За такт делаем один шаг:
        // игра проигрывает анимацию, и следующий вызов увидит уже новое состояние рук.
        private void UpdateWieldedItems()
        {
            Agent me = Agent.Main;
            if (me == null || !me.IsActive())
            {
                return;
            }
            if (Aiming)
            {
                if (me.GetPrimaryWieldedItemIndex() != EquipmentIndex.None)
                {
                    me.TryToSheathWeaponInHand(Agent.HandIndex.MainHand, Agent.WeaponWieldActionType.WithAnimation);
                }
                else if (me.GetOffhandWieldedItemIndex() != EquipmentIndex.None)
                {
                    me.TryToSheathWeaponInHand(Agent.HandIndex.OffHand, Agent.WeaponWieldActionType.WithAnimation);
                }
                return;
            }
            if (!_rewield || SuppressCombat)
            {
                return;
            }
            if (_mainHand != EquipmentIndex.None && me.GetPrimaryWieldedItemIndex() != _mainHand)
            {
                me.TryToWieldWeaponInSlot(_mainHand, Agent.WeaponWieldActionType.WithAnimation, false);
                return;
            }
            if (_offHand != EquipmentIndex.None && me.GetOffhandWieldedItemIndex() != _offHand)
            {
                me.TryToWieldWeaponInSlot(_offHand, Agent.WeaponWieldActionType.WithAnimation, false);
                return;
            }
            _rewield = false;
            _mainHand = EquipmentIndex.None;
            _offHand = EquipmentIndex.None;
        }

        // Пока колесо открыто, бой идёт медленнее — иначе выбирать заклинание некогда.
        private void SlowTime(bool enable)
        {
            if (Mission.Current == null || enable == _slowed)
            {
                return;
            }
            _slowed = enable;
            if (enable)
            {
                var request = new Mission.TimeSpeedRequest(SlowedTime, TimeRequestId);
                Mission.Current.AddTimeSpeedRequest(request);
            }
            else
            {
                Mission.Current.RemoveTimeSpeedRequest(TimeRequestId);
            }
        }

        private void Say(string key, string fallback)
        {
            _message = new TextObject("{=" + key + "}" + fallback).ToString();
            _messageUntil = Mission.Current.CurrentTime + 2f;
        }

        // ---- каст ------------------------------------------------------------------------------

        private void StartCast(EquestriaSpell spell)
        {
            if (spell == null || _casting != null)
            {
                return;
            }
            if (CooldownLeft(spell) > 0f)
            {
                Say("eq_spell_cooldown", "Spell is not ready yet");
                return;
            }
            if (Mana < spell.Mana)
            {
                Say("eq_spell_no_mana", "Not enough mana");
                return;
            }
            _casting = spell;
            _castLeft = spell.CastTime;
            SetMode(Mode.Cast);
            // Анимация замаха: та же, что у брошенного камня — своих анимаций колдовства у нас нет.
            ActionIndexCache action = ActionIndexCache.Create("act_release_heavy_thrown");
            Agent.Main.SetActionChannel(1, action, false, 0UL);
        }

        private void TickCast(float dt)
        {
            if (_casting == null)
            {
                return;
            }
            _castLeft -= dt;
            if (_castLeft > 0f)
            {
                return;
            }
            EquestriaSpell spell = _casting;
            _casting = null;
            // после каста ещё мгновение не бьём: ЛКМ игрок отпустит уже сейчас
            _suppressUntil = Mission.Current.CurrentTime + 0.4f;
            SetMode(Mode.Off);
            if (Agent.Main == null || !Agent.Main.IsActive())
            {
                return;
            }
            if (!TakeMana(spell.Mana))
            {
                Say("eq_spell_no_mana", "Not enough mana");
                return;
            }
            _readyAt[spell.Id] = Mission.Current.CurrentTime + spell.Cooldown;
            Launch(spell, Agent.Main);
        }

        private bool TakeMana(float amount)
        {
            if (Campaign.Current != null)
            {
                return EquestriaManaBehavior.TrySpend(Hero.MainHero, amount);
            }
            if (_localMana < amount)
            {
                return false;
            }
            _localMana -= amount;
            return true;
        }

        // ---- снаряд ----------------------------------------------------------------------------

        private void Launch(EquestriaSpell spell, Agent caster)
        {
            Vec3 direction = caster.LookDirection;
            direction.Normalize();
            Vec3 position = caster.GetEyeGlobalPosition() + direction * 0.7f;

            GameEntity entity = GameEntity.CreateEmpty(Mission.Current.Scene, false);
            MatrixFrame frame = new MatrixFrame(Mat3.CreateMat3WithForward(in direction), position);
            entity.SetGlobalFrame(in frame);
            AttachEffect(entity, spell.Trail);
            if (spell.HasLight)
            {
                Light light = Light.CreatePointLight(spell.LightRadius);
                light.Intensity = spell.LightIntensity;
                light.LightColor = spell.LightColor;
                light.Frame = MatrixFrame.Identity;
                light.SetVisibility(true);
                entity.AddLight(light);
            }
            _flying.Add(new Flying
            {
                Spell = spell,
                Caster = caster,
                Entity = entity,
                Position = position,
                Direction = direction,
                Life = 0f
            });
        }

        // Эффект в XML задаётся двумя способами: "psys_имя" — частица напрямую, "prefab:имя" —
        // сущность из Module/Prefabs (нужна там, где частицу надо донастроить: у хвоста снаряда
        // переопределены излучатели, иначе он не испускает пламя на ходу).
        private static void AttachEffect(GameEntity parent, string effect)
        {
            if (parent == null || string.IsNullOrEmpty(effect) || effect == "none")
            {
                return;
            }
            if (effect.StartsWith("prefab:"))
            {
                GameEntity child = GameEntity.Instantiate(
                    Mission.Current.Scene, effect.Substring("prefab:".Length), true);
                if (child == null)
                {
                    EquestriaCrashLog.Warn("магия: нет заготовки эффекта " + effect);
                    return;
                }
                parent.AddChild(child);
                return;
            }
            MatrixFrame local = MatrixFrame.Identity;
            ParticleSystem.CreateParticleSystemAttachedToEntity(effect, parent, ref local);
        }

        private void TickProjectiles(float dt)
        {
            for (int i = _flying.Count - 1; i >= 0; i--)
            {
                Flying shot = _flying[i];
                shot.Life += dt;
                Vec3 next = shot.Position + shot.Direction * (shot.Spell.Speed * dt);

                Vec3 hit;
                bool exploded = false;
                if (shot.Life > MinArmingTime && HitsSomething(shot, next, out hit))
                {
                    Explode(shot, hit);
                    exploded = true;
                }
                else if (shot.Life >= shot.Spell.Life)
                {
                    Explode(shot, next);   // выдохся на лету — всё равно рвётся, видно, докуда достал
                    exploded = true;
                }

                if (exploded)
                {
                    Remove(shot);
                    _flying.RemoveAt(i);
                    continue;
                }

                shot.Position = next;
                MatrixFrame frame = new MatrixFrame(Mat3.CreateMat3WithForward(in shot.Direction), next);
                shot.Entity.SetGlobalFrame(in frame);
            }
        }

        // Попадание ищем двумя способами: луч по сцене (земля, стены, ворота) и близость агента —
        // ровно как в TOR, где физика ловит препятствия, а агенты проверяются перебором рядом стоящих.
        private bool HitsSomething(Flying shot, Vec3 next, out Vec3 hit)
        {
            hit = next;
            float distance;
            using (new TWSharedMutexReadLock(Scene.PhysicsAndRayCastLock))
            {
                if (Mission.Current.Scene.RayCastForClosestEntityOrTerrain(
                        shot.Position, next, out distance, 0.05f,
                        BodyFlags.CommonCollisionExcludeFlagsForCombat))
                {
                    hit = shot.Position + shot.Direction * distance;
                    return true;
                }
            }
            var nearby = new MBList<Agent>();
            nearby = Mission.Current.GetNearbyAgents(next.AsVec2, shot.Spell.Radius * 0.5f + 1f, nearby);
            foreach (Agent agent in nearby)
            {
                if (agent == shot.Caster || !agent.IsActive() || agent.Health <= 0f)
                {
                    continue;
                }
                if (MathF.Abs(agent.Position.Z - next.Z) < HitHeight)
                {
                    hit = agent.GetChestGlobalPosition();
                    return true;
                }
            }
            return false;
        }

        private void Remove(Flying shot)
        {
            if (shot.Entity != null)
            {
                shot.Entity.FadeOut(0.05f, true);
                shot.Entity = null;
            }
        }

        private void Explode(Flying shot, Vec3 position)
        {
            EquestriaSpell spell = shot.Spell;
            if (!string.IsNullOrEmpty(spell.Burst) && spell.Burst != "none")
            {
                GameEntity burst = GameEntity.CreateEmpty(Mission.Current.Scene);
                MatrixFrame frame = new MatrixFrame(Mat3.Identity, position);
                burst.SetGlobalFrame(in frame);
                AttachEffect(burst, spell.Burst);
                burst.FadeOut(2.5f, true);
            }
            var nearby = new MBList<Agent>();
            nearby = Mission.Current.GetNearbyAgents(position.AsVec2, spell.Radius, nearby);
            foreach (Agent agent in nearby)
            {
                if (agent == null || !agent.IsActive() || agent.Health <= 0f || !agent.IsHuman)
                {
                    continue;
                }
                float distance = agent.GetChestGlobalPosition().Distance(position);
                if (distance > spell.Radius)
                {
                    continue;
                }
                // к краю взрыва урон падает вдвое — попадание в упор должно быть заметно лучше
                float damage = spell.Damage * (1f - 0.5f * distance / spell.Radius);
                Hit(agent, shot.Caster, (int)damage, position);
            }
        }

        // Урон наносим «ударом», а не вычитанием здоровья: так игра правильно засчитывает убийство,
        // роняет тело и даёт опыт. Сборка удара повторяет TOR (см. 04_magic.md, раздел 7).
        private static void Hit(Agent victim, Agent caster, int damage, Vec3 from)
        {
            if (damage <= 0 || caster == null)
            {
                return;
            }
            var blow = new Blow(caster.Index)
            {
                DamageType = DamageTypes.Blunt,
                BoneIndex = victim.Monster.HeadLookDirectionBoneIndex,
                GlobalPosition = victim.GetChestGlobalPosition(),
                BaseMagnitude = damage,
                InflictedDamage = damage,
                DamageCalculated = true,
                AttackType = AgentAttackType.Kick,
                BlowFlag = BlowFlags.NoSound,
                VictimBodyPart = BoneBodyPartType.Chest,
                StrikeType = StrikeType.Thrust
            };
            blow.WeaponRecord.FillAsMeleeBlow(null, null, -1, -1);
            blow.WeaponRecord.Weight = 5f;
            Vec3 direction = blow.GlobalPosition - from;
            if (direction.LengthSquared < 0.0001f)
            {
                direction = -victim.LookDirection;
            }
            direction.Normalize();
            blow.Direction = direction;
            blow.SwingDirection = direction;
            blow.WeaponRecord.Velocity = direction * blow.BaseMagnitude;

            AttackCollisionData collision = AttackCollisionData.GetAttackCollisionDataForDebugPurpose(
                false, false, false, true, false, false, false, false, false, false, false, false,
                // -999 вместо номера слота оружия: удар идёт не от предмета, а от заклинания
                CombatCollisionResult.StrikeAgent, -999, 1, 2, blow.BoneIndex, blow.VictimBodyPart,
                caster.Monster.MainHandItemBoneIndex, Agent.UsageDirection.AttackUp, -1,
                CombatHitResultFlags.NormalHit, 0.5f, 1f, 0f, 0f, 0f, 0f, 0f, 0f,
                Vec3.Up, blow.Direction, blow.GlobalPosition, Vec3.Zero, Vec3.Zero, victim.Velocity, Vec3.Up);
            victim.RegisterBlow(blow, in collision);
        }

        protected override void OnEndMission()
        {
            base.OnEndMission();
            _mode = Mode.Off;
            SlowTime(false);
            foreach (Flying shot in _flying)
            {
                Remove(shot);
            }
            _flying.Clear();
        }
    }

    // Пока герой целится заклинанием, оружие убрано, и ЛКМ должна пускать заклинание, а не бить
    // кулаком. Законного крючка нет: игра спрашивает у агента свойство CombatActionsEnabled
    // (MissionMainAgentController), его и перекрываем. Так же сделано в The Old Realms.
    //
    // Патч ставится поздно (EquestriaPatches.ApplyLate): ранний патч Agent запускает статическую
    // инициализацию класса до того, как игра прочитает анимации, и пони лежат набок в окнах.
    public static class EquestriaSpellCombatPatch
    {
        public static void Apply(HarmonyLib.Harmony harmony)
        {
            System.Reflection.MethodInfo getter =
                HarmonyLib.AccessTools.PropertyGetter(typeof(Agent), "CombatActionsEnabled");
            if (getter == null)
            {
                EquestriaCrashLog.Warn("магия: у Agent нет CombatActionsEnabled, удар по ЛКМ не отключён");
                return;
            }
            harmony.Patch(getter, postfix: new HarmonyLib.HarmonyMethod(
                typeof(EquestriaSpellCombatPatch).GetMethod(
                    "Postfix", System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.NonPublic)));
        }

        private static void Postfix(Agent __instance, ref bool __result)
        {
            if (!__result || !__instance.IsMainAgent || Mission.Current == null)
            {
                return;
            }
            EquestriaSpellMission magic = Mission.Current.GetMissionBehavior<EquestriaSpellMission>();
            if (magic != null && magic.SuppressCombat)
            {
                __result = false;
            }
        }
    }
}
