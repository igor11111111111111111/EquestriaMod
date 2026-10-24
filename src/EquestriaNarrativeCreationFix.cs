using System;
using System.Collections;
using System.Reflection;
using HarmonyLib;
using TaleWorlds.CampaignSystem.CharacterCreationContent;
using TaleWorlds.MountAndBlade.View;

namespace EquestriaMod
{
    // The "parents"/"childhood"/"youth" portraits in the character creation wizard
    // (SandBox.GauntletUI.CharacterCreation.CharacterCreationNarrativeStageView, SandBox module —
    // not referenced as an assembly in the csproj, so we patch by type name) build AgentVisuals by their
    // OWN, third independent path — not through the usual agent build in a mission (OnAgentBuild) and not
    // through BodyGeneratorView (that one was already patched with an explicit Attach call, see
    // EquestriaHairStyleView — it also explains why without it the skeleton/mesh of non-pony races is
    // not fully set up).
    //
    // Without EquestriaBodyParts.Attach here, for non-pony races (noticed 08.10.2026, first run of the
    // full wizard via -DefaultStart: ponies are fine, for the other races the "parents" portraits
    // and the later ages go into an attack animation and turn
    // horizontal) part of the setup required for the race (fitting the helmet to the head,
    // attaching tail/wings/horn to the skeleton) simply does not run.
    public static class EquestriaNarrativeCreationFix
    {
        private static readonly Type ViewType =
            AccessTools.TypeByName("SandBox.GauntletUI.CharacterCreation.CharacterCreationNarrativeStageView");
        private static readonly FieldInfo VisualsListField = ViewType == null ? null
            : AccessTools.Field(ViewType, "_currentMenuAgentVisuals");

        public static void Apply(Harmony harmony)
        {
            if (ViewType == null)
            {
                EquestriaCrashLog.Warn("портреты мастера: CharacterCreationNarrativeStageView не найден");
                return;
            }
            var method = AccessTools.Method(ViewType, "SpawnHumanNarrativeMenuCharacter");
            if (method == null || VisualsListField == null)
            {
                EquestriaCrashLog.Warn("портреты мастера: SpawnHumanNarrativeMenuCharacter или "
                    + "_currentMenuAgentVisuals не найдены");
                return;
            }
            harmony.Patch(method, postfix: new HarmonyMethod(typeof(EquestriaNarrativeCreationFix), nameof(AfterSpawn)));
            EquestriaCrashLog.Log("портреты мастера: патч на SpawnHumanNarrativeMenuCharacter поставлен");
        }

        private static void AfterSpawn(object __instance, NarrativeMenuCharacter character)
        {
            EquestriaCrashLog.Try("портреты мастера (довеска тела)", () =>
            {
                if (!(VisualsListField.GetValue(__instance) is IList list) || list.Count == 0)
                {
                    return;
                }
                var visuals = list[list.Count - 1] as AgentVisuals;
                if (visuals == null)
                {
                    return;
                }
                string bodyCode = character.BodyProperties.ToString();
                EquestriaBodyParts.Attach(visuals, character.Race,
                    "мастер создания (" + character.StringId + ")", character, bodyCode);
            });
        }
    }
}
