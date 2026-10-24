using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using Helpers;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.GameState;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.Localization;
using TaleWorlds.MountAndBlade;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Смотр рас: старт, после которого в отряде игрока стоят по три спутника КАЖДОЙ расы, и каждый
    // одет в случайную броню. Нужен, чтобы одним запуском посмотреть, как на всех наших моделях
    // сидят ванильные доспехи — до этого каждую расу приходилось смотреть отдельной кампанией.
    //
    // Запускается тремя способами:
    //   .\run.ps1 -Races          новая песочница без единого клика, спутники уже в отряде;
    //   кнопка «Эквестрия: смотр рас» в главном меню — то же самое руками;
    //   equestria.race_party [сколько] — набрать в уже начатой кампании.
    public static class EquestriaRaceParty
    {
        private const string OptionId = "EquestriaRaceParty";
        private const string ArgPrefix = "/eqraces";     // допускается /eqraces:5
        private const int DefaultPerRace = 3;
        private const int MaxPerRace = 20;

        private static int _wanted;                      // 0 — смотр не запрашивали
        private static bool _done;
        private static DateTime _mapSeenAt = DateTime.MinValue;

        public static void CheckRequest()
        {
            foreach (string arg in Environment.GetCommandLineArgs())
            {
                if (!arg.StartsWith(ArgPrefix, StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }
                string tail = arg.Substring(ArgPrefix.Length).TrimStart(':');
                _wanted = int.TryParse(tail, out int n) ? Math.Max(1, Math.Min(MaxPerRace, n)) : DefaultPerRace;
                EquestriaCrashLog.Log($"смотр рас: запрошен по ключу, по {_wanted} спутника на расу");
            }
        }

        public static void AddMenuOption()
        {
            var option = new InitialStateOption(
                OptionId,
                new TextObject("{=eq_race_party_menu}Equestria: race review"),
                9990,
                StartShowcaseCampaign,
                () => (false, null),
                null,
                () => false);
            Module.CurrentModule.AddInitialStateOption(option);
        }

        private static void StartShowcaseCampaign()
        {
            _wanted = DefaultPerRace;
            _done = false;
            _mapSeenAt = DateTime.MinValue;
            EquestriaQuickStart.StartQuickCampaign();
        }

        // Ждём карту: до неё у игрока нет ни отряда, ни клана, и спутника некуда брать.
        // Двухсекундная пауза — та же, что у примерочной шлемов: сразу после появления карты
        // кампания ещё доигрывает своё начало.
        public static void Tick()
        {
            if (_wanted <= 0 || _done)
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
            EquestriaCrashLog.Try("смотр рас по ключу", () =>
            {
                string report = Run(new List<string> { _wanted.ToString() });
                EquestriaCrashLog.Log(report.Replace("\n", " "));
                InformationManager.DisplayMessage(new InformationMessage(report, Colors.Magenta));
                // Если тем же запуском просят бой (/eqbattle), экран отряда не открываем: он сменил
                // бы состояние игры, и бой (EquestriaShowcase, ждёт карту так же, как и мы) не
                // начался бы — тот же приём, что у EquestriaHelmetTest с инвентарём.
                bool toBattle = Environment.GetCommandLineArgs()
                    .Any(a => string.Equals(a, "/eqbattle", StringComparison.OrdinalIgnoreCase));
                if (!toBattle)
                {
                    PartyScreenHelper.OpenScreenAsNormal();
                }
            });
        }

        // Слоты брони и типы предметов для них. Оружие не выдаём: смотрим именно посадку доспеха.
        private static readonly (EquipmentIndex Slot, ItemObject.ItemTypeEnum Type)[] Wear =
        {
            (EquipmentIndex.Head, ItemObject.ItemTypeEnum.HeadArmor),
            (EquipmentIndex.Body, ItemObject.ItemTypeEnum.BodyArmor),
            (EquipmentIndex.Leg, ItemObject.ItemTypeEnum.LegArmor),
            (EquipmentIndex.Gloves, ItemObject.ItemTypeEnum.HandArmor),
            (EquipmentIndex.Cape, ItemObject.ItemTypeEnum.Cape),
        };

        private static Dictionary<ItemObject.ItemTypeEnum, List<ItemObject>> _pool;

        // Что вообще можно надеть. Отсекаем предметы без меша и части тела рас (хвосты, крылья,
        // гребни): они тоже числятся бронёй, но их вешает на скелет EquestriaBodyParts, и в слоте
        // накидки им делать нечего — иначе оленю достался бы чужой хвост.
        // internal — переиспользуется EquestriaDebugCommands.DismembermentTestBattle (случайная
        // броня на бойцах тестового боя).
        internal static List<ItemObject> Pool(ItemObject.ItemTypeEnum type)
        {
            if (_pool == null)
            {
                _pool = MBObjectManager.Instance.GetObjectTypeList<ItemObject>()
                    .Where(i => i != null && i.ArmorComponent != null
                                && !string.IsNullOrEmpty(i.MultiMeshName)
                                && !EquestriaBodyParts.IsBodyPart(i.StringId))
                    .GroupBy(i => i.ItemType)
                    .ToDictionary(g => g.Key, g => g.ToList());
            }
            List<ItemObject> list;
            return _pool.TryGetValue(type, out list) ? list : new List<ItemObject>();
        }

        // Одеваем вразнобой: каждый слот — свой случайный предмет, и боевой набор совпадает с
        // гражданским, чтобы броня была видна в любом окне.
        private static string Dress(Hero hero)
        {
            var worn = new List<string>();
            foreach (var (slot, type) in Wear)
            {
                var pool = Pool(type);
                if (pool.Count == 0)
                {
                    continue;
                }
                var item = pool[MBRandom.RandomInt(pool.Count)];
                hero.BattleEquipment[slot] = new EquipmentElement(item);
                hero.CivilianEquipment[slot] = new EquipmentElement(item);
                worn.Add(item.StringId);
            }
            return string.Join(", ", worn);
        }

        // equestria.race_party [сколько на расу] — набрать в отряд спутников всех рас
        [CommandLineFunctionality.CommandLineArgumentFunction("race_party", "equestria")]
        public static string Run(List<string> args)
        {
            if (Campaign.Current == null || MobileParty.MainParty == null || Clan.PlayerClan == null)
            {
                return "Доступно только в кампании.";
            }
            int per = args != null && args.Count > 0 && int.TryParse(args[0], out int n)
                ? Math.Max(1, Math.Min(MaxPerRace, n)) : DefaultPerRace;

            var names = TaleWorlds.Core.FaceGen.GetRaceNames();
            if (names == null || names.Length == 0)
            {
                return "Список рас пуст — skins не загрузились.";
            }
            // Шаблоны странников: из них делаются обычные спутники (см. equestria.companions).
            // Канонных (spc_eq_*) не берём: у них своя внешность и своя раса, а нам нужны
            // одинаковые болванки, которым расу назначаем мы.
            var templates = CharacterObject.All
                .Where(c => c.Occupation == Occupation.Wanderer && c.IsTemplate
                            && !c.StringId.StartsWith("spc_eq_"))
                .ToList();
            if (templates.Count == 0)
            {
                return "Не нашлось ни одного шаблона странника.";
            }

            var report = new StringBuilder();
            int total = 0;
            for (int race = 0; race < names.Length; race++)
            {
                // Ванильного человека пропускаем: в моде им никто не играет, и в окне внешности
                // его тоже не видно (см. EquestriaRaceSelector).
                if (names[race] == "human")
                {
                    continue;
                }
                for (int k = 0; k < per; k++)
                {
                    var template = templates[MBRandom.RandomInt(templates.Count)];
                    var hero = EquestriaDebugCommands.CreateWanderer(template);
                    EquestriaDebugCommands.JoinParty(hero, true);
                    EquestriaRaceSaveBehavior.SetRace(hero, race);
                    string worn = Dress(hero);
                    // Имя по расе с номером — иначе в отряде не разобрать, кто какой расы.
                    var title = EquestriaRaceSelector.TitleOf(names[race]).ToString();
                    var full = new TextObject("{=!}" + title + " " + (k + 1));
                    EquestriaCrashLog.Try("смотр рас: имя спутника", () => hero.SetName(full, full));
                    EquestriaCrashLog.Log($"смотр рас: {full} — раса {names[race]} ({race}), броня {worn}");
                    total++;
                }
                report.Append(report.Length > 0 ? ", " : "").Append(names[race]);
            }
            // Пони получают гриву и хвост в свободные слоты — у остальных рас это делает
            // EquestriaBodyParts прямо в бою.
            EquestriaMane.EnsureForPonies();
            return $"Смотр рас: добавлено спутников {total} (по {per} на расу). Расы: {report}. "
                + $"Героев в отряде: {MobileParty.MainParty.MemberRoster.TotalHeroes}.";
        }
    }
}
