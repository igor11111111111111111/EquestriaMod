using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Xml;
using TaleWorlds.Core;
using TaleWorlds.Engine;
using TaleWorlds.Library;
using TaleWorlds.MountAndBlade;
using FaceGen = TaleWorlds.Core.FaceGen;
using Path = System.IO.Path;

namespace EquestriaMod
{
    // A female voice in battle for almost all peoples: grunting on hits, a cry when wounded, battle cries.
    //
    // Why. The game takes battle barks not from its voice-over files but from "voice definitions"
    // (Modules/Native/ModuleData/voice_definitions.xml): male_01..male_08 and female_01..female_05
    // for the human sound class. Which one an agent gets is decided by the engine by body gender, and stallions,
    // drones, yaks and deer grunted in male voices, which we must not have.
    //
    // Who we leave alone: griffons and hippogriffs (KeepOwnVoice); a male voice suits the bird peoples.
    // The list is for exclusion, not inclusion: a new race gets the female voice by itself,
    // and nobody has to remember about it.
    //
    // Details on the whole sound side are in docs/voices.md (how voice_definitions.xml works, how
    // battle cries differ from dialogue voice-over, what is needed for races' own voices).
    //
    // How. The only handle exposed is MBAgentVisuals.SetVoiceDefinitionIndex(index, pitch);
    // the game uses it to assign voices to horses too (MountVisualCreator.SetVoiceDefinition). The indices for
    // a class come from SkinVoiceManager, but only as numbers, without names, so we read the names ourselves from
    // voice_definitions.xml: the order in the file and the order in the engine's answer match, and just in
    // case we compare the list lengths and on a mismatch silently leave the voices alone.
    public class EquestriaBattleVoice : MissionLogic
    {
        // Races that keep the vanilla choice of voice by gender.
        private static readonly string[] KeepOwnVoice = { "griffon", "hippogriff" };
        private const string VoiceFile = "voice_definitions.xml";
        private const string FemalePrefix = "female";

        private static HashSet<int> _keep;          // the same races, but as numbers
        private static int[] _female;               // indices of female definitions for the agent's class
        private static string _forClass;            // which sound class they were computed for
        private static bool _complained;

        public override void OnAgentBuild(Agent agent, Banner banner)
        {
            EquestriaCrashLog.Try("женский голос в бою", () =>
            {
                if (agent == null || agent.IsMount || agent.Character == null || agent.IsFemale)
                {
                    return;
                }
                if (KeepsOwnVoice(agent.Character.Race))
                {
                    return;
                }
                var visuals = agent.AgentVisuals;
                if (visuals == null)
                {
                    return;
                }
                var voices = FemaleVoices(agent.GetSoundAndCollisionInfoClassName());
                if (voices == null || voices.Length == 0)
                {
                    return;
                }
                // Voice and pitch are by the agent's name: for one and the same soldier they do not change
                // from battle to battle, but they vary across a troop.
                int seed = Math.Abs((agent.Name ?? "боец").GetHashCode());
                visuals.SetVoiceDefinitionIndex(voices[seed % voices.Length],
                    (seed % 1000) / 1000f);
            });
        }

        private static bool KeepsOwnVoice(int race)
        {
            if (_keep == null)
            {
                _keep = new HashSet<int>();
                foreach (var id in KeepOwnVoice)
                {
                    // 0 is returned both for the human and when the race does not exist at all: such a race is not
                    // put into the list, otherwise a typo in the id would silently leave half the army without a female voice.
                    int index = FaceGen.GetRaceOrDefault(id);
                    if (index > 0)
                    {
                        _keep.Add(index);
                    }
                    else
                    {
                        EquestriaCrashLog.Warn("женский голос в бою: расы " + id + " в игре нет");
                    }
                }
                EquestriaCrashLog.Log("женский голос в бою: со своим голосом остаются расы "
                    + string.Join(", ", KeepOwnVoice));
            }
            return _keep.Contains(race);
        }

        /// <summary>Indices of female voice definitions for a sound class; null means we could not work it out.</summary>
        private static int[] FemaleVoices(string soundClass)
        {
            if (string.IsNullOrEmpty(soundClass))
            {
                return null;
            }
            if (_female != null && _forClass == soundClass)
            {
                return _female;
            }
            _forClass = soundClass;
            _female = null;

            int count = SkinVoiceManager.GetVoiceDefinitionCountWithMonsterSoundAndCollisionInfoClassName(soundClass);
            if (count <= 0)
            {
                return null;
            }
            var indices = new int[count];
            SkinVoiceManager.GetVoiceDefinitionListWithMonsterSoundAndCollisionInfoClassName(soundClass, indices);

            var names = NamesOfClass(soundClass);
            if (names.Count != count)
            {
                if (!_complained)
                {
                    _complained = true;
                    EquestriaCrashLog.Warn($"женский голос в бою: в {VoiceFile} для класса {soundClass}"
                        + $" описано {names.Count} голосов, а движок знает {count} — голоса не трогаем");
                }
                return null;
            }
            _female = Enumerable.Range(0, count)
                .Where(i => names[i].StartsWith(FemalePrefix, StringComparison.OrdinalIgnoreCase))
                .Select(i => indices[i]).ToArray();
            EquestriaCrashLog.Log($"женский голос в бою: класс {soundClass}, женских определений"
                + $" {_female.Length} из {count}");
            return _female;
        }

        /// <summary>Names of a sound class's voice definitions in order from voice_definitions.xml.</summary>
        private static List<string> NamesOfClass(string soundClass)
        {
            var names = new List<string>();
            foreach (var path in VoiceFiles())
            {
                var document = new XmlDocument();
                try
                {
                    document.Load(path);
                }
                catch (Exception error)
                {
                    EquestriaCrashLog.Warn($"женский голос в бою: {path} не прочитан — {error.Message}");
                    continue;
                }
                foreach (XmlNode node in document.SelectNodes("//voice_definition"))
                {
                    var forClass = node.Attributes?["sound_and_collision_info_class"]?.Value;
                    var name = node.Attributes?["name"]?.Value;
                    if (forClass == soundClass && !string.IsNullOrEmpty(name))
                    {
                        names.Add(name);
                    }
                }
            }
            return names;
        }

        // The file lives in Native, and modules may extend it. The traversal order is the same as the game's:
        // Native first, then the other modules in load order.
        private static IEnumerable<string> VoiceFiles()
        {
            var modules = Path.Combine(BasePath.Name, "Modules");
            var order = new List<string> { "Native" };
            order.AddRange(Utilities.GetModulesNames().Where(m => m != "Native"));
            foreach (var module in order)
            {
                var path = Path.Combine(modules, module, "ModuleData", VoiceFile);
                if (File.Exists(path))
                {
                    yield return path;
                }
            }
        }
    }
}
