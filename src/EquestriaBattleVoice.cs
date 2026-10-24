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
    // Женский голос в бою почти всем народам: кряхтение при ударе, вскрик от раны, боевые кличи.
    //
    // Зачем. Реплики боя игра берёт не из своих файлов озвучки, а из «определений голоса»
    // (Modules/Native/ModuleData/voice_definitions.xml): male_01..male_08 и female_01..female_05
    // для звукового класса human. Какое достанется агенту, решает движок по полу тела, и жеребцы,
    // трутни, яки и олени хрипели мужскими голосами, чего у нас быть не должно.
    //
    // Кого не трогаем: грифонов и гиппогрифов (KeepOwnVoice) — птичьим народам мужской голос идёт.
    // Список именно на исключение, а не на включение: новая раса получит женский голос сама собой,
    // и о ней не придётся вспоминать.
    //
    // Подробности по всей звуковой части — docs/voices.md (устройство voice_definitions.xml, чем
    // боевые крики отличаются от озвучки диалогов, что нужно для своих голосов расам).
    //
    // Как. Единственная ручка наружу — MBAgentVisuals.SetVoiceDefinitionIndex(индекс, высота);
    // ей же игра назначает голоса лошадям (MountVisualCreator.SetVoiceDefinition). Индексы для
    // класса даёт SkinVoiceManager, но только числами, без имён, поэтому имена читаем сами из
    // voice_definitions.xml: порядок в файле и порядок в ответе движка совпадают, а на всякий
    // случай сверяем длины списков и при расхождении молча не трогаем голоса.
    public class EquestriaBattleVoice : MissionLogic
    {
        // Расы, которым оставляем ванильный выбор голоса по полу.
        private static readonly string[] KeepOwnVoice = { "griffon", "hippogriff" };
        private const string VoiceFile = "voice_definitions.xml";
        private const string FemalePrefix = "female";

        private static HashSet<int> _keep;          // те же расы, но номерами
        private static int[] _female;               // индексы женских определений для класса агента
        private static string _forClass;            // для какого звукового класса они посчитаны
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
                // Голос и высота — по имени агента: у одного и того же бойца они не меняются
                // от боя к бою, а по отряду разнятся.
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
                    // 0 отдаётся и для человека, и когда расы нет вовсе: такую в список не берём,
                    // иначе опечатка в id молча оставила бы без женского голоса половину войска.
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

        /// <summary>Индексы женских определений голоса для звукового класса; null — не разобрались.</summary>
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

        /// <summary>Имена определений голоса звукового класса по порядку из voice_definitions.xml.</summary>
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

        // Файл лежит у Native, а модули могут его дополнять. Порядок обхода тот же, что у игры:
        // сперва Native, потом остальные модули по списку загрузки.
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
