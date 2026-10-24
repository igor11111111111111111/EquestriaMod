using System;
using System.Collections.Generic;
using HarmonyLib;
using TaleWorlds.CampaignSystem;
using TaleWorlds.Core;
using TaleWorlds.Engine.GauntletUI;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Culture cards and parallax backgrounds in the selection window at campaign start.
    //
    // The pictures are in their own sprite category ui_eq_culture (Module/GUI/EquestriaCultureSpriteData.xml,
    // built by tools/make_culture_art.py). The sprites are named the vanilla way
    // (CharacterCreation\Culture\<culture id> and _1.._4), so the vanilla brushes and the screen prefab
    // pick them up by themselves - but the game loads a category's textures only on request, the vanilla
    // ui_charactercreation is loaded by the character creation screen, and ours has to be loaded by us.
    public static class EquestriaCultureArt
    {
        public const string Category = "ui_eq_culture";

        private static bool _loaded;

        public static void Load()
        {
            if (_loaded)
            {
                return;
            }
            try
            {
                var data = UIResourceManager.SpriteData;
                if (data == null || !data.SpriteCategories.ContainsKey(Category))
                {
                    EquestriaCrashLog.Log("оформление народностей: категории " + Category + " нет — останутся ванильные картинки");
                    return;
                }
                UIResourceManager.LoadSpriteCategory(Category);
                _loaded = true;
                EquestriaCrashLog.Log("оформление народностей: категория " + Category + " загружена");
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Warn("оформление народностей: " + e.GetType().Name + ": " + e.Message);
            }
        }

        // The name and description on this same screen are taken by CharacterCreationCultureVM not from the
        // culture XML but from the strings str_culture_rich_name.<id> and str_culture_description.<id>
        // (Native/module_strings.xml): "Aserai Sultanate", "The Aserai live in the Nahasa desert..."
        // Our own strings with the same ids from XML do not
        // override the vanilla ones - GameText stores variants as a list and returns the first. So we
        // substitute the culture's name and text from our spcultures right into the string table.
        public static void ApplyTexts()
        {
            try
            {
                // The same string manager that GameTexts.FindText uses in CharacterCreationCultureVM
                var manager = AccessTools.Field(typeof(GameTexts), "_gameTextManager")?.GetValue(null) as GameTextManager
                    ?? Game.Current?.GameTextManager;
                var objects = MBObjectManager.Instance;
                if (manager == null || objects == null)
                {
                    EquestriaCrashLog.Warn("оформление народностей: тексты — нет " + (manager == null ? "менеджера строк" : "менеджера объектов"));
                    return;
                }
                GameText names = manager.GetGameText("str_culture_rich_name");
                GameText descriptions = manager.GetGameText("str_culture_description");
                if (names == null || descriptions == null)
                {
                    EquestriaCrashLog.Warn("оформление народностей: тексты — нет строк str_culture_rich_name/description");
                    return;
                }
                int done = 0;
                foreach (CultureObject culture in objects.GetObjectTypeList<CultureObject>())
                {
                    if (culture == null || !culture.IsMainCulture || culture.Name == null)
                    {
                        continue;
                    }
                    names.SetVariationWithId(culture.StringId, culture.Name, NoTags());
                    if (culture.EncyclopediaText != null && culture.EncyclopediaText.Length > 0)
                    {
                        descriptions.SetVariationWithId(culture.StringId, culture.EncyclopediaText, NoTags());
                    }
                    done++;
                }
                EquestriaCrashLog.Log("оформление народностей: имена и описания подставлены для " + done + " культур");
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Warn("оформление народностей: тексты — " + e.GetType().Name + ": " + e.Message + " | " + e.StackTrace);
            }
        }

        // GameTextVariation does choiceTags.ToArray() - null is not allowed there
        private static List<GameTextManager.ChoiceTag> NoTags()
        {
            return new List<GameTextManager.ChoiceTag>();
        }

        public static void Unload()
        {
            if (!_loaded)
            {
                return;
            }
            try
            {
                UIResourceManager.SpriteData.SpriteCategories[Category].Unload();
                _loaded = false;
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Warn("оформление народностей: выгрузка — " + e.Message);
            }
        }
    }
}
