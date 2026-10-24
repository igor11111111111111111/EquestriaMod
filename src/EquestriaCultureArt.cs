using System;
using System.Collections.Generic;
using HarmonyLib;
using TaleWorlds.CampaignSystem;
using TaleWorlds.Core;
using TaleWorlds.Engine.GauntletUI;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Карточки и параллакс-фоны народностей в окне выбора при старте кампании.
    //
    // Картинки лежат в своей категории спрайтов ui_eq_culture (Module/GUI/EquestriaCultureSpriteData.xml,
    // собирает tools/make_culture_art.py). Спрайты названы по-ванильному
    // (CharacterCreation\Culture\<id культуры> и _1.._4), поэтому ванильные кисти и префаб экрана
    // берут их сами — но текстуры категории игра грузит только по запросу, ванильная
    // ui_charactercreation грузится экраном создания персонажа, а нашу надо поднять самим.
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

        // Название и описание на этом же экране CharacterCreationCultureVM берёт не из XML культуры,
        // а из строк str_culture_rich_name.<id> и str_culture_description.<id> (Native/module_strings.xml):
        // «Султанат асераев», «Асераи живут в пустыне Нахаза…». Свои строки с теми же id из XML не
        // перекрывают ванильные — GameText хранит варианты списком и отдаёт первый. Поэтому
        // подставляем имя и текст культуры из нашего spcultures прямо в таблицу строк.
        public static void ApplyTexts()
        {
            try
            {
                // Тот же менеджер строк, которым пользуется GameTexts.FindText в CharacterCreationCultureVM
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

        // GameTextVariation делает choiceTags.ToArray() — null туда нельзя
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
