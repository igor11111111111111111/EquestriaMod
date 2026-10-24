using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.GameState;
using TaleWorlds.CampaignSystem.Settlements;
using TaleWorlds.Core;
using TaleWorlds.ObjectSystem;

namespace EquestriaMod
{
    // Ассимиляция расы захваченных поселений — перенос мода DynaCulture (github.com/Splintertx/
    // DynaCulture, открытый код, GPL) на эту расовую систему, без его слабых мест.
    //
    // КЛЮЧЕВОЙ ФАКТ (подтверждён в tools/make_troops.py, CULTURE_RACE): раса рекрута в этом моде
    // жёстко запечена в дерево войск КУЛЬТУРЫ при сборке (sturgia=драконы, aserai=чейнджлинги,
    // vlandia=грифоны, battania=гиппогрифы, khuzait=яки, nord=олени, empire=пони по умолчанию) —
    // не выбирается на лету. Значит программная смена Settlement.Culture (приём DynaCulture) САМА
    // ПО СЕБЕ уже меняет расу, которую набирает поселение — дополнительных связей раса↔культура
    // в этом файле заводить не нужно, работаем напрямую с CultureObject, как и оригинал.
    //
    // Отличия от оригинала (разобран целиком 06.10.2026):
    //  - Один класс логики, не два (в DynaCulture жил мёртвый неймспейс-прототип
    //    ChangeSettlementCulture.Data рядом с рабочим DynaCulture.Data — наследуем только рабочий).
    //  - Сохранение — через НАТИВНЫЙ IDataStore.SyncData (см. ниже), а не свой файл на диске по
    //    имени героя (в оригинале SyncData был пустым, а состояние лежало в отдельном файле —
    //    хрупко: тёзки, не привязано к слоту сохранения).
    //  - Без очистки "corrupted troops/recruits" — это обход БАГА ВАНИЛИ, актуального их инструментам
    //    сборки, у нас не воспроизводился.
    //  - Применяется ко ВСЕМ державам карты (и ИИ, и игрока), как и оригинал по умолчанию.
    //
    // На settlement — не разовый снимок, а СЕТЬ влияний (CurrentInfluences едет к TargetInfluences
    // по экспоненте, см. RaceAssimilationStatus.OnDailyTick), поэтому смена владельца не переключает
    // расу мгновенно — поселение должно какое-то время реально находиться под новой властью.
    //
    // Настройка — консольными командами equestria.race_assim_* (см.
    // EquestriaRaceAssimilationCommands.cs), подбирается вживую и потом вписывается в дефолты ниже
    // руками, тем же приёмом, что и equestria.helmet_scale/helmet_offset у EquestriaHelmetFit.
    public class EquestriaRaceAssimilation : CampaignBehaviorBase
    {
        // Подобрано DynaCulture как рабочие дефолты (DefaultDynaCultureSettings.cs) — отправная
        // точка, уточняется вживую командами ниже.
        public static float InfluenceRange = 30f;
        // Было 45 — по просьбе пользователя 07.10.2026 ("буквально за пару дней много % меняется")
        // в 10 раз медленнее: rate = influenceSum / AssimilationDelay (OnDailyTick), множитель здесь
        // делит скорость приближения Current к Target напрямую, без изменения формы кривой.
        public static int AssimilationDelay = 450;
        public static int OwnerInfluenceStrength = 5;
        public static bool TradeLinkedInfluence = true;

        // Потолок доли доминирующей расы (по просьбе пользователя 07.10.2026: "в идеальном обществе
        // никогда не будет 100% жить одной народности" — 70-90%, остальное размазано по всем прочим
        // расам понемногу). Своя добавка поверх DynaCulture — в оригинале потолка не было, Target
        // мог дойти до чистых 100%. См. применение в RecalculateInfluencers.
        public static decimal MaxDominantShare = 0.85m;

        // Все играбельные культуры мира — раса рекрута запечена на культуру намертво при сборке
        // войск (tools/make_troops.py, CULTURE_RACE), менять/расширять этот список нужно только
        // вместе с ним. Нужны, чтобы размазать остаток ниже MaxDominantShare по ВСЕМ расам, а не
        // только по текущим соседям — даже в поселении без единого соседа другой расы должна
        // появиться минимальная примесь всех остальных.
        internal static readonly string[] AllCultureIds =
            { "empire", "aserai", "vlandia", "battania", "sturgia", "khuzait", "nord" };

        public override void RegisterEvents()
        {
            CampaignEvents.DailyTickSettlementEvent.AddNonSerializedListener(this, OnDailyTickSettlement);
            CampaignEvents.HourlyTickEvent.AddNonSerializedListener(this, OnHourlyTick);
            EquestriaCrashLog.Note("ассимиляция расы: события зарегистрированы (range="
                + InfluenceRange + " delay=" + AssimilationDelay + " owner=" + OwnerInfluenceStrength
                + " trade=" + TradeLinkedInfluence + ")");
        }

        private static bool _tooltipPatchApplied;

        // Патч подсказки поселения — лениво, здесь, а не в EquestriaPatches.Apply/ApplyLate.
        // НАЙДЕНО 06.10.2026 (см. память equestria-race-assimilation): TooltipRefresherCollection
        // .RefreshSettlementTooltip напрямую зовёт CampaignUIHelper, у которой статическое
        // поле-инициализатор (_partyMoraleStr = GameTexts.FindText("str_party_morale"))
        // читает таблицу строк ДО того, как она загружена — если патчить (Harmony вынужден
        // JIT-скомпилировать метод, это запускает статический конструктор типа) на загрузке
        // мода или даже на главном меню, GameTexts.FindText возвращает null, внутри
        // CampaignUIHelper падает NullReferenceException, и тип НАВСЕГДА помечается
        // неинициализированным — родной экран карты (MapBarVM) после этого не строится
        // вовсе. К первому тику кампании движок уже сам успешно тронул CampaignUIHelper
        // (иначе мы бы сюда не добрались), и патчить уже безопасно — повторно статический
        // конструктор уже готового типа не перезапускается.
        //
        // Раньше (07.10.2026) этот гейт стоял ТОЛЬКО на DailyTickSettlementEvent — тот стреляет раз
        // в игровые СУТКИ (и вообще не стреляет, пока время на карте не запущено), подсказка не
        // появлялась почти всю первую игровую сессию (замечено пользователем: навёл на Кантерлот
        // сразу после .\run.ps1 -QuickStart — пусто). HourlyTickEvent немного быстрее, но тоже ждёт
        // хода времени. Основной путь теперь — кадровый опрос Tick() (см. ниже, зовёт
        // SubModule.OnApplicationTick): тот же приём, что уже используют EquestriaRaceParty/
        // EquestriaShowcase — ждём активную MapState и 2 секунды на "устаканивание" кампании, без
        // привязки к ходу игрового времени. По безопасности не хуже тикового гейта: за эти 2
        // секунды родной MapBarVM (который и трогает CampaignUIHelper её же штатным путём) уже
        // давно построен — те же Equestria* классы годами используют этот самый отступ перед своими
        // действиями (открытие окон и т.п.) без единого похожего краша. OnHourlyTick оставлен
        // подстраховкой на случай, если кадровый опрос почему-то не сработает (двойного применения
        // патча не будет — оба пути идут через общий _tooltipPatchApplied).
        private void OnHourlyTick()
        {
            TryApplyTooltipPatch();
            SeedTestVillage();
        }

        private static DateTime _mapSeenAt = DateTime.MinValue;

        /// <summary>Зовётся каждый кадр из SubModule.OnApplicationTick — ловит момент старта
        /// кампании (в т.ч. .\run.ps1 -QuickStart) без ожидания хода игрового времени.</summary>
        public static void Tick()
        {
            if (_tooltipPatchApplied)
            {
                return;
            }
            if (!(GameStateManager.Current?.ActiveState is MapState) || Campaign.Current == null
                || !Campaign.Current.GameStarted)
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
            TryApplyTooltipPatch();
            SeedTestVillage();
        }

        private static bool _testVillageSeeded;

        // Тестовая засевка village_empire_0 (Клеверный Дол) при старте кампании — по просьбе
        // пользователя 07.10.2026: коренная раса 70-90%, остаток размазан случайно по всем
        // остальным расам, чтобы сразу после .\run.ps1 -QuickStart было видно таблицу в подсказке,
        // не вводя equestria.race_assim_set руками. Разовая, как и применение патча подсказки —
        // дальше обычный OnDailyTick сам поведёт Current к настоящей Target как для любой деревни.
        private static void SeedTestVillage()
        {
            if (_testVillageSeeded || Campaign.Current == null || !Campaign.Current.GameStarted)
            {
                return;
            }
            _testVillageSeeded = true;
            try
            {
                if (RaceAssimilationManager.Instance.InfluenceMap.Count == 0)
                {
                    RaceAssimilationManager.Instance.Initialize();
                }
                if (!RaceAssimilationManager.Instance.InfluenceMap.TryGetValue("village_empire_0", out RaceAssimilationStatus status))
                {
                    EquestriaCrashLog.Warn("ассимиляция расы: тестовая деревня village_empire_0 не найдена, засев пропущен");
                    return;
                }
                var rng = new Random();
                decimal homeland = 70m + (decimal)rng.NextDouble() * 20m;
                string[] others = AllCultureIds.Where(id => id != status.HomelandCultureId).ToArray();
                var weights = others.Select(id => (id, w: (decimal)rng.NextDouble() + 0.1m)).ToList();
                decimal weightSum = weights.Sum(w => w.w);
                decimal remainder = 100m - homeland;
                var seeded = new Dictionary<string, decimal> { [status.HomelandCultureId] = homeland / 100m };
                foreach (var (id, w) in weights)
                {
                    seeded[id] = w / weightSum * remainder / 100m;
                }
                status.CurrentInfluences = seeded;
                EquestriaCrashLog.Log("ассимиляция расы: тестовая деревня village_empire_0 засеяна — "
                    + string.Join(", ", seeded.OrderByDescending(p => p.Value).Select(p => $"{p.Key}={p.Value * 100:0.#}%")));
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Warn("ассимиляция расы: засев тестовой деревни упал: " + e.GetType().Name
                    + ": " + e.Message + "\r\n" + e.StackTrace);
            }
        }

        private static void TryApplyTooltipPatch()
        {
            try
            {
                if (_tooltipPatchApplied || Campaign.Current == null || !Campaign.Current.GameStarted)
                {
                    return;
                }
                _tooltipPatchApplied = true;
                if (EquestriaPatches.Instance != null)
                {
                    RaceAssimilationTooltipPatch.Apply(EquestriaPatches.Instance);
                }
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Warn("ассимиляция расы: применение патча подсказки упало: "
                    + e.GetType().Name + ": " + e.Message + "\r\n" + e.StackTrace);
            }
        }

        // Тик дёргается на КАЖДОЕ поселение КАЖДЫЙ день — исключение здесь без try/catch уронило бы
        // тик для вообще всех поселений разом (один сломанный Settlement.Find — и всей кампании
        // конец). Лог — только на подозрительное: не пишем сюда на каждый нормальный тик, иначе
        // журнал (лимит 8 МБ, см. EquestriaCrashLog) захлебнётся за один игровой год на полной карте.
        private void OnDailyTickSettlement(Settlement settlement)
        {
            try
            {
                if (Campaign.Current == null || !Campaign.Current.GameStarted || settlement == null)
                {
                    return;
                }
                if (!(settlement.IsVillage || settlement.IsCastle || settlement.IsTown))
                {
                    return;
                }
                if (RaceAssimilationManager.Instance.InfluenceMap.Count == 0)
                {
                    RaceAssimilationManager.Instance.Initialize();
                }
                if (RaceAssimilationManager.Instance.InfluenceMap.TryGetValue(settlement.StringId, out RaceAssimilationStatus status))
                {
                    status.OnDailyTick();
                }
                else
                {
                    EquestriaCrashLog.Warn("ассимиляция расы: нет статуса для " + settlement.StringId
                        + " (" + settlement.Name + ") после инициализации");
                }
            }
            catch (Exception e)
            {
                EquestriaCrashLog.Warn("ассимиляция расы: тик поселения " + (settlement != null ? settlement.StringId : "?")
                    + " упал: " + e.GetType().Name + ": " + e.Message + "\r\n" + e.StackTrace);
            }
        }

        // Плоская сериализация (тот же приём, что EquestriaBodyParts.SyncHairLookCache): поселение
        // -> одна закодированная строка (RaceAssimilationStatus.Encode/Decode), хранится как два
        // параллельных List<string> — Dictionary<string,string> тоже синкается нативно
        // (см. EquestriaRaceSaveBehavior._heroRaces), но пара списков проще отлаживать руками.
        //
        // Сброс статического менеджера — ЗДЕСЬ, в ветке загрузки, а не на OnGameLoadedEvent: тот
        // стреляет ПОСЛЕ SyncData всех поведений, и обнулил бы уже загруженные данные этого самого
        // вызова. Сброс нужен, чтобы не тащить в новую загруженную игру данные от ПРЕДЫДУЩЕЙ
        // (играем, выходим в меню, грузим другое сохранение в том же процессе — статик переживёт).
        public override void SyncData(IDataStore dataStore)
        {
            if (!dataStore.IsSaving)
            {
                RaceAssimilationManager.Reset();
            }

            List<string> keys = null;
            List<string> values = null;
            if (dataStore.IsSaving)
            {
                keys = RaceAssimilationManager.Instance.InfluenceMap.Keys.ToList();
                values = keys.Select(k => RaceAssimilationManager.Instance.InfluenceMap[k].Encode()).ToList();
            }

            dataStore.SyncData("eq_race_assim_keys", ref keys);
            dataStore.SyncData("eq_race_assim_values", ref values);

            if (dataStore.IsSaving)
            {
                EquestriaCrashLog.Log("ассимиляция расы: сохранено поселений " + (keys?.Count ?? 0));
            }
            else if (keys != null && values != null && keys.Count == values.Count)
            {
                int decoded = 0;
                int failed = 0;
                for (int i = 0; i < keys.Count; i++)
                {
                    RaceAssimilationStatus status = RaceAssimilationStatus.Decode(keys[i], values[i]);
                    if (status != null)
                    {
                        RaceAssimilationManager.Instance.InfluenceMap[keys[i]] = status;
                        decoded++;
                    }
                    else
                    {
                        failed++;
                    }
                }
                EquestriaCrashLog.Log("ассимиляция расы: загружено поселений " + decoded
                    + (failed > 0 ? ", не удалось раскодировать " + failed : ""));
            }
            else if (keys != null || values != null)
            {
                EquestriaCrashLog.Warn("ассимиляция расы: ключи/значения рассинхронизированы при загрузке "
                    + "(keys=" + (keys?.Count.ToString() ?? "null") + " values=" + (values?.Count.ToString() ?? "null") + ")");
            }
        }
    }

    // Статический менеджер — доступ нужен и из CampaignBehaviorBase (тик/сохранение), и из
    // консольных команд/Harmony-патча подсказки (EquestriaRaceAssimilationCommands.cs), у которых
    // нет ссылки на экземпляр поведения. Тот же паттерн, что ChangeCultureManager/DynaCultureManager
    // в оригинале.
    internal sealed class RaceAssimilationManager
    {
        private static RaceAssimilationManager _instance;

        public static RaceAssimilationManager Instance => _instance ?? (_instance = new RaceAssimilationManager());

        public readonly Dictionary<string, RaceAssimilationStatus> InfluenceMap =
            new Dictionary<string, RaceAssimilationStatus>();

        internal static void Reset()
        {
            _instance = null;
        }

        // Устойчиво к новым поселениям, заведённым позже (кампания расширилась и т.п.) — то же,
        // что DynaCultureManager.Initialize().
        public void Initialize()
        {
            int before = InfluenceMap.Count;
            foreach (Settlement settlement in Settlement.All.Where(s => s.IsVillage || s.IsCastle || s.IsTown))
            {
                if (!InfluenceMap.ContainsKey(settlement.StringId))
                {
                    InfluenceMap[settlement.StringId] = new RaceAssimilationStatus(settlement);
                }
            }
            foreach (RaceAssimilationStatus status in InfluenceMap.Values)
            {
                status.OnCampaignLoad();
            }
            EquestriaCrashLog.Log("ассимиляция расы: инициализировано поселений " + InfluenceMap.Count
                + (before > 0 ? " (было " + before + " до вызова)" : ""));
        }
    }

    // На одно поселение: сеть влияний (CurrentInfluences едет к TargetInfluences по экспоненте) и
    // применение победившей расы. Перенос DynaCultureStatus (DynaCulture/Data/DynaCultureStatus.cs)
    // — комментарии ниже объясняют только то, что отличается от оригинала или не очевидно само по
    // себе; сама механика разобрана и задокументирована в [[dynaculture-race-assimilation]] (память).
    internal sealed class RaceAssimilationStatus
    {
        private const int BaseInfluence = 1;

        private readonly string _settlementId;

        // Раса, с которой поселение родилось — не меняется, используется для бонуса сопротивления
        // (см. GetInfluenceFromSettlement) и для разрешения ничьей в GetTopCultureId.
        public readonly string HomelandCultureId;

        public Dictionary<string, decimal> CurrentInfluences = new Dictionary<string, decimal>();
        public Dictionary<string, decimal> TargetInfluences = new Dictionary<string, decimal>();

        // Только для дневной дельты в подсказке (EquestriaRaceAssimilationCommands) — не
        // сохраняется между сессиями (как и в оригинале не портит механику: первый тик после
        // загрузки просто покажет дельту 0, GetPreviousInfluenceForCulture откатится на Current).
        public Dictionary<string, decimal> PreviousInfluences;

        public int DaysSinceTargetsChanged;
        public int ExpectedIdKey;
        public int TargetInfluencesIdKey;

        public RaceAssimilationStatus(Settlement settlement)
        {
            _settlementId = settlement.StringId;
            HomelandCultureId = settlement.Culture.StringId;
        }

        private RaceAssimilationStatus(string settlementId, string homelandCultureId)
        {
            _settlementId = settlementId;
            HomelandCultureId = homelandCultureId;
        }

        public void OnCampaignLoad()
        {
            if (CurrentInfluences.Count == 0)
            {
                Settlement settlement = Settlement.Find(_settlementId);
                CurrentInfluences[settlement.Culture.StringId] = 1m;
            }
            if (TargetInfluences.Count == 0)
            {
                RecalculateInfluencers(firstTimeSetup: true);
            }
        }

        public void OnDailyTick()
        {
            int influenceSum = RecalculateInfluencers(firstTimeSetup: false);
            PreviousInfluences = new Dictionary<string, decimal>(CurrentInfluences);

            if (ExpectedIdKey != TargetInfluencesIdKey)
            {
                // сосед/владелец поменялся с прошлого тика — считаем дни заново
                DaysSinceTargetsChanged = 0;
                ExpectedIdKey = TargetInfluencesIdKey;
            }
            else
            {
                DaysSinceTargetsChanged++;
            }

            // Экспоненциальное приближение: каждый день проходим 1/AssimilationDelay доли разницы.
            // Не линейно — быстрый прогресс вначале, медленно доходит до конца, в упор никогда не
            // встаёт (намеренно, как в оригинале: имитирует инерцию ассимиляции населения).
            //
            // БАГ (найден пользователем 07.10.2026 через equestria.race_assim_set, но воспроизводим
            // и без него): цикл раньше шёл только по ключам TargetInfluences — расу, у которой
            // влияние пропало совсем (сосед той расы разрушен/сменил владельца, целевая доля стала
            // ровно 0 и ключ исчез из Target), никто не трогал. Current у неё замирал навсегда на
            // последнем значении, а остальные расы продолжали расти к своим целям — сумма долей
            // уезжала выше 100%. Поэтому идём по ОБЪЕДИНЕНИЮ ключей обоих словарей: для расы, которой
            // нет в Target, цель считается 0 и она так же экспоненциально угасает, как и остальные.
            decimal rate = Math.Min((decimal)influenceSum / EquestriaRaceAssimilation.AssimilationDelay, 1m);
            foreach (string cultureId in CurrentInfluences.Keys.Union(TargetInfluences.Keys).ToList())
            {
                decimal current = CurrentInfluences.TryGetValue(cultureId, out decimal c) ? c : 0m;
                decimal target = TargetInfluences.TryGetValue(cultureId, out decimal t) ? t : 0m;
                CurrentInfluences[cultureId] = current + (target - current) * rate;
            }
            // Угасание к 0 никогда не даёт отрицательных значений — чистим по порогу, иначе давно
            // угасшие расы (доля вроде 0.0001%) остаются в словаре навечно.
            foreach (string key in CurrentInfluences.Where(p => p.Value < 0.0001m).Select(p => p.Key).ToList())
            {
                CurrentInfluences.Remove(key);
            }

            ApplyRace();
        }

        public decimal GetPreviousInfluenceForCulture(string cultureId)
        {
            if (PreviousInfluences != null && PreviousInfluences.TryGetValue(cultureId, out decimal previous))
            {
                return previous;
            }
            return CurrentInfluences.TryGetValue(cultureId, out decimal current) ? current : 0m;
        }

        /// <summary>Пересчитывает цель (TargetInfluences) по текущим соседям/владельцу. Возвращает
        /// сумму влияния (знаменатель долей) — она же скорость приближения в OnDailyTick.</summary>
        private int RecalculateInfluencers(bool firstTimeSetup)
        {
            Settlement settlement = Settlement.Find(_settlementId);
            TaleWorlds.Library.Vec2 position = settlement.GetPosition2D;

            List<Settlement> influencing = Settlement.All
                .Where(s => (s.IsVillage || s.IsCastle || s.IsTown)
                            && s.GetPosition2D.Distance(position) <= EquestriaRaceAssimilation.InfluenceRange)
                .ToList();

            if (EquestriaRaceAssimilation.TradeLinkedInfluence)
            {
                if (settlement.IsCastle || settlement.IsTown)
                {
                    influencing.AddRange(settlement.BoundVillages.Select(v => v.Settlement));
                }
                if (settlement.IsVillage)
                {
                    Settlement parent = Settlement.All.FirstOrDefault(s =>
                        s.BoundVillages != null && s.BoundVillages.Any(v => v.Settlement == settlement));
                    if (parent != null)
                    {
                        influencing.AddRange(parent.BoundVillages.Select(v => v.Settlement));
                    }
                }
            }

            int sum = 0;
            var influencers = new Dictionary<string, int>();
            foreach (Settlement other in influencing.Distinct())
            {
                int influence = GetInfluenceFromSettlement(other, settlement, firstTimeSetup);
                sum += influence;
                // Бакет — ТЕКУЩАЯ раса соседа (а не раса его владельца): наполовину
                // ассимилированный сосед и давит слабее (см. GetInfluenceFromSettlement, вес домножен
                // на его же GetTopCulturePercent).
                string cultureId = other.Culture.StringId;
                influencers[cultureId] = influencers.TryGetValue(cultureId, out int existing)
                    ? existing + influence : influence;
            }

            int ownerInfluence = BaseInfluence * EquestriaRaceAssimilation.OwnerInfluenceStrength;
            sum += ownerInfluence;
            if (ownerInfluence > 0)
            {
                string ownerCultureId = GetOwnerCulture(settlement).StringId;
                influencers[ownerCultureId] = influencers.TryGetValue(ownerCultureId, out int existingOwner)
                    ? existingOwner + ownerInfluence : ownerInfluence;
            }

            bool didTargetsChange = false;
            foreach (KeyValuePair<string, int> pair in influencers)
            {
                decimal percent = sum > 0 ? (decimal)pair.Value / sum : 0m;
                if (!TargetInfluences.TryGetValue(pair.Key, out decimal existing) || existing != percent)
                {
                    TargetInfluences[pair.Key] = percent;
                    didTargetsChange = true;
                }
            }
            foreach (string key in TargetInfluences.Keys.Where(k => !influencers.ContainsKey(k)).ToList())
            {
                if (TargetInfluences[key] != 0m)
                {
                    TargetInfluences[key] = 0m;
                    didTargetsChange = true;
                }
            }

            // Потолок доминирующей расы (EquestriaRaceAssimilation.MaxDominantShare) — остаток
            // размазываем по ВСЕМ играбельным расам (не только нынешним соседям), включая те, у
            // которых пока доли вообще не было: даже чисто монокультурное поселение (сосед и
            // владелец одной расы, обрезанная доля ушла бы к 100%) получает минимальную примесь
            // каждой расы мира.
            //
            // НЕ поровну (по просьбе пользователя 07.10.2026: "2.5% для каждой выглядит странно") —
            // вес каждой расы берём от СТАБИЛЬНОГО псевдослучайного числа (хэш id поселения + id
            // расы, не new Random()): у разных поселений остаток размазан по-разному, но у ОДНОГО
            // и того же поселения веса не тасуются заново на каждом дневном тике без всякой причины.
            if (TargetInfluences.Count > 0)
            {
                var top = TargetInfluences.OrderByDescending(p => p.Value).First();
                if (top.Value > EquestriaRaceAssimilation.MaxDominantShare)
                {
                    decimal excess = top.Value - EquestriaRaceAssimilation.MaxDominantShare;
                    TargetInfluences[top.Key] = EquestriaRaceAssimilation.MaxDominantShare;
                    string[] others = EquestriaRaceAssimilation.AllCultureIds.Where(id => id != top.Key).ToArray();
                    if (others.Length > 0)
                    {
                        Dictionary<string, decimal> weights = others.ToDictionary(id => id,
                            id => 0.2m + StableWeight01(_settlementId + "|" + id) * 0.8m);
                        decimal weightSum = weights.Values.Sum();
                        foreach (string id in others)
                        {
                            decimal share = weights[id] / weightSum * excess;
                            TargetInfluences[id] = TargetInfluences.TryGetValue(id, out decimal existing)
                                ? existing + share : share;
                        }
                    }
                    didTargetsChange = true;
                }
            }

            if (didTargetsChange)
            {
                TargetInfluencesIdKey++;
            }
            return sum;
        }

        // Стабильное псевдослучайное число в [0, 1) от строки — тот же приём FNV-1a, что
        // EquestriaBodyParts.LoreColor (там для цвета героя, здесь для веса расы в остатке
        // потолка). Не System.Random: его не засеять строкой напрямую, а GetHashCode() в .NET не
        // детерминирован между запусками процесса.
        private static decimal StableWeight01(string s)
        {
            uint hash = 2166136261;
            unchecked
            {
                foreach (char c in s)
                {
                    hash ^= c;
                    hash *= 16777619;
                }
            }
            return hash / (decimal)uint.MaxValue;
        }

        /// <summary>Вес влияния poselения other на self. Город×3/замок×2/деревня×1, само на себя
        /// ×2, и ещё ×2 если ВЛАДЕЛЕЦ этого (self) поселения до сих пор той же расы, с которой оно
        /// родилось (сопротивление смене) — бонус именно по владельцу, не по текущей отображаемой
        /// расе poselения (та как раз и есть то, что мы постепенно меняем).</summary>
        private int GetInfluenceFromSettlement(Settlement other, Settlement self, bool firstTimeSetup)
        {
            int influence = BaseInfluence;
            if (other.IsTown)
            {
                influence *= 3;
            }
            else if (other.IsCastle)
            {
                influence *= 2;
            }

            bool isSelf = other.StringId == self.StringId;
            if (isSelf)
            {
                influence *= 2;
                if (GetOwnerCulture(other).StringId == HomelandCultureId)
                {
                    influence *= 2;
                }
            }

            if (!firstTimeSetup)
            {
                decimal otherTop = RaceAssimilationManager.Instance.InfluenceMap.TryGetValue(other.StringId, out RaceAssimilationStatus status)
                    ? status.GetTopCulturePercent() : 1m;
                influence = (int)Math.Round(influence * otherTop, MidpointRounding.AwayFromZero);
            }
            return influence;
        }

        /// <summary>Побеждающая раса: ничья разрешается в пользу родной расы поселения, иначе —
        /// по алфавиту (тот же порядок, что в оригинале, чтобы результат был детерминирован).</summary>
        public string GetTopCultureId()
        {
            KeyValuePair<string, decimal> top = CurrentInfluences.OrderByDescending(p => p.Value).First();
            List<KeyValuePair<string, decimal>> tied = CurrentInfluences.Where(p => p.Value == top.Value).ToList();
            if (tied.Count > 1)
            {
                return tied.Any(p => p.Key == HomelandCultureId)
                    ? HomelandCultureId
                    : tied.OrderBy(p => p.Key).First().Key;
            }
            return top.Key;
        }

        public decimal GetTopCulturePercent()
        {
            if (CurrentInfluences.Count == 0)
            {
                return 0m;
            }
            string topId = GetTopCultureId();
            return CurrentInfluences.TryGetValue(topId, out decimal value) ? value : 0m;
        }

        /// <summary>Если доминирующая раса отличается от текущей Settlement.Culture — переключает
        /// её по-настоящему (и привязанные деревни тоже). Предохранитель оригинала: не оставлять
        /// расу вовсе без городов — иначе компаньонам той расы негде заспауниться (краш).</summary>
        private void ApplyRace()
        {
            if (CurrentInfluences.Count == 0)
            {
                return;
            }
            Settlement settlement = Settlement.Find(_settlementId);
            string topId = GetTopCultureId();
            if (settlement.Culture.StringId == topId)
            {
                return;
            }

            if (settlement.IsTown)
            {
                int remainingTowns = Settlement.All.Count(s => s.IsTown && s.Culture.StringId == settlement.Culture.StringId);
                if (remainingTowns <= 1)
                {
                    EquestriaCrashLog.Log("ассимиляция расы: " + settlement.Name + " — смена "
                        + settlement.Culture.StringId + "->" + topId + " ОТМЕНЕНА, последний город расы");
                    return;
                }
            }

            CultureObject topCulture = MBObjectManager.Instance.GetObject<CultureObject>(topId);
            if (topCulture == null)
            {
                EquestriaCrashLog.Warn("ассимиляция расы: культура " + topId + " не найдена в MBObjectManager, "
                    + settlement.Name + " не переключена");
                return;
            }

            EquestriaCrashLog.Log("ассимиляция расы: " + settlement.Name + " (" + _settlementId + ") сменила расу "
                + settlement.Culture.StringId + " -> " + topId + " (день " + DaysSinceTargetsChanged + ")");
            settlement.Culture = topCulture;
            if (settlement.BoundVillages != null)
            {
                foreach (Village attached in settlement.BoundVillages)
                {
                    if (attached.Settlement != null)
                    {
                        attached.Settlement.Culture = topCulture;
                    }
                }
            }
        }

        private static CultureObject GetOwnerCulture(Settlement settlement)
        {
            if (settlement.OwnerClan?.Kingdom != null)
            {
                return settlement.OwnerClan.Kingdom.Culture;
            }
            if (settlement.OwnerClan?.Culture != null)
            {
                return settlement.OwnerClan.Culture;
            }
            return settlement.Culture;
        }

        // ---- плоская сериализация под IDataStore (см. EquestriaRaceAssimilation.SyncData) ----

        public string Encode()
        {
            return string.Join("|", new[]
            {
                HomelandCultureId,
                EncodeMap(CurrentInfluences),
                EncodeMap(TargetInfluences),
                DaysSinceTargetsChanged.ToString(CultureInfo.InvariantCulture),
                ExpectedIdKey.ToString(CultureInfo.InvariantCulture),
                TargetInfluencesIdKey.ToString(CultureInfo.InvariantCulture),
            });
        }

        public static RaceAssimilationStatus Decode(string settlementId, string encoded)
        {
            if (string.IsNullOrEmpty(encoded))
            {
                return null;
            }
            string[] parts = encoded.Split('|');
            if (parts.Length != 6)
            {
                return null;
            }
            var status = new RaceAssimilationStatus(settlementId, parts[0])
            {
                CurrentInfluences = DecodeMap(parts[1]),
                TargetInfluences = DecodeMap(parts[2]),
            };
            int.TryParse(parts[3], NumberStyles.Integer, CultureInfo.InvariantCulture, out int days);
            int.TryParse(parts[4], NumberStyles.Integer, CultureInfo.InvariantCulture, out int expected);
            int.TryParse(parts[5], NumberStyles.Integer, CultureInfo.InvariantCulture, out int targetKey);
            status.DaysSinceTargetsChanged = days;
            status.ExpectedIdKey = expected;
            status.TargetInfluencesIdKey = targetKey;
            return status;
        }

        private static string EncodeMap(Dictionary<string, decimal> map)
        {
            return string.Join(";", map.Select(p => p.Key + "=" + p.Value.ToString(CultureInfo.InvariantCulture)));
        }

        private static Dictionary<string, decimal> DecodeMap(string encoded)
        {
            var result = new Dictionary<string, decimal>();
            if (string.IsNullOrEmpty(encoded))
            {
                return result;
            }
            foreach (string entry in encoded.Split(';'))
            {
                int eq = entry.IndexOf('=');
                if (eq <= 0)
                {
                    continue;
                }
                string key = entry.Substring(0, eq);
                if (decimal.TryParse(entry.Substring(eq + 1), NumberStyles.Float, CultureInfo.InvariantCulture, out decimal value))
                {
                    result[key] = value;
                }
            }
            return result;
        }
    }
}
