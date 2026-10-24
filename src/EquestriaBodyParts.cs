﻿using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using HarmonyLib;
using TaleWorlds.CampaignSystem;
using TaleWorlds.Core;
using TaleWorlds.Engine;
using TaleWorlds.Library;
using TaleWorlds.MountAndBlade;

namespace EquestriaMod
{
    // Хвост пони, крылья чейнджлинга и хвост оленя — части тела, а не снаряжение.
    //
    // В движке нельзя ни добавить свой слот (EquipmentIndex — константы, всего 12, брони из них пять),
    // ни положить в слот два предмета: в Equipment на индекс приходится ровно один элемент. Держать
    // хвост предметом плаща тоже плохо — надетая накидка его вытесняет. А вшить в меш тела нельзя:
    // нагрудник с covers_body скрывает тело целиком, а без этого флага под каждой броней пришлось бы
    // рисовать ещё и тело — лишние полигоны в больших боях.
    //
    // Поэтому меш вешается прямо на скелет уже собранного персонажа (GameEntity.AddMultiMeshToSkeleton):
    // слот остаётся свободным, скиннинг настоящий (хвост сидит на тазе и не ездит за головой),
    // и ничего не пропадает под броней. Снимать при смерти не нужно — это часть тела.
    //
    // Два места, где собирается персонаж: миссия (бой, город, разговор) — здесь через OnAgentBuild,
    // и экраны с портретами (инвентарь, отряд, цирюльник) — там свой механизм, CharacterTableau,
    // его цепляем патчем (см. ApplyTableau).
    public class EquestriaBodyParts : MissionBehavior
    {
        public override MissionBehaviorType BehaviorType => MissionBehaviorType.Other;

        // раса -> меши, которые всегда на теле (у грифона их два: крылья и хвост)
        private static readonly Dictionary<string, string[]> PartByRace = new Dictionary<string, string[]>
        {
            // Новая пони (tools/make_pony_model.py): рог, маленькие крылья и длинный хвост на теле.
            // Пока её FBX не импортирован, тут прежний хвост Twilight — см. RaceParts.
            // Уши (07.10.2026, пользователь отделил их от гривы в Blender) — отдельная часть, как
            // у грифона/чейнджлинга/оленя: красятся ОБЩИМ материалом тела (не в списке
            // hair-переопределения tools/pony_material.ps1, в отличие от рога/хвоста/крыльев,
            // которые у пони нарочно перекрашены в материал гривы), прячутся под любым головным
            // убором тем же приёмом, что и у остальных рас (см. EarMeshByRace).
            { "pony", new[] { "eq_pony_tail", "eq_pony_wings", "eq_pony_horn", "eq_pony_ears" } },
            // Чейнджлинг (tools/make_changeling_model.py): две пары стрекозиных крыльев одним
            // мешем и хвост на тазе. Раньше был только меш крыльев, хвоста у старой модели не было.
            // Рог и уши (04.10.2026, пересборка модели) — рог существовал отдельным мешем и раньше,
            // но тут не был упомянут вовсе и висел в .tpac без хозяина; уши — новая часть, прячем
            // при надетом шлеме (см. EarMeshByRace).
            { "changeling", new[] { "eq_changeling_wings", "eq_changeling_tail",
                "eq_changeling_horn", "eq_changeling_ears" } },
            // Олениха (tools/make_deer_model.py): короткий хвост на тазе. Рога (04.10.2026,
            // пересборка модели) раньше были причёской (eq_deer_hair), теперь отдельная часть —
            // настоящие "волосы" (другой меш, та же причёска-слот) и уши — новые, уши прячем под
            // шлемом (EarMeshByRace), рога — нет, они часть тела, как у остальных рас.
            // Четыре варианта рогов (10.10.2026): крепятся все, видны только выбранные — см.
            // DeerAntlers ниже (номер берётся из причёски).
            { "deer", new[] { "eq_deer_tail", "eq_deer_horn", "eq_deer_horn_2", "eq_deer_horn_3",
                "eq_deer_horn_4", "eq_deer_ears" } },
            // Як (tools/make_yak_model.py): кончик хвоста — отдельный предмет на кости таза. Рог —
            // отдельная часть (04.10.2026, пользователь отделил его от головы в Blender, как рог
            // у пони/дракона) — раньше был частью face_meta_mesh, в скине расы не упомянут и без
            // этой строки висел бы в .tpac без хозяина.
            { "yak", new[] { "eq_yak_tail", "eq_yak_horn" } },
            // Дракон (tools/make_dragon.py): хвост на тазе, крылья на верхе позвоночника.
            // В слот плаща их не кладём — надетая накидка вытеснила бы, а крылья нужны всегда.
            // Рог — отдельная часть (06.10.2026, пользователь отделил его от головы в Blender,
            // как рог у пони/яка/оленя) — красится ОБЩИМ материалом тела (eq_dragon_body), не
            // волосяным: в отличие от пони, где рог/хвост/крылья нарочно перекрашены в материал
            // гривы (см. tools/pony_material.ps1), у дракона только eq_dragon_hair получает
            // волосяной материал (tools/dragon_material.ps1), а eq_dragon_horn — обычный, как
            // тело, по общему правилу без явного переопределения.
            { "dragon", new[] { "eq_dragon_tail", "eq_dragon_wings", "eq_dragon_horn" } },
            // Грифон (tools/make_griffon.py): львиный хвост на тазе, крылья на верхе позвоночника.
            // Крылья у него растут из рук, но в слот плаща их всё равно не кладём — накидка бы их
            // вытеснила, а без крыльев грифон не грифон. Уши — отдельная часть (04.10.2026,
            // пользователь отделил их от головы в Blender); волос у этой модели нет вовсе, уши —
            // единственное, что прячем при надетом шлеме (см. EarMeshByRace/HideEarsUnderHelmet).
            { "griffon", new[] { "eq_griffon_tail", "eq_griffon_wings", "eq_griffon_ear" } },
            // Гиппогриф (tools/make_hippogriff.py): устроен как грифон — крылья из рук,
            // хвост-веер на тазе.
            { "hippogriff", new[] { "eq_hippogriff_tail", "eq_hippogriff_wings" } },
        };

        // Части тела есть и предметами (equestria_items.xml, слот плаща) — для окон, где агента нет.
        // Смотру рас (EquestriaRaceParty) надо знать их имена, чтобы не выдать хвост вместо накидки.
        internal static bool IsBodyPart(string itemId)
        {
            return itemId != null && PartByRace.Values.Any(parts => parts.Contains(itemId));
        }

        private static Dictionary<int, string[]> _partByRaceId;

        private static Dictionary<int, string[]> RaceParts()
        {
            if (_partByRaceId == null)
            {
                _partByRaceId = new Dictionary<int, string[]>();
                foreach (var pair in PartByRace)
                {
                    int race = TaleWorlds.Core.FaceGen.GetRaceOrDefault(pair.Key);
                    // GetRaceOrDefault отдаёт 0 (человек), если расы нет — такую не путаем с людьми
                    if (race != 0)
                    {
                        _partByRaceId[race] = pair.Value;
                    }
                }
                // Пока новая пони не импортирована в редакторе, у неё нет мешей eq_pony_*, и
                // в игре она ещё прежняя Twilight с её хвостом.
                int pony = TaleWorlds.Core.FaceGen.GetRaceOrDefault("pony");
                if (pony != 0 && MetaMesh.GetCopy("eq_pony_wings", true, false) == null)
                {
                    _partByRaceId[pony] = new[] { "eq_twilight_tail" };
                }
            }
            return _partByRaceId;
        }

        // Какой экран сейчас открыт — нужно только для журнала, чтобы видеть, дошли ли части тела
        // до окна отряда и инвентаря.
        private static string Screen()
        {
            var state = TaleWorlds.Core.Game.Current?.GameStateManager?.ActiveState;
            return state == null ? "нет" : state.GetType().Name;
        }

        // Куда в списке мешей персонажа кладём нашу часть тела. У движка список слотов свой,
        // добавить в него нельзя (BodyMeshTypes — константы). Берём Shoulderpiece: это слот плаща,
        // у пони он обычно пуст, а если плащ всё же надет — хвост сменится плащом, как и раньше.
        private const BodyMeshTypes Slot = BodyMeshTypes.Shoulderpiece;

        /// <summary>
        /// Вешает меш расы на персонажа. Повторный вызов ничего не портит.
        /// </summary>
        /// <param name="visuals">Внешность персонажа (TaleWorlds.MountAndBlade.View.AgentVisuals).</param>
        /// <param name="cacheKey">
        /// Объект, по которому помнится цвет причёски между пересборками (см. LastHairLook). По
        /// умолчанию — сама внешность, но в окнах (см. AfterTableauTick) её пересоздаёт CharacterTableau
        /// при каждой смене снаряжения, а вот сам CharacterTableau — нет, поэтому оттуда передаётся он.
        /// </param>
        /// <param name="bodyCode">
        /// Код внешности персонажа (см. HairLookByCode) — тот же кэш, но переживающий даже совсем
        /// новое окно, открытое сразу со шлемом на голове.
        /// </param>
        // internal, не private: EquestriaHairStyleView зовёт напрямую для экрана барбера —
        // у него свой AgentVisuals (BodyGeneratorView._visualToShow), не через CharacterTableau,
        // и без принудительного тика полосы/сплошная не переключались бы, пока снаряжение
        // не поменяется (замечено 29.09.2026: первый клик на «Полосатая» применился — видимо,
        // совпал с чужим Refresh, — а «Сплошная» после него уже не применялась никогда).
        // Оверрайды ниже — только для рядовых бойцов в бою (RandomizeCommonTroopLook): у них нет
        // своего окна, где игрок жмёт кнопки, поэтому полосы/крылья/хвост/рог решаются случайно
        // на бойца, а не берутся из общих EquestriaHairStyle.Striped/EquestriaPonyBody.*Enabled
        // (те — только для игрока и остаются как есть).
        internal static void Attach(object visuals, int race, string where, object cacheKey = null, string bodyCode = null,
            bool? stripedOverride = null, bool? wingsOverride = null, bool? tailOverride = null, bool? hornOverride = null,
            float? wingsScaleOverride = null, float? tailScaleOverride = null)
        {
            if (visuals == null)
            {
                return;
            }
            bool striped = stripedOverride ?? EquestriaHairStyle.Striped;
            // Шлем подгоняем здесь же: эти точки зовутся и при сборке персонажа, и каждый кадр из
            // окна снаряжения — а опора растяжения должна идти за головой.
            //
            // Настоящая крошечная иконка отряда на карте — единственный случай, где Attach зовётся
            // с именем "создание PartyIcon …" (это имя движок сам даёт объекту внешности при
            // AgentVisuals.Create, см. AfterVisualsCreate). Всё остальное — окна и энциклопедия,
            // ActiveState у них тот же MapState, что и у настоящей карты (это оверлеи поверх неё),
            // поэтому по ActiveState иконку от окна было не отличить — EquestriaHelmetFit прятал
            // шлем и там, каждый кадр, сразу после того как сам же его верно подгонял (замечено
            // 25.09.2026: в логе — успешная подгонка, на экране — пусто).
            bool isMapIcon = where != null && where.IndexOf("PartyIcon", StringComparison.Ordinal) >= 0;
            EquestriaHelmetFit.Fit(visuals, race, isMapIcon);
            // Скрытую причёску-донора заводим ДО того, как красим хвост/крылья/рог ниже: под шлемом
            // скелет пересобирается заново каждый раз, и если завести её после покраски, донора
            // ещё не будет на месте — FindDonor не найдёт цвет именно в этот раз.
            if (HairReferenceByRaceId().TryGetValue(race, out string hairRef))
            {
                EnsureHiddenHairReference(visuals, hairRef, where, cacheKey ?? visuals, bodyCode, striped);
                EnsureHairNotBald(visuals, race, hairRef);
            }
            if (!RaceParts().TryGetValue(race, out string[] meshNames))
            {
                return;
            }
            foreach (string meshName in meshNames)
            {
                // Масштаб крыльев/хвоста — только рядовым бойцам (OnAgentBuild), по суффиксу имени
                // меша, не по расе напрямую: тот же механизм, по просьбе пользователя 07.10.2026
                // сначала для крыльев griffon, потом распространён на все крылатые расы и отдельно
                // на хвост dragon. Рог пробовали так же (dragon/deer) — убрано, см. комментарий
                // у SetPartVisible: кость головы вращается быстро, оверрайд трансформации не
                // поспевает за ней.
                float? scale = null;
                if (meshName.EndsWith("_wings", StringComparison.OrdinalIgnoreCase))
                {
                    scale = wingsScaleOverride;
                }
                else if (meshName.EndsWith("_tail", StringComparison.OrdinalIgnoreCase))
                {
                    scale = tailScaleOverride;
                }
                AttachOne(visuals, meshName, where, striped, scale);
            }
            // Брови у movies.xml остаются человеческими (pony_skins.xml, см. make_pony_race.py —
            // пустой список там валит редактор при создании героя), ставятся в точку человеческого
            // лица и у пони прячутся сами внутри более крупной головы. У оленя (05.10.2026, после
            // правок геометрии головы под моргание) голова там уже не настолько крупнее человеческой
            // — брови/ресницы стали видны. Прячем их тем же SetVisibilityMask(0), что и уши выше,
            // для всех наших рас разом — человеческих бровей не должно быть видно ни у кого из них.
            SetPartVisible(visuals, "male_eyebrow", false);
            SetPartVisible(visuals, "female_eyebrow", false);
            // Временные переключатели "крылья/хвост/рог вкл-выкл" (EquestriaPonyBody) — в лоре
            // MLP не у каждой пони есть все части. Часть всегда крепится и красится, как раньше
            // (выше, в общем цикле) — вкл/выкл это только видимость меша, SetVisibilityMask(0),
            // тот же приём, что и у скрытой причёски-донора под шлемом. Пробовали снимать меш
            // по-настоящему (GameEntity.RemoveComponentWithMesh) — расходится с тем, как его
            // вешает MBAgentVisuals.AddMultiMesh: тот думает, что слот всё ещё занят, и не даёт
            // надеть обратно без переоткрытия окна (замечено 29.09.2026).
            if (EarMeshByRaceId().TryGetValue(race, out string earMesh))
            {
                // Уши прячем под шлемом тем же SetVisibilityMask(0), что и переключатели ниже —
                // только условие не ручное, а "надет ли вообще головной убор" (HasHeadgear).
                SetPartVisible(visuals, earMesh, !HasHeadgear(visuals));
            }
            if (race == DeerRaceId())
            {
                string report = ShowDeerAntlers(visuals, bodyCode);
                if (_deerAttachLogged++ < 12)
                {
                    EquestriaCrashLog.Log($"рога оленихи [{where}]: {report}");
                }
            }
            if (race == PonyRaceId())
            {
                SetPartVisible(visuals, "eq_pony_wings", wingsOverride ?? EquestriaPonyBody.WingsEnabled);
                SetPartVisible(visuals, "eq_pony_tail", tailOverride ?? EquestriaPonyBody.TailEnabled);
                SetPartVisible(visuals, "eq_pony_horn", hornOverride ?? EquestriaPonyBody.HornEnabled);
            }
        }

        private static int _ponyRaceId = -1;

        private static int PonyRaceId()
        {
            if (_ponyRaceId == -1)
            {
                _ponyRaceId = TaleWorlds.Core.FaceGen.GetRaceOrDefault("pony");
            }
            return _ponyRaceId;
        }

        private static int _dragonRaceId = -1;

        private static int DragonRaceId()
        {
            if (_dragonRaceId == -1)
            {
                _dragonRaceId = TaleWorlds.Core.FaceGen.GetRaceOrDefault("dragon");
            }
            return _dragonRaceId;
        }

        // Расы с крыльями — те же PartByRace/RaceParts(), просто отфильтрованные по суффиксу
        // имени меша, чтобы не заводить отдельный список руками (pony, changeling, dragon,
        // griffon, hippogriff — сверено 07.10.2026).
        private static HashSet<int> _wingsRaceIds;

        private static HashSet<int> WingsRaceIds()
        {
            if (_wingsRaceIds == null)
            {
                _wingsRaceIds = new HashSet<int>(RaceParts()
                    .Where(kv => kv.Value.Any(p => p.EndsWith("_wings", StringComparison.OrdinalIgnoreCase)))
                    .Select(kv => kv.Key));
            }
            return _wingsRaceIds;
        }

        // Диапазон случайного масштаба крыльев по расе (см. вызов выше) — по умолчанию (0.5, 1.0),
        // кроме явно перечисленных здесь исключений. dragon — пошире вниз (0.25-1.0), changeling —
        // и вниз, и вверх крупнее стандартного (0.7-1.5, просьба пользователя 07.10.2026).
        private static readonly Dictionary<string, (float Min, float Max)> WingsScaleRangeByRace =
            new Dictionary<string, (float, float)>
        {
            { "dragon", (0.25f, 1f) },
            { "changeling", (0.7f, 1.5f) },
            { "pony", (0.7f, 1.2f) },
            { "hippogriff", (0.3f, 1f) },
        };

        private static Dictionary<int, (float Min, float Max)> _wingsScaleRangeByRaceId;

        private static Dictionary<int, (float Min, float Max)> WingsScaleRangeByRaceId()
        {
            if (_wingsScaleRangeByRaceId == null)
            {
                _wingsScaleRangeByRaceId = new Dictionary<int, (float, float)>();
                foreach (var pair in WingsScaleRangeByRace)
                {
                    int race = TaleWorlds.Core.FaceGen.GetRaceOrDefault(pair.Key);
                    if (race != 0)
                    {
                        _wingsScaleRangeByRaceId[race] = pair.Value;
                    }
                }
            }
            return _wingsScaleRangeByRaceId;
        }

        // Диапазон случайного масштаба хвоста по расе — тот же приём, что у WingsScaleRangeByRace.
        // По умолчанию хвост случайный размер не получает вовсе (расы нет в словаре); dragon —
        // (0.25, 1.0, только вниз), changeling — (0.7, 1.5), как и крылья, просьба 07.10.2026.
        private static readonly Dictionary<string, (float Min, float Max)> TailScaleRangeByRace =
            new Dictionary<string, (float, float)>
        {
            { "dragon", (0.25f, 1f) },
            { "changeling", (0.7f, 1.5f) },
            { "pony", (0.7f, 1.2f) },
            { "hippogriff", (0.3f, 1f) },
        };

        private static Dictionary<int, (float Min, float Max)> _tailScaleRangeByRaceId;

        private static Dictionary<int, (float Min, float Max)> TailScaleRangeByRaceId()
        {
            if (_tailScaleRangeByRaceId == null)
            {
                _tailScaleRangeByRaceId = new Dictionary<int, (float, float)>();
                foreach (var pair in TailScaleRangeByRace)
                {
                    int race = TaleWorlds.Core.FaceGen.GetRaceOrDefault(pair.Key);
                    if (race != 0)
                    {
                        _tailScaleRangeByRaceId[race] = pair.Value;
                    }
                }
            }
            return _tailScaleRangeByRaceId;
        }

        // Случайный размер рога пробовали для dragon и deer (07.10.2026) через ту же рантайм-
        // трансформацию, что крылья/хвост — убрано: рог крепится к кости ГОЛОВЫ, которая
        // вращается быстро и часто, а статичный оверрайд (SetLocalFrame/SetAdditionalBoneFrame)
        // не поспевает за ней кадр-в-кадр при заметном уменьшении (у крыльев/хвоста на костях
        // спины/таза то же самое, но из-за более вялого движения кости незаметно). Если понадобится
        // снова — только готовыми уменьшенными вариантами меша (как разрезанные руки/ноги), не
        // рантайм-скейлом.

        // Части, чьё имя — начало имени другой части той же расы: рога оленихи eq_deer_horn и их
        // варианты eq_deer_horn_2..4 (10.10.2026). Для них сравнение по началу имени задело бы все
        // варианты разом, поэтому — точное имя или копия с точкой (как HideWholePart в
        // EquestriaDismemberment). Остальным оставлено прежнее сравнение по началу: так, например,
        // ищутся человеческие брови male_eyebrow*.
        private static readonly HashSet<string> ExactPartNames =
            new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "eq_deer_horn" };

        internal static bool PartNameMatches(string actual, string meshName)
        {
            if (!actual.StartsWith(meshName, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }
            return !ExactPartNames.Contains(meshName) || actual.Length == meshName.Length
                || actual[meshName.Length] == '.';
        }

        // Рога оленихи: четыре варианта, номер — по причёске (косы eq_deer_hair, eq_deer_hair_2..4,
        // tools/make_pony_race.py DEER_HAIR). Сначала смотрим на надетую косу — это правда даже в
        // окне цирюльника, где код внешности ещё старый. Под шлемом косы нет (движок её не строит),
        // тогда номер причёски берём из кода внешности; без кода — первые рога.
        internal static readonly string[] DeerHornVariants =
            { "eq_deer_horn", "eq_deer_horn_2", "eq_deer_horn_3", "eq_deer_horn_4" };
        private const string DeerHairPrefix = "eq_deer_hair";

        private static int _deerRaceId = -1;
        private static int _deerAttachLogged;

        private static int DeerRaceId()
        {
            if (_deerRaceId == -1)
            {
                _deerRaceId = TaleWorlds.Core.FaceGen.GetRaceOrDefault("deer");
            }
            return _deerRaceId;
        }

        internal static int DeerAntlerVariant(Skeleton skeleton, string bodyCode)
        {
            return DeerAntlerVariant(skeleton, bodyCode, out _);
        }

        internal static int DeerAntlerVariant(Skeleton skeleton, string bodyCode, out string source)
        {
            source = "нет данных";
            var hair = skeleton?.GetAllMeshes().FirstOrDefault(m => m != null && m.Name != null
                && m.VisibilityMask != 0 && m.Name.StartsWith(DeerHairPrefix, StringComparison.OrdinalIgnoreCase));
            if (hair != null)
            {
                source = "коса " + hair.Name;
                string tail = hair.Name.Substring(DeerHairPrefix.Length);
                if (tail.Length >= 2 && tail[0] == '_' && char.IsDigit(tail[1]))
                {
                    int n = tail[1] - '0';
                    if (n >= 1 && n <= DeerHornVariants.Length)
                    {
                        return n - 1;
                    }
                }
                return 0;
            }
            if (!string.IsNullOrEmpty(bodyCode) && BodyProperties.FromString(bodyCode, out BodyProperties body))
            {
                try
                {
                    var face = FaceGenerationParams.Create();
                    MBBodyProperties.GetParamsFromKey(ref face, body, false, false);
                    source = "причёска №" + face.CurrentHair;
                    // 0 — «лысая» запись списка, дальше косы по кругу (см. DEER_HAIR)
                    return face.CurrentHair <= 0 ? 0 : (face.CurrentHair - 1) % DeerHornVariants.Length;
                }
                catch (Exception e)
                {
                    EquestriaCrashLog.Warn("рога оленихи: номер причёски не прочитан — " + e.Message);
                }
            }
            return 0;
        }

        /// <returns>Строка для лога: откуда взят номер и сколько мешей каждого варианта нашлось.</returns>
        private static string ShowDeerAntlers(object visuals, string bodyCode)
        {
            var entity = AccessTools.Method(visuals.GetType(), "GetEntity")?.Invoke(visuals, null) as GameEntity;
            var skeleton = entity?.Skeleton;
            if (skeleton == null)
            {
                return "нет скелета";
            }
            int chosen = DeerAntlerVariant(skeleton, bodyCode, out string source);
            for (int i = 0; i < DeerHornVariants.Length; i++)
            {
                SetPartVisible(visuals, DeerHornVariants[i], i == chosen);
            }
            var meshes = skeleton.GetAllMeshes().Where(m => m != null && m.Name != null).ToList();
            string found = string.Join(", ", DeerHornVariants.Select(v =>
                v.Substring("eq_deer_".Length) + ":" + meshes.Count(m => PartNameMatches(m.Name, v))
                + "/" + meshes.Count(m => PartNameMatches(m.Name, v) && m.VisibilityMask != 0)));
            return $"рога {chosen + 1} ({source}); мешей всего/видно — {found}";
        }

        // Бой: при OnAgentBuild меши частей и шлем у агента ещё не всегда на месте (тот же
        // тайминг, что у причёски яка, см. HideBaldHairUnderConfirmedHelmet), поэтому рога
        // оленихи выбираются ещё раз чуть позже — через DeerLateFrames кадров после сборки.
        private const int DeerLateFrames = 20;
        private readonly Dictionary<Agent, int> _deerPending = new Dictionary<Agent, int>();
        private int _deerLogged;

        internal static void SetPartVisible(object visuals, string meshName, bool visible)
        {
            var entity = AccessTools.Method(visuals.GetType(), "GetEntity")?.Invoke(visuals, null) as GameEntity;
            var skeleton = entity?.Skeleton;
            if (skeleton == null)
            {
                return;
            }
            foreach (var mesh in skeleton.GetAllMeshes().Where(m => m != null && m.Name != null
                && PartNameMatches(m.Name, meshName)))
            {
                mesh.SetVisibilityMask(visible ? VisibilityMaskFlags.DefaultDynamic : 0);
            }
        }

        // Раса -> любая её причёска, что красится цветом волос (одной хватает, чтобы всегда было
        // с кого списывать цвет хвоста/крыльев/рога, даже под шлемом) — и она же причёска по
        // умолчанию, которую включаем назад, если игрок выбрал "лысую" (см. HairVariantsByRace
        // и EnsureHairNotBald ниже).
        private static readonly Dictionary<string, string> HairReferenceByRace =
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            { "pony", "eq_pony_hair" },
            // griffon и hippogriff сюда намеренно не входят: у пересобранных 04.10.2026 моделей
            // волос как таковых больше нет вовсе (у griffon есть уши — см. EarMeshByRace; у
            // hippogriff нет даже ушей отдельно), ссылка на eq_*_hair стала бы мёртвой. changeling
            // (05.10.2026) — прядевые гривы отключили, слишком похожи на человеческие причёски.
            { "dragon", "eq_dragon_hair" },
            { "yak", "eq_yak_hair" },
            { "deer", "eq_deer_hair" },
        };

        // Раса -> ВСЕ меши причёски, которые скин считает валидным выбором (pony_skins.xml,
        // hair_mesh). У каждой оставшейся здесь расы вариант только один — скин подсовывает его на
        // любую позицию в списке причёсок, поэтому лысой выбрать физически нечего.
        private static readonly Dictionary<string, string[]> HairVariantsByRace =
            new Dictionary<string, string[]>(StringComparer.OrdinalIgnoreCase)
        {
            { "pony", new[] { "eq_pony_hair" } },
            { "dragon", new[] { "eq_dragon_hair" } },
            { "yak", new[] { "eq_yak_hair" } },
            { "deer", new[] { "eq_deer_hair", "eq_deer_hair_2", "eq_deer_hair_3", "eq_deer_hair_4" } },
        };

        // Раса -> меш, который прячем при надетом шлеме любого вида (см. HasHeadgear). Изначально
        // только уши (griffon/changeling/deer — волос у них нет, единственное, что требует скрытия
        // под шлемом), но приём тот же для любой части на голове: дракон (06.10.2026, по просьбе
        // пользователя) прячет сюда рог — тот тоже крепится как обычно (RaceParts выше), сюда
        // заходит только ради прятки под шлемом.
        private static readonly Dictionary<string, string> EarMeshByRace =
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            { "griffon", "eq_griffon_ear" },
            { "changeling", "eq_changeling_ears" },
            { "deer", "eq_deer_ears" },
            { "dragon", "eq_dragon_horn" },
            { "pony", "eq_pony_ears" },
        };

        private static Dictionary<int, string> _earMeshByRaceId;

        private static Dictionary<int, string> EarMeshByRaceId()
        {
            if (_earMeshByRaceId == null)
            {
                _earMeshByRaceId = new Dictionary<int, string>();
                foreach (var pair in EarMeshByRace)
                {
                    int race = TaleWorlds.Core.FaceGen.GetRaceOrDefault(pair.Key);
                    if (race != 0)
                    {
                        _earMeshByRaceId[race] = pair.Value;
                    }
                }
            }
            return _earMeshByRaceId;
        }

        private static Dictionary<int, string> _hairReferenceByRaceId;

        private static Dictionary<int, string> HairReferenceByRaceId()
        {
            if (_hairReferenceByRaceId == null)
            {
                _hairReferenceByRaceId = new Dictionary<int, string>();
                foreach (var pair in HairReferenceByRace)
                {
                    int race = TaleWorlds.Core.FaceGen.GetRaceOrDefault(pair.Key);
                    if (race != 0)
                    {
                        _hairReferenceByRaceId[race] = pair.Value;
                    }
                }
            }
            return _hairReferenceByRaceId;
        }

        private static Dictionary<int, string[]> _hairVariantsByRaceId;

        private static Dictionary<int, string[]> HairVariantsByRaceId()
        {
            if (_hairVariantsByRaceId == null)
            {
                _hairVariantsByRaceId = new Dictionary<int, string[]>();
                foreach (var pair in HairVariantsByRace)
                {
                    int race = TaleWorlds.Core.FaceGen.GetRaceOrDefault(pair.Key);
                    if (race != 0)
                    {
                        _hairVariantsByRaceId[race] = pair.Value;
                    }
                }
            }
            return _hairVariantsByRaceId;
        }

        // "Лысая" причёска — это когда игрок в редакторе выбрал вариант, которого у расы нет
        // (движок просто ничего не показывает на этом слоте). У нас же причёска — часть расы, а не
        // съёмный предмет, поэтому лысых быть не должно вовсе: если НИ ОДИН известный вариант
        // причёски расы не виден на скелете — включаем запасной (HairReferenceByRace) обратно,
        // тем же SetVisibilityMask, что и переключатель крыльев/хвоста/рога у пони (см. SetPartVisible).
        //
        // ВАЖНО (04.10.2026): под закрытым шлемом движок сам прячет причёску (hair_cover_type у
        // шлема) — это не лысина, а нормальная посадка шлема, и форсировать причёску обратно нельзя,
        // иначе она торчит сквозь шлем (замечено в игре). Поэтому при надетом головном уборе эта
        // проверка вообще не выполняется — его прикрытие молчаливо считается законным.
        private static void EnsureHairNotBald(object visuals, int race, string defaultHairRef)
        {
            if (!HairVariantsByRaceId().TryGetValue(race, out string[] variants) || variants.Length == 0)
            {
                return;
            }
            if (HasHeadgear(visuals))
            {
                return;
            }
            var entity = AccessTools.Method(visuals.GetType(), "GetEntity")?.Invoke(visuals, null) as GameEntity;
            var skeleton = entity?.Skeleton;
            if (skeleton == null)
            {
                return;
            }
            var meshes = skeleton.GetAllMeshes().Where(m => m != null && m.Name != null).ToList();
            bool anyVisible = meshes.Any(m => m.VisibilityMask != 0
                && variants.Any(v => m.Name.StartsWith(v, StringComparison.OrdinalIgnoreCase)));
            if (anyVisible)
            {
                return;
            }
            foreach (var mesh in meshes.Where(m => m.Name.StartsWith(defaultHairRef, StringComparison.OrdinalIgnoreCase)))
            {
                mesh.SetVisibilityMask(VisibilityMaskFlags.DefaultDynamic);
            }
        }

        // Подчистка гонки таймингов (05.10.2026): OnAgentBuild зовёт Attach ОДИН раз при спавне
        // агента в бою, и HasHeadgear там смотрит на GetCopyAgentVisualsData — в этот самый такт
        // она иногда ещё не содержит только что надетый шлем (замечено на яке: шлем на голове,
        // а причёска всё равно включена поверх него до конца боя — EnsureHairNotBald один раз
        // ошибочно решил "лысый" и подняла видимость гривы, второй раз уже не зовётся).
        // EquestriaHelmetFit.Fit(Agent) знает шлем из agent.SpawnEquipment — источник, который
        // не гонится ни с чем — и зовёт этот метод, когда впервые (или заново) опознаёт шлем на
        // агенте. Прячем всё, что EnsureHairNotBald могла успеть включить по ошибке.
        // Тот же приём и по той же причине, что у HideBaldHairUnderConfirmedHelmet (см. там): уши
        // тоже решаются один раз при OnAgentBuild по менее надёжному снимку (HasHeadgear внутри
        // Attach) и в бою иногда остаются видны под шлемом (замечено в игре 07.10.2026 — в окне
        // инвентаря верно, в бою нет). Здесь шлем уже подтверждён надёжным agent.SpawnEquipment —
        // прячем уши без условий, раз этот код и так выполняется только когда шлем точно есть.
        internal static void HideEarsUnderConfirmedHelmet(object visuals, int race)
        {
            if (EarMeshByRaceId().TryGetValue(race, out string earMesh))
            {
                SetPartVisible(visuals, earMesh, false);
            }
        }

        internal static void HideBaldHairUnderConfirmedHelmet(object visuals, int race)
        {
            if (!HairVariantsByRaceId().TryGetValue(race, out string[] variants) || variants.Length == 0)
            {
                return;
            }
            var entity = AccessTools.Method(visuals.GetType(), "GetEntity")?.Invoke(visuals, null) as GameEntity;
            var skeleton = entity?.Skeleton;
            if (skeleton == null)
            {
                return;
            }
            foreach (var mesh in skeleton.GetAllMeshes())
            {
                if (mesh == null || mesh.Name == null || mesh.VisibilityMask == 0)
                {
                    continue;
                }
                if (variants.Any(v => mesh.Name.StartsWith(v, StringComparison.OrdinalIgnoreCase)))
                {
                    mesh.SetVisibilityMask(0);
                }
            }
        }

        // Тот же приём, что у EquestriaHelmetFit.HideEquippedHelmet: смотрим слот головы через
        // копию данных внешности, а не через Agent — Attach зовётся и там, где агента нет
        // (окна, цирюльник). Любой непустой головной убор (не только шлем — капюшон, шапка и т.п.)
        // учитывается: причина спрятанной причёски нас не касается, лишь бы не чинить то, что не
        // сломано.
        private static bool HasHeadgear(object visuals)
        {
            var getData = AccessTools.Method(visuals.GetType(), "GetCopyAgentVisualsData");
            var data = getData?.Invoke(visuals, null);
            if (data == null)
            {
                return false;
            }
            var equipment = AccessTools.Property(data.GetType(), "EquipmentData")?.GetValue(data) as Equipment;
            string meshName = equipment?[EquipmentIndex.Head].Item?.MultiMeshName;
            return !string.IsNullOrEmpty(meshName);
        }

        private sealed class HairLook
        {
            public uint Color;
            public uint Color2;
            public float Ax, Ay, Az, Aw, Bx, By, Bz, Bw;
        }

        // По логу выяснилось (28.09.2026): в тот же такт, когда шлем прячет настоящую гриву,
        // движок сам чистит список мешей на скелете (готовит новое снаряжение) — вместе с гривой
        // пропадает и наша скрытая копия-донор, а новая копия рождается в этот же такт уже без
        // всякого живого цвета рядом (цвет скрытой в логе — FFFFFFFF, ровно как у свежей
        // некрашеной копии). Поэтому одной скрытой копии мало — нужен цвет, переживающий сам
        // такт пересборки. Держим его снаружи скелета — но и не по самой внешности (visuals):
        // в окнах её тоже пересоздаёт CharacterTableau при смене снаряжения (тот же лог: цвет
        // писался в кэш по visuals за 70 мс до сброса, а на сбросе TryGetValue по НОВОМУ visuals
        // уже ничего не нашёл). Ключ передаёт вызывающая сторона (cacheKey в Attach) — то, что
        // переживает пересборку внешности, у окон это сам CharacterTableau.
        private static readonly System.Runtime.CompilerServices.ConditionalWeakTable<object, HairLook> LastHairLook =
            new System.Runtime.CompilerServices.ConditionalWeakTable<object, HairLook>();

        // Тот же кэш, но по коду внешности персонажа (BodyProperties, см. AfterTableauTick):
        // переживает даже совсем новое окно, а не только пересборку внутри одного. Нужен, когда
        // окно открывается сразу со шлемом на голове — своя причёска в нём не строится ни разу,
        // и cacheKey (сам CharacterTableau) ничего не запомнит просто потому, что нечего было
        // запоминать. А вот код внешности у персонажа один и тот же во всех окнах, и если причёску
        // хоть где-то уже видели (например, в редакторе персонажа, там шлема не бывает) — цвет
        // найдётся и тут.
        private static readonly Dictionary<string, HairLook> HairLookByCode = new Dictionary<string, HairLook>();

        // Кэш выше жил только в памяти текущего сеанса: у бойца, чья голова закрыта с самого
        // появления, движок ни разу не строит настоящую гриву — подсмотреть цвет неоткуда, и
        // рог/хвост оставались белыми в каждом новом бою (замечено 29.09.2026, лучник в капюшоне
        // верхом). Прочитать цвет из данных напрямую нельзя — декомпиляция TaleWorlds.Core.dll
        // показала, что IFaceGen отдаёt только запись (SetPigmentation), без чтения назад. Поэтому
        // сохраняем сам кэш: один раз увиденный цвет (в редакторе, цирюльне, инвентаре — там, где
        // голова открыта) переживает и новые бои, и перезапуск игры. Зовёт EquestriaHairStyle.
        // SyncData — сам EquestriaBodyParts MissionBehavior, у него SyncData нет.
        public static void SyncHairLookCache(IDataStore dataStore)
        {
            List<string> keys = null;
            List<string> values = null;
            if (dataStore.IsSaving)
            {
                keys = HairLookByCode.Keys.ToList();
                values = keys.Select(k => EncodeHairLook(HairLookByCode[k])).ToList();
            }
            dataStore.SyncData("eq_hair_look_keys", ref keys);
            dataStore.SyncData("eq_hair_look_values", ref values);
            if (!dataStore.IsSaving && keys != null && values != null && keys.Count == values.Count)
            {
                HairLookByCode.Clear();
                for (int i = 0; i < keys.Count; i++)
                {
                    if (TryDecodeHairLook(values[i], out HairLook look))
                    {
                        HairLookByCode[keys[i]] = look;
                    }
                }
            }
        }

        private static string EncodeHairLook(HairLook look)
        {
            return string.Join("|", new[]
            {
                look.Color.ToString(CultureInfo.InvariantCulture),
                look.Color2.ToString(CultureInfo.InvariantCulture),
                look.Ax.ToString(CultureInfo.InvariantCulture), look.Ay.ToString(CultureInfo.InvariantCulture),
                look.Az.ToString(CultureInfo.InvariantCulture), look.Aw.ToString(CultureInfo.InvariantCulture),
                look.Bx.ToString(CultureInfo.InvariantCulture), look.By.ToString(CultureInfo.InvariantCulture),
                look.Bz.ToString(CultureInfo.InvariantCulture), look.Bw.ToString(CultureInfo.InvariantCulture),
            });
        }

        private static bool TryDecodeHairLook(string encoded, out HairLook look)
        {
            look = null;
            var parts = encoded?.Split('|');
            if (parts == null || parts.Length != 10)
            {
                return false;
            }
            if (!uint.TryParse(parts[0], NumberStyles.Integer, CultureInfo.InvariantCulture, out uint color)
                || !uint.TryParse(parts[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out uint color2))
            {
                return false;
            }
            var f = new float[8];
            for (int i = 0; i < 8; i++)
            {
                if (!float.TryParse(parts[i + 2], NumberStyles.Float, CultureInfo.InvariantCulture, out f[i]))
                {
                    return false;
                }
            }
            look = new HairLook
            {
                Color = color, Color2 = color2,
                Ax = f[0], Ay = f[1], Az = f[2], Aw = f[3],
                Bx = f[4], By = f[5], Bz = f[6], Bw = f[7],
            };
            return true;
        }

        private static void EnsureHiddenHairReference(object visuals, string meshName, string where,
            object cacheKey, string bodyCode, bool striped)
        {
            var entity = AccessTools.Method(visuals.GetType(), "GetEntity")?.Invoke(visuals, null) as GameEntity;
            var skeleton = entity?.Skeleton;
            if (skeleton == null)
            {
                return;
            }
            var candidates = skeleton.GetAllMeshes()
                .Where(m => m != null && m.Name != null
                            && m.Name.StartsWith(meshName, StringComparison.OrdinalIgnoreCase)).ToList();
            var visible = candidates.FirstOrDefault(m => m.VisibilityMask != 0);
            var hidden = candidates.FirstOrDefault(m => m.VisibilityMask == 0);
            if (hidden == null)
            {
                var mesh = MetaMesh.GetCopy(meshName, true, false);
                if (mesh == null)
                {
                    EquestriaCrashLog.Log($"причёска[{where} / {Screen()}]: {meshName} не скопирован — MetaMesh.GetCopy вернул null");
                    return;
                }
                for (int i = 0; i < mesh.MeshCount; i++)
                {
                    mesh.GetMeshAtIndex(i)?.SetVisibilityMask(0);
                }
                var mbVisuals = AccessTools.Method(visuals.GetType(), "GetVisuals")?.Invoke(visuals, null)
                    as MBAgentVisuals;
                if (mbVisuals != null)
                {
                    mbVisuals.AddMultiMesh(mesh, Slot);
                }
                else
                {
                    var frame = entity.GetFrame();
                    entity.AddMultiMeshToSkeleton(mesh);
                    entity.SetFrame(ref frame);
                }
                hidden = skeleton.GetAllMeshes().FirstOrDefault(m => m != null && m.Name != null
                    && m.Name.StartsWith(meshName, StringComparison.OrdinalIgnoreCase) && m.VisibilityMask == 0);
            }
            if (visible != null)
            {
                // Сама причёска (грива) — не часть тела, Tint() её не красит; переключаем материал
                // прямо тут, раз уж мы и так каждый раз находим видимую причёску.
                if (EquestriaHairStyle.StripeMaterialByMesh.TryGetValue(meshName, out string maneStripe))
                {
                    string wantName = striped ? maneStripe : EquestriaHairStyle.PlainMaterial;
                    var wantMat = Material.GetFromResource(wantName);
                    var ownMat = visible.GetMaterial();
                    if (wantMat != null && (ownMat == null || ownMat.Name != wantMat.Name))
                    {
                        visible.SetMaterial(wantMat);
                    }
                }
                var arg = visible.GetVectorArgument();
                var arg2 = visible.GetVectorArgument2();
                var look = new HairLook
                {
                    Color = visible.Color, Color2 = visible.Color2,
                    Ax = arg.x, Ay = arg.y, Az = arg.z, Aw = arg.w,
                    Bx = arg2.x, By = arg2.y, Bz = arg2.z, Bw = arg2.w,
                };
                LastHairLook.Remove(cacheKey);
                LastHairLook.Add(cacheKey, look);
                if (!string.IsNullOrEmpty(bodyCode))
                {
                    if (HairLookByCode.Count > 500)
                    {
                        HairLookByCode.Clear();
                    }
                    HairLookByCode[bodyCode] = look;
                }
                if (hidden != null)
                {
                    hidden.Color = look.Color;
                    hidden.Color2 = look.Color2;
                    hidden.SetVectorArgument(look.Ax, look.Ay, look.Az, look.Aw);
                    hidden.SetVectorArgument2(look.Bx, look.By, look.Bz, look.Bw);
                }
            }
            else if (hidden != null)
            {
                HairLook look = null;
                if (string.IsNullOrEmpty(bodyCode) || !HairLookByCode.TryGetValue(bodyCode, out look))
                {
                    LastHairLook.TryGetValue(cacheKey, out look);
                }
                if (look != null)
                {
                    hidden.Color = look.Color;
                    hidden.Color2 = look.Color2;
                    hidden.SetVectorArgument(look.Ax, look.Ay, look.Az, look.Aw);
                    hidden.SetVectorArgument2(look.Bx, look.By, look.Bz, look.Bw);
                }
            }
        }

        /// <summary>
        /// Надеть один меш на уже собранного персонажа. Нужна шлему: на карте мира он прячется,
        /// а причёску игра под ним не строит — её приходится возвращать отдельно.
        /// Повторный вызов ничего не портит: меш, который уже висит, не удваивается.
        /// </summary>
        public static void AttachPart(object visuals, string meshName, string where)
        {
            if (visuals != null && !string.IsNullOrEmpty(meshName))
            {
                AttachOne(visuals, meshName, where, EquestriaHairStyle.Striped);
            }
        }

        private static void AttachOne(object visuals, string meshName, string where, bool striped, float? scale = null)
        {
            var entity = AccessTools.Method(visuals.GetType(), "GetEntity")?.Invoke(visuals, null) as GameEntity;
            if (entity == null)
            {
                return;
            }
            // Экраны обновляют персонажа на каждый чих — иначе хвосты копились бы друг на друге.
            // Но окраску при этом обновляем: цвет кожи игрок меняет прямо в окне, и уже надетый
            // хвост должен перекраситься вместе с телом.
            var skeleton = entity.Skeleton;
            var already = skeleton == null ? null : skeleton.GetAllMeshes()
                .Where(m => m != null && m.Name != null && PartNameMatches(m.Name, meshName)).ToList();
            if (already != null && already.Count > 0)
            {
                Tint(already, skeleton, meshName, where, striped);
                return;
            }
            var mesh = MetaMesh.GetCopy(meshName, true, false);
            if (mesh == null)
            {
                return;
            }
            Tint(mesh, skeleton, meshName, where, striped);
            if (scale.HasValue)
            {
                ApplyUniformScale(mesh, scale.Value);
            }
            // Просто положить меш в скелет объекта (GameEntity.AddMultiMeshToSkeleton) мало: в бою
            // так работает, а в окнах отряда и снаряжения персонажа рисует отдельная система
            // (agent renderer), и меш, о котором она не знает, не попадает в кадр. Поэтому отдаём
            // меш самой внешности — MBAgentVisuals.AddMultiMesh: она и в бою, и в окнах одна.
            var mbVisuals = AccessTools.Method(visuals.GetType(), "GetVisuals")?.Invoke(visuals, null)
                as MBAgentVisuals;
            if (mbVisuals != null)
            {
                mbVisuals.AddMultiMesh(mesh, Slot);
            }
            else
            {
                var frame = entity.GetFrame();
                entity.AddMultiMeshToSkeleton(mesh);
                entity.SetFrame(ref frame);
            }
        }

        // Уменьшает меш вокруг его геометрического центра (bounding box) — подходит для крыльев
        // и хвоста (кости спины/таза вращаются вяло, рассинхрон незаметен). Для рога (кость
        // головы, вращается быстро) этот же приём пробовали и убрали — см. комментарий
        // у SetPartVisible.
        private static void ApplyUniformScale(MetaMesh mesh, float scale)
        {
            Vec3 center = mesh.GetBoundingBox().center;
            MatrixFrame frame = MatrixFrame.Identity;
            frame.rotation.ApplyScaleLocal(scale);
            frame.origin = center * (1f - scale);

            for (int i = 0; i < mesh.MeshCount; i++)
            {
                mesh.GetMeshAtIndex(i)?.SetLocalFrame(frame);
            }
        }

        // ---------------------------------------------------------------- окраска
        // Цвет кожи движок раздаёт мешам тела сам, когда собирает персонажа по его внешности.
        // Наши хвост и крылья добавляются мимо этой сборки и остаются белыми, поэтому окраску
        // просто списываем с уже одетого меша той же расы: цвет, второй цвет и оба векторных
        // аргумента материала. Донора ищем по общему началу имени (eq_dragon_tail -> eq_dragon_),
        // но не у самих себя — иначе списали бы белизну с соседнего крыла.
        private static readonly string[] DonorOrder = { "body", "legs", "gloves", "head" };

        // Части, которые красятся цветом ПРИЧЁСКИ, а не кожи: у пони хвост идёт в цвет гривы
        // (выбор цвета волос в окне внешности). Цвет берём у меша причёски на том же скелете;
        // материал у этих частей — волосяной (tools/pony_material.ps1), иначе шейдер кожи цвет
        // волос не читает.
        // Крылья и рог сюда НЕ входят: по лору MLP они цвета тела, а не гривы (крылья проверены
        // 29.09.2026, рог — 30.09.2026). Без записи здесь они попадают в обычную ветку Tint() и
        // красятся, как обычная часть тела (цвет и материал — с ближайшего донора
        // body/legs/gloves; материал донора копируется целиком, так что волосяной шейдер им не
        // нужен, даже если сам меш экспортирован с ним).
        // Часть -> начало имени меша причёски, у которого берётся цвет (у чейнджлингов четыре
        // гривы eq_hair_chrysalis_*, у пони одна eq_pony_hair).
        private static readonly Dictionary<string, string> HairTinted =
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            { "eq_pony_tail", "eq_pony_hair" },
            { "eq_changeling_wings", "eq_hair_chrysalis" }, { "eq_changeling_tail", "eq_hair_chrysalis" },
        };

        private static Mesh FindDonor(Skeleton skeleton, string meshName)
        {
            int cut = meshName.LastIndexOf('_');
            if (skeleton == null || cut <= 0)
            {
                return null;
            }
            string prefix = meshName.Substring(0, cut + 1);
            if (HairTinted.TryGetValue(meshName, out string hairPrefix))
            {
                var hair = skeleton.GetAllMeshes().FirstOrDefault(m => m != null && m.Name != null
                    && m.Name.StartsWith(hairPrefix, StringComparison.OrdinalIgnoreCase));
                if (hair != null)
                {
                    return hair;
                }
            }
            var mine = RaceParts().Values.SelectMany(v => v).ToArray();
            var meshes = skeleton.GetAllMeshes()
                .Where(m => m != null && m.Name != null
                            && m.Name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)
                            && !mine.Any(n => m.Name.StartsWith(n, StringComparison.OrdinalIgnoreCase)))
                .ToList();
            // Голова идёт последней: у неё бывает своя лицевая текстура, и материал с неё брать нельзя
            foreach (string kind in DonorOrder)
            {
                var found = meshes.FirstOrDefault(m =>
                    m.Name.StartsWith(prefix + kind, StringComparison.OrdinalIgnoreCase));
                if (found != null)
                {
                    return found;
                }
            }
            return meshes.FirstOrDefault();
        }

        private static void Tint(IEnumerable<Mesh> targets, Skeleton skeleton, string meshName, string where, bool striped)
        {
            var donor = FindDonor(skeleton, meshName);
            bool fromHair = donor != null && donor.Name != null
                && donor.Name.IndexOf("_hair", StringComparison.OrdinalIgnoreCase) >= 0;
            if (donor == null)
            {
                return;
            }
            uint colour = donor.Color;
            uint colour2 = donor.Color2;
            var arg = donor.GetVectorArgument();
            var arg2 = donor.GetVectorArgument2();
            var material = donor.GetMaterial();
            // Полосатая грива — отдельный материал (у Color2 в шейдере волос нет видимого эффекта,
            // проверено в игре 29.09.2026), а не второй цвет. Переключаем его сами, по сохранённому
            // выбору игрока (EquestriaHairStyle), а не по тому, что донор — материал донора тут не
            // подходит: до этой части донор просто отдаёт цвет, а не свою заливку/полосы.
            Material wantHairMaterial = null;
            if (fromHair && EquestriaHairStyle.StripeMaterialByMesh.TryGetValue(meshName, out string stripeMat))
            {
                string wantName = striped ? stripeMat : EquestriaHairStyle.PlainMaterial;
                wantHairMaterial = Material.GetFromResource(wantName);
            }
            foreach (var target in targets)
            {
                if (target == null)
                {
                    continue;
                }
                target.Color = colour;
                target.Color2 = colour2;
                target.SetVectorArgument(arg.x, arg.y, arg.z, arg.w);
                target.SetVectorArgument2(arg2.x, arg2.y, arg2.z, arg2.w);
                var own = target.GetMaterial();
                if (wantHairMaterial != null)
                {
                    if (own == null || own.Name != wantHairMaterial.Name)
                    {
                        target.SetMaterial(wantHairMaterial);
                    }
                }
                // Материал берём только если движок выдал телу свой, отличный от нашего: так
                // приходит окраска, запечённая в материал персонажа.
                else if (!fromHair && material != null && own != null && material.Name != own.Name)
                {
                    target.SetMaterial(material);
                }
            }
        }

        private static void Tint(MetaMesh mesh, Skeleton skeleton, string meshName, string where, bool striped)
        {
            var list = new List<Mesh>();
            for (int i = 0; i < mesh.MeshCount; i++)
            {
                list.Add(mesh.GetMeshAtIndex(i));
            }
            Tint(list, skeleton, meshName, where, striped);
        }

        // ---------------------------------------------------------------- миссия
        // Шлем в бою: одной подгонки при сборке мало. Во-первых, в миссии персонажа собирает не
        // тот путь, что в окнах (в бою шлем оставался стандартным). Во-вторых, опора растяжения —
        // ТЕКУЩЕЕ положение кости головы, а в бою голова всё время движется, поэтому пересчитываем
        // каждый кадр. Считаем только для рас со своим размером шлема — их единицы.
        // Вблизи пересчитываем каждый кадр, дальше — реже, чтобы не считать на тысячу бойцов разом.
        // Было 25 м / раз в 15 кадров (~250 мс при 60 fps) — пока подгонка сама была рассинхронизирована
        // (нераспознанный поворот shift/pivot, см. EquestriaHelmetFit.Fit), рывки на этом фоне были не
        // так заметны. После починки вращения шлем идеально следует за головой каждый кадр — и рывки
        // раз в 15 кадров стали отчётливо видны («мелькает», замечено 03.10.2026). Сократили разрыв
        // (4 кадра — не более ~66 мс при 60 fps, почти незаметно) и чуть подняли ближний радиус.
        private const float CloseUp = 30f;     // метров: тут считаем каждый кадр
        private const int FarEvery = 4;        // дальше — раз в столько кадров
        private int _frame;

        public override void OnPreDisplayMissionTick(float dt)
        {
            if (Mission.Current == null)
            {
                return;
            }
            _frame++;
            if (_deerPending.Count > 0)
            {
                foreach (var agent in _deerPending.Keys.ToList())
                {
                    int left = _deerPending[agent] - 1;
                    if (left > 0)
                    {
                        _deerPending[agent] = left;
                        continue;
                    }
                    _deerPending.Remove(agent);
                    if (agent == null || !agent.IsActive() || agent.AgentVisuals == null)
                    {
                        continue;
                    }
                    var visuals = agent.AgentVisuals;
                    string bodyCode = agent.BodyPropertiesValue.ToString();
                    EquestriaCrashLog.Try("рога оленихи позже", () =>
                    {
                        string report = ShowDeerAntlers(visuals, bodyCode);
                        if (_deerLogged++ < 12)
                        {
                            EquestriaCrashLog.Log($"рога оленихи [{agent.Name}] спустя {DeerLateFrames} кадров: {report}");
                        }
                    });
                }
            }
            Vec3 eye = Mission.Current.Scene != null
                ? Mission.Current.Scene.LastFinalRenderCameraPosition
                : Vec3.Zero;
            foreach (var agent in Mission.Current.Agents)
            {
                if (agent == null || agent.IsMount || agent.Character == null)
                {
                    continue;
                }
                if (eye.DistanceSquared(agent.VisualPosition) > CloseUp * CloseUp
                    && (_frame + agent.Index) % FarEvery != 0)
                {
                    continue;
                }
                EquestriaHelmetFit.Fit(agent);
            }
        }

        public override void OnAgentBuild(Agent agent, Banner banner)
        {
            EquestriaCrashLog.Try("части тела в миссии", () =>
            {
                if (agent == null || agent.IsMount || agent.Character == null)
                {
                    return;
                }
                // Тот же код внешности, что и в окнах (см. AfterTableauTick) — своя причёска под
                // шлемом в бою тоже не строится, а игрок почти всегда уже открывал редактор или
                // инвентарь до боя, так что цвет в общем кэше HairLookByCode обычно уже есть.
                string bodyCode = agent.BodyPropertiesValue.ToString();
                int race = agent.Character.Race;
                if (race == DeerRaceId())
                {
                    _deerPending[agent] = DeerLateFrames;
                }
                bool? striped = null, wings = null, tail = null, horn = null;
                uint? skinColor = null, hairColor = null;
                // Игрока не трогаем — его цвет выбран самим игроком в редакторе персонажа и уже
                // идёт верно через обычную пигментацию движка. Рядовые бойцы и герои (в т.ч. лорды,
                // ПОЧЕМУ они раньше были все белые — см. LoreColor) красятся нашим кодом: общий
                // шаблон внешности лордов (BodyProperty.fighter_empire_tall, без Min/Max-разброса)
                // у всех пони-лордов отдаёт один и тот же немасштабированный цвет пигментации.
                bool isPlayer = Hero.MainHero != null && agent.Character == Hero.MainHero.CharacterObject;
                if (race == PonyRaceId() && !isPlayer)
                {
                    if (!agent.Character.IsHero)
                    {
                        RandomizeCommonTroopLook(agent, out bool s, out bool w, out bool t, out bool h,
                            out uint skin, out uint hair);
                        striped = s; wings = w; tail = t; horn = h;
                        skinColor = skin; hairColor = hair;
                    }
                    else
                    {
                        LoreColor(agent.Character.StringId, out uint skin, out uint hair);
                        skinColor = skin; hairColor = hair;
                    }
                }
                // У dragon нет случайной покраски вовсе (ApplyPonyColors ей никогда не звалась) —
                // база всегда одна и та же текстура (eq_dragon_body_d, сама по себе почти белая,
                // под тонирование — не лор, а просто недоделанная покраска), окрашена не нами,
                // а обычной движковой пигментацией BodyProperties, отсюда и "в основном ярко
                // зелёные и голубые" (замечено пользователем 07.10.2026). ApplyPonyColors/
                // RandomPonyPalette/LoreColor уже общие по коду (ключ — race), нужно было только
                // позвать их и для dragon, как у пони. Свой множитель ГСЧ (ещё один большой
                // простой на agent.Index) — не совпадает ни с одним из масштабов крыльев/хвоста/рога.
                else if (race == DragonRaceId() && !isPlayer)
                {
                    if (!agent.Character.IsHero)
                    {
                        var rng = new Random(unchecked(agent.Index * 32452867 + (Mission.Current?.GetHashCode() ?? 0)));
                        RandomPonyPalette(rng, out uint skin, out uint hair);
                        skinColor = skin; hairColor = hair;
                    }
                    else
                    {
                        LoreColor(agent.Character.StringId, out uint skin, out uint hair);
                        skinColor = skin; hairColor = hair;
                    }
                }
                // Случайный размер крыльев у рядовых бойцов любой крылатой расы (по просьбе
                // пользователя 07.10.2026, сначала только griffon, затем распространено на всех) —
                // диапазон по умолчанию (0.5, 1.0), у dragon (0.25, 1.0), у changeling — ещё и
                // крупнее стандартного (0.7, 1.5), отдельная просьба 07.10.2026. Герои/лорды и сам
                // игрок — нет, их облик не должен дрожать между боями. Тот же детерминированный ГСЧ
                // на агента, что и у RandomizeCommonTroopLook (agent.Index + Mission.Current),
                // иначе размер скакал бы при каждой пересборке агента в одном бою.
                float? wingsScale = null;
                if (WingsRaceIds().Contains(race) && !isPlayer && !agent.Character.IsHero)
                {
                    var rng = new Random(unchecked(agent.Index * 7919 + (Mission.Current?.GetHashCode() ?? 0)));
                    var (minScale, maxScale) = WingsScaleRangeByRaceId().TryGetValue(race, out var r) ? r : (0.5f, 1f);
                    wingsScale = minScale + (float)rng.NextDouble() * (maxScale - minScale);
                }
                // Случайный размер хвоста — dragon (0.25-1.0) и changeling (0.7-1.5, как крылья,
                // просьба пользователя 07.10.2026). Отдельный ГСЧ (другой множитель на agent.Index)
                // — иначе было бы то же число, что и у крыльев, и оба масштаба дрожали бы синхронно.
                float? tailScale = null;
                if (TailScaleRangeByRaceId().TryGetValue(race, out var tailRange)
                    && !isPlayer && !agent.Character.IsHero)
                {
                    var rng = new Random(unchecked(agent.Index * 104729 + (Mission.Current?.GetHashCode() ?? 0)));
                    tailScale = tailRange.Min + (float)rng.NextDouble() * (tailRange.Max - tailRange.Min);
                }
                Attach(agent.AgentVisuals, race, agent.Name ?? "агент", bodyCode: bodyCode,
                    stripedOverride: striped, wingsOverride: wings, tailOverride: tail, hornOverride: horn,
                    wingsScaleOverride: wingsScale, tailScaleOverride: tailScale);
                // Красим ПОСЛЕ Attach, не до: под шлемом настоящей гривы на скелете ещё нет в
                // момент сборки — её создаёт сам Attach -> EnsureHiddenHairReference, пустой
                // (белой) копией. Красили раньше "в пустоту" до Attach: без шлема цвет прилипал,
                // а под шлемом — почти никогда, оттого белых хвостов оказалось подавляющее
                // большинство (замечено 30.09.2026: белые именно у бойцов в шлемах).
                if (skinColor.HasValue && hairColor.HasValue)
                {
                    ApplyPonyColors(agent.AgentVisuals, race, skinColor.Value, hairColor.Value);
                }
            });
        }

        // Решает случайный облик рядового бойца (свой ГСЧ на бойца — детерминирован agent.Index
        // в пределах ОДНОГО боя, иначе выбор дрожал бы при каждой пересборке того же агента;
        // Mission.Current в замесе даёт разницу между боями). Только числа — меши ещё не красим,
        // это делает ApplyPonyColors уже после Attach (см. там, почему).
        private static void RandomizeCommonTroopLook(Agent agent, out bool striped, out bool wings, out bool tail, out bool horn,
            out uint skinColor, out uint hairColor)
        {
            var rng = new Random(unchecked(agent.Index * 7919 + (Mission.Current?.GetHashCode() ?? 0)));
            striped = rng.NextDouble() < 0.5;
            wings = rng.NextDouble() < 0.5;
            tail = rng.NextDouble() < 0.5;
            horn = rng.NextDouble() < 0.5;
            RandomPonyPalette(rng, out skinColor, out hairColor);
        }

        // Как в оригинале MLP: тело и грива не берутся из воздуха независимо друг от друга —
        // у почти белого тела грива вольна быть любой (Рэрити и т.п.), у остальных грива того же
        // цветового семейства, что и тело, только темнее/насыщеннее и со сдвигом тона в тёплую
        // сторону (розовое тело -> тёмно-розовая грива, оранжевое -> жёлтая) (замечено
        // 30.09.2026: до этой правки цвета тела и гривы браковались независимо и не сочетались).
        private const float PaleSkinChance = 0.25f;

        private static void RandomPonyPalette(Random rng, out uint skinColor, out uint hairColor)
        {
            bool paleSkin = rng.NextDouble() < PaleSkinChance;
            float skinHue = (float)rng.NextDouble();
            float skinSat = paleSkin ? (float)rng.NextDouble() * 0.1f : 0.3f + (float)rng.NextDouble() * 0.5f;
            float skinVal = paleSkin ? 0.9f + (float)rng.NextDouble() * 0.08f : 0.55f + (float)rng.NextDouble() * 0.35f;
            skinColor = TaleWorlds.Library.Color.FromHSV(skinHue, skinSat, skinVal).ToUnsignedInteger();

            float hairHue, hairSat, hairVal;
            if (paleSkin)
            {
                hairHue = (float)rng.NextDouble();
                hairSat = 0.5f + (float)rng.NextDouble() * 0.5f;
                hairVal = 0.35f + (float)rng.NextDouble() * 0.5f;
            }
            else
            {
                // Сдвиг тона в основном в тёплую сторону (оранжевое -> жёлтое), но не всегда —
                // при небольшом сдвиге просто темнее оттенок того же тона (розовое -> тёмно-розовое).
                float shift = -0.05f + (float)rng.NextDouble() * 0.25f;
                hairHue = Wrap01(skinHue + shift);
                hairSat = Math.Min(1f, skinSat + 0.15f + (float)rng.NextDouble() * 0.25f);
                hairVal = Math.Max(0.15f, skinVal * (0.55f + (float)rng.NextDouble() * 0.3f));
            }
            hairColor = TaleWorlds.Library.Color.FromHSV(hairHue, hairSat, hairVal).ToUnsignedInteger();
        }

        private static float Wrap01(float x)
        {
            x %= 1f;
            return x < 0f ? x + 1f : x;
        }

        // Известные по сериалу персонажи-лорды (Module/ModuleData/equestria_lords.xml, id пони-лордов)
        // — цвет шерсти/гривы сверен по официальному цветовому гайду сериала (MLP Vector Club,
        // mlpvector.club/cg/pony, заливка без обводки/теней — у нас один сплошной тон на часть).
        // У Селестии и Кэденс в оригинале многоцветная/градиентная грива — одним тоном её не
        // передать, взят самый заметный оттенок. Остальные лорды (их в equestria_lords.xml
        // несколько сотен, в основном процедурно собранные имена) сюда не входят — см. LoreColor.
        private static readonly Dictionary<string, (uint Skin, uint Hair)> LoreColors =
            new Dictionary<string, (uint, uint)>(StringComparer.OrdinalIgnoreCase)
        {
            { "eq_celestia", (0xFFF6E4EF, 0xFFD9B8DD) },
            { "eq_luna", (0xFF363E7A, 0xFF1C4CC2) },
            { "eq_cadance", (0xFFFFCBE4, 0xFF8034BA) },
            { "eq_twilight", (0xFFCC9CDF, 0xFF243870) },
            { "eq_blueblood", (0xFFFFFFFF, 0xFFE3CA75) },
            { "eq_spitfire", (0xFFF8EA62, 0xFFED7B00) },
            { "eq_soarin", (0xFFD8E6F5, 0xFF2D3263) },
            { "eq_fleetfoot", (0xFF8BD8DF, 0xFFFFFFFF) },
            { "eq_big_mac", (0xFFE64A57, 0xFFFBBA62) },
            { "eq_apple_bloom", (0xFFF3F49B, 0xFFF5415F) },
        };

        // Цвет героя-пони: у известных персонажей — лорный (LoreColors), у остальных (их
        // в equestria_lords.xml несколько сотен, по лору не прописаны) — стабильный случайный
        // по StringId персонажа. Важно: не Random(agent.Index), как у рядовых бойцов — герой один
        // и тот же между боями и после перезапуска игры, его цвет не должен "дрожать" каждый раз.
        // string.GetHashCode() в .NET не детерминирован между запусками процесса — свой FNV-1a.
        private static void LoreColor(string heroId, out uint skinColor, out uint hairColor)
        {
            if (!string.IsNullOrEmpty(heroId) && LoreColors.TryGetValue(heroId, out var known))
            {
                skinColor = known.Skin;
                hairColor = known.Hair;
                return;
            }
            var rng = new Random(unchecked((int)StableHash(heroId ?? "")));
            RandomPonyPalette(rng, out skinColor, out hairColor);
        }

        private static uint StableHash(string s)
        {
            unchecked
            {
                uint hash = 2166136261;
                foreach (char c in s)
                {
                    hash ^= c;
                    hash *= 16777619;
                }
                return hash;
            }
        }

        // Раньше звалась ApplyRandomTroopColors — теперь красит и рядовых (случайно), и героев-лордов
        // (по лору известных или стабильно-случайно неизвестных, см. LoreColor), поэтому принимает
        // visuals напрямую, как остальные методы файла, а не Agent.
        private static void ApplyPonyColors(object visuals, int race, uint skinColor, uint hairColor)
        {
            var entity = AccessTools.Method(visuals.GetType(), "GetEntity")?.Invoke(visuals, null) as GameEntity;
            var skeleton = entity?.Skeleton;
            if (skeleton == null || !RaceParts().TryGetValue(race, out string[] parts) || parts.Length == 0)
            {
                return;
            }
            foreach (var mesh in FindPrefixMeshes(skeleton, parts[0]))
            {
                mesh.Color = skinColor;
                mesh.Color2 = skinColor;
            }
            // Хвост — цвета гривы (HairTinted), крылья и рог — цвета тела (см. правку 30.09.2026
            // в HairTinted). Красим их напрямую, а не через донора: донор (Tint()) уже отработал
            // внутри Attach() выше со старым (белым) цветом гривы/тела, второй раз его не позвать
            // без потери материала.
            foreach (string partName in parts)
            {
                uint color = HairTinted.ContainsKey(partName) ? hairColor : skinColor;
                foreach (var mesh in skeleton.GetAllMeshes().Where(m => m != null && m.Name != null
                    && m.Name.StartsWith(partName, StringComparison.OrdinalIgnoreCase)))
                {
                    mesh.Color = color;
                    mesh.Color2 = color;
                }
            }
            if (HairReferenceByRaceId().TryGetValue(race, out string hairRef))
            {
                foreach (var mesh in skeleton.GetAllMeshes().Where(m => m != null && m.Name != null
                    && m.Name.StartsWith(hairRef, StringComparison.OrdinalIgnoreCase)))
                {
                    mesh.Color = hairColor;
                    mesh.Color2 = hairColor;
                }
            }
        }

        // Меши "кожи" (тело/ноги/голова/перчатки) — тот же приём, что FindDonor: общее начало
        // имени с любой нашей частью расы (eq_pony_tail -> eq_pony_), кроме самих наших частей.
        private static IEnumerable<Mesh> FindPrefixMeshes(Skeleton skeleton, string samplePartName)
        {
            int cut = samplePartName.LastIndexOf('_');
            if (cut <= 0)
            {
                yield break;
            }
            string prefix = samplePartName.Substring(0, cut + 1);
            var mine = RaceParts().Values.SelectMany(v => v).ToArray();
            foreach (var m in skeleton.GetAllMeshes())
            {
                if (m != null && m.Name != null && m.Name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)
                    && !mine.Any(n => m.Name.StartsWith(n, StringComparison.OrdinalIgnoreCase)))
                {
                    yield return m;
                }
            }
        }

        // ---------------------------------------------------------------- портреты и карта кампании
        // Вне миссий персонажа собирают через один и тот же завод — AgentVisuals.Create: так делают
        // окна снаряжения, отряда и цирюльника (CharacterTableau) и фигурки отрядов на карте
        // (MobilePartyVisual.HumanAgentVisuals). Цепляемся к нему — меш попадает на скелет сразу
        // при создании.
        //
        // Важно, КОГДА ставить этот патч: только из EquestriaPatches.ApplyLate (главное меню).
        // Поставленный при загрузке мода, он запускает статическую инициализацию AgentVisuals
        // раньше, чем игра прочитала анимации, и все пони в окнах лежат набок — ровно та же беда,
        // что была с ранним патчем Agent. Проверено 2026-09-18 ключом /eqnoparts.
        //
        // Дочерняя сущность вместо скелета (GameEntity.CreateEmpty + AddChild) не годится:
        // меш у пони скиннованный, без скелета движок его просто не рисует — сущность создаётся,
        // в журнале всё хорошо, а хвоста нет.
        private const string VisualsType = "TaleWorlds.MountAndBlade.View.AgentVisuals";

        // Раса известна только в момент создания, а Refresh (смена снаряжения) меши пересобирает —
        // поэтому расу запоминаем за объектом внешности.
        private static readonly System.Runtime.CompilerServices.ConditionalWeakTable<object, object> RaceOf =
            new System.Runtime.CompilerServices.ConditionalWeakTable<object, object>();

        // Тот же приём, что и RaceOf: AgentVisuals.Refresh не получает данные заново, только
        // __instance, поэтому StringId персонажа (для лор-цвета/стабильного случайного, см.
        // LoreColor) запоминаем здесь при создании и используем же при каждом обновлении.
        private static readonly System.Runtime.CompilerServices.ConditionalWeakTable<object, string> CharIdOf =
            new System.Runtime.CompilerServices.ConditionalWeakTable<object, string>();

        public static void ApplyVisuals(Harmony harmony)
        {
            var type = AccessTools.TypeByName(VisualsType);
            var create = type == null ? null : AccessTools.Method(type, "Create");
            if (create == null)
            {
                EquestriaCrashLog.Warn("части тела: AgentVisuals.Create не найден — вне боя хвоста не будет");
                return;
            }
            harmony.Patch(create, postfix: new HarmonyMethod(typeof(EquestriaBodyParts), nameof(AfterVisualsCreate)));
            foreach (var refresh in AccessTools.GetDeclaredMethods(type))
            {
                if (refresh.Name != "Refresh")
                {
                    continue;
                }
                harmony.Patch(refresh, postfix: new HarmonyMethod(typeof(EquestriaBodyParts), nameof(AfterVisualsRefresh)));
            }
            ApplyTableau(harmony);
        }

        // Окна снаряжения, отряда и цирюльника рисуют персонажа не через AgentVisuals.Create,
        // а своим полотном — CharacterTableau: оно само держит внешность в поле _agentVisuals
        // и пересобирает её при смене снаряжения. Поэтому цепляемся к его такту: внешность там
        // готовится не сразу (счётчики загрузки), а надеть повторно нам не страшно — Attach
        // проверяет, не висит ли меш уже.
        private const string TableauType = "TaleWorlds.MountAndBlade.View.Tableaus.CharacterTableau";

        private static void ApplyTableau(Harmony harmony)
        {
            var type = AccessTools.TypeByName(TableauType);
            var tick = type == null ? null : AccessTools.Method(type, "OnTick");
            if (tick == null)
            {
                EquestriaCrashLog.Warn("части тела: CharacterTableau.OnTick не найден — "
                    + "в окнах снаряжения и отряда хвоста не будет");
                return;
            }
            harmony.Patch(tick, postfix: new HarmonyMethod(typeof(EquestriaBodyParts), nameof(AfterTableauTick)));
        }

        private static void AfterTableauTick(object __instance)
        {
            EquestriaCrashLog.Try("части тела в окне", () =>
            {
                if (__instance == null)
                {
                    return;
                }
                var visuals = AccessTools.Field(__instance.GetType(), "_agentVisuals")?.GetValue(__instance);
                object race = AccessTools.Field(__instance.GetType(), "_race")?.GetValue(__instance);
                if (visuals != null && race is int raceId)
                {
                    // cacheKey — сам CharacterTableau: при смене снаряжения он пересоздаёт _agentVisuals
                    // заново (проверено логом), а сам переживает — цвет причёски помнить нужно по нему.
                    // bodyCode — код внешности персонажа: один и тот же во всех окнах, переживает даже
                    // совсем новое окно, открытое сразу со шлемом (там cacheKey ничего не запомнит,
                    // потому что своя причёска в нём не строится ни разу).
                    string bodyCode = AccessTools.Field(__instance.GetType(), "_bodyPropertiesCode")
                        ?.GetValue(__instance) as string;
                    Attach(visuals, raceId, "окно", __instance, bodyCode);
                    // Тот же лор-цвет/стабильный случайный, что и в бою (OnAgentBuild) — иначе
                    // в инвентаре, отряде, цирюльне и энциклопедии лорды снова белые: окна собирают
                    // персонажа этим же полотном (CharacterTableau), а не через миссию, и наш патч
                    // там не выполняется. _charStringId — StringId персонажа (у героев совпадает
                    // с Hero.StringId), найден через рефлексию поля — других способов узнать,
                    // КТО показан в этом окне, у полотна нет.
                    string charStringId = AccessTools.Field(__instance.GetType(), "_charStringId")
                        ?.GetValue(__instance) as string;
                    ApplyLoreColorIfPony(visuals, raceId, charStringId);
                }
            });
        }

        private static void AfterVisualsCreate(object __result, object[] __args)
        {
            EquestriaCrashLog.Try("части тела вне боя", () =>
            {
                object data = __args != null && __args.Length > 0 ? __args[0] : null;
                object raceValue = data == null ? null : AccessTools.Property(data.GetType(), "RaceData")?.GetValue(data);
                if (__result == null || !(raceValue is int race))
                {
                    return;
                }
                RaceOf.Remove(__result);
                RaceOf.Add(__result, race);
                string charStringId = AccessTools.Property(data.GetType(), "CharacterObjectStringIdData")
                    ?.GetValue(data) as string;
                CharIdOf.Remove(__result);
                if (!string.IsNullOrEmpty(charStringId))
                {
                    CharIdOf.Add(__result, charStringId);
                }
                string owner = __args != null && __args.Length > 1 ? __args[1] as string : null;
                Attach(__result, race, "создание " + (owner ?? "без имени"));
                ApplyLoreColorIfPony(__result, race, charStringId);
            });
        }

        // Фигурки отрядов на карте (MobilePartyVisual), разговор на карте (EquestriaHelmetFit.
        // AfterMapConversationTick) и прочие AgentVisuals вне CharacterTableau — тот же лор-цвет/
        // стабильный случайный, что и в бою и в окнах (см. OnAgentBuild, AfterTableauTick), иначе
        // лорды там опять белые. internal — зовётся и из EquestriaHelmetFit.
        internal static void ApplyLoreColorIfPony(object visuals, int race, string charStringId)
        {
            bool isPlayer = !string.IsNullOrEmpty(charStringId) && Hero.MainHero != null
                && (charStringId == Hero.MainHero.StringId
                    || charStringId == Hero.MainHero.CharacterObject?.StringId);
            if (race == PonyRaceId() && !string.IsNullOrEmpty(charStringId) && !isPlayer)
            {
                LoreColor(charStringId, out uint skin, out uint hair);
                ApplyPonyColors(visuals, race, skin, hair);
            }
        }

        private static void AfterVisualsRefresh(object __instance)
        {
            EquestriaCrashLog.Try("части тела вне боя (обновление)", () =>
            {
                if (__instance != null && RaceOf.TryGetValue(__instance, out object race) && race is int raceId)
                {
                    Attach(__instance, raceId, "обновление");
                    CharIdOf.TryGetValue(__instance, out string charStringId);
                    ApplyLoreColorIfPony(__instance, raceId, charStringId);
                }
            });
        }
    }
}
