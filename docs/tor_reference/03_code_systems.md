# The Old Realms — код и игровые системы

Справочник по файлам The Old Realms (Bannerlord v1.3.15), 2026-09-15. Имена типов — из reflection-only загрузки TOR_Core.dll и строк; ничего не декомпилировалось и не копировалось.
Пути: **CORE** = TOR_Core (3025574678), **ARM** = TOR_Armory (3025575223), **ENV** = TOR_Environment (3025579210), **RU** = TOR_RU_Translation (3708788710).

## 1. Архитектура кода

- Код только в **TOR_Core**: `TOR_Core.dll`, класс `TOR_Core.SubModule : MBSubModuleBase`. Armory и Environment — `<SubModules/>` (только данные).
- Harmony: DLL ссылается на `0Harmony 2.4.2.0`, берёт его из модуля Bannerlord.Harmony (сама зависимость в XML закомментирована). id `"mod.harmony.theoldrealms"`.
- **.NET Framework 4.8**. Без ButterLib/UIExtenderEx/MCM — свои аналоги.
- bin: TOR_Core.dll (2.6 МБ) + pdb, NLog, ink-engine-runtime, ink_compiler, NAudio*, NVorbis; `ResolveDllPath` (AssemblyResolve для своих DLL).
- SubModule: `OnSubModuleLoad`, `ConfigureLogging`, `InitializeGameStarter`, `OnGameStart`, `OnGameInitializationFinished`,
  `OnBeforeInitialModuleScreenSetAsRoot`, `OnBeforeMissionBehaviorInitialize`, `OnMissionBehaviorInitialize`, `OnApplicationTick`.

Пространства имён (1482 типа), ключевое:
- `AbilitySystem`: `Ability`, `AbilityComponent : AgentComponent`, `AbilityFactory`, `AbilityManagerMissionLogic`, `AbilityHUDMissionView`, `AbilityTemplate`,
  `CareerAbility`, `ItemBoundAbility`, `Prayer`, `SummonedCombatant`; `.Scripts` — 48 `ScriptComponentBehavior` (MissileScript, WindScript, HealScript, AugmentScript,
  HexScript, SummoningScript, BlastScript, TeleportScript, ShadowStepScript…); `.CrossHairs`; `.SpellBook` (`SpellBookScreen`, `SpellBookState`, `SpellBookVM`).
- `BattleMechanics.AI.CastingAI`: `WizardAIComponent : HumanAIComponent`, `AgentCastingBehaviorConfiguration`, casting behaviors по типам эффекта,
  тактические (`KeepSafeAgentTacticalBehavior`), utility-AI (`Axis`, `DecisionManager`, `ScoringFunctions`).
- `BattleMechanics.StatusEffect`, `.TriggeredEffect` (+ ~50 скриптов: SummonScript, PrefabSpawnerScript, KnockDownScript, EnchantWeaponScript),
  `.DamageSystem`, `.Firearms`, `.Artillery`, `.Dismemberment`, `.Morale`, `.Voice`, `.CustomArenaModes`, `.SFX` (`PlayerFlyableObjectScript`).
- `CampaignMechanics`: Religion (`ReligionObject : MBObjectBase`), TORCustomSettlement, CustomResources, CustomEvents, CharacterCreation, Companions,
  Crafting (зачарование), Diplomacy, RaiseDead, RegimentsOfRenown, SpellTrainers, ServeAsAHireling, RaidingParties, Assimilation.
- `CharacterDevelopment`: `TORSkills` (Faith, GunPowder, Spellcraft), `TORAttributes` (Discipline), `TORPerks`, `TORCareers` + 23 `*CareerChoices`, `CareerScreen`.
- `Extensions.ExtendedInfoSystem`: `CharacterExtendedInfo`, `HeroExtendedInfo`, `MobilePartyExtendedInfo`, `ExtendedInfoManager : CampaignBehaviorBase`.
  `Extensions.UI`: `ViewModelExtensionManager`, `[ViewModelExtension]` (свой заменитель UIExtenderEx).
- `GameManagers`: `TorCampaignGameManager : SandBoxGameManager`, `TORGameKeyContext`, `TorKeyMap`.
- `HarmonyPatches` (85 типов): Agent, Mission, Model, CharacterCreation, CustomWorldMap, Settlement, ObjectManager, RaceFix, ViewModel, GameText, Encyclopedia, FaceGen…
- `Ink`, `Items` (ItemTrait, WeaponHitScripts, InventoryUseScripts), `Models` (~60 `GameModel`: TORAbilityModel, TORAgentApplyDamageModel,
  TORAgentStatCalculateModel, TORPartySpeedCalculatingModel, TORMapVisibilityModel, TORFaithModel…), `Missions`, `Quests` (`QuestBase`),
  `SaveGameSystem` (`TORSaveableTypeDefiner`), `Utilities` (TORConfig, TORPaths, TORCommon.Log/Say, TORConsoleCommands, TORCampaignEvents).

## 2. Магия / способности

Данные в `CORE\ModuleData\tor_custom_xmls\` (грузит DLL, не SubModule): `tor_abilitytemplates.xml` (135), `tor_triggeredeffects.xml`,
`tor_statuseffects.xml` (300), `tor_extendedunitproperties.xml` (1372), `tor_animation_triggers.xml`, `tor_itemtraits.xml`, `tor_extendeditemproperties.xml`.

```xml
<AbilityTemplate StringID="Dart" Name="{=dart_label_str}Magic Bolt" SpriteName="dart_icon"
   CoolDown="10" WindsOfMagicCost="4" BaseMisCastChance="0.05" Duration="300" Radius="0.4"
   AbilityType="Spell" AbilityEffectType="SeekerMissile" BaseMovementSpeed="30" TickInterval="-1"
   TriggerType="OnCollision" HasLight="true" LightIntensity="50" LightRadius="10"
   ParticleEffectPrefab="dart_particle" SoundEffectToPlay="dart" CastType="WindUp" CastTime="0.5"
   AnimationActionName="act_release_stone" SpellTier="1" BelongsToLoreID="MinorMagic"
   MaxDistance="100" CrosshairType="SingleTarget" AbilityTargetType="EnemiesInAOE"
   TooltipDescription="{=dart_label_description_str}...">
  <LightColorRGB x="0" y="204" z="255" w="-1"/>
  <TriggeredEffect>dart_explosion</TriggeredEffect>
  <SeekerParameters Proportional="0.5" Derivative="0" DisableDistance="10" />
</AbilityTemplate>
```
- Енумы: `AbilityType` Innate/Spell/Prayer/ItemBound/CareerAbility; `AbilityEffectType` Projectile/Missile/SeekerMissile/Wind/Vortex/Heal/Augment/Hex/
  Summoning/Bombardment/Blast/ArtilleryPlacement/TimeWarpEffect/CareerAbilityEffect/TacticalReposition (каждому — свой *Script);
  `AbilityTargetType` Self/SingleEnemy/SingleAlly/EnemiesInAOE/AlliesInAOE/WorldPosition/GroundAtPosition; `CastType` Instant/WindUp/Channel;
  `TriggerType` EveryTick/OnCollision/TickOnce/OnStop/None; `ChargeType` CooldownOnly/NumberOfKills/DamageDone/Healed/DamageTaken/Custom.
- Школы (лоры): MinorMagic, LoreOfFire, LoreOfLight, LoreOfHeavens, LoreOfLife, LoreOfBeasts, LoreOfMetal, LoreOfDeath, DarkMagic, Necromancy, HighMagic, Waaagh.

Привязка к бойцам — по id NPCCharacter, сам troopdefinitions остаётся ванильного формата:
```xml
<CharacterExtendedInfo id="tor_emp_lord_college_magic_1">
  <Abilities><string>QuicksilverSwords</string><string>GleamingArrow</string></Abilities>
  <Attributes><string>AbilityUser</string><string>SpellCaster</string><string>LegendaryLord</string></Attributes>
  <Resistances><ResistanceTuple .../></Resistances>
  <DamageAmplifiers><AmplifierTuple AmplifiedDamageType="Physical" DamageAmplifier="0.25"/></DamageAmplifiers>
  <DamageProportions><DamageProportionTuple DamageType="Physical" Percent="1.00"/></DamageProportions>
  <ResourceCost ResourceType="Prestige" UpkeepCost="0" UpgradeCost="1"/>
</CharacterExtendedInfo>
```
- Атрибуты — строковые флаги, проверяемые в коде: AbilityUser, SpellCaster, Undead, Unbreakable, Expendable, Tough, Necromancer, CannotClimbLadders, TrollRegeneration…
- Во время игры `ExtendedInfoManager` (CampaignBehavior с `SyncData`) держит `HeroExtendedInfo`: MaxWindsOfMagic, WindsOfMagicRechargeRate, KnownLores, AllAbilities, SelectedAbilities, DominantReligion.
- Обучение игрока: учителя в городах, книги навыков, консоль `add_spells_to_player`.
- Конвейер: `AbilityComponent` на агентах с AbilityUser → `Ability.TryCast` → `DoCast` → `SpawnEntity` (свет, физика, скрипт) → скрипт тикает и
  запускает TriggeredEffect; числа — `TORAbilityModel`; клавиши — `TORGameKeyContext`.
- ИИ: `WizardAIComponent` строит «оси» полезности, `DecisionManager` выбирает лучшее поведение.
- VFX: `ParticleEffectPrefab` = имя сущности в `CORE\Prefabs\spelleffects_prefab.xml`:
  ```xml
  <prefabs>
   <game_entity name="dart_particle" old_prefab_name="" mobility="1">
    <transform position="0.000, 0.000, 0.000" rotation_euler="0.000, 0.000, 0.000"/>
    <components>
     <particle_system_instanced_component><effect_ref base_effect="{GUID}"/></particle_system_instanced_component>
    </components>
   </game_entity>
  ```
  Сами частицы — в tpac (редактор). Звук — id `module_sound`; иконки — спрайт-категория `ui_abilityicons`.

## 3. Эффекты, урон, навыки, карьеры

```xml
<TriggeredEffectTemplate StringID="dart_explosion" BurstParticleEffectPrefab="blue_particle_explosion" SoundEffectId="dart_explosion"
   SoundEffectLength="2.5" DamageType="Magical" DamageAmount="40" Radius="3" HasShockWave="false" TargetType="All" DamageVariance="0.2" ScriptNameToTrigger="none" />
<TriggeredEffectTemplate StringID="apply_minor_healing_statuseffect" DamageType="Invalid" Radius="4" TargetType="Friendly" ImbuedStatusEffectDuration="7" ScriptNameToTrigger="none">
  <ImbuedStatusEffect>minor_healing_regeneration</ImbuedStatusEffect>
</TriggeredEffectTemplate>
<!-- призыв: TroopIdToSummon="..." NumberToSummon="15" ScriptNameToTrigger="TOR_Core.BattleMechanics.TriggeredEffect.Scripts.SummonScript" -->
```
- **`ScriptNameToTrigger` — полное имя C#-типа, реализующего `ITriggeredScript`, создаётся через reflection** — главная точка расширения.
- TargetType: Friendly, Enemy, All, FriendlyHero, EnemyHero, Self.

```xml
<StatusEffectTemplate id="minor_healing_regeneration" particle_id="healing_regeneration" particle_intensity="High" base_effect_value="3" type="HealthOverTime"/>
<StatusEffectTemplate id="righteous_fury_effect" particle_id="righteous_fury" do_not_attach_to_agent_skeleton="true" base_effect_value="0.2"
    type="DamageAmplification" damage_type="All" applies_for_attack_type="Melee">
  <temporary_attribute>Unstoppable</temporary_attribute>
</StatusEffectTemplate>
```
- type: HealthOverTime, WindsOverTime, LanceSteadiness, DamageOverTime, DamageAmplification, Resistance, MovementManipulation,
  AttackSpeedManipulation, ReloadSpeedManipulation, TemporaryAttributeOnly.
- DamageType: Invalid, Physical, Magical, Fire, Holy, Lightning, Frost, All; AttackTypeMask Ranged/Melee/Spell/All. Применяется в `TORAgentApplyDamageModel`.
- `<AnimationTrigger action_name="act_lhm_hitground_right" animation_percent_to_trigger="0.5" bone_index="27" triggered_effect="treeman_smash" />`
  — эффект в момент анимации (удар копытом, взмах крыльев).
- Навыки (`SkillObject`) и атрибуты регистрируются в коде; используются в `tor_skillsets.xml` и опциях создания персонажа. Перки и карьеры — полностью в коде.
- Создание персонажа: `tor_cc_options.xml`, `tor_specialization_options.xml` → своя стадия `TORSpecializationStage`.

## 4. Кампания

**Ink-истории** (`CORE\InkStories\*.ink`): компилируются во время игры (`ink_compiler.dll` + `ink-engine-runtime.dll`), `InkStoryManager.LoadStories`,
случайный запуск в пути по тегу `frequency`, также от предмета или консолью (`open_ink_story`, `reload_ink_stories`); UI `GUI\Prefabs\InkStory\InkStory.xml`.
```
# title: Pond
# frequency: Common
# development: false
# illustration: pond
INCLUDE include.ink
-> Start
===Start===
Text line #STR_Start1
 {IsNight(): Silver moonlight | Golden sunlight} ...
    *[Gather wild plants (...{LoreOfLifeInParty: 50%|25%})] ... ->ForageLoop
```
`#STR_x` — ключи локализации. C#-функции объявлены `EXTERNAL` в `include.ink`: GetPlayerSkillValue, GiveSkillExperience, PartyHasSpellcaster,
GetNearestSettlement, ChangePartyTroopCount, GiveGold, GiveItem, ChangeRelations, HealPartyToFull, OpenDuelMission, Get/SetPlayerCustomTag, IsNight, PlayMusic, StartQuest, CloseStory.

**Квесты** — подклассы `QuestBase` в коде (+ `QuestPartyComponent`, `QuestFightMissionController`); события — `CustomEventsCampaignBehavior`.

**Свои типы поселений** (`tor_settlements.xml`, 1107 шт.):
```xml
<Settlement id="sigmar_shrine_02" name="{=...}Shrine of Sigmar" owner="Faction.averland_clan_1" posX="1501.502" posY="872.269" culture="Culture.empire" gate_posX=".." gate_posY="..">
  <Components>
    <Shrine id="sigmar_shrine_01" religion="cult_of_sigmar" background_crop_position="0.0" background_mesh="shrine_of_sigmar" wait_mesh="wait_empire_village" gate_rotation="0.0"/>
  </Components>
</Settlement>
```
Элемент компонента → C# `TORBaseSettlementComponent : SettlementComponent` + `*MenuLogic` (меню) + состояние в CampaignBehavior.SyncData.
Типы: Shrine, CursedSite, HerdStone, TrollCave, ChaosPortal, SlaverCamp, OakOfAges, WorldRoots.

**Религии** — XmlNode `Religions` → `ReligionObject : MBObjectBase`:
```xml
<Religion id="cult_of_sigmar" Name="{=..}Cult of Sigmar" Culture="Culture.empire" Pantheon="Human" DeityName="Sigmar">
  <HostileReligions><HostileReligion id="Religion.cult_of_nagash"/></HostileReligions>
  <ReligiousTroops><ReligiousTroop id="NPCCharacter.tor_empire_flagellant"/></ReligiousTroops>
  <ReligiousArtifacts><ArtifactItem id="Item.tor_..."/></ReligiousArtifacts>
</Religion>
```
+ `ReligionCampaignBehavior`, `TORFaithModel`, навык Faith, своя страница энциклопедии. Свои ресурсы: `CustomResourceManager` (Prestige, Chivalry…).

**Своя глобальная карта**: `ENV\SceneObj\Main_map\` (`scene.xscene` 24 МБ, `terrain.bin`, `flora.bin`, `navmesh.bin`, `atmosphere.xml`).
- **Подменяет ванильную тем же именем сцены `Main_map`** в модуле, загружаемом после SandBoxCore.
- Harmony `CustomWorldMapPatch`: `ChangeSettlementPathToTOR`, `ChangeCachePathToTOR` (кэш `settlements_distance_cache_Default.bin`), `LoadSinglePlayerBattleScenes`.
- `tor_singleplayerbattlescenes.xml`: `<Scene id="TOR_vampire_battle_001_atmo_w_night" terrain="Swamp" map_indices="41,42"/>`; Custom Battle — `tor_custombattlescenes.xml`.
- `flora_kinds.xml`, `flora_layer_sets.xml`, `terrain_materials.xml`; атмосферы `ENV\Atmospheres\*.xml` + `Interpolated\campaign_map.xml`.
- Иконки/нейм-плейты карты — Gauntlet (`GUI\Prefabs\Nameplate\SettlementNameplateItem*.xml`), 3D-иконки — ассеты в tpac.
- Музыка: PSAI `Music\soundtrack.xml` (mbproj) + свой обработчик и NAudio.

## 5. GUI

- `CORE\GUI\Prefabs\`: новые экраны (AbilityHUD, SpellBook, CareerScreen, InkStory, SpecializationStage…) и **замена ванильных тем же именем файла**
  (InitialScreen.xml, Map\MapBar.xml, Party\PartyScreen.xml, Inventory\*, FaceGen\FaceGenBody.xml, Encyclopedia\…).
- Привязки Gauntlet: `@Property` из C# ViewModel. Миссия: `MissionView` → `LoadMovie("AbilityHUD", vm)`; экран: `GameState` + `ScreenBase`; карта: `MapView`.
- Расширение ванильных VM без UIExtenderEx: свой `ViewModelExtensionManager` + Harmony. Свои виджеты — классы от Widget, используются по имени тега.
- Brushes: `TorBrushes.xml`, `VanillaBrushOverrides.xml` (те же имена, что в ванили). Спрайты — в Armory (см. 02).

## 6. Настройки, логи, сохранения

- Без MCM: `tor_config.xml` (`<TORConfiguration MaximumNumberOfCareerPerkPoints="30" MinPeaceDays="20" .../>`) → статический `TORConfig`, консоль `reload_config`.
- `TORPaths` — все пути в одном месте. Консольные команды через `[CommandLineArgumentFunction]`.
- NLog: `Logs/yyyy/MMMM/dd/TOR_log<date>.txt`, `TORCommon.Log`; `TORCommon.Say` — сообщения в игре.
- Сохранения: `TORSaveableTypeDefiner : SaveableTypeDefiner` с базовым id **771000** (+ 789123, 789124 у отдельных определителей);
  состояние — в `SyncData` CampaignBehavior; **шаблоны (способности, эффекты) не сохраняются, а перечитываются из XML** — баланс можно менять без поломки сейвов.

## 7. Перевод (TOR_RU_Translation)

- Стандарт: `ModuleData\Languages\RU\language_data.xml` + `str_tor_*-rus.xml` (`<base xml_name=".."><tags><tag language="Русский"/></tags><strings>…`) — работает, потому что везде `{=id}`.
- Для захардкоженных строк — свой DLL с Harmony (подмена `MBTextManager.SetTextVariable`, конструктора TextObject); ink-файлы копируются поверх; свои GUI prefabs под длину текста.
- **Урок**: `{=id}` везде, `#STR_` в ink, никаких видимых строк в C# — тогда перевод не требует кода.

## Чеклист для пони-мода (магия единорогов, полёт пегасов, карта Эквестрии)

1. Модули как у TOR: Core (DLL + геймплейные XML + GUI + Ink), Armory (предметы, расы, монстры, action sets, спрайты, звуки, tpac), Environment (Main_map, сцены боёв, атмосферы, флора).
2. .NET Framework 4.7.2/4.8; зависимость от Bannerlord.Harmony; один `new Harmony("mod.harmony.equestria").PatchAll()` в `OnSubModuleLoad`; свои доп. DLL + AssemblyResolve.
3. `InitializeGameStarter`/`OnGameStart`: GameModel-переопределения, CampaignBehavior; `OnMissionBehaviorInitialize`: логика способностей/эффектов/ИИ.
4. Расы earth_pony/unicorn/pegasus (см. 01) + Monster + `race=` + ограничение брони по расе.
5. Магия единорогов — та же триада данных: `abilitytemplates.xml` (ману вместо Winds of Magic, школы вроде `SchoolOfLevitation`), `triggeredeffects.xml`
   (свои DamageType, `ScriptNameToTrigger` для телепорта/левитации/щита), `statuseffects.xml`; `extendedunitproperties.xml` с Abilities/Attributes
   (`AbilityUser`, `SpellCaster`, `Flyer`); `AbilityComponent` на агентах; мана героя в `HeroExtendedInfo` через `SyncData`.
6. VFX — частицы в редакторе, обёрнутые в именованные `game_entity` в `Prefabs\*.xml`; свечение рога — свет из полей шаблона.
7. ИИ колдовства — utility-скоринг с поведением на тип эффекта; HUD — MissionView + VM + prefab; клавиши — GameKeyContext; книга заклинаний — GameState/ScreenBase.
8. **Полёт пегасов**: в TOR общей системы нет (только `PlayerFlyableObjectScript` для объекта + телепорты). Делать режим агента: способность/статус + `AgentComponent`,
   отключающий гравитацию и ведущий позицию каждый тик; свои `as_pegasus_*` action sets; `AnimationTrigger` для удара крыльями; `MovementManipulation` для посадки/выносливости;
   на карте кампании — бонус скорости и игнор местности через `PartySpeedCalculatingModel`, обзор — `MapVisibilityModel`.
9. **Карта Эквестрии**: сцена `Main_map` в SceneObj своего Environment; `settlements.xml` под карту + `settlements_distance_cache`; Harmony-патч путей как `CustomWorldMapPatch`
   (или XmlNode + xslt); `singleplayerbattlescenes.xml`; атмосферы.
10. Особые места (руины Вечнодикого леса, Кристальное сердце, улей чейнджлингов) — свои `<Components>` + `SettlementComponent` + меню + CampaignBehavior.
11. «Веры» (принцессы/Гармония) — по образцу `Religions` MBObject.
12. События — ink с заголовком `# title/frequency/illustration`, `INCLUDE include.ink`, `EXTERNAL`-функции C#; длинные цепочки — `QuestBase`.
13. Карьеры/перки (Вондерболты, Королевская гвардия, Ученица магии) — объекты в коде + экран; навыки Magic/Flight — `SkillObject`.
14. Отладка: XML-конфиг + консольные reload-команды, логи по дням, свой `SaveableTypeDefiner` с уникальным id (далеко от 771000/789123), шаблоны не в сейвах.
15. Локализация: `{=id}`, `#STR_` в ink, `Languages\<LANG>\language_data.xml`, без захардкоженных строк.
