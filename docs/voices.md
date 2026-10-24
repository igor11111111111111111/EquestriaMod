# Голоса: как они устроены в игре и что с ними сделано у нас

Заметки по всему, что касается голоса персонажей: боевые крики, реплики в разговорах, отклики на
приказы. Собрано по ходу работы 25.09.2026, дополнять по мере новых правок.

## 1. Три разные системы, которые легко перепутать

| Что звучит | Откуда берётся | Кто выбирает | Наш код |
| --- | --- | --- | --- |
| Крики боя: удар, боль, смерть, клич | `voice_definitions.xml` + звуковые события FMOD | движок, по полу и звуковому классу тела | `src/EquestriaBattleVoice.cs` |
| Озвучка реплик диалога | банки FMOD игры, по `voice=` персонажа и `voices.xml` | `VoiceOverModel` | — (ванильную не трогаем) |
| Наши свои клипы: приветствия, отклики на приказы | файлы в `Module\Sounds\<папка>` | наш код | `src/EquestriaGreetings.cs`, `src/EquestriaOrderVoice.cs` |

Главное: **боевые крики и озвучка диалогов никак не связаны**. Персонаж с `voice="curt"` в
`spnpccharacters.xml` получает эту озвучку только в разговорах; в бою он кряхтит тем голосом,
который движок выбрал по `voice_definitions.xml`.

## 2. Боевые крики

### Файл `Modules/Native/ModuleData/voice_definitions.xml`

Состоит из двух частей.

**Объявления типов** (`voice_type_declarations`) — 62 штуки, это перечень поводов подать голос:

```
Grunt, Jump, Yell, Pain, Death, Stun, Fear, Climb, Focus, Debacle, Victory, HorseStop, HorseRally,
Drown, Infantry, Cavalry, Archers, HorseArchers, Everyone, Mixed, Move, Follow, Charge, Advance,
FallBack, Stop, Retreat, Mount, Dismount, FireAtWill, HoldFire, PickSpears, PickDefault, FaceEnemy,
FaceDirection, UseSiegeWeapon, UseLadders, AttackGate, CommandDelegate, CommandUndelegate, FormLine,
FormShieldWall, FormLoose, FormCircle, FormSquare, FormSkein, FormColumn, FormScatter, BoardAtWill,
AvoidBoarding, MpHelp, MpSpot, MpThanks, MpSorry, MpAffirmative, MpNegative, MpRegroup, MpDefend,
MpAttack, Idle, Neigh, Collide
```

**Сами определения** (`voice_definition`) — 24 штуки в ванили:

| Звуковой класс | Определения |
| --- | --- |
| `human` | `male_01`…`male_08`, `female_01`…`female_05` — всего 13 |
| остальные | `horse_01`…`horse_04`, `camel_01`, `cow_01`, `hog_01`, `mule_01`, `sheep_01`, `goose_sound`, `dog_01` |

Ни один другой модуль игры их не дополняет — проверено по всем `Modules/*/ModuleData`.

Устройство одного определения:

```xml
<voice_definition name="female_01" sound_and_collision_info_class="human" only_for_npcs="true"
                  min_pitch_multiplier="0.89" max_pitch_multiplier="1.09">
  <voice type="Grunt" path="event:/voice/combat/female/01/grunt" face_anim="grunt" />
  <voice type="Pain"  path="event:/voice/combat/female/01/pain"  face_anim="hit" />
  ...
</voice_definition>
```

- `path` — событие FMOD из банков игры, а не файл на диске. Своё событие без сборки банка не
  добавить, поэтому «новый голос» из наших wav-файлов этим путём не сделать (см. раздел 5).
- `face_anim` — мимика под крик, берётся из анимаций лица.
- `min/max_pitch_multiplier` — в каких пределах движок дёргает высоту; конкретное значение задаётся
  вторым параметром `SetVoiceDefinitionIndex`.

### Кто выбирает голос агенту

Выбор делает движок при постройке агента: по **полу тела** и по **звуковому классу** его монстра
(`sound_and_collision_info_class` в `*_monsters.xml`). У всех наших рас класс ванильный — `human`
(см. `Module/ModuleData/pony_monsters.xml`), поэтому им доступны те же 13 человеческих голосов.

Из управляемого кода есть ровно одна ручка:

```csharp
agent.AgentVisuals.SetVoiceDefinitionIndex(int voiceDefinitionIndex, float voicePitch);
```

Образец применения — как игра назначает голос лошадям:
`TaleWorlds.MountAndBlade.View` → `MountVisualCreator.SetVoiceDefinition`.

Полезные методы:

| Метод | Что даёт |
| --- | --- |
| `Agent.GetSoundAndCollisionInfoClassName()` | звуковой класс агента (`human`, `horse`, …) |
| `SkinVoiceManager.GetVoiceDefinitionCountWithMonsterSoundAndCollisionInfoClassName(class)` | сколько определений у класса |
| `SkinVoiceManager.GetVoiceDefinitionListWithMonsterSoundAndCollisionInfoClassName(class, int[])` | их индексы |
| `Agent.GetAgentVoiceDefinition()` | имя текущего определения агента (удобно для проверки) |
| `Agent.MakeVoice(SkinVoiceManager.VoiceType.Yell, ...)` | заставить агента подать голос вручную |
| `MBAgentVisuals.SetVoiceDefinitionIndex(index, pitch)` | подменить голос |

**Индексы даются числами, без имён.** Какой из них женский, по числу не понять, поэтому имена
читаем сами из `voice_definitions.xml` и сопоставляем по порядку: порядок в файле и порядок в
ответе движка совпадают. Проверка на расхождение обязательна — см. ниже.

## 3. Что сделано у нас

`src/EquestriaBattleVoice.cs` — `MissionLogic`, подключён в `SubModule.OnMissionBehaviorInitialize`.
На каждом рождении бойца (`OnAgentBuild`):

1. пропускает женщин, коней и расы из списка-исключения;
2. берёт индексы женских определений звукового класса агента (кэш на класс);
3. ставит одно из них через `SetVoiceDefinitionIndex`.

**Кто получает женский голос:** все народы — пони, чейнджлинги, драконы, яки, олени.
**Кто остаётся со своим:** грифоны и гиппогрифы (`KeepOwnVoice` в том же файле).

Решения, которые стоит помнить:

- **Список именно на исключение, а не на включение.** Новая раса получит женский голос сама собой,
  и о ней не придётся вспоминать; чтобы оставить расе ванильный выбор по полу, её id добавляют
  в `KeepOwnVoice`.
- **Опечатка в id не проходит молча.** `FaceGen.GetRaceOrDefault` отдаёт 0 и для человека, и когда
  расы нет вовсе, поэтому нули в список исключений не попадают, а в лог уходит предупреждение —
  иначе опечатка тихо оставила бы без женского голоса половину войска.
- **Голос и высота выбираются по имени агента**, а не случайно: один и тот же боец звучит одинаково
  от боя к бою, а по отряду голоса разные.
- **Проверка длин списков.** Если число определений класса в XML не совпадёт с тем, что знает
  движок (например, после патча игры), голоса не трогаются вовсе и в лог уходит предупреждение.
  Лучше мужской крик, чем случайный визг коровы: чужой индекс — это чужой голос из того же списка.
- **Женщин не трогаем**: у них женский голос и так.

## 4. Грабли

- **Нельзя просто сделать агента женским.** `AgentBuildData.IsFemale` управляет не только голосом,
  но и телом: сменится скелет, меши и посадка брони. Только `SetVoiceDefinitionIndex`.
- **Патчи на `Agent` ставить поздно.** Harmony-патчи классов боя (`Agent`, `AgentVisuals`,
  `MBSoundEvent`) в этом моде применяются из `EquestriaPatches.ApplyLate` — в главном меню. Если
  поставить их при загрузке модуля, статическая инициализация уйдёт раньше загрузки анимаций и все
  пони в окнах лягут набок. То же правило действует и для будущих правок голоса.
- **`voice=` у персонажа к бою отношения не имеет** — это озвучка диалогов.
- **Свои звуки в бою — только через FMOD.** `path` в определении это событие банка. Наши приветствия
  и отклики на приказы играют через программируемое событие `event:/Extra/voiceover`, которым игра
  озвучивает диалоги (см. `EquestriaOrderVoice`); для боевых криков такого обхода пока нет.

## 5. Что можно сделать дальше

- **Вернуть расе мужской голос.** Добавить её id в `KeepOwnVoice` в `EquestriaBattleVoice`.
- **Свои определения голоса на расу** (грифоний клёкот, драконий рык). Порядок такой: добавить
  `voice_definition` в свой `ModuleData/voice_definitions.xml` со своим `sound_and_collision_info_class`,
  прописать этот класс монстру расы — и собрать банк FMOD со своими событиями `event:/...`.
  Банк — самая дорогая часть; без него определение будет молчать.
- **Разные голоса по ролям** (командиры кричат ниже, новобранцы выше) — уже возможно без новых
  банков: достаточно раздавать разные `female_XX` и высоту по войску.
- **Проверка в игре.** Удобнее всего слушать бой с одной расой: `equestria.merc_camp` наберёт войск,
  а `campaign.add_gold_to_hero` даст на них денег. В логе мода (`Module/eq_exceptions.log`) при
  первом бою появятся строки «женский голос в бою: со своим голосом остаются расы griffon,
  hippogriff» и «женский голос в бою: класс human, женских определений 5 из 13».
