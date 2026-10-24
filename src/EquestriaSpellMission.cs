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
    // Magic in battle: holding Q opens the wheel, releasing it casts the selected spell.
    //
    // In The Old Realms each projectile gets its own ScriptComponentBehavior; here all projectiles
    // are driven by one mission behaviour: there are only a few of them, and it is easier to debug and count this way
    // (breakdown of the TOR design: docs/tor_reference/04_magic.md).
    public class EquestriaSpellMission : MissionBehavior
    {
        public const InputKey WheelKey = InputKey.Q;

        private const float SlowedTime = 0.3f;     // as in TOR: the wheel slows down the battle
        private const int TimeRequestId = 0x4551;  // "EQ": our own time speed request number
        private const float MinArmingTime = 0.1f;  // before this the projectile does not explode, otherwise it would hit the mage himself
        private const float HitHeight = 2.0f;      // how "tall" the projectile is when checking for a hit

        // Off: regular battle; Wheel: the wheel is open; Aim: weapon put away, the crosshair is shown,
        // waiting for LMB; Cast: the swing has started, the projectile is about to fly.
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

        // The weapon put away for the duration of casting: after the cast the same one goes back into the hands
        private EquipmentIndex _mainHand = EquipmentIndex.None;
        private EquipmentIndex _offHand = EquipmentIndex.None;
        private bool _rewield;
        private float _suppressUntil;   // a little longer we do not let it strike: LMB is released after the cast

        // Mana outside the campaign (custom battle): we keep our own, the hero has nowhere to get it from.
        private float _localMana = EquestriaManaBehavior.MaxMana;

        public override MissionBehaviorType BehaviorType
        {
            get { return MissionBehaviorType.Other; }
        }

        // ---- what the wheel shows -------------------------------------------------------------

        public List<EquestriaSpell> Spells { get { return _spells; } }

        public Mode State { get { return _mode; } }

        public bool WheelOpen { get { return _mode == Mode.Wheel; } }

        public bool Aiming { get { return _mode == Mode.Aim || _mode == Mode.Cast; } }

        // While aiming and casting, the game must not strike with the hand on LMB (see EquestriaSpellCombatPatch)
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

        // ---- behaviour lifecycle -------------------------------------------------------------------

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
                _spells.AddRange(EquestriaSpells.All);   // custom battle: give everything there is
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

        // The order is as in The Old Realms: holding Q is the choice, releasing it switches to aiming
        // (the weapon is put away, the crosshair appears), the shot is on LMB, cancel is on RMB.
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
                        SetMode(Mode.Wheel);      // changed their mind: back to the wheel
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
            // What was in the hands is returned after the cast
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
            // The wheel and aiming run in slowed time, as in TOR
            SlowTime(mode == Mode.Wheel || mode == Mode.Aim);
            if (mode == Mode.Off)
            {
                _rewield = _mainHand != EquipmentIndex.None || _offHand != EquipmentIndex.None;
            }
        }

        // Put the weapon away for the duration of casting and return it afterwards. We do one step per tick:
        // the game plays the animation, and the next call already sees the new state of the hands.
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

        // While the wheel is open, the battle runs slower; otherwise there is no time to choose a spell.
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

        // ---- cast ------------------------------------------------------------------------------

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
            // The swing animation: the same as for a thrown stone; we have no casting animations of our own.
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
            // after the cast we do not strike for a moment longer: the player releases LMB right now
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

        // ---- projectile ----------------------------------------------------------------------------

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

        // The effect is set in XML in two ways: "psys_name" is a particle directly, "prefab:name" is
        // an entity from Module/Prefabs (needed where the particle has to be tuned further: the projectile tail
        // has overridden emitters, otherwise it does not emit flame in flight).
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
                    Explode(shot, next);   // ran out in flight: it still bursts, so you can see how far it reached
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

        // The hit is searched for in two ways: a ray through the scene (ground, walls, gates) and agent proximity,
        // exactly as in TOR, where physics catches obstacles and agents are checked by iterating over those standing nearby.
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
                // towards the edge of the explosion the damage halves: a point-blank hit must be noticeably better
                float damage = spell.Damage * (1f - 0.5f * distance / spell.Radius);
                Hit(agent, shot.Caster, (int)damage, position);
            }
        }

        // Damage is dealt as a "blow", not by subtracting health: this way the game correctly credits the kill,
        // drops the body and gives experience. The blow assembly follows TOR (see 04_magic.md, section 7).
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
                // -999 instead of a weapon slot number: the blow comes not from an item but from a spell
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

    // While the hero is aiming a spell, the weapon is put away, and LMB must cast the spell, not punch
    // with the fist. There is no legitimate hook: the game asks the agent for the CombatActionsEnabled property
    // (MissionMainAgentController), and that is what we override. The Old Realms does the same.
    //
    // The patch is applied late (EquestriaPatches.ApplyLate): an early Agent patch triggers the static
    // initialization of the class before the game reads the animations, and ponies lie on their side in windows.
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
