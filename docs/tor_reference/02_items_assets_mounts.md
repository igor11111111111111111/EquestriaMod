# The Old Realms — предметы, ассеты, ездовые животные

Справочник по файлам The Old Realms (Bannerlord v1.3.15), 2026-09-15. Только описание устройства — без копирования кода/ассетов.
Пути: **CORE** = TOR_Core (3025574678), **ARM** = TOR_Armory (3025575223), **ENV** = TOR_Environment (3025579210), **VAN** = ванильные `Modules`.

## 1. Деление на модули

Тяжёлые бинарные ассеты — в модулях без DLL; код и данные кампании — в Core. Модули обновляются независимо.

| Модуль | Зависимости | DLL | Содержимое |
|---|---|---|---|
| TOR_Armory | Native, SandBoxCore, Sandbox, CustomBattle, BirthAndDeath, StoryMode | нет | `AssetPackages\pack0..8.tpac` (~11 ГБ), GUI-арт, ModuleSounds, Shaders\Sources, все XML предметов/рас/анимаций/монстров |
| TOR_Environment | Native, SandBoxCore, Sandbox | нет | `AssetPackages\pack0..4.tpac` (~6.5 ГБ), SceneObj (193 сцены), Prefabs (154), Atmospheres, NavMeshPrefabs, flora_kinds, terrain_materials, custombattlescenes |
| TOR_Core | Native, SandBoxCore, Sandbox, StoryMode, TOR_Armory, TOR_Environment | TOR_Core.dll (+NAudio, ink) | бойцы, rosters, культуры, кланы, королевства, поселения, строки, tor_custom_xmls, GUI prefabs/brushes, Prefabs (VFX заклинаний, артиллерия), Music |

Armory SubModule.xml:
```xml
<XmlNode><XmlName id="Items" path="tor_items"/> <!-- папка: tor_armors, tor_horseandharness, tor_meleeweapons, tor_rangedweapons, tor_shields, tor_projectiles, tor_other_items -->
<XmlNode><XmlName id="CraftingPieces" path="tor_crafting_pieces"/>
<XmlNode><XmlName id="CraftingTemplates" path="tor_crafting_templates"/>
<XmlNode><XmlName id="Monsters" path="tor_monsters"/>
<XmlNode><XmlName id="WeaponDescriptions" path="tor_weapon_descriptions"/>
```
Движковые XML — в `ModuleData\project.mbproj`: `item_usage_set`, `monster_usage_set`, `action_set`, `action_type`, `item_holster`, `skin`,
`voice_definitions`, `monster`, `module_sound`, `animation_combat_parameters`, movement sets. Core mbproj: `tor_sounds.xml` (module_sound), `Music/soundtrack.xml` (soundtrack).

XSLT-патчи (`X.xslt` рядом с `X.xml`): удаление ванильного human-skin, human monster_usage_set, `player_char_creation_show_*` rosters.
Культуры — ванильные id (empire = Империя, vlandia = Бретония, khuzait = Вампиры, battania = Лесные эльфы, sturgia = Дварфы, aserai = Зеленокожие) + новые (`chaos_culture`, `eonir`, `mousillon`, `neutral_culture`).

## 2. Упаковка ассетов

- Выпускаются **только `AssetPackages\packN.tpac`** (результат Publish в Modding Kit, 0.3–1.9 ГБ каждый). Нет Assets/AssetSources/RuntimeDataCache.
  Меши, материалы, текстуры, скелеты, анимации, частицы, текстуры спрайтов — внутри tpac; XML ссылается по имени.
- Shaders: только исходники `.rs/.rsh` двух своих шейдеров (варианты base, _constant_output, _gbuffer, _overdraw, _pointlight, _shadowmap). Свои шейдеры обычно не нужны.
- GUI (`ARM\GUI`): `SpriteParts\Config.xml` (`<SpriteCategory Name="ui_abilityicons"><AlwaysLoad/></SpriteCategory>`), исходные PNG в `SpriteParts\ui_<category>\`,
  сгенерированный упаковщиком `<ModuleName>SpriteData.xml` (SpriteCategory/SpritePart/GenericSprite); листы — в tpac.
  Шрифты: `GUI\Fonts\*.bfnt/.fnt` + `<Module>Languages.xml` (`<Map From="Galahad" To="CasablancaAntique"/>`). Gauntlet prefabs и brushes — в Core.
- Звуки: `ModuleSounds\` (+подпапки), описание `<base type="module_sounds">`, регистрация в mbproj:
  ```xml
  <module_sound name="beastmen_01_death" sound_category="mission_voice_shout" is_2d="false" min_pitch_multiplier="0.90" max_pitch_multiplier="1.10">
    <variation path="\VoiceCommands\Beastmen\beastmen_01\BMdeath_01.ogg" weight="1.00" />
  </module_sound>
  ```
  Валидные `sound_category`: mission_ambient_bed, mission_ambient_3d_big/medium/small, mission_material_impact, mission_combat_trivial,
  mission_combat, mission_foley, mission_voice_shout, mission_voice, mission_voice_trivial, mission_siege_loud, mission_footstep,
  mission_footstep_run, mission_horse_gallop, mission_horse_walk, ui, alert, campaign_node, campaign_bed. **Без валидной категории звук не играет.**
  В C#: `SoundEvent.GetEventIdFromString("name")`.
  ⚠️ Анти-пример: Core ссылается на звуки Armory путём `../../3025575223/ModuleSounds/...` (workshop id) — не делать так.
- Голоса: `<voice_definition name="beastmen_01" sound_and_collision_info_class="human"><voice type="Grunt" path="beastmen_01_grunt" face_anim="grunt"/>`.

## 3. XML предметов

- Одна категория — один файл в папке; id `tor_<faction>_<slot>_<kind>_<name>_NNN`; имена `{=str_<item_id>}Name`.
- `<Armor>`: `head_armor`, `body_armor`, `leg_armor`, `arm_armor`, `modifier_group` (plate/leather/cloth/chain), `material_type` (Plate/Leather/Cloth/Chainmail),
  `hair_cover_type` (all/type1/type2/type3), `beard_cover_type` (all/type2/type3), `covers_head`, `covers_body`, `covers_legs`, `covers_hands`, `has_gender_variations`.
  Упряжь: `mane_cover_type`, `reins_mesh`, `family_type`, `maneuver_bonus`, `speed_bonus`, `charge_bonus`.
- **`covers_beard` не существует** (использовать `beard_cover_type`). `item_category` — только у лошадей. `prefab=` — у знамён и артиллерии.
- Броня всегда одним `mesh=` (наплечники и т.п. внутри меша). **Наплечники/накидки — слот `Type="Cape"`.**
```xml
<Item id="tor_empire_head_helm_militia_001" name="{=str_tor_empire_head_helm_militia_001}Militia Sallet" mesh="emp_militiahelmet_a"
      weight="2.7" appearance="1" Type="HeadArmor" is_merchandise="true" culture="Culture.empire" subtype="head_armor" value="900">
  <ItemComponent><Armor modifier_group="plate" material_type="Plate" head_armor="18" hair_cover_type="type1" beard_cover_type="type2" /></ItemComponent>
  <Flags Civilian="true" UseTeamColor="true" />
</Item>
<!-- тело:  <Armor body_armor="30" leg_armor="10" arm_armor="10" has_gender_variations="true" covers_body="true" .../> -->
<!-- руки:  Type="HandArmor" subtype="hand_armor"  <Armor arm_armor="36" covers_hands="true" .../> -->
<!-- ноги:  Type="LegArmor" subtype="leg_armor"    <Armor leg_armor="40" covers_legs="true" .../> -->
```
`covers_body/legs/hands="true"` скрывает соответствующую часть голого базового тела — полные меши-замены без просвечивания.

Нечеловеческие головы:
- **«Шлем»-замена головы**: `covers_head="true"` + `hair_cover_type="all"` + `beard_cover_type="all"`; меш и есть голова (treeman, dryad, minotaur, spirit host).
  → **Это ровно подход «костюма пони» для теста.**
- Отдельные расы со своими базовыми мешами (см. 01_races_characters.md); волосы с `cover_type1..4` вариантами под шлемы.
- Шлемы под конкретную расу — отдельные предметы + `RaceLock` в custom XML (C#). В ванили ограничения по расе нет.

Ваниль отличается стилем (атрибут на строку), использует `body_mesh_type="shoulders"`, `lod_atlas_index`, больше `prefab`, `item_category` лошадей: horse, noble_horse, war_horse, sumpter_horse, animal.

Щит:
```xml
<Item id="tor_empire_weapon_shield_001" body_name="bo_cap_empire_shield_001" shield_body_name="bo_empire_shield_001" recalculate_body="false"
      mesh="empire_shield_001" using_tableau="true" weight="5.3" Type="Shield" culture="Culture.empire"
      item_holsters="shield_kite:shield_2:shield_3:shield_4" has_lower_holster_priority="true" holster_position_shift="0.0,0.0,0.0">
  <ItemComponent>
    <Weapon weapon_class="LargeShield" body_armor="8" thrust_damage="2" thrust_speed="82" thrust_damage_type="Blunt" speed_rating="82"
            item_usage="shield" rotation="5.0,15.0,40.0" physics_material="metal_shield" weapon_length="60" modifier_group="shield" hit_points="500">
      <WeaponFlags CanBlockRanged="true" HasHitPoints="true" />
    </Weapon>
  </ItemComponent>
  <Flags WoodenParry="true" HeldInOffHand="true" ForceAttachOffHandSecondaryItemBone="true" />
</Item>
```
`bo_*` — коллизии в tpac; `using_tableau="true"` — геральдика на щите.

## 4. Оружие

- `tor_crafting_pieces.xml`: части Blade/Handle/Guard/Pommel, по мешу на часть `<weapon>_NNN_blade/_handle/_guard/_pommel`; `is_hidden="true"` — не в кузнице игрока.
```xml
<CraftingPiece id="runefang_001_blade" tier="6" piece_type="Blade" culture="Culture.empire" length="96.2" weight="1.35" is_hidden="true" mesh="runefang_001_blade">
  <BladeData stack_amount="1" physics_material="metal_weapon" body_name="bo_runefang_001_blade">
    <Thrust damage_type="Pierce" damage_factor="3.0" /><Swing damage_type="Cut" damage_factor="4.0" />
  </BladeData>
  <Materials><Material id="Iron5" count="3" /></Materials>
</CraftingPiece>
<!-- Handle: <BuildData piece_offset="0" next_piece_offset="0.5" previous_piece_offset="0.5" /> -->
<CraftedItem id="tor_empire_weapon_sword_runefang_001" crafting_template="tor_sword_template" is_merchandise="false" culture="Culture.empire" value="58800">
  <Pieces><Piece id="runefang_001_blade" Type="Blade" scale_factor="100" /><Piece id="runefang_001_handle" Type="Handle" scale_factor="100" />
          <Piece id="runefang_001_guard" Type="Guard" /><Piece id="runefang_001_pommel" Type="Pommel" /></Pieces>
</CraftedItem>
```
- Шаблоны (`tor_crafting_templates.xml`) по классам оружия + расовые варианты со сдвигом ножен (`default_item_holster_position_offset="0,0.2,-0.45"`).
  Посох: `<CraftingTemplate id="tor_staff_template" item_type="Polearm" ... use_weapon_as_holster_mesh="true">` с PieceDatas, WeaponDescriptions, StatsData, UsablePieces.
- `tor_weapon_descriptions.xml`: `<WeaponDescription id="TorStaves" weapon_class="TwoHandedPolearm" item_usage_features="polearm:block:long:shield:swing:thrust">` + WeaponFlags + AvailablePieces.
- **Магический посох = обычное крафтовое древковое**, «сфера» — это Blade-часть. Магия — в C# + `tor_abilitytemplates.xml`.
- Огнестрел — ручные `<Item>` (`weapon_class="Musket" ammo_class="Cartridge" item_usage="handgun"`), свои `item_usage_set` (`base_set="crossbow"`) в `tor_item_usages.xml`,
  ножны в `tor_item_holsters.xml` (`<item_holster id=".." group_name="crossbow_back" holster_skeleton="holster_skeleton_back" base_set="thorax_back_crossbow" .../>`). Звук/VFX выстрела — из C#.
- Боеприпасы: `Type="Bullets"`, `flying_mesh`, `WeaponFlags AttachAmmoToVisual Consumable AmmoBreaksOnBounceBack`.
  **Снаряды заклинаний — тоже предметы-боеприпасы** (`weapon_class="Undefined"`, `CanPenetrateShield`, `MultiplePenetration`), C# запускает их как снаряды.
  Без кода: `trail_particle_name="psys_cannonball_trail"` + `WeaponFlags LeavesTrail="true"`, `flying_sound_code="event:/..."`.
- Артиллерия — `Type="Goods"` с `prefab="MortarSpawner"` (`CORE\Prefabs\artillery.xml`).

## 5. Ездовые животные (важно для пегасов/единорогов)

- **Грифонов/пегасов в TOR нет; никто не летает.** Есть лошади разных размеров, нежить-кони, призрачный конь, демигриф, олень, **единорог**, кабан, волк — все `Type="Horse"` на **ванильном `horse_skeleton` и анимациях лошади**.
- Монстры (`tor_monsters.xml`), все от `horse`:
  ```xml
  <Monster id="demigryph" base_monster="horse" action_set="as_demigryph" monster_usage="demigryph" family_type="9" />
  <Monster id="ghost_horse" base_monster="horse" action_set="as_ghost_horse" family_type="10" />
  <Monster id="great_stag" base_monster="horse" action_set="as_great_stag" />
  ```
  Action sets — алиасы: `<action_set id="as_demigryph" base_set="as_horse" />`, `as_demigryph_map` → `as_horse_map`. Копия `monster_usage_set id="demigryph"`.
  `family_type` (ваниль): 0 human, 1 horse, 2 camel, 3 cow, 4 goose, 5 hog, 6 sheep, 8 chicken; TOR добавил 9 и 10 — **упряжь подходит только при совпадении family_type**.
- **Единорог = `Monster.horse` со своим мешем** (рог в меше), самый простой путь:
  ```xml
  <Item id="tor_we_mount_unicorn_001" name="{=str_tor_horses_unicorn1}Unicorn" mesh="unicorn_body_001" subtype="horse" item_category="horse"
        weight="380" difficulty="150" appearance="0.7" Type="Horse" is_merchandise="false" value="350000" culture="Culture.battania">
    <ItemComponent>
      <Horse monster="Monster.horse" maneuver="80" speed="70" charge_damage="65" body_length="110" is_mountable="true" skeleton_scale="vlandia_horse">
        <AdditionalMeshes></AdditionalMeshes><Materials></Materials>
      </Horse>
    </ItemComponent>
    <Flags Civilian="true" />
  </Item>
  ```
  Демигриф: `<AdditionalMeshes><Mesh name="demigryph_feathers_001" affected_by_cover="true" /></AdditionalMeshes>` (скрывается упряжью с `mane_cover_type="all"`).
  Окраска: `<Materials><Material name="horse_brown_mat"><MeshMultipliers><MeshMultiplier mesh_multiplier="FF010101" percentage="0.75" />…`.
- Размер: `skeleton_scale="vlandia_horse"` → `VAN\Native\ModuleData\skeleton_scales.xml` (`skeleton="horse_skeleton" mount_sit_bone_scale=".."` + `<BoneScale bone_name="horseneck1" scale=".."/>`);
  свой размер — своя запись skeleton_scales, `body_length`, масштаб меша.
- Упряжь: `Type="HorseHarness"`, `<Armor body_armor="120" mane_cover_type="all" reins_mesh="demigryph_reins_001" charge_bonus="50" family_type="9" .../>`; `reins_mesh=""` допустим.
- **Полёт** XML не поддерживает — только C#. Косметический пегас: horse_skeleton, крылья в меше или AdditionalMesh.

## 6. Наборы экипировки

`CORE\ModuleData\tor_equipment_sets.xml` — 807 `<EquipmentRoster id=".." culture="..">`, id `tor_<faction>_<troop>_template`, несколько `<EquipmentSet>` (случайные варианты) + `civilian="true"`.
Слоты: Item0..Item3, Head, Body, Cape, Gloves, Leg, Horse, HorseHarness. Боец ссылается: `<Equipments><EquipmentSet id="tor_empire_recruit_template" /><EquipmentSet id="..." civilian="true" /></Equipments>`.

## 7. Визуальные эффекты

- Системы частиц (`psys_flaming_weapon`, `psys_magic_weapon`, `psys_fireball_explosion_1`, …) **создаются в редакторе и лежат в tpac**; XML ссылается по имени.
- Без кода: `trail_particle_name` + `LeavesTrail` на снаряде; частица через `prefab=` предмета; эмиссивный материал.
- Светящееся/горящее оружие — C# по `tor_itemtraits.xml`:
  ```xml
  <ItemTrait ItemTraitStringId="flaming_weapon" ImbuedStatusEffectId="fireball_dot" ImbuedEffectChance="0.25" IconName="traits_fire_icon">
    <ValidItemType>Weapon</ValidItemType>
    <AdditionalDamageTuple DamageType="Fire" Percent="0.25" />
    <WeaponParticlePreset ParticlePrefab="psys_flaming_weapon" IsUniqueSingleCopy="false" />
  </ItemTrait>
  ```
- Взрывы: `tor_triggeredeffects.xml` (`<TriggeredEffectTemplate StringID="dart_explosion" BurstParticleEffectPrefab=".." SoundEffectId=".." DamageType="Magical" DamageAmount="40" Radius="3"/>`).
- Префабы `CORE\Prefabs\*.xml` (`<prefabs><game_entity name="fireball_prefab">` с `<particle_system_instanced_component base_effect="{GUID}">`) — можно держать россыпью в папке Prefabs любого модуля.

## Чеклист для пони-мода

1. Модули: `Pony_Assets` (без DLL: tpac, GUI-арт, звуки, XML предметов/skins/monsters/анимаций) + `Pony_Core` (DLL, бойцы, культуры, rosters, строки; зависит от Pony_Assets); сцены — `Pony_Environment`.
2. Выпускать только `AssetPackages\*.tpac` + XML, звуки, GUI; никаких путей с workshop id.
3. SubModule: Items папкой (`pony_items`: armors, weapons, mounts, shields, ammo), CraftingPieces, CraftingTemplates, WeaponDescriptions, Monsters, EquipmentRosters, NPCCharacters, BodyProperties, SPCultures.
   mbproj: skins, action_sets, monster_usage_sets, item_usage_sets, item_holsters, voice_definitions, module_sound, movement_sets.
4. Имена: `pony_<faction>_<slot>_<kind>_<name>_NNN`, `{=str_<id>}`, один меш на предмет, коллизии `bo_<mesh>`.
5. Антро-тела: раса в `pony_skins.xml` на human_skeleton (см. 01); Monster + action sets.
6. Броня: `covers_body/legs/hands`; головы — пони-шлемы с mane-вариантами или полная замена `covers_head="true" hair_cover_type="all"`; наплечники — `Cape`; ограничение по расе — C#.
7. Оружие: скрытые CraftingPiece + шаблон + WeaponDescription + CraftedItem; щиты/луки — `<Item>` с `<Weapon>`; магические снаряды — боеприпасы с `flying_mesh` + `trail_particle_name`.
8. Пегас/единорог: меш на `horse_skeleton`, `Type="Horse"` с `Monster.horse`; эксклюзивная упряжь — свой Monster с `family_type="11"` + `as_pegasus` → `as_horse`; размер — skeleton_scales/body_length; полёт — C#.
9. Rosters: один на бойца, несколько вариантов + civilian.
10. Звуки: `ModuleSounds` + `pony_sounds.xml` в mbproj, валидная `sound_category`; голоса через voice_definitions.
11. GUI: PNG в `GUI\SpriteParts\ui_pony_*\` + Config.xml, упаковщик спрайтов Kit; Gauntlet prefabs/brushes в модуле кода.
12. VFX: частицы в редакторе, ссылки по имени; ауры оружия на лету — C#.
13. Изменения ванили — через одноимённые `.xslt`, а не копии файлов.
