using System;
using System.IO;
using System.Linq;
using System.Reflection;
using HarmonyLib;
using Helpers;
using SandBox.Missions.MissionLogics;
using SandBox.View.Map;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.CampaignBehaviors;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.Core;
using TaleWorlds.Localization;
using TaleWorlds.MountAndBlade;
using Path = System.IO.Path;

namespace EquestriaMod
{
    // Приветствия при встрече на карте: голос и слова.
    //
    // Голос. Первая реплика разбойника или лорда в разговоре звучит нашим временным клипом:
    //   разбойники — Module\Sounds\bandit_greeting, лорды — Module\Sounds\lord_greeting.
    // Перехватываем сам запуск звука реплики, а не
    // VoiceOverModel: модель спрашивают только про реплики с ванильной озвучкой, а у наших новых
    // текстов её нет. Разговор на карте идёт через MapConversationView.MapConversationMission, разговор в
    // сцене (город, замок) — через CampaignMissionComponent; перехвачены оба. Рядом с клипами лежат файлы губ <имя>.xml (tools\make_lipsync.py).
    //
    // Слова. Приветствия и угрозы разбойников игра выбирает в условиях диалога
    // BanditInteractionsCampaignBehavior и кладёт в переменные BANDIT_NEUTRAL_GREETING и ROBBERY_*.
    // После ванильного условия подменяем их своими — шутки о вселенной пони с угрозой. Постоянные реплики
    // (сдача, отказ, уход) перекрыты по id в ModuleData\Languages\<язык>\eq_bandits_rus.xml.
    // Приветствия лордов — так же, варианты в ModuleData\Languages\<язык>\eq_lords_rus.xml.
    public static class EquestriaGreetings
    {
        private static readonly Random Random = new Random();
        private static string[] _banditClips;
        private static string[] _lordClips;
        private static object _lastSpeaker;

        // Реплики разбойников при нападении игрока (eq_neutral_N) и при нападении на игрока
        // (eq_robbery_threat_N, _pay_N, _done_N, _fight_N — четыре строки одного разговора) лежат
        // в языковых файлах вместе с остальными: ModuleData\Languages\<язык>\eq_bandits_*.xml.
        // Раньше они были зашиты здесь по-русски и не переводились.

        // Выбор реплики не должен меняться, пока длится разговор: условия диалога игра проверяет
        // несколько раз. Поэтому выбираем по отряду и дню, а не случайно при каждом вызове.
        private static int Pick(int count)
        {
            MobileParty party = MobileParty.ConversationParty;
            int seed = (party?.StringId ?? "").GetHashCode() ^ (int)CampaignTime.Now.ToDays;
            return (seed & int.MaxValue) % count;
        }

        // Реплики из XML. У ванильной строки в ModuleData\Languages\<язык>\*.xml вместо текста стоит
        // переменная {EQV_ИМЯ}; её варианты — строки имя_1, имя_2, ... (имя строчными). Список
        // переменных собираем из самих файлов, так что новые группы не требуют правки кода.
        private static string[] _xmlVariables;

        private static string[] XmlVariables()
        {
            if (_xmlVariables != null)
            {
                return _xmlVariables;
            }
            var found = new System.Collections.Generic.SortedSet<string>();
            // Переменные одни на все языки, но смотрим все папки: так не важно, какой файл первым
            // попался и есть ли вообще русский.
            string folder = Path.Combine(TaleWorlds.ModuleManager.ModuleHelper.GetModuleFullPath("EquestriaMod"),
                "ModuleData", "Languages");
            if (Directory.Exists(folder))
            {
                var pattern = new System.Text.RegularExpressions.Regex(@"text=""\{(EQV_[A-Z0-9_]+)\}""");
                foreach (string file in Directory.GetFiles(folder, "*.xml", SearchOption.AllDirectories))
                {
                    foreach (System.Text.RegularExpressions.Match m in pattern.Matches(File.ReadAllText(file)))
                    {
                        found.Add(m.Groups[1].Value);
                    }
                }
            }
            _xmlVariables = found.ToArray();
            EquestriaCrashLog.Log($"реплики из XML: групп {_xmlVariables.Length}");
            return _xmlVariables;
        }

        // Сколько вариантов в группе: по порядку номеров до первого отсутствующего, так что новые
        // строки в XML подхватываются без пересборки.
        private static int VariantCount(string group)
        {
            int count = 0;
            while (count < 100 && !string.IsNullOrEmpty(new TextObject("{=" + group + (count + 1) + "}").ToString()))
            {
                count++;
            }
            return count;
        }

        // Вариант группы: случайный, либо по «зерну» (чтобы реплика не менялась при повторных
        // проверках условий диалога). null — если в группе нет строк.
        private static TextObject Variant(string group, int? seed = null)
        {
            int count = VariantCount(group);
            if (count == 0)
            {
                return null;
            }
            int index = seed.HasValue ? (seed.Value & int.MaxValue) % count : Random.Next(count);
            return new TextObject("{=" + group + (index + 1) + "}");
        }

        // Для каждой группы реплик из XML — случайный вариант (перед каждым разговором).
        internal static void RollFixedLines()
        {
            foreach (string variable in XmlVariables())
            {
                TextObject text = Variant(variable.Substring(4).ToLowerInvariant() + "_");
                if (text != null)
                {
                    MBTextManager.SetTextVariable(variable, text);
                }
            }
        }

        // ---------------------------------------------------------------- лорды
        // Приветствие лорда: ModuleData\Languages\<язык>\eq_lords_rus.xml, группы eq_lord_*.
        internal static void SetLordGreeting(string variable, string group)
        {
            Hero hero = Hero.OneToOneConversationHero;
            if (hero == null)
            {
                return;
            }
            bool isLord = hero.CharacterObject.Occupation == Occupation.Lord;
            if (!isLord && group == "eq_lord_attack_")
            {
                return;
            }
            if (group == null)
            {
                bool first = Campaign.Current.ConversationManager.CurrentConversationIsFirst;
                if (isLord)
                {
                    bool atWar = hero.MapFaction != null && Hero.MainHero.MapFaction != null
                        && FactionManager.IsAtWarAgainstFaction(hero.MapFaction, Hero.MainHero.MapFaction);
                    int relation = CharacterRelationManager.GetHeroRelation(Hero.MainHero, hero);
                    group = first ? "eq_lord_meet_"
                        : relation >= 20 && !atWar ? "eq_lord_friend_"
                        : relation <= -10 || atWar ? "eq_lord_cold_"
                        : "eq_lord_greet_";
                }
                else
                {
                    // знатные горожане и спутники: ModuleData\Languages\<язык>\eq_npc_rus.xml
                    string kind = hero.IsWanderer ? "wanderer" : hero.IsHeadman ? "headman" : hero.IsMerchant ? "merchant"
                        : hero.IsArtisan ? "artisan" : hero.IsGangLeader ? "gangleader" : hero.IsPreacher ? "preacher"
                        : hero.IsRuralNotable ? "ruralnotable" : null;
                    if (kind == null)
                    {
                        return;
                    }
                    string stage = first ? "meet_" : "greet_";
                    group = VariantCount("eq_" + kind + "_" + stage) > 0 ? "eq_" + kind + "_" + stage : "eq_notable_" + stage;
                }
            }
            Settlement place = hero.CurrentSettlement ?? hero.HomeSettlement;
            MBTextManager.SetTextVariable("EQ_SETTLEMENT", place?.Name ?? TextObject.GetEmpty());
            TextObject text = Variant(group, (hero.StringId + group).GetHashCode() ^ (int)CampaignTime.Now.ToDays);
            if (text == null)
            {
                return;
            }
            StringHelpers.SetCharacterProperties("PLAYER", Hero.MainHero.CharacterObject);
            StringHelpers.SetCharacterProperties("LORD", hero.CharacterObject);
            MBTextManager.SetTextVariable("EQ_LORD_CLAN", hero.Clan?.Name ?? TextObject.GetEmpty());
            MBTextManager.SetTextVariable("EQ_LORD_KINGDOM", hero.MapFaction?.Name ?? hero.Clan?.Name ?? TextObject.GetEmpty());
            MBTextManager.SetTextVariable(variable, text);
        }

        internal static void SetNeutralGreeting()
        {
            RollFixedLines();
            int count = VariantCount("eq_neutral_");
            if (count > 0)
            {
                MBTextManager.SetTextVariable("BANDIT_NEUTRAL_GREETING",
                    new TextObject("{=eq_neutral_" + (Pick(count) + 1) + "}"));
            }
        }

        // Четыре реплики одного разговора берутся под одним номером — так угроза, согласие и прощание
        // остаются одной историей. Если в языке нет ни одного набора, остаётся ванильный текст.
        internal static void SetRobbery()
        {
            RollFixedLines();
            int count = VariantCount("eq_robbery_threat_");
            if (count == 0)
            {
                return;
            }
            string number = (Pick(count) + 1).ToString();
            MBTextManager.SetTextVariable("ROBBERY_THREAT", new TextObject("{=eq_robbery_threat_" + number + "}"));
            MBTextManager.SetTextVariable("ROBBERY_PAY_AGREEMENT", new TextObject("{=eq_robbery_pay_" + number + "}"));
            MBTextManager.SetTextVariable("ROBBERY_CONCLUSION", new TextObject("{=eq_robbery_done_" + number + "}"));
            MBTextManager.SetTextVariable("ROBBERY_START_FIGHT", new TextObject("{=eq_robbery_fight_" + number + "}"));
        }

        // ---------------------------------------------------------------- голос
        internal static void ApplyVoice(Harmony harmony)
        {
            var targets = new[]
            {
                // Разговор на карте: подменяем, когда реплика ставится в очередь. Первая реплика ждёт,
                // пока откроется окно разговора, и к моменту проигрывания говорящим уже числится
                // игрок — перехват в самом окне (MapConversationTableau) её пропускал.
                AccessTools.Method(typeof(MapConversationView.MapConversationMission),
                    "TaleWorlds.CampaignSystem.ICampaignMission.OnConversationPlay"),
                AccessTools.Method(typeof(CampaignMissionComponent),
                    "TaleWorlds.CampaignSystem.ICampaignMission.OnConversationPlay"),
            };
            foreach (MethodInfo target in targets)
            {
                if (target == null)
                {
                    EquestriaCrashLog.Log("приветствия: не найден метод OnConversationPlay");
                    continue;
                }
                harmony.Patch(target, prefix: new HarmonyMethod(typeof(EquestriaGreetings), nameof(VoicePrefix)));
            }
        }

        // Конец разговора: следующая реплика снова будет «первой».
        internal static void ResetConversation()
        {
            _lastSpeaker = null;
        }

        private static void VoicePrefix(ref string soundPath)
        {
            try
            {
                IAgent speaker = Campaign.Current?.ConversationManager?.SpeakerAgent;
                var character = speaker?.Character as CharacterObject;
                if (character == null || character == CharacterObject.PlayerCharacter)
                {
                    return;
                }
                // только первая реплика собеседника в разговоре
                if (ReferenceEquals(character, _lastSpeaker))
                {
                    return;
                }
                _lastSpeaker = character;
                // разбойники — свои клипы, все остальные собеседники (лорды, караванщики, старосты,
                // торговцы, трактирщики, спутники) — общие
                string[] clips = IsBandit(character) ? BanditClips() : LordClips();
                if (clips == null || clips.Length == 0)
                {
                    return;
                }
                string clip = clips[Random.Next(clips.Length)];
                EquestriaCrashLog.Log($"приветствие {character.Name}: {Path.GetFileName(clip)} вместо "
                    + (string.IsNullOrEmpty(soundPath) ? "тишины" : Path.GetFileName(soundPath)));
                soundPath = clip;
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Log("приветствие: ошибка " + e.Message);
            }
        }

        private static bool IsBandit(CharacterObject character)
        {
            if (character.Occupation == Occupation.Bandit || (character.Culture != null && character.Culture.IsBandit))
            {
                return true;
            }
            return MobileParty.ConversationParty?.IsBandit == true && !character.IsHero;
        }

        private static string[] BanditClips() => _banditClips ?? (_banditClips = Clips("bandit_greeting"));

        private static string[] LordClips() => _lordClips ?? (_lordClips = Clips("lord_greeting"));

        private static string[] Clips(string folderName)
        {
            string bin = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
            string folder = Path.GetFullPath(Path.Combine(bin, "..", "..", "Sounds", folderName));
            string[] files = Directory.Exists(folder)
                ? Directory.GetFiles(folder, "*.wav").OrderBy(f => f).ToArray()
                : new string[0];
            EquestriaCrashLog.Log($"приветствия: клипов {files.Length} в {folder}");
            return files;
        }
    }

    // Слова разбойников: после ванильного условия диалога подменяем выбранный текст своим.
    [HarmonyPatch(typeof(BanditInteractionsCampaignBehavior), "bandit_neutral_greet_on_condition")]
    public static class BanditNeutralGreetingText
    {
        private static void Postfix(bool __result)
        {
            if (__result)
            {
                EquestriaCrashLog.Try("приветствие разбойников", EquestriaGreetings.SetNeutralGreeting);
            }
        }
    }

    [HarmonyPatch(typeof(BanditInteractionsCampaignBehavior), "bandit_start_defender_condition")]
    public static class BanditRobberyText
    {
        private static void Postfix(bool __result)
        {
            if (__result)
            {
                EquestriaCrashLog.Try("угроза разбойников", EquestriaGreetings.SetRobbery);
            }
        }
    }

    public class EquestriaGreetingsBehavior : CampaignBehaviorBase
    {
        public override void RegisterEvents()
        {
            CampaignEvents.ConversationEnded.AddNonSerializedListener(this, _ =>
            {
                EquestriaGreetings.ResetConversation();
                EquestriaCrashLog.Try("реплики из XML", EquestriaGreetings.RollFixedLines);
            });
            // переменные постоянных реплик должны быть заданы до первого разговора (логово и пр.)
            CampaignEvents.OnSessionLaunchedEvent.AddNonSerializedListener(this, _ =>
                EquestriaCrashLog.Try("реплики из XML", EquestriaGreetings.RollFixedLines));
        }

        public override void SyncData(IDataStore dataStore)
        {
        }
    }

    // Приветствия лордов: после ванильного выбора подставляем свой текст.
    [HarmonyPatch(typeof(LordConversationsCampaignBehavior), "conversations_set_voiced_line")]
    public static class LordVoicedLineText
    {
        private static void Postfix()
        {
            EquestriaCrashLog.Try("приветствие лорда", () => EquestriaGreetings.SetLordGreeting("VOICED_LINE", null));
        }
    }

    [HarmonyPatch(typeof(LordConversationsCampaignBehavior), "conversation_lord_attacking_on_condition")]
    public static class LordAttackText
    {
        private static void Postfix(bool __result)
        {
            if (__result)
            {
                EquestriaCrashLog.Try("угроза лорда",
                    () => EquestriaGreetings.SetLordGreeting("VOICED_LINE", "eq_lord_attack_"));
            }
        }
    }

    [HarmonyPatch(typeof(LordConversationsCampaignBehavior), "conversation_lord_greets_under_24_hours_on_condition")]
    public static class LordShortAbsenceText
    {
        private static void Postfix(bool __result)
        {
            if (__result)
            {
                EquestriaCrashLog.Try("короткое приветствие лорда",
                    () => EquestriaGreetings.SetLordGreeting("SHORT_ABSENCE_GREETING", "eq_lord_short_"));
            }
        }
    }
}
