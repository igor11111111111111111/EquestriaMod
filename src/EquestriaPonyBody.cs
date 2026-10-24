using System.Collections.Generic;
using TaleWorlds.CampaignSystem;
using TaleWorlds.Library;

namespace EquestriaMod
{
    // Temporary "wings/tail/horn on-off" switch - in MLP lore not every pony has all the
    // parts: earth ponies have no horn or wings, unicorns only a horn, pegasi only wings,
    // alicorns both. All types have a tail, but a button is needed for it too just in case
    // (e.g. for reviewing races or tests). For now these are just buttons in the corner of the screen
    // (EquestriaHairStyleView), not a real pony type choice at character creation - that is still
    // to be done.
    public class EquestriaPonyBody : CampaignBehaviorBase
    {
        private static bool _wingsEnabled = true;
        private static bool _tailEnabled = true;
        private static bool _hornEnabled = true;

        public static bool WingsEnabled => _wingsEnabled;
        public static bool TailEnabled => _tailEnabled;
        public static bool HornEnabled => _hornEnabled;

        public static void SetWingsEnabled(bool value)
        {
            _wingsEnabled = value;
        }

        public static void SetTailEnabled(bool value)
        {
            _tailEnabled = value;
        }

        public static void SetHornEnabled(bool value)
        {
            _hornEnabled = value;
        }

        public override void RegisterEvents()
        {
        }

        public override void SyncData(IDataStore dataStore)
        {
            dataStore.SyncData("eq_pony_wings_enabled", ref _wingsEnabled);
            dataStore.SyncData("eq_pony_tail_enabled", ref _tailEnabled);
            dataStore.SyncData("eq_pony_horn_enabled", ref _hornEnabled);
        }

        // Console (Alt+~): equestria.pony_wings on|off, equestria.pony_tail on|off,
        // equestria.pony_horn on|off
        [CommandLineFunctionality.CommandLineArgumentFunction("pony_wings", "equestria")]
        public static string SetWingsCommand(List<string> args)
        {
            return SetPart(args, "Крылья", ref _wingsEnabled);
        }

        [CommandLineFunctionality.CommandLineArgumentFunction("pony_tail", "equestria")]
        public static string SetTailCommand(List<string> args)
        {
            return SetPart(args, "Хвост", ref _tailEnabled);
        }

        [CommandLineFunctionality.CommandLineArgumentFunction("pony_horn", "equestria")]
        public static string SetHornCommand(List<string> args)
        {
            return SetPart(args, "Рог", ref _hornEnabled);
        }

        private static string SetPart(List<string> args, string label, ref bool field)
        {
            if (args.Count != 1 || (args[0] != "on" && args[0] != "off"))
            {
                return "Формат: on|off";
            }
            field = args[0] == "on";
            return label + " " + (field ? "включены" : "выключены")
                + " — переоткрой окно (инвентарь/отряд/редактор), чтобы увидеть.";
        }
    }
}
