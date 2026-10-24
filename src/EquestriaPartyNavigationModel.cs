using TaleWorlds.CampaignSystem.GameComponents;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.Core;

namespace EquestriaMod
{
    // Проходимость карты мира для отрядов.
    //
    // У граней нашей сетки проходимости (Module\SceneObj\Main_map\navmesh.bin, её строит редактор)
    // тип местности равен 0 — такого типа в игре нет, и стандартная модель считала всю карту
    // непроходимой для сухопутных отрядов. Отсюда были все странности:
    //   - к точке на земле отряд шёл (путь не строился, и он двигался по прямой);
    //   - к другому отряду — стоял на месте: игра решала, что цель на непроходимой местности;
    //   - лорды не могли никого догнать и через пару недель застревали.
    //
    // Проставить тип граням можно только в редакторе (файл, изменённый нашим кодом, игра не
    // принимает), поэтому пока считаем «нулевую» местность равниной.
    public class EquestriaPartyNavigationModel : DefaultPartyNavigationModel
    {
        private const TerrainType Unset = (TerrainType)0;

        public override bool IsTerrainTypeValidForNavigationType(TerrainType terrainType,
                                                                  MobileParty.NavigationType navigationType)
        {
            if (terrainType == Unset)
            {
                terrainType = TerrainType.Plain;
            }
            return base.IsTerrainTypeValidForNavigationType(terrainType, navigationType);
        }
    }
}
