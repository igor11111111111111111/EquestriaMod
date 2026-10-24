using System;
using System.Linq;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.GameState;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.Core;
using TaleWorlds.Library;

namespace EquestriaMod
{
    // Bandit hideout inspection on the map (10.10.2026, checking the hideout models: tools/dress_hideouts.py).
    //   /eqhideout   once the map is up, finds the nearest hideout (an infested one first),
    //                makes it spotted, puts the player's party ~15 m from it and leads it there.
    // run.ps1 -Hideout. The log gets "hideout: …" lines with the name, id and coordinates.
    public static class EquestriaHideoutTest
    {
        private const string Arg = "/eqhideout";
        private const float StartDistance = 15f;
        private static bool _requested;
        private static bool _done;
        private static DateTime _mapSeenAt = DateTime.MinValue;

        public static void CheckRequest()
        {
            if (Environment.GetCommandLineArgs().Any(a => string.Equals(a, Arg, StringComparison.OrdinalIgnoreCase)))
            {
                _requested = true;
                EquestriaCrashLog.Log("логово: запрошено по ключу");
            }
        }

        public static void Tick()
        {
            if (!_requested || _done)
            {
                return;
            }
            if (!(GameStateManager.Current?.ActiveState is MapState) || Campaign.Current == null || MobileParty.MainParty == null)
            {
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
            EquestriaCrashLog.Try("логово", Run);
        }

        private static void Run()
        {
            Vec2 me = MobileParty.MainParty.GetPosition2D;
            var hideouts = Settlement.All.Where(s => s.IsHideout && s.Hideout != null)
                .OrderBy(s => s.GetPosition2D.DistanceSquared(me)).ToList();
            if (hideouts.Count == 0)
            {
                EquestriaCrashLog.Warn("логово: на карте нет ни одного логова");
                return;
            }
            Settlement target = hideouts.FirstOrDefault(s => s.Hideout.IsInfested) ?? hideouts[0];
            target.Hideout.IsSpotted = true;

            // Put the party StartDistance from the hideout, on the side it came from, and lead it there
            Vec2 pos = target.GetPosition2D;
            Vec2 dir = me - pos;
            dir = dir.LengthSquared > 0.01f ? dir.Normalized() : new Vec2(-1f, -1f).Normalized();
            MobileParty.MainParty.Position = new CampaignVec2(pos + dir * StartDistance, true);
            MobileParty.MainParty.SetMoveGoToSettlement(target, MobileParty.NavigationType.Default, false);
            Campaign.Current.TimeControlMode = CampaignTimeControlMode.StoppablePlay;

            EquestriaCrashLog.Note($"логово: {target.Name} [{target.StringId}] в ({pos.x:0}, {pos.y:0}), "
                + $"занято разбойниками: {target.Hideout.IsInfested}; отряд поставлен в {StartDistance:0} м и идёт к нему");
            foreach (var other in hideouts.Take(4))
            {
                EquestriaCrashLog.Log($"логово рядом: {other.Name} [{other.StringId}] ({other.GetPosition2D.x:0}, {other.GetPosition2D.y:0}), "
                    + $"до старта {other.GetPosition2D.Distance(me):0} м, занято: {other.Hideout.IsInfested}");
            }
        }
    }
}
