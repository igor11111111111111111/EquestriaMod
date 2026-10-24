using System.Linq;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.GameComponents;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.Core;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Recruit pool (notables' volunteers in a village/town): the vanilla DefaultVolunteerModel takes
    // the race STRICTLY from sellerHero.Culture: for a notable it is fixed once when he appears and does not
    // follow the settlement's race assimilation (EquestriaRaceAssimilation.cs). This is a different system from
    // the garrison militia (RaceAssimilationMilitiaPatch, EquestriaRaceAssimilationMilitia.cs); they
    // had to be fixed separately (noticed by the user 07.10.2026: the militia was fixed, the recruit
    // pool was not, one was mixed up with the other).
    //
    // GetBasicVolunteer is called from RecruitmentCampaignBehavior.UpdateVolunteersOfNotablesInSettlement
    // ONCE A DAY per notable; the result goes ONLY into emptied slots (already occupied ones are only
    // promoted in rank within the same race, see decompile). So swapping the race here gives a mixed
    // pool not instantly and not per slot, but gradually, as recruiting/refreshing happens: once a day
    // a notable may get a new race, in proportion to the settlement's current CurrentInfluences shares.
    public class EquestriaVolunteerModel : DefaultVolunteerModel
    {
        public override CharacterObject GetBasicVolunteer(Hero sellerHero)
        {
            CultureObject culture = PickCulture(sellerHero.CurrentSettlement) ?? sellerHero.Culture;
            if (sellerHero.IsRuralNotable && sellerHero.CurrentSettlement.Village.Bound.IsCastle)
            {
                return culture.EliteBasicTroop ?? sellerHero.Culture.EliteBasicTroop;
            }
            return culture.BasicTroop ?? sellerHero.Culture.BasicTroop;
        }

        private static CultureObject PickCulture(Settlement settlement)
        {
            if (settlement == null
                || !RaceAssimilationManager.Instance.InfluenceMap.TryGetValue(settlement.StringId, out RaceAssimilationStatus status)
                || status.CurrentInfluences.Count == 0)
            {
                return null;
            }
            decimal roll = (decimal)MBRandom.RandomFloat;
            decimal acc = 0m;
            foreach (var pair in status.CurrentInfluences)
            {
                acc += pair.Value;
                if (roll <= acc)
                {
                    return MBObjectManager.Instance.GetObject<CultureObject>(pair.Key);
                }
            }
            return MBObjectManager.Instance.GetObject<CultureObject>(status.CurrentInfluences.Keys.First());
        }
    }
}
