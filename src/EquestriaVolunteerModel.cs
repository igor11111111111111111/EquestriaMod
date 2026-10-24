using System.Linq;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.GameComponents;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.Core;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Резерв найма (добровольцы нотаблей в деревне/городе) — ванильная DefaultVolunteerModel берёт
    // расу СТРОГО с sellerHero.Culture: у нотабля она фиксируется один раз при его появлении и не
    // следит за ассимиляцией расы поселения (EquestriaRaceAssimilation.cs). Это другая система, чем
    // гарнизонное ополчение (RaceAssimilationMilitiaPatch, EquestriaRaceAssimilationMilitia.cs) — их
    // пришлось чинить раздельно (замечено пользователем 07.10.2026: ополчение поправлено, резерв
    // найма — нет, перепутал одно с другим).
    //
    // GetBasicVolunteer зовётся из RecruitmentCampaignBehavior.UpdateVolunteersOfNotablesInSettlement
    // РАЗ В ДЕНЬ на нотабля — результат уходит ТОЛЬКО в опустевшие слоты (уже занятые только
    // повышаются в звании той же расы, см. decompile). Поэтому подмена расы здесь даёт смешанный
    // резерв не мгновенно и не на ячейку, а постепенно, по мере найма/обновления — раз в день
    // возможна новая раса у нотабля, пропорционально текущим долям CurrentInfluences поселения.
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
