using System.Collections.Generic;
using System.Linq;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Грива с ушами у пони — предмет в слоте шлема без защиты (eq_pony_mane в equestria_items.xml).
    // Слот причёски для расы pony непригоден: движок рвёт на куски любую причёску, даже ванильную.
    // Зато настоящий шлем занимает тот же слот и просто заменяет гриву — сквозь него ничего не торчит.
    public static class EquestriaMane
    {
        // Грива и рог пони — настоящая причёска расы (tools/make_pony_manes.py), предметов для них нет.

        public const string RaceId = "pony";
        public const string ChangelingRaceId = "changeling";
        public const string DeerRaceId = "deer";

        // У пони грива и рог — причёска расы (tools/make_pony_manes.py), слот головы остаётся пустым.
        // Хвост, крылья и хвост оленя больше не предметы: их вешает на скелет EquestriaBodyParts,
        // поэтому слот плаща остаётся свободным (можно надеть накидку) и ничего не пропадает.
        private static readonly (string Id, EquipmentIndex Slot)[] Parts = { };
        // У чейнджлингов рог, уши и гребень — часть головы новой модели (make_changeling_model.py),
        // предмета eq_changeling_crest больше нет. Пока он тут оставался, журнал на каждый запуск
        // получал по 468 строк «предмет не найден» — по одной на каждого чейнджлинга в мире.
        private static readonly (string Id, EquipmentIndex Slot)[] ChangelingParts = { };
        private static readonly (string Id, EquipmentIndex Slot)[] DeerParts = { };

        // Надевает гриву героям-пони со свободной головой (и в бою, и в гражданской одежде).
        public static int EnsureForPonies()
        {
            if (Campaign.Current == null)
            {
                return 0;
            }
            var race = FaceGen.GetRaceOrDefault(RaceId);
            var changeling = FaceGen.GetRaceOrDefault(ChangelingRaceId);
            var deer = FaceGen.GetRaceOrDefault(DeerRaceId);
            var count = 0;
            var ponies = 0;
            foreach (var hero in Hero.AllAliveHeroes)
            {
                // GetRaceOrDefault отдаёт 0 (человек), если расы нет, — такую не путаем с людьми
                var heroRace = hero.CharacterObject?.Race ?? -1;
                var parts = heroRace == race ? Parts
                    : heroRace == changeling && changeling != 0 ? ChangelingParts
                    : heroRace == deer && deer != 0 ? DeerParts
                    : null;
                if (parts == null)
                {
                    continue;
                }
                ponies++;
                foreach (var (id, slot) in parts)
                {
                    var item = MBObjectManager.Instance.GetObject<ItemObject>(id);
                    if (item == null)
                    {
                        EquestriaCrashLog.Warn($"предмет {id} не найден — {hero.StringId} останется без него");
                        continue;
                    }
                    foreach (var equipment in new[] { hero.BattleEquipment, hero.CivilianEquipment })
                    {
                        if (equipment != null && equipment[slot].IsEmpty)
                        {
                            equipment.AddEquipmentToSlotWithoutAgent(slot, new EquipmentElement(item));
                            count++;
                        }
                    }
                }
            }
            EquestriaCrashLog.Log($"грива/хвост: героев-пони, чейнджлингов и оленей {ponies}, "
                + $"заполнено пустых слотов {count}");
            return count;
        }

        // Консоль (Alt+~): equestria.give_mane — выдать гриву и хвост в инвентарь и надеть в свободные слоты
        [CommandLineFunctionality.CommandLineArgumentFunction("give_mane", "equestria")]
        public static string GiveManeCommand(List<string> args)
        {
            if (Campaign.Current == null || Hero.MainHero == null)
            {
                return "Available only in a campaign.";
            }
            var missing = new List<string>();
            foreach (var (id, _) in Parts)
            {
                var item = MBObjectManager.Instance.GetObject<ItemObject>(id);
                if (item == null)
                {
                    missing.Add(id);
                }
                else
                {
                    MobileParty.MainParty.ItemRoster.AddToCounts(item, 1);
                }
            }
            var worn = EnsureForPonies();
            var result = worn > 0 ? "Mane/tail added and equipped." : "Mane/tail added to the party inventory.";
            return missing.Count > 0 ? result + " Missing items: " + string.Join(", ", missing) : result;
        }
    }
}
