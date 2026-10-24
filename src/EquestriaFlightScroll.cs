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
    // Flight scroll (tools/make_items.py: eq_flight_scroll_50, fitting room: src/EquestriaFlightTest.cs):
    // a replacement for riding horses, since a beast riding a beast is absurd. The item takes the horse slot (Type="Horse"
    // in XML; that is enough for the equipment editor, checked by decompilation: Equipment.IsItemFitsToSlot
    // looks only at ItemType), but the character must fight and move like one on foot.
    //
    // THE MAIN DECISION (05.10.2026, after a long search): the item has NO <ItemComponent><Horse/>.
    // It used to have one (our own monster eq_flight_mount, IsRideable/GetFormationClass patches, etc.);
    // it was removed when decompilation showed that the hoof sounds, the formation class (cavalry) and the riding
    // pose itself in battle are read by the engine from the mere presence of a HorseComponent in the equipment, BYPASSING
    // the real Agent.MountAgent/IsMounted: four independent places did this, and patching each
    // separately turned into an endless game of hide-and-seek (the "in the saddle with reins" pose did not yield
    // to anything at all: neither freezing animation channels nor the formation class). Without the component all these
    // systems simply do not fire by themselves: the item stays HasHorseComponent=false, and this
    // was the only way that proved reliable.
    //
    // What still has to be patched:
    //  - ItemThumbnailCache.AddItem: the item icon in the inventory crashes with a NullReferenceException
    //    when ItemComponent==null, while the code expects a HorseComponent (decompile confirmed).
    //  - SandboxAgentStatCalculateModel.UpdateAgentStats: +50% speed, tied to the StringId
    //    of the item in SpawnEquipment, not to the component.
    // The IsRideable/AddMountMesh patches are kept as insurance (cheap, harmless) in case
    // some other path still reaches them, but according to the decompilation they should now
    // never fire at all.
    //
    // FLIGHT POSE: our own clip anim_eq_flight_pose on channel 0 (act_eq_flight_pose, see
    // Module/ModuleData/action_types.xml and the partial as_human_warrior in pony_action_sets.xml).
    // The clip sets the arms (spread) and legs (bent back and crossed); the other bones are rest.
    // The legs are visible (hiding the eq_<race>_legs mesh and clearing the Leg slot were removed 10.10.2026 at the
    // user's request); under the legs is a vortex of leaves and dust (prefab eq_flight_vortex).
    //
    // HISTORY of the "180° turn" (solved 10.10.2026, see equestria-flight-scroll.md): any clip
    // built in Blender on modding_resources/human_skeleton.fbx turned the torso by 180° in game
    // with a correct head (or the other way round, depending on the export axes). The cause was
    // measured, not guessed (tools/solve_bone_axes.py on the equestria.dump_bones dump): the editor
    // takes the bones' parent-relative rotations from the FBX VERBATIM, without a basis change, while the engine
    // skeleton's rest pose does NOT match that FBX's PreRotation (neck 180°, spine ~120°, thigh
    // 154°, clavicles 91°). So the clip is now built NOT on a Blender armature but directly on
    // the engine rest: tools/make_flight_pose_engine.py writes absolute local rotations into the FBX:
    // engine_rest × delta (tools/engine_rest_human_skeleton.txt is that very dump).
    //
    // Levitation was tried by shifting the visual up (GlobalFrame.origin.z += N): the engine
    // blends the pose with the pelvis height above the ground, and the mismatch broke the pose and hid the weapon even at
    // 15 cm (see the discussion of 05.10.2026). A 30 cm lift holds without artefacts; the dust/vortex
    // particles under the legs are added on top as a visual accent.
    public class EquestriaFlightScroll : MissionBehavior
    {
        private const string ItemId = "eq_flight_scroll_50";
        // Three scrolls (10.10.2026): id → speed multiplier (tools/make_items.py, the same ids).
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
        // Our own tornado vortex, prefab Module/Prefabs/eq_flight_fx.xml: vanilla effects by GUID
        // with overridden emitters (an inline effect definition in the prefab is not found in battle).
        // It lives on a SEPARATE entity that we place on the ground under the agent every tick: a particle
        // attached to the agent's own entity (CreateParticleSystemAttachedToEntity) is not
        // rendered at all (checked 10.10.2026 even with the vanilla psys_game_campfire; the same
        // observation in the Bannerlord-Twitch mod). Works since 10.10.2026.
        private const string VortexPrefab = "eq_flight_vortex";
        // Vortex optimization (10.10.2026: at 100 vs 100 flyers with a vortex each, FPS dropped to the floor:
        // 200 entities × 5 emitters). Only flyers no further than VortexMaxDistance from the
        // camera get a vortex, and no more than the VortexMaxCount nearest; the list is revised every
        // VortexUpdatePeriod seconds, extra vortices are removed, those entering the radius are created.
        private const bool VortexEnabled = true;
        private const float VortexMaxDistance = 35f;        // metres from the camera
        private const int VortexMaxCount = 24;              // vortices alive at once
        private const float VortexUpdatePeriod = 0.25f;     // seconds between list revisions
        private float _vortexNextUpdate;
        private const float LiftHeight = 0.3f;              // game metres: lift of the visual above the ground

        public override MissionBehaviorType BehaviorType => MissionBehaviorType.Other;

        private readonly Dictionary<Agent, GameEntity> _vortex = new Dictionary<Agent, GameEntity>();
        private sealed class SwayState { public float Phase; public float Progress; }
        private readonly Dictionary<Agent, SwayState> _sway = new Dictionary<Agent, SwayState>();
        private const float SwayPeriod = 1.2f;              // seconds per arm swing while walking
        private const float SwayPeriodIdle = 2.5f;          // the same while standing
        private const float SwayAmplitudeIdle = 0.4f;       // share of the swing amplitude while standing

        // The "holding the flow" pose (08.10.2026, 6th attempt with our own clip, after the legs reset in battle;
        // see the class comment above and the equestria-flight-scroll.md memory). act_eq_flight_pose
        // is registered in Module/ModuleData/action_types.xml (id=soln_action_types) and bound
        // to anim_eq_flight_pose by a partial as_human_warrior block in pony_action_sets.xml
        // (tools/make_flight_pose.py, tools/make_race_action_sets.py). ActionIndexCache.Create
        // resolves the index lazily: at the time of the class's static initialization the engine has not yet
        // loaded action_types.xml.
        private static ActionIndexCache? _flightPoseAction;
        private static ActionIndexCache FlightPoseAction =>
            (_flightPoseAction ?? (_flightPoseAction = ActionIndexCache.Create("act_eq_flight_pose"))).Value;

        private static bool _campaignUiPatched;

        // The campaign UI patches are installed from SubModule.OnGameStart, not from ApplyLate: when Harmony
        // installs a patch it runs the static constructor of CampaignUIHelper, which reads
        // GameTexts, which do not exist yet in the main menu → TypeInitializationException, and the character
        // creation wizard crashed (10.10.2026).
        public static void ApplyCampaignUi(Harmony harmony)
        {
            if (_campaignUiPatched || harmony == null)
            {
                return;
            }
            _campaignUiPatched = true;
            // Inventory/market (10.10.2026, scrolls became goods): three places in the campaign UI read
            // the HorseComponent of any Type=Horse without a check:
            //  - CampaignUIHelper.GetItemObjectTypeSortIndex (sorting by type, the market crashed);
            //  - SPInventoryVM.IsItemEquipmentPossible / AfterTransfer: a harness next to the scroll in the horse slot.
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
            // The hover tooltip on a cart compares it with the EQUIPPED scroll (the same slot):
            // ItemMenuVM.SetHorseComponentTooltip takes the scroll's HorseComponent (null) and passes it to
            // AddHorseItemFlags → NRE (10.10.2026). An empty component means no flags.
            // …and further along SetHorseComponentTooltip the comparison with the scroll computes the horse's
            // charge/speed (EquipmentElement.GetModifiedMountCharge → NRE). If the compared item is
            // a scroll, the comparison is switched off entirely for the duration of the tooltip.
            var horseTooltip = AccessTools.Method(typeof(ItemMenuVM), "SetHorseComponentTooltip");
            if (horseTooltip == null)
            {
                EquestriaCrashLog.Log("свиток полёта: ItemMenuVM.SetHorseComponentTooltip НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(horseTooltip, prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeSetHorseComponentTooltip)));
            }
            // The scroll's own tooltip: it has no components, the vanilla tooltip is empty;
            // we append the line "Flight speed; at the user's request 10.10.2026".
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
            // IsRideable=false does not affect the party icon on the map: it builds a horse mesh for anyone
            // who has anything at all in the horse slot, bypassing this check, and crashes with a
            // NullReferenceException in SetHorseColors when the mesh is empty (noticed in game 05.10.2026).
            // We mute the horse visual building method itself for our item, separately and earlier.
            var addMountMesh = AccessTools.Method(typeof(MountVisualCreator), "AddMountMesh");
            if (addMountMesh == null)
            {
                EquestriaCrashLog.Log("свиток полёта: MountVisualCreator.AddMountMesh НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(addMountMesh, prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeAddMountMesh)));
            }
            // A third place where the horse mesh is built bypassing both IsRideable and AddMountMesh: the item
            // icon in the inventory (ItemThumbnailCache.AddItem), the same NullReferenceException on
            // an empty mesh (noticed in game 05.10.2026, crash when opening the inventory with the scroll).
            var addItem = AccessTools.Method(typeof(ItemThumbnailCache), "AddItem");
            if (addItem == null)
            {
                EquestriaCrashLog.Log("свиток полёта: ItemThumbnailCache.AddItem НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(addItem, prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeAddItem)));
            }
            // A fourth place (10.10.2026, when all the cavalry got the scroll): the troop/hero portrait
            // (CharacterThumbnailCache → CharacterSpawner.SpawnMount) takes item.HorseComponent.Monster
            // without a check: a NullReferenceException on the very first render of a Wonderbolt's card.
            var spawnMount = AccessTools.Method(typeof(TaleWorlds.MountAndBlade.View.Scripts.CharacterSpawner), "SpawnMount");
            if (spawnMount == null)
            {
                EquestriaCrashLog.Log("свиток полёта: CharacterSpawner.SpawnMount НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(spawnMount, prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeSpawnMount)));
            }
            // A fifth place (10.10.2026, town market): the item card along the path OnCreateTexture →
            // CreateItemBaseEntity → GetItemPoseAndCamera takes ((HorseComponent)item.ItemComponent)
            // .Monster.MonsterUsage for any Type=Horse; the scroll has no component → NRE. The AddItem
            // patch does not cover this path. We substitute the scroll with ordinary goods only for computing
            // the pose/camera (the mesh in the card is empty anyway).
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
            // A sixth place (10.10.2026, troop encyclopedia): CharacterTableau for former cavalry
            // picks a "mounted" stance (StanceTypes 2/4), while the horse visual (_mountVisuals) is created only
            // with a HorseComponent → AdjustCharacterForStanceIndex crashes on null. The scroll gets foot stance 0.
            var stance = AccessTools.Method(typeof(TaleWorlds.MountAndBlade.View.Tableaus.CharacterTableau), "SetStanceIndex");
            if (stance == null)
            {
                EquestriaCrashLog.Log("свиток полёта: CharacterTableau.SetStanceIndex НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(stance, prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeSetStanceIndex)));
            }
            // …and the flight pose in this same tableau (encyclopedia/inventory): a tick postfix puts on channel 0
            // our act_eq_flight_pose while a scroll is in the horse slot (at the user's request 10.10.2026).
            var tableauTick = AccessTools.Method(typeof(TaleWorlds.MountAndBlade.View.Tableaus.CharacterTableau), "OnTick");
            if (tableauTick == null)
            {
                EquestriaCrashLog.Log("свиток полёта: CharacterTableau.OnTick НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(tableauTick, postfix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(AfterTableauTick)));
            }
            // +50% speed: SandboxAgentStatCalculateModel.UpdateAgentStats is the only implementation
            // of the model for the single-player campaign (checked by decompilation), and the AI tactics read it too, so
            // soldiers with the scroll will run faster themselves, not only the player. We patch precisely
            // MaxSpeedMultiplier/CombatMaxSpeedMultiplier, what armour/skills write into them,
            // not the absolute speed limit (Agent.SetMaximumSpeedLimit is something else, a reset on
            // dismounting, not a tactical speed estimate).
            var updateStats = AccessTools.Method(typeof(SandboxAgentStatCalculateModel), "UpdateAgentStats");
            if (updateStats == null)
            {
                EquestriaCrashLog.Log("свиток полёта: SandboxAgentStatCalculateModel.UpdateAgentStats НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(updateStats, postfix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(AfterUpdateAgentStats)));
            }
            // A fifth place tied to HorseComponent (it surfaced precisely because we
            // removed it from the item, 05.10.2026): the party icon on the map computes the battle
            // stance animation of the leader/horse (MobilePartyVisual.GetPartyBattleAnimation) and crashes with a
            // NullReferenceException, expecting a HorseComponent where there is none any more. We mute it for
            // a party whose leader carries our scroll, returning a safe "no animation".
            var getPartyBattleAnimation = AccessTools.Method(typeof(MobilePartyVisual), "GetPartyBattleAnimation");
            if (getPartyBattleAnimation == null)
            {
                EquestriaCrashLog.Log("свиток полёта: MobilePartyVisual.GetPartyBattleAnimation НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(getPartyBattleAnimation, prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeGetPartyBattleAnimation)));
            }
            // A sixth place (the very root cause of the fifth): BasicCharacterObject.HasMount() honestly
            // checks only Equipment[Horse].Item != null (decompile confirmed), not
            // HasHorseComponent, so it thinks there is a horse because an item lies in the slot. Because of this
            // AddCharacterToPartyIcon reaches into Item.HorseComponent.Monster without a check and crashes.
            // We patch the source itself: if HasMount() honestly says "no", there is no need to chase
            // every place that trusts it.
            var hasMount = AccessTools.Method(typeof(BasicCharacterObject), "HasMount");
            if (hasMount == null)
            {
                EquestriaCrashLog.Log("свиток полёта: BasicCharacterObject.HasMount НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(hasMount, postfix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(AfterHasMount)));
            }
            // A seventh place: MountCreationKey.GetRandomMountKey, called when spawning reinforcements in
            // battle (Mission.SpawnTroop(..., spawnWithHorse: true, ...)), reaches without a check into
            // mountItem.HorseComponent.HorseMaterialNames. This patch is not tied to our item's StringId:
            // it should never call HorseComponent on an item that has none at all;
            // a safe guard for any similar future item, not only the scroll.
            var getRandomMountKey = AccessTools.Method(typeof(MountCreationKey), "GetRandomMountKey");
            if (getRandomMountKey == null)
            {
                EquestriaCrashLog.Log("свиток полёта: MountCreationKey.GetRandomMountKey НЕ НАЙДЕН — патч не поставлен");
            }
            else
            {
                harmony.Patch(getRandomMountKey, prefix: new HarmonyMethod(typeof(EquestriaFlightScroll), nameof(BeforeGetRandomMountKey)));
            }
            // An eighth place: Mission.BuildAgent (private): after building the agent, in the middle of the method,
            // without looking at HasHorseComponent it reaches into equipmentElement.Item.HorseComponent.BodyLength
            // if the horse slot is simply not empty (decompile: IL_0051 get_HorseComponent -> IL_0056
            // get_BodyLength, 05.10.2026, crash when spawning reinforcements in battle). The method is big and
            // private: an ordinary prefix/postfix cannot cut logic out from inside, so for the duration of the
            // ORIGINAL call we simply empty slot 10 in SpawnEquipment (prefix), and right
            // after we put the item back (postfix). Checked by decompilation: Agent.Build()
            // does not touch the slot before this block, and EquipItemsFromSpawnEquipment afterwards reads the already
            // built agent.Equipment, not SpawnEquipment, and does not look at the horse slot at all:
            // emptying for this call has no effect, the item is equipped as usual anyway.
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
            // With its own mesh (lib_scroll_*, 10.10.2026) the scroll is drawn the ordinary way; an empty entity
            // only if there is no mesh (that is what AddItem crashed with on 05.10.2026).
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

        // Scroll/cart preview (10.10.2026): for Type=Horse the engine takes the "horse" camera (with the scroll
        // this gives an NRE on HorseComponent, with the cart the wagon mesh does not fit in the frame), while for goods
        // it picks the frame by the mesh's bounding box. For the duration of the pose calculation we declare the item
        // goods: ItemObject.Type is a public field. Cart = a vanilla pack animal with a bd_cart_* mesh (equestria_items.xslt).
        // internal: EquestriaFlightArmy tells a cart apart by the same sign: in vanilla "pack animal" also covers
        // the riding horse (saddle_horse) and the old nag (old_horse), while there are only three carts, with a wagon mesh
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

        // Sorting by type: the scroll counts as a pack animal (the same index as sumpter_horse).
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
            // HintViewModel lives in TaleWorlds.Core.ViewModelCollection (not in the references): the method is found by name.
            System.Reflection.MethodInfo create = AccessTools.Method(typeof(ItemMenuVM), "CreateProperty");
            create?.Invoke(__instance, new object[] { __instance.TargetItemProperties, label, value, 0, null });
        }

        private static ItemObject ItemOf(object itemVm)
        {
            if (itemVm == null)
            {
                return null;
            }
            // ItemVM.ItemRosterElement is a public FIELD (not a property), checked by decompilation.
            object element = Traverse.Create(itemVm).Field("ItemRosterElement").GetValue();
            return element is ItemRosterElement roster ? roster.EquipmentElement.Item : null;
        }

        // ItemVM lives in TaleWorlds.Core.ViewModelCollection (not in the project references): via Traverse.
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

        // A harness cannot be put on a scroll: otherwise IsItemEquipmentPossible reaches into the scroll's HorseComponent.
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

        // After a transfer: if the horse slot holds a scroll while the harness is still equipped, we remove it ourselves, before
        // AfterTransfer compares the animal families through the scroll's HorseComponent.
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

        // Who gets a vortex: flyers within VortexMaxDistance of the camera, the VortexMaxCount nearest.
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

        // Dump of the player's skeleton to eq_exceptions.log: the rest frames of all bones (the source of truth for
        // tools/make_flight_pose_engine.py, see tools/engine_rest_human_skeleton.txt) plus
        // the current frames and channel0, to check how the engine understood the clip (tools/solve_bone_axes.py).
        // Console: equestria.dump_bones (in battle, the player must stand in the pose being checked).
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

        // The rotation that takes rest to now (now = R * rest): axis and angle, in entity space.
        private static string Delta(MatrixFrame rest, MatrixFrame now)
        {
            Mat3 r = rest.rotation;
            Mat3 n = now.rotation;
            // R = n * rest^-1; rest is orthonormal, the inverse = the transpose
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

        // a * b for column matrices (s,f,u are the columns X,Y,Z)
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
                    // Pose on channel 0 every tick: the ordinary locomotion overwrites channel 0 itself,
                    // a one-off setting fell off within a fraction of a second. actionSpeed 0: the clip does not run by itself,
                    // its progress is set below. For the AI, with ignorePriority (its locomotion holds channel 0
                    // with a higher priority); not for the player: it broke the transition into an attack (act_stand_1).
                    // The action itself has NO type (action_types.xml): actions of type actt_idle the AI
                    // reset from the channel every frame when moving in formation, which looked like walking.
                    if (agent.GetCurrentAction(0) != FlightPoseAction)
                    {
                        agent.SetActionChannel(0, FlightPoseAction, !agent.IsPlayerControlled, 0UL, 0f, 0f);
                    }
                    // Arm sway while walking: clip frame 1 is the base pose, frame 250 has the arms slightly
                    // higher and forward (tools/make_flight_pose_engine.py, ARM_SWAY_*). While the agent walks,
                    // we drive the progress 0..1 along a cosine; standing, slower and with a smaller amplitude.
                    SwayState sway;
                    if (!_sway.TryGetValue(agent, out sway))
                    {
                        sway = new SwayState();
                        _sway[agent] = sway;
                    }
                    // Before the first attack the AI's weapon is sheathed, and the "unarmed" locomotion walks on top of
                    // the pose; with a weapon in hand (after an attack, always for the player) the pose holds (screenshot
                    // 10.10.2026). The flyer gets a weapon in hand right away.
                    // Standing, the arms breathe too, but slower and weaker.
                    bool moving = agent.MovementVelocity.LengthSquared > 0.05f;
                    float period = moving ? SwayPeriod : SwayPeriodIdle;
                    float amplitude = moving ? 1f : SwayAmplitudeIdle;
                    sway.Phase += dt * (2f * (float)System.Math.PI / period);
                    sway.Progress = amplitude * (0.5f - 0.5f * (float)System.Math.Cos(sway.Phase));
                    // Speed/progress ONLY when our pose is on the channel. Otherwise the AI's own actions
                    // on channel 0 (strike, block, turn) froze, and the soldiers twitched
                    // and "stood up" (noticed in a 100 vs 100 battle, 10.10.2026).
                    if (agent.GetCurrentAction(0) == FlightPoseAction)
                    {
                        agent.SetCurrentActionSpeed(0, 0f);
                        agent.SetCurrentActionProgress(0, sway.Progress);
                    }
                    // The vortex is a separate entity on the ground under the agent (Agent.Position is the physical
                    // legs, without the visual lift), like a projectile in EquestriaSpellMission. Who gets it
                    // is decided by UpdateVortexSet (radius from the camera + cap); here we only move it.
                    GameEntity vortex;
                    if (_vortex.TryGetValue(agent, out vortex) && vortex != null)
                    {
                        MatrixFrame ground = new MatrixFrame(Mat3.Identity, agent.Position);
                        vortex.SetGlobalFrame(in ground);
                    }
                    // Lift of the visual above the ground: we try again (05.10.2026) now that the
                    // item has had HasHorseComponent removed and the pose is honestly on foot. The old bug (bent
                    // legs, the sword vanishing already at +15 cm) by the decompilation looked like a conflict
                    // specifically with the "rider" pose: a separate system that keeps the legs at the ground
                    // does not exist at all for humans, unlike the horse/camel/boar in monsters.xml (there it is
                    // configured individually per-monster, and the human has no fields for it).
                    // We start small (30 cm): if the artefact comes back after all, the cause
                    // was something else, and the lift will have to be removed again.
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
                    // One frame of animation/visual is not worth bringing down the battle: skip the agent and move on.
                }
            }
        }

    }
}
