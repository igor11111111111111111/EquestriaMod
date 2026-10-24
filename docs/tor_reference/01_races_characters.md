# The Old Realms — расы и персонажи

Справочник составлен по файлам The Old Realms (Bannerlord v1.3.15) перед удалением мода, 2026-09-15.
Только описание устройства — код и ассеты TOR не копировались.

Пути: **CORE** = TOR_Core (workshop 3025574678), **ARM** = TOR_Armory (3025575223), **VAN** = ванильные `Modules`.

Итог: визуальные и физические данные рас лежат в **Armory** (без DLL): skins, monsters, action sets, голоса, cloth bodies,
скелеты внутри tpac. Данные персонажей — в **Core**: бойцы, лорды, шаблоны тел, культуры, строки. Геймплейные правила
для рас — в C# DLL Core.

## 1. Определение рас — skins.xml

- TOR: `ARM\ModuleData\tor_skins.xml` (7 МБ) + `tor_skins.xslt`; ваниль: `VAN\Native\ModuleData\skins.xml` (та же схема, одна раса `human`).
- Skins грузятся **не через SubModule.xml**, а через `ModuleData\project.mbproj`:
  ```xml
  <file id="soln_skins" name="ModuleData/tor_skins.xml" type="skin" />
  <file id="soln_action_sets" name="ModuleData/tor_action_sets.xml" type="action_set" />
  <file id="soln_action_types" name="ModuleData/tor_action_types.xml" type="action_type" />
  <file id="soln_monster_usage_sets" name="ModuleData/tor_monster_usage_sets.xml" type="monster_usage_set" />
  <file id="soln_voice_definitions" name="ModuleData/tor_voice_definitions.xml" type="voice_definitions" />
  <file id="soln_monsters" name="ModuleData/tor_monsters.xml" type="monster" />
  <!-- + movement_sets, full_movement_sets, module_sound, combat_system -->
  ```
- `tor_skins.xslt` удаляет ванильного human (`<xsl:template match="race[@id='human']"/>`), TOR даёт свой `<race id="human">` первым (индекс 0).
- **Порядок рас = целочисленный id в сохранениях** (0 human, 1 vampire, … 13 dwarf, 14 orc, 15 goblin, 16 troll, 17 bretonnian). Новые расы только в конец.
- У каждой расы ровно **10 `<skin>`**: `man`/`woman` (adult), `kid_2_*`, `kid_1_*`, `kid_3_*`, `toddler_*`; детские обычно копия человеческих.

Пример (дварф, мужчина):
```xml
<race id="dwarf">
  <skin gender="0" name="man" mesh_maturity_type="adult" morph_key="0" uses_stitching="true"
        body_mesh_suffix="" min_scale="1.01" skeleton="dwarf_skeleton"
        body_meta_mesh="dwarf_body" body_meta_mesh_shoulders="dwarf_body" body_meta_mesh_upperbody="box_a"
        legs_mesh="dwarf_feet" hands_mesh="dwarf_hands" face_meta_mesh="dwarf_head"
        underwear_bottom_mesh="" underwear_top_mesh="">
```
Вампир — новые меши на `human_skeleton`; женский skin с `body_mesh_suffix="_fem"`, `min_scale="1.06"`.
Многие расы имеют «заглушку» `woman` на человеческих женских мешах (у дварфов женщин в контенте избегают: `townswoman` → мужчина).

Дочерние элементы `<skin>`:
- `<deform_keys>` — 63 ключа: слайдеры лица (id, key_time_point, key_min/max, group_id, helmet_scaling_factor_min/max, deforms_hair) и тело: `weight`(60), `build`(61), `height`(62), `age`(63).
- `<bone_scales>` внутри weight/build: `<bone_scale bone_type="biped_thigh_l" axis="x" key_min="0.95" key_max="1.12"/>` — пропорции тела.
- `<voice_types><voice_type name="dwarf_male_01"/>`.
- `<hair_meshes group_id="7">`, `<beard_meshes>` (группы: брови 5, борода 6, волосы 7, тату 8), `<eyebrow_meshes>`, `<tattoo_materials group_id="8">`.
- Палитры: `hair_/skin_/eye_/tattoo_color_gradient_points` (`<skin_color_gradient_point point="1.0, 1.0, 1.0"/>`).
- `<face_textures group_id="1">` (`<face_texture name=".." lod_material=".." color="0xFFFFFFFF" tags=".."/>`), `<mouth_textures group_id="4">`, `<constraints>`.
- Волосы/бороды: `cover_type1..4` (варианты под шлемами) и `<style_tags><style_tag name="DwarfHair"/>` — по тегам NPC выбирают причёски. Пустой `<hair_mesh>` с тегом `Bald` = лысый вариант.
- **Слайдеры лица у всех рас — копия человеческих (те же id и time points)**; морфы лежат в меше головы расы. Новая голова должна иметь те же морф-каналы, иначе слайдеры ничего не делают.

## 2. Нечеловеческие формы

- **Свой скелет**: dwarf (`dwarf_skeleton`), orc (`orc_skeleton2`, min_scale 1.2), goblin, troll. Скелеты только в скомпилированных tpac.
- **Человеческий скелет + новые меши**: vampire, necrarch, skeleton, spirit_host, wraith, ungor, gor, elf, marauder, bretonnian и др.
- **Масштабированный человек**: `large_humanoid_monster` min_scale 2.9/2.7, `medium_humanoid_monster` 1.5/1.4, marauder/gor 1.27.
- Рост = `min_scale` в skin + ключ `height` + соответствующая капсула Monster.

### Monsters (`ARM\ModuleData\tor_monsters.xml`, SubModule `XmlName id="Monsters"`)
**id монстра = id расы.** Движок ищет `race`, `race_child`, `race_settlement`, `race_settlement_slow`, `race_settlement_fast` — TOR задаёт все 5:
```xml
<Monster id="dwarf" action_set="as_dwarf_warrior" base_monster="human">
  <Capsules>
    <body_capsule radius="0.35" pos1="0.0, 0.0, 1.3" pos2="0.0, 0, 0.8" />
    <crouched_body_capsule radius="0.35" pos1="0.0, 0.0, 1.3" pos2="0.0, 0, 0.8" />
  </Capsules>
</Monster>
<Monster id="dwarf_child" base_monster="human_child" />
<Monster id="dwarf_settlement" base_monster="dwarf" walking_speed_limit="0.9">
  <Flags CanAttack="true" CanDefend="true" CanBeCharged="true" CanClimbLadders="true" CanBeInGroup="true"
         CanSprint="true" IsHumanoid="true" CanRide="true" CanWieldWeapon="true" CanCrouch="true" />
</Monster>
<Monster id="dwarf_settlement_slow" base_monster="dwarf_settlement" walking_speed_limit="0.7" />
<Monster id="dwarf_settlement_fast" base_monster="dwarf_settlement" walking_speed_limit="0.9" />
```
Примеры: goblin radius 0.3 / верх 1.1; orc 0.45 / 1.65; troll 0.7 / pos1 3.35, `weight="300"`, без CanRide;
medium monster `walking_speed_limit="3.5" jump_acceleration="10.0" weight="200"`. Простые расы: `<Monster id="elf" base_monster="human" action_set="as_elf_warrior"/>`.

### Action sets (`ARM\ModuleData\tor_action_sets.xml`)
- Новые действия добавляются в ванильный `as_human_warrior` (тот же id → слияние).
- Каждой расе **85 наборов** `as_<race>_<suffix>` с `base_set="as_human_<suffix>"`; для своего скелета + `skeleton="dwarf_skeleton"`.
  Для рас на человеческом скелете: `<action_set id="as_vampire_warrior" base_set="as_human_warrior" />`.
- Суффиксы (нужны все, иначе ломаются города, карта, редактор лица, таверны):
  warrior, female_warrior, hideout_bandit, female_hideout_bandit, villager, female_villager, villager_in_tavern, female_villager_in_tavern,
  warrior_in_tavern, female_warrior_in_tavern, villager_in_aserai_tavern, female_villager_in_aserai_tavern, warrior_in_aserai_tavern,
  female_warrior_in_aserai_tavern, child, female_child, facegen, female_facegen, map, female_map, map_with_banner, female_map_with_banner,
  villain, female_villain, lord, female_lord, seller, female_seller, weaponsmith, female_weaponsmith, villager_artisan, female_villager_artisan,
  villager_merchant, female_villager_merchant, villager_preacher, female_villager_preacher, villager_gangleader, female_villager_gangleader,
  villager_ruralnotable, female_villager_ruralnotable, gangleader_bodyguard, female_gangleader_bodyguard, merchant_notary, female_merchant_notary,
  barmaid, female_barmaid, tavern_keeper, female_tavern_keeper, musician, female_musician, dancer, female_dancer, beggar, female_beggar,
  guard, female_guard, unarmed_guard, female_unarmed_guard, villager_with_backpack, female_villager_with_backpack, villager_with_staff,
  female_villager_with_staff, villager_carry_on_shoulder, female_villager_carry_on_shoulder, villager_carry_axe, female_villager_carry_axe,
  villager_carry_right_side, female_villager_carry_right_side, villager_carry_front, female_villager_carry_front, villager_carry_right_hand,
  female_villager_carry_right_hand, villager_carry_right_arm, female_villager_carry_right_arm, villager_carry_over_head,
  female_villager_carry_over_head, poses.
- Прочее: `tor_action_types.xml` (новые `act_*`), `tor_movement_sets.xml`, `tor_full_movement_sets.xml`,
  `tor_monster_usage_sets.xml` + xslt, `tor_cloth_bodies.xml` (капсулы ткани на скелет: `<body name="dwarf_legs" owner_skeleton="dwarf_skeleton">` —
  **свой скелет требует своих cloth bodies**). Предметы брони скелет не указывают — просто меши, заскиненные под нужный скелет.
- Ваниль также умеет `SkeletonScales` (масштаб костей по предмету) — TOR не использует.
- Хаки для своих скелетов в TOR_Core.dll (Harmony): `ModifyHeadBoneScalingForCustomSkeletons`, `RaceFixPatches`, `PreserveRace`,
  `DisableNativeMissionFaceCacheForCustomRaces`, `BlockCrossRaceMissionFaceReuse`, `GetRandomTownsManActionSetAndMonster`, `FaceGenPatches`.

## 3. Как персонажи ссылаются на расу

Бойцы (`CORE\ModuleData\tor_troopdefinitions.xml`):
```xml
<NPCCharacter id="tor_dw_recruit" default_group="infantry" level="6" name="{=str_tor_dw_recruit}Dawi"
    occupation="Soldier" culture="Culture.sturgia" skill_template="SkillSet.tor_skills_dwarf_dawi"
    is_basic_troop="true" race="dwarf">
  <face>
    <face_key_template value="BodyProperty.dwarf_low_tier" />
    <hair_tags><hair_tag name="DwarfHair" /></hair_tags>
    <beard_tags><beard_tag name="DwarfBeardLow" /></beard_tags>
  </face>
  <upgrade_targets><upgrade_target id="NPCCharacter.tor_dw_militia" /></upgrade_targets>
  <Equipments>
    <EquipmentSet id="tor_dw_recruit_template" />
    <EquipmentSet id="tor_dw_recruit_template" civilian="true" />
  </Equipments>
</NPCCharacter>
```
- `race="<id>"` — единственная связь; без него = human. `is_female="true"`. Теги волос/бород должны совпадать со `style_tag` расы.
- Шаблоны тел (`tor_bodyproperties.xml`, `XmlName id="BodyProperties"`):
  ```xml
  <BodyProperty id="dwarf_low_tier">
    <BodyPropertiesMin version="4" age="25" weight="0.2793" build="0.1067" key="..." />
    <BodyPropertiesMax version="4" age="25" weight="0.5659" build="0.1437" key="..." />
  </BodyProperty>
  ```
  Ключ не содержит расу и декодируется по deform_keys расы → **ключи делать в редакторе лица с выбранной расой** (Ctrl+C).
- Лорды — фиксированное лицо `<face><BodyProperties version="4" age=".." weight=".." build=".." key=".."/></face>`, `is_hero="true"`, `race=`.
- `tor_heroes.xml` (`<Hero id faction text>`) — без расы, раса из NPCCharacter.
- Компаньоны-шаблоны: `occupation="Wanderer" is_template="true" race="dwarf"`, имя `{FIRSTNAME} the Thane`.
- Горожане/ремесленники: `tor_townspeople\tor_townspeople_dawi.xml` (`occupation="Blacksmith" race="dwarf"`).
- Культуры (`tor_cultures.xml` + xslt `<xsl:template match="Culture"/>` удаляет **все** ванильные) — TOR пере-создаёт их **с ванильными id**
  (sturgia = дварфы, vlandia = Бретония, battania = эльфы, khuzait = Сильвания), чтобы не падали жёстко прописанные ссылки.
  У культуры нет атрибута расы — связь через NPCCharacter (basic_troop, villager, townsman, blacksmith, …).

## 4. Регистрация в SubModule.xml

- CORE зависит от Native, SandBoxCore, Sandbox, StoryMode, TOR_Armory, TOR_Environment; `TOR_Core.dll`, `TOR_Core.SubModule`.
- XmlNode: NPCCharacters (`tor_lords` только CustomGame; `tor_troopdefinitions`; папки `tor_townspeople`, `tor_npccharacters`),
  BodyProperties (+EditorGame), EquipmentRosters, SPCultures, Heroes, Kingdoms, Factions, SkillSets, partyTemplates, Settlements,
  GameText (`tor_string_overrides`, `tor_strings`, `tor_voiced_strings`), Religions (свой тип из DLL), Concepts, BannerIcons.
- **`path` может быть папкой** — грузятся все XML в ней.
- **`X.xslt` рядом с `X.xml`** применяется к уже слитому XML этого типа до слияния файла мода — так удаляют/заменяют ванильные записи.
- ARM без DLL: Items (папка tor_items), CraftingPieces, CraftingTemplates, Monsters, WeaponDescriptions; остальное через project.mbproj.

## 5. Собственные XML-типы (грузит TOR_Core.dll)

Из `ModuleData/tor_custom_xmls/` по имени файла, корни в стиле XmlSerializer (`ArrayOf...`):
- `tor_extendeditemproperties.xml` — `ExtendedItemObjectProperties ItemStringId=".." RaceLock=".."` (**ограничение предметов по расе**, трейты, описания).
- `tor_extendedunitproperties.xml` — `CharacterExtendedInfo id="<npc>"`: Abilities, Attributes, Resistances, DamageProportions.
- `tor_cc_options.xml` (создание персонажа), `tor_specialization_options.xml` (`RaceId="vampire"` — смена расы игрока),
  `tor_abilitytemplates.xml`, `tor_statuseffects.xml`, `tor_triggeredeffects.xml`, `tor_itemtraits.xml`, `tor_animation_triggers.xml`, `tor_config.xml`.
- Хелперы: `LoadXmlWithOverride`, `GetMergedXmlForManaged`. Голоса: `tor_voice_definitions.xml`
  (`<voice_definition name="dwarf_male_01" sound_and_collision_info_class="human"><voice type="Grunt" path="dwarf_male_01_grunt" face_anim="grunt"/>`).
- C#-идентификаторы по расам: `CanCharacterUseItemBasedOnRace`, `AddTooltipForRaceLock`, `CanPlayerHireBasedOnRace`, `ApplyRaceChangeImmediate`,
  `EnableFreeRaceSelection`, `RaceSelector`, `_humanCompatibleRaces`, `FaceGenHelper`, `CharacterCreationFaceGeneratorStage`.
  UI: `CORE\GUI\Prefabs\FaceGen\FaceGenBody.xml` — виджет выбора расы (в ванильном FaceGen он есть, но скрыт).
- **В ванили нет ограничения предметов по расе** — нужен DLL + Harmony. `culture=` у предмета влияет только на магазины/лут.

## 6. Локализация

- Везде `{=id}Английский текст` с **читаемыми id** (`{=str_tor_dw_recruit}Dawi`).
- Строки для кода — GameText в `tor_strings.xml`; варианты через `id.variation`: `tor_race_name.dwarf`.
- `tor_string_overrides.xml` переопределяет ванильные строки с условиями-тегами (`<tags><tag tag_name="IsDwarfTag"/></tags>`, теги из DLL).
- Перевод — отдельный мод: `ModuleData\Languages\RU\language_data.xml`
  (`<LanguageData id="Русский" ... text_processor="TaleWorlds.Localization.TextProcessor.LanguageProcessors.RussianTextProcessor"><LanguageFile xml_path="RU/..."/>`),
  файлы `<base xml_name=".."><tags><tag language="Русский"/></tags><strings><string id=".." text=".."/>`.

## Чеклист для расы пони

1. (Опционально) модуль ассетов без DLL (skins, monsters, action sets, items, AssetPackages) + модуль контента (персонажи, культуры, строки, DLL).
2. `project.mbproj`: `type="skin"`, `action_set`, при необходимости `action_type`, `voice_definitions`, `module_sound`.
3. `pony_skins.xml`: не трогать `human` (или удалять через xslt); добавить `<race id="pony">` с 10 skin-блоками, скопированными с ванильного человека;
   заменить body/shoulders/legs/hands/face меши; `skeleton="human_skeleton"`; подобрать `min_scale`, `bone_scales`;
   те же deform_key id + морфы в голове; гривы как hair_meshes со `style_tag` `PonyMane`; палитры шерсти/гривы/глаз; голоса.
4. `pony_monsters.xml`: `pony`, `pony_child`, `pony_settlement`, `_slow`, `_fast` от human.
5. `pony_action_sets.xml`: `as_pony_<suffix>` для всех 85 суффиксов с `base_set="as_human_<suffix>"`; при своём скелете + `skeleton=`, анимации, cloth bodies, фиксы головы/кэша лиц.
6. Голоса: voice_definitions + module_sounds + `<voice_type>` в skin.
7. BodyProperties-шаблоны, ключи из редактора лица с выбранной расой пони (нужен выбор расы в FaceGen — DLL).
8. NPCCharacter: `race="pony" is_female=..`, `face_key_template`, `hair_tags`.
9. Культуры: переиспользовать ванильные id или заменять через xslt.
10. Ограничение брони по расе — DLL + Harmony (как `RaceLock`).
11. Расы только добавлять в конец (совместимость сохранений).
12. Локализация: читаемые `{=pony_xxx}`, отдельные `Languages\<LANG>`.
