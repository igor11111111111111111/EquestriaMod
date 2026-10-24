using System.Linq;
using System.Reflection;
using HarmonyLib;
using Helpers;
using SandBox.View.Map;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.CampaignBehaviors;
using TaleWorlds.Core;

namespace EquestriaMod
{
    // Патчи Harmony: подмена методов игры на лету там, где официального крючка нет.
    //
    // Библиотека едет вместе с модом (0Harmony.dll кладётся рядом с нашей DLL), отдельный модуль
    // Bannerlord.Harmony ставить не нужно.
    //
    // Правило: сначала ищем законный способ — XML, поведение кампании, модель, XSLT. Патч ставим
    // только когда упёрлись. Каждый патч привязан к сигнатуре метода игры и переживает не всякое
    // обновление, поэтому их должно быть мало и каждый должен быть объяснён.
    public static class EquestriaPatches
    {
        private const string Id = "com.equestria.bannerlord";

        private static Harmony _harmony;

        // Доступ для патчей, которые нельзя поставить ни в Apply(), ни в ApplyLate() — см.
        // RaceAssimilationTooltipPatch (ставится лениво на первом тике кампании, не здесь).
        public static Harmony Instance => _harmony;

        public static void Apply()
        {
            if (_harmony != null)
            {
                return;
            }
            EquestriaCrashLog.Try("подключение патчей Harmony", () =>
            {
                _harmony = new Harmony(Id);
                _harmony.PatchAll(Assembly.GetExecutingAssembly());
                EquestriaLoadingScreen.Apply(_harmony);
                // Надпись о сборке шейдеров на самом загрузочном экране (см. класс)
                EquestriaLoadingNote.Apply(_harmony);
                EquestriaEnglishTexts.Apply(_harmony);
                // Видео на фоне главного меню — только наше (см. класс)
                EquestriaMenuVideo.Apply(_harmony);
                var names = _harmony.GetPatchedMethods()
                    .Select(m => m.DeclaringType.Name + "." + m.Name).ToList();
                EquestriaCrashLog.Log($"Harmony: патчей применено {names.Count}"
                    + (names.Count > 0 ? " — " + string.Join(", ", names) : ""));
            });
        }

        private static bool _lateApplied;

        // Патчи на игровые классы боя (Agent, MBSoundEvent) ставим позже — когда игра уже
        // загрузила свои данные, в том числе анимации. Если патчить их при загрузке мода,
        // Harmony раньше времени запускает статическую инициализацию этих классов, и таблица
        // действий строится без анимаций пони: в окнах просмотра (отряд, инвентарь) все пони
        // лежали набок. Вызывается при показе главного меню.
        public static void ApplyLate()
        {
            if (_lateApplied || _harmony == null)
            {
                return;
            }
            _lateApplied = true;
            EquestriaCrashLog.Try("поздние патчи Harmony", () =>
            {
                // Части тела вне миссий (портреты, карта, цирюльник): меш вешаем отдельной дочерней
                // сущностью, скелет не трогаем. Патч ставим именно здесь, а не при загрузке мода:
                // ранний патч AgentVisuals запускает статическую инициализацию класса до того, как
                // игра прочитала анимации, и все пони в окнах лежат набок (проверено 2026-09-18,
                // ключ /eqnoparts для сравнения). В миссиях нужен скиннинг — там OnAgentBuild.
                EquestriaBodyParts.ApplyVisuals(_harmony);
                // Шлем под крупную голову расы — сюда же: цепляется к той же сборке внешности
                EquestriaHelmetFit.Apply(_harmony);
                // Кнопки "Сплошная/Полосатая" поверх экрана внешности пони
                EquestriaHairStyleView.Apply(_harmony);
                // Портреты "родителей"/детства/юности в мастере создания персонажа — третий
                // независимый путь сборки AgentVisuals, тоже нуждается в EquestriaBodyParts.Attach
                EquestriaNarrativeCreationFix.Apply(_harmony);
                // Магия: пока целимся заклинанием, ЛКМ не бьёт кулаком
                EquestriaSpellCombatPatch.Apply(_harmony);
                MuteVanillaOrderShouts.Apply(_harmony);
                MuteVanillaOrderNods.Apply(_harmony);
                EquestriaGreetings.ApplyVoice(_harmony);
                EquestriaMusic.Apply(_harmony);
                // Свиток полёта в слоте коня: не даёт движку завести агента-коня (src/EquestriaFlightScroll.cs)
                EquestriaFlightScroll.Apply(_harmony);
                EquestriaCrashLog.Log("Harmony: поздние патчи (голос приказов, голос приветствий, музыка) применены");
            });
        }
    }

    // Ванильный кэш расстояний между поселениями нам не подходит.
    //
    // При запуске кампании SettlementPositionScript обходит все включённые модули и берёт у
    // последнего, у кого есть файл ModuleData/DistanceCaches/settlements_distance_cache_*.bin.
    // Такой файл есть у SandBox, и он посчитан для Кальрадии: внутри имена поселений, которых в
    // нашем мире больше нет. При чтении игра ищет каждое по имени, не находит и падает на пустой
    // ссылке в NavigationCacheElement.GetHashCode.
    //
    // Законного способа отказаться от чужого кэша нет — отсюда патч. Говорим «файла нет» для всех
    // модулей, кроме нашего, и игра честно считает расстояния сама при старте кампании.
    //
    // Свой кэш. На карте 1024 м с 122 крепостями расчёт соседства идёт минут шесть, поэтому
    // посчитанный кэш сохраняем в наш ModuleData/DistanceCaches (DistanceCacheSaveOurs ниже).
    // Игра при чтении кэша НЕ сверяет его с картой, а устаревший кэш ломает расстояния, поэтому
    // рядом лежит отметка — хэш сетки проходимости и списка поселений. Не совпала — делаем вид,
    // что файла нет: игра пересчитает, а мы сохраним заново.
    [HarmonyPatch(typeof(SettlementPositionScript), "GetSettlementsDistanceCacheFileForCapability")]
    public static class DistanceCacheFromOurModuleOnly
    {
        internal const string OurModule = "EquestriaMod";

        // Путь, куда сохранить кэш после расчёта (задаётся, когда нашего кэша нет или он устарел)
        internal static string PendingSavePath;

        private static bool Prefix(string moduleId, ref string filePath, ref bool __result)
        {
            if (moduleId != OurModule)
            {
                filePath = string.Empty;
                __result = false;
                return false;
            }
            return true;  // наш модуль проверяем как обычно, а отметку — в Postfix
        }

        private static void Postfix(string moduleId, ref string filePath, ref bool __result)
        {
            if (moduleId != OurModule)
            {
                return;
            }
            string stamp = DistanceCacheStamp.Current();
            string found = __result ? DistanceCacheStamp.Read(filePath) : null;
            if (found != null && (found == stamp || found == DistanceCacheStamp.Legacy()))
            {
                if (found != stamp)
                {
                    DistanceCacheStamp.Write(filePath, stamp);   // отметка старого образца — переписываем
                }
                PendingSavePath = null;
                return;
            }
            if (__result)
            {
                EquestriaCrashLog.Log("кэш расстояний устарел (карта или поселения изменились) — пересчёт");
            }
            __result = false;
            PendingSavePath = filePath;
        }
    }

    // Сохранение посчитанного кэша в наш модуль (см. выше).
    [HarmonyPatch(typeof(SettlementPositionScript), "ReadNavigationCacheForNavigationTypeOnGameLoad")]
    public static class DistanceCacheSaveOurs
    {
        private static void Postfix(object __result)
        {
            string path = DistanceCacheFromOurModuleOnly.PendingSavePath;
            DistanceCacheFromOurModuleOnly.PendingSavePath = null;
            if (string.IsNullOrEmpty(path) || __result == null)
            {
                return;
            }
            EquestriaCrashLog.Try("сохранение кэша расстояний", () =>
            {
                System.IO.Directory.CreateDirectory(System.IO.Path.GetDirectoryName(path));
                __result.GetType().GetMethod("Serialize").Invoke(__result, new object[] { path });
                DistanceCacheStamp.Write(path, DistanceCacheStamp.Current());
                EquestriaCrashLog.Log("кэш расстояний сохранён: " + path);
            });
        }
    }

    internal static class DistanceCacheStamp
    {
        private static string ModuleDir =>
            TaleWorlds.ModuleManager.ModuleHelper.GetModuleFullPath(DistanceCacheFromOurModuleOnly.OurModule);

        private const string Navmesh = "SceneObj/Main_map/navmesh.bin";
        private const string Settlements = "ModuleData/equestria_settlements.xml";

        // Хэш того, от чего кэш зависит на самом деле: сетка проходимости и у каждого поселения —
        // id и координаты (в том числе ворот). Раньше хэшировался весь файл поселений, и любая
        // правка названия или описания (например, перевода) стоила пересчёта в шесть-девять минут.
        internal static string Current()
        {
            using (var sha = System.Security.Cryptography.SHA1.Create())
            {
                Feed(sha, FileBytes(Navmesh));
                string xml = System.IO.Path.Combine(ModuleDir, Settlements);
                if (System.IO.File.Exists(xml))
                {
                    var lines = new System.Collections.Generic.List<string>();
                    foreach (var node in System.Xml.Linq.XDocument.Load(xml).Descendants("Settlement"))
                    {
                        lines.Add(string.Join(";", new[] { "id", "posX", "posY", "gate_posX", "gate_posY" }
                            .Select(a => (string)node.Attribute(a) ?? "")));
                    }
                    Feed(sha, System.Text.Encoding.UTF8.GetBytes(string.Join("\n", lines)));
                }
                sha.TransformFinalBlock(new byte[0], 0, 0);
                return System.BitConverter.ToString(sha.Hash).Replace("-", "");
            }
        }

        // Отметка старого образца (весь файл поселений целиком). Принимаем её один раз, чтобы
        // смена способа не вызвала лишний пересчёт, и переписываем по-новому.
        internal static string Legacy()
        {
            using (var sha = System.Security.Cryptography.SHA1.Create())
            {
                Feed(sha, FileBytes(Navmesh));
                Feed(sha, FileBytes(Settlements));
                sha.TransformFinalBlock(new byte[0], 0, 0);
                return System.BitConverter.ToString(sha.Hash).Replace("-", "");
            }
        }

        private static byte[] FileBytes(string rel)
        {
            string file = System.IO.Path.Combine(ModuleDir, rel);
            return System.IO.File.Exists(file) ? System.IO.File.ReadAllBytes(file) : new byte[0];
        }

        private static void Feed(System.Security.Cryptography.SHA1 sha, byte[] data)
        {
            sha.TransformBlock(data, 0, data.Length, null, 0);
        }

        internal static string Read(string cachePath)
        {
            string file = cachePath + ".stamp";
            return System.IO.File.Exists(file) ? System.IO.File.ReadAllText(file).Trim() : null;
        }

        internal static void Write(string cachePath, string stamp)
        {
            System.IO.File.WriteAllText(cachePath + ".stamp", stamp);
        }
    }

    // Ванильная предыстория Кальрадии нам не нужна и мешает.
    //
    // BackstoryCampaignBehavior при создании новой игры расставляет отношения между конкретными
    // ванильными лордами: ссора lord_1_7 с lord_1_1, убийство dead_lord_2_2, притязание на town_V6
    // и так далее. Все эти имена прописаны прямо в коде. Мы этих героев удалили, HeroObject у них
    // пустой — и первое же обращение роняет кампанию.
    //
    // Содержимое всё равно про имперскую гражданскую войну, к Эквестрии отношения не имеет.
    // Отключаем целиком. Свою предысторию — ссоры принцесс, раскол Сталлионграда — напишем потом
    // отдельным поведением.
    [HarmonyPatch(typeof(BackstoryCampaignBehavior), nameof(BackstoryCampaignBehavior.OnNewGameCreated))]
    public static class SkipCalradianBackstory
    {
        private static bool Prefix()
        {
            EquestriaCrashLog.Log("ванильная предыстория Кальрадии пропущена");
            return false;
        }
    }

    // Страховка от пустого снаряжения.
    //
    // Helpers.EquipmentHelper.AssignHeroEquipmentFromEquipment берёт набор снаряжения и сразу
    // читает его свойства, не проверяя на пустоту. Пустой набор прилетает, когда для культуры героя
    // не нашлось подходящего шаблона — на этом мы уже дважды теряли запуск игры.
    //
    // Шаблоны мы завели все восемь, но при перекройке мира лордов и культур станет много, и одна
    // забытая строчка в XML снова уронила бы кампанию без всякого объяснения. Теперь вместо падения
    // герой просто останется в чём был, а в журнал ляжет его имя — сразу видно, кому чего не хватает.
    [HarmonyPatch(typeof(EquipmentHelper), nameof(EquipmentHelper.AssignHeroEquipmentFromEquipment))]
    public static class AssignHeroEquipmentGuard
    {
        // Возврат false отменяет исходный метод.
        private static bool Prefix(Hero hero, Equipment equipment)
        {
            if (equipment != null)
            {
                return true;
            }
            string who = hero != null ? hero.StringId : "неизвестный герой";
            string culture = hero != null && hero.Culture != null ? hero.Culture.StringId : "нет культуры";
            EquestriaCrashLog.Warn($"снаряжение не подобрано: {who} (культура {culture}) — "
                + "нет подходящего шаблона в EquipmentRosters; герой оставлен без смены одежды");
            return false;
        }
    }
}
