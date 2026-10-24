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
    // .\run.ps1 -DefaultStart (/eqdefaultstart): настоящая новая кампания, мастер создания
    // персонажа идёт ПОЛНОСТЬЮ (раса выбирается там же, на этапе «Внешность», готовым списком
    // народностей — EquestriaRaceSelector), кроме самого первого этапа «Народность» — его
    // пропускаем автоматически (раса там всё равно только 6 из 7, без оленей, а настоящий выбор
    // расы — на «Внешности»). Сразу после мастера — свой выбор начала игры: обычный нищий старт,
    // либо наёмник/вассал/правитель выбранной державы (тир клана 1/3/4; вассалу и правителю
    // вдобавок дарится одно поселение).
    //
    // Пропуск этапа «Народность» — НАПРЯМУЮ через CharacterCreationManager/CharacterCreationContent
    // (SetSelectedCulture/ApplyCulture/NextStage, то же самое в итоге делает нажатие «Далее»),
    // а не через чужой View (SandBox.GauntletUI...CultureStageView.NextStage()) — тот вызов падал
    // NullReferenceException: CurrentSelectedCulture у VM ещё не готов сразу после появления
    // экрана, а раз он не выставляется сам по себе, повторы по кадрам тоже не помогали (замечено
    // 08.10.2026). Работа напрямую с данными мастера этой проблемы не имеет вовсе.
    public static class EquestriaDefaultStart
    {
        // Выставляется EquestriaQuickStart.Tick() при запуске по /eqdefaultstart.
        public static bool Active;

        private static bool _cultureSkipped;
        private static int _cultureAttempts;
        private const int MaxCultureAttempts = 5;
        private static bool _pendingPrompt;
        private static DateTime _mapSeenAt = DateTime.MinValue;

        // Вызывается из EquestriaQuickStart.Tick() при старте новой кампании — сбрасывает
        // состояние на случай повторного -DefaultStart в том же запуске игры.
        internal static void Begin()
        {
            Active = true;
            _cultureSkipped = false;
            _cultureAttempts = 0;
            _pendingPrompt = false;
            _mapSeenAt = DateTime.MinValue;
        }

        // Вызывается из EquestriaCharacterCreationBehavior.OnCharacterCreationFinalize — срабатывает
        // у ЛЮБОГО завершения мастера (и полного, и пропущенного), поэтому сам проверяет Active.
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

        // Пока этап «Народность» активен — выбираем культуру "empire" (та же, что у Equestria/
        // пони) и сразу жмём «Далее» данными, минуя сам экран. Какая культура выбрана — не важно:
        // EquestriaCharacterCreationBehavior.OnStageCompleted всё равно форсит расу в пони сразу
        // после этого этапа, а настоящую расу игрок меняет сам на этапе «Внешность».
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
            // Не больше нескольких попыток: при ошибке внутри движка (10.10.2026 — у культуры не было
            // списка названий кланов) попытка повторялась каждый кадр, 2213 одинаковых ошибок в журнале.
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

        // Ждём карту тем же приёмом, что EquestriaRaceParty: сразу после мастера кампания ещё
        // доигрывает своё начало, отряда/клана может не хватать для немедленных действий.
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

        // Раса -> держава, у чьей столицы (Kingdom.InitialHomeSettlement, задана в
        // equestria_kingdoms.xml атрибутом initial_home_settlement) появляется игрок при
        // -DefaultStart, независимо от выбранного типа старта — по просьбе пользователя
        // 08.10.2026. У империи (пони) четыре княжества culture="Culture.empire"
        // (kingdom_equestria/lunar/friendship/crystal) — за "родину" расы берём Solar Equestria
        // (kingdom_equestria, Селестия) как основную/заглавную.
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

        // Общий хелпер: отряд игрока — к столице указанной державы (Kingdom.InitialHomeSettlement).
        // Используется и для расы (сразу после мастера, по умолчанию), и для выбранной игроком
        // державы (после применения наёмника/вассала/короля — просьба пользователя 08.10.2026:
        // если служим не своей родной державе, отряд должен появиться у НЕЁ, а не у родины расы).
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

        // Золото сверх того, что выдаёт мастер создания персонажа — тир клана без денег в кошельке
        // смотрелся бы нелепо. Числа подобраны на глаз, не ванильная константа — подправить можно
        // прямо здесь, без консольной команды (старт выбирается один раз за кампанию).
        private const int MercenaryGold = 5000;
        private const int VassalGold = 15000;
        private const int KingGold = 40000;

        private static void ApplyStart(string startType, Kingdom kingdom)
        {
            Clan clan = Clan.PlayerClan;
            int tier = startType == "mercenary" ? MercenaryTier : startType == "vassal" ? VassalTier : KingTier;
            int gold = startType == "mercenary" ? MercenaryGold : startType == "vassal" ? VassalGold : KingGold;

            // Clan.Tier сам не выставить (сеттер недоступен снаружи) — поднимаем ренаун до нужного
            // тиру порога, Clan.AddRenown сама пересчитывает тир (Clan.cs: Tier = CalculateTier(this)).
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
                    // Мирный захват трона: клан сперва входит в державу, потом становится
                    // правящим — ChangeRulingClanAction лишь переставляет Kingdom.RulingClan,
                    // прежний правитель остаётся рядовым вассалом той же державы, войны нет.
                    ChangeKingdomAction.ApplyByJoinToKingdom(clan, kingdom);
                    ChangeRulingClanAction.Apply(kingdom, clan);
                    GrantSettlement(kingdom, clan);
                    break;
            }

            // Вдруг держава или старт что-то добавили — конское снаряжение у нас не в ходу
            EquestriaCrashLog.Try("конское снаряжение игрока", EquestriaFlightArmy.StripPlayerHorseGear);

            // Служим не родной державе расы — отряд появляется у НЕЁ, а не у столицы расы (там
            // уже стояли после PositionAtRaceCapital сразу после мастера).
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

        // Короткая подпись типа старта для текста сообщения — startType сам по себе внутренний
        // английский идентификатор ("mercenary"/"vassal"/"king"), подставлять его напрямую в
        // локализованную фразу нельзя.
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

        // Самое скромное владение державы: сначала замок (не город), затем минимальное
        // процветание — не отбираем у державы её главную жемчужину ради стартового подарка.
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
