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
    // Дети родителей разных рас (10.10.2026). Ванильная модель браков расу не проверяет, и
    // лорды разных народов женятся. При родах движок берёт расу сына от отца, дочери — от матери
    // (DefaultHeroCreationModel.GetCharacterTemplateForOffspring), а лицо ребёнка ЛЮБОЙ расы
    // строит по расе матери (GetStaticBodyProperties: GetRandomBodyProperties(Mother.Race, …)) —
    // сын-олень от матери-пони получал ползунки и причёску пони. По просьбе пользователя:
    //   - раса ребёнка любого пола — 50 на 50 от матери или от отца;
    //   - лицо — случайное в пределах его расы и пола (диапазон берётся у любого шаблона этой
    //     расы и пола, как у новых лордов), а не смесь лиц родителей.
    // Родители одной расы — всё по-ванильному. Мягкое предупреждение движка «раса матери ≠ раса
    // отца» (HeroCreator.DeliverOffSpring, строка 272) убрано ниже (EquestriaMixedOffspringAssertPatch):
    // оно ни на что не влияет, но пишет отчёт о краше и открывает окно TWCrashUploader поверх
    // работающей игры (замечено пользователем 10.10.2026) — у игроков это выглядело бы как краш.
    internal static class EquestriaMixedOffspring
    {
        internal static bool MixedParents(Hero mother, Hero father)
        {
            return mother?.CharacterObject != null && father?.CharacterObject != null
                && mother.CharacterObject.Race != father.CharacterObject.Race;
        }

        /// <summary>Шаблон с разбросом лица той же расы и пола: шаблоны лордов, спутников,
        /// знати. Герои не годятся — у них диапазон схлопнут в одно лицо.</summary>
        internal static CharacterObject RandomFaceTemplate(int race, bool isFemale)
        {
            var pool = CharacterObject.All.Where(c => c != null && !c.IsHero && c.Race == race
                    && c.IsFemale == isFemale && c.Age >= 18   // детские записи (village_woman_child_*) не берём
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
                    // шаблона нет — как в ванили, между лицами родителей, но по расе ребёнка
                    min = hero.Mother.BodyProperties;
                    max = hero.Father.BodyProperties;
                }
                BodyProperties body = BodyProperties.GetRandomBodyProperties(race, hero.IsFemale, min, max, 0,
                    MBRandom.RandomInt(), hairTags, beardTags, tattooTags);
                // Причёска/борода/татуировка без тегов — по культуре и расе ребёнка, как в ванили
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
                // имя ребёнку движок даёт позже — здесь hero.Name ещё имя шаблона-родителя
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

    // Убирает из HeroCreator.DeliverOffSpring вызов Debug.SilentAssert(мать.Race == отец.Race): для нас
    // такие пары — норма. Патчить сам Debug.SilentAssert ненадёжно (маленький метод, JIT встраивает
    // его в вызывающий код) — поэтому транспайлер на месте вызова: аргументы снимаются со стека.
    [HarmonyPatch(typeof(HeroCreator), nameof(HeroCreator.DeliverOffSpring))]
    internal static class EquestriaMixedOffspringAssertPatch
    {
        // Беременность без мужа (Pregnancy.Father == null: мать забеременела, будучи не замужем —
        // так вышло в первом тесте -MixedBirths 10.10.2026, свадьба тогда молча не состоялась)
        // роняла роды NullReferenceException. Тогда ребёнок рождается «по матери» вместо краша.
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
                    // шесть аргументов: условие, сообщение, getDump, файл, метод, строка
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
