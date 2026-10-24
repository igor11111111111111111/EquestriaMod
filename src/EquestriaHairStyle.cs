using System.Collections.Generic;
using TaleWorlds.CampaignSystem;
using TaleWorlds.Library;

namespace EquestriaMod
{
    // A striped mane/tail/wings/horn on a pony is a choice, not always on: only the fill itself (Color2 of
    // the hair shader draws nothing at all, checked in game 29.09.2026 — a second colour is no good for
    // stripes), so stripes are a SEPARATE material with a texture baked through the real UV
    // (tools/make_pony_hair_stripe_texture.py and bake_stripes_all.py), not a second colour of one and
    // the same material. The choice is kept here, separate from EquestriaBodyParts — it is character
    // state (saved), not a per-frame mesh adjustment.
    public class EquestriaHairStyle : CampaignBehaviorBase
    {
        private static bool _striped;

        public static bool Striped => _striped;

        public static void SetStriped(bool value)
        {
            _striped = value;
        }

        public override void RegisterEvents()
        {
        }

        public override void SyncData(IDataStore dataStore)
        {
            dataStore.SyncData("eq_pony_hair_striped", ref _striped);
            // Cache of "what colour the mane was for this bodyCode" (EquestriaBodyParts.HairLookByCode) —
            // without saving it, fighters in fully closed helmets/hoods got a white horn/tail again every
            // new session until their mane was shown somewhere (noticed 29.09.2026).
            EquestriaBodyParts.SyncHairLookCache(dataStore);
        }

        // Tested in game: striped materials are separate ones, not just a second colour. For each part —
        // which material to switch to (the plain one is the same for all: eq_pony_hair).
        public const string PlainMaterial = "eq_pony_hair";

        // Wings and horn are no longer here: by MLP lore they are body-coloured, not mane-coloured (see
        // HairTinted in EquestriaBodyParts.cs) — stripes existed only while they were tinted with the hair
        // colour (horn removed 30.09.2026, the same way the wings were earlier).
        public static readonly Dictionary<string, string> StripeMaterialByMesh =
            new Dictionary<string, string>(System.StringComparer.OrdinalIgnoreCase)
        {
            { "eq_pony_tail", "eq_pony_tail_stripe" },
            { "eq_pony_hair", "eq_pony_mane_stripe" },
        };

        // Console (Alt+~), until there are buttons in the editor: equestria.hair_stripe on|off
        [CommandLineFunctionality.CommandLineArgumentFunction("hair_stripe", "equestria")]
        public static string SetStripeCommand(List<string> args)
        {
            if (args.Count != 1 || (args[0] != "on" && args[0] != "off"))
            {
                return "Формат: equestria.hair_stripe on|off";
            }
            _striped = args[0] == "on";
            return "Полосы " + (_striped ? "включены" : "выключены")
                + " — переоткрой окно (инвентарь/отряд/редактор), чтобы увидеть.";
        }
    }
}
