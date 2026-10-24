using System;
using System.Collections;
using System.Reflection;
using HarmonyLib;
using TaleWorlds.CampaignSystem.CharacterCreationContent;
using TaleWorlds.MountAndBlade.View;

namespace EquestriaMod
{
    // Портреты "родителей"/"детства"/"юности" в мастере создания персонажа
    // (SandBox.GauntletUI.CharacterCreation.CharacterCreationNarrativeStageView, модуль SandBox —
    // в csproj не подключён как сборка, патчим по имени типа) строят AgentVisuals СВОИМ, третьим
    // по счёту независимым путём — не через обычную сборку агента в миссии (OnAgentBuild) и не
    // через BodyGeneratorView (тот уже патчили явным вызовом Attach, см. EquestriaHairStyleView —
    // там же объяснение, почему без него скелет/меш у не-пони рас настроен не полностью).
    //
    // Без EquestriaBodyParts.Attach здесь у не-пони рас (замечено 08.10.2026, первый прогон
    // полного мастера через -DefaultStart: у пони всё нормально, у остальных рас портреты
    // "родителей" и дальше по возрастам уходят в атакующую анимацию и разворачиваются
    // горизонтально) часть обязательной для расы настройки (подгонка шлема под голову,
    // довеска хвоста/крыльев/рога на скелет) просто не выполняется.
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
