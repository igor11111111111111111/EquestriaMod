using System;
using System.IO;
using System.Linq;
using IOPath = System.IO.Path;
using HarmonyLib;
using TaleWorlds.Engine;
using TaleWorlds.Engine.GauntletUI;
using TaleWorlds.Library;
using TaleWorlds.ModuleManager;

namespace EquestriaMod
{
    // Our own picture on the loading screen.
    //
    // Loading pictures are sprites of a category: GauntletDefaultLoadingWindowManager takes a category and
    // before each loading asks itself for a part name (LoadImage). Adding a part to the vanilla
    // category is impossible: the game takes the picture count from the vanilla category and ours never comes up.
    // Replacing the category name is too late as well: the loading screen is created before our mod loads
    // (verified 2026-09-18: the patch on GetSpriteCategoryName is applied, but the picture stays vanilla).
    // So we replace the PICTURE NAME in LoadImage, and load our category ourselves.
    //
    // The second pitfall: sprite sheets are TEXTURES, and the game takes textures only from
    // packed .tpac files. Our PNG lies loose, and the log had «Cannot find texture:
    // ui_eq_loading_1», after which the loading window fell back to the vanilla picture. To avoid running
    // the picture through the editor on every replacement, we intercept the texture loading itself and read the PNG
    // from disk.
    public static class EquestriaLoadingScreen
    {
        public const string Category = "ui_eq_loading";
        // There can be any number of pictures: each lies in its own sheet and as its own part
        // eq_loading_01, eq_loading_02, ... (tools/make_loading_screen.py). The list is not hardcoded
        // here but taken from the loaded category: add a picture, rerun the script,
        // and it will enter the draw by itself.
        public const string PartPrefix = "eq_loading_";
        private const string ManagerType = "TaleWorlds.MountAndBlade.GauntletUI.GauntletDefaultLoadingWindowManager";

        private static bool _loaded;
        private static string[] _parts = new string[0];
        private static readonly Random _dice = new Random();
        // Number of the previous picture: with two or more, the same one does not come up twice in a row
        private static int _last = -1;

        public static void Apply(Harmony harmony)
        {
            var context = typeof(TwoDimensionEngineResourceContext);
            var loadTexture = AccessTools.Method(
                context, "TaleWorlds.TwoDimension.ITwoDimensionResourceContext.LoadTexture");
            if (loadTexture != null)
            {
                harmony.Patch(loadTexture, prefix: new HarmonyMethod(typeof(EquestriaLoadingScreen), nameof(OurSheet)));
            }
            else
            {
                EquestriaCrashLog.Warn("загрузочный экран: загрузка текстур не найдена — лист спрайтов не подменить");
            }

            var manager = AccessTools.TypeByName(ManagerType);
            var load = manager == null ? null : AccessTools.Method(manager, "LoadImage");
            if (load == null)
            {
                EquestriaCrashLog.Warn("загрузочный экран: метод выбора картинки не найден — останется ванильный");
                return;
            }
            harmony.Patch(load, postfix: new HarmonyMethod(typeof(EquestriaLoadingScreen), nameof(UseOurImage)));
            EquestriaCrashLog.Log($"загрузочный экран: картинки мода {PartPrefix}* из категории {Category}");
        }

        // All our sprite categories start with ui_eq_ (loading, culture decorations…);
        // their sheets also lie loose and are read here too.
        public const string OurCategoryPrefix = "ui_eq_";

        // Path to the category sheets: Module/GUI/SpriteSheets/<category>/<category>_1.png
        private static string SheetFolder(string category)
        {
            return IOPath.Combine(ModuleHelper.GetModuleFullPath("EquestriaMod"), "GUI", "SpriteSheets", category);
        }

        // The engine will not find our category's sheet (it is not in a .tpac), so we hand over a texture read from
        // disk. Which sheet is needed, the engine says in the name: ui_eq_loading_1, _2 and so on;
        // the category is the name without the number.
        private static bool OurSheet(string name, ref TaleWorlds.TwoDimension.Texture __result)
        {
            if (string.IsNullOrEmpty(name))
            {
                return true;
            }
            string sheet = IOPath.GetFileNameWithoutExtension(name);
            if (!sheet.StartsWith(OurCategoryPrefix, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
            int cut = sheet.LastIndexOf('_');
            string category = cut > 0 ? sheet.Substring(0, cut) : sheet;
            string folder = SheetFolder(category);
            string file = IOPath.Combine(folder, sheet + ".png");
            if (!File.Exists(file))
            {
                // Unexpected sheet name: hand over the first one, it always exists
                file = IOPath.Combine(folder, category + "_1.png");
            }
            Texture texture = FromFile(folder, file);
            if (texture == null)
            {
                EquestriaCrashLog.Warn("лист спрайтов: не удалось прочитать " + file);
                return true;
            }
            __result = new TaleWorlds.TwoDimension.Texture(new EngineTexture(texture));
            return false;
        }

        // How the engine loads PNG is not known in advance: we try one by one and write to the log
        // which one worked.
        private static Texture FromFile(string folder, string file)
        {
            if (!File.Exists(file))
            {
                return null;
            }
            Texture texture = Attempt("LoadTextureFromPath",
                () => Texture.LoadTextureFromPath(IOPath.GetFileName(file), folder));
            if (texture == null)
            {
                texture = Attempt("CreateTextureFromPath", () => Texture.CreateTextureFromPath(
                    new PlatformFilePath(new PlatformDirectoryPath(PlatformFileType.Application, folder),
                        IOPath.GetFileName(file))));
            }
            if (texture == null)
            {
                texture = Attempt("CreateFromMemory", () => Texture.CreateFromMemory(File.ReadAllBytes(file)));
            }
            return texture;
        }

        private static Texture Attempt(string how, Func<Texture> make)
        {
            try
            {
                Texture texture = make();
                bool ok = texture != null && texture.IsValid;
                EquestriaCrashLog.Log($"загрузочный экран: {how} — {(ok ? "лист загружен" : "не вышло")}");
                return ok ? texture : null;
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Log($"загрузочный экран: {how} — {e.GetType().Name}: {e.Message}");
                return null;
            }
        }

        private static void UseOurImage(ref string imageName)
        {
            try
            {
                if (!_loaded)
                {
                    _loaded = true;
                    object category = UIResourceManager.LoadSpriteCategory(Category);
                    EquestriaCrashLog.Log(category != null
                        ? $"загрузочный экран: категория {Category} загружена"
                        : $"загрузочный экран: категория {Category} не найдена — картинка останется ванильной");
                    if (category == null)
                    {
                        return;
                    }
                    var data = UIResourceManager.SpriteData;
                    _parts = data.SpriteParts.Keys
                        .Where(k => k.StartsWith(PartPrefix, StringComparison.OrdinalIgnoreCase)
                            && data.GetSprite(k) != null)
                        .OrderBy(k => k, StringComparer.OrdinalIgnoreCase).ToArray();
                    EquestriaCrashLog.Log("загрузочный экран: наших картинок " + _parts.Length
                        + (_parts.Length > 0 ? " — " + string.Join(", ", _parts) : "")
                        + ", всего спрайтов " + data.Sprites.Count);
                }
                if (_parts.Length == 0)
                {
                    return;
                }
                imageName = _parts[Pick()];
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Warn("загрузочный экран: " + e.Message);
            }
        }

        // A random picture, but not the same as last time: with two pictures a repeat in a row
        // is immediately noticeable.
        private static int Pick()
        {
            if (_parts.Length == 1)
            {
                return 0;
            }
            int index = _dice.Next(_parts.Length);
            if (index == _last)
            {
                index = (index + 1 + _dice.Next(_parts.Length - 1)) % _parts.Length;
            }
            _last = index;
            return index;
        }
    }
}
