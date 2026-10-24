using System.Collections.Generic;
using TaleWorlds.CampaignSystem;
using TaleWorlds.Library;

namespace EquestriaMod
{
    // Полосатая грива/хвост/крылья/рог у пони — выбор, а не всегда: только сама заливка (Color2 у
    // шейдера волос не рисует ничего вообще, проверено в игре 29.09.2026 — второй цвет для полос
    // не годится), поэтому полосы — это ОТДЕЛЬНЫЙ материал с запечённой через реальную UV текстурой
    // (tools/make_pony_hair_stripe_texture.py и bake_stripes_all.py), а не второй цвет одного и
    // того же материала. Держим выбор здесь, отдельно от EquestriaBodyParts — это состояние
    // персонажа (сохраняется), а не подгонка меша на кадр.
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
            // Кэш "какого цвета была грива у этого bodyCode" (EquestriaBodyParts.HairLookByCode) —
            // без сохранения бойцы в наглухо закрытых шлемах/капюшонах каждую новую сессию заново
            // получали белый рог/хвост, пока их гриву хоть где-то не покажут (замечено 29.09.2026).
            EquestriaBodyParts.SyncHairLookCache(dataStore);
        }

        // Испытано в игре: полосатые материалы — свои, не просто второй цвет. По каждой части —
        // на какой материал переключаться (сплошной у всех один и тот же: eq_pony_hair).
        public const string PlainMaterial = "eq_pony_hair";

        // Крыльев и рога тут больше нет: по лору MLP они цвета тела, а не гривы (см. HairTinted в
        // EquestriaBodyParts.cs) — полоски были только пока они красились цветом волос (рог убран
        // 30.09.2026, тем же приёмом, что и крылья раньше).
        public static readonly Dictionary<string, string> StripeMaterialByMesh =
            new Dictionary<string, string>(System.StringComparer.OrdinalIgnoreCase)
        {
            { "eq_pony_tail", "eq_pony_tail_stripe" },
            { "eq_pony_hair", "eq_pony_mane_stripe" },
        };

        // Консоль (Alt+~), пока нет кнопок в редакторе: equestria.hair_stripe on|off
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
