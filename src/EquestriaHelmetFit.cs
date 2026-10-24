using System;
using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using TaleWorlds.CampaignSystem.GameState;
using TaleWorlds.Core;
using TaleWorlds.Engine;
using TaleWorlds.Library;
using TaleWorlds.MountAndBlade;

namespace EquestriaMod
{
    // Шлем на драконью голову.
    //
    // Голова у дракона крупнее человеческой, и любой ванильный шлем сидит на ней шапочкой.
    // Дубликаты шлемов делать нельзя — их в игре сотни, и это же пришлось бы повторять для каждой
    // расы; уменьшать голову пользователь не хочет.
    //
    // Движок УЖЕ умеет подгонять шлем под размер головы: собирая персонажа, он для каждого меша
    // с признаком UsingFacegenScaling зовёт MetaMesh.UseHeadBoneFaceGenScaling с матрицей из
    // MBAgentVisuals.GetFacegenScalingMatrix (под ней нативная GetCurrentHelmetScalingFactor —
    // то есть матрица ровно про шлемы). Мы эту матрицу и домножаем. Так масштаб применяется
    // В КООРДИНАТАХ КОСТИ ГОЛОВЫ, и шлем ездит вместе с головой.
    //
    // Раньше тут была своя рамка на мешах шлема (Mesh.SetLocalFrame). Размер она меняла, но
    // применялась в координатах персонажа: при повороте головы шлем оставался на месте
    // («шлем движется не от кости головы»). Не возвращать.
    //
    // 28.09.2026: комментарий выше описывал родной путь (UsingFacegenScaling/
    // GetFacegenScalingMatrix/UseHeadBoneFaceGenScaling) как уже работающий — на деле патча на
    // него никогда не было, весь файл всегда жил на ручной рамке ниже. Попробовали включить
    // родной путь по-настоящему: движок его действительно позвал (подтверждено логом), но
    // размер шлема развалился — в бою сел стандартным (нерастянутым), в инвентаре улетел вверх
    // и раздулся. Судя по всему, GetFacegenScalingMatrix — это не простая диагональная матрица
    // масштаба, и наивное покомпонентное домножение (.rotation.s/.f/.u на свой множитель) её
    // портит. Откатили обратно на ручную рамку — она хотя бы держит размер верно везде, просто
    // не поворачивается вместе с головой. Родной путь можно будет пробовать снова, но сначала
    // нужно понять настоящий формат этой матрицы (скорее всего не диагональ), а не гадать.
    public static class EquestriaHelmetFit
    {
        // Трассировка поворота шлема в журнал — строка на каждый кадр боя, только для отладки
        private const bool TraceHelmet = false;

        // Во сколько раз растягивать шлем на этой расе. Список, а не одно число: у каждой расы
        // своя голова, и грифону с яком понадобятся свои значения.
        // По осям, а не одним числом: голова расы вытянута иначе человеческой, и шлем нередко
        // просится шире, чем выше. Порядок как в Vec3: вбок, вперёд-назад, вверх.
        // Причёска расы — её приходится возвращать вручную там, где мы прячем шлем: игра не
        // строит причёску под надетым шлемом (HairCoverType), и голова остаётся голой.
        private static readonly Dictionary<string, string> HairByRace = new Dictionary<string, string>
        {
            { "dragon", "eq_dragon_hair" },
            { "griffon", "eq_griffon_hair" },
            { "hippogriff", "eq_hippogriff_hair" },
            // у яка в причёске сидят ещё и рога — без этой строки он под шлемом остаётся и без
            // гривы, и безрогим
            { "yak", "eq_yak_hair" },
            // у оленихи причёска — это рога целиком, без неё она под шлемом безрогая
            { "deer", "eq_deer_hair" },
            // у пони причёска — рог; грива вшита в голову
            { "pony", "eq_pony_hair" },
        };

        private static readonly Dictionary<string, Vec3> ScaleByRace = new Dictionary<string, Vec3>
        {
            // подобрано в игре: equestria.helmet_scale 2.25 2.25 1.9 (05.10.2026, после правки моргания)
            { "pony", new Vec3(2.25f, 2.25f, 1.9f) },
            // подобрано в игре: equestria.helmet_scale 2 2 1.85 (10.10.2026, поправленная модель дракона)
            { "dragon", new Vec3(2f, 2f, 1.85f) },
            // подобрано в игре: equestria.helmet_scale 2.1 1.9 1.75 (05.10.2026, после правки моргания)
            { "griffon", new Vec3(2.1f, 1.9f, 1.75f) },
            // подобрано в игре: equestria.helmet_scale 2 1.8 1.6 (05.10.2026, после правки моргания)
            { "changeling", new Vec3(2f, 1.8f, 1.6f) },
            // подобрано в игре: equestria.helmet_scale 1.8 1.8 1.4 (05.10.2026, после правки моргания)
            { "hippogriff", new Vec3(1.8f, 1.8f, 1.4f) },
            // подобрано в игре: equestria.helmet_scale 1.95 1.95 1.7 (04.10.2026, после пересборки модели)
            { "yak", new Vec3(1.95f, 1.95f, 1.7f) },
            // подобрано в игре: equestria.helmet_scale 1.85 1.85 1.55 (05.10.2026, после правки моргания)
            { "deer", new Vec3(1.85f, 1.85f, 1.55f) },
        };

        /// <summary>Множитель расы — чтобы подбирать его на лету командой, без перезапуска.</summary>
        public static Vec3 ScaleFor(string race)
        {
            return ScaleByRace.TryGetValue(race, out Vec3 scale) ? scale : new Vec3(1f, 1f, 1f);
        }

        public static void SetScale(string race, Vec3 scale)
        {
            ScaleByRace[race] = scale;
            _byRaceId = null;               // пересобрать таблицу по номерам рас
        }

        private static Dictionary<int, Vec3> _byRaceId;
        // Раса персонажа, которого движок собирает ПРЯМО СЕЙЧАС. Матрицу он просит в середине
        // сборки, когда раса известна только из её данных, поэтому запоминаем на время вызова.
        [ThreadStatic]
        private static int _building;
        // Меши шлема запоминаем за внешностью бойца: иначе каждый кадр пришлось бы перебирать
        // все меши скелета (у бойца их несколько десятков) и сравнивать имена. В бою на тысячу
        // бойцов это заметно. Внешность пересобирается при смене снаряжения — тогда появляется
        // новый объект, и запись заводится заново; на всякий случай сверяем и имя меша.
        //
        // Этого мало: посадка на коня (замечено 28.09.2026, «шлем едет с телом, а не с головой»)
        // пересобирает скелет ВНУТРИ того же объекта внешности — сам visuals не меняется, и старая
        // запись в кэше проходила бы по имени меша, а Meshes/Bone в ней остались бы от ПРЕЖНЕГО
        // скелета: мы бы двигали уже не показываемые меши, а настоящий шлем всадника так и стоял
        // бы в позе обычного скина брони (то есть ехал бы с телом). Тот же класс бага, что уже был
        // с CharacterTableau и цветом причёски — там тоже нельзя было полагаться на неизменность
        // объекта-владельца. Поэтому сверяем ещё и сам скелет.
        private sealed class Fitted
        {
            public string MeshName;
            public Mesh[] Meshes;
            public sbyte Bone;
            public int Race;              // только для окон: путь боя race не хранит (см. Fit(Agent))
            public Skeleton Skeleton;
        }

        private static readonly System.Runtime.CompilerServices.ConditionalWeakTable<object, Fitted> _cache =
            new System.Runtime.CompilerServices.ConditionalWeakTable<object, Fitted>();


        private static System.Reflection.MethodInfo _getData, _getEntity;
        private static System.Reflection.PropertyInfo _raceData, _equipmentData, _monsterData;
        // Раньше был один общий флаг: успех логировался ОДИН РАЗ за весь процесс, и первая же
        // удачная раса (например, як) навсегда скрывала от лога все остальные — по такому логу
        // нельзя было понять, подгоняется ли конкретно грифон (замечено 25.09.2026). Теперь по
        // имени меша: одна строка на каждый отдельный шлем, а не одна на весь сеанс.
        private static readonly HashSet<string> _shiftLoggedMeshes = new HashSet<string>();

        private static Dictionary<int, Vec3> Scales()
        {
            if (_byRaceId == null)
            {
                _byRaceId = new Dictionary<int, Vec3>();
                foreach (var pair in ScaleByRace)
                {
                    int race = TaleWorlds.Core.FaceGen.GetRaceOrDefault(pair.Key);
                    if (race != 0)          // 0 — человек, туда же попадают ненайденные расы
                    {
                        _byRaceId[race] = pair.Value;
                    }
                }
            }
            return _byRaceId;
        }

        public static void Apply(Harmony harmony)
        {
            var visuals = AccessTools.TypeByName("TaleWorlds.MountAndBlade.View.AgentVisuals");
            var matrix = AccessTools.Method(typeof(MBAgentVisuals), "GetFacegenScalingMatrix");
            if (visuals == null || matrix == null)
            {
                EquestriaCrashLog.Warn("шлем под расу: не найден AgentVisuals или матрица подгонки");
                return;
            }
            int marked = 0;
            // Какие из точек сборки реально нашлись — печатаем поимённо в конце: одно число
            // "точек 5" не говорило, какая именно из шести пропала (замечено 25.09.2026).
            var found = new List<string>();
            foreach (var method in AccessTools.GetDeclaredMethods(visuals))
            {
                // Доспех навешивает отдельный метод, и зовут его не только из сборки внешности —
                // без него раса в нужный миг оставалась неизвестной и подгонка молчала.
                if (method.Name == "AddArmorMultiMeshesToAgentEntity")
                {
                    // префикс — сказать движку расу (без неё он не растянет шлем),
                    // постфикс — опустить уже надетый шлем на место
                    harmony.Patch(method,
                        prefix: new HarmonyMethod(typeof(EquestriaHelmetFit), nameof(BeforeArmour)),
                        postfix: new HarmonyMethod(typeof(EquestriaHelmetFit), nameof(AfterArmour)),
                        finalizer: new HarmonyMethod(typeof(EquestriaHelmetFit), nameof(AfterBuild)));
                    marked++;
                    found.Add("AgentVisuals.AddArmorMultiMeshesToAgentEntity");
                    continue;
                }
                // Кадр окна: только здесь персонаж шевелится без пересборки (энциклопедия,
                // окно отряда). См. Tick.
                if (method.Name == "TickVisuals")
                {
                    harmony.Patch(method,
                        postfix: new HarmonyMethod(typeof(EquestriaHelmetFit), nameof(AfterTick)));
                    marked++;
                    found.Add("AgentVisuals.TickVisuals");
                    continue;
                }
                if (method.Name != "Create" && method.Name != "Refresh")
                {
                    continue;
                }
                harmony.Patch(method,
                    prefix: new HarmonyMethod(typeof(EquestriaHelmetFit), nameof(BeforeBuild)),
                    finalizer: new HarmonyMethod(typeof(EquestriaHelmetFit), nameof(AfterBuild)));
                marked++;
                found.Add("AgentVisuals." + method.Name);
            }
            // Кость головы у наших монстров выходит -1: движок ищет кости монстра через скелет его
            // набора движений, и у рас мода эта связка не срабатывает (skeleton в наборах прописан,
            // а номер всё равно -1). Этот же -1 движок передаёт в подгонку шлема, и тот улетает.
            // Подставляем верный номер: в человеческом скелете голова — кость 13 (порядок костей
            // виден в выгрузке tpac_export bones: pelvis 0, spine 9, spine1 10, spine2 11, neck 12,
            // head 13; те же номера стоят в именах костей пони-блендера — bip01_head_13).
            // Картинки-заготовки: персонажа собирают, ставят позу и проигрывают анимацию, и только
            // потом снимают кадр. Подгонка при сборке доспеха приходится на позу покоя, поэтому
            // повторяем её в конце сборки заготовки (см. FitStatic).
            // Оба класса лежат в TaleWorlds.MountAndBlade.View.SCRIPTS, а не прямо в View — тип не
            // находился ни разу (AccessTools.TypeByName отдавал null), поэтому весь путь заготовок
            // молчал с самого начала (замечено 25.09.2026 по подробному списку точек ниже).
            foreach (var typeName in new[] { "TaleWorlds.MountAndBlade.View.Scripts.CharacterSpawner",
                                             "TaleWorlds.MountAndBlade.View.Scripts.CharacterDebugSpawner" })
            {
                var spawner = AccessTools.TypeByName(typeName);
                if (spawner == null)
                {
                    found.Add(typeName.Substring(typeName.LastIndexOf('.') + 1) + " — ТИП НЕ НАЙДЕН");
                    continue;
                }
                var init = AccessTools.GetDeclaredMethods(spawner).FirstOrDefault(m => m.Name == "InitWithCharacter");
                if (init == null)
                {
                    found.Add(spawner.Name + ".InitWithCharacter — МЕТОД НЕ НАЙДЕН");
                    continue;
                }
                harmony.Patch(init,
                    postfix: new HarmonyMethod(typeof(EquestriaHelmetFit), nameof(AfterSpawner)));
                marked++;
                found.Add(spawner.Name + ".InitWithCharacter");
            }

            // Встреча с отрядом лорда на карте: SandBox.View.Map.MapConversationTableau держит
            // СПИСОК внешностей (говорящий первым, за ним до двух телохранителей — читал класс
            // напрямую), но в своём OnTick тикает ТОЛЬКО _agentVisuals[0] — только говорящего.
            // Телохранители не получают ни одного кадра после создания, а их поза (и с ней —
            // положение головы) ставится ПОСЛЕ Create тем же TickAnimationsAndForceUpdate, что и у
            // заготовок миниатюр, — поэтому у них та же беда: шлем остаётся на позе покоя и висит
            // в стороне (замечено 25.09.2026, «Императрица Селестия» в порядке, эскорт — нет).
            // Тикаем весь список сами постфиксом на OnTick.
            var mapConvType = AccessTools.TypeByName("SandBox.View.Map.MapConversationTableau");
            var mapConvTick = mapConvType == null ? null : AccessTools.Method(mapConvType, "OnTick");
            if (mapConvTick == null)
            {
                found.Add("MapConversationTableau.OnTick — "
                    + (mapConvType == null ? "ТИП НЕ НАЙДЕН" : "МЕТОД НЕ НАЙДЕН"));
            }
            else
            {
                harmony.Patch(mapConvTick,
                    postfix: new HarmonyMethod(typeof(EquestriaHelmetFit), nameof(AfterMapConversationTick)));
                marked++;
                found.Add("MapConversationTableau.OnTick");
            }

            var boneIndex = AccessTools.PropertyGetter(typeof(Monster), "HeadLookDirectionBoneIndex");
            if (boneIndex != null)
            {
                harmony.Patch(boneIndex, postfix: new HarmonyMethod(typeof(EquestriaHelmetFit), nameof(AfterBone)));
            }
            EquestriaCrashLog.Log($"шлем под расу: патч поставлен (точек сборки {marked}, "
                + $"подстраховка по кости: {(boneIndex != null ? "да" : "НЕ НАЙДЕНА")})\r\n  "
                + string.Join("\r\n  ", found));
        }

        // Раса берётся из данных внешности: у Create они первым доводом, у Refresh — вторым.
        private static void BeforeBuild(object[] __args)
        {
            _building = 0;
            EquestriaCrashLog.Try("шлем под расу (начало сборки)", () =>
            {
                foreach (var arg in __args ?? new object[0])
                {
                    var race = arg == null ? null
                        : AccessTools.Property(arg.GetType(), "RaceData")?.GetValue(arg);
                    if (race is int id)
                    {
                        _building = id;
                        return;
                    }
                }
            });
        }

        // Раса — у самой внешности: на этом шаге её данные уже собраны. Заодно считаем, вокруг
        // какой точки растягивать: движок применяет матрицу в координатах КОСТИ ГОЛОВЫ, а она
        // сидит у основания шеи. Без поправки шлем при двойном масштабе уезжает на свою же
        // высоту над головой (проверено в игре). Поэтому в матрицу кладём сдвиг, оставляющий
        // середину шлема на месте.
        // Кость головы берём НЕ ПО ИМЕНИ, а по номеру из данных монстра — тому самому, который
        // движок сам передаёт в подгонку. По имени не вышло дважды: ни блендеровское
        // «bip01_head_13», ни короткое «head» скелет не находит, и поправка выходила нулевой.
        private const float HelmetUp = 0.12f;        // насколько середина шлема выше кости головы

        // Куда сдвинуть шлем после растяжения: череп у расы сидит не там же, где человеческий.
        // Порядок как в Vec3: вбок (+X — вправо, если смотреть на персонажа спереди), вперёд
        // (морда смотрит в -Y, поэтому вперёд — это минус) и вверх. Подбирается на лету командой
        // equestria.helmet_offset, значения тут — начальные.
        private static readonly Dictionary<string, Vec3> ShiftByRace = new Dictionary<string, Vec3>
        {
            // подобрано в игре: equestria.helmet_offset 0.0 0.08 0.12 (05.10.2026, после правки моргания)
            // — шлем сдвигается вперёд, поэтому по Y минус (морда смотрит в -Y)
            { "pony", new Vec3(0f, -0.08f, 0.12f) },
            // подобрано в игре: equestria.helmet_offset 0.0 0.13 0.07 (10.10.2026, поправленная
            // модель дракона) — шлем сдвигается вперёд, поэтому по Y минус (морда смотрит в -Y)
            { "dragon", new Vec3(0f, -0.13f, 0.07f) },
            // подобрано в игре: equestria.helmet_offset 0.0 0.07 0.15 (05.10.2026, после правки моргания)
            { "griffon", new Vec3(0f, -0.07f, 0.15f) },
            // подобрано в игре: equestria.helmet_offset 0.0 0.04 0.12 (05.10.2026, после правки моргания)
            { "changeling", new Vec3(0f, -0.04f, 0.12f) },
            // подобрано в игре: equestria.helmet_offset 0.0 0.04 0.06 (05.10.2026, после правки моргания)
            { "hippogriff", new Vec3(0f, -0.04f, 0.06f) },
            // подобрано в игре: equestria.helmet_offset 0.0 0.0 0.06 (04.10.2026, после пересборки модели)
            { "yak", new Vec3(0f, 0f, 0.06f) },
            // подобрано в игре: equestria.helmet_offset 0.0 0.03 0.13 (05.10.2026, после правки моргания)
            { "deer", new Vec3(0f, -0.03f, 0.13f) },
        };

        public static Vec3 ShiftFor(string race)
        {
            return ShiftByRace.TryGetValue(race, out Vec3 shift) ? shift : Vec3.Zero;
        }

        public static void SetShift(string race, float right, float forward, float up)
        {
            ShiftByRace[race] = new Vec3(right, -forward, up);
        }

        private static Vec3 Shift(int raceId)
        {
            foreach (var pair in ShiftByRace)
            {
                if (TaleWorlds.Core.FaceGen.GetRaceOrDefault(pair.Key) == raceId)
                {
                    return pair.Value;
                }
            }
            return Vec3.Zero;
        }

        private static int _bone = -1;
        private static string _why = "не считали";
        private static string _monster = "?";

        // Раса — у самой внешности: движок спросит масштаб шлема посреди этой сборки, и узнать
        // её там больше неоткуда.
        private static void BeforeArmour(object __instance)
        {
            _building = 0;
            EquestriaCrashLog.Try("шлем под расу (начало доспеха)", () =>
            {
                var data = AccessTools.Method(__instance.GetType(), "GetCopyAgentVisualsData")
                    ?.Invoke(__instance, null);
                var race = data == null ? null
                    : AccessTools.Property(data.GetType(), "RaceData")?.GetValue(data);
                if (race is int id)
                {
                    _building = id;
                }
            });
        }

        // Меш шлема уже надет — опускаем его на место.
        //
        // Почему не через матрицу движка: он берёт из неё только масштаб, а сдвиг игнорирует,
        // поэтому шлем всегда растёт вокруг кости (та сидит у основания шеи) и уезжает вверх.
        // Своя рамка задаёт преобразование целиком.
        /// <summary>
        /// Растягивает надетый шлем под голову расы. Зовётся и при сборке доспеха, и каждый кадр
        /// из тех же точек, что и части тела, — опора должна идти за головой (см. ниже).
        /// </summary>
        /// <summary>Подгонка по бойцу — путь боя. Там у агента ДРУГОЙ тип внешности
        /// (MBAgentVisuals, а не оконный AgentVisuals), и данные берутся прямо у него.</summary>
        public static void Fit(Agent agent)
        {
            if (agent == null || agent.IsMount || agent.Character == null
                || !Scales().ContainsKey(agent.Character.Race))
            {
                return;
            }
            var visuals = agent.AgentVisuals;
            var skeleton = visuals?.GetEntity()?.Skeleton;
            string meshName = agent.SpawnEquipment[EquipmentIndex.Head].Item?.MultiMeshName;
            if (skeleton == null || string.IsNullOrEmpty(meshName))
            {
                return;
            }
            if (!_cache.TryGetValue(visuals, out Fitted kept) || kept.MeshName != meshName
                || kept.Skeleton != skeleton)
            {
                sbyte bone = agent.Monster?.HeadLookDirectionBoneIndex ?? HumanHeadBone;
                sbyte mapped = skeleton.GetSkeletonBoneMapping(bone);
                kept = new Fitted
                {
                    MeshName = meshName,
                    Bone = mapped >= 0 && mapped < skeleton.GetBoneCount() ? mapped : bone,
                    Meshes = HelmetMeshes(skeleton, meshName),
                    Skeleton = skeleton,
                };
                _cache.Remove(visuals);
                _cache.Add(visuals, kept);
                // Шлем подтверждён надёжным agent.SpawnEquipment — если спавн-time проверка
                // (EnsureHairNotBald, завязанная на менее надёжный снимок) успела включить гриву
                // по ошибке, гасим её здесь (см. HideBaldHairUnderConfirmedHelmet). Та же гонка
                // была и у ушей (HideEarsUnderConfirmedHelmet) — видны в бою под шлемом, хотя в
                // окне инвентаря прячутся верно.
                EquestriaBodyParts.HideBaldHairUnderConfirmedHelmet(visuals, agent.Character.Race);
                EquestriaBodyParts.HideEarsUnderConfirmedHelmet(visuals, agent.Character.Race);
            }
            Fit(skeleton, kept.Meshes, kept.Bone, agent.Character.Race, meshName,
                // Трассировка поворота шлема (28.09.2026) писала строку КАЖДЫЙ кадр боя — выключена;
                // включить для отладки: TraceHelmet = true
                traceAgent: TraceHelmet && agent == Agent.Main ? agent : null);
        }

        // Отладка "летающего треугольника" (30.09.2026): разворачивает участников разговора на
        // карте (и игрока в миссии) вокруг вертикальной оси, чтобы посмотреть на них с любой
        // стороны. Консоль: equestria.rotate_lord <градусы> (накопительно к предыдущему повороту).
        [CommandLineFunctionality.CommandLineArgumentFunction("rotate_lord", "equestria")]
        public static string RotateLordCommand(List<string> args)
        {
            if (args.Count != 1 || !float.TryParse(args[0], out float degrees))
            {
                return "Формат: equestria.rotate_lord <градусы>, например equestria.rotate_lord 90";
            }
            float rad = degrees * (float)Math.PI / 180f;
            int count = 0;
            if (Agent.Main?.AgentVisuals != null && RotateVisuals(Agent.Main.AgentVisuals, rad))
            {
                count++;
            }
            var conv = LastMapConversation;
            var list = conv == null ? null : AccessTools.Field(conv.GetType(), "_agentVisuals")
                ?.GetValue(conv) as System.Collections.IEnumerable;
            if (list != null)
            {
                foreach (var visuals in list)
                {
                    if (RotateVisuals(visuals, rad))
                    {
                        count++;
                    }
                }
            }
            return count > 0 ? $"Повёрнуто персонажей: {count}." : "Не нашёл ни игрока, ни разговора на карте.";
        }

        private static bool RotateVisuals(object visuals, float radians)
        {
            var entity = AccessTools.Method(visuals.GetType(), "GetEntity")?.Invoke(visuals, null) as GameEntity;
            if (entity == null)
            {
                return false;
            }
            var frame = entity.GetFrame();
            frame.Rotate(radians, new Vec3(0f, 0f, 1f));
            entity.SetFrame(ref frame);
            return true;
        }

        // Отладка "летающего треугольника": прячет надетый шлем у игрока/участников разговора на
        // карте. Консоль: equestria.hide_helmet
        [CommandLineFunctionality.CommandLineArgumentFunction("hide_helmet", "equestria")]
        public static string HideHelmetCommand(List<string> args)
        {
            int count = 0;
            if (Agent.Main?.AgentVisuals != null && HideEquippedHelmet(Agent.Main.AgentVisuals))
            {
                count++;
            }
            var conv2 = LastMapConversation;
            var list2 = conv2 == null ? null : AccessTools.Field(conv2.GetType(), "_agentVisuals")
                ?.GetValue(conv2) as System.Collections.IEnumerable;
            if (list2 != null)
            {
                foreach (var visuals in list2)
                {
                    if (HideEquippedHelmet(visuals))
                    {
                        count++;
                    }
                }
            }
            return count > 0 ? $"Шлем скрыт у {count} персонажей (тест)." : "Не нашёл ни игрока, ни разговора на карте.";
        }

        private static bool HideEquippedHelmet(object visuals)
        {
            if (visuals == null)
            {
                return false;
            }
            var getData = AccessTools.Method(visuals.GetType(), "GetCopyAgentVisualsData");
            var getEntity = AccessTools.Method(visuals.GetType(), "GetEntity");
            var data = getData?.Invoke(visuals, null);
            var entity = getEntity?.Invoke(visuals, null) as GameEntity;
            var skeleton = entity?.Skeleton;
            if (data == null || skeleton == null)
            {
                return false;
            }
            var equipment = AccessTools.Property(data.GetType(), "EquipmentData")?.GetValue(data) as Equipment;
            string meshName = equipment?[EquipmentIndex.Head].Item?.MultiMeshName;
            if (string.IsNullOrEmpty(meshName))
            {
                return false;
            }
            foreach (var mesh in HelmetMeshes(skeleton, meshName))
            {
                mesh.SetVisibilityMask(0);
            }
            return true;
        }

        // Отладка "летающего треугольника": печатает в eq_exceptions.log все меши скелета
        // (имя, видимость, материал, bounding box) — ищем лишнюю не-скрытую копию причёски.
        // Консоль: equestria.dump_meshes
        [CommandLineFunctionality.CommandLineArgumentFunction("dump_meshes", "equestria")]
        public static string DumpMeshesCommand(List<string> args)
        {
            int count = 0;
            if (Agent.Main?.AgentVisuals != null)
            {
                DumpVisualsMeshes(Agent.Main.AgentVisuals, "игрок");
                count++;
            }
            var conv = LastMapConversation;
            var list = conv == null ? null : AccessTools.Field(conv.GetType(), "_agentVisuals")
                ?.GetValue(conv) as System.Collections.IEnumerable;
            if (list != null)
            {
                int i = 0;
                foreach (var visuals in list)
                {
                    DumpVisualsMeshes(visuals, $"разговор #{i}");
                    count++;
                    i++;
                }
            }
            return count > 0 ? $"Мешей выгружено для {count} персонажей — смотри eq_exceptions.log."
                : "Не нашёл ни игрока, ни разговора на карте.";
        }

        private static void DumpVisualsMeshes(object visuals, string who)
        {
            if (visuals == null)
            {
                return;
            }
            var getEntity = AccessTools.Method(visuals.GetType(), "GetEntity");
            var entity = getEntity?.Invoke(visuals, null) as GameEntity;
            var skeleton = entity?.Skeleton;
            if (skeleton == null)
            {
                EquestriaCrashLog.Log($"меши[{who}]: скелета нет");
                return;
            }
            foreach (var mesh in skeleton.GetAllMeshes())
            {
                if (mesh == null)
                {
                    continue;
                }
                var min = mesh.GetBoundingBoxMin();
                var max = mesh.GetBoundingBoxMax();
                string mat = mesh.GetMaterial()?.Name ?? "(нет)";
                EquestriaCrashLog.Log($"меш[{who}]: {mesh.Name} видимость={mesh.VisibilityMask} материал={mat} "
                    + $"bbox=({min.x:0.###},{min.y:0.###},{min.z:0.###})-({max.x:0.###},{max.y:0.###},{max.z:0.###})");
            }
            int multiCount = entity?.MultiMeshComponentCount ?? 0;
            for (int i = 0; i < multiCount; i++)
            {
                var meta = entity.GetMetaMesh(i);
                if (meta == null)
                {
                    continue;
                }
                for (int j = 0; j < meta.MeshCount; j++)
                {
                    var mesh = meta.GetMeshAtIndex(j);
                    if (mesh == null)
                    {
                        continue;
                    }
                    EquestriaCrashLog.Log($"метамеш[{who}][{i}/{j}]: {mesh.Name} видимость={mesh.VisibilityMask}");
                }
            }
        }

        private static Mesh[] HelmetMeshes(Skeleton skeleton, string meshName)
        {
            var found = new List<Mesh>();
            foreach (var mesh in skeleton.GetAllMeshes())
            {
                if (mesh?.Name != null
                    && mesh.Name.StartsWith(meshName, StringComparison.OrdinalIgnoreCase))
                {
                    found.Add(mesh);
                }
            }
            return found.ToArray();
        }

        /// <summary>Подгонка по внешности — путь окон (инвентарь, отряд, цирюльник).</summary>
        /// <param name="isMapIcon">
        /// Настоящая крошечная фигурка отряда на карте (а не окно/энциклопедия поверх карты) —
        /// шлем ей прячем. Раньше это решали по ActiveState is MapState, но энциклопедия и другие
        /// окна — это ОВЕРЛЕИ поверх карты, у них ТО ЖЕ САМОЕ ActiveState. Проверка тихо прятала
        /// шлем и в энциклопедии: EquestriaBodyParts.Attach зовёт Fit на КАЖДЫЙ такт CharacterTableau
        /// (по разу за кадр), и onMap==true возвращала его невидимым сразу вслед за тем, как
        /// EquestriaHelmetFit.Tick этот же кадр только что верно поставил (замечено 25.09.2026,
        /// лог показывал успешную подгонку, а шлема на экране не было). Теперь признак приходит
        /// явно от вызывающего — тот уже знает, кто он: EquestriaBodyParts различает "PartyIcon"
        /// (настоящая карта) и "окно"/"Tableau"/"обновление" по имени, которым движок сам подписал
        /// объект внешности при создании.
        /// </param>
        public static void Fit(object visuals, int race, bool isMapIcon)
        {
            if (visuals == null || !Scales().ContainsKey(race))
            {
                return;
            }
            // НА КАРТЕ МИРА ШЛЕМ ПРОСТО ПРЯЧЕМ. Фигурку отряда игра собирает один раз и больше
            // не трогает, а опора растяжения должна идти за головой — от разовой подгонки шлем
            // уезжал вверх. Оставить его нерастянутым тоже плохо: человеческий шлем тонет в
            // крупной драконьей голове. Фигурки там с ноготь, отсутствия шлема не видно.
            bool onMap = isMapIcon;
            // Поиск методов и свойств кешируем: зовётся часто, отражение обошлось бы дорого.
            if (_getData == null || _getData.DeclaringType != visuals.GetType())
            {
                _getData = AccessTools.Method(visuals.GetType(), "GetCopyAgentVisualsData");
                _getEntity = AccessTools.Method(visuals.GetType(), "GetEntity");
                _raceData = null;
            }
            var data = _getData?.Invoke(visuals, null);
            var entity = _getEntity?.Invoke(visuals, null) as GameEntity;
            if (data == null)
            {
                return;
            }
            if (_raceData == null)
            {
                _raceData = AccessTools.Property(data.GetType(), "RaceData");
                _equipmentData = AccessTools.Property(data.GetType(), "EquipmentData");
                _monsterData = AccessTools.Property(data.GetType(), "MonsterData");
            }
            var equipment = _equipmentData?.GetValue(data) as Equipment;
            var monster = _monsterData?.GetValue(data) as Monster;
            var skeleton = entity?.Skeleton;
            string meshName = equipment?[EquipmentIndex.Head].Item?.MultiMeshName;
            if (skeleton == null || string.IsNullOrEmpty(meshName))
            {
                return;
            }
            // В окне персонаж пересобирается на каждый чих, кеш тут ни к чему — мешей ищем сразу
            sbyte bone = monster?.HeadLookDirectionBoneIndex ?? HumanHeadBone;
            sbyte mapped = skeleton.GetSkeletonBoneMapping(bone);
            var meshes = HelmetMeshes(skeleton, meshName);
            if (onMap)
            {
                foreach (var mesh in meshes)
                {
                    mesh.SetVisibilityMask(0);          // ноль — не рисовать вовсе
                }
                // Вместо спрятанного шлема возвращаем причёску: под шлемом игра её не строит,
                // и на карте дракон оставался с голой головой.
                foreach (var pair in HairByRace)
                {
                    if (TaleWorlds.Core.FaceGen.GetRaceOrDefault(pair.Key) == race)
                    {
                        EquestriaBodyParts.AttachPart(visuals, pair.Value, "карта");
                    }
                }
                return;
            }
            Fit(skeleton, meshes,
                mapped >= 0 && mapped < skeleton.GetBoneCount() ? mapped : bone, race, meshName);
        }

        private static void Fit(Skeleton skeleton, Mesh[] meshes, sbyte bone, int race, string meshName,
            Agent traceAgent = null)
        {
            if (meshes == null || meshes.Length == 0 || !Scales().TryGetValue(race, out Vec3 scale))
            {
                return;
            }
            // ОПОРА — ТЕКУЩЕЕ положение кости головы, а не поза покоя. Рамка меша применяется
            // ПОСЛЕ скиннинга, и растяжение вокруг текущей кости даёт ровно тот же результат,
            // что правильное растяжение до скиннинга вокруг кости в позе привязки (обе записи
            // сводятся к b + s*B*(v - b_bind)). Поэтому опору пересчитываем каждый кадр: от
            // разового выставления шлем поехал бы, как только персонаж двинется с места.
            MatrixFrame now = skeleton.GetBoneEntitialFrameWithIndex(bone);
            if (traceAgent != null)
            {
                // Трассировка поворота шлема (28.09.2026): сравниваем то, что реально читает наша
                // подгонка (вектор "вперёд" кости в координатах сущности), с тем, что движок сам
                // считает направлением взгляда/тела агента — чтобы понять, какую кость шлем
                // на самом деле повторяет.
                Vec3 f = now.rotation.f;
                // Единицы LookDirectionAsAngle/MovementDirectionAsAngle не проверены — пишем как
                // есть (сырым числом), разберёмся по логу: радианы уложатся в ~[-3.14;3.14],
                // градусы — в ~[-180;180] или [0;360].
                EquestriaCrashLog.Log($"шлем трассировка: кость={bone} вперёд=({f.x:0.00},{f.y:0.00},{f.z:0.00}) "
                    + $"взгляд(сырое)={traceAgent.LookDirectionAsAngle:0.000} "
                    + $"тело(сырое)={traceAgent.MovementDirectionAsAngle:0.000}");
            }
            Vec3 shift = Shift(race);

            // ОСИ РАСТЯЖЕНИЯ ПОВОРАЧИВАЕМ ВМЕСТЕ С ГОЛОВОЙ. Множитель неравномерный (шлем шире,
            // чем выше), а рамка задаёт его по осям персонажа — при повороте головы шлем каждый
            // раз растягивался по-новому и «плыл». Поэтому берём поворот головы ОТНОСИТЕЛЬНО позы
            // покоя и разворачиваем им сам масштаб: M = R * S * Rᵀ. В покое R единичный, и
            // выходит ровно прежнее поведение, так что подобранные числа не меняют смысла.
            MatrixFrame rest = skeleton.GetBoneEntitialRestFrame(bone, false);
            Vec3 c1 = now.rotation.TransformToParent(rest.rotation.TransformToLocal(new Vec3(1f, 0f, 0f)));
            Vec3 c2 = now.rotation.TransformToParent(rest.rotation.TransformToLocal(new Vec3(0f, 1f, 0f)));
            Vec3 c3 = now.rotation.TransformToParent(rest.rotation.TransformToLocal(new Vec3(0f, 0f, 1f)));
            // ПОДЪЁМ ОПОРЫ (HelmetUp) — ТОЖЕ ПО c3, не по сырой мировой Z. Кость сидит у основания
            // шеи, а центр головы — выше; раньше этот подъём шёл прямо вверх по миру, что верно
            // только когда голова смотрит ровно вперёд. При сильном наклоне головы вниз (бой,
            // осмотр земли) мировой верх и верх головы расходятся — опора уезжала назад/вверх от
            // настоящего центра головы, и затылок вылезал из-под шлема сзади (29.09.2026-правка,
            // тот же класс бага, что и с shift чуть ниже).
            Vec3 pivot = now.origin + c3 * HelmetUp;
            // столбцы M — сумма внешних произведений, по одному на ось масштаба
            Vec3 mx = c1 * (scale.x * c1.x) + c2 * (scale.y * c2.x) + c3 * (scale.z * c3.x);
            Vec3 my = c1 * (scale.x * c1.y) + c2 * (scale.y * c2.y) + c3 * (scale.z * c3.y);
            Vec3 mz = c1 * (scale.x * c1.z) + c2 * (scale.y * c2.z) + c3 * (scale.z * c3.z);
            Vec3 moved = mx * pivot.x + my * pivot.y + mz * pivot.z;
            // SHIFT ТОЖЕ ПОВОРАЧИВАЕМ ВМЕСТЕ С ГОЛОВОЙ — тем же разворотом c1/c2/c3, что и оси
            // масштаба выше. Раньше shift добавлялся сырым, в осях мира/тела: в покое (now.rotation
            // ≈ rest.rotation, c1/c2/c3 ≈ единичный базис) это не отличить от верного поведения —
            // поэтому в окнах/меню, где голова почти не отклоняется от позы покоя, шлем сидел ровно.
            // В бою голова активно поворачивается (взгляд на цель, удары, уклонения), c1/c2/c3
            // расходятся с единичным базисом — и несповёрнутый сдвиг «уезжал» в сторону от кости,
            // тем заметнее, чем больше сам shift и множитель расы (у пони и то, и другое большие).
            // Именно это и есть «рассинхронизация шлема в бою», не частота пересчёта.
            Vec3 shiftRotated = c1 * shift.x + c2 * shift.y + c3 * shift.z;
            foreach (var mesh in meshes)
            {
                // Рамку задаём АБСОЛЮТНО, а не накапливаем: исходная всегда нулевая (вершины
                // доспеха записаны в координатах тела), поэтому повторный вызов ничего не портит.
                var frame = MatrixFrame.Identity;
                frame.rotation.s = mx;
                frame.rotation.f = my;
                frame.rotation.u = mz;
                frame.origin = pivot - moved + shiftRotated;
                mesh.SetLocalFrame(frame);
            }
            if (_shiftLoggedMeshes.Add(meshName))
            {
                EquestriaCrashLog.Log($"шлем под расу: {meshName} растянут в "
                    + $"({scale.x:0.00},{scale.y:0.00},{scale.z:0.00}) раза ({meshes.Length} мешей) "
                    + $"вокруг кости {bone} ({skeleton.GetBoneName(bone)}) на высоте {pivot.z:0.00}");
            }
        }

        /// <summary>
        /// Подгонка каждый кадр в окнах: энциклопедия, отряд, снаряжение.
        ///
        /// Разовой подгонки при сборке не хватает. Рамка меша задаётся В КООРДИНАТАХ ПЕРСОНАЖА и
        /// считается вокруг ТЕКУЩЕГО положения кости головы; в окне персонажа собирают в одной
        /// позе, а потом проигрывают стойку — голова уезжает, и шлем при множителе около двух
        /// оказывается в стороне от неё (в энциклопедии он висел выше и правее головы, замечено
        /// 25.09.2026). В бою этого не было: там подгонка и так идёт каждый кадр.
        /// </summary>
        public static void Tick(object visuals)
        {
            // Проверку "ActiveState is MapState" здесь держали как отсечку "мы — крошечная
            // иконка отряда на карте, туда не лезем". Ошиблись с самим состоянием: у окна
            // энциклопедии, открытого поверх карты, ActiveState — ТОТ ЖЕ MapState (это оверлей,
            // не отдельное игровое состояние). Проверка тихо выключала подгонку и в энциклопедии
            // тоже — в логе не было ни одной строки о ней (замечено 25.09.2026). Крошечную иконку
            // прячет отдельно Fit(object, int) при сборке (mesh.SetVisibilityMask(0)); перерисовать
            // ей ещё и рамку — не вредно, невидимый меш просто передвинется невидимо.
            if (visuals == null)
            {
                return;
            }
            Tick(visuals, "кадр окна");
        }

        /// <summary>
        /// Разовая подгонка для картинок-заготовок: миниатюры в дереве войск, лица в списках.
        ///
        /// Их рисуют так: собирают персонажа, задают позу и один раз проигрывают анимацию
        /// (CharacterSpawner.InitWithCharacter -> TickAnimationsAndForceUpdate), потом снимают
        /// картинку. Наша подгонка при сборке доспеха случается ДО этой анимации, то есть по позе
        /// покоя, — и на миниатюре шлем висел в стороне от головы, хотя в большом окне сидел верно
        /// (замечено 25.09.2026). Поэтому подгоняем ещё раз, когда поза уже проиграна.
        ///
        /// Проверку «мы на карте» тут не делаем нарочно: энциклопедию открывают и с карты мира,
        /// а миниатюра статична — один верный расчёт ей и нужен.
        /// </summary>
        public static void FitStatic(object visuals)
        {
            if (visuals != null)
            {
                Tick(visuals, "заготовка");
            }
        }

        // Раньше здесь было ускорение — переиспользовать запомненные меши по нескольку кадров
        // подряд, перечитывая внешность раз в 15 кадров. Сломало и большое окно, и заготовки: окна
        // персонажей переиспользуют один и тот же объект внешности при переключении войска в
        // дереве (замечено 25.09.2026), и залежавшийся кеш держал меши ПРЕЖНЕГО персонажа, пока не
        // истекут кадры, — шлем не подгонялся вовсе. Читаем внешность заново на каждый вызов: тут
        // не бой на тысячу бойцов, а окно с одним-двумя персонажами, лишний мусор не страшен.
        private static void Tick(object visuals, string where)
        {
            EquestriaCrashLog.Try("шлем под расу (" + where + ")", () =>
            {
                if (_getEntity == null || _getEntity.DeclaringType != visuals.GetType())
                {
                    _getData = AccessTools.Method(visuals.GetType(), "GetCopyAgentVisualsData");
                    _getEntity = AccessTools.Method(visuals.GetType(), "GetEntity");
                    _raceData = null;
                }
                var skeleton = (_getEntity?.Invoke(visuals, null) as GameEntity)?.Skeleton;
                if (skeleton == null)
                {
                    return;
                }
                var kept = Read(visuals, skeleton);
                if (kept != null && kept.Meshes.Length > 0)
                {
                    Fit(skeleton, kept.Meshes, kept.Bone, kept.Race, kept.MeshName);
                }
                else if (kept != null && _shiftLoggedMeshes.Add("!missing:" + kept.MeshName))
                {
                    // Раса своя, шлем в снаряжении есть, а мешей на скелете не нашлось — на всякий
                    // случай смотрим, если подгонка снова где-то замолчит. По имени меша, а не
                    // одноразово: иначе первый же промах навсегда скроет остальные.
                    EquestriaCrashLog.Warn($"шлем под расу ({where}): меш {kept.MeshName}"
                        + $" не найден на скелете (мешей всего {skeleton.GetAllMeshes().Count()})");
                }
            });
        }

        /// <summary>Разобрать внешность: раса, меши шлема, кость головы. null — шлема нет.</summary>
        private static Fitted Read(object visuals, Skeleton skeleton)
        {
            var data = _getData?.Invoke(visuals, null);
            if (data == null)
            {
                return null;
            }
            if (_raceData == null)
            {
                _raceData = AccessTools.Property(data.GetType(), "RaceData");
                _equipmentData = AccessTools.Property(data.GetType(), "EquipmentData");
                _monsterData = AccessTools.Property(data.GetType(), "MonsterData");
            }
            if (!(_raceData?.GetValue(data) is int race) || !Scales().ContainsKey(race))
            {
                return null;
            }
            string meshName = (_equipmentData?.GetValue(data) as Equipment)?[EquipmentIndex.Head]
                .Item?.MultiMeshName;
            if (string.IsNullOrEmpty(meshName))
            {
                return null;
            }
            sbyte bone = (_monsterData?.GetValue(data) as Monster)?.HeadLookDirectionBoneIndex ?? HumanHeadBone;
            sbyte mapped = skeleton.GetSkeletonBoneMapping(bone);
            return new Fitted
            {
                MeshName = meshName,
                Meshes = HelmetMeshes(skeleton, meshName),
                Bone = mapped >= 0 && mapped < skeleton.GetBoneCount() ? mapped : bone,
                Race = race,
            };
        }

        private static void AfterArmour(object __instance)
        {
            EquestriaCrashLog.Try("шлем под расу (доспех)", () =>
            {
                var data = AccessTools.Method(__instance.GetType(), "GetCopyAgentVisualsData")
                    ?.Invoke(__instance, null);
                var race = data == null ? null
                    : AccessTools.Property(data.GetType(), "RaceData")?.GetValue(data);
                if (race is int id)
                {
                    // Настоящую карточную иконку прячет EquestriaBodyParts.Attach (он видит имя,
                    // которым движок подписал объект внешности); отсюда — никогда не прячем, чтобы
                    // не спрятать шлем окну по ошибке ещё до того, как Attach разберётся, кто это.
                    Fit(__instance, id, isMapIcon: false);
                }
            });
        }

        private static void AfterBuild()
        {
            _building = 0;
        }

        private static void AfterTick(object __instance)
        {
            Tick(__instance);
        }

        private static bool _spawnerLogged;

        private static void AfterSpawner(object __instance)
        {
            EquestriaCrashLog.Try("шлем под расу (заготовка собрана)", () =>
            {
                var field = AccessTools.Field(__instance.GetType(), "_agentVisuals");
                var visuals = field?.GetValue(__instance);
                if (!_spawnerLogged)
                {
                    _spawnerLogged = true;
                    EquestriaCrashLog.Log($"шлем под расу: заготовка {__instance.GetType().Name}"
                        + $" — поле _agentVisuals {(field == null ? "НЕ НАЙДЕНО" : "есть")},"
                        + $" значение {(visuals == null ? "пусто" : "есть")}");
                }
                FitStatic(visuals);
            });
        }

        private static bool _mapConvLogged;

        public static object LastMapConversation { get; private set; }

        // Тикаем ВЕСЬ список внешностей разговора, а не только говорящего (см. комментарий у
        // патча в Apply). Список приватный (List<AgentVisuals>), достаём его отражением один раз
        // на класс — как и в остальных местах файла, тип у всех вызовов один и тот же.
        private static void AfterMapConversationTick(object __instance)
        {
            LastMapConversation = __instance;
            EquestriaCrashLog.Try("шлем под расу (разговор на карте)", () =>
            {
                var list = AccessTools.Field(__instance.GetType(), "_agentVisuals")
                    ?.GetValue(__instance) as System.Collections.IEnumerable;
                if (list == null)
                {
                    return;
                }
                // У разговора на карте нет CharacterObjectStringIdData во внешности (проверено
                // логом: null у всех участников) — зато у самого полотна есть _data с двумя
                // явными персонажами (игрок и собеседник). По ИНДЕКСУ в списке их не отличить
                // надёжно (порядок оказался не "игрок, потом собеседник" — первый тест окрасил не
                // того), поэтому сверяем BodyProperties каждой внешности (AgentVisualsData.
                // BodyPropertiesData) с BodyProperties игрока/собеседника: это те же самые данные,
                // ключ совпадает побайтово у одного и того же персонажа, независимо от позиции
                // в списке. Эскорт лорда своего Hero не имеет — его BodyProperties ни с кем не
                // совпадёт, и он останется некрашеным (это не главные персонажи).
                var conv = ConversationCharacterKeys(__instance);
                int count = 0;
                foreach (var visuals in list)
                {
                    Tick(visuals, "разговор");
                    // Разговор на карте собирает участников СВОИМ путём — EquestriaBodyParts.Attach
                    // к его такту не подключён (хвост/крылья/рог приходят через AgentVisuals.Create/
                    // Refresh где-то выше по цепочке, а лор-цвет там иногда не долетает — например,
                    // если CharacterObjectStringIdData к моменту Create ещё пуст). Красим и крепим
                    // части тела ЕЩЁ РАЗ прямо здесь, заведомо рабочим путём — Attach идемпотентен.
                    AttachAndColorConversationParticipant(visuals, conv);
                    count++;
                }
                if (!_mapConvLogged)
                {
                    _mapConvLogged = true;
                    EquestriaCrashLog.Log($"шлем под расу: разговор на карте — участников {count}");
                }
            });
        }

        // Раса и BodyProperties персонажа — тем же способом, что Read() выше
        // (GetCopyAgentVisualsData), но отдельным кэшем метода: тип внешности участников
        // разговора — не обязательно тот же, что у _getData/_raceData (те кэшируются под
        // последний вызов обычного Tick).
        private static System.Reflection.MethodInfo _convGetData;
        private static System.Reflection.PropertyInfo _convRaceData;
        private static System.Reflection.PropertyInfo _convBodyData;

        // Кто есть кто в разговоре. По ИНДЕКСУ в _agentVisuals отличить игрока/собеседника
        // ненадёжно (первый тест окрасил не того — порядок не "игрок, потом собеседник", как
        // ожидалось), поэтому сверяем BodyProperties: у одного и того же персонажа ключ
        // побайтово совпадает что у Hero, что у его внешности в разговоре, независимо от
        // позиции в списке.
        private struct ConvKeys
        {
            public string PlayerKey, PlayerId, PartnerKey, PartnerId;
        }

        private static System.Reflection.FieldInfo _dataField;
        private static System.Reflection.PropertyInfo _playerCharData, _partnerCharData;
        private static System.Reflection.FieldInfo _charField;

        private static ConvKeys ConversationCharacterKeys(object tableau)
        {
            if (_dataField == null || _dataField.DeclaringType != tableau.GetType())
            {
                _dataField = AccessTools.Field(tableau.GetType(), "_data");
            }
            var data = _dataField?.GetValue(tableau);
            if (data == null)
            {
                return default;
            }
            if (_playerCharData == null || _playerCharData.DeclaringType != data.GetType())
            {
                _playerCharData = AccessTools.Property(data.GetType(), "PlayerCharacterData");
                _partnerCharData = AccessTools.Property(data.GetType(), "ConversationPartnerData");
            }
            CharacterIdAndKey(_playerCharData?.GetValue(data), out string playerId, out string playerKey);
            CharacterIdAndKey(_partnerCharData?.GetValue(data), out string partnerId, out string partnerKey);
            return new ConvKeys { PlayerKey = playerKey, PlayerId = playerId, PartnerKey = partnerKey, PartnerId = partnerId };
        }

        // ConversationCharacterData.Character (CharacterObject) — публичное поле, не свойство.
        // BodyProperties берём с HeroObject: у самого CharacterObject-шаблона своей уникальной
        // внешности нет, она только у конкретного живого Hero.
        private static void CharacterIdAndKey(object conversationCharacterData, out string id, out string bodyKey)
        {
            id = null;
            bodyKey = null;
            if (conversationCharacterData == null)
            {
                return;
            }
            if (_charField == null || _charField.DeclaringType != conversationCharacterData.GetType())
            {
                _charField = AccessTools.Field(conversationCharacterData.GetType(), "Character");
            }
            var character = _charField?.GetValue(conversationCharacterData);
            if (character == null)
            {
                return;
            }
            id = AccessTools.Property(character.GetType(), "StringId")?.GetValue(character) as string;
            var hero = AccessTools.Property(character.GetType(), "HeroObject")?.GetValue(character);
            object bodyProps = hero == null
                ? null
                : AccessTools.Property(hero.GetType(), "BodyProperties")?.GetValue(hero);
            bodyKey = bodyProps?.ToString();
        }

        private static void AttachAndColorConversationParticipant(object visuals, ConvKeys conv)
        {
            EquestriaCrashLog.Try("части тела и цвет (разговор)", () =>
            {
                if (_convGetData == null || _convGetData.DeclaringType != visuals.GetType())
                {
                    _convGetData = AccessTools.Method(visuals.GetType(), "GetCopyAgentVisualsData");
                    _convRaceData = null;
                    _convBodyData = null;
                }
                var data = _convGetData?.Invoke(visuals, null);
                if (data == null)
                {
                    return;
                }
                if (_convRaceData == null)
                {
                    _convRaceData = AccessTools.Property(data.GetType(), "RaceData");
                    _convBodyData = AccessTools.Property(data.GetType(), "BodyPropertiesData");
                }
                if (!(_convRaceData?.GetValue(data) is int race))
                {
                    return;
                }
                string bodyKey = _convBodyData?.GetValue(data)?.ToString();
                string charStringId = bodyKey != null && bodyKey == conv.PartnerKey ? conv.PartnerId
                    : bodyKey != null && bodyKey == conv.PlayerKey ? conv.PlayerId
                    : null;
                EquestriaBodyParts.Attach(visuals, race, "разговор", cacheKey: visuals);
                EquestriaBodyParts.ApplyLoreColorIfPony(visuals, race, charStringId);
            });
        }

        private const sbyte HumanHeadBone = 13;
        private static bool _boneLogged;

        private static void AfterBone(Monster __instance, ref sbyte __result)
        {
            if (__result >= 0 || __instance == null || string.IsNullOrEmpty(__instance.StringId))
            {
                return;
            }
            // только наши расы: у ванильных монстров номер и так верный
            if (!Scales().Keys.Any() || !ScaleByRace.Keys.Any(r => __instance.StringId.StartsWith(r)))
            {
                return;
            }
            __result = HumanHeadBone;
            if (!_boneLogged)
            {
                _boneLogged = true;
                EquestriaCrashLog.Log($"шлем под расу: у монстра {__instance.StringId} кость головы "
                    + $"была -1, подставлена {HumanHeadBone}");
            }
        }


    }
}
