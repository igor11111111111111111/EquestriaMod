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
    // Greetings when meeting on the map: voice and words.
    //
    // Voice. A bandit's or lord's first line in a conversation plays our temporary clip:
    //   bandits - Module\Sounds\bandit_greeting, lords - Module\Sounds\lord_greeting.
    // We intercept the launch of the line's sound itself, not
    // VoiceOverModel: the model is only asked about lines with vanilla voice-over, and our new
    // texts have none. A conversation on the map goes through MapConversationView.MapConversationMission, a
    // conversation in a scene (town, castle) - through CampaignMissionComponent; both are intercepted. Next to the
    // clips lie lip files <name>.xml (tools\make_lipsync.py).
    //
    // Words. The game picks bandit greetings and threats in the dialog conditions of
    // BanditInteractionsCampaignBehavior and puts them in the variables BANDIT_NEUTRAL_GREETING and ROBBERY_*.
    // After the vanilla condition we replace them with our own - jokes about the pony universe plus a threat.
    // Fixed lines (surrender, refusal, leaving) are overridden by id in
    // ModuleData\Languages\<language>\eq_bandits_rus.xml.
    // Lord greetings work the same way, variants in ModuleData\Languages\<language>\eq_lords_rus.xml.
    public static class EquestriaGreetings
    {
        private static readonly Random Random = new Random();
        private static string[] _banditClips;
        private static string[] _lordClips;
        private static object _lastSpeaker;

        // Bandit lines when the player attacks (eq_neutral_N) and when they attack the player
        // (eq_robbery_threat_N, _pay_N, _done_N, _fight_N - four lines of one conversation) live
        // in the language files together with the rest: ModuleData\Languages\<language>\eq_bandits_*.xml.
        // They used to be hardcoded here in Russian and were not translated.

        // The chosen line must not change while the conversation lasts: the game checks dialog conditions
        // several times. So we pick by party and day, not randomly on every call.
        private static int Pick(int count)
        {
            MobileParty party = MobileParty.ConversationParty;
            int seed = (party?.StringId ?? "").GetHashCode() ^ (int)CampaignTime.Now.ToDays;
            return (seed & int.MaxValue) % count;
        }

        // Lines from XML. A vanilla string in ModuleData\Languages\<language>\*.xml has, instead of text,
        // the variable {EQV_NAME}; its variants are strings name_1, name_2, ... (name in lowercase). The list
        // of variables is collected from the files themselves, so new groups need no code changes.
        private static string[] _xmlVariables;

        private static string[] XmlVariables()
        {
            if (_xmlVariables != null)
            {
                return _xmlVariables;
            }
            var found = new System.Collections.Generic.SortedSet<string>();
            // The variables are the same for all languages, but we look in all folders: that way it does not
            // matter which file came first or whether Russian exists at all.
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

        // How many variants a group has: by number order up to the first missing one, so new
        // strings in XML are picked up without a rebuild.
        private static int VariantCount(string group)
        {
            int count = 0;
            while (count < 100 && !string.IsNullOrEmpty(new TextObject("{=" + group + (count + 1) + "}").ToString()))
            {
                count++;
            }
            return count;
        }

        // A variant of a group: random, or by a "seed" (so the line does not change on repeated
        // checks of dialog conditions). null if the group has no strings.
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

        // For each group of XML lines - a random variant (before each conversation).
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

        // ---------------------------------------------------------------- lords
        // Lord greeting: ModuleData\Languages\<language>\eq_lords_rus.xml, groups eq_lord_*.
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
                    // notables and companions: ModuleData\Languages\<language>\eq_npc_rus.xml
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

        // The four lines of one conversation are taken under one number - so the threat, the agreement and
        // the farewell stay one story. If the language has no set at all, the vanilla text remains.
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

        // ---------------------------------------------------------------- voice
        internal static void ApplyVoice(Harmony harmony)
        {
            var targets = new[]
            {
                // Conversation on the map: replace when the line is queued. The first line waits
                // until the conversation window opens, and by the time it plays the speaker is already
                // the player - intercepting in the window itself (MapConversationTableau) missed it.
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

        // End of conversation: the next line will again be the "first".
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
                // only the interlocutor's first line in the conversation
                if (ReferenceEquals(character, _lastSpeaker))
                {
                    return;
                }
                _lastSpeaker = character;
                // bandits - their own clips, all other interlocutors (lords, caravan leaders, headmen,
                // merchants, tavern keepers, companions) - shared ones
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

    // Bandit words: after the vanilla dialog condition we replace the chosen text with our own.
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
            // variables of fixed lines must be set before the first conversation (hideout etc.)
            CampaignEvents.OnSessionLaunchedEvent.AddNonSerializedListener(this, _ =>
                EquestriaCrashLog.Try("реплики из XML", EquestriaGreetings.RollFixedLines));
        }

        public override void SyncData(IDataStore dataStore)
        {
        }
    }

    // Lord greetings: after the vanilla choice we substitute our own text.
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
