# Магия: как устроена в The Old Realms и как делаем у себя

Разбор системы способностей TOR (Bannerlord v1.3.15) и рабочие заметки по нашей магии.
Файл живой: сюда дописываем всё, что выясняем про заклинания — и чужие, и свои.

Исходники TOR никуда не копируются: ниже — описание устройства, имена типов и форматы XML.

## 0. Где смотреть (воспроизводимо)

Мод удалён из `Modules`, но остался в подписках Steam:

| Что | Путь |
|---|---|
| TOR_Core (код + XML + GUI) | `steamapps\workshop\content\261550\3025574678` |
| TOR_Armory (предметы, спрайты) | `...\3025575223` |
| TOR_Environment (карта) | `...\3025579210` |
| RU-перевод | `...\3708788710` |

Декомпиляция (одноразово):

```powershell
dotnet tool install -g ilspycmd --version 8.2.0.7535     # свежая 10.x ставится битой
$w = "D:\...\workshop\content\261550\3025574678\bin\Win64_Shipping_Client"
$b = "D:\...\Mount & Blade II Bannerlord\bin\Win64_Shipping_Client"
ilspycmd -o <куда> -p -r $b "$w\TOR_Core.dll"            # 820 файлов .cs
```
Так же смотрим ванильные сборки (`TaleWorlds.GauntletUI.dll`, `TaleWorlds.MountAndBlade.View.dll`,
`TaleWorlds.CampaignSystem.ViewModelCollection.dll`) — половина магии TOR опирается на ванильные виджеты.

## 1. Из чего собрана магия

Три XML с данными + движок на C#. Данные лежат в `CORE\ModuleData\tor_custom_xmls\` и грузятся
**самой DLL** (`XmlSerializer` по пути из `TORPaths`), а не через `SubModule.xml` — это не игровые
объекты, игра о них не знает.

| Файл | Что описывает | Шт. |
|---|---|---|
| `tor_abilitytemplates.xml` | заклинание целиком: цена, откат, снаряд, анимация, прицел | 135 |
| `tor_triggeredeffects.xml` | что происходит в точке попадания: урон, радиус, частицы, звук | ~200 |
| `tor_statuseffects.xml` | длящиеся эффекты (горение, регенерация, замедление) | 300 |
| `tor_extendedunitproperties.xml` | кто какие заклинания знает (по id NPCCharacter) | 1372 |

Правило TOR, которое стоит повторить: **шаблоны не попадают в сейв**, они перечитываются из XML при
каждом запуске. Баланс можно править, не ломая сохранения.

## 2. AbilityTemplate — поля

Пример (ванильный Fireball, сокращён):

```xml
<AbilityTemplate StringID="Fireball" Name="{=fireball_label_str}Fireball" SpriteName="fireball_icon"
    CoolDown="40" WindsOfMagicCost="16" BaseMisCastChance="0.05" Duration="3" Radius="0.5"
    AbilityType="Spell" AbilityEffectType="Missile" BaseMovementSpeed="35" TickInterval="-1"
    TriggerType="OnCollision" HasLight="true" LightIntensity="50" LightRadius="10"
    LightFlickeringMagnitude="3" LightFlickeringInterval="0.7" ShadowCastEnabled="true"
    ParticleEffectPrefab="fireball_prefab" SoundEffectToPlay="fireball" ShouldSoundLoopOverDuration="true"
    CastType="WindUp" CastTime="0.5" AnimationActionName="act_release_heavy_thrown" Offset="0.5"
    CrosshairType="Missile" AbilityTargetType="WorldPosition" SpellTier="3"
    MinDistance="3" MaxDistance="40" BelongsToLoreID="LoreOfFire"
    TooltipDescription="{=fireball_description_str}...">
  <LightColorRGB x="255" y="170" z="0" w="-1"/>
  <TriggeredEffect>fireball_explosion</TriggeredEffect>
</AbilityTemplate>
```

Смысл полей:

- `Duration` — **время жизни снаряда**, а не длительность эффекта. Через `Duration` секунд скрипт
  сам себя гасит (`Stop()` → `FadeOut`). У фаербола 3 с при скорости 35 → дальность ~100 м.
- `Radius` — радиус тела снаряда (сфера физики) и радиус проверки «рядом ли агент».
- `TickInterval` = −1 у снарядов: эффект один раз, при столкновении.
- `Offset` — сдвиг точки вылета вперёд (чтобы снаряд не рождался внутри самого мага).
- `BaseMisCastChance` — **не используется в коде**, остаток от старой версии.
- `SpellTier`, `BelongsToLoreID` — только для книги заклинаний и обучения.

Перечисления:

| Енум | Значения |
|---|---|
| `AbilityType` | Innate, Spell, Prayer, ItemBound, CareerAbility |
| `AbilityEffectType` | Projectile, Missile, SeekerMissile, Wind, Vortex, Heal, Augment, Hex, Summoning, Bombardment, Blast, ArtilleryPlacement, TimeWarpEffect, CareerAbilityEffect, TacticalReposition |
| `AbilityTargetType` | Self, SingleEnemy, SingleAlly, EnemiesInAOE, AlliesInAOE, WorldPosition, GroundAtPosition |
| `CastType` | Instant, WindUp, Channel |
| `TriggerType` | EveryTick, OnCollision, TickOnce, OnStop, None |
| `CrosshairType` | Missile, SingleTarget, Wind, Pointer, TargetedAOE, Self |

Каждому `AbilityEffectType` соответствует свой `ScriptComponentBehavior` (`MissileScript`,
`WindScript`, `BlastScript`, `SummoningScript`…) — `Ability.AddBehaviour` просто выбирает класс по енуму.

## 3. TriggeredEffect и StatusEffect

```xml
<TriggeredEffectTemplate StringID="fireball_explosion" BurstParticleEffectPrefab="psys_fireball_explosion_1"
    SoundEffectId="fireball_explosion" SoundEffectLength="2.5" DamageType="Fire" DamageAmount="60"
    Radius="4" HasShockWave="false" TargetType="All" ImbuedStatusEffectDuration="5"
    DamageVariance="0.05" ScriptNameToTrigger="none">
  <ImbuedStatusEffect>fireball_dot</ImbuedStatusEffect>
</TriggeredEffectTemplate>

<StatusEffectTemplate id="minor_healing_regeneration" particle_id="healing_regeneration"
    particle_intensity="High" base_effect_value="3" type="HealthOverTime"/>
```

- `DamageAmount` > 0 — урон, < 0 — лечение (тот же шаблон).
- `TargetType`: Friendly, Enemy, All, FriendlyHero, EnemyHero, Self. Цели ищутся вокруг точки взрыва
  (`Mission.GetNearbyEnemyAgents/AllyAgents/Agents`), если скрипт не передал явный список.
- `HasShockWave` — сбивает с ног (`BlowFlags.KnockDown`, магнитуда 1000) и урон падает с расстоянием.
- `ScriptNameToTrigger` — **полное имя C#-типа с `ITriggeredScript`**, создаётся рефлексией. Главная
  точка расширения: призыв, телепорт, зачарование оружия.
- `type` у статус-эффекта: HealthOverTime, WindsOverTime, DamageOverTime, DamageAmplification,
  Resistance, MovementManipulation, AttackSpeedManipulation, ReloadSpeedManipulation, LanceSteadiness,
  TemporaryAttributeOnly.

## 4. Жизненный цикл каста

```
Agent (атрибут AbilityUser) → AbilityComponent : AgentComponent
   └ список Ability (Spell / Prayer / ItemBound / CareerAbility), у каждого свой Crosshair

Ability.TryCast(caster)
   ├ CanCast → IsDisabled: откат, «мало маны» (переопределено в Spell), мёртв/бежит, угол каста с коня
   └ DoCast
       ├ SetAnimationAction  (SetActionChannel(1, AnimationActionName))
       ├ CastType.Instant → ActivateAbility сразу
       └ CastType.WindUp  → IsCasting = true, ждём CastTime; AbilityComponent.OnTick видит
                            IsActivationPending и зовёт ActivateAbility

Ability.ActivateAbility(caster)
   ├ откат: ExplainedNumber(CoolDown) с модификаторами карьеры
   ├ GetSpawnFrame — отдельно для игрока с прицелом, для быстрого каста и для ИИ
   ├ GameEntity.CreateEmpty(scene, createPhysics: true) + SetGlobalFrame
   ├ AddLight (если HasLight) → Light.CreatePointLight
   ├ AddPhysics (если TriggerType == OnCollision) → сфера радиуса Radius, BodyFlags.Moveable
   └ AddBehaviour → CreateAndAddScriptComponent("MissileScript") + дочерняя сущность с частицами

AbilityScript.OnTick (каждый кадр)
   ├ UpdateLifeTime: дожил до Duration → Stop()
   ├ TriggerType == OnCollision и CollidedWithAgent() → HandleCollision → TriggerEffects
   ├ ShouldMove() → frame.Advance(BaseMovementSpeed * dt), SetGlobalFrame, ManualInvalidate тела
   └ TriggerEffects → по каждому TriggeredEffectTemplate: new TriggeredEffect(...).Trigger(...)

TriggeredEffect.Trigger
   ├ собирает цели в радиусе, отсеивает мёртвых/исчезающих/дублей
   ├ DamageAgents / HealAgents (через TORAbilityModel, там навыки и перки)
   ├ навешивает статус-эффекты
   ├ частицы взрыва + звук
   └ ScriptNameToTrigger, затем Dispose
```

Мелочи, которые важны на практике:

- `CollidedWithAgent()` — не физика, а проверка «есть ли агент ближе `Radius + 1` по XY и по Z».
  Физическое столкновение (`OnPhysicsCollision`) ловится отдельно и даёт попадание в стены/землю.
- `_minArmingTimeForCollision = 0.1 с` — иначе снаряд взрывается о самого мага.
- Снаряд летит **прямо**: `MatrixFrame.Advance`. Наведение (`SeekerMissile`) — отдельный
  `SeekerController` с пропорционально-дифференциальным доворотом к цели.

## 5. Ветра магии (мана)

Хранение — не в `Hero`, а в своей структуре `HeroExtendedInfo` (`ExtendedInfoManager : CampaignBehaviorBase`,
всё через `SyncData`):

```csharp
Dictionary<string, float> CustomResources;    // "WindsOfMagic", "DarkEnergy", "Prestige"…
float MaxWindsOfMagic            => Campaign.Current.Models.GetAbilityModel().GetMaximumWindsOfMagic(ch);
float WindsOfMagicRechargeRate   => ... .GetWindsRechargeRate(ch);
```

- **Накопление — на глобальной карте, по часам**: `CampaignEvents.HourlyTickEvent` → у каждого живого
  героя с атрибутом `SpellCaster` `AddCustomResource("WindsOfMagic", rate * множитель)`. Множитель —
  перк «Катализатор» в городе (+X). В бою мана не растёт вовсе.
- Числа ванильного TOR: база максимума **10** (+ навык Spellcraft, + зачарованная экипировка,
  + карьерные пассивки), база регенерации **1/час**. У героев не в отряде игрока — фиксированные
  100 максимума и 2/час, чтобы ИИ-маги не считались подробно. У культуры `sturgia` (дварфы) магии
  нет вообще: и максимум, и регенерация 0.
- Трата — в `Spell.DoCast`: `AddCustomResource("WindsOfMagic", -cost)`; проверка «хватает ли» —
  в `Spell.IsDisabled`, то есть заклинание просто становится недоступным в колесе.
- Показ на карте: расширение ванильной `MapInfoVM` — в `SecondaryInfoItems` добавляются
  `MapInfoItemVM("winds", подсказка)`. Никакого своего окна: ванильная панель сама рисует иконку
  (`IconBrush="MapBar.Right.Icons"`, `IconID="@VisualId"`) и значение.

## 6. Ввод и колесо выбора

`TORGameKeyContext : GameKeyContext` (id 120), три клавиши:

| id | Имя | По умолчанию |
|---|---|---|
| 111 | QuickCastSelectionMenu | **Q** |
| 112 | QuickCast | средняя кнопка мыши |
| 113 | CareerAbilityCast | правый Shift |

Контекст подсовывается ванили Harmony-префиксом на `HotKeyManager.RegisterInitialContexts`.

Состояния (`AbilityModeState`): `Off → QuickMenuSelection → Targeting → Casting`.
`AbilityManagerMissionLogic.HandleInput` (в `OnPreMissionTick`):

- **Q нажата** → `EnableQuickSelectionMenuMode`: состояние `QuickMenuSelection`,
  `MissionScreen.RegisterRadialMenuObject(view)` (это отключает поворот камеры мышью),
  время замедляется до **0.3** (`Mission.TimeSpeedRequest`), клавиши смены оружия отвязываются.
- **Q отпущена** → если заклинанию нужна цель — `Targeting` (появляется прицел, маг убирает оружие,
  играет стойка `act_spellcasting_idle`), иначе каст сразу.
- **ЛКМ в режиме Targeting** → `TryCastCurrentAbility`; **ПКМ** → отмена.

Само колесо — ванильный виджет `CircleActionSelectorWidget` (TaleWorlds.GauntletUI):

- раскладывает дочерние виджеты по кругу: `360/N` градусов, радиус `DistanceFromCenterModifier`;
- копит **смещение мыши** (не позицию курсора!), нормирует к 125 px и по углу выбирает сектор;
- у выбранного ребёнка ставит `ButtonWidget.IsSelected = true`;
- `DirectionWidget` — точка-указатель, летающая от центра в сторону движения мыши.

TOR добавляет свой `AbilityRadialSelectionItemWidget : ButtonWidget`, который на изменение
`IsSelected` дёргает событие `OnSelected` → VM → `AbilityComponent.SelectAbility`. Префаб —
`GUI\Prefabs\AbilitySystem\AbilityRadialSelection.xml`, грузится как обычный `GauntletLayer`
из `MissionView` (`OnBehaviorInitialize` → `LoadMovie("AbilityRadialSelection", vm)`).

Прицелы (`AbilityCrosshair`): `Missile` — просто Gauntlet-точка в центре экрана; `TargetedAOE` —
круг на земле из меша; `SingleTarget` — захват агента под курсором.

## 7. Как наносится урон

TOR не трогает здоровье напрямую, а собирает «удар» (`Blow`), чтобы игра правильно записала убийство,
проиграла реакцию и дала опыт:

```csharp
Blow blow = new Blow(damager.Index);
blow.DamageType = DamageTypes.Blunt;              // тип урона магии считается отдельно
blow.BoneIndex  = agent.Monster.HeadLookDirectionBoneIndex;
blow.GlobalPosition = agent.GetChestGlobalPosition();
blow.BaseMagnitude = blow.InflictedDamage = damage;
blow.WeaponRecord.FillAsMeleeBlow(null, null, -1, -1);
blow.DamageCalculated = true;                      // игра не пересчитывает броню
blow.AttackType = AgentAttackType.Kick;            // «не оружие» — иначе ищется предмет
blow.BlowFlag = BlowFlags.NoSound;
blow.VictimBodyPart = BoneBodyPartType.Chest;
agent.RegisterBlow(blow, AttackCollisionData.GetAttackCollisionDataForDebugPurpose(...));
```

Стихия (`DamageType` Fire/Magical/Holy/Frost…) и сопротивления считаются в `TORAgentApplyDamageModel`
по данным `tor_extendedunitproperties.xml` (`Resistances`, `DamageProportions`).

## 8. ИИ колдовства

`WizardAIComponent : HumanAIComponent` + `DecisionManager` с «осями» полезности: дистанция до цели,
плотность строя, оставшаяся мана, здоровье своих. На каждый `AbilityEffectType` — своё
`AgentCastingBehavior`, плюс тактические (`KeepSafeAgentTacticalBehavior` — держаться позади).
Целью может быть агент или **строй** (для площадных заклинаний берётся центр формации).

## 9. Прочее из TOR, что пригодится

- Сейвы: `TORSaveableTypeDefiner` с базовым id 771000; в сейв идут только «сколько маны у кого»
  и списки выученного, не шаблоны.
- Логи: NLog по дням, `TORCommon.Log`; каждый каст пишет строку `spell cast start | spell=… | caster=…`.
- Консоль: `[CommandLineArgumentFunction]`, например `add_spells_to_player`.
- Частицы заклинаний — именованные `game_entity` в `CORE\Prefabs\spelleffects_prefab.xml`, внутри
  `particle_system_instanced_component` со ссылкой на GUID эффекта из их tpac.

---

# Наша магия (EquestriaMod)

## 10. Чем отличаемся от TOR и почему

| TOR | У нас | Почему |
|---|---|---|
| 135 шаблонов, 12 школ, карьеры, книга заклинаний | один XML со списком заклинаний, пока 1 | начинаем с рабочего скелета, растим по одному |
| `ScriptComponentBehavior` на каждый снаряд | один `MissionBehavior` ведёт список снарядов | не зависим от того, как движок ищет типы скриптов; проще отлаживать |
| свои частицы в tpac | ванильные `psys_*` из `particles.tpac` | своих частиц у нас нет, редактор для этого не нужен |
| свои спрайты иконок | текст на колесе + ванильная иконка на карте | не нужен свой спрайт-атлас |
| `HeroExtendedInfo` + своя модель | `Dictionary<героя → мана>` в `SyncData` | у нас нет карьер и перков, считать нечего |
| `GameKeyContext` с настройкой в меню | `InputKey.Q` напрямую | одна клавиша, настройку добавим, когда заклинаний станет много |

Общее с TOR намеренно: данные в XML и не в сейве; мана копится **по часам на глобальной карте**;
колесо на удержание Q через ванильный `CircleActionSelectorWidget`; урон через `Blow`;
**порядок каста**: выбор в колесе → прицеливание с убранным оружием → выстрел по ЛКМ.

Состояния у нас те же, что у TOR, только названы короче:

| Наше | У TOR | Что происходит |
|---|---|---|
| `Off` | `Off` | обычный бой |
| `Wheel` | `QuickMenuSelection` | держим Q: колесо, время 0.3, мышь крутит выбор, а не камеру |
| `Aim` | `Targeting` | отпустили Q: оружие убрано, висит прицел, мышь снова водит камерой |
| `Cast` | `Casting` | нажали ЛКМ: идёт замах `CastTime`, потом вылетает снаряд |

Отмена — ПКМ (возвращаемся в `Off` и достаём оружие), повторное удержание Q из прицеливания
открывает колесо заново.

Чтобы ЛКМ в прицеливании не била кулаком, перекрываем у главного агента свойство
`Agent.CombatActionsEnabled` — той же точкой пользуется TOR (`ShouldSuppressCombatActions`).
Патч ставится **поздно** (`EquestriaPatches.ApplyLate`): ранний патч `Agent` ломает анимации пони.
Прицел рисуем ванильными кистями `Crosshair.Top/Bottom/Left.Square/Right.Square` — тот же,
что у лука и дротиков; своего спрайта (у TOR это `test_spell_crosshair`) не нужно.

## 11. Что где лежит у нас

| Файл | Что делает |
|---|---|
| `Module/ModuleData/equestria_spells.xml` | список заклинаний (собирается `tools/make_spells.py`) |
| `tools/make_spells.py` | пишет XML + русские строки в `Languages/*/eq_spells_*.xml` |
| `src/EquestriaSpells.cs` | чтение XML, класс заклинания, кто что знает |
| `src/EquestriaMana.cs` | мана героев: накопление по часам, трата, сейв, показ на карте |
| `src/EquestriaSpellMission.cs` | бой: ввод (Q), полёт снарядов, взрыв, урон |
| `src/EquestriaSpellWheel.cs` | колесо: `MissionView` + ViewModel |
| `Module/GUI/Prefabs/EquestriaSpellWheel.xml` | разметка колеса |

## 12. Числа первой итерации

| Величина | Значение | Замечание |
|---|---|---|
| Максимум маны | 60 | герой-заклинатель |
| Накопление | 3 в час на карте | полный запас примерно за сутки пути |
| «Огненный шар» | 15 маны, откат 12 с | 4 каста с полного запаса |
| Урон | 60 в радиусе 4 м | падает к краю радиуса |
| Скорость снаряда | 35 м/с, жизнь 3 с | дальность ~100 м |
| Задержка каста | 0.5 с | время анимации броска |
| Замедление времени в колесе | 0.3 | как в TOR |

Ещё две мелочи, которые заметны в игре:

- Новый герой-заклинатель получает **полный запас маны** при первом запуске сессии, иначе первый бой
  он стоит без магии сутки игрового времени.
- **Q в бою у ванили свободна** (проверено по `MapHotKeyCategory`/`PhotoModeHotKeyCategory`: там Q —
  поворот карты и наклон камеры в фоторежиме, к бою отношения не имеет), поэтому читаем клавишу
  напрямую, без своего `GameKeyContext`.

## 13. Как проверить в игре

```powershell
.\run.ps1 -Battle          # собрать, загрузить последний сейв и сразу бой с разбойниками
```
В бою: **удерживать Q** — время замедляется, появляется колесо; **двигать мышь** — выбор пункта
(колесо смотрит на направление движения мыши, а не на курсор); **отпустить Q** — герой убирает
оружие и появляется прицел; **ЛКМ** — пустить заклинание туда, куда смотрим; **ПКМ** — отмена,
оружие возвращается в руки. Мана и выбранное заклинание видны внизу слева, на карте — в нижней
панели рядом со скоростью.

Замедление 0.3 держится и в прицеливании — так было в TOR. Если в бою это окажется неудобно
(целиться можно сколько угодно в «замедленном времени»), снять — одна строка в `SetMode`.

Консоль (Alt+~): `equestria.mana` — показать запас, `equestria.mana 60` — выставить.

## 14. Эффекты: что стоит сейчас и как это достали

Временно (до своих частиц) огненный шар выглядит как в TOR:

| Что | Откуда | Где лежит |
|---|---|---|
| хвост снаряда | **ванильная** частица `psys_game_burning_agent` `{BA0CCB36-…}` с настройкой излучателей из TOR | `Module/Prefabs/eq_spell_fx.xml`, сущность `eq_fireball_trail` |
| взрыв | частица TOR `psys_fireball_explosion_1` | `Module/Assets/spells/eq_spell_fx.tpac` (53 КБ) |

Важное, что выяснилось по дороге:

- «Фаербол TOR» на три четверти **ванильный**: в их `fireball_prefab` хвост — это ванильная
  `psys_game_burning_agent`, у которой переопределены три излучателя (разрешено испускание на ходу,
  размер частиц 3, два лишних излучателя заглушены). Поэтому хвост мы не копировали вовсе —
  только повторили настройку в своей заготовке.
- Своя у TOR только частица взрыва. Она тянет за собой **ванильный** материал `prt_shd_fire_1`,
  поэтому перенос обошёлся в один ассет на 53 КБ вместо 1.4 ГБ пакета.
- TOR_Armory выпущен **без** `RuntimeDataCache` — значит частицам запечённый кэш не нужен,
  перенесённый пакет работает сам по себе.

Как это делается (команды добавлены в `tools/tpac_export`):

```powershell
$tor = "D:\...\workshop\content\261550\3025575223\AssetPackages"   # TOR_Armory
tpac_export assets     $tor "particle:."                    # все частицы: имя + GUID
tpac_export assets     $tor "."                             # вообще все ассеты пакета
tpac_export copy-assets $tor psys_fireball_explosion_1 Module\Assets\spells\eq_spell_fx.tpac
```
`copy-assets` перекладывает ассет как есть (тело не разбирается) и дотягивает зависимости,
которые видны в метаданных. Чужой ассет при этом **не изменяется** — если зависимость окажется
не найдена, значит она ванильная и уже есть в игре.

Проверить, на что ссылается получившийся пакет, можно по готовому файлу: взять список
`assets` по ваниле и TOR и поискать 16-байтовые GUID в байтах `.tpac` (так и нашёлся `prt_shd_fire_1`).

**Это заглушка.** Свои частицы делаются в редакторе Modding Kit (Particle Editor), после чего
меняются два значения `trail` и `burst` в `tools/make_spells.py`, а `eq_spell_fx.tpac`
и чужой блок из `eq_spell_fx.xml` удаляются.

## 15. Как добавить заклинание

1. Дописать запись в `SPELLS` в `tools/make_spells.py` (название по-русски, цена, урон, частицы).
2. `py tools\make_spells.py Module` — перепишет XML и языковые файлы.
3. Если нужен новый вид эффекта (не «снаряд»), добавить ветку в `EquestriaSpellMission`.
4. Подобрать частицы: имена ванильных берутся из `Native\AssetPackages\particles.tpac`
   (в файле лежат строки `psys_*`; огонь — `psys_game_missile_flame`, `psys_burning_projectile_stone_coll`).
