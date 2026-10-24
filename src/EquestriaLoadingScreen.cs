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
    // Своя картинка на загрузочном экране.
    //
    // Картинки загрузки — спрайты категории: GauntletDefaultLoadingWindowManager берёт категорию и
    // перед каждой загрузкой просит у себя же имя части (LoadImage). Дописать часть в ванильную
    // категорию нельзя: число картинок игра берёт у ванильной категории и наша никогда не выпадает.
    // Подменить имя категории тоже поздно: загрузочный экран создаётся раньше, чем грузится наш мод
    // (проверено 2026-09-18: патч на GetSpriteCategoryName применяется, а картинка остаётся ванильной).
    // Поэтому подменяем ИМЯ КАРТИНКИ в LoadImage, а свою категорию подгружаем сами.
    //
    // Второй подводный камень: листы спрайтов — это ТЕКСТУРЫ, а текстуры игра берёт только из
    // упакованных .tpac. Наш PNG лежит россыпью, и в журнале было «Cannot find texture:
    // ui_eq_loading_1», после чего окно загрузки откатывалось на ванильную картинку. Чтобы не гонять
    // картинку через редактор при каждой замене, перехватываем саму загрузку текстуры и читаем PNG
    // с диска.
    public static class EquestriaLoadingScreen
    {
        public const string Category = "ui_eq_loading";
        // Картинок может быть сколько угодно: каждая лежит своим листом и своей частью
        // eq_loading_01, eq_loading_02, ... (tools/make_loading_screen.py). Список не прописан
        // здесь, а берётся из загруженной категории — добавили картинку, перезапустили скрипт,
        // и она сама попадёт в розыгрыш.
        public const string PartPrefix = "eq_loading_";
        private const string ManagerType = "TaleWorlds.MountAndBlade.GauntletUI.GauntletDefaultLoadingWindowManager";

        private static bool _loaded;
        private static string[] _parts = new string[0];
        private static readonly Random _dice = new Random();
        // Номер прошлой картинки: при двух и более подряд одна и та же не выпадает
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

        // Все наши категории спрайтов начинаются с ui_eq_ (загрузка, оформление народностей…) —
        // их листы тоже лежат россыпью и читаются здесь же.
        public const string OurCategoryPrefix = "ui_eq_";

        // Путь к листам категории: Module/GUI/SpriteSheets/<категория>/<категория>_1.png
        private static string SheetFolder(string category)
        {
            return IOPath.Combine(ModuleHelper.GetModuleFullPath("EquestriaMod"), "GUI", "SpriteSheets", category);
        }

        // Лист нашей категории движок не найдёт (он не в .tpac) — отдаём текстуру, прочитанную с
        // диска. Какой именно лист нужен, движок говорит в имени: ui_eq_loading_1, _2 и так далее;
        // категория — имя без номера.
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
                // Неожиданное имя листа — отдаём первый, он есть всегда
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

        // Способ загрузки PNG движком заранее не известен — пробуем по очереди и пишем в журнал,
        // какой сработал.
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

        // Случайная картинка, но не та же, что в прошлый раз: на двух картинках повтор подряд
        // сразу бросается в глаза.
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
