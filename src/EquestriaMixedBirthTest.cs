using System;
using System.Collections.Generic;
using System.Linq;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Actions;
using TaleWorlds.CampaignSystem.GameState;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.MountAndBlade;

namespace EquestriaMod
{
    // Проверка детей от родителей разных рас (src/EquestriaMixedOffspring.cs), 10.10.2026.
    //   /eqmixedbirths:N   дождавшись карты, женит N пар героев разных рас (по одной паре на
    //                      сочетание «раса жены + раса мужа», пока хватает), каждая пара сразу
    //                      рожает одного ребёнка (HeroCreator.DeliverOffSpring — тот же вызов, что
    //                      у обычных родов), а потом жена беременеет по-настоящему. Вместе с
    //                      /eqlongrun (run.ps1 -MixedBirths) время крутится дальше, и через
    //                      ~36 дней беременности дети рождаются уже обычным путём движка.
    // В журнал (eq_exceptions.log) — строки «смешанные роды: …»: пара, пол, раса ребёнка и чья
    // она, культура, номер причёски; плюс строки самого патча «ребёнок разных рас: …».
    public static class EquestriaMixedBirthTest
    {
        private const string Prefix = "/eqmixedbirths:";
        private static int _pairs;
        private static bool _done;
        private static DateTime _mapSeenAt = DateTime.MinValue;
        private static readonly object Owner = new object();
        private static int _natural;

        public static void CheckRequest()
        {
            foreach (string arg in Environment.GetCommandLineArgs())
            {
                if (arg.StartsWith(Prefix, StringComparison.OrdinalIgnoreCase)
                    && int.TryParse(arg.Substring(Prefix.Length), out int pairs) && pairs > 0)
                {
                    _pairs = pairs;
                    EquestriaCrashLog.Log("смешанные роды: запрошено пар " + pairs);
                }
            }
        }

        public static void Tick()
        {
            if (_pairs <= 0 || _done)
            {
                return;
            }
            if (!(GameStateManager.Current?.ActiveState is MapState) || Campaign.Current == null)
            {
                return;
            }
            if (_mapSeenAt == DateTime.MinValue)
            {
                _mapSeenAt = DateTime.UtcNow;
                return;
            }
            if ((DateTime.UtcNow - _mapSeenAt).TotalSeconds < 2)
            {
                return;
            }
            _done = true;
            EquestriaCrashLog.Try("смешанные роды", Run);
        }

        private static string RaceName(int race)
        {
            string[] names = TaleWorlds.Core.FaceGen.GetRaceNames();
            return race >= 0 && race < names.Length ? names[race] : race.ToString();
        }

        private static bool Free(Hero h)
        {
            return h != null && h.IsAlive && !h.IsChild && h.Spouse == null && h != Hero.MainHero
                && !h.IsPrisoner && h.CharacterObject != null && (h.IsLord || h.IsWanderer)
                && h.Clan != null && h.Clan != Clan.PlayerClan && !h.IsPregnant;
        }

        private static void Run()
        {
            CampaignEvents.OnGivenBirthEvent.AddNonSerializedListener(Owner, OnBirth);
            var heroes = Hero.AllAliveHeroes.Where(Free).ToList();
            var marriage = Campaign.Current.Models.MarriageModel;
            var wives = heroes.Where(h => h.IsFemale && h.Age >= 18 && h.Age <= 38).ToList();
            var husbands = heroes.Where(h => !h.IsFemale && h.Age >= 18).ToList();
            EquestriaCrashLog.Note($"смешанные роды: свободных невест {wives.Count}, женихов {husbands.Count}");

            // По одной паре на каждое сочетание рас — так в журнале видны все расы сразу
            var used = new HashSet<Hero>();
            var combos = new HashSet<string>();
            var pairs = new List<(Hero wife, Hero husband)>();
            foreach (var wife in wives.OrderBy(_ => MBRandom.RandomInt()))
            {
                if (pairs.Count >= _pairs)
                {
                    break;
                }
                // Только пары, которых движок готов поженить: иначе MarriageAction молча ничего не
                // делает (родня, оба главы кланов, …), а беременность без мужа роняет роды.
                var husband = husbands.Where(m => !used.Contains(m)
                        && m.CharacterObject.Race != wife.CharacterObject.Race
                        && marriage.IsCoupleSuitableForMarriage(m, wife)
                        && !combos.Contains(wife.CharacterObject.Race + ">" + m.CharacterObject.Race))
                    .OrderBy(_ => MBRandom.RandomInt()).FirstOrDefault();
                if (husband == null)
                {
                    continue;
                }
                used.Add(husband);
                combos.Add(wife.CharacterObject.Race + ">" + husband.CharacterObject.Race);
                pairs.Add((wife, husband));
            }

            int married = 0, born = 0;
            foreach (var (wife, husband) in pairs)
            {
                string pair = $"{wife.Name} ({RaceName(wife.CharacterObject.Race)}) + {husband.Name} ({RaceName(husband.CharacterObject.Race)})";
                try
                {
                    MarriageAction.Apply(husband, wife, false);
                    if (wife.Spouse != husband)
                    {
                        EquestriaCrashLog.Warn($"смешанные роды: свадьба {pair} не состоялась — движок отказал");
                        continue;
                    }
                    married++;
                }
                catch (Exception e)
                {
                    EquestriaCrashLog.Warn($"смешанные роды: свадьба {pair} не удалась — {e.GetType().Name}: {e.Message}");
                    continue;
                }
                try
                {
                    bool daughter = MBRandom.RandomFloat < 0.5f;
                    Hero child = HeroCreator.DeliverOffSpring(wife, husband, daughter);
                    born++;
                    EquestriaCrashLog.Log("смешанные роды (сразу): " + pair + " → " + Describe(child, wife, husband));
                }
                catch (Exception e)
                {
                    EquestriaCrashLog.Warn($"смешанные роды: ребёнок {pair} не родился — {e.GetType().Name}: {e.Message}");
                }
                try
                {
                    if (!wife.IsPregnant)
                    {
                        MakePregnantAction.Apply(wife);
                    }
                }
                catch (Exception e)
                {
                    EquestriaCrashLog.Warn($"смешанные роды: беременность {pair} — {e.GetType().Name}: {e.Message}");
                }
            }
            EquestriaCrashLog.Note($"смешанные роды: пар {pairs.Count}, свадеб {married}, детей сразу {born}, "
                + $"беременных {pairs.Count(p => p.wife.IsPregnant)} — обычные роды через ~"
                + $"{(int)Campaign.Current.Models.PregnancyModel.PregnancyDurationInDays} дн.");
        }

        private static void OnBirth(Hero mother, List<Hero> children, int stillborn)
        {
            if (mother == null || children == null)
            {
                return;
            }
            foreach (var child in children)
            {
                Hero father = child?.Father;
                if (child == null || father == null || mother.CharacterObject.Race == father.CharacterObject.Race)
                {
                    continue;
                }
                _natural++;
                EquestriaCrashLog.Note($"смешанные роды (обычные, №{_natural}): {mother.Name} ({RaceName(mother.CharacterObject.Race)}) + "
                    + $"{father.Name} ({RaceName(father.CharacterObject.Race)}) → " + Describe(child, mother, father));
            }
            if (stillborn > 0)
            {
                EquestriaCrashLog.Log($"смешанные роды: у {mother.Name} мертворождённых {stillborn}");
            }
        }

        private static string Describe(Hero child, Hero mother, Hero father)
        {
            if (child == null)
            {
                return "ребёнка нет";
            }
            int race = child.CharacterObject.Race;
            string whose = race == mother.CharacterObject.Race ? "матери" : race == father.CharacterObject.Race ? "отца" : "ЧУЖАЯ";
            int hair = -1;
            try
            {
                var face = FaceGenerationParams.Create();
                MBBodyProperties.GetParamsFromKey(ref face, child.BodyProperties, false, false);
                hair = face.CurrentHair;
            }
            catch (Exception)
            {
            }
            return $"{child.Name}, {(child.IsFemale ? "дочь" : "сын")}, раса {RaceName(race)} ({whose}), "
                + $"культура {child.Culture?.StringId}, клан {child.Clan?.StringId}, причёска №{hair}";
        }
    }
}
