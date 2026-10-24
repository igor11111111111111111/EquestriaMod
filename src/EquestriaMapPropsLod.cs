using System;
using System.Collections.Generic;
using HarmonyLib;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.GameState;
using TaleWorlds.Core;
using TaleWorlds.Engine;

namespace EquestriaMod
{
    // Large environment props on the world map (trees, boulders: tools/map_props.py, names with
    // the eq_prop_ prefix) disappear as the camera moves away, although they are visible up close (seen in game
    // 07.10.2026). It is not the number of mesh LOD levels: replacing the single-level map_tree_a/b/c/d with
    // the two-level map_tree_new_a/b/c/d (lod0+lod1 billboard) changed nothing; it looks like a
    // separate distance culling system (possibly shared with the foliage quality,
    // foliage_quality in engine_config.txt). At the user's request the graphics settings are not
    // touched; instead we force the best LOD on our props with GameEntity.
    // SetEnforcedMaximumLodLevel(0) regardless of the distance to the camera (apidoc.bannerlord.com,
    // class GameEntity).
    //
    // Access to the world map Scene: Campaign.Current.MapSceneWrapper; the IMapScene interface gives no
    // direct access to the scene entities, but its concrete (non-public) type has a Scene property
    // (seen in decompiled SandBox.View.Map.MapScreen: "MapScene = ((MapScene)Campaign.Current.
    // MapSceneWrapper).Scene"). The same trick as EquestriaBodyParts.GetEntity on AgentVisuals:
    // taken via reflection by property name, not by type.
    public static class EquestriaMapPropsLod
    {
        private const string Prefix = "eq_prop_";

        private static bool _done;
        private static DateTime _mapSeenAt = DateTime.MinValue;

        /// <summary>Called every frame from SubModule.OnApplicationTick.</summary>
        public static void Tick()
        {
            if (_done)
            {
                return;
            }
            if (!(GameStateManager.Current?.ActiveState is MapState) || Campaign.Current == null)
            {
                _mapSeenAt = DateTime.MinValue;
                return;
            }
            if (_mapSeenAt == DateTime.MinValue)
            {
                _mapSeenAt = DateTime.UtcNow;
                return;
            }
            if ((DateTime.UtcNow - _mapSeenAt).TotalSeconds < 2)
            {
                return;
            }
            _done = true;
            EquestriaCrashLog.Try("предметы карты: форс LOD", Apply);
        }

        private static void Apply()
        {
            object wrapper = Campaign.Current?.MapSceneWrapper;
            if (wrapper == null)
            {
                EquestriaCrashLog.Warn("предметы карты: MapSceneWrapper пуст");
                return;
            }
            var sceneProp = AccessTools.Property(wrapper.GetType(), "Scene");
            Scene scene = sceneProp?.GetValue(wrapper) as Scene;
            if (scene == null)
            {
                EquestriaCrashLog.Warn("предметы карты: не нашёл свойство Scene у " + wrapper.GetType().FullName);
                return;
            }
            var entities = new List<GameEntity>();
            scene.GetEntities(ref entities);
            int touched = 0;
            foreach (GameEntity entity in entities)
            {
                if (entity != null && entity.Name != null && entity.Name.StartsWith(Prefix, StringComparison.Ordinal))
                {
                    entity.SetEnforcedMaximumLodLevel(0);
                    touched++;
                }
            }
            EquestriaCrashLog.Log("предметы карты: форс LOD применён к " + touched + " сущностям из " + entities.Count);
        }
    }
}
