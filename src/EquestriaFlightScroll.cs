using System;
using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using SandBox.GameComponents;
using SandBox.View.Map.Visuals;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.CampaignSystem.ViewModelCollection;
using TaleWorlds.CampaignSystem.ViewModelCollection.Inventory;
using TaleWorlds.CampaignSystem.Roster;
using TaleWorlds.Localization;
using TaleWorlds.Core;
using TaleWorlds.Engine;
using TaleWorlds.Library;
using TaleWorlds.MountAndBlade;
using TaleWorlds.ObjectSystem;
using TaleWorlds.MountAndBlade.View;
using TaleWorlds.MountAndBlade.View.Tableaus.Thumbnails;

namespace EquestriaMod
{
    // Свиток полёта (tools/make_items.py: eq_flight_scroll_50, примерочная — src/EquestriaFlightTest.cs)
    // — замена ездовым коням: зверю на звере ездить нелепо. Предмет занимает слот коня (Type="Horse"
    // в XML — этого хватает редактору снаряжения, декомпиляцией проверено: Equipment.IsItemFitsToSlot
    // смотрит только на ItemType), но персонаж должен драться и двигаться как пеший.
    //
    // ГЛАВНОЕ РЕШЕНИЕ (05.10.2026, после долгого перебора): у предмета НЕТ <ItemComponent><Horse/>.
    // Раньше он был (свой монстр eq_flight_mount, патчи IsRideable/GetFormationClass и т.д.) —
    // убрали, когда декомпиляцией нашли, что звук копыт, класс построения (кавалерия) и сама поза
    // верховой езды в бою читаются движком по самому наличию HorseComponent в снаряжении, В ОБХОД
    // реального Agent.MountAgent/IsMounted — четыре независимых места так делали, и патчить каждое
    // по отдельности оказалось бесконечной игрой в прятки (поза "в седле с поводьями" не поддавалась
    // вообще ничему — ни заморозке каналов анимации, ни классу построения). Без компонента все эти
    // системы просто не срабатывают сами по себе — предмет остаётся HasHorseComponent=false, и это
    // единственный способ оказался надёжным.
    //
    // Что ещё остаётся патчить:
    //  - ItemThumbnailCache.AddItem — иконка предмета в инвентаре падает на NullReferenceException,
    //    когда ItemComponent==null, а код ожидает HorseComponent (decompile подтвердил).
    //  - SandboxAgentStatCalculateModel.UpdateAgentStats — +50% скорости, завязано на StringId
    //    предмета в SpawnEquipment, не на компоненте.
    // IsRideable/AddMountMesh патчи оставлены как страховка (дёшево, не мешают) на случай, если
    // где-то ещё остался путь, который их всё же достанет — но по декомпиляции они теперь не
    // должны срабатывать вовсе.
    //
    // ПОЗА ПОЛЁТА — свой клип anim_eq_flight_pose на канале 0 (act_eq_flight_pose, см.
    // Module/ModuleData/action_types.xml и частичный as_human_warrior в pony_action_sets.xml).
    // Клип задаёт руки (разведены) и ноги (согнуты назад и накрест); остальные кости — rest.
    // Ноги видны (скрытие меша eq_<раса>_legs и снятие слота Leg убраны 10.10.2026 по просьбе
    // пользователя), под ногами — вихрь из листьев и пыли (prefab eq_flight_vortex).
    //
    // ИСТОРИЯ "разворота на 180°" (решено 10.10.2026, см. equestria-flight-scroll.md): любой клип,
    // собранный в Blender на modding_resources/human_skeleton.fbx, в игре разворачивал торс на
    // 180° при правильной голове (или наоборот — в зависимости от осей экспорта). Причина
    // измерена, не угадана (tools/solve_bone_axes.py по дампу equestria.dump_bones): редактор
    // берёт parent-relative повороты костей из FBX ДОСЛОВНО, без смены базиса, а rest-поза
    // скелета в движке НЕ совпадает с PreRotation того FBX (шея 180°, позвоночник ~120°, бедро
    // 154°, ключицы 91°). Поэтому клип теперь собирается НЕ в Blender-арматуре, а напрямую на
    // rest движка: tools/make_flight_pose_engine.py пишет в FBX абсолютные локальные повороты
    // rest_движка × дельта (tools/engine_rest_human_skeleton.txt — тот самый дамп).
    //
    // Левитацию пробовали сделать сдвигом визуала вверх (GlobalFrame.origin.z += N) — движок
    // смешивает позу с высотой таза над землёй, и расхождение ломало позу и прятало оружие даже на
    // 15 см (см. обсуждение 05.10.2026). Подъём на 30 см держится без артефактов — частицы
    // пыли/вихря под ногами добавлены сверху как визуальный акцент.
    public class EquestriaFlightScroll : MissionBehavior
    {
        private const string ItemId = "eq_flight_scroll_50";
        // Три свитка (10.10.2026): id → множитель скорости (tools/make_items.py, те же id).
        private static readonly Dictionary<string, float> Scrolls = new Dictionary<string, float>
        {
            { "eq_flight_scroll_50", 1.5f },
            { "eq_flight_scroll_40", 1.4f },
            { "eq_flight_scroll_30", 1.3f },
        };

        internal static bool IsScroll(ItemObject item) => item != null && Scrolls.ContainsKey(item.StringId);

        private static float SpeedOf(ItemObject item)
        {
            float m;
            return item != null && Scrolls.TryGetValue(item.StringId, out m) ? m : 1f;
        }
        // Свой вихрь-торнадо — prefab Module/Prefabs/eq_flight_fx.xml: ванильные эффекты по GUID
        // с переопределёнными эмиттерами (inline-определение эффекта в prefab в бою не находится).
        // Живёт на ОТДЕЛЬНОЙ сущности, которую ставим на землю под агентом каждый тик, — частица,
        // прицепленная к сущности самого агента (CreateParticleSystemAttachedToEntity), не
        // рендерится вовсе (проверено 10.10.2026 даже с ванильным psys_game_campfire; то же
        // наблюдение у мода Bannerlord-Twitch). Работает с 10.10.2026.
        private const string VortexPrefab = "eq_flight_vortex";
        // Оптимизация вихря (10.10.2026: при 100 на 100 летунов с вихрем у каждого FPS падал на дно —
        // 200 сущностей × 5 эмиттеров). Вихрь получают только летуны не дальше VortexMaxDistance от
        // камеры и не больше VortexMaxCount ближайших; список пересматривается раз в
        // VortexUpdatePeriod секунд, лишние вихри удаляются, вошедшие в радиус — создаются.
        private const bool VortexEnabled = true;
        private const float VortexMaxDistance = 35f;        // метров от камеры
        private const int VortexMaxCount = 24;              // одновременно живых вихрей
        private const float VortexUpdatePeriod = 0.25f;     // секунд между пересмотрами списка
        private float _vortexNextUpdate;
        private const float LiftHeight = 0.3f;              // игровых метров — подъём визуала над землёй

        public override MissionBehaviorType BehaviorType => MissionBehaviorType.Other;

        private readonly Dictionary<Agent, GameEntity> _vortex = new Dictionary<Agent, GameEntity>();
        private sealed class SwayState { public float Phase; public float Progress; }
        private readonly Dictionary<Agent, SwayState> _sway = new Dictionary<Agent, SwayState>();
        private const float SwayPeriod = 1.2f;              // секунд на одно качание рук при ходьбе
        private const float SwayPeriodIdle = 2.5f;          // то же стоя
        private const float SwayAmplitudeIdle = 0.4f;       // доля размаха стоя

        // Поза "держит поток" (08.10.2026, 6-я попытка со своим клипом, после сброса ног в бою —
        // см. класс-комментарий выше и память equestria-flight-scroll.md). act_eq_flight_pose
        // зарегистрирован в Module/ModuleData/action_types.xml (id=soln_action_types) и привязан
        // к anim_eq_flight_pose частичным блоком as_human_warrior в pony_action_sets.xml
        // (tools/make_flight_pose.py, tools/make_race_action_sets.py). ActionIndexCache.Create
        // резолвит индекс лениво — на момент статической инициализации класса движок ещё не
        // загрузил action_types.xml.
        private static ActionIndexCache? _flightPoseAction;
        private static ActionIndexCache FlightPoseAction =>
            (_flightPoseAction ?? (_flightPoseAction = ActionIndexCache.Create("act_eq_flight_pose"))).Value;

        private static bool _campaignUiPatched;

        // Патчи UI кампании ставятся из SubModule.OnGameStart, а не из ApplyLate: Harmony при
        // установке патча запускает статический конструктор CampaignUIHelper, тот читает
        // GameTexts, которых в главном меню ещё нет → TypeInitializationException, и мастер
        // создания персонажа падал (10.10.2026).
        public static void ApplyCampaignUi(Harmony harmony)
        {
            if (_campaignUiPatched || harmony == null)
            {
                return;
            }
            _campaignUiPatched = true;
            // Инвентарь/рынок (10.10.2026, свитки стали товаром): три места в UI кампании читают
            // HorseComponent у любого Type=Horse без проверки —
            //  - CampaignUIHelper.GetItemObjectTypeSortIndex (сортировка по типу, падал рынок);
            //  - SPInventoryVM.IsItemEquipmentPossible / AfterTransfer — упряжь рядом со свитком в слоте коня.
            var sortIndex = AccessTools.Method(typeof(CampaignUIHelper), "GetItemObjectTypeSortIndex");
            var equipPossible = AccessTools.Method(typeof(SPInventoryVM), "IsItemEquipmentPossible");
            var afterTransfer = AccessTools.Method(typeof(SPInventoryVM), "AfterTransfer");
            if (sortIndex == null || equipPossible == null || afterTransfer == null)
            {
                EquestriaCrashLog.Log("свиток полёта: методы инвентаря НЕ НАЙДЕНЫ — патчи UI не поставлены");
            }
            else
            {
                harmony.Patch(sortIndex, prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeItemTypeSortIndex)));
                harmony.Patch(equipPossible, prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeIsItemEquipmentPossible)));
                harmony.Patch(afterTransfer, prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeAfterTransfer)));
            }
            // Подсказка при наведении на повозку сравнивает её с НАДЕТЫМ свитком (тот же слот):
            // ItemMenuVM.SetHorseComponentTooltip берёт HorseComponent свитка (null) и отдаёт его в
            // AddHorseItemFlags → NRE (10.10.2026). Пустой компонент — флагов нет.
            // …и дальше по SetHorseComponentTooltip сравнение со свитком считает заряд/скорость
            // коня (EquipmentElement.GetModifiedMountCharge → NRE). Если сравниваемый предмет —
            // свиток, сравнение на время подсказки выключаем целиком.
            var horseTooltip = AccessTools.Method(typeof(ItemMenuVM), "SetHorseComponentTooltip");
            if (horseTooltip == null)
            {
                EquestriaCrashLog.Log("свиток полёта: ItemMenuVM.SetHorseComponentTooltip НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(horseTooltip, prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeSetHorseComponentTooltip)));
            }
            // Подсказка самого свитка: у него нет компонентов, ванильная подсказка пуста —
            // дописываем строку «Скорость полёта: +N%» (просьба пользователя 10.10.2026).
            var refreshTooltips = AccessTools.Method(typeof(ItemMenuVM), "RefreshItemTooltips");
            if (refreshTooltips == null)
            {
                EquestriaCrashLog.Log("свиток полёта: ItemMenuVM.RefreshItemTooltips НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(refreshTooltips, postfix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(AfterRefreshItemTooltips)));
            }
            var horseFlags = AccessTools.Method(typeof(ItemMenuVM), "AddHorseItemFlags");
            if (horseFlags == null)
            {
                EquestriaCrashLog.Log("свиток полёта: ItemMenuVM.AddHorseItemFlags НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(horseFlags, prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeAddHorseItemFlags)));
            }
        }

        public static void Apply(Harmony harmony)
        {
            var isRideable = AccessTools.PropertyGetter(typeof(HorseComponent), "IsRideable");
            if (isRideable == null)
            {
                EquestriaCrashLog.Log("свиток полёта: HorseComponent.IsRideable НЕ НАЙДЕН — патч не поставлен");
                return;
            }
            harmony.Patch(isRideable, postfix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(AfterIsRideable)));
            // IsRideable=false не трогает иконку отряда на карте: она строит мешик коня любому,
            // у кого в слоте коня хоть что-то лежит, в обход этой проверки — и падает с
            // NullReferenceException в SetHorseColors, когда меш пустой (замечено в игре 05.10.2026).
            // Глушим сам метод постройки визуала коня для нашего предмета — отдельно и раньше.
            var addMountMesh = AccessTools.Method(typeof(MountVisualCreator), "AddMountMesh");
            if (addMountMesh == null)
            {
                EquestriaCrashLog.Log("свиток полёта: MountVisualCreator.AddMountMesh НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(addMountMesh, prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeAddMountMesh)));
            }
            // Третье место, где в обход и IsRideable, и AddMountMesh строится меш коня: иконка
            // предмета в инвентаре (ItemThumbnailCache.AddItem) — та же NullReferenceException на
            // пустом меше (замечено в игре 05.10.2026, краш при открытии инвентаря со свитком).
            var addItem = AccessTools.Method(typeof(ItemThumbnailCache), "AddItem");
            if (addItem == null)
            {
                EquestriaCrashLog.Log("свиток полёта: ItemThumbnailCache.AddItem НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(addItem, prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeAddItem)));
            }
            // Четвёртое место (10.10.2026, когда свиток получила вся конница): портрет войска/героя
            // (CharacterThumbnailCache → CharacterSpawner.SpawnMount) берёт item.HorseComponent.Monster
            // без проверки — NullReferenceException при первой же отрисовке карточки Wonderbolt'а.
            var spawnMount = AccessTools.Method(typeof(TaleWorlds.MountAndBlade.View.Scripts.CharacterSpawner), "SpawnMount");
            if (spawnMount == null)
            {
                EquestriaCrashLog.Log("свиток полёта: CharacterSpawner.SpawnMount НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(spawnMount, prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeSpawnMount)));
            }
            // Пятое место (10.10.2026, рынок города): карточка предмета по пути OnCreateTexture →
            // CreateItemBaseEntity → GetItemPoseAndCamera берёт ((HorseComponent)item.ItemComponent)
            // .Monster.MonsterUsage для любого Type=Horse — у свитка компонента нет → NRE. Патч
            // AddItem этот путь не покрывает. Подменяем свиток обычным товаром только для расчёта
            // позы/камеры (меш в карточке всё равно пустой).
            var poseAndCamera = AccessTools.Method(typeof(ItemThumbnailCache), "GetItemPoseAndCamera");
            if (poseAndCamera == null)
            {
                EquestriaCrashLog.Log("свиток полёта: ItemThumbnailCache.GetItemPoseAndCamera НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(poseAndCamera,
                    prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeGetItemPoseAndCamera)),
                    postfix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(AfterGetItemPoseAndCamera)));
            }
            // Шестое место (10.10.2026, энциклопедия войск): CharacterTableau для бывшей конницы
            // выбирает «конную» стойку (StanceTypes 2/4), а визуал коня (_mountVisuals) создаётся только
            // при HorseComponent → AdjustCharacterForStanceIndex падает на null. Свитку — пешая стойка 0.
            var stance = AccessTools.Method(typeof(TaleWorlds.MountAndBlade.View.Tableaus.CharacterTableau), "SetStanceIndex");
            if (stance == null)
            {
                EquestriaCrashLog.Log("свиток полёта: CharacterTableau.SetStanceIndex НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(stance, prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeSetStanceIndex)));
            }
            // …и поза полёта в этой же таблице (энциклопедия/инвентарь): постфикс тика ставит на канал 0
            // наш act_eq_flight_pose, пока в слоте коня свиток (просьба пользователя 10.10.2026).
            var tableauTick = AccessTools.Method(typeof(TaleWorlds.MountAndBlade.View.Tableaus.CharacterTableau), "OnTick");
            if (tableauTick == null)
            {
                EquestriaCrashLog.Log("свиток полёта: CharacterTableau.OnTick НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(tableauTick, postfix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(AfterTableauTick)));
            }
            // +50% скорости: SandboxAgentStatCalculateModel.UpdateAgentStats — единственная реализация
            // модели для одиночной кампании (проверено декомпиляцией), её же читает тактика ИИ, так
            // что бойцы со свитком сами побегут быстрее, а не только игрок. Патчим именно
            // MaxSpeedMultiplier/CombatMaxSpeedMultiplier — то, что вписывает в них броня/навыки,
            // а не абсолютный предел скорости (Agent.SetMaximumSpeedLimit — другое, это сброс при
            // спешивании, не тактическая оценка скорости).
            var updateStats = AccessTools.Method(typeof(SandboxAgentStatCalculateModel), "UpdateAgentStats");
            if (updateStats == null)
            {
                EquestriaCrashLog.Log("свиток полёта: SandboxAgentStatCalculateModel.UpdateAgentStats НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(updateStats, postfix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(AfterUpdateAgentStats)));
            }
            // Пятое место, завязанное на HorseComponent (вылезло именно из-за того, что мы его
            // убрали у предмета, 05.10.2026) — иконка отряда на карте считает анимацию боевой
            // стойки лидера/коня (MobilePartyVisual.GetPartyBattleAnimation) и падает на
            // NullReferenceException, ожидая HorseComponent там, где его больше нет. Глушим для
            // партии, чей лидер несёт наш свиток — отдаём безопасные "нет анимации".
            var getPartyBattleAnimation = AccessTools.Method(typeof(MobilePartyVisual), "GetPartyBattleAnimation");
            if (getPartyBattleAnimation == null)
            {
                EquestriaCrashLog.Log("свиток полёта: MobilePartyVisual.GetPartyBattleAnimation НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(getPartyBattleAnimation, prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeGetPartyBattleAnimation)));
            }
            // Шестое место (та самая первопричина пятого): BasicCharacterObject.HasMount() честно
            // проверяет только Equipment[Horse].Item != null (decompile подтвердил), а не
            // HasHorseComponent — думает, что конь есть, раз предмет лежит в слоте. От этого
            // AddCharacterToPartyIcon без проверки лезет в Item.HorseComponent.Monster и падает.
            // Патчим сам источник: если HasMount() честно скажет "нет", не придётся гоняться за
            // каждым местом, которое ему верит.
            var hasMount = AccessTools.Method(typeof(BasicCharacterObject), "HasMount");
            if (hasMount == null)
            {
                EquestriaCrashLog.Log("свиток полёта: BasicCharacterObject.HasMount НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(hasMount, postfix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(AfterHasMount)));
            }
            // Седьмое место: MountCreationKey.GetRandomMountKey — зовётся при спавне подкрепления в
            // бою (Mission.SpawnTroop(..., spawnWithHorse: true, ...)), без проверки лезет в
            // mountItem.HorseComponent.HorseMaterialNames. Этот патч не завязан на StringId нашего
            // предмета: он вообще не должен звать HorseComponent у предмета, где его нет, —
            // безопасная защита на любой будущий подобный предмет, не только на свиток.
            var getRandomMountKey = AccessTools.Method(typeof(MountCreationKey), "GetRandomMountKey");
            if (getRandomMountKey == null)
            {
                EquestriaCrashLog.Log("свиток полёта: MountCreationKey.GetRandomMountKey НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(getRandomMountKey, prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeGetRandomMountKey)));
            }
            // Восьмое место: Mission.BuildAgent (приватный) — после сборки агента, посреди метода,
            // не глядя на HasHorseComponent лезет в equipmentElement.Item.HorseComponent.BodyLength,
            // если слот коня просто не пуст (decompile: IL_0051 get_HorseComponent -> IL_0056
            // get_BodyLength, 05.10.2026, краш при спавне подкрепления в бою). Метод большой и
            // приватный — обычный prefix/postfix не вырезать логику изнутри, поэтому на время
            // ОРИГИНАЛЬНОГО вызова просто опустошаем слот 10 в SpawnEquipment (prefix), а сразу
            // после возвращаем предмет обратно (postfix). Проверено декомпиляцией: Agent.Build()
            // перед этим блоком слот не трогает, а EquipItemsFromSpawnEquipment после — читает уже
            // собранный agent.Equipment, а не SpawnEquipment, и вообще не смотрит на слот коня —
            // опустошение на этот вызов никак не влияет, предмет всё равно наденется как обычно.
            var buildAgent = AccessTools.Method(typeof(Mission), "BuildAgent", new[] { typeof(Agent), typeof(AgentBuildData) });
            if (buildAgent == null)
            {
                EquestriaCrashLog.Log("свиток полёта: Mission.BuildAgent НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(buildAgent,
                    prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeBuildAgent)),
                    postfix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(AfterBuildAgent)));
            }
            EquestriaCrashLog.Log("свиток полёта: патчи IsRideable/AddMountMesh/AddItem/SpawnMount/UpdateAgentStats/GetPartyBattleAnimation/HasMount/GetRandomMountKey/BuildAgent поставлены");
        }

        private static bool BeforeBuildAgent(Agent agent, out EquipmentElement __state)
        {
            __state = default(EquipmentElement);
            Equipment equipment = agent?.SpawnEquipment;
            if (equipment == null)
            {
                return true;
            }
            EquipmentElement element = equipment[EquipmentIndex.ArmorItemEndSlot];
            if (!element.IsEmpty && IsScroll(element.Item))
            {
                __state = element;
                equipment[EquipmentIndex.ArmorItemEndSlot] = default(EquipmentElement);
            }
            return true;
        }

        private static void AfterBuildAgent(Agent agent, EquipmentElement __state)
        {
            if (!__state.IsEmpty)
            {
                agent.SpawnEquipment[EquipmentIndex.ArmorItemEndSlot] = __state;
            }
        }

        private static bool BeforeGetRandomMountKey(ItemObject mountItem, ref MountCreationKey __result)
        {
            if (mountItem != null && mountItem.HasHorseComponent)
            {
                return true;
            }
            __result = new MountCreationKey(0, 0, 0, 0, 0, 0);
            return false;
        }

        private static void AfterHasMount(BasicCharacterObject __instance, ref bool __result)
        {
            if (__result && IsScroll(__instance?.Equipment?[EquipmentIndex.Horse].Item))
            {
                __result = false;
            }
        }

        private static bool BeforeGetPartyBattleAnimation(PartyBase party, out ActionIndexCache leaderAction, out ActionIndexCache mountAction)
        {
            leaderAction = ActionIndexCache.act_none;
            mountAction = ActionIndexCache.act_none;
            Hero leader = party?.MobileParty?.LeaderHero;
            if (leader == null || !IsScroll(leader.BattleEquipment[EquipmentIndex.Horse].Item))
            {
                return true;
            }
            return false;
        }

        private static void AfterUpdateAgentStats(Agent agent, AgentDrivenProperties agentDrivenProperties)
        {
            if (agent == null || !HasScroll(agent))
            {
                return;
            }
            float speed = SpeedOf(agent.SpawnEquipment[EquipmentIndex.Horse].Item);
            agentDrivenProperties.MaxSpeedMultiplier *= speed;
            agentDrivenProperties.CombatMaxSpeedMultiplier *= speed;
        }

        private static bool BeforeAddItem(ItemObject item, Scene scene, ref GameEntity __result)
        {
            // Со своим мешем (lib_scroll_*, 10.10.2026) свиток рисуется обычным путём; пустая сущность
            // — только если меша нет (с ним и падал AddItem 05.10.2026).
            if (!IsScroll(item) || !string.IsNullOrEmpty(item.MultiMeshName))
            {
                return true;
            }
            __result = GameEntity.CreateEmpty(scene);
            return false;
        }

        private static bool BeforeAddMountMesh(ItemObject mountItem, ref MountVisualCreationOutput __result)
        {
            if (!IsScroll(mountItem))
            {
                return true;
            }
            __result = new MountVisualCreationOutput(null, null, null, null);
            return false;
        }

        // Превью свитка/повозки (10.10.2026): для Type=Horse движок берёт «конскую» камеру (у свитка
        // при этом NRE на HorseComponent, у повозки меш телеги не влезает в кадр), а для товаров
        // подбирает кадр по габаритам меша. На время расчёта позы объявляем предмет товаром:
        // ItemObject.Type — публичное поле. Повозка = ванильный вьючный с мешем bd_cart_* (equestria_items.xslt).
        // internal: тем же признаком повозку отличает EquestriaFlightArmy — «вьючный» у ванили ещё и
        // ездовая лошадь (saddle_horse) и старая кляча (old_horse), а повозки только три — с мешем телеги
        internal static bool IsCart(ItemObject item) =>
            item != null && item.Type == ItemObject.ItemTypeEnum.Horse && (item.MultiMeshName ?? "").StartsWith("bd_cart", StringComparison.OrdinalIgnoreCase);

        private static void BeforeGetItemPoseAndCamera(ItemObject item, out bool __state)
        {
            __state = item != null && item.Type == ItemObject.ItemTypeEnum.Horse && (IsScroll(item) || IsCart(item));
            if (__state)
            {
                item.Type = ItemObject.ItemTypeEnum.Goods;
            }
        }

        private static void AfterGetItemPoseAndCamera(ItemObject item, bool __state)
        {
            if (__state && item != null)
            {
                item.Type = ItemObject.ItemTypeEnum.Horse;
            }
        }

        private static ItemObject _sortStandIn;

        // Сортировка по типу: свиток считаем вьючным зверем (тот же индекс, что у sumpter_horse).
        private static void BeforeItemTypeSortIndex(ref ItemObject item)
        {
            if (!IsScroll(item))
            {
                return;
            }
            if (_sortStandIn == null)
            {
                _sortStandIn = MBObjectManager.Instance.GetObject<ItemObject>("sumpter_horse");
            }
            if (_sortStandIn != null)
            {
                item = _sortStandIn;
            }
        }

        private static bool BeforeAddHorseItemFlags(HorseComponent horse) => horse != null;

        private static void AfterRefreshItemTooltips(ItemMenuVM __instance, object item)
        {
            ItemObject target = ItemOf(item);
            float speed;
            if (target == null || !Scrolls.TryGetValue(target.StringId, out speed))
            {
                return;
            }
            string label = new TextObject("{=eq_flight_speed}Flight speed").ToString();
            string value = "+" + Math.Round((speed - 1f) * 100f) + "%";
            // HintViewModel живёт в TaleWorlds.Core.ViewModelCollection (нет в ссылках) — метод ищем по имени.
            System.Reflection.MethodInfo create = AccessTools.Method(typeof(ItemMenuVM), "CreateProperty");
            create?.Invoke(__instance, new object[] { __instance.TargetItemProperties, label, value, 0, null });
        }

        private static ItemObject ItemOf(object itemVm)
        {
            if (itemVm == null)
            {
                return null;
            }
            // ItemVM.ItemRosterElement — публичное ПОЛЕ (не свойство), проверено декомпиляцией.
            object element = Traverse.Create(itemVm).Field("ItemRosterElement").GetValue();
            return element is ItemRosterElement roster ? roster.EquipmentElement.Item : null;
        }

        // ItemVM живёт в TaleWorlds.Core.ViewModelCollection (не в ссылках проекта) — через Traverse.
        private static void BeforeSetHorseComponentTooltip(ItemMenuVM __instance)
        {
            Traverse field = Traverse.Create(__instance).Field("_comparedItem");
            object compared = field.GetValue();
            ItemObject comparedItem = ItemOf(compared);
            if (IsScroll(comparedItem))
            {
                field.SetValue(null);
                __instance.IsComparing = false;
            }
        }

        private static Equipment ActiveEquipment(SPInventoryVM vm)
        {
            try
            {
                return (Equipment)AccessTools.Property(typeof(SPInventoryVM), "ActiveEquipment")?.GetValue(vm);
            }
            catch
            {
                return null;
            }
        }

        private static bool MountIsScroll(SPInventoryVM vm)
        {
            Equipment equipment = ActiveEquipment(vm);
            return equipment != null && IsScroll(equipment[EquipmentIndex.ArmorItemEndSlot].Item);
        }

        // Упряжь на свиток не надеть: иначе IsItemEquipmentPossible лезет в HorseComponent свитка.
        private static bool BeforeIsItemEquipmentPossible(SPInventoryVM __instance, SPItemVM itemVM, ref bool __result)
        {
            ItemObject item = itemVM?.ItemRosterElement.EquipmentElement.Item;
            if (item != null && item.Type == ItemObject.ItemTypeEnum.HorseHarness && MountIsScroll(__instance))
            {
                __result = false;
                return false;
            }
            return true;
        }

        // После переноса: если в слоте коня свиток, а упряжь ещё надета — снимаем её сами, до того
        // как AfterTransfer сравнит семейства зверей через HorseComponent свитка.
        private static void BeforeAfterTransfer(SPInventoryVM __instance)
        {
            Equipment equipment = ActiveEquipment(__instance);
            if (equipment == null || equipment[EquipmentIndex.HorseHarness].IsEmpty || !IsScroll(equipment[EquipmentIndex.ArmorItemEndSlot].Item))
            {
                return;
            }
            SPItemVM harness = __instance.CharacterMountArmorSlot;
            if (harness != null)
            {
                AccessTools.Method(typeof(SPInventoryVM), "UnequipEquipment")?.Invoke(__instance, new object[] { harness });
            }
        }

        private static void BeforeSetStanceIndex(TaleWorlds.MountAndBlade.View.Tableaus.CharacterTableau __instance, ref int index)
        {
            if (index != 2 && index != 4)
            {
                return;
            }
            Equipment equipment = Traverse.Create(__instance).Field("_equipment").GetValue() as Equipment;
            if (equipment != null && IsScroll(equipment[EquipmentIndex.Horse].Item))
            {
                index = 0;
            }
        }

        private static void AfterTableauTick(TaleWorlds.MountAndBlade.View.Tableaus.CharacterTableau __instance)
        {
            Traverse tr = Traverse.Create(__instance);
            Equipment equipment = tr.Field("_equipment").GetValue() as Equipment;
            if (equipment == null || !IsScroll(equipment[EquipmentIndex.Horse].Item))
            {
                return;
            }
            var visuals = tr.Field("_agentVisuals").GetValue() as TaleWorlds.MountAndBlade.View.AgentVisuals;
            Skeleton skeleton = visuals?.GetEntity()?.Skeleton;
            if (skeleton == null)
            {
                return;
            }
            if (MBSkeletonExtensions.GetActionAtChannel(skeleton, 0) != FlightPoseAction)
            {
                visuals.SetAction(FlightPoseAction);
            }
        }

        private static bool BeforeSpawnMount(TaleWorlds.MountAndBlade.View.Scripts.CharacterSpawner __instance, CharacterCode characterCode)
        {
            ItemObject mount = characterCode?.CalculateEquipment()[EquipmentIndex.Horse].Item;
            if (mount == null || mount.HasHorseComponent)
            {
                return true;
            }
            __instance.HasMount = false;
            return false;
        }

        private static void AfterIsRideable(HorseComponent __instance, ref bool __result)
        {
            if (__result && IsScroll(__instance?.Item))
            {
                __result = false;
            }
        }

        internal static bool HasScrollPublic(Agent agent) => HasScroll(agent);

        private static bool HasScroll(Agent agent)
        {
            return IsScroll(agent.SpawnEquipment[EquipmentIndex.Horse].Item);
        }

        public override void OnAgentRemoved(Agent affectedAgent, Agent affectorAgent, AgentState agentState, KillingBlow blow)
        {
            base.OnAgentRemoved(affectedAgent, affectorAgent, agentState, blow);
            RemoveVortex(affectedAgent);
        }

        protected override void OnEndMission()
        {
            base.OnEndMission();
            foreach (Agent agent in new List<Agent>(_vortex.Keys))
            {
                RemoveVortex(agent);
            }
        }

        // Кому положен вихрь: летуны в радиусе VortexMaxDistance от камеры, ближайшие VortexMaxCount.
        private void UpdateVortexSet()
        {
            Vec3 eye = Mission.Current.Scene.LastFinalRenderCameraPosition;
            if (eye.LengthSquared < 0.01f && Agent.Main != null)
            {
                eye = Agent.Main.Position;
            }
            float maxDist2 = VortexMaxDistance * VortexMaxDistance;
            var candidates = new List<KeyValuePair<float, Agent>>();
            foreach (Agent agent in Mission.Current.Agents)
            {
                if (agent == null || agent.IsMount || !agent.IsActive() || !HasScroll(agent))
                {
                    continue;
                }
                float d2 = agent.Position.DistanceSquared(eye);
                if (d2 <= maxDist2)
                {
                    candidates.Add(new KeyValuePair<float, Agent>(d2, agent));
                }
            }
            candidates.Sort((a, b) => a.Key.CompareTo(b.Key));
            var wanted = new HashSet<Agent>();
            for (int i = 0; i < candidates.Count && i < VortexMaxCount; i++)
            {
                wanted.Add(candidates[i].Value);
            }
            foreach (Agent agent in new List<Agent>(_vortex.Keys))
            {
                if (!wanted.Contains(agent))
                {
                    RemoveVortex(agent);
                }
            }
            foreach (Agent agent in wanted)
            {
                if (_vortex.ContainsKey(agent))
                {
                    continue;
                }
                GameEntity vortex = GameEntity.Instantiate(Mission.Current.Scene, VortexPrefab, true);
                if (vortex == null)
                {
                    EquestriaCrashLog.Warn("свиток полёта: нет заготовки " + VortexPrefab);
                    return;
                }
                MatrixFrame ground = new MatrixFrame(Mat3.Identity, agent.Position);
                vortex.SetGlobalFrame(in ground);
                _vortex[agent] = vortex;
            }
        }

        private void RemoveVortex(Agent agent)
        {
            GameEntity vortex;
            if (agent != null && _vortex.TryGetValue(agent, out vortex))
            {
                _vortex.Remove(agent);
                _sway.Remove(agent);
                vortex?.Remove(0);
            }
        }

        // Дамп скелета игрока в eq_exceptions.log: rest-фреймы всех костей (источник правды для
        // tools/make_flight_pose_engine.py — см. tools/engine_rest_human_skeleton.txt) плюс
        // текущие фреймы и channel0, чтобы сверять, как движок понял клип (tools/solve_bone_axes.py).
        // Консоль: equestria.dump_bones (в бою, игрок должен стоять в проверяемой позе).
        [CommandLineFunctionality.CommandLineArgumentFunction("dump_bones", "equestria")]
        public static string DumpBonesCommand(List<string> args)
        {
            if (Agent.Main == null || Mission.Current == null)
            {
                return "Нужен бой с игроком.";
            }
            DumpBones(Agent.Main);
            return "Дамп костей записан в eq_exceptions.log.";
        }

        // Поворот, переводящий rest в now (now = R * rest): ось и угол, в системе сущности.
        private static string Delta(MatrixFrame rest, MatrixFrame now)
        {
            Mat3 r = rest.rotation;
            Mat3 n = now.rotation;
            // R = n * rest^-1; rest ортонормирована, обратная = транспонированная
            Mat3 rt = r;
            rt.Transpose();
            Mat3 d = n;
            d = Mat3Mul(n, rt);
            float trace = d.s.x + d.f.y + d.u.z;
            float cos = (trace - 1f) / 2f;
            cos = cos > 1f ? 1f : (cos < -1f ? -1f : cos);
            float angle = (float)System.Math.Acos(cos) * 180f / (float)System.Math.PI;
            Vec3 axis = new Vec3(d.f.z - d.u.y, d.u.x - d.s.z, d.s.y - d.f.x);
            if (axis.Length > 1e-4f)
            {
                axis.Normalize();
            }
            return $"угол={angle:0.0}° ось={F(axis)}";
        }

        // a * b для столбцовых матриц (s,f,u — столбцы X,Y,Z)
        private static Mat3 Mat3Mul(Mat3 a, Mat3 b)
        {
            return new Mat3(
                a.TransformToParent(b.s),
                a.TransformToParent(b.f),
                a.TransformToParent(b.u));
        }

        private static string F(Vec3 v)
        {
            return $"({v.x:0.000},{v.y:0.000},{v.z:0.000})";
        }

        private static string F(MatrixFrame m)
        {
            return $"o={F(m.origin)} f={F(m.rotation.f)} s={F(m.rotation.s)} u={F(m.rotation.u)}";
        }

        private static void DumpBones(Agent agent)
        {
            Skeleton skeleton = agent.AgentVisuals?.GetSkeleton();
            if (skeleton == null)
            {
                return;
            }
            sbyte count = skeleton.GetBoneCount();
            var sb = new System.Text.StringBuilder();
            sb.AppendLine($"свиток полёта: ДАМП КОСТЕЙ ({count}) agent.Frame {F(agent.Frame)}");
            for (sbyte i = 0; i < count; i++)
            {
                try
                {
                    sb.AppendLine($"  [{i}] {skeleton.GetBoneName(i)} parent={skeleton.GetParentBoneIndex(i)}");
                    sb.AppendLine($"      localRest    {F(skeleton.GetBoneLocalRestFrame(i, false))}");
                    sb.AppendLine($"      entitialRest {F(skeleton.GetBoneEntitialRestFrame(i, false))}");
                    MatrixFrame rest = skeleton.GetBoneEntitialRestFrame(i, false);
                    MatrixFrame now = skeleton.GetBoneEntitialFrameWithIndex(i);
                    MatrixFrame ch0 = skeleton.GetBoneEntitialFrameAtChannel(0, i);
                    sb.AppendLine($"      entitialNow  {F(now)}");
                    sb.AppendLine($"      channel0     {F(ch0)}");
                    sb.AppendLine($"      now/rest  {Delta(rest, now)}   ch0/rest  {Delta(rest, ch0)}");
                }
                catch (System.Exception ex)
                {
                    sb.AppendLine($"  [{i}] ошибка: {ex.Message}");
                }
            }
            EquestriaCrashLog.Log(sb.ToString());
        }

        public override void OnMissionTick(float dt)
        {
            base.OnMissionTick(dt);
            if (VortexEnabled && Mission.Current.CurrentTime >= _vortexNextUpdate)
            {
                _vortexNextUpdate = Mission.Current.CurrentTime + VortexUpdatePeriod;
                EquestriaCrashLog.Try("свиток полёта: пересмотр вихрей", UpdateVortexSet);
            }
            foreach (Agent agent in Mission.Current.Agents)
            {
                if (agent == null || agent.IsMount || !agent.IsActive() || !HasScroll(agent))
                {
                    continue;
                }
                try
                {
                    // Поза на канале 0 — каждый тик: обычная локомоция перезаписывает канал 0 сама,
                    // разовая установка слетала через долю секунды. actionSpeed 0: клип сам не идёт,
                    // его прогресс задаём ниже. ИИ — с ignorePriority (его локомоция держит канал 0
                    // с большим приоритетом); игроку не даём — рвал переход в атаку (act_stand_1).
                    // У самого действия НЕТ type (action_types.xml): действия типа actt_idle ИИ
                    // сбрасывал с канала каждый кадр при движении строем — выглядело как ходьба.
                    if (agent.GetCurrentAction(0) != FlightPoseAction)
                    {
                        agent.SetActionChannel(0, FlightPoseAction, !agent.IsPlayerControlled, 0UL, 0f, 0f);
                    }
                    // Покачивание рук при ходьбе: кадр 1 клипа — базовая поза, кадр 250 — руки чуть
                    // выше и вперёд (tools/make_flight_pose_engine.py, ARM_SWAY_*). Пока агент идёт,
                    // гоняем прогресс 0..1 по косинусу; стоя — медленнее и с меньшим размахом.
                    SwayState sway;
                    if (!_sway.TryGetValue(agent, out sway))
                    {
                        sway = new SwayState();
                        _sway[agent] = sway;
                    }
                    // До первой атаки у ИИ оружие в ножнах, и локомоция "без оружия" идёт шагом поверх
                    // позы; с оружием в руках (после атаки, у игрока всегда) поза держится (скриншот
                    // 10.10.2026). Летуну оружие в руки сразу.
                    // Стоя руки тоже дышат, но медленнее и слабее.
                    bool moving = agent.MovementVelocity.LengthSquared > 0.05f;
                    float period = moving ? SwayPeriod : SwayPeriodIdle;
                    float amplitude = moving ? 1f : SwayAmplitudeIdle;
                    sway.Phase += dt * (2f * (float)System.Math.PI / period);
                    sway.Progress = amplitude * (0.5f - 0.5f * (float)System.Math.Cos(sway.Phase));
                    // Скорость/прогресс — ТОЛЬКО когда на канале наша поза. Иначе у ИИ замораживались
                    // его собственные действия на канале 0 (удар, блок, разворот) — бойцы дёргались
                    // и "вставали" (замечено в бою 100 на 100, 10.10.2026).
                    if (agent.GetCurrentAction(0) == FlightPoseAction)
                    {
                        agent.SetCurrentActionSpeed(0, 0f);
                        agent.SetCurrentActionProgress(0, sway.Progress);
                    }
                    // Вихрь — отдельная сущность на земле под агентом (Agent.Position — физические
                    // ноги, без подъёма визуала), как снаряд в EquestriaSpellMission. Кому он положен,
                    // решает UpdateVortexSet (радиус от камеры + потолок), здесь только двигаем.
                    GameEntity vortex;
                    if (_vortex.TryGetValue(agent, out vortex) && vortex != null)
                    {
                        MatrixFrame ground = new MatrixFrame(Mat3.Identity, agent.Position);
                        vortex.SetGlobalFrame(in ground);
                    }
                    // Подъём визуала над землёй: пробуем снова (05.10.2026) теперь, когда у
                    // предмета убран HasHorseComponent и поза честно пешая — старый баг (согнутые
                    // ноги, пропадающий меч уже на +15 см) по декомпиляции был похож на конфликт
                    // именно с позой "наездника": отдельной системы, которая держит ноги у земли,
                    // у людей в отличие от коня/верблюда/кабана в monsters.xml вообще нет (там это
                    // настраивается индивидуально per-monster, и у человека полей для этого нет).
                    // Начинаем с малого (30 см): если артефакт всё же вернётся — значит, причина
                    // была другая, и подъём придётся снова убрать.
                    var visuals = agent.AgentVisuals;
                    if (visuals != null)
                    {
                        MatrixFrame frame = visuals.GetGlobalFrame();
                        frame.origin.z += LiftHeight;
                        visuals.SetFrame(ref frame);
                    }
                }
                catch
                {
                    // Один кадр анимации/визуала не стоит ронять бой — пропускаем агента и едем дальше.
                }
            }
        }

    }
}
