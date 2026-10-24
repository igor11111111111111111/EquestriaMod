using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection.Emit;
using HarmonyLib;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.GameComponents;
using TaleWorlds.Core;
using TaleWorlds.Library;

namespace EquestriaMod
{
    // Children of parents of different races (10.10.2026). The vanilla marriage model does not check race, and
    // lords of different peoples marry. At birth the engine takes a son's race from the father, a daughter's from
    // the mother (DefaultHeroCreationModel.GetCharacterTemplateForOffspring), and builds the face of a child of ANY
    // race from the mother's race (GetStaticBodyProperties: GetRandomBodyProperties(Mother.Race, ...)) -
    // a deer son of a pony mother got pony sliders and a pony hairstyle. At the user's request:
    //   - the race of a child of either sex is 50/50 from the mother or from the father;
    //   - the face is random within its race and sex (the range is taken from any template of that
    //     race and sex, as for new lords), not a mix of the parents' faces.
    // Parents of the same race - everything as in vanilla. The engine's soft warning "mother's race != father's
    // race" (HeroCreator.DeliverOffSpring, line 272) is removed below (EquestriaMixedOffspringAssertPatch):
    // it affects nothing, but writes a crash report and opens the TWCrashUploader window on top of the
    // running game (noticed by the user 10.10.2026) - for players it would look like a crash.
    internal static class EquestriaMixedOffspring
    {
        internal static bool MixedParents(Hero mother, Hero father)
        {
            return mother?.CharacterObject != null && father?.CharacterObject != null
                && mother.CharacterObject.Race != father.CharacterObject.Race;
        }

        /// <summary>A template with face variation of the same race and sex: templates of lords, companions,
        /// nobles. Heroes do not fit - their range is collapsed to a single face.</summary>
        internal static CharacterObject RandomFaceTemplate(int race, bool isFemale)
        {
            var pool = CharacterObject.All.Where(c => c != null && !c.IsHero && c.Race == race
                    && c.IsFemale == isFemale && c.Age >= 18   // child records (village_woman_child_*) are skipped
                    && !c.GetBodyPropertiesMin(true).StaticProperties.Equals(c.GetBodyPropertiesMax(true).StaticProperties))
                .ToList();
            return pool.Count == 0 ? null : pool[MBRandom.RandomInt(pool.Count)];
        }
    }

    [HarmonyPatch(typeof(DefaultHeroCreationModel), nameof(DefaultHeroCreationModel.GetCharacterTemplateForOffspring))]
    internal static class EquestriaMixedOffspringRacePatch
    {
        private static bool Prefix(Hero mother, Hero father, bool isOffspringFemale, ref CharacterObject __result)
        {
            if (!EquestriaMixedOffspring.MixedParents(mother, father))
            {
                return true;
            }
            bool fromMother = MBRandom.RandomFloat < 0.5f;
            __result = fromMother ? mother.CharacterObject : father.CharacterObject;
            EquestriaCrashLog.Log($"ребёнок разных рас: {mother.Name} + {father.Name}, "
                + $"{(isOffspringFemale ? "дочь" : "сын")} — раса {(fromMother ? "матери" : "отца")}");
            return false;
        }
    }

    [HarmonyPatch(typeof(DefaultHeroCreationModel), nameof(DefaultHeroCreationModel.GetStaticBodyProperties))]
    internal static class EquestriaMixedOffspringFacePatch
    {
        private static bool Prefix(Hero hero, bool isOffspring, ref StaticBodyProperties __result)
        {
            if (!isOffspring || hero?.CharacterObject == null
                || !EquestriaMixedOffspring.MixedParents(hero.Mother, hero.Father))
            {
                return true;
            }
            try
            {
                int race = hero.CharacterObject.Race;
                var range = hero.CharacterObject.BodyPropertyRange;
                string hairTags = range?.HairTags ?? "";
                string beardTags = range?.BeardTags ?? "";
                string tattooTags = range?.TattooTags ?? "";
                CharacterObject template = EquestriaMixedOffspring.RandomFaceTemplate(race, hero.IsFemale);
                BodyProperties min, max;
                if (template != null)
                {
                    min = template.GetBodyPropertiesMin(true);
                    max = template.GetBodyPropertiesMax(true);
                }
                else
                {
                    // no template - as in vanilla, between the parents' faces, but by the child's race
                    min = hero.Mother.BodyProperties;
                    max = hero.Father.BodyProperties;
                }
                BodyProperties body = BodyProperties.GetRandomBodyProperties(race, hero.IsFemale, min, max, 0,
                    MBRandom.RandomInt(), hairTags, beardTags, tattooTags);
                // Hairstyle/beard/tattoo without tags - by the child's culture and race, as in vanilla
                var model = Campaign.Current.Models.BodyPropertiesModel;
                int gender = hero.IsFemale ? 1 : 0;
                int hair = -1, beard = -1, tattoo = -1;
                if (string.IsNullOrEmpty(hairTags))
                {
                    int[] list = model.GetHairIndicesForCulture(race, gender, hero.Age, hero.Culture);
                    hair = list.Length != 0 ? list.GetRandomElement() : -1;
                }
                if (string.IsNullOrEmpty(beardTags))
                {
                    int[] list = model.GetBeardIndicesForCulture(race, gender, hero.Age, hero.Culture);
                    beard = list.Length != 0 ? list.GetRandomElement() : -1;
                }
                if (string.IsNullOrEmpty(tattooTags))
                {
                    int[] list = model.GetTattooIndicesForCulture(race, gender, hero.Age, hero.Culture);
                    tattoo = list.Length != 0 ? list.GetRandomElement() : -1;
                    if (MBRandom.RandomFloat < FaceGen.GetTattooZeroProbability(race, gender, hero.Age))
                    {
                        tattoo = 0;
                    }
                }
                FaceGen.SetHair(ref body, hair, beard, tattoo);
                __result = body.StaticProperties;
                // the engine gives the child a name later - here hero.Name is still the parent template's name
                EquestriaCrashLog.Log($"ребёнок разных рас ({hero.Mother.Name} + {hero.Father.Name}, "
                    + $"{(hero.IsFemale ? "дочь" : "сын")}): случайное лицо расы "
                    + $"{FaceGen.GetBaseMonsterFromRace(race)?.StringId ?? race.ToString()} по шаблону "
                    + (template?.StringId ?? "лиц родителей"));
                return false;
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Warn("ребёнок разных рас: лицо не собрано, остаётся ванильное — " + e.Message);
                return true;
            }
        }
    }

    // Removes from HeroCreator.DeliverOffSpring the call Debug.SilentAssert(mother.Race == father.Race): for us
    // such pairs are normal. Patching Debug.SilentAssert itself is unreliable (a small method, the JIT inlines
    // it into the caller) - hence a transpiler at the call site: the arguments are popped off the stack.
    [HarmonyPatch(typeof(HeroCreator), nameof(HeroCreator.DeliverOffSpring))]
    internal static class EquestriaMixedOffspringAssertPatch
    {
        // A pregnancy without a husband (Pregnancy.Father == null: the mother got pregnant while unmarried -
        // this happened in the first -MixedBirths test 10.10.2026, the wedding silently did not take place then)
        // crashed the birth with a NullReferenceException. Now the child is born "after the mother" instead of a crash.
        private static void Prefix(Hero mother, ref Hero father)
        {
            if (father == null && mother != null)
            {
                EquestriaCrashLog.Warn($"роды: у {mother.Name} нет отца ребёнка — ребёнок по матери");
                father = mother.Spouse ?? mother;
            }
        }

        private static IEnumerable<CodeInstruction> Transpiler(IEnumerable<CodeInstruction> instructions)
        {
            var silentAssert = AccessTools.Method(typeof(Debug), nameof(Debug.SilentAssert));
            int removed = 0;
            foreach (var code in instructions)
            {
                if (silentAssert != null && code.Calls(silentAssert))
                {
                    // six arguments: condition, message, getDump, file, method, line
                    for (int i = 0; i < 6; i++)
                    {
                        var pop = new CodeInstruction(OpCodes.Pop);
                        if (i == 0)
                        {
                            pop.labels.AddRange(code.labels);
                            pop.blocks.AddRange(code.blocks);
                        }
                        yield return pop;
                    }
                    removed++;
                    continue;
                }
                yield return code;
            }
            EquestriaCrashLog.Log("ребёнок разных рас: проверка движка «раса матери = раса отца» убрана, вызовов " + removed);
        }
    }
}
