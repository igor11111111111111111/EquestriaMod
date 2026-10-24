// Exports meshes from packed Bannerlord assets (.tpac) to FBX via the TpacTool library (hunharibo, MIT).
//   tpac_export list   <tpac folder> <filter>             - find metameshes and skeletons by name
//   tpac_export export <tpac folder> <mesh1,mesh2,...> <output folder> - one FBX each with the human_skeleton
//                                                                      skeleton and textures in <output>\<mesh>\
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
        // OBJ is read only with a dot in decimals, and the system here is Russian
        private static readonly System.Globalization.CultureInfo Culture =
            System.Globalization.CultureInfo.InvariantCulture;

        // Object properties via reflection: simple values are printed, lists - by length and first elements,
        // nested objects - two levels deep.
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

        // Editing shader flags: an argument like flags=+self_illumination,-use_double_colormap...
        // Plus adds a flag, minus removes it. Everything else on the clone stays from the source -
        // including the vertex layout (skinning), without which the armour would stop bending.
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

        // The material GUID is derived from the name: a rerun gives the same identifier,
        // and meshes already bound to our material do not lose it.
        private static Guid StableGuid(string name)
        {
            using (var md5 = System.Security.Cryptography.MD5.Create())
            {
                return new Guid(md5.ComputeHash(System.Text.Encoding.UTF8.GetBytes(name)));
            }
        }

        // Which assets this one references: the package's separate list plus GUIDs found in
        // unparsed metadata (particles have no parser, and that is exactly where textures sit).
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
                // a parsed type (material, mesh) - its dependencies are already in the list above
            }
            // Metadata only. We do not touch the asset body: for unparsed types reading the Data field
            // breaks lazy loading, and on save the package crashes on an empty buffer
            // (verified on particles 2026-09-24). What is inside the body - we look at the finished file.
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
            for (var i = 0; i + 16 <= data.Length; i += 4)   // references are aligned to 4 bytes
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

            // Several asset folders can be given separated by «;»: that way a material is cloned from a
            // vanilla package, and its textures are taken from ours.
            var manager = new AssetManager();
            foreach (var dir in args[1].Split(';'))
            {
                Console.WriteLine($"loading {dir} ...");
                manager.Load(new DirectoryInfo(dir));
            }
            DefaultDependenceResolver.Instance = manager; // mesh references to materials and textures are resolved here
            Console.WriteLine($"packages: {manager.LoadedPackages.Count}, assets: {manager.LoadedAssets.Count}");

            if (args[0] == "diag")
            {
                // which materials a mesh needs and whether they are loaded; how many assets of each type were read
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

            // tpac_export info <tpac folder> <mesh1,mesh2,...> - everything in a mesh: flags, vertex streams, morphs
            if (args[0] == "info")
            {
                foreach (var name in args[2].Split(','))
                {
                    var mesh = manager.LoadedAssets.OfType<Metamesh>().FirstOrDefault(a => a.Name == name);
                    if (mesh == null)
                    {
                        // not a mesh - any asset with that name (material, texture, shader)
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

            // tpac_export texture <tpac folder> <filter,filter,...> <output folder> [.png/.dds] - textures
            // Several filters can be listed separated by commas: the game's editor packages
            // (Modules\Native\EmAssetPackages - only there do vanilla textures have the actual pixels)
            // take some twenty seconds to read, and there is no point repeating that for every name.
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

            // Materials. Building them in the editor takes dozens of clicks each, so we clone
            // a vanilla material into our own package: a new name, textures swapped by slot number.
            //   mat-info  <tpac folder> <name or part of name>
            //   mat-clone <tpac folder> <source material> <output .tpac> <new name> [slot=texture ...]
            if (args[0] == "mat-info" && args.Length >= 3)
            {
                // Several names can be listed separated by commas: every run rereads
                // a hundred and fifty vanilla packages, and calling it for each material takes minutes.
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

            // Editing shader flags on a clone: argument flags=+name,-name.
            // Needed by the hive armour: to make it glow, the material has to get self_illumination added and
            // use_double_colormap_with_mask_texture removed - both settings read the SAME texture
            // slot (the first), and they do not work together.
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
                        continue;   // parsed below, in EditFlags
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

            // Mesh materials: mesh-mats <folder> <mesh1,mesh2,...> - which material is on which mesh.
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

            // Batch material cloning: one pass over the assets instead of a run per material.
            //   mat-batch <tpac folder> <output folder> <prefix> <material1,material2,...>
            // For each material <output folder>/<prefix><name>_mtl.tpac is written; the diffuse (slot 0)
            // is swapped for the texture <prefix><name>_d if it has already been imported into the module.
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
                    // the name of our texture is taken from the material's current diffuse (material and
                    // texture names do not always match in vanilla: bandit_leather_mat -> bandit_leather_d)
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
                    // Glow map in slot 1 (the same slot where vanilla has the clan colour mask): we set it
                    // only when glow is requested by a flag - otherwise the slot must keep the
                    // vanilla clan colour mask.
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

            // Rebinding materials on our meshes: mesh-rebind <game+mod folder> <package.tpac> <prefix>
            // For each mesh eq_pony_<name> we take the materials of the vanilla mesh <name> and set our
            // <prefix><material>. Needed when the materials were recreated after an FBX import.
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

            // A copy of a vanilla mesh under our own name:
            //   mesh-copy <tpac folders> <package.tpac> <prefix> <mesh1,mesh2,...>
            // The mesh goes into our package as <prefix><name> with its own guid, and the materials are swapped
            // for ours - <prefix><vanilla material>. That way the hive armour gets its own textures and
            // glow, while the vanilla assets stay untouched (only the editor edits them).
            if (args[0] == "mesh-copy" && args.Length >= 5)
            {
                var prefix = args[3];
                // fallback=<material> - what to fill submeshes with an empty material with
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
                    // The mesh's first parsed material - also used to fill submeshes without a material:
                    // the vanilla mittens mail_mitten_e/f/h have an empty material (a defect of the game itself),
                    // and the engine does not draw a mesh with an empty material.
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
                            // first the material of this same mesh, then the shared spare one from the argument
                            // fallback=<name>: on the mittens ALL submeshes are empty, there is nothing to take from
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

            // One material for all meshes with a common name prefix:
            //   mesh-setmat <tpac folder> <package .tpac> <mesh name prefix> <material>
            // This is how our own race model is bound after an FBX import (it has five meshes eq_yak_*,
            // and all of them wear one material eq_yak_body).
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

            // tpac_export obj <tpac folder> <mesh1,mesh2,...> <file.obj> - only the vertices and faces
            // of LOD zero. Needed where FBX does not work: the vanilla body and head carry morphs,
            // and the Blender importer crashes on them (assert in blen_read_shapes). This extracts the reference
            // for fitting race models to armour: body_male_a -> assets\human_ref\human.obj.
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
                        // a face refers to Vertices, and those to Positions: vanilla meshes have
                        // more vertices than points (UV seams), hence the index goes through Vertices
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

            // tpac_export assets <tpac folder> <name filter or ".", optionally with a type: particle:.>
            // - all assets of any type: type, name, GUID. list shows only meshes and skeletons.
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

            // tpac_export copy-assets <source folder> <name1,name2,...> <out.tpac>
            // - moves assets into our own package together with the textures they reference.
            //
            // TpacTool does not parse particle contents (the Particle class is empty), but the package keeps
            // references to other assets in a separate list (UnknownDependences) - we pull the textures by it,
            // and just in case we also search for GUIDs in the raw metadata. The data itself is not touched:
            // the asset is moved into the new package as is.
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
