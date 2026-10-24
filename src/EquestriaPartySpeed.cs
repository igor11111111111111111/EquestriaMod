using System;
using System.IO;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.GameComponents;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.Library;
using TaleWorlds.Localization;
using TaleWorlds.ModuleManager;

namespace EquestriaMod
{
    // Party speed by terrain.
    //
    // The vanilla model looks only at the navmesh face type and does three things: forest -30%,
    // water and fords -30%, desert and dunes -10%. Mountains are not on this list - in vanilla they are simply
    // impassable. In our mod mountains are passable, otherwise the map of Equus falls apart into disconnected
    // pieces, and in the mesh they are marked as steppe (the game treats the Mountain type as impassable). Hence
    // our own multiplier: it lives in Module/ModuleData/equestria_speed_map.bin (written by
    // tools/make_speed_map.py from the same terrain map and heights as everything else) and is applied ON TOP
    // of the vanilla rules. Forest and desert are deliberately not penalized a second time there.
    public class EquestriaPartySpeedModel : DefaultPartySpeedCalculatingModel
    {
        private const string FileName = "equestria_speed_map.bin";

        private static byte[] _cells;
        private static byte[] _why;
        private static int _grid;
        private static float _mapSize;
        private static bool _tried;

        private static readonly TextObject Rough = new TextObject("{=eq_speed_rough}Rough country");
        private static readonly TextObject Ford = new TextObject("{=eq_speed_ford}Fording a river");

        private static void Load()
        {
            if (_tried)
            {
                return;
            }
            _tried = true;
            try
            {
                string path = Path.Combine(ModuleHelper.GetModuleFullPath("EquestriaMod"),
                                           "ModuleData", FileName);
                if (!File.Exists(path))
                {
                    EquestriaCrashLog.Warn("скорость по местности: нет файла " + path);
                    return;
                }
                byte[] raw = File.ReadAllBytes(path);
                if (raw.Length < 12 || raw[0] != 'E' || raw[1] != 'Q' || raw[2] != 'S' || raw[3] != 'P')
                {
                    EquestriaCrashLog.Warn("скорость по местности: чужой файл " + FileName);
                    return;
                }
                _grid = BitConverter.ToInt32(raw, 4);
                _mapSize = BitConverter.ToInt32(raw, 8);
                if (_grid <= 0 || raw.Length < 12 + _grid * _grid)
                {
                    EquestriaCrashLog.Warn("скорость по местности: файл короче заявленного");
                    return;
                }
                _cells = new byte[_grid * _grid];
                Array.Copy(raw, 12, _cells, 0, _cells.Length);
                // second half of the file, if present: why it slows down (1 - river)
                if (raw.Length >= 12 + 2 * _cells.Length)
                {
                    _why = new byte[_cells.Length];
                    Array.Copy(raw, 12 + _cells.Length, _why, 0, _why.Length);
                }
                EquestriaCrashLog.Log("скорость по местности: сетка " + _grid + "x" + _grid
                                      + " на " + _mapSize + " м");
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Warn("скорость по местности: " + e.GetType().Name + ": " + e.Message);
            }
        }

        // Multiplier at a map point: 1.0 - easy going, 0.7 - mountains and fords, 0.55 - the hardest.
        // onRiver - whether the party stands on a river: only the label in the speed breakdown depends on it.
        public static float FactorAt(Vec2 position, out bool onRiver)
        {
            onRiver = false;
            Load();
            if (_cells == null)
            {
                return 1f;
            }
            int x = (int)(position.x / _mapSize * _grid);
            int y = (int)(position.y / _mapSize * _grid);
            if (x < 0 || y < 0 || x >= _grid || y >= _grid)
            {
                return 1f;
            }
            int cell = y * _grid + x;
            onRiver = _why != null && _why[cell] != 0;
            return _cells[cell] / 100f;
        }

        public override ExplainedNumber CalculateFinalSpeed(MobileParty mobileParty, ExplainedNumber finalSpeed)
        {
            ExplainedNumber result = base.CalculateFinalSpeed(mobileParty, finalSpeed);
            try
            {
                if (mobileParty != null && !mobileParty.IsCurrentlyAtSea)
                {
                    bool onRiver;
                    float factor = FactorAt(mobileParty.GetPosition2D, out onRiver);
                    if (factor < 0.999f)
                    {
                        result.AddFactor(factor - 1f, onRiver ? Ford : Rough);
                    }
                }
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Warn("скорость по местности: " + e.Message);
            }
            return result;
        }
    }
}
