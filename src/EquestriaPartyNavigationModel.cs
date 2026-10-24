using TaleWorlds.CampaignSystem.GameComponents;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.Core;

namespace EquestriaMod
{
    // World map passability for parties.
    //
    // The faces of our navmesh (Module\SceneObj\Main_map\navmesh.bin, built by the editor) have
    // terrain type 0 - the game has no such type, and the default model treated the whole map as
    // impassable for land parties. That caused all the oddities:
    //   - a party did go to a point on the ground (no path was built, so it moved in a straight line);
    //   - towards another party it stood still: the game decided the target was on impassable terrain;
    //   - lords could not catch anyone and got stuck after a couple of weeks.
    //
    // Face types can only be set in the editor (the game does not accept a file modified by our
    // code), so for now we treat the "zero" terrain as plain.
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
