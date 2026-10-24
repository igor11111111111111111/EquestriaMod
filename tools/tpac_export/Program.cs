// Выгрузка мешей из упакованных ассетов Bannerlord (.tpac) в FBX через библиотеку TpacTool (hunharibo, MIT).
//   tpac_export list   <папка с tpac> <фильтр>             — найти метамеши и скелеты по имени
//   tpac_export export <папка с tpac> <меш1,меш2,...> <папка вывода> — по FBX со скелетом human_skeleton
//                                                                      и текстурами в <вывод>\<меш>\
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using TpacTool.IO;
using TpacTool.IO.Assimp;
using TpacTool.Lib;

namespace TpacExport
{
    internal static class Program
    {
        // OBJ читается только с точкой в дробях, а система здесь русская
        private static readonly System.Globalization.CultureInfo Culture =
            System.Globalization.CultureInfo.InvariantCulture;

        // Свойства объекта через рефлексию: простые значения печатаются, списки — длиной и первыми элементами,
        // вложенные объекты — на два уровня вглубь.
        private static void Dump(object obj, string indent, int depth)
        {
            if (obj == null || depth > 2)
                return;
            foreach (var p in obj.GetType().GetProperties(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance))
            {
                if (p.GetIndexParameters().Length > 0)
                    continue;
                object v;
                try { v = p.GetValue(obj); } catch (Exception e) { v = "<" + e.GetType().Name + ">"; }
                if (v == null || v is string || v.GetType().IsPrimitive || v is Guid || v is Enum || v is decimal)
                {
                    Console.WriteLine($"{indent}{p.Name} = {v}");
                }
                else if (v is System.Collections.ICollection c)
                {
                    var first = c.Cast<object>().Take(3).Select(x => x?.ToString());
                    Console.WriteLine($"{indent}{p.Name}: {v.GetType().Name} count={c.Count} [{string.Join("; ", first)}]");
                    if (depth < 2 && c.Count > 0 && c.Count < 8)
                        foreach (var item in c)
                            if (item != null && !item.GetType().IsPrimitive && !(item is string))
                                Dump(item, indent + "    ", depth + 1);
                }
                else if (p.Name == "Material" || p.Name == "Owner" || p.Name == "Package")
                {
                    Console.WriteLine($"{indent}{p.Name} = {v}");
                }
                else
                {
                    Console.WriteLine($"{indent}{p.Name}: {v.GetType().Name}");
                    Dump(v, indent + "    ", depth + 1);
                }
            }
        }

        // Правка флагов шейдера: аргумент вида flags=+self_illumination,-use_double_colormap...
        // Плюс добавляет флаг, минус снимает. Всё остальное у клона остаётся от исходника —
        // в том числе разметка вершин (скиннинг), без которой броня перестала бы гнуться.
        private static void EditFlags(Material material, string[] args)
        {
            var spec = args.FirstOrDefault(a => a.StartsWith("flags="));
            if (spec == null)
            {
                return;
            }
            foreach (var item in spec.Substring("flags=".Length).Split(','))
            {
                var name = item.Trim();
                if (name.Length < 2)
                {
                    continue;
                }
                var flag = name.Substring(1);
                if (name[0] == '+')
                {
                    if (!material.ShaderMaterialFlags.Contains(flag))
                    {
                        material.ShaderMaterialFlags.Add(flag);
                    }
                }
                else if (name[0] == '-')
                {
                    material.ShaderMaterialFlags.Remove(flag);
                }
                else
                {
                    Console.WriteLine("флаг без знака (+ или -): " + name);
                    continue;
                }
                Console.WriteLine($"  флаг {name[0]}{flag}");
            }
        }

        // GUID материала считаем от имени: повторный запуск даёт тот же идентификатор,
        // и меши, уже привязанные к нашему материалу, не теряют его.
        private static Guid StableGuid(string name)
        {
            using (var md5 = System.Security.Cryptography.MD5.Create())
            {
                return new Guid(md5.ComputeHash(System.Text.Encoding.UTF8.GetBytes(name)));
            }
        }

        // На какие ассеты ссылается этот: отдельный список пакета плюс GUID'ы, встреченные в
        // неразобранных метаданных (у частиц разбора нет, а текстуры там именно так и лежат).
        private static IEnumerable<Guid> References(AssetItem asset)
        {
            var guids = new List<Guid>();
            foreach (var dependence in asset.UnknownDependences)
            {
                guids.Add(dependence.UnknownGuid1);
                guids.Add(dependence.UnknownGuid2);
                guids.Add(dependence.UnknownGuid3);
            }
            byte[] metadata = null;
            try
            {
                metadata = asset.WriteMetadata();
            }
            catch (NotImplementedException)
            {
                // разобранный тип (материал, меш) — у него зависимости и так в списке выше
            }
            // Только метаданные. Тело ассета не трогаем: у неразобранных типов чтение поля Data
            // сбивает ленивую загрузку, и при сохранении пакет падает на пустом буфере
            // (проверено на частицах 2026-09-24). Что внутри тела — смотрим уже по готовому файлу.
            ScanForGuids(metadata, guids);
            return guids.Where(g => g != Guid.Empty && g != asset.Guid).Distinct();
        }

        private static void ScanForGuids(byte[] data, List<Guid> guids)
        {
            if (data == null)
            {
                return;
            }
            var buffer = new byte[16];
            for (var i = 0; i + 16 <= data.Length; i += 4)   // ссылки выровнены по 4 байта
            {
                Array.Copy(data, i, buffer, 0, 16);
                var guid = new Guid(buffer);
                if (guid != Guid.Empty)
                {
                    guids.Add(guid);
                }
            }
        }

        private static int Main(string[] args)
        {
            if (args.Length < 3)
            {
                Console.WriteLine("usage: list <asset dir> <filter> | export <asset dir> <mesh name> <out.fbx>");
                return 1;
            }

            // Папок с ассетами можно указать несколько через «;»: так материал клонируется из
            // ванильного пакета, а текстуры к нему берутся из нашего.
            var manager = new AssetManager();
            foreach (var dir in args[1].Split(';'))
            {
                Console.WriteLine($"loading {dir} ...");
                manager.Load(new DirectoryInfo(dir));
            }
            DefaultDependenceResolver.Instance = manager; // ссылки мешей на материалы и текстуры ищутся здесь
            Console.WriteLine($"packages: {manager.LoadedPackages.Count}, assets: {manager.LoadedAssets.Count}");

            if (args[0] == "diag")
            {
                // какие материалы нужны мешу и загружены ли они; сколько ассетов каждого типа прочитано
                foreach (var group in manager.LoadedAssets.GroupBy(a => a.GetType().Name).OrderBy(g => g.Key))
                    Console.WriteLine($"type {group.Key}: {group.Count()}");
                var mesh = manager.LoadedAssets.OfType<Metamesh>().FirstOrDefault(a => a.Name == args[2]);
                if (mesh == null)
                    return 2;
                foreach (var m in mesh.Meshes)
                {
                    var resolved = m.Material.TryGetItem(out var mat);
                    var raw = manager.GetAsset(m.Material.Guid);
                    Console.WriteLine($"lod {m.Lod} mesh {m.Name}: material {m.Material.Guid} resolved={resolved} " +
                                      $"{(mat != null ? mat.Name : "")} asset-in-manager={(raw != null ? raw.GetType().Name + " " + raw.Name : "none")}");
                }
                return 0;
            }

            // tpac_export info <папка с tpac> <меш1,меш2,...> — всё, что лежит в меше: флаги, потоки вершин, морфы
            if (args[0] == "info")
            {
                foreach (var name in args[2].Split(','))
                {
                    var mesh = manager.LoadedAssets.OfType<Metamesh>().FirstOrDefault(a => a.Name == name);
                    if (mesh == null)
                    {
                        // не меш — любой ассет с таким именем (материал, текстура, шейдер)
                        var any = manager.LoadedAssets.Where(x => x.Name == name).ToList();
                        if (any.Count == 0)
                            Console.WriteLine($"asset not found: {name}");
                        foreach (var asset in any)
                        {
                            Console.WriteLine($"== {name}: {asset.GetType().Name}");
                            Dump(asset, "  ", 0);
                        }
                        continue;
                    }
                    Console.WriteLine($"== {name}: meshes {mesh.Meshes.Count}");
                    Dump(mesh, "  ", 0);
                    foreach (var m in mesh.Meshes)
                    {
                        Console.WriteLine($"  -- lod {m.Lod} {m.Name}");
                        Dump(m, "    ", 0);
                    }
                }
                return 0;
            }

            if (args[0] == "list")
            {
                var filter = args[2].ToLowerInvariant();
                foreach (var asset in manager.LoadedAssets
                             .Where(a => (a.Type == Metamesh.TYPE_GUID || a.Type == Skeleton.TYPE_GUID)
                                         && a.Name.ToLowerInvariant().Contains(filter))
                             .OrderBy(a => a.Name))
                {
                    var kind = asset.Type == Skeleton.TYPE_GUID ? "skeleton" : "metamesh";
                    var extra = asset is Metamesh m ? $" meshes={m.Meshes.Count}" : "";
                    Console.WriteLine($"{kind,-9} {asset.Name}{extra}");
                }
                return 0;
            }

            // tpac_export texture <папка с tpac> <фильтр,фильтр,...> <папка вывода> [.png/.dds] — текстуры
            // Фильтров можно перечислить несколько через запятую: редакторские пакеты игры
            // (Modules\Native\EmAssetPackages — только там у ванильных текстур есть сами пиксели)
            // читаются секунд двадцать, и повторять это на каждое имя незачем.
            if (args[0] == "texture" && args.Length >= 4)
            {
                var filters = args[2].ToLowerInvariant().Split(',')
                    .Select(f => f.Trim()).Where(f => f.Length > 0).ToArray();
                Directory.CreateDirectory(args[3]);
                var failed = 0;
                foreach (var texture in manager.LoadedAssets.OfType<Texture>()
                             .Where(t => filters.Any(f => t.Name.ToLowerInvariant().Contains(f)))
                             .OrderBy(t => t.Name))
                {
                    var ext = args.Length >= 5 ? args[4] : ".png";
                    var path = Path.Combine(Path.GetFullPath(args[3]), texture.Name + ext);
                    try
                    {
                        TextureExporter.ExportToFile(path, texture);
                        Console.WriteLine($"texture {texture.Name} {texture.Width}x{texture.Height} -> {path}");
                    }
                    catch (Exception e)
                    {
                        Console.WriteLine($"FAILED {texture.Name}: {e.Message}");
                        failed++;
                    }
                }
                return failed;
            }

            // Материалы. Собирать их в редакторе — десятки кликов на каждый, поэтому клонируем
            // ванильный материал в свой пакет: имя новое, текстуры подменяем по номеру слота.
            //   mat-info  <папка с tpac> <имя или часть имени>
            //   mat-clone <папка с tpac> <исходный материал> <выходной .tpac> <новое имя> [слот=текстура ...]
            if (args[0] == "mat-info" && args.Length >= 3)
            {
                // Имён можно перечислить несколько через запятую: каждый запуск заново читает
                // полторы сотни ванильных пакетов, и звать его на каждый материал — минуты.
                var needles = args[2].ToLowerInvariant().Split(',')
                    .Select(n => n.Trim()).Where(n => n.Length > 0).ToArray();
                foreach (var mat in manager.LoadedAssets.OfType<Material>()
                             .Where(m => needles.Any(n => m.Name.ToLowerInvariant().Contains(n)))
                             .OrderBy(m => m.Name))
                {
                    Console.WriteLine($"material {mat.Name} guid {mat.Guid}");
                    Console.WriteLine("  shader: " + (mat.Shader.TryGetItem(out var shader) ? shader.Name : mat.Shader.Guid.ToString()));
                    foreach (var pair in mat.Textures)
                    {
                        Console.WriteLine($"  tex[{pair.Key}] = " +
                                          (pair.Value.TryGetItem(out var tex) ? tex.Name : pair.Value.Guid.ToString()));
                    }
                    Console.WriteLine("  shader flags: " + string.Join(", ", mat.ShaderMaterialFlags));
                    Console.WriteLine("  vertex layout: " + string.Join(", ", mat.VertexLayoutFlags));
                }
                return 0;
            }

            // Правка флагов шейдера у клона: аргумент flags=+имя,-имя.
            // Нужна броне улья: чтобы она светилась, материалу надо добавить self_illumination и
            // снять use_double_colormap_with_mask_texture — обе настройки читают ОДИН слот
            // текстуры (первый), и вместе они не работают.
            if (args[0] == "mat-clone" && args.Length >= 5)
            {
                var source = manager.LoadedAssets.OfType<Material>().FirstOrDefault(m => m.Name == args[2]);
                if (source == null)
                {
                    Console.WriteLine("material not found: " + args[2]);
                    return 2;
                }
                source.Name = args[4];
                source.Guid = StableGuid(args[4]);
                for (var i = 5; i < args.Length; i++)
                {
                    if (args[i].StartsWith("flags="))
                    {
                        continue;   // разбирается ниже, в EditFlags
                    }
                    var parts = args[i].Split('=');
                    if (parts.Length != 2 || !int.TryParse(parts[0], out var slot))
                    {
                        Console.WriteLine("bad texture override (expected slot=name): " + args[i]);
                        return 3;
                    }
                    var texture = manager.LoadedAssets.OfType<Texture>().FirstOrDefault(t => t.Name == parts[1]);
                    if (texture == null)
                    {
                        Console.WriteLine("texture not found: " + parts[1]);
                        return 4;
                    }
                    source.Textures[slot] = new AssetDependence<Texture>(texture);
                    Console.WriteLine($"  tex[{slot}] <- {texture.Name}");
                }
                EditFlags(source, args);
                var package = new AssetPackage();
                package.Items.Clear();
                package.Items.Add(source);
                var outPath = Path.GetFullPath(args[3]);
                Directory.CreateDirectory(Path.GetDirectoryName(outPath));
                package.Save(outPath);
                Console.WriteLine($"material {source.Name} -> {outPath}");
                return 0;
            }

            // Материалы мешей: mesh-mats <папка> <меш1,меш2,...> — что на каком меше стоит.
            if (args[0] == "mesh-mats" && args.Length >= 3)
            {
                foreach (var name in args[2].Split(','))
                {
                    var mesh = manager.LoadedAssets.OfType<Metamesh>().FirstOrDefault(a => a.Name == name);
                    if (mesh == null)
                    {
                        Console.WriteLine($"{name}: not found");
                        continue;
                    }
                    var mats = mesh.Meshes.Where(m => m.Lod == 0)
                        .Select(m => m.Material.TryGetItem(out var mat) ? mat.Name : m.Material.Guid.ToString())
                        .Distinct();
                    Console.WriteLine($"{name}: {string.Join(", ", mats)}");
                }
                return 0;
            }

            // Пакетное клонирование материалов: один проход по ассетам вместо запуска на каждый.
            //   mat-batch <папка с tpac> <папка вывода> <префикс> <материал1,материал2,...>
            // Для каждого материала пишется <папка вывода>/<префикс><имя>_mtl.tpac; diffuse (слот 0)
            // подменяется на текстуру <префикс><имя>_d, если она уже импортирована в модуль.
            if (args[0] == "mat-batch" && args.Length >= 5)
            {
                var outDir = Path.GetFullPath(args[2]);
                var prefix = args[3];
                Directory.CreateDirectory(outDir);
                var missing = 0;
                foreach (var name in args[4].Split(','))
                {
                    var source = manager.LoadedAssets.OfType<Material>().FirstOrDefault(m => m.Name == name);
                    if (source == null)
                    {
                        Console.WriteLine($"{name}: material not found");
                        missing++;
                        continue;
                    }
                    var newName = prefix + name;
                    // имя нашей текстуры берём от текущей diffuse материала (имена материала и
                    // текстуры у ванили совпадают не всегда: bandit_leather_mat -> bandit_leather_d)
                    var texName = prefix + name + "_d";
                    if (source.Textures.TryGetValue(0, out var current) && current.TryGetItem(out var currentTex))
                    {
                        texName = prefix + currentTex.Name;
                    }
                    var texture = manager.LoadedAssets.OfType<Texture>().FirstOrDefault(t => t.Name == texName);
                    source.Name = newName;
                    source.Guid = StableGuid(newName);
                    if (texture != null)
                    {
                        source.Textures[0] = new AssetDependence<Texture>(texture);
                    }
                    // Карта свечения в слоте 1 (там же, где у ванили маска цвета клана): ставим её
                    // только когда свечение просят флагом — иначе в слоте должна остаться
                    // ванильная маска цвета клана.
                    var wantGlow = args.Any(a => a.StartsWith("flags=") && a.Contains("+self_illumination"));
                    var selfName = wantGlow && texName.EndsWith("_d")
                        ? texName.Substring(0, texName.Length - 2) + "_self" : null;
                    var selfTex = selfName == null ? null
                        : manager.LoadedAssets.OfType<Texture>().FirstOrDefault(t => t.Name == selfName);
                    if (selfTex != null)
                    {
                        source.Textures[1] = new AssetDependence<Texture>(selfTex);
                        Console.WriteLine($"    свечение <- {selfName}");
                    }
                    EditFlags(source, args);
                    var package = new AssetPackage();
                    package.Items.Clear();
                    package.Items.Add(source);
                    var outPath = Path.Combine(outDir, newName + "_mtl.tpac");
                    package.Save(outPath);
                    Console.WriteLine($"{newName}: diffuse {(texture != null ? texName : "ВАНИЛЬНЫЙ (текстуры нет)")} -> {Path.GetFileName(outPath)}");
                }
                return missing;
            }

            // Перепривязка материалов у наших мешей: mesh-rebind <папка игры+мода> <пакет.tpac> <префикс>
            // Для каждого меша eq_pony_<имя> берём материалы ванильного меша <имя> и ставим наши
            // <префикс><материал>. Нужна, когда материалы пересозданы после импорта FBX.
            if (args[0] == "mesh-rebind" && args.Length >= 4)
            {
                var packagePath = Path.GetFullPath(args[2]);
                var prefix = args[3];
                var package = manager.LoadedPackages.FirstOrDefault(
                    p => string.Equals(p.File?.FullName, packagePath, StringComparison.OrdinalIgnoreCase));
                if (package == null)
                {
                    Console.WriteLine("package not loaded: " + packagePath);
                    return 2;
                }
                package.Load(true);
                var changed = 0;
                foreach (var mesh in package.Items.OfType<Metamesh>())
                {
                    if (!mesh.Name.StartsWith("eq_pony_"))
                        continue;
                    var vanillaName = mesh.Name.Substring("eq_pony_".Length);
                    var vanilla = manager.LoadedAssets.OfType<Metamesh>().FirstOrDefault(m => m.Name == vanillaName);
                    if (vanilla == null)
                    {
                        Console.WriteLine($"{mesh.Name}: ванильного меша {vanillaName} нет");
                        continue;
                    }
                    var wanted = vanilla.Meshes.Where(m => m.Lod == 0)
                        .Select(m => m.Material.TryGetItem(out var mat) ? mat.Name : null).ToList();
                    var index = 0;
                    foreach (var sub in mesh.Meshes.Where(m => m.Lod == 0))
                    {
                        var vanillaMat = index < wanted.Count ? wanted[index] : wanted.LastOrDefault();
                        index++;
                        if (vanillaMat == null)
                            continue;
                        var ours = manager.LoadedAssets.OfType<Material>()
                            .FirstOrDefault(m => m.Name == prefix + vanillaMat);
                        if (ours == null)
                        {
                            Console.WriteLine($"{mesh.Name}: материала {prefix + vanillaMat} нет");
                            continue;
                        }
                        sub.Material = new AssetDependence<Material>(ours);
                        changed++;
                    }
                }
                package.Save(packagePath);
                Console.WriteLine($"перепривязано подмешей: {changed} -> {Path.GetFileName(packagePath)}");
                return 0;
            }

            // Копия ванильного меша под своим именем:
            //   mesh-copy <папки с tpac> <пакет.tpac> <приставка> <меш1,меш2,...>
            // Меш кладётся в наш пакет как <приставка><имя> со своим guid, а материалы подменяются
            // на наши — <приставка><ванильный материал>. Так броня улья получает свои текстуры и
            // свечение, а ванильные ассеты остаются нетронутыми (их правит только редактор).
            if (args[0] == "mesh-copy" && args.Length >= 5)
            {
                var prefix = args[3];
                // fallback=<материал> — чем закрывать подмеши с пустым материалом
                var spareName = args.FirstOrDefault(a => a.StartsWith("fallback="));
                var spare = spareName == null ? null : manager.LoadedAssets.OfType<Material>()
                    .FirstOrDefault(m => m.Name == spareName.Substring("fallback=".Length));
                if (spareName != null && spare == null)
                {
                    Console.WriteLine("запасной материал не найден: " + spareName);
                    return 2;
                }
                var package = new AssetPackage();
                package.Items.Clear();
                var copied = 0;
                var bound = 0;
                foreach (var name in args[4].Split(',').Select(n => n.Trim()).Where(n => n.Length > 0
                             && !n.StartsWith("fallback=")))
                {
                    var mesh = manager.LoadedAssets.OfType<Metamesh>().FirstOrDefault(m => m.Name == name);
                    if (mesh == null)
                    {
                        Console.WriteLine("metamesh not found: " + name);
                        return 2;
                    }
                    // Первый разобранный материал меша — им же закрываем подмеши без материала:
                    // у ванильных рукавиц mail_mitten_e/f/h материал пустой (дефект самой игры),
                    // и меш с пустым материалом движок не рисует.
                    Material fallback = null;
                    foreach (var sub in mesh.Meshes)
                    {
                        Material ours = null;
                        if (sub.Material.TryGetItem(out var vanilla))
                        {
                            ours = manager.LoadedAssets.OfType<Material>()
                                .FirstOrDefault(m => m.Name == prefix + vanilla.Name);
                            if (ours == null)
                            {
                                Console.WriteLine($"    {name}: нет материала {prefix + vanilla.Name}, остаётся ванильный");
                                continue;
                            }
                            fallback = fallback ?? ours;
                        }
                        else
                        {
                            // сначала материал этого же меша, потом — общий запасной из аргумента
                            // fallback=<имя>: у рукавиц пустые ВСЕ подмеши, брать неоткуда
                            ours = fallback ?? spare;
                            if (ours == null)
                            {
                                Console.WriteLine($"    {name}: подмеш без материала, заменить нечем");
                                continue;
                            }
                            Console.WriteLine($"    {name}: подмеш без материала -> {ours.Name}");
                        }
                        sub.Material = new AssetDependence<Material>(ours);
                        bound++;
                    }
                    mesh.Name = prefix + name;
                    mesh.Guid = StableGuid(prefix + name);
                    package.Items.Add(mesh);
                    copied++;
                    Console.WriteLine($"{name} -> {mesh.Name}");
                }
                var outPath = Path.GetFullPath(args[2]);
                Directory.CreateDirectory(Path.GetDirectoryName(outPath));
                package.Save(outPath);
                Console.WriteLine($"мешей {copied}, подмешей привязано {bound} -> {outPath}");
                return 0;
            }

            // Один материал на все меши с общим началом имени:
            //   mesh-setmat <папка с tpac> <пакет .tpac> <начало имени меша> <материал>
            // Так привязывается своя модель расы после импорта FBX (у неё пять мешей eq_yak_*,
            // и все носят один материал eq_yak_body).
            if (args[0] == "mesh-setmat" && args.Length >= 5)
            {
                var packagePath = Path.GetFullPath(args[2]);
                var package = manager.LoadedPackages.FirstOrDefault(
                    p => string.Equals(p.File?.FullName, packagePath, StringComparison.OrdinalIgnoreCase));
                if (package == null)
                {
                    Console.WriteLine("package not loaded: " + packagePath);
                    return 2;
                }
                var material = manager.LoadedAssets.OfType<Material>().FirstOrDefault(m => m.Name == args[4]);
                if (material == null)
                {
                    Console.WriteLine("material not found: " + args[4]);
                    return 3;
                }
                package.Load(true);
                var changed = 0;
                foreach (var mesh in package.Items.OfType<Metamesh>().Where(m => m.Name.StartsWith(args[3])))
                {
                    foreach (var sub in mesh.Meshes)
                    {
                        sub.Material = new AssetDependence<Material>(material);
                        changed++;
                    }
                    Console.WriteLine($"{mesh.Name}: -> {material.Name}");
                }
                package.Save(packagePath);
                Console.WriteLine($"привязано подмешей: {changed} -> {Path.GetFileName(packagePath)}");
                return 0;
            }

            // tpac_export obj <папка с tpac> <меш1,меш2,...> <файл.obj> — только вершины и грани
            // нулевого LOD. Нужна там, где FBX не годится: у ванильных тела и головы лежат морфы,
            // и импортёр Blender на них падает (assert в blen_read_shapes). Этим достаётся образец
            // для подгонки моделей рас под доспех: body_male_a -> assets\human_ref\human.obj.
            if (args[0] == "obj" && args.Length >= 4)
            {
                var lines = new List<string>();
                var shift = 1;
                foreach (var name in args[2].Split(','))
                {
                    var mesh = manager.LoadedAssets.OfType<Metamesh>().FirstOrDefault(a => a.Name == name);
                    if (mesh == null)
                    {
                        Console.WriteLine($"metamesh not found: {name}");
                        continue;
                    }
                    foreach (var sub in mesh.Meshes.Where(m => m.Lod == 0))
                    {
                        var data = sub.EditData?.Data;
                        if (data == null || data.Positions == null)
                            continue;
                        lines.Add($"o {sub.Name}");
                        foreach (var p in data.Positions)
                            lines.Add($"v {p.X.ToString(Culture)} {p.Y.ToString(Culture)} {p.Z.ToString(Culture)}");
                        // грань ссылается на Vertices, а те — на Positions: у ванильных мешей
                        // вершин больше, чем точек (швы развёртки), поэтому индекс через Vertices
                        foreach (var f in data.Faces)
                            lines.Add(string.Format("f {0} {1} {2}",
                                data.Vertices[f.V0].PositionIndex + shift,
                                data.Vertices[f.V1].PositionIndex + shift,
                                data.Vertices[f.V2].PositionIndex + shift));
                        Console.WriteLine($"{sub.Name}: вершин {data.Positions.Length}, граней {data.Faces.Length}");
                        shift += data.Positions.Length;
                    }
                }
                File.WriteAllLines(args[3], lines);
                Console.WriteLine($"записано {args[3]}");
                return 0;
            }

            // tpac_export assets <папка с tpac> <фильтр имени или ".", можно с типом: particle:.>
            // — все ассеты любого типа: тип, имя, GUID. list показывает только меши и скелеты.
            if (args[0] == "assets")
            {
                var filter = args[2].ToLowerInvariant();
                var type = "";
                if (filter.Contains(":"))
                {
                    var parts = filter.Split(new[] { ':' }, 2);
                    type = parts[0];
                    filter = parts[1];
                }
                if (filter == ".")
                {
                    filter = "";
                }
                foreach (var asset in manager.LoadedAssets
                             .Where(a => a.Name.ToLowerInvariant().Contains(filter)
                                         && (type == "" || a.GetType().Name.ToLowerInvariant() == type))
                             .OrderBy(a => a.GetType().Name).ThenBy(a => a.Name))
                {
                    Console.WriteLine($"{asset.GetType().Name,-16} {asset.Name,-48} {asset.Guid}");
                }
                return 0;
            }

            // tpac_export copy-assets <папка-источник> <имя1,имя2,...> <out.tpac>
            // — переносит ассеты в свой пакет вместе с текстурами, на которые они ссылаются.
            //
            // Содержимое частиц TpacTool не разбирает (класс Particle пустой), но ссылки на чужие
            // ассеты пакет хранит отдельным списком (UnknownDependences) — по нему и тянем текстуры,
            // а на всякий случай ещё ищем GUID'ы в сырых метаданных. Сами данные не трогаются:
            // ассет перекладывается в новый пакет как есть.
            if (args[0] == "copy-assets" && args.Length >= 4)
            {
                var wanted = args[2].Split(',').Select(n => n.Trim()).Where(n => n.Length > 0).ToList();
                var chosen = new List<AssetItem>();
                foreach (var name in wanted)
                {
                    var found = manager.LoadedAssets.Where(a => a.Name == name).ToList();
                    if (found.Count == 0)
                    {
                        Console.WriteLine("asset not found: " + name);
                        return 2;
                    }
                    chosen.AddRange(found);
                }
                var extra = new List<AssetItem>();
                var queue = new Queue<AssetItem>(chosen);
                while (queue.Count > 0)
                {
                    var asset = queue.Dequeue();
                    foreach (var guid in References(asset))
                    {
                        var target = manager.GetAsset(guid);
                        if (target == null || chosen.Contains(target) || extra.Contains(target))
                        {
                            continue;
                        }
                        extra.Add(target);
                        queue.Enqueue(target);
                        Console.WriteLine($"    + {target.GetType().Name} {target.Name}");
                    }
                }
                var package = new AssetPackage();
                package.Items.Clear();
                foreach (var asset in chosen.Concat(extra))
                {
                    package.Items.Add(asset);
                }
                var outPath = Path.GetFullPath(args[3]);
                Directory.CreateDirectory(Path.GetDirectoryName(outPath));
                package.Save(outPath);
                Console.WriteLine($"ассетов {chosen.Count} + зависимостей {extra.Count} -> {outPath}");
                return 0;
            }

            if (args[0] == "export" && args.Length >= 4)
            {
                var skeleton = manager.LoadedAssets.OfType<Skeleton>().FirstOrDefault(s => s.Name == "human_skeleton");
                Console.WriteLine($"skeleton: {(skeleton != null ? skeleton.Name : "not found (static export)")}");
                Console.WriteLine($"assimp available: {AssimpModelExporter.IsAssimpAvailable()}");
                var option = ModelExporter.ModelExportOption.ExportTextures | ModelExporter.ModelExportOption.PreferPng;

                var failed = 0;
                foreach (var name in args[2].Split(','))
                {
                    var mesh = manager.LoadedAssets.OfType<Metamesh>().FirstOrDefault(a => a.Name == name);
                    if (mesh == null)
                    {
                        Console.WriteLine($"metamesh not found: {name}");
                        failed++;
                        continue;
                    }
                    var dir = Path.Combine(Path.GetFullPath(args[3]), name);
                    Directory.CreateDirectory(dir);
                    var path = Path.Combine(dir, name + ".fbx");
                    try
                    {
                        AssimpModelExporter.ExportToFile(path, mesh, skeleton, option);
                        Console.WriteLine($"exported {name} -> {path}");
                    }
                    catch (Exception e)
                    {
                        Console.WriteLine($"FAILED {name}: {e}");
                        failed++;
                    }
                }
                return failed;
            }

            Console.WriteLine("unknown command");
            return 1;
        }
    }
}
