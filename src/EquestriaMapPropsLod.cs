using System;
using System.Collections.Generic;
using HarmonyLib;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.GameState;
using TaleWorlds.Core;
using TaleWorlds.Engine;

namespace EquestriaMod
{
    // Крупные предметы окружения на карте мира (деревья, валуны — tools/map_props.py, имена с
    // префиксом eq_prop_) пропадают при отдалении камеры, хотя видны вблизи (замечено в игре
    // 07.10.2026). Дело не в числе LOD-уровней меша: замена одноуровневых map_tree_a/b/c/d на
    // двухуровневые map_tree_new_a/b/c/d (lod0+lod1-билборд) ничего не изменила — похоже на
    // отдельную систему отсечения по дальности (возможно, общую с качеством растительности,
    // foliage_quality в engine_config.txt). По просьбе пользователя графические настройки не
    // трогаем — вместо этого форсируем нашим предметам лучший LOD GameEntity.
    // SetEnforcedMaximumLodLevel(0) независимо от дистанции до камеры (apidoc.bannerlord.com,
    // класс GameEntity).
    //
    // Доступ к Scene карты мира: Campaign.Current.MapSceneWrapper — интерфейс IMapScene не даёт
    // прямого доступа к сущностям сцены, у его конкретного (непубличного) типа есть свойство Scene
    // (видно в decompile SandBox.View.Map.MapScreen: "MapScene = ((MapScene)Campaign.Current.
    // MapSceneWrapper).Scene"). Тот же приём, что EquestriaBodyParts.GetEntity у AgentVisuals —
    // берём через рефлексию по имени свойства, не по типу.
    public static class EquestriaMapPropsLod
    {
        private const string Prefix = "eq_prop_";

        private static bool _done;
        private static DateTime _mapSeenAt = DateTime.MinValue;

        /// <summary>Зовётся каждый кадр из SubModule.OnApplicationTick.</summary>
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
