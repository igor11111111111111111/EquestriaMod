using System.Linq;
using System.Reflection;
using HarmonyLib;
using Helpers;
using SandBox.View.Map;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.CampaignBehaviors;
using TaleWorlds.Core;

namespace EquestriaMod
{
    // Harmony patches: replacing game methods on the fly where there is no official hook.
    //
    // The library ships with the mod (0Harmony.dll is placed next to our DLL); the separate
    // Bannerlord.Harmony module does not need to be installed.
    //
    // Rule: first we look for a legitimate way: XML, a campaign behaviour, a model, XSLT. A patch is applied
    // only when we hit a wall. Each patch is tied to a game method signature and does not survive every
    // update, so there must be few of them and each must be explained.
    public static class EquestriaPatches
    {
        private const string Id = "com.equestria.bannerlord";

        private static Harmony _harmony;

        // Access for patches that can be applied neither in Apply() nor in ApplyLate(); see
        // RaceAssimilationTooltipPatch (applied lazily on the first campaign tick, not here).
        public static Harmony Instance => _harmony;

        public static void Apply()
        {
            if (_harmony != null)
            {
                return;
            }
            EquestriaCrashLog.Try("подключение патчей Harmony", () =>
            {
                _harmony = new Harmony(Id);
                _harmony.PatchAll(Assembly.GetExecutingAssembly());
                EquestriaLoadingScreen.Apply(_harmony);
                // The shader compilation label on the loading screen itself (see the class)
                EquestriaLoadingNote.Apply(_harmony);
                EquestriaEnglishTexts.Apply(_harmony);
                // The video in the main menu background: only ours (see the class)
                EquestriaMenuVideo.Apply(_harmony);
                var names = _harmony.GetPatchedMethods()
                    .Select(m => m.DeclaringType.Name + "." + m.Name).ToList();
                EquestriaCrashLog.Log($"Harmony: патчей применено {names.Count}"
                    + (names.Count > 0 ? " — " + string.Join(", ", names) : ""));
            });
        }

        private static bool _lateApplied;

        // Patches on the battle game classes (Agent, MBSoundEvent) are applied later, when the game has already
        // loaded its data, including animations. If they are patched at mod load,
        // Harmony triggers the static initialization of these classes too early, and the action table
        // is built without the pony animations: in the preview windows (party, inventory) all ponies
        // lay on their side. Called when the main menu is shown.
        public static void ApplyLate()
        {
            if (_lateApplied || _harmony == null)
            {
                return;
            }
            _lateApplied = true;
            EquestriaCrashLog.Try("поздние патчи Harmony", () =>
            {
                // Body parts outside missions (portraits, map, barber): the mesh is hung as a separate child
                // entity, the skeleton is not touched. The patch is applied exactly here, not at mod load:
                // an early AgentVisuals patch triggers the static initialization of the class before
                // the game has read the animations, and all ponies in windows lie on their side (verified 2026-09-18,
                // the /eqnoparts switch for comparison). In missions skinning is needed: there it is OnAgentBuild.
                EquestriaBodyParts.ApplyVisuals(_harmony);
                // The helmet for the race's large head goes here too: it hooks into the same visuals assembly
                EquestriaHelmetFit.Apply(_harmony);
                // The "Solid/Striped" buttons on top of the pony appearance screen
                EquestriaHairStyleView.Apply(_harmony);
                // The "parents"/childhood/youth portraits in the character creation wizard: the third
                // independent AgentVisuals assembly path, it also needs EquestriaBodyParts.Attach
                EquestriaNarrativeCreationFix.Apply(_harmony);
                // Magic: while aiming a spell, LMB does not punch
                EquestriaSpellCombatPatch.Apply(_harmony);
                MuteVanillaOrderShouts.Apply(_harmony);
                MuteVanillaOrderNods.Apply(_harmony);
                EquestriaGreetings.ApplyVoice(_harmony);
                EquestriaMusic.Apply(_harmony);
                // The flight scroll in the horse slot: prevents the engine from creating a horse agent (src/EquestriaFlightScroll.cs)
                EquestriaFlightScroll.Apply(_harmony);
                EquestriaCrashLog.Log("Harmony: поздние патчи (голос приказов, голос приветствий, музыка) применены");
            });
        }
    }

    // The vanilla settlement distance cache does not suit us.
    //
    // On campaign start SettlementPositionScript goes through all enabled modules and takes it from
    // the last one that has a ModuleData/DistanceCaches/settlements_distance_cache_*.bin file.
    // SandBox has such a file, and it is computed for Calradia: inside are names of settlements that
    // no longer exist in our world. On reading, the game looks each one up by name, does not find it and crashes on a null
    // reference in NavigationCacheElement.GetHashCode.
    //
    // There is no legitimate way to refuse someone else's cache, hence the patch. We say "no file" for all
    // modules except ours, and the game honestly computes the distances itself at campaign start.
    //
    // Our own cache. On a 1024 m map with 122 fortresses the neighbourhood computation takes about six minutes, so
    // the computed cache is saved to our ModuleData/DistanceCaches (DistanceCacheSaveOurs below).
    // When reading the cache the game does NOT check it against the map, and a stale cache breaks distances, so
    // next to it lies a stamp: a hash of the navigation grid and the settlement list. If it does not match, we pretend
    // there is no file: the game recomputes, and we save it again.
    [HarmonyPatch(typeof(SettlementPositionScript), "GetSettlementsDistanceCacheFileForCapability")]
    public static class DistanceCacheFromOurModuleOnly
    {
        internal const string OurModule = "EquestriaMod";

        // Path where to save the cache after computation (set when our cache is missing or stale)
        internal static string PendingSavePath;

        private static bool Prefix(string moduleId, ref string filePath, ref bool __result)
        {
            if (moduleId != OurModule)
            {
                filePath = string.Empty;
                __result = false;
                return false;
            }
            return true;  // our module is checked as usual, and the stamp in the Postfix
        }

        private static void Postfix(string moduleId, ref string filePath, ref bool __result)
        {
            if (moduleId != OurModule)
            {
                return;
            }
            string stamp = DistanceCacheStamp.Current();
            string found = __result ? DistanceCacheStamp.Read(filePath) : null;
            if (found != null && (found == stamp || found == DistanceCacheStamp.Legacy()))
            {
                if (found != stamp)
                {
                    DistanceCacheStamp.Write(filePath, stamp);   // an old-style stamp: rewrite it
                }
                PendingSavePath = null;
                return;
            }
            if (__result)
            {
                EquestriaCrashLog.Log("кэш расстояний устарел (карта или поселения изменились) — пересчёт");
            }
            __result = false;
            PendingSavePath = filePath;
        }
    }

    // Saving the computed cache into our module (see above).
    [HarmonyPatch(typeof(SettlementPositionScript), "ReadNavigationCacheForNavigationTypeOnGameLoad")]
    public static class DistanceCacheSaveOurs
    {
        private static void Postfix(object __result)
        {
            string path = DistanceCacheFromOurModuleOnly.PendingSavePath;
            DistanceCacheFromOurModuleOnly.PendingSavePath = null;
            if (string.IsNullOrEmpty(path) || __result == null)
            {
                return;
            }
            EquestriaCrashLog.Try("сохранение кэша расстояний", () =>
            {
                System.IO.Directory.CreateDirectory(System.IO.Path.GetDirectoryName(path));
                __result.GetType().GetMethod("Serialize").Invoke(__result, new object[] { path });
                DistanceCacheStamp.Write(path, DistanceCacheStamp.Current());
                EquestriaCrashLog.Log("кэш расстояний сохранён: " + path);
            });
        }
    }

    internal static class DistanceCacheStamp
    {
        private static string ModuleDir =>
            TaleWorlds.ModuleManager.ModuleHelper.GetModuleFullPath(DistanceCacheFromOurModuleOnly.OurModule);

        private const string Navmesh = "SceneObj/Main_map/navmesh.bin";
        private const string Settlements = "ModuleData/equestria_settlements.xml";

        // A hash of what the cache actually depends on: the navigation grid and, for each settlement,
        // the id and coordinates (including the gates). Previously the whole settlements file was hashed, and any
        // edit of a name or description (for example, a translation) cost a six-to-nine-minute recomputation.
        internal static string Current()
        {
            using (var sha = System.Security.Cryptography.SHA1.Create())
            {
                Feed(sha, FileBytes(Navmesh));
                string xml = System.IO.Path.Combine(ModuleDir, Settlements);
                if (System.IO.File.Exists(xml))
                {
                    var lines = new System.Collections.Generic.List<string>();
                    foreach (var node in System.Xml.Linq.XDocument.Load(xml).Descendants("Settlement"))
                    {
                        lines.Add(string.Join(";", new[] { "id", "posX", "posY", "gate_posX", "gate_posY" }
                            .Select(a => (string)node.Attribute(a) ?? "")));
                    }
                    Feed(sha, System.Text.Encoding.UTF8.GetBytes(string.Join("\n", lines)));
                }
                sha.TransformFinalBlock(new byte[0], 0, 0);
                return System.BitConverter.ToString(sha.Hash).Replace("-", "");
            }
        }

        // An old-style stamp (the whole settlements file). We accept it once, so that
        // changing the method does not cause an extra recomputation, and rewrite it the new way.
        internal static string Legacy()
        {
            using (var sha = System.Security.Cryptography.SHA1.Create())
            {
                Feed(sha, FileBytes(Navmesh));
                Feed(sha, FileBytes(Settlements));
                sha.TransformFinalBlock(new byte[0], 0, 0);
                return System.BitConverter.ToString(sha.Hash).Replace("-", "");
            }
        }

        private static byte[] FileBytes(string rel)
        {
            string file = System.IO.Path.Combine(ModuleDir, rel);
            return System.IO.File.Exists(file) ? System.IO.File.ReadAllBytes(file) : new byte[0];
        }

        private static void Feed(System.Security.Cryptography.SHA1 sha, byte[] data)
        {
            sha.TransformBlock(data, 0, data.Length, null, 0);
        }

        internal static string Read(string cachePath)
        {
            string file = cachePath + ".stamp";
            return System.IO.File.Exists(file) ? System.IO.File.ReadAllText(file).Trim() : null;
        }

        internal static void Write(string cachePath, string stamp)
        {
            System.IO.File.WriteAllText(cachePath + ".stamp", stamp);
        }
    }

    // The vanilla Calradia backstory is not needed and gets in the way.
    //
    // BackstoryCampaignBehavior, when creating a new game, sets up relations between specific
    // vanilla lords: a quarrel of lord_1_7 with lord_1_1, the murder of dead_lord_2_2, a claim on town_V6
    // and so on. All these names are hardcoded. We removed these heroes, their HeroObject is
    // null, and the very first access crashes the campaign.
    //
    // The content is about the imperial civil war anyway and has nothing to do with Equestria.
    // We disable it entirely. Our own backstory (the princesses' quarrels, the Stalliongrad split) will be written later
    // as a separate behaviour.
    [HarmonyPatch(typeof(BackstoryCampaignBehavior), nameof(BackstoryCampaignBehavior.OnNewGameCreated))]
    public static class SkipCalradianBackstory
    {
        private static bool Prefix()
        {
            EquestriaCrashLog.Log("ванильная предыстория Кальрадии пропущена");
            return false;
        }
    }

    // Insurance against empty equipment.
    //
    // Helpers.EquipmentHelper.AssignHeroEquipmentFromEquipment takes an equipment set and immediately
    // reads its properties without a null check. An empty set arrives when no suitable template was found
    // for the hero's culture; we have already lost a game launch to this twice.
    //
    // We created all eight templates, but when the world is redrawn there will be many lords and cultures, and one
    // forgotten line in XML would again crash the campaign without any explanation. Now instead of a crash
    // the hero just stays in what he had, and his name goes into the log: you can see at once who is missing what.
    [HarmonyPatch(typeof(EquipmentHelper), nameof(EquipmentHelper.AssignHeroEquipmentFromEquipment))]
    public static class AssignHeroEquipmentGuard
    {
        // Returning false cancels the original method.
        private static bool Prefix(Hero hero, Equipment equipment)
        {
            if (equipment != null)
            {
                return true;
            }
            string who = hero != null ? hero.StringId : "неизвестный герой";
            string culture = hero != null && hero.Culture != null ? hero.Culture.StringId : "нет культуры";
            EquestriaCrashLog.Warn($"снаряжение не подобрано: {who} (культура {culture}) — "
                + "нет подходящего шаблона в EquipmentRosters; герой оставлен без смены одежды");
            return false;
        }
    }
}
