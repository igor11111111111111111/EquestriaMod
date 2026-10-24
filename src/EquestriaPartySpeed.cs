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
    // Скорость отряда по местности.
    //
    // Ванильная модель смотрит только на тип грани сетки проходимости и умеет три вещи: лес -30%,
    // вода и броды -30%, пустыня и дюны -10%. Гор в этом списке нет — в ванили они просто
    // непроходимы. У нас горы проходимы, иначе карта Эквуса распадается на несвязные куски, и в
    // сетке они помечены степью (тип Mountain игра считает непроходимым). Поэтому свой множитель:
    // он лежит в Module/ModuleData/equestria_speed_map.bin (его пишет tools/make_speed_map.py по
    // той же карте местности и высотам, что и всё остальное) и применяется ПОВЕРХ ванильных
    // правил. Лес и пустыню там намеренно не штрафуем второй раз.
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
                // вторая половина файла, если есть: почему замедление (1 — река)
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

        // Множитель в точке карты: 1.0 — идти легко, 0.7 — горы и броды, 0.55 — самое тяжёлое.
        // onRiver — стоит ли отряд на реке: от этого зависит только подпись в разборе скорости.
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
