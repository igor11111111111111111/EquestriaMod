using System;
using System.Collections.Generic;
using System.Linq;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Actions;
using TaleWorlds.CampaignSystem.CharacterCreationContent;
using TaleWorlds.CampaignSystem.GameState;
using TaleWorlds.CampaignSystem.Party;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.Core;
using TaleWorlds.Library;
using TaleWorlds.Localization;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // .\run.ps1 -DefaultStart (/eqdefaultstart): a real new campaign, the character creation wizard
    // runs IN FULL (the race is chosen there too, at the "Appearance" stage, from a ready list
    // of peoples - EquestriaRaceSelector), except for the very first stage "Culture" - it
    // is skipped automatically (the race there is only 6 of 7 anyway, no deer, and the real race
    // choice is at "Appearance"). Right after the wizard comes our own game start choice: the usual pauper start,
    // or mercenary/vassal/ruler of a chosen realm (clan tier 1/3/4; the vassal and the ruler
    // are also given one settlement).
    //
    // Skipping the "Culture" stage is done DIRECTLY through CharacterCreationManager/CharacterCreationContent
    // (SetSelectedCulture/ApplyCulture/NextStage, which is what pressing "Next" does in the end),
    // not through someone else's View (SandBox.GauntletUI...CultureStageView.NextStage()) - that call crashed
    // with a NullReferenceException: the VM's CurrentSelectedCulture is not ready right after the screen
    // appears, and since it does not get set on its own, retrying over frames did not help either (noticed
    // 08.10.2026). Working directly with the wizard's data does not have this problem at all.
    public static class EquestriaDefaultStart
    {
        // Set by EquestriaQuickStart.Tick() when launched with /eqdefaultstart.
        public static bool Active;

        private static bool _cultureSkipped;
        private static int _cultureAttempts;
        private const int MaxCultureAttempts = 5;
        private static bool _pendingPrompt;
        private static DateTime _mapSeenAt = DateTime.MinValue;

        // Called from EquestriaQuickStart.Tick() at the start of a new campaign - resets the
        // state in case of a repeated -DefaultStart in the same game session.
        internal static void Begin()
        {
            Active = true;
            _cultureSkipped = false;
            _cultureAttempts = 0;
            _pendingPrompt = false;
            _mapSeenAt = DateTime.MinValue;
        }

        // Called from EquestriaCharacterCreationBehavior.OnCharacterCreationFinalize - fires
        // on ANY completion of the wizard (both full and skipped), so it checks Active itself.
        internal static void OnCharacterCreationFinished()
        {
            if (!Active)
            {
                return;
            }
            _pendingPrompt = true;
            _mapSeenAt = DateTime.MinValue;
        }

        public static void Tick()
        {
            if (Active && !_cultureSkipped)
            {
                TrySkipCultureStage();
            }
            if (!_pendingPrompt)
            {
                return;
            }
            TickWaitForMap();
        }

        // While the "Culture" stage is active - select the "empire" culture (the same as Equestria/
        // the ponies) and immediately press "Next" via the data, bypassing the screen itself. Which culture
        // is chosen does not matter: EquestriaCharacterCreationBehavior.OnStageCompleted forces the race to
        // pony right after this stage anyway, and the player changes to the real race himself at the
        // "Appearance" stage.
        private static void TrySkipCultureStage()
        {
            if (!(GameStateManager.Current?.ActiveState is CharacterCreationState creation))
            {
                return;
            }
            CharacterCreationManager manager = creation.CharacterCreationManager;
            if (!(manager?.CurrentStage is CharacterCreationCultureStage))
            {
                return;
            }
            // No more than a few attempts: on an error inside the engine (10.10.2026 - the culture had no
            // list of clan names) the attempt was repeated every frame, 2213 identical errors in the log.
            if (++_cultureAttempts > MaxCultureAttempts)
            {
                _cultureSkipped = true;
                EquestriaCrashLog.Warn("старт по умолчанию: экран народности пропустить не удалось — оставлен игроку");
                return;
            }
            EquestriaCrashLog.Try("старт по умолчанию: пропуск экрана народности", () =>
            {
                var culture = MBObjectManager.Instance.GetObject<CultureObject>("empire");
                if (culture == null || Hero.MainHero == null)
                {
                    return;
                }
                CharacterCreationContent content = manager.CharacterCreationContent;
                content.SetSelectedCulture(culture, manager);
                content.ApplyCulture(manager);
                content.SetMainCharacterName(
                    NameGenerator.Current.GenerateFirstNameForPlayer(culture, Hero.MainHero.IsFemale).ToString());
                manager.NextStage();
                _cultureSkipped = true;
                EquestriaCrashLog.Log("старт по умолчанию: экран народности пропущен автоматически");
            });
        }

        // Wait for the map the same way as EquestriaRaceParty: right after the wizard the campaign is still
        // finishing its start, the party/clan may not be ready for immediate actions.
        private static void TickWaitForMap()
        {
            if (!(GameStateManager.Current?.ActiveState is MapState) || Campaign.Current == null)
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
            _pendingPrompt = false;
            EquestriaCrashLog.Try("старт по умолчанию: телепорт к столице расы", PositionAtRaceCapital);
            EquestriaCrashLog.Try("старт по умолчанию: попап выбора", ShowStartTypePrompt);
        }

        // Race -> realm at whose capital (Kingdom.InitialHomeSettlement, set in
        // equestria_kingdoms.xml by the initial_home_settlement attribute) the player appears with
        // -DefaultStart, regardless of the chosen start type - at the user's request
        // 08.10.2026. The empire (ponies) has four principalities culture="Culture.empire"
        // (kingdom_equestria/lunar/friendship/crystal) - as the race's "homeland" we take Solar Equestria
        // (kingdom_equestria, Celestia) as the main/title one.
        private static readonly Dictionary<string, string> CapitalKingdomByRace = new Dictionary<string, string>
        {
            { "pony", "kingdom_equestria" },
            { "changeling", "kingdom_changeling" },
            { "griffon", "kingdom_griffonia" },
            { "hippogriff", "kingdom_hippogriffia" },
            { "dragon", "kingdom_dragons" },
            { "yak", "kingdom_yakyakistan" },
            { "deer", "kingdom_olenia" },
        };

        private static void PositionAtRaceCapital()
        {
            if (MobileParty.MainParty == null)
            {
                return;
            }
            string[] raceNames = FaceGen.GetRaceNames();
            int race = CharacterObject.PlayerCharacter.Race;
            string raceName = raceNames != null && race >= 0 && race < raceNames.Length
                ? raceNames[race] : null;
            if (raceName == null || !CapitalKingdomByRace.TryGetValue(raceName, out string kingdomId))
            {
                EquestriaCrashLog.Warn($"старт по умолчанию: нет державы для расы {raceName ?? "?"}");
                return;
            }
            Kingdom kingdom = Kingdom.All.FirstOrDefault(k => k.StringId == kingdomId);
            PositionAtKingdomCapital(kingdom, $"столице расы {raceName}");
        }

        // Shared helper: the player's party - to the capital of the given realm (Kingdom.InitialHomeSettlement).
        // Used both for the race (right after the wizard, by default) and for the realm chosen by the player
        // (after applying mercenary/vassal/king - user's request 08.10.2026:
        // if we serve a realm other than our home one, the party must appear at IT, not at the race's homeland).
        private static void PositionAtKingdomCapital(Kingdom kingdom, string why)
        {
            if (MobileParty.MainParty == null)
            {
                return;
            }
            Settlement capital = kingdom?.InitialHomeSettlement;
            if (capital == null)
            {
                EquestriaCrashLog.Warn($"старт по умолчанию: не нашёл столицу державы "
                    + $"{kingdom?.StringId ?? "?"} ({why})");
                return;
            }
            MobileParty.MainParty.Position = capital.Position;
            EquestriaCrashLog.Log($"старт по умолчанию: игрок перемещён к {why} — "
                + $"{capital.StringId} ({kingdom.StringId})");
        }

        private static readonly (string Id, string Title)[] StartTypes =
        {
            ("poor", "{=eq_start_poor}Ordinary humble start"),
            ("mercenary", "{=eq_start_mercenary}Mercenary of a kingdom (clan tier 1)"),
            ("vassal", "{=eq_start_vassal}Vassal of a kingdom (clan tier 3, one fief)"),
            ("king", "{=eq_start_king}Ruler of a kingdom (clan tier 4, one fief)"),
        };

        private static void ShowStartTypePrompt()
        {
            var elements = StartTypes
                .Select(t => new InquiryElement(t.Id, new TextObject(t.Title).ToString(), null))
                .ToList();
            var data = new MultiSelectionInquiryData(
                new TextObject("{=eq_start_title}Choose your start").ToString(),
                new TextObject("{=eq_start_desc}How do you begin your adventure in Equestria?").ToString(),
                elements, false, 1, 1,
                new TextObject("{=eq_start_confirm}Confirm").ToString(), "",
                OnStartTypeChosen, null);
            MBInformationManager.ShowMultiSelectionInquiry(data, true);
        }

        private static void OnStartTypeChosen(List<InquiryElement> selected)
        {
            string startType = (string)selected[0].Identifier;
            if (startType == "poor")
            {
                EquestriaCrashLog.Log("старт по умолчанию: обычный нищий старт");
                InformationManager.DisplayMessage(new InformationMessage(
                    new TextObject("{=eq_start_poor_note}Equestria: an ordinary humble start").ToString(),
                    Colors.Magenta));
                return;
            }
            EquestriaCrashLog.Try("старт по умолчанию: попап державы",
                () => ShowFactionPrompt(startType));
        }

        private static void ShowFactionPrompt(string startType)
        {
            var kingdoms = Kingdom.All.ToList();
            var elements = kingdoms
                .Select(k => new InquiryElement(k, k.Name.ToString(), null))
                .ToList();
            var data = new MultiSelectionInquiryData(
                new TextObject("{=eq_start_kingdom_title}Choose a kingdom").ToString(),
                new TextObject("{=eq_start_kingdom_desc}Which kingdom will you serve?").ToString(),
                elements, false, 1, 1,
                new TextObject("{=eq_start_confirm}Confirm").ToString(), "",
                selected => EquestriaCrashLog.Try("старт по умолчанию: применение",
                    () => ApplyStart(startType, (Kingdom)selected[0].Identifier)),
                null);
            MBInformationManager.ShowMultiSelectionInquiry(data, true);
        }

        private const int MercenaryTier = 1;
        private const int VassalTier = 3;
        private const int KingTier = 4;

        // Gold on top of what the character creation wizard gives - a clan tier with no money in the purse
        // would look absurd. The numbers are picked by eye, not a vanilla constant - they can be adjusted
        // right here, without a console command (the start is chosen once per campaign).
        private const int MercenaryGold = 5000;
        private const int VassalGold = 15000;
        private const int KingGold = 40000;

        private static void ApplyStart(string startType, Kingdom kingdom)
        {
            Clan clan = Clan.PlayerClan;
            int tier = startType == "mercenary" ? MercenaryTier : startType == "vassal" ? VassalTier : KingTier;
            int gold = startType == "mercenary" ? MercenaryGold : startType == "vassal" ? VassalGold : KingGold;

            // Clan.Tier cannot be set directly (the setter is not accessible from outside) - we raise renown to the
            // threshold for the tier, Clan.AddRenown recalculates the tier itself
            // (Clan.cs: Tier = CalculateTier(this)).
            float requiredRenown = Campaign.Current.Models.ClanTierModel.GetRequiredRenownForTier(tier);
            if (requiredRenown > clan.Renown)
            {
                clan.AddRenown(requiredRenown - clan.Renown, false);
            }
            Hero.MainHero.ChangeHeroGold(gold);

            switch (startType)
            {
                case "mercenary":
                    ChangeKingdomAction.ApplyByJoinFactionAsMercenary(clan, kingdom);
                    break;
                case "vassal":
                    ChangeKingdomAction.ApplyByJoinToKingdom(clan, kingdom);
                    GrantSettlement(kingdom, clan);
                    break;
                case "king":
                    // Peaceful seizure of the throne: the clan first joins the realm, then becomes the
                    // ruling one - ChangeRulingClanAction only reassigns Kingdom.RulingClan,
                    // the former ruler stays an ordinary vassal of the same realm, there is no war.
                    ChangeKingdomAction.ApplyByJoinToKingdom(clan, kingdom);
                    ChangeRulingClanAction.Apply(kingdom, clan);
                    GrantSettlement(kingdom, clan);
                    break;
            }

            // In case the realm or the start added something - horse gear is not used in our mod
            EquestriaCrashLog.Try("конское снаряжение игрока", EquestriaFlightArmy.StripPlayerHorseGear);

            // We serve a realm other than the race's home one - the party appears at IT, not at the race's capital
            // (where it already stood after PositionAtRaceCapital right after the wizard).
            PositionAtKingdomCapital(kingdom, $"столице выбранной державы {kingdom.StringId}");

            EquestriaCrashLog.Log($"старт по умолчанию: {startType}, держава {kingdom.StringId}, "
                + $"тир {tier}, золото {gold}");
            InformationManager.DisplayMessage(new InformationMessage(
                new TextObject("{=eq_start_done}Equestria: start applied ({TYPE} of {KINGDOM})")
                    .SetTextVariable("TYPE", StartTypeLabel(startType))
                    .SetTextVariable("KINGDOM", kingdom.Name)
                    .ToString(),
                Colors.Magenta));
        }

        // A short label of the start type for the message text - startType itself is an internal
        // English identifier ("mercenary"/"vassal"/"king"), it must not be substituted directly into
        // a localized phrase.
        private static string StartTypeLabel(string startType)
        {
            switch (startType)
            {
                case "mercenary": return new TextObject("{=eq_start_type_mercenary}mercenary").ToString();
                case "vassal": return new TextObject("{=eq_start_type_vassal}vassal").ToString();
                case "king": return new TextObject("{=eq_start_type_king}ruler").ToString();
                default: return startType;
            }
        }

        // The realm's most modest holding: a castle first (not a town), then minimum
        // prosperity - we do not take the realm's crown jewel away for a starting gift.
        private static void GrantSettlement(Kingdom kingdom, Clan clan)
        {
            Settlement grant = kingdom.Settlements
                .Where(s => s.IsFortification && s.OwnerClan != clan)
                .OrderBy(s => s.IsCastle ? 0 : 1)
                .ThenBy(s => s.Town?.Prosperity ?? 0f)
                .FirstOrDefault();
            if (grant == null)
            {
                EquestriaCrashLog.Warn($"старт по умолчанию: в державе {kingdom.StringId} "
                    + "не нашлось поселения для подарка");
                return;
            }
            ChangeOwnerOfSettlementAction.ApplyByGift(grant, Hero.MainHero);
            EquestriaCrashLog.Log($"старт по умолчанию: подарено поселение {grant.StringId}");
        }
    }
}
