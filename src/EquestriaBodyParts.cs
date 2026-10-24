﻿using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using HarmonyLib;
using TaleWorlds.CampaignSystem;
using TaleWorlds.Core;
using TaleWorlds.Engine;
using TaleWorlds.Library;
using TaleWorlds.MountAndBlade;

namespace EquestriaMod
{
    // The pony tail, changeling wings and deer tail are body parts, not equipment.
    //
    // The engine lets you neither add your own slot (EquipmentIndex is constants, 12 in total, five of them armour)
    // nor put two items into one slot: Equipment holds exactly one element per index. Keeping the
    // tail as a cape item is bad too: a worn cape pushes it out. And it cannot be baked into the body mesh:
    // a chest piece with covers_body hides the whole body, and without that flag every armour would
    // have to render the body as well, i.e. extra polygons in large battles.
    //
    // So the mesh is hung directly on the skeleton of the already assembled character (GameEntity.AddMultiMeshToSkeleton):
    // the slot stays free, the skinning is real (the tail sits on the pelvis and does not follow the head),
    // and nothing disappears under armour. No need to remove it on death: it is part of the body.
    //
    // Two places where a character is assembled: the mission (battle, town, conversation), here via OnAgentBuild,
    // and screens with portraits (inventory, party, barber), which have their own mechanism, CharacterTableau;
    // we hook it with a patch (see ApplyTableau).
    public class EquestriaBodyParts : MissionBehavior
    {
        public override MissionBehaviorType BehaviorType => MissionBehaviorType.Other;

        // race -> meshes that are always on the body (the griffon has two: wings and tail)
        private static readonly Dictionary<string, string[]> PartByRace = new Dictionary<string, string[]>
        {
            // New pony (tools/make_pony_model.py): horn, small wings and a long tail on the body.
            // Until its FBX is imported, the old Twilight tail is used here; see RaceParts.
            // Ears (07.10.2026, the user separated them from the mane in Blender) are a separate part, as
            // for the griffon/changeling/deer: painted with the COMMON body material (not in the
            // hair-override list of tools/pony_material.ps1, unlike the horn/tail/wings,
            // which on the pony are deliberately repainted with the mane material), hidden under any headgear
            // with the same trick as for the other races (see EarMeshByRace).
            { "pony", new[] { "eq_pony_tail", "eq_pony_wings", "eq_pony_horn", "eq_pony_ears" } },
            // Changeling (tools/make_changeling_model.py): two pairs of dragonfly wings as one
            // mesh and a tail on the pelvis. Previously there was only the wing mesh; the old model had no tail.
            // Horn and ears (04.10.2026, model rebuild): the horn existed as a separate mesh before too,
            // but was not mentioned here at all and hung in the .tpac without an owner; the ears are a new part, hidden
            // when a helmet is worn (see EarMeshByRace).
            { "changeling", new[] { "eq_changeling_wings", "eq_changeling_tail",
                "eq_changeling_horn", "eq_changeling_ears" } },
            // Deer doe (tools/make_deer_model.py): a short tail on the pelvis. The antlers (04.10.2026,
            // model rebuild) used to be a hairstyle (eq_deer_hair), now they are a separate part;
            // the real "hair" (a different mesh, the same hairstyle slot) and the ears are new; the ears are hidden under
            // a helmet (EarMeshByRace), the antlers are not, they are part of the body, as with the other races.
            // Four antler variants (10.10.2026): all are attached, only the chosen one is visible; see
            // DeerAntlers below (the number is taken from the hairstyle).
            { "deer", new[] { "eq_deer_tail", "eq_deer_horn", "eq_deer_horn_2", "eq_deer_horn_3",
                "eq_deer_horn_4", "eq_deer_ears" } },
            // Yak (tools/make_yak_model.py): the tail tip is a separate item on the pelvis bone. The horn is a
            // separate part (04.10.2026, the user separated it from the head in Blender, like the horn
            // of the pony/dragon); it used to be part of face_meta_mesh, is not mentioned in the race skin, and without
            // this line would hang in the .tpac without an owner.
            { "yak", new[] { "eq_yak_tail", "eq_yak_horn" } },
            // Dragon (tools/make_dragon.py): tail on the pelvis, wings on the upper spine.
            // We do not put them in the cape slot: a worn cape would push them out, and the wings are always needed.
            // The horn is a separate part (06.10.2026, the user separated it from the head in Blender,
            // like the horn of the pony/yak/deer); it is painted with the COMMON body material (eq_dragon_body), not
            // the hair one: unlike the pony, where the horn/tail/wings are deliberately repainted with the mane
            // material (see tools/pony_material.ps1), on the dragon only eq_dragon_hair gets the
            // hair material (tools/dragon_material.ps1), and eq_dragon_horn is a regular one, like
            // the body, by the general rule without an explicit override.
            { "dragon", new[] { "eq_dragon_tail", "eq_dragon_wings", "eq_dragon_horn" } },
            // Griffon (tools/make_griffon.py): a lion tail on the pelvis, wings on the upper spine.
            // Its wings grow from the arms, but we still do not put them in the cape slot: a cape would push them
            // out, and a griffon without wings is not a griffon. The ears are a separate part (04.10.2026,
            // the user separated them from the head in Blender); this model has no hair at all, so the ears are
            // the only thing we hide when a helmet is worn (see EarMeshByRace/HideEarsUnderHelmet).
            { "griffon", new[] { "eq_griffon_tail", "eq_griffon_wings", "eq_griffon_ear" } },
            // Hippogriff (tools/make_hippogriff.py): built like the griffon, wings from the arms,
            // a fan tail on the pelvis.
            { "hippogriff", new[] { "eq_hippogriff_tail", "eq_hippogriff_wings" } },
        };

        // Body parts also exist as items (equestria_items.xml, cape slot), for windows where there is no agent.
        // The race review (EquestriaRaceParty) needs to know their names so as not to hand out a tail instead of a cape.
        internal static bool IsBodyPart(string itemId)
        {
            return itemId != null && PartByRace.Values.Any(parts => parts.Contains(itemId));
        }

        private static Dictionary<int, string[]> _partByRaceId;

        private static Dictionary<int, string[]> RaceParts()
        {
            if (_partByRaceId == null)
            {
                _partByRaceId = new Dictionary<int, string[]>();
                foreach (var pair in PartByRace)
                {
                    int race = TaleWorlds.Core.FaceGen.GetRaceOrDefault(pair.Key);
                    // GetRaceOrDefault returns 0 (human) if there is no race; such a one is not confused with humans
                    if (race != 0)
                    {
                        _partByRaceId[race] = pair.Value;
                    }
                }
                // Until the new pony is imported in the editor, it has no eq_pony_* meshes, and
                // in the game it is still the old Twilight with her tail.
                int pony = TaleWorlds.Core.FaceGen.GetRaceOrDefault("pony");
                if (pony != 0 && MetaMesh.GetCopy("eq_pony_wings", true, false) == null)
                {
                    _partByRaceId[pony] = new[] { "eq_twilight_tail" };
                }
            }
            return _partByRaceId;
        }

        // Which screen is open now; needed only for the log, to see whether the body parts reached
        // the party and inventory windows.
        private static string Screen()
        {
            var state = TaleWorlds.Core.Game.Current?.GameStateManager?.ActiveState;
            return state == null ? "нет" : state.GetType().Name;
        }

        // Where in the character's mesh list we put our body part. The engine has its own slot list,
        // it cannot be extended (BodyMeshTypes is constants). We take Shoulderpiece: it is the cape slot,
        // usually empty on a pony, and if a cape is worn after all, the tail is replaced by the cape, as before.
        private const BodyMeshTypes Slot = BodyMeshTypes.Shoulderpiece;

        /// <summary>
        /// Hangs the race mesh on the character. Calling it again does no harm.
        /// </summary>
        /// <param name="visuals">The character's visuals (TaleWorlds.MountAndBlade.View.AgentVisuals).</param>
        /// <param name="cacheKey">
        /// The object by which the hairstyle colour is remembered between rebuilds (see LastHairLook). By
        /// default it is the visuals themselves, but in windows (see AfterTableauTick) CharacterTableau recreates them
        /// on every equipment change, while CharacterTableau itself is not recreated, so it is passed from there.
        /// </param>
        /// <param name="bodyCode">
        /// The character's appearance code (see HairLookByCode): the same cache, but it survives even a completely
        /// new window opened with a helmet already on the head.
        /// </param>
        // internal, not private: EquestriaHairStyleView calls it directly for the barber screen;
        // it has its own AgentVisuals (BodyGeneratorView._visualToShow), not via CharacterTableau,
        // and without a forced tick striped/solid would not switch until the equipment
        // changes (noticed 29.09.2026: the first click on "Striped" applied, apparently
        // coinciding with someone else's Refresh, and "Solid" after it never applied).
        // The overrides below are only for rank-and-file troops in battle (RandomizeCommonTroopLook): they have no
        // window of their own where the player presses buttons, so stripes/wings/tail/horn are decided randomly
        // per soldier rather than taken from the shared EquestriaHairStyle.Striped/EquestriaPonyBody.*Enabled
        // (those are only for the player and stay as they are).
        internal static void Attach(object visuals, int race, string where, object cacheKey = null, string bodyCode = null,
            bool? stripedOverride = null, bool? wingsOverride = null, bool? tailOverride = null, bool? hornOverride = null,
            float? wingsScaleOverride = null, float? tailScaleOverride = null)
        {
            if (visuals == null)
            {
                return;
            }
            bool striped = stripedOverride ?? EquestriaHairStyle.Striped;
            // The helmet is fitted right here: these points are called both when the character is assembled and every frame from
            // the equipment window, and the stretch anchor has to follow the head.
            //
            // The real tiny party icon on the map is the only case where Attach is called
            // with the name (the engine itself gives this name to the visuals object on
            // AgentVisuals.Create, see AfterVisualsCreate). Everything else is windows and the encyclopedia;
            // their ActiveState is the same MapState as on the real map (they are overlays on top of it),
            // so by ActiveState the icon could not be told from a window: EquestriaHelmetFit hid
            // the helmet there too, every frame, right after fitting it correctly itself (noticed
            // 25.09.2026: in the log a successful fit, on the screen nothing).
            bool isMapIcon = where != null && where.IndexOf("PartyIcon", StringComparison.Ordinal) >= 0;
            EquestriaHelmetFit.Fit(visuals, race, isMapIcon);
            // The hidden donor hairstyle is set up BEFORE we paint the tail/wings/horn below: under a helmet
            // the skeleton is rebuilt from scratch every time, and if it is set up after the painting, the donor
            // will not be in place yet and FindDonor will not find the colour this particular time.
            if (HairReferenceByRaceId().TryGetValue(race, out string hairRef))
            {
                EnsureHiddenHairReference(visuals, hairRef, where, cacheKey ?? visuals, bodyCode, striped);
                EnsureHairNotBald(visuals, race, hairRef);
            }
            if (!RaceParts().TryGetValue(race, out string[] meshNames))
            {
                return;
            }
            foreach (string meshName in meshNames)
            {
                // Wing/tail scale only for rank-and-file troops (OnAgentBuild), by the mesh name suffix,
                // not by race directly: the same mechanism, at the user's request on 07.10.2026,
                // first for griffon wings, then extended to all winged races and separately
                // to the dragon tail. The horn was tried the same way (dragon/deer) and removed, see the comment
                // at SetPartVisible: the head bone rotates quickly, the transform override does not
                // keep up with it.
                float? scale = null;
                if (meshName.EndsWith("_wings", StringComparison.OrdinalIgnoreCase))
                {
                    scale = wingsScaleOverride;
                }
                else if (meshName.EndsWith("_tail", StringComparison.OrdinalIgnoreCase))
                {
                    scale = tailScaleOverride;
                }
                AttachOne(visuals, meshName, where, striped, scale);
            }
            // The eyebrows in movies.xml stay human (pony_skins.xml, see make_pony_race.py:
            // an empty list there crashes the editor when creating a hero), are placed at the point of the human
            // face and on a pony hide by themselves inside the larger head. On the deer (05.10.2026, after
            // head geometry edits for blinking) the head is no longer that much bigger than the human one
            // and the eyebrows/eyelashes became visible. We hide them with the same SetVisibilityMask(0) as the ears above,
            // for all our races at once: human eyebrows must not be visible on any of them.
            SetPartVisible(visuals, "male_eyebrow", false);
            SetPartVisible(visuals, "female_eyebrow", false);
            // Temporary "wings/tail/horn on-off" toggles (EquestriaPonyBody): in MLP lore
            // not every pony has all the parts. The part is always attached and painted, as before
            // (above, in the common loop); on/off is only mesh visibility, SetVisibilityMask(0),
            // the same trick as for the hidden donor hairstyle under a helmet. We tried removing the mesh
            // for real (GameEntity.RemoveComponentWithMesh): it conflicts with how
            // MBAgentVisuals.AddMultiMesh hangs it: that one thinks the slot is still occupied and does not let
            // it be put back without reopening the window (noticed 29.09.2026).
            if (EarMeshByRaceId().TryGetValue(race, out string earMesh))
            {
                // Ears are hidden under a helmet with the same SetVisibilityMask(0) as the toggles below;
                // only the condition is not manual but "is any headgear worn at all" (HasHeadgear).
                SetPartVisible(visuals, earMesh, !HasHeadgear(visuals));
            }
            if (race == DeerRaceId())
            {
                string report = ShowDeerAntlers(visuals, bodyCode);
                if (_deerAttachLogged++ < 12)
                {
                    EquestriaCrashLog.Log($"рога оленихи [{where}]: {report}");
                }
            }
            if (race == PonyRaceId())
            {
                SetPartVisible(visuals, "eq_pony_wings", wingsOverride ?? EquestriaPonyBody.WingsEnabled);
                SetPartVisible(visuals, "eq_pony_tail", tailOverride ?? EquestriaPonyBody.TailEnabled);
                SetPartVisible(visuals, "eq_pony_horn", hornOverride ?? EquestriaPonyBody.HornEnabled);
            }
        }

        private static int _ponyRaceId = -1;

        private static int PonyRaceId()
        {
            if (_ponyRaceId == -1)
            {
                _ponyRaceId = TaleWorlds.Core.FaceGen.GetRaceOrDefault("pony");
            }
            return _ponyRaceId;
        }

        private static int _dragonRaceId = -1;

        private static int DragonRaceId()
        {
            if (_dragonRaceId == -1)
            {
                _dragonRaceId = TaleWorlds.Core.FaceGen.GetRaceOrDefault("dragon");
            }
            return _dragonRaceId;
        }

        // Races with wings: the same PartByRace/RaceParts(), just filtered by the
        // mesh name suffix, so as not to keep a separate list by hand (pony, changeling, dragon,
        // griffon, hippogriff; checked 07.10.2026).
        private static HashSet<int> _wingsRaceIds;

        private static HashSet<int> WingsRaceIds()
        {
            if (_wingsRaceIds == null)
            {
                _wingsRaceIds = new HashSet<int>(RaceParts()
                    .Where(kv => kv.Value.Any(p => p.EndsWith("_wings", StringComparison.OrdinalIgnoreCase)))
                    .Select(kv => kv.Key));
            }
            return _wingsRaceIds;
        }

        // Range of the random wing scale per race (see the call above): by default (0.5, 1.0),
        // except for the exceptions listed explicitly here. dragon goes lower (0.25-1.0), changeling
        // both lower and larger than the standard (0.7-1.5, at the user's request 07.10.2026).
        private static readonly Dictionary<string, (float Min, float Max)> WingsScaleRangeByRace =
            new Dictionary<string, (float, float)>
        {
            { "dragon", (0.25f, 1f) },
            { "changeling", (0.7f, 1.5f) },
            { "pony", (0.7f, 1.2f) },
            { "hippogriff", (0.3f, 1f) },
        };

        private static Dictionary<int, (float Min, float Max)> _wingsScaleRangeByRaceId;

        private static Dictionary<int, (float Min, float Max)> WingsScaleRangeByRaceId()
        {
            if (_wingsScaleRangeByRaceId == null)
            {
                _wingsScaleRangeByRaceId = new Dictionary<int, (float, float)>();
                foreach (var pair in WingsScaleRangeByRace)
                {
                    int race = TaleWorlds.Core.FaceGen.GetRaceOrDefault(pair.Key);
                    if (race != 0)
                    {
                        _wingsScaleRangeByRaceId[race] = pair.Value;
                    }
                }
            }
            return _wingsScaleRangeByRaceId;
        }

        // Range of the random tail scale per race: the same trick as WingsScaleRangeByRace.
        // By default the tail gets no random size at all (the race is not in the dictionary); dragon:
        // (0.25, 1.0, only down), changeling: (0.7, 1.5), same as the wings, requested 07.10.2026.
        private static readonly Dictionary<string, (float Min, float Max)> TailScaleRangeByRace =
            new Dictionary<string, (float, float)>
        {
            { "dragon", (0.25f, 1f) },
            { "changeling", (0.7f, 1.5f) },
            { "pony", (0.7f, 1.2f) },
            { "hippogriff", (0.3f, 1f) },
        };

        private static Dictionary<int, (float Min, float Max)> _tailScaleRangeByRaceId;

        private static Dictionary<int, (float Min, float Max)> TailScaleRangeByRaceId()
        {
            if (_tailScaleRangeByRaceId == null)
            {
                _tailScaleRangeByRaceId = new Dictionary<int, (float, float)>();
                foreach (var pair in TailScaleRangeByRace)
                {
                    int race = TaleWorlds.Core.FaceGen.GetRaceOrDefault(pair.Key);
                    if (race != 0)
                    {
                        _tailScaleRangeByRaceId[race] = pair.Value;
                    }
                }
            }
            return _tailScaleRangeByRaceId;
        }

        // A random horn size was tried for dragon and deer (07.10.2026) via the same runtime
        // transform as the wings/tail and removed: the horn is attached to the HEAD bone, which
        // rotates quickly and often, and a static override (SetLocalFrame/SetAdditionalBoneFrame)
        // does not keep up with it frame by frame at a noticeable shrink (wings/tail on the
        // back/pelvis bones have the same issue, but it is unnoticeable due to the slower bone movement). If it is needed
        // again, only with ready-made shrunken mesh variants (like the cut arms/legs), not
        // a runtime scale.

        // Parts whose name is the start of another part's name of the same race: the deer doe antlers eq_deer_horn and their
        // variants eq_deer_horn_2..4 (10.10.2026). For them a prefix comparison would hit all
        // variants at once, so it is the exact name or a copy with a dot (like HideWholePart in
        // EquestriaDismemberment). The rest keep the old prefix comparison: that is how, for example,
        // the human eyebrows male_eyebrow* are found.
        private static readonly HashSet<string> ExactPartNames =
            new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "eq_deer_horn" };

        internal static bool PartNameMatches(string actual, string meshName)
        {
            if (!actual.StartsWith(meshName, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }
            return !ExactPartNames.Contains(meshName) || actual.Length == meshName.Length
                || actual[meshName.Length] == '.';
        }

        // Deer doe antlers: four variants, the number comes from the hairstyle (braids eq_deer_hair, eq_deer_hair_2..4,
        // tools/make_pony_race.py DEER_HAIR). First we look at the worn braid: it is true even in
        // the barber window, where the appearance code is still the old one. Under a helmet there is no braid (the engine does not build it),
        // then the hairstyle number is taken from the appearance code; without a code, the first antlers.
        internal static readonly string[] DeerHornVariants =
            { "eq_deer_horn", "eq_deer_horn_2", "eq_deer_horn_3", "eq_deer_horn_4" };
        private const string DeerHairPrefix = "eq_deer_hair";

        private static int _deerRaceId = -1;
        private static int _deerAttachLogged;

        private static int DeerRaceId()
        {
            if (_deerRaceId == -1)
            {
                _deerRaceId = TaleWorlds.Core.FaceGen.GetRaceOrDefault("deer");
            }
            return _deerRaceId;
        }

        internal static int DeerAntlerVariant(Skeleton skeleton, string bodyCode)
        {
            return DeerAntlerVariant(skeleton, bodyCode, out _);
        }

        internal static int DeerAntlerVariant(Skeleton skeleton, string bodyCode, out string source)
        {
            source = "нет данных";
            var hair = skeleton?.GetAllMeshes().FirstOrDefault(m => m != null && m.Name != null
                && m.VisibilityMask != 0 && m.Name.StartsWith(DeerHairPrefix, StringComparison.OrdinalIgnoreCase));
            if (hair != null)
            {
                source = "коса " + hair.Name;
                string tail = hair.Name.Substring(DeerHairPrefix.Length);
                if (tail.Length >= 2 && tail[0] == '_' && char.IsDigit(tail[1]))
                {
                    int n = tail[1] - '0';
                    if (n >= 1 && n <= DeerHornVariants.Length)
                    {
                        return n - 1;
                    }
                }
                return 0;
            }
            if (!string.IsNullOrEmpty(bodyCode) && BodyProperties.FromString(bodyCode, out BodyProperties body))
            {
                try
                {
                    var face = FaceGenerationParams.Create();
                    MBBodyProperties.GetParamsFromKey(ref face, body, false, false);
                    source = "причёска №" + face.CurrentHair;
                    // 0 is the "bald" list entry, then the braids in a cycle (see DEER_HAIR)
                    return face.CurrentHair <= 0 ? 0 : (face.CurrentHair - 1) % DeerHornVariants.Length;
                }
                catch (Exception e)
                {
                    EquestriaCrashLog.Warn("рога оленихи: номер причёски не прочитан — " + e.Message);
                }
            }
            return 0;
        }

        /// <returns>A string for the log: where the number came from and how many meshes of each variant were found.</returns>
        private static string ShowDeerAntlers(object visuals, string bodyCode)
        {
            var entity = AccessTools.Method(visuals.GetType(), "GetEntity")?.Invoke(visuals, null) as GameEntity;
            var skeleton = entity?.Skeleton;
            if (skeleton == null)
            {
                return "нет скелета";
            }
            int chosen = DeerAntlerVariant(skeleton, bodyCode, out string source);
            for (int i = 0; i < DeerHornVariants.Length; i++)
            {
                SetPartVisible(visuals, DeerHornVariants[i], i == chosen);
            }
            var meshes = skeleton.GetAllMeshes().Where(m => m != null && m.Name != null).ToList();
            string found = string.Join(", ", DeerHornVariants.Select(v =>
                v.Substring("eq_deer_".Length) + ":" + meshes.Count(m => PartNameMatches(m.Name, v))
                + "/" + meshes.Count(m => PartNameMatches(m.Name, v) && m.VisibilityMask != 0)));
            return $"рога {chosen + 1} ({source}); мешей всего/видно — {found}";
        }

        // Battle: at OnAgentBuild the part meshes and the helmet are not always in place on the agent yet (the same
        // timing as with the yak hairstyle, see HideBaldHairUnderConfirmedHelmet), so the deer doe
        // antlers are chosen once more a bit later, DeerLateFrames frames after assembly.
        private const int DeerLateFrames = 20;
        private readonly Dictionary<Agent, int> _deerPending = new Dictionary<Agent, int>();
        private int _deerLogged;

        internal static void SetPartVisible(object visuals, string meshName, bool visible)
        {
            var entity = AccessTools.Method(visuals.GetType(), "GetEntity")?.Invoke(visuals, null) as GameEntity;
            var skeleton = entity?.Skeleton;
            if (skeleton == null)
            {
                return;
            }
            foreach (var mesh in skeleton.GetAllMeshes().Where(m => m != null && m.Name != null
                && PartNameMatches(m.Name, meshName)))
            {
                mesh.SetVisibilityMask(visible ? VisibilityMaskFlags.DefaultDynamic : 0);
            }
        }

        // Race -> any of its hairstyles that is painted with the hair colour (one is enough so that there is always
        // something to copy the tail/wings/horn colour from, even under a helmet), and it is also the default
        // hairstyle that we switch back on if the player chose the "bald" one (see HairVariantsByRace
        // and EnsureHairNotBald below).
        private static readonly Dictionary<string, string> HairReferenceByRace =
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            { "pony", "eq_pony_hair" },
            // griffon and hippogriff are deliberately not included: the models rebuilt on 04.10.2026
            // no longer have hair as such at all (the griffon has ears, see EarMeshByRace; the
            // hippogriff does not even have separate ears), a reference to eq_*_hair would be dead. changeling
            // (05.10.2026): the strand manes were disabled, too similar to human hairstyles.
            { "dragon", "eq_dragon_hair" },
            { "yak", "eq_yak_hair" },
            { "deer", "eq_deer_hair" },
        };

        // Race -> ALL hairstyle meshes that the skin considers a valid choice (pony_skins.xml,
        // hair_mesh). Every race remaining here has only one variant: the skin slips it into
        // any position in the hairstyle list, so there is physically nothing bald to choose.
        private static readonly Dictionary<string, string[]> HairVariantsByRace =
            new Dictionary<string, string[]>(StringComparer.OrdinalIgnoreCase)
        {
            { "pony", new[] { "eq_pony_hair" } },
            { "dragon", new[] { "eq_dragon_hair" } },
            { "yak", new[] { "eq_yak_hair" } },
            { "deer", new[] { "eq_deer_hair", "eq_deer_hair_2", "eq_deer_hair_3", "eq_deer_hair_4" } },
        };

        // Race -> the mesh we hide when a helmet of any kind is worn (see HasHeadgear). Originally
        // only ears (griffon/changeling/deer have no hair, the only thing that needs hiding
        // under a helmet), but the trick is the same for any part on the head: the dragon (06.10.2026, at the
        // user's request) hides its horn here; it is also attached as usual (RaceParts above) and
        // comes here only to be hidden under a helmet.
        private static readonly Dictionary<string, string> EarMeshByRace =
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            { "griffon", "eq_griffon_ear" },
            { "changeling", "eq_changeling_ears" },
            { "deer", "eq_deer_ears" },
            { "dragon", "eq_dragon_horn" },
            { "pony", "eq_pony_ears" },
        };

        private static Dictionary<int, string> _earMeshByRaceId;

        private static Dictionary<int, string> EarMeshByRaceId()
        {
            if (_earMeshByRaceId == null)
            {
                _earMeshByRaceId = new Dictionary<int, string>();
                foreach (var pair in EarMeshByRace)
                {
                    int race = TaleWorlds.Core.FaceGen.GetRaceOrDefault(pair.Key);
                    if (race != 0)
                    {
                        _earMeshByRaceId[race] = pair.Value;
                    }
                }
            }
            return _earMeshByRaceId;
        }

        private static Dictionary<int, string> _hairReferenceByRaceId;

        private static Dictionary<int, string> HairReferenceByRaceId()
        {
            if (_hairReferenceByRaceId == null)
            {
                _hairReferenceByRaceId = new Dictionary<int, string>();
                foreach (var pair in HairReferenceByRace)
                {
                    int race = TaleWorlds.Core.FaceGen.GetRaceOrDefault(pair.Key);
                    if (race != 0)
                    {
                        _hairReferenceByRaceId[race] = pair.Value;
                    }
                }
            }
            return _hairReferenceByRaceId;
        }

        private static Dictionary<int, string[]> _hairVariantsByRaceId;

        private static Dictionary<int, string[]> HairVariantsByRaceId()
        {
            if (_hairVariantsByRaceId == null)
            {
                _hairVariantsByRaceId = new Dictionary<int, string[]>();
                foreach (var pair in HairVariantsByRace)
                {
                    int race = TaleWorlds.Core.FaceGen.GetRaceOrDefault(pair.Key);
                    if (race != 0)
                    {
                        _hairVariantsByRaceId[race] = pair.Value;
                    }
                }
            }
            return _hairVariantsByRaceId;
        }

        // A "bald" hairstyle is when the player chose a variant in the editor that the race does not have
        // (the engine simply shows nothing in that slot). For us the hairstyle is part of the race, not
        // a removable item, so there must be no bald ones at all: if NOT A SINGLE known hairstyle variant
        // of the race is visible on the skeleton, we switch the fallback one (HairReferenceByRace) back on,
        // with the same SetVisibilityMask as the pony's wings/tail/horn toggle (see SetPartVisible).
        //
        // IMPORTANT (04.10.2026): under a closed helmet the engine hides the hairstyle itself (the helmet's
        // hair_cover_type); this is not baldness but the normal helmet fit, and forcing the hairstyle back is wrong,
        // otherwise it sticks out through the helmet (noticed in game). So when headgear is worn this
        // check is not performed at all: its covering is silently considered legitimate.
        private static void EnsureHairNotBald(object visuals, int race, string defaultHairRef)
        {
            if (!HairVariantsByRaceId().TryGetValue(race, out string[] variants) || variants.Length == 0)
            {
                return;
            }
            if (HasHeadgear(visuals))
            {
                return;
            }
            var entity = AccessTools.Method(visuals.GetType(), "GetEntity")?.Invoke(visuals, null) as GameEntity;
            var skeleton = entity?.Skeleton;
            if (skeleton == null)
            {
                return;
            }
            var meshes = skeleton.GetAllMeshes().Where(m => m != null && m.Name != null).ToList();
            bool anyVisible = meshes.Any(m => m.VisibilityMask != 0
                && variants.Any(v => m.Name.StartsWith(v, StringComparison.OrdinalIgnoreCase)));
            if (anyVisible)
            {
                return;
            }
            foreach (var mesh in meshes.Where(m => m.Name.StartsWith(defaultHairRef, StringComparison.OrdinalIgnoreCase)))
            {
                mesh.SetVisibilityMask(VisibilityMaskFlags.DefaultDynamic);
            }
        }

        // Cleanup of a timing race (05.10.2026): OnAgentBuild calls Attach ONCE when the agent spawns
        // in battle, and HasHeadgear there looks at GetCopyAgentVisualsData; at that very tick
        // it sometimes does not contain the just-equipped helmet yet (noticed on the yak: helmet on the head,
        // yet the hairstyle stays switched on over it until the end of the battle: EnsureHairNotBald once
        // wrongly decided "bald" and raised the mane visibility, and it is not called a second time).
        // EquestriaHelmetFit.Fit(Agent) knows the helmet from agent.SpawnEquipment, a source that
        // races with nothing, and calls this method when it first (or again) recognises a helmet on
        // the agent. We hide everything EnsureHairNotBald may have switched on by mistake.
        // The same trick for the same reason as in HideBaldHairUnderConfirmedHelmet (see there): the ears
        // are also decided once at OnAgentBuild from a less reliable snapshot (HasHeadgear inside
        // Attach) and in battle sometimes stay visible under a helmet (noticed in game 07.10.2026: correct in the
        // inventory window, not in battle). Here the helmet is already confirmed by the reliable agent.SpawnEquipment,
        // so we hide the ears unconditionally, since this code only runs when there definitely is a helmet.
        internal static void HideEarsUnderConfirmedHelmet(object visuals, int race)
        {
            if (EarMeshByRaceId().TryGetValue(race, out string earMesh))
            {
                SetPartVisible(visuals, earMesh, false);
            }
        }

        internal static void HideBaldHairUnderConfirmedHelmet(object visuals, int race)
        {
            if (!HairVariantsByRaceId().TryGetValue(race, out string[] variants) || variants.Length == 0)
            {
                return;
            }
            var entity = AccessTools.Method(visuals.GetType(), "GetEntity")?.Invoke(visuals, null) as GameEntity;
            var skeleton = entity?.Skeleton;
            if (skeleton == null)
            {
                return;
            }
            foreach (var mesh in skeleton.GetAllMeshes())
            {
                if (mesh == null || mesh.Name == null || mesh.VisibilityMask == 0)
                {
                    continue;
                }
                if (variants.Any(v => mesh.Name.StartsWith(v, StringComparison.OrdinalIgnoreCase)))
                {
                    mesh.SetVisibilityMask(0);
                }
            }
        }

        // The same trick as in EquestriaHelmetFit.HideEquippedHelmet: we look at the head slot through
        // a copy of the visuals data, not through Agent, because Attach is also called where there is no agent
        // (windows, barber). Any non-empty headgear (not only a helmet: a hood, a hat, etc.)
        // counts: the reason the hairstyle is hidden does not concern us, as long as we do not fix what is not
        // broken.
        private static bool HasHeadgear(object visuals)
        {
            var getData = AccessTools.Method(visuals.GetType(), "GetCopyAgentVisualsData");
            var data = getData?.Invoke(visuals, null);
            if (data == null)
            {
                return false;
            }
            var equipment = AccessTools.Property(data.GetType(), "EquipmentData")?.GetValue(data) as Equipment;
            string meshName = equipment?[EquipmentIndex.Head].Item?.MultiMeshName;
            return !string.IsNullOrEmpty(meshName);
        }

        private sealed class HairLook
        {
            public uint Color;
            public uint Color2;
            public float Ax, Ay, Az, Aw, Bx, By, Bz, Bw;
        }

        // The log revealed (28.09.2026): in the same tick in which the helmet hides the real mane,
        // the engine itself clears the mesh list on the skeleton (preparing the new equipment); together with the mane
        // our hidden donor copy disappears too, and the new copy is born in that same tick already without
        // any live colour nearby (the hidden one's colour in the log is FFFFFFFF, exactly like a fresh
        // unpainted copy). So one hidden copy is not enough: we need a colour that survives the
        // rebuild tick itself. We keep it outside the skeleton, but not keyed by the visuals themselves either:
        // in windows CharacterTableau also recreates them on an equipment change (the same log: the colour
        // was written to the cache by visuals 70 ms before the reset, and on the reset TryGetValue by the NEW visuals
        // found nothing). The key is passed by the caller (cacheKey in Attach): something that
        // survives a visuals rebuild; for windows it is CharacterTableau itself.
        private static readonly System.Runtime.CompilerServices.ConditionalWeakTable<object, HairLook> LastHairLook =
            new System.Runtime.CompilerServices.ConditionalWeakTable<object, HairLook>();

        // The same cache, but keyed by the character's appearance code (BodyProperties, see AfterTableauTick):
        // it survives even a completely new window, not just a rebuild inside one. Needed when
        // a window opens with a helmet already on the head: its own hairstyle is never built in it,
        // and cacheKey (CharacterTableau itself) remembers nothing simply because there was nothing
        // to remember. But the appearance code of a character is the same in all windows, and if the hairstyle
        // has been seen anywhere already (for example, in the character editor, where there is no helmet), the colour
        // will be found here too.
        private static readonly Dictionary<string, HairLook> HairLookByCode = new Dictionary<string, HairLook>();

        // The cache above lived only in the memory of the current session: for a soldier whose head is covered from the
        // very start, the engine never builds the real mane, there is nowhere to peek at the colour, and
        // the horn/tail stayed white in every new battle (noticed 29.09.2026, a hooded archer
        // on horseback). Reading the colour from the data directly is impossible: decompiling TaleWorlds.Core.dll
        // showed that IFaceGen only offers writing (SetPigmentation), with no reading back. So
        // we save the cache itself: a colour seen once (in the editor, barber, inventory, wherever
        // the head is uncovered) survives both new battles and a game restart. Called by EquestriaHairStyle.
        // SyncData: EquestriaBodyParts itself is a MissionBehavior and has no SyncData.
        public static void SyncHairLookCache(IDataStore dataStore)
        {
            List<string> keys = null;
            List<string> values = null;
            if (dataStore.IsSaving)
            {
                keys = HairLookByCode.Keys.ToList();
                values = keys.Select(k => EncodeHairLook(HairLookByCode[k])).ToList();
            }
            dataStore.SyncData("eq_hair_look_keys", ref keys);
            dataStore.SyncData("eq_hair_look_values", ref values);
            if (!dataStore.IsSaving && keys != null && values != null && keys.Count == values.Count)
            {
                HairLookByCode.Clear();
                for (int i = 0; i < keys.Count; i++)
                {
                    if (TryDecodeHairLook(values[i], out HairLook look))
                    {
                        HairLookByCode[keys[i]] = look;
                    }
                }
            }
        }

        private static string EncodeHairLook(HairLook look)
        {
            return string.Join("|", new[]
            {
                look.Color.ToString(CultureInfo.InvariantCulture),
                look.Color2.ToString(CultureInfo.InvariantCulture),
                look.Ax.ToString(CultureInfo.InvariantCulture), look.Ay.ToString(CultureInfo.InvariantCulture),
                look.Az.ToString(CultureInfo.InvariantCulture), look.Aw.ToString(CultureInfo.InvariantCulture),
                look.Bx.ToString(CultureInfo.InvariantCulture), look.By.ToString(CultureInfo.InvariantCulture),
                look.Bz.ToString(CultureInfo.InvariantCulture), look.Bw.ToString(CultureInfo.InvariantCulture),
            });
        }

        private static bool TryDecodeHairLook(string encoded, out HairLook look)
        {
            look = null;
            var parts = encoded?.Split('|');
            if (parts == null || parts.Length != 10)
            {
                return false;
            }
            if (!uint.TryParse(parts[0], NumberStyles.Integer, CultureInfo.InvariantCulture, out uint color)
                || !uint.TryParse(parts[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out uint color2))
            {
                return false;
            }
            var f = new float[8];
            for (int i = 0; i < 8; i++)
            {
                if (!float.TryParse(parts[i + 2], NumberStyles.Float, CultureInfo.InvariantCulture, out f[i]))
                {
                    return false;
                }
            }
            look = new HairLook
            {
                Color = color, Color2 = color2,
                Ax = f[0], Ay = f[1], Az = f[2], Aw = f[3],
                Bx = f[4], By = f[5], Bz = f[6], Bw = f[7],
            };
            return true;
        }

        private static void EnsureHiddenHairReference(object visuals, string meshName, string where,
            object cacheKey, string bodyCode, bool striped)
        {
            var entity = AccessTools.Method(visuals.GetType(), "GetEntity")?.Invoke(visuals, null) as GameEntity;
            var skeleton = entity?.Skeleton;
            if (skeleton == null)
            {
                return;
            }
            var candidates = skeleton.GetAllMeshes()
                .Where(m => m != null && m.Name != null
                            && m.Name.StartsWith(meshName, StringComparison.OrdinalIgnoreCase)).ToList();
            var visible = candidates.FirstOrDefault(m => m.VisibilityMask != 0);
            var hidden = candidates.FirstOrDefault(m => m.VisibilityMask == 0);
            if (hidden == null)
            {
                var mesh = MetaMesh.GetCopy(meshName, true, false);
                if (mesh == null)
                {
                    EquestriaCrashLog.Log($"причёска[{where} / {Screen()}]: {meshName} не скопирован — MetaMesh.GetCopy вернул null");
                    return;
                }
                for (int i = 0; i < mesh.MeshCount; i++)
                {
                    mesh.GetMeshAtIndex(i)?.SetVisibilityMask(0);
                }
                var mbVisuals = AccessTools.Method(visuals.GetType(), "GetVisuals")?.Invoke(visuals, null)
                    as MBAgentVisuals;
                if (mbVisuals != null)
                {
                    mbVisuals.AddMultiMesh(mesh, Slot);
                }
                else
                {
                    var frame = entity.GetFrame();
                    entity.AddMultiMeshToSkeleton(mesh);
                    entity.SetFrame(ref frame);
                }
                hidden = skeleton.GetAllMeshes().FirstOrDefault(m => m != null && m.Name != null
                    && m.Name.StartsWith(meshName, StringComparison.OrdinalIgnoreCase) && m.VisibilityMask == 0);
            }
            if (visible != null)
            {
                // The hairstyle itself (the mane) is not a body part, Tint() does not paint it; we switch its material
                // right here, since we find the visible hairstyle every time anyway.
                if (EquestriaHairStyle.StripeMaterialByMesh.TryGetValue(meshName, out string maneStripe))
                {
                    string wantName = striped ? maneStripe : EquestriaHairStyle.PlainMaterial;
                    var wantMat = Material.GetFromResource(wantName);
                    var ownMat = visible.GetMaterial();
                    if (wantMat != null && (ownMat == null || ownMat.Name != wantMat.Name))
                    {
                        visible.SetMaterial(wantMat);
                    }
                }
                var arg = visible.GetVectorArgument();
                var arg2 = visible.GetVectorArgument2();
                var look = new HairLook
                {
                    Color = visible.Color, Color2 = visible.Color2,
                    Ax = arg.x, Ay = arg.y, Az = arg.z, Aw = arg.w,
                    Bx = arg2.x, By = arg2.y, Bz = arg2.z, Bw = arg2.w,
                };
                LastHairLook.Remove(cacheKey);
                LastHairLook.Add(cacheKey, look);
                if (!string.IsNullOrEmpty(bodyCode))
                {
                    if (HairLookByCode.Count > 500)
                    {
                        HairLookByCode.Clear();
                    }
                    HairLookByCode[bodyCode] = look;
                }
                if (hidden != null)
                {
                    hidden.Color = look.Color;
                    hidden.Color2 = look.Color2;
                    hidden.SetVectorArgument(look.Ax, look.Ay, look.Az, look.Aw);
                    hidden.SetVectorArgument2(look.Bx, look.By, look.Bz, look.Bw);
                }
            }
            else if (hidden != null)
            {
                HairLook look = null;
                if (string.IsNullOrEmpty(bodyCode) || !HairLookByCode.TryGetValue(bodyCode, out look))
                {
                    LastHairLook.TryGetValue(cacheKey, out look);
                }
                if (look != null)
                {
                    hidden.Color = look.Color;
                    hidden.Color2 = look.Color2;
                    hidden.SetVectorArgument(look.Ax, look.Ay, look.Az, look.Aw);
                    hidden.SetVectorArgument2(look.Bx, look.By, look.Bz, look.Bw);
                }
            }
        }

        /// <summary>
        /// Put one mesh on an already assembled character. Needed for the helmet: on the world map it is hidden,
        /// and the game does not build the hairstyle under it, so it has to be restored separately.
        /// Calling it again does no harm: a mesh that is already hanging is not doubled.
        /// </summary>
        public static void AttachPart(object visuals, string meshName, string where)
        {
            if (visuals != null && !string.IsNullOrEmpty(meshName))
            {
                AttachOne(visuals, meshName, where, EquestriaHairStyle.Striped);
            }
        }

        private static void AttachOne(object visuals, string meshName, string where, bool striped, float? scale = null)
        {
            var entity = AccessTools.Method(visuals.GetType(), "GetEntity")?.Invoke(visuals, null) as GameEntity;
            if (entity == null)
            {
                return;
            }
            // Screens refresh the character at the slightest excuse; otherwise tails would pile up on each other.
            // But we do update the painting: the player changes the skin colour right in the window, and the already worn
            // tail must be repainted together with the body.
            var skeleton = entity.Skeleton;
            var already = skeleton == null ? null : skeleton.GetAllMeshes()
                .Where(m => m != null && m.Name != null && PartNameMatches(m.Name, meshName)).ToList();
            if (already != null && already.Count > 0)
            {
                Tint(already, skeleton, meshName, where, striped);
                return;
            }
            var mesh = MetaMesh.GetCopy(meshName, true, false);
            if (mesh == null)
            {
                return;
            }
            Tint(mesh, skeleton, meshName, where, striped);
            if (scale.HasValue)
            {
                ApplyUniformScale(mesh, scale.Value);
            }
            // Just putting the mesh into the object's skeleton (GameEntity.AddMultiMeshToSkeleton) is not enough: in battle
            // it works, but in the party and equipment windows the character is drawn by a separate system
            // (agent renderer), and a mesh it does not know about does not get into the frame. So we give
            // the mesh to the visuals themselves, MBAgentVisuals.AddMultiMesh: they are the same in battle and in windows.
            var mbVisuals = AccessTools.Method(visuals.GetType(), "GetVisuals")?.Invoke(visuals, null)
                as MBAgentVisuals;
            if (mbVisuals != null)
            {
                mbVisuals.AddMultiMesh(mesh, Slot);
            }
            else
            {
                var frame = entity.GetFrame();
                entity.AddMultiMeshToSkeleton(mesh);
                entity.SetFrame(ref frame);
            }
        }

        // Shrinks the mesh around its geometric centre (bounding box); suitable for wings
        // and tail (the back/pelvis bones rotate slowly, the desync is unnoticeable). For the horn (the head
        // bone, rotates quickly) the same trick was tried and removed; see the comment
        // at SetPartVisible.
        private static void ApplyUniformScale(MetaMesh mesh, float scale)
        {
            Vec3 center = mesh.GetBoundingBox().center;
            MatrixFrame frame = MatrixFrame.Identity;
            frame.rotation.ApplyScaleLocal(scale);
            frame.origin = center * (1f - scale);

            for (int i = 0; i < mesh.MeshCount; i++)
            {
                mesh.GetMeshAtIndex(i)?.SetLocalFrame(frame);
            }
        }

        // ---------------------------------------------------------------- painting
        // The engine assigns the skin colour to the body meshes itself when it assembles the character from its appearance.
        // Our tail and wings are added outside this assembly and stay white, so the painting
        // is simply copied from an already worn mesh of the same race: colour, second colour and both vector
        // arguments of the material. The donor is searched by the common name prefix (eq_dragon_tail -> eq_dragon_),
        // but not among ourselves, otherwise we would copy whiteness from the neighbouring wing.
        private static readonly string[] DonorOrder = { "body", "legs", "gloves", "head" };

        // Parts that are painted with the HAIRSTYLE colour, not the skin colour: on a pony the tail matches the mane
        // (hair colour choice in the appearance window). The colour is taken from the hairstyle mesh on the same skeleton;
        // these parts have a hair material (tools/pony_material.ps1), otherwise the skin shader does not read
        // the hair colour.
        // The wings and horn are NOT included here: by MLP lore they are body-coloured, not mane-coloured (wings checked
        // 29.09.2026, horn 30.09.2026). Without an entry here they go into the regular Tint() branch and
        // are painted like a regular body part (colour and material from the nearest donor
        // body/legs/gloves; the donor material is copied whole, so they do not need the hair shader,
        // even if the mesh itself was exported with it).
        // Part -> the prefix of the hairstyle mesh name from which the colour is taken (changelings have four
        // manes eq_hair_chrysalis_*, the pony has one eq_pony_hair).
        private static readonly Dictionary<string, string> HairTinted =
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            { "eq_pony_tail", "eq_pony_hair" },
            { "eq_changeling_wings", "eq_hair_chrysalis" }, { "eq_changeling_tail", "eq_hair_chrysalis" },
        };

        private static Mesh FindDonor(Skeleton skeleton, string meshName)
        {
            int cut = meshName.LastIndexOf('_');
            if (skeleton == null || cut <= 0)
            {
                return null;
            }
            string prefix = meshName.Substring(0, cut + 1);
            if (HairTinted.TryGetValue(meshName, out string hairPrefix))
            {
                var hair = skeleton.GetAllMeshes().FirstOrDefault(m => m != null && m.Name != null
                    && m.Name.StartsWith(hairPrefix, StringComparison.OrdinalIgnoreCase));
                if (hair != null)
                {
                    return hair;
                }
            }
            var mine = RaceParts().Values.SelectMany(v => v).ToArray();
            var meshes = skeleton.GetAllMeshes()
                .Where(m => m != null && m.Name != null
                            && m.Name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)
                            && !mine.Any(n => m.Name.StartsWith(n, StringComparison.OrdinalIgnoreCase)))
                .ToList();
            // The head goes last: it can have its own face texture, and its material must not be taken
            foreach (string kind in DonorOrder)
            {
                var found = meshes.FirstOrDefault(m =>
                    m.Name.StartsWith(prefix + kind, StringComparison.OrdinalIgnoreCase));
                if (found != null)
                {
                    return found;
                }
            }
            return meshes.FirstOrDefault();
        }

        private static void Tint(IEnumerable<Mesh> targets, Skeleton skeleton, string meshName, string where, bool striped)
        {
            var donor = FindDonor(skeleton, meshName);
            bool fromHair = donor != null && donor.Name != null
                && donor.Name.IndexOf("_hair", StringComparison.OrdinalIgnoreCase) >= 0;
            if (donor == null)
            {
                return;
            }
            uint colour = donor.Color;
            uint colour2 = donor.Color2;
            var arg = donor.GetVectorArgument();
            var arg2 = donor.GetVectorArgument2();
            var material = donor.GetMaterial();
            // The striped mane is a separate material (Color2 has no visible effect in the hair shader,
            // checked in game 29.09.2026), not a second colour. We switch it ourselves, by the saved
            // player choice (EquestriaHairStyle), not by what the donor is: the donor's material does not
            // fit here; up to this part the donor just gives the colour, not its fill/stripes.
            Material wantHairMaterial = null;
            if (fromHair && EquestriaHairStyle.StripeMaterialByMesh.TryGetValue(meshName, out string stripeMat))
            {
                string wantName = striped ? stripeMat : EquestriaHairStyle.PlainMaterial;
                wantHairMaterial = Material.GetFromResource(wantName);
            }
            foreach (var target in targets)
            {
                if (target == null)
                {
                    continue;
                }
                target.Color = colour;
                target.Color2 = colour2;
                target.SetVectorArgument(arg.x, arg.y, arg.z, arg.w);
                target.SetVectorArgument2(arg2.x, arg2.y, arg2.z, arg2.w);
                var own = target.GetMaterial();
                if (wantHairMaterial != null)
                {
                    if (own == null || own.Name != wantHairMaterial.Name)
                    {
                        target.SetMaterial(wantHairMaterial);
                    }
                }
                // The material is taken only if the engine gave the body its own one, different from ours: that is how
                // the painting baked into the character material arrives.
                else if (!fromHair && material != null && own != null && material.Name != own.Name)
                {
                    target.SetMaterial(material);
                }
            }
        }

        private static void Tint(MetaMesh mesh, Skeleton skeleton, string meshName, string where, bool striped)
        {
            var list = new List<Mesh>();
            for (int i = 0; i < mesh.MeshCount; i++)
            {
                list.Add(mesh.GetMeshAtIndex(i));
            }
            Tint(list, skeleton, meshName, where, striped);
        }

        // ---------------------------------------------------------------- mission
        // Helmet in battle: one fit at assembly is not enough. First, in a mission the character is assembled not
        // by the same path as in windows (in battle the helmet stayed standard). Second, the stretch anchor is
        // the CURRENT position of the head bone, and in battle the head is moving all the time, so we recompute
        // every frame. We compute only for races with their own helmet size; there are only a few of them.
        // Close up we recompute every frame, farther away less often, so as not to compute for a thousand soldiers at once.
        // It used to be 25 m / once every 15 frames (~250 ms at 60 fps); while the fit itself was out of sync
        // (unrecognised shift/pivot rotation, see EquestriaHelmetFit.Fit), the jerks were not so
        // noticeable against that background. After the rotation fix the helmet follows the head perfectly every frame, and the jerks
        // every 15 frames became clearly visible ("flickering", noticed 03.10.2026). We shortened the gap
        // (4 frames, no more than ~66 ms at 60 fps, almost unnoticeable) and slightly raised the close radius.
        private const float CloseUp = 30f;     // metres: here we compute every frame
        private const int FarEvery = 4;        // farther away: once every this many frames
        private int _frame;

        public override void OnPreDisplayMissionTick(float dt)
        {
            if (Mission.Current == null)
            {
                return;
            }
            _frame++;
            if (_deerPending.Count > 0)
            {
                foreach (var agent in _deerPending.Keys.ToList())
                {
                    int left = _deerPending[agent] - 1;
                    if (left > 0)
                    {
                        _deerPending[agent] = left;
                        continue;
                    }
                    _deerPending.Remove(agent);
                    if (agent == null || !agent.IsActive() || agent.AgentVisuals == null)
                    {
                        continue;
                    }
                    var visuals = agent.AgentVisuals;
                    string bodyCode = agent.BodyPropertiesValue.ToString();
                    EquestriaCrashLog.Try("рога оленихи позже", () =>
                    {
                        string report = ShowDeerAntlers(visuals, bodyCode);
                        if (_deerLogged++ < 12)
                        {
                            EquestriaCrashLog.Log($"рога оленихи [{agent.Name}] спустя {DeerLateFrames} кадров: {report}");
                        }
                    });
                }
            }
            Vec3 eye = Mission.Current.Scene != null
                ? Mission.Current.Scene.LastFinalRenderCameraPosition
                : Vec3.Zero;
            foreach (var agent in Mission.Current.Agents)
            {
                if (agent == null || agent.IsMount || agent.Character == null)
                {
                    continue;
                }
                if (eye.DistanceSquared(agent.VisualPosition) > CloseUp * CloseUp
                    && (_frame + agent.Index) % FarEvery != 0)
                {
                    continue;
                }
                EquestriaHelmetFit.Fit(agent);
            }
        }

        public override void OnAgentBuild(Agent agent, Banner banner)
        {
            EquestriaCrashLog.Try("части тела в миссии", () =>
            {
                if (agent == null || agent.IsMount || agent.Character == null)
                {
                    return;
                }
                // The same appearance code as in windows (see AfterTableauTick): the own hairstyle under
                // a helmet is not built in battle either, and the player has almost always opened the editor or
                // inventory before the battle, so the colour is usually already in the shared HairLookByCode cache.
                string bodyCode = agent.BodyPropertiesValue.ToString();
                int race = agent.Character.Race;
                if (race == DeerRaceId())
                {
                    _deerPending[agent] = DeerLateFrames;
                }
                bool? striped = null, wings = null, tail = null, horn = null;
                uint? skinColor = null, hairColor = null;
                // We do not touch the player: their colour was chosen by the player in the character editor and already
                // comes through correctly via the engine's regular pigmentation. Rank-and-file troops and heroes (incl. lords;
                // WHY they all used to be white, see LoreColor) are painted by our code: the shared
                // lord appearance template (BodyProperty.fighter_empire_tall, without Min/Max spread)
                // gives all pony lords the same unscaled pigmentation colour.
                bool isPlayer = Hero.MainHero != null && agent.Character == Hero.MainHero.CharacterObject;
                if (race == PonyRaceId() && !isPlayer)
                {
                    if (!agent.Character.IsHero)
                    {
                        RandomizeCommonTroopLook(agent, out bool s, out bool w, out bool t, out bool h,
                            out uint skin, out uint hair);
                        striped = s; wings = w; tail = t; horn = h;
                        skinColor = skin; hairColor = hair;
                    }
                    else
                    {
                        LoreColor(agent.Character.StringId, out uint skin, out uint hair);
                        skinColor = skin; hairColor = hair;
                    }
                }
                // dragon had no random painting at all (ApplyPonyColors was never called for it):
                // the base is always the same texture (eq_dragon_body_d, almost white by itself,
                // meant for tinting; not lore, just unfinished painting), coloured not by us
                // but by the regular engine BodyProperties pigmentation, hence the "mostly bright
                // green and blue" (noticed by the user 07.10.2026). ApplyPonyColors/
                // RandomPonyPalette/LoreColor are already generic in code (the key is race), they only needed
                // to be called for dragon too, as for the pony. Its own RNG multiplier (another large
                // prime on agent.Index) does not coincide with any of the wing/tail/horn scales.
                else if (race == DragonRaceId() && !isPlayer)
                {
                    if (!agent.Character.IsHero)
                    {
                        var rng = new Random(unchecked(agent.Index * 32452867 + (Mission.Current?.GetHashCode() ?? 0)));
                        RandomPonyPalette(rng, out uint skin, out uint hair);
                        skinColor = skin; hairColor = hair;
                    }
                    else
                    {
                        LoreColor(agent.Character.StringId, out uint skin, out uint hair);
                        skinColor = skin; hairColor = hair;
                    }
                }
                // Random wing size for rank-and-file troops of any winged race (at the
                // user's request 07.10.2026, at first only griffon, then extended to all):
                // default range (0.5, 1.0), for dragon (0.25, 1.0), for changeling also
                // larger than the standard (0.7, 1.5), a separate request 07.10.2026. Heroes/lords and the
                // player themselves are excluded: their look must not jitter between battles. The same deterministic RNG
                // per agent as in RandomizeCommonTroopLook (agent.Index + Mission.Current),
                // otherwise the size would jump on every rebuild of the agent within one battle.
                float? wingsScale = null;
                if (WingsRaceIds().Contains(race) && !isPlayer && !agent.Character.IsHero)
                {
                    var rng = new Random(unchecked(agent.Index * 7919 + (Mission.Current?.GetHashCode() ?? 0)));
                    var (minScale, maxScale) = WingsScaleRangeByRaceId().TryGetValue(race, out var r) ? r : (0.5f, 1f);
                    wingsScale = minScale + (float)rng.NextDouble() * (maxScale - minScale);
                }
                // Random tail size: dragon (0.25-1.0) and changeling (0.7-1.5, like the wings,
                // at the user's request 07.10.2026). A separate RNG (a different multiplier on agent.Index),
                // otherwise it would be the same number as for the wings, and both scales would jitter in sync.
                float? tailScale = null;
                if (TailScaleRangeByRaceId().TryGetValue(race, out var tailRange)
                    && !isPlayer && !agent.Character.IsHero)
                {
                    var rng = new Random(unchecked(agent.Index * 104729 + (Mission.Current?.GetHashCode() ?? 0)));
                    tailScale = tailRange.Min + (float)rng.NextDouble() * (tailRange.Max - tailRange.Min);
                }
                Attach(agent.AgentVisuals, race, agent.Name ?? "агент", bodyCode: bodyCode,
                    stripedOverride: striped, wingsOverride: wings, tailOverride: tail, hornOverride: horn,
                    wingsScaleOverride: wingsScale, tailScaleOverride: tailScale);
                // We paint AFTER Attach, not before: under a helmet the real mane is not yet on the skeleton at
                // assembly time; Attach itself creates it -> EnsureHiddenHairReference, as an empty
                // (white) copy. We used to paint "into the void" before Attach: without a helmet the colour stuck,
                // and under a helmet almost never, which is why white tails turned out to be the overwhelming
                // majority (noticed 30.09.2026: white ones were exactly the soldiers in helmets).
                if (skinColor.HasValue && hairColor.HasValue)
                {
                    ApplyPonyColors(agent.AgentVisuals, race, skinColor.Value, hairColor.Value);
                }
            });
        }

        // Decides the random look of a rank-and-file soldier (its own RNG per soldier, deterministic by agent.Index
        // within ONE battle, otherwise the choice would jitter on every rebuild of the same agent;
        // Mission.Current in the mix gives the difference between battles). Only numbers; the meshes are not painted yet,
        // ApplyPonyColors does that after Attach (see there for why).
        private static void RandomizeCommonTroopLook(Agent agent, out bool striped, out bool wings, out bool tail, out bool horn,
            out uint skinColor, out uint hairColor)
        {
            var rng = new Random(unchecked(agent.Index * 7919 + (Mission.Current?.GetHashCode() ?? 0)));
            striped = rng.NextDouble() < 0.5;
            wings = rng.NextDouble() < 0.5;
            tail = rng.NextDouble() < 0.5;
            horn = rng.NextDouble() < 0.5;
            RandomPonyPalette(rng, out skinColor, out hairColor);
        }

        // As in the original MLP: the body and the mane are not picked out of thin air independently of each other:
        // with an almost white body the mane is free to be anything (Rarity etc.), for the others the mane is of the same
        // colour family as the body, only darker/more saturated and with a hue shift towards the warm
        // side (pink body -> dark pink mane, orange -> yellow) (noticed
        // 30.09.2026: before this fix the body and mane colours were rejected independently and did not match).
        private const float PaleSkinChance = 0.25f;

        private static void RandomPonyPalette(Random rng, out uint skinColor, out uint hairColor)
        {
            bool paleSkin = rng.NextDouble() < PaleSkinChance;
            float skinHue = (float)rng.NextDouble();
            float skinSat = paleSkin ? (float)rng.NextDouble() * 0.1f : 0.3f + (float)rng.NextDouble() * 0.5f;
            float skinVal = paleSkin ? 0.9f + (float)rng.NextDouble() * 0.08f : 0.55f + (float)rng.NextDouble() * 0.35f;
            skinColor = TaleWorlds.Library.Color.FromHSV(skinHue, skinSat, skinVal).ToUnsignedInteger();

            float hairHue, hairSat, hairVal;
            if (paleSkin)
            {
                hairHue = (float)rng.NextDouble();
                hairSat = 0.5f + (float)rng.NextDouble() * 0.5f;
                hairVal = 0.35f + (float)rng.NextDouble() * 0.5f;
            }
            else
            {
                // The hue shift is mostly towards the warm side (orange -> yellow), but not always:
                // with a small shift it is just a darker shade of the same hue (pink -> dark pink).
                float shift = -0.05f + (float)rng.NextDouble() * 0.25f;
                hairHue = Wrap01(skinHue + shift);
                hairSat = Math.Min(1f, skinSat + 0.15f + (float)rng.NextDouble() * 0.25f);
                hairVal = Math.Max(0.15f, skinVal * (0.55f + (float)rng.NextDouble() * 0.3f));
            }
            hairColor = TaleWorlds.Library.Color.FromHSV(hairHue, hairSat, hairVal).ToUnsignedInteger();
        }

        private static float Wrap01(float x)
        {
            x %= 1f;
            return x < 0f ? x + 1f : x;
        }

        // Lord characters known from the show (Module/ModuleData/equestria_lords.xml, pony lord ids):
        // the coat/mane colour is checked against the show's official colour guide (MLP Vector Club,
        // mlpvector.club/cg/pony, fill without outline/shadows; we have one solid tone per part).
        // Celestia and Cadance have a multicoloured/gradient mane in the original; it cannot be
        // conveyed with one tone, so the most noticeable shade is taken. The other lords (there are
        // several hundred of them in equestria_lords.xml, mostly procedurally built names) are not included here; see LoreColor.
        private static readonly Dictionary<string, (uint Skin, uint Hair)> LoreColors =
            new Dictionary<string, (uint, uint)>(StringComparer.OrdinalIgnoreCase)
        {
            { "eq_celestia", (0xFFF6E4EF, 0xFFD9B8DD) },
            { "eq_luna", (0xFF363E7A, 0xFF1C4CC2) },
            { "eq_cadance", (0xFFFFCBE4, 0xFF8034BA) },
            { "eq_twilight", (0xFFCC9CDF, 0xFF243870) },
            { "eq_blueblood", (0xFFFFFFFF, 0xFFE3CA75) },
            { "eq_spitfire", (0xFFF8EA62, 0xFFED7B00) },
            { "eq_soarin", (0xFFD8E6F5, 0xFF2D3263) },
            { "eq_fleetfoot", (0xFF8BD8DF, 0xFFFFFFFF) },
            { "eq_big_mac", (0xFFE64A57, 0xFFFBBA62) },
            { "eq_apple_bloom", (0xFFF3F49B, 0xFFF5415F) },
        };

        // A pony hero's colour: for known characters the lore one (LoreColors), for the others (there are
        // several hundred of them in equestria_lords.xml, not specified by lore) a stable random one
        // by the character's StringId. Important: not Random(agent.Index) as for rank-and-file troops: a hero is one
        // and the same between battles and after a game restart, their colour must not "jitter" every time.
        // string.GetHashCode() in .NET is not deterministic between process runs, hence our own FNV-1a.
        private static void LoreColor(string heroId, out uint skinColor, out uint hairColor)
        {
            if (!string.IsNullOrEmpty(heroId) && LoreColors.TryGetValue(heroId, out var known))
            {
                skinColor = known.Skin;
                hairColor = known.Hair;
                return;
            }
            var rng = new Random(unchecked((int)StableHash(heroId ?? "")));
            RandomPonyPalette(rng, out skinColor, out hairColor);
        }

        private static uint StableHash(string s)
        {
            unchecked
            {
                uint hash = 2166136261;
                foreach (char c in s)
                {
                    hash ^= c;
                    hash *= 16777619;
                }
                return hash;
            }
        }

        // Used to be called ApplyRandomTroopColors; now it paints both rank-and-file troops (randomly) and lord heroes
        // (known ones by lore or unknown ones stably random, see LoreColor), so it takes
        // visuals directly, like the other methods of the file, not Agent.
        private static void ApplyPonyColors(object visuals, int race, uint skinColor, uint hairColor)
        {
            var entity = AccessTools.Method(visuals.GetType(), "GetEntity")?.Invoke(visuals, null) as GameEntity;
            var skeleton = entity?.Skeleton;
            if (skeleton == null || !RaceParts().TryGetValue(race, out string[] parts) || parts.Length == 0)
            {
                return;
            }
            foreach (var mesh in FindPrefixMeshes(skeleton, parts[0]))
            {
                mesh.Color = skinColor;
                mesh.Color2 = skinColor;
            }
            // The tail is mane-coloured (HairTinted), the wings and horn are body-coloured (see the 30.09.2026 fix
            // in HairTinted). We paint them directly, not via the donor: the donor (Tint()) has already run
            // inside Attach() above with the old (white) mane/body colour, and it cannot be called a second time
            // without losing the material.
            foreach (string partName in parts)
            {
                uint color = HairTinted.ContainsKey(partName) ? hairColor : skinColor;
                foreach (var mesh in skeleton.GetAllMeshes().Where(m => m != null && m.Name != null
                    && m.Name.StartsWith(partName, StringComparison.OrdinalIgnoreCase)))
                {
                    mesh.Color = color;
                    mesh.Color2 = color;
                }
            }
            if (HairReferenceByRaceId().TryGetValue(race, out string hairRef))
            {
                foreach (var mesh in skeleton.GetAllMeshes().Where(m => m != null && m.Name != null
                    && m.Name.StartsWith(hairRef, StringComparison.OrdinalIgnoreCase)))
                {
                    mesh.Color = hairColor;
                    mesh.Color2 = hairColor;
                }
            }
        }

        // "Skin" meshes (body/legs/head/gloves): the same trick as FindDonor: a common name
        // prefix with any of our race parts (eq_pony_tail -> eq_pony_), except our parts themselves.
        private static IEnumerable<Mesh> FindPrefixMeshes(Skeleton skeleton, string samplePartName)
        {
            int cut = samplePartName.LastIndexOf('_');
            if (cut <= 0)
            {
                yield break;
            }
            string prefix = samplePartName.Substring(0, cut + 1);
            var mine = RaceParts().Values.SelectMany(v => v).ToArray();
            foreach (var m in skeleton.GetAllMeshes())
            {
                if (m != null && m.Name != null && m.Name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)
                    && !mine.Any(n => m.Name.StartsWith(n, StringComparison.OrdinalIgnoreCase)))
                {
                    yield return m;
                }
            }
        }

        // ---------------------------------------------------------------- portraits and the campaign map
        // Outside missions the character is assembled by one and the same factory, AgentVisuals.Create: this is used by
        // the equipment, party and barber windows (CharacterTableau) and the party figures on the map
        // (MobilePartyVisual.HumanAgentVisuals). We hook into it, so the mesh gets onto the skeleton right
        // at creation.
        //
        // It matters WHEN this patch is applied: only from EquestriaPatches.ApplyLate (main menu).
        // Applied at mod load, it triggers the static initialization of AgentVisuals
        // before the game has read the animations, and all ponies in windows lie on their side: exactly the same trouble
        // as with the early Agent patch. Verified 2026-09-18 with the /eqnoparts switch.
        //
        // A child entity instead of the skeleton (GameEntity.CreateEmpty + AddChild) does not work:
        // the pony mesh is skinned, and without a skeleton the engine simply does not draw it: the entity is created,
        // all is well in the log, but there is no tail.
        private const string VisualsType = "TaleWorlds.MountAndBlade.View.AgentVisuals";

        // The race is known only at the moment of creation, and Refresh (equipment change) rebuilds the meshes,
        // so we remember the race per visuals object.
        private static readonly System.Runtime.CompilerServices.ConditionalWeakTable<object, object> RaceOf =
            new System.Runtime.CompilerServices.ConditionalWeakTable<object, object>();

        // The same trick as RaceOf: AgentVisuals.Refresh does not get the data again, only
        // __instance, so the character's StringId (for the lore colour/stable random one, see
        // LoreColor) is remembered here at creation and used on every refresh.
        private static readonly System.Runtime.CompilerServices.ConditionalWeakTable<object, string> CharIdOf =
            new System.Runtime.CompilerServices.ConditionalWeakTable<object, string>();

        public static void ApplyVisuals(Harmony harmony)
        {
            var type = AccessTools.TypeByName(VisualsType);
            var create = type == null ? null : AccessTools.Method(type, "Create");
            if (create == null)
            {
                EquestriaCrashLog.Warn("части тела: AgentVisuals.Create не найден — вне боя хвоста не будет");
                return;
            }
            harmony.Patch(create, postfix: new HarmonyMethod(typeof(EquestriaBodyParts), nameof(AfterVisualsCreate)));
            foreach (var refresh in AccessTools.GetDeclaredMethods(type))
            {
                if (refresh.Name != "Refresh")
                {
                    continue;
                }
                harmony.Patch(refresh, postfix: new HarmonyMethod(typeof(EquestriaBodyParts), nameof(AfterVisualsRefresh)));
            }
            ApplyTableau(harmony);
        }

        // The equipment, party and barber windows draw the character not via AgentVisuals.Create
        // but with their own canvas, CharacterTableau: it keeps the visuals itself in the _agentVisuals field
        // and rebuilds them on an equipment change. So we hook into its tick: the visuals there
        // are not ready right away (loading counters), and putting it on again does not hurt us: Attach
        // checks whether the mesh is already hanging.
        private const string TableauType = "TaleWorlds.MountAndBlade.View.Tableaus.CharacterTableau";

        private static void ApplyTableau(Harmony harmony)
        {
            var type = AccessTools.TypeByName(TableauType);
            var tick = type == null ? null : AccessTools.Method(type, "OnTick");
            if (tick == null)
            {
                EquestriaCrashLog.Warn("части тела: CharacterTableau.OnTick не найден — "
                    + "в окнах снаряжения и отряда хвоста не будет");
                return;
            }
            harmony.Patch(tick, postfix: new HarmonyMethod(typeof(EquestriaBodyParts), nameof(AfterTableauTick)));
        }

        private static void AfterTableauTick(object __instance)
        {
            EquestriaCrashLog.Try("части тела в окне", () =>
            {
                if (__instance == null)
                {
                    return;
                }
                var visuals = AccessTools.Field(__instance.GetType(), "_agentVisuals")?.GetValue(__instance);
                object race = AccessTools.Field(__instance.GetType(), "_race")?.GetValue(__instance);
                if (visuals != null && race is int raceId)
                {
                    // cacheKey is CharacterTableau itself: on an equipment change it recreates _agentVisuals
                    // from scratch (verified by the log) but survives itself, so the hairstyle colour must be remembered by it.
                    // bodyCode is the character's appearance code: the same in all windows, it survives even
                    // a completely new window opened with a helmet already on (cacheKey remembers nothing there,
                    // because the own hairstyle is never built in it).
                    string bodyCode = AccessTools.Field(__instance.GetType(), "_bodyPropertiesCode")
                        ?.GetValue(__instance) as string;
                    Attach(visuals, raceId, "окно", __instance, bodyCode);
                    // The same lore colour/stable random one as in battle (OnAgentBuild); otherwise
                    // in the inventory, party, barber and encyclopedia the lords are white again: the windows assemble
                    // the character with this same canvas (CharacterTableau), not via the mission, and our patch
                    // does not run there. _charStringId is the character's StringId (for heroes it matches
                    // Hero.StringId), found via field reflection; the canvas has no other way to tell
                    // WHO is shown in this window.
                    string charStringId = AccessTools.Field(__instance.GetType(), "_charStringId")
                        ?.GetValue(__instance) as string;
                    ApplyLoreColorIfPony(visuals, raceId, charStringId);
                }
            });
        }

        private static void AfterVisualsCreate(object __result, object[] __args)
        {
            EquestriaCrashLog.Try("части тела вне боя", () =>
            {
                object data = __args != null && __args.Length > 0 ? __args[0] : null;
                object raceValue = data == null ? null : AccessTools.Property(data.GetType(), "RaceData")?.GetValue(data);
                if (__result == null || !(raceValue is int race))
                {
                    return;
                }
                RaceOf.Remove(__result);
                RaceOf.Add(__result, race);
                string charStringId = AccessTools.Property(data.GetType(), "CharacterObjectStringIdData")
                    ?.GetValue(data) as string;
                CharIdOf.Remove(__result);
                if (!string.IsNullOrEmpty(charStringId))
                {
                    CharIdOf.Add(__result, charStringId);
                }
                string owner = __args != null && __args.Length > 1 ? __args[1] as string : null;
                Attach(__result, race, "создание " + (owner ?? "без имени"));
                ApplyLoreColorIfPony(__result, race, charStringId);
            });
        }

        // Party figures on the map (MobilePartyVisual), conversation on the map (EquestriaHelmetFit.
        // AfterMapConversationTick) and other AgentVisuals outside CharacterTableau: the same lore colour/
        // stable random one as in battle and in windows (see OnAgentBuild, AfterTableauTick), otherwise
        // the lords are white there again. internal: also called from EquestriaHelmetFit.
        internal static void ApplyLoreColorIfPony(object visuals, int race, string charStringId)
        {
            bool isPlayer = !string.IsNullOrEmpty(charStringId) && Hero.MainHero != null
                && (charStringId == Hero.MainHero.StringId
                    || charStringId == Hero.MainHero.CharacterObject?.StringId);
            if (race == PonyRaceId() && !string.IsNullOrEmpty(charStringId) && !isPlayer)
            {
                LoreColor(charStringId, out uint skin, out uint hair);
                ApplyPonyColors(visuals, race, skin, hair);
            }
        }

        private static void AfterVisualsRefresh(object __instance)
        {
            EquestriaCrashLog.Try("части тела вне боя (обновление)", () =>
            {
                if (__instance != null && RaceOf.TryGetValue(__instance, out object race) && race is int raceId)
                {
                    Attach(__instance, raceId, "обновление");
                    CharIdOf.TryGetValue(__instance, out string charStringId);
                    ApplyLoreColorIfPony(__instance, raceId, charStringId);
                }
            });
        }
    }
}
