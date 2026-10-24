using System.Collections.Generic;
using System.Linq;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // The pony mane with ears is an item in the helmet slot with no protection (eq_pony_mane in
    // equestria_items.xml). The hair slot is unusable for the pony race: the engine tears any hairstyle
    // to pieces, even a vanilla one. But a real helmet takes the same slot and simply replaces the mane -
    // nothing pokes through it.
    public static class EquestriaMane
    {
        // The pony mane and horn are a real race hairstyle (tools/make_pony_manes.py); there are no items for them.

        public const string RaceId = "pony";
        public const string ChangelingRaceId = "changeling";
        public const string DeerRaceId = "deer";

        // For ponies the mane and horn are the race hairstyle (tools/make_pony_manes.py); the head slot stays empty.
        // The tail, wings and the deer tail are no longer items: EquestriaBodyParts attaches them to the skeleton,
        // so the cape slot stays free (a cloak can be worn) and nothing disappears.
        private static readonly (string Id, EquipmentIndex Slot)[] Parts = { };
        // For changelings the horn, ears and crest are part of the new model's head (make_changeling_model.py);
        // the eq_changeling_crest item no longer exists. While it stayed here, the log got 468 lines of
        // "item not found" on every launch - one per changeling in the world.
        private static readonly (string Id, EquipmentIndex Slot)[] ChangelingParts = { };
        private static readonly (string Id, EquipmentIndex Slot)[] DeerParts = { };

        // Puts the mane on pony heroes with a free head slot (both battle and civilian equipment).
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
                // GetRaceOrDefault returns 0 (human) if the race is missing - do not confuse that with humans
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

        // Console (Alt+~): equestria.give_mane - give the mane and tail to the inventory and equip them in free slots
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
