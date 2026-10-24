using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using Helpers;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Encounters;
using TaleWorlds.CampaignSystem.GameState;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.CampaignSystem.Party.PartyComponents;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Примерочная шлемов: одной командой попасть в инвентарь с надетым шлемом и с набором чужих
    // под рукой. Нужна для подгонки шлема под крупную голову расы (src/EquestriaHelmetFit.cs):
    // важно посмотреть и закрытые шлемы, и открытые — движок подгоняет их по-разному.
    public static class EquestriaHelmetTest
    {
        private const int PerKind = 8;      // сколько взять открытых и сколько закрытых

        // Ключ запуска: /eqhelmets или /eqhelmets:open — всё то же самое, но без консоли.
        // Дождавшись карты, сам выдаёт шлемы, надевает один и открывает инвентарь.
        private const string ArgPrefix = "/eqhelmets";
        private const string BigBattleArg = "/eqbigbattle";
        private static bool _bigBattle;
        private static string _requested;
        private static bool _done;
        private static DateTime _mapSeenAt = DateTime.MinValue;

        public static void CheckRequest()
        {
            foreach (string arg in Environment.GetCommandLineArgs())
            {
                if (string.Equals(arg, BigBattleArg, StringComparison.OrdinalIgnoreCase))
                {
                    _bigBattle = true;
                    _requested = _requested ?? "open";
                    EquestriaCrashLog.Log("примерочная шлемов: запрошен крупный бой драконов");
                }
                if (!arg.StartsWith(ArgPrefix, StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }
                string tail = arg.Substring(ArgPrefix.Length).TrimStart(':');
                _requested = string.IsNullOrEmpty(tail) ? "closed" : tail.ToLower();
                EquestriaCrashLog.Log("примерочная шлемов: запрошена по ключу, шлем " + _requested);
            }
        }

        // Ждём, пока кампания встанет на карту: до этого у игрока ещё нет персонажа.
        public static void Tick()
        {
            if (_requested == null || _done)
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
            EquestriaCrashLog.Try("примерочная шлемов по ключу",
                () => EquestriaCrashLog.Log(Run(new List<string> { _requested }).Replace("\n", " ")));
        }

        private static bool IsOpen(ItemObject item)
        {
            // «Открытый» — тот, что оставляет голову видимой; по этому же признаку движок решает,
            // подгонять ли шлем под размер головы (ItemObject.UsingFacegenScaling)
            return item.ArmorComponent != null
                   && item.ArmorComponent.MeshesMask.HasAnyFlag(SkinMask.HeadVisible);
        }

        private static List<ItemObject> Pick(bool open)
        {
            // Только ванильные шлемы: наши предметы (eq_*) — это рога и гривы рас, они тоже
            // числятся «шлемами», и в прошлый раз примерочная выдала именно их.
            var all = MBObjectManager.Instance.GetObjectTypeList<ItemObject>()
                .Where(i => i != null && i.ItemType == ItemObject.ItemTypeEnum.HeadArmor
                            && i.ArmorComponent != null && IsOpen(i) == open
                            && !string.IsNullOrEmpty(i.MultiMeshName)
                            && !(i.StringId ?? "").StartsWith("eq_"))
                .OrderBy(i => i.Value)
                .ToList();
            if (all.Count <= PerKind)
            {
                return all;
            }
            // берём вразнобой по всей цене — от шапки до шлема полководца
            var step = (double)(all.Count - 1) / (PerKind - 1);
            return Enumerable.Range(0, PerKind).Select(k => all[(int)(k * step)]).Distinct().ToList();
        }

        // equestria.helmet_test [open|closed] — выдать шлемы, надеть один и открыть инвентарь
        [CommandLineFunctionality.CommandLineArgumentFunction("helmet_test", "equestria")]
        public static string Run(List<string> args)
        {
            if (Campaign.Current == null || Hero.MainHero == null)
            {
                return "Нужна начатая кампания.";
            }
            string want = args != null && args.Count > 0 ? args[0].ToLower() : "closed";
            // Примерка нужна именно на драконе — ставим расу героя, если он ещё не дракон
            int dragon = TaleWorlds.Core.FaceGen.GetRaceOrDefault("dragon");
            if (dragon != 0 && Hero.MainHero.CharacterObject.Race != dragon)
            {
                EquestriaRaceSaveBehavior.SetRace(Hero.MainHero, dragon);
            }
            var open = Pick(true);
            var closed = Pick(false);
            var party = PartyBase.MainParty;
            foreach (var item in open.Concat(closed))
            {
                if (party.ItemRoster.GetItemNumber(item) == 0)
                {
                    party.ItemRoster.AddToCounts(item, 1);
                }
            }

            // Надеваем сразу: так окно открывается с уже надетым шлемом, и видно посадку
            var wear = (want == "open" ? open : closed).FirstOrDefault()
                       ?? open.Concat(closed).FirstOrDefault();
            if (wear != null)
            {
                Hero.MainHero.BattleEquipment[EquipmentIndex.Head] = new EquipmentElement(wear);
                Hero.MainHero.CivilianEquipment[EquipmentIndex.Head] = new EquipmentElement(wear);
            }

            var report = new StringBuilder();
            report.AppendLine($"Раса героя: {Hero.MainHero.CharacterObject.Race} "
                + $"({TaleWorlds.Core.FaceGen.GetRaceOrDefault("dragon")} — дракон)");
            report.AppendLine($"Выдано шлемов: открытых {open.Count}, закрытых {closed.Count}.");
            report.AppendLine($"Надет: {(wear != null ? wear.Name.ToString() : "нет")} "
                + $"({(wear != null && IsOpen(wear) ? "открытый" : "закрытый")}).");
            // Если тем же запуском просят бой, инвентарь не открываем: он сменил бы состояние
            // игры, и бой не начался бы — показ боя ждёт карту.
            bool toBattle = _bigBattle || Environment.GetCommandLineArgs()
                .Any(a => string.Equals(a, "/eqbattle", StringComparison.OrdinalIgnoreCase));
            report.Append(toBattle
                ? "Шлем надет, инвентарь не открываю — сейчас бой."
                : "Открываю инвентарь — шлемы в списке справа, примеряйте по очереди.");
            EquestriaCrashLog.Log("примерочная шлемов: " + report.ToString().Replace("\n", " "));
            if (_bigBattle)
            {
                EquestriaCrashLog.Log("примерочная шлемов: " + BigBattle(null));
            }
            else if (!toBattle)
            {
                InventoryScreenHelper.OpenScreenAsInventory();
            }
            return report.ToString();
        }

        // Крупный бой драконов: обе стороны — стургийские ветераны (у мода эта культура и есть
        // драконы), они в полном доспехе со шлемами. Нужен, чтобы смотреть шлем в гуще и заодно
        // мерить, во что обходится подгонка на тысяче бойцов.
        private const string BigTroop = "sturgian_veteran_warrior";

        // equestria.big_battle [сколько с каждой стороны] [id войска]
        [CommandLineFunctionality.CommandLineArgumentFunction("big_battle", "equestria")]
        public static string BigBattle(List<string> args)
        {
            if (Campaign.Current == null || MobileParty.MainParty == null)
            {
                return "Доступно только в кампании.";
            }
            if (MobileParty.MainParty.MapEvent != null || PlayerEncounter.Current != null)
            {
                return "Игрок уже в бою или в разговоре.";
            }
            int side = args != null && args.Count > 0 && int.TryParse(args[0], out int n)
                ? Math.Max(1, Math.Min(2000, n)) : 500;
            string troopId = args != null && args.Count > 1 ? args[1] : BigTroop;
            var troop = MBObjectManager.Instance.GetObject<CharacterObject>(troopId);
            if (troop == null)
            {
                return "Нет такого войска: " + troopId;
            }

            // Врага делаем отрядом разбойников — это самый короткий путь создать отряд на карте, —
            // но состав подменяем целиком: в бою важны сами бойцы, а не вывеска банды.
            var clan = Clan.BanditFactions.FirstOrDefault(c => c.StringId == "looters");
            if (clan?.DefaultPartyTemplate == null)
            {
                return "В этой кампании нет разбойников, не из чего сделать врага.";
            }
            var near = new CampaignVec2(MobileParty.MainParty.GetPosition2D + new Vec2(0.6f, 0.6f), true);
            var home = Settlement.All.Where(x => x.IsTown || x.IsVillage)
                .OrderBy(x => x.GetPosition2D.DistanceSquared(near.ToVec2())).FirstOrDefault();
            var enemy = BanditPartyComponent.CreateLooterParty(
                "eq_big_battle_" + MBRandom.RandomInt(100000), clan, home, false,
                clan.DefaultPartyTemplate, near);
            enemy.MemberRoster.Clear();
            enemy.MemberRoster.AddToCounts(troop, side);
            MobileParty.MainParty.MemberRoster.AddToCounts(troop, side);

            EncounterManager.StartPartyEncounter(PartyBase.MainParty, enemy.Party);
            // Сразу в поле, без меню стычки: иначе игра ждёт нажатия «Атаковать»
            EquestriaCrashLog.Try("крупный бой: вход в сражение", PlayerEncounter.StartAttackMission);
            string report = $"Бой {side} на {side}: обе стороны — {troop.Name} ({troopId}).";
            EquestriaCrashLog.Log("крупный бой: " + report);
            return report;
        }

        // Чью посадку шлема настраивают команды — расу ИГРОКА. Раньше обе команды правили дракона
        // намертво, и подобрать числа для грифона было нечем. Вне кампании (и у человека) остаётся
        // дракон: с него всё начиналось, и в пользовательском бою настраивать больше нечего.
        private static string TunedRace()
        {
            if (Campaign.Current != null && Hero.MainHero != null && Hero.MainHero.CharacterObject != null)
            {
                string[] names = TaleWorlds.Core.FaceGen.GetRaceNames();
                int race = Hero.MainHero.CharacterObject.Race;
                if (race > 0 && race < names.Length)
                {
                    return names[race];
                }
            }
            return "dragon";
        }

        // equestria.helmet_offset <вправо> <вперёд> <вверх> — сдвиг шлема в метрах, на лету
        [CommandLineFunctionality.CommandLineArgumentFunction("helmet_offset", "equestria")]
        public static string SetOffset(List<string> args)
        {
            string race = TunedRace();
            var was = EquestriaHelmetFit.ShiftFor(race);
            string now = $"(сейчас вправо {was.x:0.00}, вперёд {-was.y:0.00}, вверх {was.z:0.00})";
            if (args == null || args.Count < 3
                || !float.TryParse(args[0], out float right) || !float.TryParse(args[1], out float forward)
                || !float.TryParse(args[2], out float up)
                || Math.Abs(right) > 1f || Math.Abs(forward) > 1f || Math.Abs(up) > 1f)
            {
                return "Укажите три числа в метрах: вправо, вперёд и вверх, например "
                    + $"equestria.helmet_offset 0.02 0 0.03 {now}";
            }
            EquestriaHelmetFit.SetShift(race, right, forward, up);
            return $"Сдвиг шлема у расы «{race}»: вправо {right:0.00}, вперёд {forward:0.00}, вверх {up:0.00}. "
                + "Сдвиг применяется сразу, в окне снаряжения — на следующем кадре.";
        }

        // equestria.helmet_scale <число> | <вбок> <вперёд> <вверх> — размер шлема на лету
        [CommandLineFunctionality.CommandLineArgumentFunction("helmet_scale", "equestria")]
        public static string SetScale(List<string> args)
        {
            string race = TunedRace();
            var was = EquestriaHelmetFit.ScaleFor(race);
            string now = $"(сейчас {was.x:0.00} {was.y:0.00} {was.z:0.00})";
            var numbers = new List<float>();
            foreach (var arg in args ?? new List<string>())
            {
                if (float.TryParse(arg, out float value) && value > 0.1f && value <= 6f)
                {
                    numbers.Add(value);
                }
            }
            // одно число — поровну по всем осям, три — по осям врозь
            if (numbers.Count != 1 && numbers.Count != 3)
            {
                return "Укажите один множитель или три — вбок, вперёд и вверх, например "
                    + $"equestria.helmet_scale 2.2 или equestria.helmet_scale 2.4 2.2 2 {now}";
            }
            var scale = numbers.Count == 1
                ? new Vec3(numbers[0], numbers[0], numbers[0])
                : new Vec3(numbers[0], numbers[1], numbers[2]);
            EquestriaHelmetFit.SetScale(race, scale);
            return $"Размер шлема у расы «{race}»: вбок {scale.x:0.00}, вперёд {scale.y:0.00}, "
                + $"вверх {scale.z:0.00}. Видно сразу, в окне снаряжения — на следующем кадре.";
        }
    }
}
