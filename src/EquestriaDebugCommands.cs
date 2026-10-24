using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using HarmonyLib;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Actions;
using TaleWorlds.CampaignSystem.Conversation;
using TaleWorlds.CampaignSystem.Encounters;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.CampaignSystem.Party.PartyComponents;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Отладочные команды для проверки лордов Эквестрии на карте. В ванильной консоли нет ни телепорта,
    // ни вызова разговора, поэтому делаем свои.
    public static class EquestriaDebugCommands
    {
        private const string ClanId = "clan_equestria_royal";

        private static IEnumerable<Hero> ClanHeroes()
        {
            return Hero.AllAliveHeroes.Where(h => h.Clan != null && h.Clan.StringId == ClanId);
        }

        private static Hero Find(List<string> args)
        {
            var name = args.Count > 0 ? string.Join(" ", args) : null;
            if (name == null)
            {
                // Без имени: лидер нашего клана, а если в этой кампании его нет (быстрый тест) —
                // любой живой лорд с отрядом, лишь бы было с кем поговорить
                return ClanHeroes().FirstOrDefault()
                    ?? Hero.AllAliveHeroes.FirstOrDefault(h => h.IsLord && h.PartyBelongedTo != null
                        && h != Hero.MainHero && h.Clan != Clan.PlayerClan);
            }
            // С именем — ищем среди ВСЕХ живых лордов, а не только своего клана: по имени часто
            // проверяют конкретного перса из другого дома (например, лор-цвет лорда — см.
            // EquestriaBodyParts.LoreColors), а не обязательно кого-то из clan_equestria_royal.
            // Консоль принимает только латиницу — имя на русском (локализация) с неё не ввести,
            // поэтому ищем ещё и по StringId персонажа (id="eq_..." из equestria_lords.xml,
            // он всегда латиницей): equestria.talk_to_lord eq_posey_shy сработает, даже если
            // игра на русском и в консоли "Поузи Шай" не напечатать.
            var needle = name.ToLower();
            return Hero.AllAliveHeroes.FirstOrDefault(h => h.IsLord
                && (h.Name.ToString().ToLower().Contains(needle)
                    || (h.CharacterObject?.StringId?.ToLower().Contains(needle) ?? false)));
        }

        // equestria.list_lords — кто в клане, где находится и есть ли отряд
        [CommandLineFunctionality.CommandLineArgumentFunction("list_lords", "equestria")]
        public static string ListLords(List<string> args)
        {
            if (Campaign.Current == null)
            {
                return "Available only in a campaign.";
            }
            var lines = new List<string>();
            foreach (var hero in ClanHeroes())
            {
                var party = hero.PartyBelongedTo;
                var where = party != null
                    ? $"party at {party.GetPosition2D.x:F1}, {party.GetPosition2D.y:F1}"
                    : (hero.CurrentSettlement != null ? "in " + hero.CurrentSettlement.Name : "no party");
                lines.Add($"{hero.Name} ({hero.CharacterObject.Race}) — {where}");
            }
            return lines.Count > 0 ? string.Join("\n", lines) : "Clan " + ClanId + " has no living heroes.";
        }

        // equestria.goto_lord [имя] — перенести отряд игрока к лорду (по умолчанию к лидеру клана)
        [CommandLineFunctionality.CommandLineArgumentFunction("goto_lord", "equestria")]
        public static string GotoLord(List<string> args)
        {
            if (Campaign.Current == null || MobileParty.MainParty == null)
            {
                return "Available only in a campaign.";
            }
            var hero = Find(args);
            if (hero == null)
            {
                return "Lord not found. Use equestria.list_lords.";
            }
            var target = hero.PartyBelongedTo;
            if (target == null)
            {
                return hero.Name + " has no party on the map.";
            }
            MobileParty.MainParty.Position = target.Position;  // CampaignVec2, в 1.4.8 Position2D нет
            return $"Teleported to {hero.Name} at {target.GetPosition2D.x:F1}, {target.GetPosition2D.y:F1}.";
        }

        // equestria.talk_to_lord [имя] — открыть разговор с лордом, где бы он ни был
        [CommandLineFunctionality.CommandLineArgumentFunction("talk_to_lord", "equestria")]
        public static string TalkToLord(List<string> args)
        {
            if (Campaign.Current == null || Hero.MainHero == null)
            {
                return "Available only in a campaign.";
            }
            var hero = Find(args);
            if (hero == null)
            {
                return "Lord not found. Use equestria.list_lords.";
            }
            var player = new ConversationCharacterData(CharacterObject.PlayerCharacter, PartyBase.MainParty);
            var other = new ConversationCharacterData(hero.CharacterObject, hero.PartyBelongedTo?.Party);
            CampaignMapConversation.OpenConversation(player, other);
            return "Talking to " + hero.Name + ".";
        }

        // equestria.companions [сколько] — набрать в отряд случайных спутников (по умолчанию 100)
        // из всех шаблонов странников всех культур; среди них попадаются и канонные второстепенные
        // персонажи (шаблоны spc_eq_*: Лира, Оцеллус, Гэллус...), но каждый не больше одного раза.
        // Главных героев канона (Твайлайт, Эпплджек...) команда не трогает: они лорды своих кланов,
        // и спутником герой может быть только вместо этого — мир бы остался без них.
        // Предел размера отряда не проверяется — это проверочная команда.
        [CommandLineFunctionality.CommandLineArgumentFunction("companions", "equestria")]
        public static string Companions(List<string> args)
        {
            if (Campaign.Current == null || MobileParty.MainParty == null)
            {
                return "Доступно только в кампании.";
            }
            int wanted = args.Count > 0 && int.TryParse(args[0], out int n) ? n : 100;
            var templates = CharacterObject.All
                .Where(c => c.Occupation == Occupation.Wanderer && c.IsTemplate).ToList();
            var usedCanon = new HashSet<CharacterObject>();
            int added = 0;
            int canon = 0;
            while (added < wanted && templates.Count > 0)
            {
                var template = templates[MBRandom.RandomInt(templates.Count)];
                if (template.StringId.StartsWith("spc_eq_"))
                {
                    if (!usedCanon.Add(template))
                    {
                        continue;   // канонный — только один раз
                    }
                    canon++;
                }
                JoinParty(CreateWanderer(template), true);
                added++;
            }
            return $"В отряд добавлено спутников: {added}, из них канонных {canon}. "
                + $"Героев в отряде: {MobileParty.MainParty.MemberRoster.TotalHeroes}.";
        }

        // internal: тем же способом набирает спутников смотр рас (EquestriaRaceParty)
        internal static Hero CreateWanderer(CharacterObject template)
        {
            Settlement home = Settlement.All.FirstOrDefault(s => s.IsTown && s.Culture == template.Culture)
                ?? Settlement.All.First(s => s.IsTown);
            int age = template.Age > 0 ? (int)template.Age : 25;
            return HeroCreator.CreateSpecialHero(template, home, null, null, age);
        }

        // Забрать героя в отряд игрока. asCompanion — сделать спутником клана игрока (для странников);
        // лорды остаются в своих кланах, только едут с игроком.
        internal static void JoinParty(Hero hero, bool asCompanion)
        {
            var own = hero.PartyBelongedTo;
            if (own != null && own != MobileParty.MainParty)
            {
                if (own.LeaderHero == hero)
                {
                    TaleWorlds.CampaignSystem.Actions.DestroyPartyAction.Apply(null, own);
                }
                else
                {
                    own.MemberRoster.RemoveTroop(hero.CharacterObject, 1);
                }
            }
            if (hero.CurrentSettlement != null)
            {
                TaleWorlds.CampaignSystem.Actions.LeaveSettlementAction.ApplyForCharacterOnly(hero);
            }
            if (asCompanion && hero.Clan != Clan.PlayerClan)
            {
                TaleWorlds.CampaignSystem.Actions.AddCompanionAction.Apply(Clan.PlayerClan, hero);
            }
            TaleWorlds.CampaignSystem.Actions.AddHeroToPartyAction.Apply(hero, MobileParty.MainParty, false);
        }

        // equestria.meet <часть имени или id> | all — «познакомиться» с героем без встречи: в
        // энциклопедии открываются портрет, возраст, занятие и отношения (Hero.SetHasMet). all — со
        // всеми живыми героями разом. В ванили такой команды нет (10.10.2026).
        [CommandLineFunctionality.CommandLineArgumentFunction("meet", "equestria")]
        public static string Meet(List<string> args)
        {
            if (Campaign.Current == null)
            {
                return "Нужна начатая кампания.";
            }
            string key = string.Join(" ", args ?? new List<string>()).Trim().ToLower();
            if (key.Length == 0)
            {
                return "Укажите часть имени или id героя, например equestria.meet найтшейд, или all — со всеми.";
            }
            var heroes = key == "all"
                ? Hero.AllAliveHeroes.ToList()
                : Hero.AllAliveHeroes.Concat(Hero.DeadOrDisabledHeroes)
                    .Where(h => h.StringId.ToLower() == key || h.Name.ToString().ToLower().Contains(key)).ToList();
            if (heroes.Count == 0)
            {
                return "Героев не найдено: " + key;
            }
            foreach (var hero in heroes)
            {
                hero.SetHasMet();
            }
            return heroes.Count <= 10
                ? "Знакомы теперь: " + string.Join(", ", heroes.Select(h => h.Name.ToString()))
                : $"Знакомы теперь со всеми: {heroes.Count} героев.";
        }

        // equestria.hero_info <часть имени или id> — что игра на самом деле знает о герое: раса,
        // возраст, ключ внешности, снаряжение боевое и гражданское. Для сравнения тех, кто в окне
        // отряда рисуется, с теми, у кого окно пустое.
        [CommandLineFunctionality.CommandLineArgumentFunction("hero_info", "equestria")]
        public static string HeroInfo(List<string> args)
        {
            if (Campaign.Current == null || args.Count == 0)
            {
                return "equestria.hero_info <имя или id>";
            }
            string key = string.Join(" ", args).ToLower();
            var hero = Hero.AllAliveHeroes.FirstOrDefault(h => h.StringId.ToLower() == key || h.StringId.ToLower() == "eq_" + key)
                ?? Hero.AllAliveHeroes.FirstOrDefault(h => h.Name.ToString().ToLower().Contains(key));
            if (hero == null)
            {
                return "Не найден: " + key;
            }
            var c = hero.CharacterObject;
            string Items(Equipment e) => e == null ? "нет" : string.Join(", ",
                Enumerable.Range(0, 12).Select(i => e[i].Item).Where(it => it != null).Select(it => it.StringId));
            return $"{hero.Name} [{hero.StringId}] раса {c.Race}, возраст {(int)hero.Age}, пол {(hero.IsFemale ? "ж" : "м")}, "
                + $"культура {hero.Culture?.StringId}, клан {hero.Clan?.StringId}, {(hero.IsWanderer ? "спутник" : hero.Occupation.ToString())}\n"
                + $"  внешность: {hero.BodyProperties}\n"
                + $"  бой: {Items(hero.BattleEquipment)}\n"
                + $"  быт: {Items(hero.CivilianEquipment)}";
        }

        // equestria.fight_bandits [банда] [сколько] — создать рядом отряд разбойников и сразу вступить с ним в бой.
        //   банда: looters (по умолчанию), sea_raiders, mountain_bandits, forest_bandits,
        //          desert_bandits, steppe_bandits
        //   сколько: во сколько раз увеличить отряд (1..10), по умолчанию 1
        // Консоль открывается Alt+~ (нужен запуск с включённым режимом разработчика).
        [CommandLineFunctionality.CommandLineArgumentFunction("fight_bandits", "equestria")]
        public static string FightBandits(List<string> args)
        {
            if (Campaign.Current == null || MobileParty.MainParty == null)
            {
                return "Доступно только в кампании.";
            }
            if (MobileParty.MainParty.MapEvent != null || PlayerEncounter.Current != null)
            {
                return "Игрок уже в бою или в диалоге.";
            }
            string clanId = args.Count > 0 ? args[0] : "looters";
            int scale = args.Count > 1 && int.TryParse(args[1], out int n) ? MathF.Max(1, MathF.Min(10, n)) : 1;

            Clan clan = Clan.BanditFactions.FirstOrDefault(c => c.StringId == clanId);
            if (clan == null)
            {
                return "Нет такой банды: " + clanId + ". Есть: "
                    + string.Join(", ", Clan.BanditFactions.Select(c => c.StringId));
            }
            if (clan.DefaultPartyTemplate == null)
            {
                return "У банды " + clanId + " нет шаблона отряда.";
            }

            // Рядом с игроком, чуть в стороне — иначе отряд появится прямо в нём.
            var near = new CampaignVec2(MobileParty.MainParty.GetPosition2D + new Vec2(0.6f, 0.6f), true);
            Settlement home = Settlement.All.Where(s => s.IsTown || s.IsVillage)
                .OrderBy(s => s.GetPosition2D.DistanceSquared(near.ToVec2())).FirstOrDefault();
            string id = "eq_debug_bandits_" + MBRandom.RandomInt(100000);
            MobileParty bandits = BanditPartyComponent.CreateLooterParty(id, clan, home, false,
                clan.DefaultPartyTemplate, near);

            // Шаблон даёт скромный отряд — по желанию умножаем.
            if (scale > 1)
            {
                foreach (var element in bandits.MemberRoster.GetTroopRoster().ToList())
                {
                    bandits.MemberRoster.AddToCounts(element.Character, element.Number * (scale - 1));
                }
            }
            int size = bandits.MemberRoster.TotalManCount;
            if (size == 0)
            {
                DestroyPartyAction.Apply(null, bandits);
                return "Отряд вышел пустым — у шаблона банды " + clanId + " нет бойцов.";
            }

            EncounterManager.StartPartyEncounter(PartyBase.MainParty, bandits.Party);
            EquestriaCrashLog.Log($"отладка: бой с разбойниками {clan.Name}, бойцов {size}");
            return $"Бой с «{clan.Name}»: {size} бойцов.";
        }

        // Двуручные мечи (а не топоры — те бывают дробящими, не рубящими, и не подходят под
        // детект отрубания, который требует DamageType.Cut). Все шесть реально существуют
        // (проверено — используются battania-войсками в equestria_troops.xml).
        private static readonly string[] TwoHandedSwords =
        {
            "battania_2hsword_1_t2", "battania_2hsword_2_t3", "battania_2hsword_3_t3",
            "battania_2hsword_4_t4", "battania_2hsword_5_t4", "battania_2hsword_6",
        };

        // Раса -> войско для equestria.dismember_test: по одному рослому Infantry-бойцу тир 21-26
        // на расу (сверено с equestria_troops.xml), чтобы было у кого отрубать руки/ноги — для
        // этого нужен race с уже разрезанными на _l/_r gloves/legs (EquestriaDismemberment.RaceInfo).
        private static readonly Dictionary<string, string> DismemberTestTroopByRace = new Dictionary<string, string>
        {
            { "pony", "embers_of_flame_tier_3" },        // Golden Horseshoe Veteran
            { "changeling", "aserai_veteran_infantry" }, // Hive Veteran
            { "dragon", "vlandian_sergeant" },            // Dragon Warrior (вландийская ветка)
            { "griffon", "khuzait_darkhan" },             // Griffonstone Axebearer (хузаитская ветка)
            { "hippogriff", "eq_hg_sturgian_veteran_warrior" }, // Surf Veteran (копии стургийской ветки)
            { "yak", "sturgian_veteran_warrior" },        // Yakyakistan Axebearer (стургийская ветка)
            { "deer", "battanian_oathsworn" },            // Guard of Deer Grove (баттанийская ветка)
        };

        // equestria.dismember_test [сколько на сторону] [раса] — бой "по пояс в крови" для проверки
        // отрубания (EquestriaDismemberment.cs): столько же бойцов выбранной расы (по умолчанию
        // пони) в своём отряде и у врага. По умолчанию 100 на сторону. Раса — ключ из
        // DismemberTestTroopByRace (pony/changeling/dragon/griffon/hippogriff/yak/deer), по
        // просьбе пользователя 07.10.2026 (раньше бой всегда был пони-онли).
        // Вражеский отряд — контейнер бандитского клана (гарантированно враждебен любому), но состав
        // полностью свой, не бандитский шаблон.
        //
        // Не один на всех одинаковый комплект (как раньше) — по просьбе пользователя 07.10.2026
        // добавляем войску НЕСКОЛЬКО вариантов снаряжения (разный двуручный меч + случайная броня
        // по слотам, тот же пул, что у EquestriaRaceParty.Dress), а дальше это уже штатное
        // поведение движка: обычным войскам при спавне случайно достаётся один из вариантов
        // BattleEquipments (так и ваниль делает бойцам с несколькими EquipmentRoster в XML).
        // Доступа на добавление варианта в публичном API нет — добираемся до приватного списка
        // MBEquipmentRoster._equipments рефлексией (тот же приём, что уже используется в проекте
        // для AgentVisuals.GetEntity и т.п.).
        [CommandLineFunctionality.CommandLineArgumentFunction("dismember_test", "equestria")]
        public static string DismembermentTestBattle(List<string> args)
        {
            if (Campaign.Current == null || MobileParty.MainParty == null)
            {
                return "Доступно только в кампании.";
            }
            if (MobileParty.MainParty.MapEvent != null || PlayerEncounter.Current != null)
            {
                return "Игрок уже в бою или в диалоге.";
            }
            int perSide = args != null && args.Count > 0 && int.TryParse(args[0], out int n)
                ? Math.Max(1, Math.Min(200, n)) : 100;
            string race = args != null && args.Count > 1 && !string.IsNullOrWhiteSpace(args[1])
                ? args[1].Trim().ToLowerInvariant() : "pony";
            if (!DismemberTestTroopByRace.TryGetValue(race, out string troopId))
            {
                return "Неизвестная раса \"" + race + "\". Доступные: "
                    + string.Join(", ", DismemberTestTroopByRace.Keys) + ".";
            }

            CharacterObject troop = MBObjectManager.Instance.GetObject<CharacterObject>(troopId);
            if (troop == null)
            {
                return $"Не нашлось войско {troopId} (раса {race}).";
            }
            string variantsResult = AddRandomEquipmentVariants(troop, 10);
            if (variantsResult != null)
            {
                return variantsResult;
            }

            MobileParty.MainParty.MemberRoster.AddToCounts(troop, perSide);

            // Герою — тоже двуручный меч (по просьбе пользователя 07.10.2026), чтобы и его удары
            // попадали под детект отрубания, не только у войск.
            if (Hero.MainHero != null)
            {
                var swords = TwoHandedSwords.Select(id => MBObjectManager.Instance.GetObject<ItemObject>(id))
                    .Where(it => it != null).ToList();
                if (swords.Count > 0)
                {
                    var sword = new EquipmentElement(swords[MBRandom.RandomInt(swords.Count)]);
                    Hero.MainHero.BattleEquipment[EquipmentIndex.Weapon0] = sword;
                    Hero.MainHero.CivilianEquipment[EquipmentIndex.Weapon0] = sword;
                }
            }

            Clan clan = Clan.BanditFactions.FirstOrDefault();
            if (clan == null || clan.DefaultPartyTemplate == null)
            {
                return "Не нашлось шаблона отряда для вражеской стороны.";
            }
            var near = new CampaignVec2(MobileParty.MainParty.GetPosition2D + new Vec2(0.6f, 0.6f), true);
            Settlement home = Settlement.All.Where(s => s.IsTown || s.IsVillage)
                .OrderBy(s => s.GetPosition2D.DistanceSquared(near.ToVec2())).FirstOrDefault();
            string id = "eq_dismember_test_" + MBRandom.RandomInt(100000);
            MobileParty enemy = BanditPartyComponent.CreateLooterParty(id, clan, home, false,
                clan.DefaultPartyTemplate, near);
            enemy.MemberRoster.Clear();
            enemy.MemberRoster.AddToCounts(troop, perSide);

            EncounterManager.StartPartyEncounter(PartyBase.MainParty, enemy.Party);
            EquestriaCrashLog.Log($"тест отрубания: {perSide} vs {perSide} ({race}, {troopId}), "
                + "разные двуручные мечи и броня");
            return $"Бой начат: {perSide} vs {perSide}, раса {race} ({troop.Name}), у каждого свой двуручный меч и броня.";
        }

        private static readonly FieldInfo EquipmentRosterField =
            AccessTools.Field(typeof(BasicCharacterObject), "_equipmentRoster");
        private static readonly FieldInfo EquipmentsListField =
            AccessTools.Field(typeof(MBEquipmentRoster), "_equipments");

        /// <summary>Добавляет count случайных вариантов снаряжения (двуручный меч + броня по
        /// слотам) войску troop — движок дальше сам раздаёт их бойцам случайно при спавне, как
        /// у любого ванильного войска с несколькими EquipmentRoster. Возвращает сообщение об
        /// ошибке, либо null при успехе.</summary>
        private static string AddRandomEquipmentVariants(CharacterObject troop, int count)
        {
            var swords = TwoHandedSwords.Select(id => MBObjectManager.Instance.GetObject<ItemObject>(id))
                .Where(it => it != null).ToList();
            if (swords.Count == 0)
            {
                return "Не нашлось ни одного двуручного меча из списка.";
            }
            object roster = EquipmentRosterField?.GetValue(troop);
            if (roster == null)
            {
                return "У войска embers_of_flame_tier_3 нет _equipmentRoster — не могу добавить варианты.";
            }
            if (!(EquipmentsListField?.GetValue(roster) is System.Collections.IList equipments))
            {
                return "Не нашёл список _equipments у MBEquipmentRoster.";
            }
            for (int i = 0; i < count; i++)
            {
                var equipment = new Equipment(Equipment.EquipmentType.Battle);
                equipment[EquipmentIndex.Weapon0] = new EquipmentElement(swords[MBRandom.RandomInt(swords.Count)]);
                // Полуголые в лёгкой броне (по просьбе пользователя 07.10.2026) — только лёгкий
                // торс (ткань/кожа, не кольчуга/латы), ноги/руки/голова голые: и отрубание виднее
                // на глаз, и сам крой брони не мешает разрезу.
                SetRandomArmor(equipment, EquipmentIndex.Body, ItemObject.ItemTypeEnum.BodyArmor, lightOnly: true);
                equipments.Add(equipment);
            }
            return null;
        }

        private static void SetRandomArmor(Equipment equipment, EquipmentIndex slot, ItemObject.ItemTypeEnum type,
            bool lightOnly = false)
        {
            var pool = EquestriaRaceParty.Pool(type);
            if (lightOnly)
            {
                pool = pool.Where(it => it.ArmorComponent.MaterialType == ArmorComponent.ArmorMaterialTypes.Cloth
                    || it.ArmorComponent.MaterialType == ArmorComponent.ArmorMaterialTypes.Leather).ToList();
            }
            if (pool.Count == 0)
            {
                return;
            }
            equipment[slot] = new EquipmentElement(pool[MBRandom.RandomInt(pool.Count)]);
        }
    }
}
