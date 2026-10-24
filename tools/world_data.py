# Table of the world: the Equus kingdoms, their clans, lords, families, relations and settlements.
#
# All campaign XML is generated from here (tools/make_world.py). Edit the world here, not in the XML -
# otherwise the links between files (clan -> kingdom -> holdings -> lords -> families) drift apart.
#
# Names and rulers are taken from docs/lore/equestria_at_war.md and docs/lore/mlp_lore.md.
#
# Cultures and kingdoms take over VANILLA ids (empire, vlandia, ...) - the same as
# The Old Realms does. Reason: the game code has hard-coded references to these ids (for example, the list
# of six cultures at character creation). A custom culture with a new id will not replace them.

# The map is 1024x1024 m after the Equestria at War reference (tools/make_equus_map.py, tools/equus_map.py).
# Settlements are placed at EaW cities: each kingdom has its own EaW countries ("eaw"),
# the capital is "capital".
MAP_SIZE = 1024.0

# Which EaW cities become which settlement: by the city's "victory points" (victory_points).
TOWN_VALUE = 15      # from 15 - town
CASTLE_VALUE = 5     # from 5 to 15 - castle, less - village

# Gender: "f" - female, "m" - male.
# Unique looks of named heroes: a ready BodyProperties key (taken in the appearance editor -
# the mod writes it to the log, see EquestriaShowcase.WatchBodyProperties). A character's XML cannot
# set the face variant by tag (face_textures in skins.xml), and for Chrysalis exactly that gives green
# eyes with slit pupils ("skin type" 4 of the changeling race).
# Per-hero equipment on top of the kingdom set. Chrysalis used to have her own horn with a crown here
# (eq_chrysalis_crown) - an item from the old changeling model. The new model came with its own horn
# in the head, and the packages have no crown mesh at all, so the reference gave "Unable to find mesh".
# Until the crown is redrawn, the queen wears an ordinary helmet of her kingdom.
HERO_GEAR = {}

FACE_KEYS = {
    "chrysalis": "00109C0D8000334D59A4894CAAA8A4A6BC7262A86699976479AD7D8A99877A3A"
                 "007886030768E986000000000000000000000000000000000000000000FC1142",
}


ALL_KINGDOMS = [
    # ---- Equestria, divided among four princesses (like the three Empires in vanilla). They all share
    # one culture - Equestrian. The lands of the EaW country EQS are split among them by proximity to "seat",
    # the capitals are assigned to their own princesses.
    {
        "culture": "empire",
        "ruler_title": "Принцесса",
        "kingdom": "kingdom_equestria",
        "name": "Солнечная Эквестрия",
        "short": "Солнечная Эквестрия",
        "title": "Солнечная Эквестрия",
        "color": "FFE8B53A",
        "color2": "FFFFF6E0",
        # Kingdom banner - the sun (icon numbers are in Native/ModuleData/banner_icons.xml)
        "emblem": 411,
        "text": "Сердце Эквестрии под рукой принцессы Селестии, что поднимает солнце. Кантерлот, "
                "старая знать и Королевская стража — самая древняя и гордая из четырёх Эквестрий.",
        # Clans. The first hero of a clan is its leader (alive and adult).
        #   heroes:    (id, name, gender, age, description)
        #   dead:      heroes who are no longer alive (parents, ancestors) - needed for the family tree
        #   marriages: (he/she, he/she)
        #   children:  (child, father, mother) - parents may be from another clan
        #   emblem:    clan banner icon; color/color2 - background and icon (ARGB)
        "clans": [
            {
                "id": "clan_eq_royal", "color": "FFFFF6E0", "color2": "FFE8B53A", "name": "Дом Солнца", "tier": 6, "ruling": True,
                "emblem": 411,  # sun
                "heroes": [
                    ("celestia", "Селестия", "f", 60, "Старшая сестра, поднимающая солнце. Правит Эквестрией тысячу лет."),
                    ("blueblood", "Принц Блюблад", "m", 30, "Дальний родственник принцесс, кантерлотский сноб."),
                ],
            },
            {
                "id": "clan_eq_wonderbolt", "color": "FF1F4E9A", "color2": "FFF4D03F", "name": "Вандерболты", "tier": 5,
                "emblem": 115,  # flying bird
                "heroes": [
                    ("spitfire", "Спитфайр", "f", 32, "Командир Вандерболтов, лучшая лётчица Эквестрии."),
                    ("soarin", "Сорин", "m", 31, "Ведомый Спитфайр."),
                    ("fleetfoot", "Флитфут", "f", 29, "Пилот пилотажной группы."),
                    ("misty_fly", "Мисти Флай", "f", 28, "Пилот пилотажной группы."),
                    ("lightning_dust", "Лайтнинг Даст", "f", 25, "Отчисленная кадетка, дерзкая и опасная."),
                ],
            },
            {
                "id": "clan_eq_pants", "color": "FF2C3E50", "color2": "FFD4AF37", "name": "Дом Фэнси Пэнтс", "tier": 4,
                "emblem": 340,  # crown - Canterlot nobility
                "heroes": [
                    ("fancy_pants", "Фэнси Пэнтс", "m", 40, "Кантерлотский аристократ, законодатель мод высшего света."),
                    ("fleur", "Флёр де Лис", "f", 34, "Модель, спутница Фэнси Пэнтса."),
                ],
                "marriages": [("fancy_pants", "fleur")],
            },
            {
                "id": "clan_eq_guard", "color": "FF2E4053", "color2": "FFE8B53A", "name": "Королевская стража", "tier": 4,
                "emblem": 316,  # shield
                "heroes": [
                    ("flash_sentry", "Флэш Сентри", "m", 24, "Капитан дворцовой стражи Кантерлота."),
                    ("gleaming_shield", "Глиминг Шилд", "f", 30, "Офицер стражи, давняя сослуживица Шайнинг Армора."),
                    ("thunderlane", "Тандерлейн", "m", 26, "Пегас-стражник из Понивилля."),
                ],
            },
            {
                "id": "clan_eq_rich", "color": "FF6D4C41", "color2": "FFE5C07B", "name": "Дом Рич", "tier": 3,
                "emblem": 335,  # horseshoe
                "heroes": [
                    ("filthy_rich", "Филти Рич", "m", 46, "Богатейший торговец Понивилля, владелец «Барнис энд Кобл»."),
                    ("spoiled_rich", "Спойлд Рич", "f", 42, "Жена Филти Рича, заносчивая и властная."),
                    ("diamond_tiara", "Даймонд Тиара", "f", 13, "Дочь Ричей, школьная задира."),
                    ("silver_spoon", "Сильвер Спун", "f", 13, "Лучшая подруга Даймонд Тиары."),
                ],
                "marriages": [("filthy_rich", "spoiled_rich")],
                "children": [("diamond_tiara", "filthy_rich", "spoiled_rich")],
            },
        ],
        # Friendship and enmity: (hero, hero, relation from -100 to 100). Relations apply to the whole
        # world, no matter in which kingdom they are written.
        "relations": [
            # Celestia and her family, students
            ("celestia", "luna", 90),
            ("celestia", "twilight", 95),
            ("celestia", "cadance", 80),
            ("luna", "twilight", 70),
            ("celestia", "blueblood", 10),
            ("twilight", "starlight", 85),
            ("starlight", "sunburst", 80),
            ("starlight", "trixie", 85),
            ("twilight", "trixie", -20),
            ("twilight", "sunburst", 50),
            ("twilight", "shining_armor", 95),
            ("twilight", "cadance", 90),
            ("twilight", "spike", 100),
            # The Mane Six, Elements of Harmony
            ("twilight", "applejack", 90), ("twilight", "rainbow_dash", 85), ("twilight", "rarity", 90),
            ("twilight", "pinkie", 90), ("twilight", "fluttershy", 90),
            ("applejack", "rainbow_dash", 80), ("applejack", "rarity", 75), ("applejack", "pinkie", 85),
            ("applejack", "fluttershy", 85), ("rainbow_dash", "rarity", 70), ("rainbow_dash", "pinkie", 85),
            ("rainbow_dash", "fluttershy", 90), ("rarity", "pinkie", 80), ("rarity", "fluttershy", 90),
            ("pinkie", "fluttershy", 85),
            ("rarity", "spike", 70),
            # Cutie Mark Crusaders
            ("apple_bloom", "sweetie_belle", 95), ("apple_bloom", "scootaloo", 95),
            ("sweetie_belle", "scootaloo", 95), ("rainbow_dash", "scootaloo", 90),
            ("diamond_tiara", "apple_bloom", -40), ("diamond_tiara", "sweetie_belle", -40),
            ("diamond_tiara", "scootaloo", -40), ("diamond_tiara", "silver_spoon", 70),
            # Wonderbolts
            ("spitfire", "rainbow_dash", 70), ("spitfire", "soarin", 80), ("spitfire", "fleetfoot", 60),
            ("spitfire", "lightning_dust", -50), ("rainbow_dash", "lightning_dust", -60),
            # Nobility
            ("rarity", "fancy_pants", 60), ("rarity", "blueblood", -50), ("fancy_pants", "blueblood", -10),
            ("spoiled_rich", "applejack", -30), ("filthy_rich", "applejack", 20),
            ("granny_smith", "grand_pear", -30),
            # Families and guards
            ("pinkie", "maud", 95), ("maud", "limestone", 50), ("limestone", "pinkie", 30),
            ("fluttershy", "zephyr", 20), ("big_mac", "applejack", 90),
            ("shining_armor", "flash_sentry", 60), ("shining_armor", "gleaming_shield", 70),
            ("celestia", "flash_sentry", 40), ("luna", "flash_sentry", 30),
            ("rainbow_dash", "thunderlane", 30),
            # sisters and princesses
            ("luna", "starswirl", 60), ("luna", "somnambula", 50), ("cadance", "radiant_hope", 70),
            ("cadance", "sunburst", 75), ("sunburst", "stellar_flare", 60), ("luna", "nightshade", 80),
            ("stygian", "starswirl", -20), ("sombra", "cadance", -90), ("sombra", "shining_armor", -80),
        ],
        "eaw": ["EQS"],
        "capital": "Кантерлот",
        "power": 1.15,
        "anchors": ["Кантерлот", "Мейнхеттен", "Филлидельфия", "Балтимейр", "Альбион"],
    },
    {
        "culture": "empire",
        "ruler_title": "Принцесса",
        "kingdom": "kingdom_lunar",
        "name": "Лунная Эквестрия",
        "short": "Лунная Эквестрия",
        "title": "Лунная Эквестрия",
        "color": "FF1B2A5E",
        "color2": "FFC9D6FF",
        "emblem": 516,
        "text": "Западные земли принцессы Луны: города ночных огней, фестралы Ночной стражи и "
                "герои древности, вернувшиеся из Лимба. Здесь ночь — не время страха, а время снов.",
        "clans": [
            {
                "id": "clan_lu_night", "name": "Дом Ночи", "tier": 6, "ruling": True,
                "color": "FF1B2A5E", "color2": "FFC9D6FF", "emblem": 516,
                "heroes": [
                    ("luna", "Луна", "f", 56, "Младшая сестра, хранительница ночи и снов. Вернулась после тысячи лет изгнания."),
                    ("moon_dancer", "Мун Дансер", "f", 26, "Кантерлотская единорожка, ставшая звездочётом при дворе Луны."),
                ],
            },
            {
                "id": "clan_lu_guard", "name": "Ночная стража", "tier": 4,
                "color": "FF2C2C54", "color2": "FFB388FF", "emblem": 316,
                "heroes": [
                    ("nightshade", "Найтшейд", "f", 30, "Капитан Ночной стражи, фестралка, что ходит тише тени."),
                    ("moonlight_raven", "Мунлайт Рейвен", "m", 34, "Командир летучих дозоров."),
                    ("dusk_shine", "Даск Шайн", "m", 27, "Страж снов, охотник на кошмары."),
                ],
            },
            {
                "id": "clan_lu_pillars", "name": "Столпы Эквестрии", "tier": 5,
                "color": "FF4A3B6B", "color2": "FFE8D8A0", "emblem": 340,
                "heroes": [
                    ("starswirl", "Старсвирл Бородатый", "m", 90, "Величайший волшебник древности, вернувшийся из Лимба."),
                    ("somnambula", "Сомнамбула", "f", 40, "Героиня пустынь, воплощение надежды."),
                    ("mistmane", "Мистмейн", "f", 70, "Волшебница, подарившая свою красоту ради родного края."),
                    ("rockhoof", "Рокхуф", "m", 55, "Силач с лопатой, спасший деревню от вулкана."),
                    ("flash_magnus", "Флэш Магнус", "m", 45, "Отважный пегас-воин древней Клаудсдейлской армии."),
                    ("meadowbrook", "Мэдоубрук", "f", 50, "Целительница из болотных земель."),
                ],
            },
            {
                "id": "clan_lu_shadow", "name": "Дом Тени", "tier": 3,
                "color": "FF212121", "color2": "FF7E57C2", "emblem": 518,
                "heroes": [
                    ("stygian", "Стигиан", "m", 50, "Бывший Пони Теней, ищущий искупления."),
                    ("tantabus_keeper", "Эклипс Мист", "f", 32, "Хранительница Тантабуса, запертого в лунной башне."),
                ],
            },
        ],
        "eaw": ["EQS"],
        "capital": "Лас-Пегасус",
        "power": 1.08,
        "anchors": ["Лас-Пегасус", "Пранциско", "Толл Тейл", "Ванхувер", "Роквилль", "Хэйстин"],
    },
    {
        "culture": "empire",
        "ruler_title": "Принцесса",
        "kingdom": "kingdom_friendship",
        "name": "Эквестрия Дружбы",
        "short": "Эквестрия Дружбы",
        "title": "Эквестрия Дружбы",
        "color": "FF6B3FA0",
        "color2": "FFF26BB5",
        "emblem": 518,
        "text": "Земли принцессы Твайлайт и Элементов Гармонии: Понивилль, Замок Дружбы и шумные "
                "города восточного побережья. Здесь верят, что дружба сильнее любой армии, — но армию держат.",
        "clans": [
            {
                "id": "clan_eq_sparkle", "color": "FF6B3FA0", "color2": "FFF26BB5", "name": "Дом Спаркл", "tier": 6, "ruling": True,
                "emblem": 518,  # six-pointed star - Twilight's cutie mark
                "heroes": [
                    ("twilight", "Твайлайт Спаркл", "f", 26, "Принцесса дружбы, ученица Селестии и сильнейшая волшебница поколения."),
                    ("night_light", "Найт Лайт", "m", 56, "Отец Твайлайт и Шайнинг Армора, кантерлотский астроном."),
                    ("velvet", "Твайлайт Вельвет", "f", 54, "Мать Твайлайт, писательница приключенческих романов."),
                    ("spike", "Спайк", "m", 16, "Дракончик, выращенный Твайлайт. Её помощник и верный друг."),
                ],
                "marriages": [("night_light", "velvet")],
                "children": [("twilight", "night_light", "velvet")],
            },
            {
                "id": "clan_eq_apple", "color": "FFE0862F", "color2": "FFC0392B", "name": "Семья Эппл", "tier": 4,
                "emblem": 211,  # apple
                "heroes": [
                    ("applejack", "Эпплджек", "f", 24, "Хозяйка Сладкого Яблока, честнейшая пони Эквестрии."),
                    ("big_mac", "Биг Макинтош", "m", 28, "Старший брат Эпплджек, тягловая сила фермы."),
                    ("apple_bloom", "Эппл Блум", "f", 14, "Младшая сестра, основательница Меткоискателей."),
                    ("granny_smith", "Бабуля Смит", "f", 80, "Основательница Понивилля и старейшина семьи Эппл."),
                    ("sugar_belle", "Шугар Белль", "f", 26, "Пекарша, жена Биг Макинтоша."),
                    ("braeburn", "Брейберн", "m", 25, "Кузен Эпплджек из Эпплузы."),
                    ("bright_mac", "Брайт Мак", "m", 50, "Отец Эпплджек. Погиб, когда дети были маленькими."),
                    ("pear_butter", "Пир Баттер", "f", 48, "Мать Эпплджек, из семьи Пир. Погибла вместе с мужем."),
                    ("grand_pear", "Гранд Пир", "m", 82, "Отец Пир Баттер, давний соперник семьи Эппл."),
                ],
                "dead": ["bright_mac", "pear_butter"],
                "marriages": [("bright_mac", "pear_butter"), ("big_mac", "sugar_belle")],
                "children": [
                    ("bright_mac", None, "granny_smith"),
                    ("pear_butter", "grand_pear", None),
                    ("applejack", "bright_mac", "pear_butter"),
                    ("big_mac", "bright_mac", "pear_butter"),
                    ("apple_bloom", "bright_mac", "pear_butter"),
                ],
            },
            {
                "id": "clan_eq_dash", "color": "FF7EC8F0", "color2": "FFE74C3C", "name": "Дом Дэш", "tier": 3,
                "emblem": 524,  # lightning bolt - Rainbow Dash's cutie mark
                "heroes": [
                    ("rainbow_dash", "Рэйнбоу Дэш", "f", 24, "Быстрейшая пегаска Эквестрии, воплощение верности."),
                    ("bow_hothoof", "Боу Хотхуф", "m", 50, "Отец Рэйнбоу Дэш, её самый громкий болельщик."),
                    ("windy_whistles", "Винди Висслс", "f", 48, "Мать Рэйнбоу Дэш."),
                    ("scootaloo", "Скуталу", "f", 13, "Меткоискательница, для которой Рэйнбоу — старшая сестра."),
                ],
                "marriages": [("bow_hothoof", "windy_whistles")],
                "children": [("rainbow_dash", "bow_hothoof", "windy_whistles")],
            },
            {
                "id": "clan_eq_belle", "color": "FFF5F5F5", "color2": "FF3E6FD8", "name": "Дом Белль", "tier": 3,
                "emblem": 512,  # diamond - Rarity's cutie mark
                "heroes": [
                    ("rarity", "Рарити", "f", 25, "Модельер из Понивилля, воплощение щедрости."),
                    ("sweetie_belle", "Свити Белль", "f", 13, "Младшая сестра Рарити, Меткоискательница."),
                    ("hondo_flanks", "Хондо Флэнкс", "m", 52, "Отец Рарити."),
                    ("cookie_crumbles", "Куки Крамблс", "f", 50, "Мать Рарити."),
                ],
                "marriages": [("hondo_flanks", "cookie_crumbles")],
                "children": [
                    ("rarity", "hondo_flanks", "cookie_crumbles"),
                    ("sweetie_belle", "hondo_flanks", "cookie_crumbles"),
                ],
            },
            {
                "id": "clan_eq_pie", "color": "FFF48FB1", "color2": "FF4FC3F7", "name": "Семья Пай", "tier": 3,
                "emblem": 516,  # star
                "heroes": [
                    ("pinkie", "Пинки Пай", "f", 25, "Устроительница праздников, воплощение смеха."),
                    ("maud", "Мод Пай", "f", 27, "Старшая сестра Пинки, знаток камней."),
                    ("limestone", "Лаймстоун Пай", "f", 29, "Хозяйка каменной фермы, суровая и строгая."),
                    ("marble", "Марбл Пай", "f", 24, "Самая тихая из сестёр Пай."),
                    ("igneous", "Игнеус Рок Пай", "m", 58, "Отец сестёр Пай, каменный фермер."),
                    ("cloudy_quartz", "Клауди Кварц", "f", 56, "Мать сестёр Пай."),
                ],
                "marriages": [("igneous", "cloudy_quartz")],
                "children": [
                    ("pinkie", "igneous", "cloudy_quartz"),
                    ("maud", "igneous", "cloudy_quartz"),
                    ("limestone", "igneous", "cloudy_quartz"),
                    ("marble", "igneous", "cloudy_quartz"),
                ],
            },
            {
                "id": "clan_eq_shy", "color": "FFFBEA8C", "color2": "FFF28DB2", "name": "Дом Шай", "tier": 3,
                "emblem": 157,  # swan
                "heroes": [
                    ("fluttershy", "Флаттершай", "f", 25, "Смотрительница зверей, воплощение доброты."),
                    ("zephyr", "Зефир Бриз", "m", 23, "Младший брат Флаттершай, вечный бездельник."),
                    ("gentle_breeze", "Джентл Бриз", "m", 55, "Отец Флаттершай."),
                    ("posey_shy", "Поузи Шай", "f", 53, "Мать Флаттершай."),
                ],
                "marriages": [("gentle_breeze", "posey_shy")],
                "children": [
                    ("fluttershy", "gentle_breeze", "posey_shy"),
                    ("zephyr", "gentle_breeze", "posey_shy"),
                ],
            },
            {
                "id": "clan_eq_glimmer", "color": "FF8E6BBF", "color2": "FF3AB0C8", "name": "Школа Дружбы", "tier": 3,
                "emblem": 517,  # pentagram - magic
                "heroes": [
                    ("starlight", "Старлайт Глиммер", "f", 26, "Бывшая предводительница «равных», ученица Твайлайт."),
                    ("trixie", "Трикси Луламун", "f", 25, "Великая и могущественная фокусница, подруга Старлайт."),
                ],
            },
        ],
        # STG is shared with the Crystal Empire: its southern part borders the east coast
        "eaw": ["EQS"],
        "capital": "Понивилль",
        "power": 1.02,
        "anchors": ["Понивилль", "Клаудсдейл", "Кэрроттоп", "Ферма Камней Семьи Пай"],
    },
    {
        "culture": "empire",
        "ruler_title": "Принцесса",
        "kingdom": "kingdom_crystal",
        "name": "Кристальная Империя",
        "short": "Кристальная Империя",
        "title": "Кристальная Империя",
        "color": "FF5BC8E8",
        "color2": "FFF5A9C8",
        "emblem": 514,
        "text": "Северная империя кристальных пони под рукой принцессы Кейденс, союзница Эквестрии. "
                "Пока Кристальное Сердце на месте, холод и тьма Сомбры сюда не вернутся.",
        "clans": [
            {
                "id": "clan_eq_amore", "color": "FFF5A9C8", "color2": "FF7E4FB3", "name": "Дом Ми Аморе", "tier": 6, "ruling": True,
                "emblem": 514,  # heart - Cadance's cutie mark
                "heroes": [
                    ("cadance", "Кейденс", "f", 30, "Принцесса любви, правительница Кристальной Империи."),
                    ("shining_armor", "Шайнинг Армор", "m", 31, "Бывший капитан Королевской стражи, брат Твайлайт и супруг Кейденс."),
                    ("flurry", "Флурри Харт", "f", 6, "Дочь Кейденс и Шайнинг Армора, аликорн от рождения."),
                ],
                "marriages": [("cadance", "shining_armor")],
                "children": [
                    ("shining_armor", "night_light", "velvet"),
                    ("flurry", "shining_armor", "cadance"),
                ],
            },
            {
                "id": "clan_cr_hope", "name": "Дом Радиант Хоуп", "tier": 4,
                "color": "FF80DEEA", "color2": "FF6A1B9A", "emblem": 524,
                "heroes": [
                    ("radiant_hope", "Радиант Хоуп", "f", 27, "Кристальная целительница, подруга детства Сомбры."),
                    ("arctic_lily", "Арктик Лили", "f", 34, "Предводительница северных кристальных родов."),
                ],
            },
            {
                "id": "clan_cr_crystaller", "name": "Кристальные хранители", "tier": 4,
                "color": "FF4FC3F7", "color2": "FFFFE082", "emblem": 517,
                "heroes": [
                    ("sunburst", "Санбёрст", "m", 27, "Кристаллер Империи, учёный-волшебник и друг детства Старлайт."),
                    ("stellar_flare", "Стеллар Флэр", "f", 52, "Мать Санбёрста, строгая и очень деловая."),
                    ("firelight", "Файрлайт", "m", 54, "Отец Санбёрста."),
                ],
                "marriages": [("firelight", "stellar_flare")],
                "children": [("sunburst", "firelight", "stellar_flare")],
            },
            {
                "id": "clan_cr_sombra", "name": "Тени Сомбры", "tier": 3,
                "color": "FF263238", "color2": "FFD32F2F", "emblem": 316,
                "heroes": [
                    ("sombra", "Сомбра", "m", 45, "Бывший король-тиран. Его сторонники ждут возвращения."),
                    ("umbra", "Умбра", "f", 33, "Хранительница теневых кристаллов."),
                ],
            },
        ],
        # CRY is the Crystal Empire itself, STG is the fan-made Stalliongrad of EaW, absent in canon:
        # these northern lands are given to the Empire (city names are in RENAMES)
        "eaw": ["CRY", "STG"],
        "capital": "Кристальный Город",
        "power": 0.98,
        "anchors": ["Кристальный Город", "Сталлионград", "Наш Городок", "Спайктаун"],
    },
    {
        "culture": "vlandia",
        "kingdom": "kingdom_griffonia",
        "name": "Грифонстоун",
        "short": "Грифонстоун",
        "title": "Королевство Грифонстоун",
        "ruler_title": "Король",
        "color": "FF7B5E2E",
        "color2": "FFE8C547",
        "emblem": 115,
        "text": "Горное королевство грифонов, когда-то растерявшее всё из-за утраченного Идола Бориаса. "
                "Теперь Идол возвращён, и грифоны снова учатся быть не только жадными, но и верными.",
        "clans": [
            {
                "id": "clan_gr_ironclaw", "name": "Дом Гровера", "tier": 5, "ruling": True,
                "color": "FF5D4037", "color2": "FFE8C547", "emblem": 340,
                "heroes": [
                    ("reyhard_ironclaw", "Гровер Второй", "m", 52, "Король Грифонстоуна, потомок легендарного короля Гровера."),
                    ("wilhelm_silverwing", "Вильгельм Сильвервинг", "m", 44, "Маршал короля, ветеран горных войн."),
                    ("erika_rosetalon", "Эрика Роузталон", "f", 36, "Советница двора, мастер тайных переговоров."),
                ],
            },
            {
                "id": "clan_gr_redtail", "name": "Дом Редтейл", "tier": 4,
                "color": "FF8E2A1E", "color2": "FFF4D03F", "emblem": 115,
                "heroes": [
                    ("heinrich_redtail", "Генрих Редтейл", "m", 48, "Старый полководец, хозяин восточных перевалов."),
                    ("ulla_redtail", "Улла Редтейл", "f", 42, "Жена Генриха, правящая Фронтиром в его отсутствие."),
                    ("triton_blackpeak", "Тритон Блэкпик", "m", 39, "Командир горных егерей."),
                ],
                "marriages": [("heinrich_redtail", "ulla_redtail")],
            },
            {
                "id": "clan_gr_goldcrest", "name": "Дом Голдкрест", "tier": 3,
                "color": "FF8D6E1F", "color2": "FFF5F5F5", "emblem": 518,
                "heroes": [
                    ("hector_goldcrest", "Гектор Голдкрест", "m", 47, "Казначей короны, самый богатый грифон севера."),
                    ("erwin_highhill", "Эрвин Хайхилл", "m", 41, "Командир воздушной кавалерии."),
                    ("toki_bright", "Токи Брайт", "f", 29, "Разведчица, знающая каждое ущелье Грифонских гор."),
                ],
            },
            {
                "id": "clan_gr_gruff", "name": "Грифонстоунский Род", "tier": 3,
                "color": "FF6D6D6D", "color2": "FFE0C080", "emblem": 316,
                "heroes": [
                    ("grampa_gruff", "Дедушка Грифф", "m", 84, "Хранитель легенды об Идоле Бориаса, ворчливый старейшина."),
                    ("gilda", "Гильда", "f", 25, "Резкая грифонша, давняя подруга Рэйнбоу Дэш."),
                    ("gabby", "Габби", "f", 20, "Весёлая почтальонша, мечтающая о метке."),
                ],
            },
            {
                "id": "clan_gr_gustave", "name": "Дом Гюстава", "tier": 3,
                "color": "FFB71C1C", "color2": "FFFFF8E1", "emblem": 211,
                "heroes": [
                    ("gustave", "Гюстав ле Гран", "m", 45, "Знаменитый шеф-кондитер из Прансии, мастер эклеров."),
                    ("greta", "Грета", "f", 30, "Племянница Гюстава, лучшая лучница гнезда."),
                ],
            },
        ],
        "relations": [
            ("reyhard_ironclaw", "wilhelm_silverwing", 70), ("reyhard_ironclaw", "heinrich_redtail", 20),
            ("gilda", "gabby", 30), ("grampa_gruff", "gilda", 40), ("gilda", "rainbow_dash", 40),
            ("gabby", "spike", 40),
        ],
        # GRF, GFF, PNG - fan-made griffons and penguins of EaW; in canon this is the Griffonstone kingdom
        "eaw": ["GRF", "GFF", "PNG"],
        "capital": "Уэтер",
        "power": 1.02,
        "anchors": ["Уэтер", "Нуво Аквила", "Борейфьорд", "Дахи", "Ню Вингхаген"],
    },
    {
        "culture": "battania",
        "kingdom": "kingdom_hippogriffia",
        "name": "Гиппогриффия",
        "short": "Гиппогриффия",
        "title": "Королевство горы Арис",
        "ruler_title": "Королева",
        "color": "FF00838F",
        "color2": "FFFFD54F",
        "emblem": 157,
        "text": "Гиппогрифы горы Арис и морские пони Сиквестрии. Однажды они спрятались от Короля "
                "Шторма под водой, а теперь снова летают над своим западным побережьем.",
        "clans": [
            {
                "id": "clan_hp_novo", "name": "Дом Ново", "tier": 5, "ruling": True,
                "color": "FF00838F", "color2": "FFFFD54F", "emblem": 157,
                "heroes": [
                    ("queen_novo", "Королева Ново", "f", 52, "Правительница гиппогрифов и морских пони, хранительница Жемчужины."),
                    ("skystar", "Скайстар", "f", 22, "Принцесса, мечтающая о жизни над волнами."),
                ],
                "children": [("skystar", None, "queen_novo")],
            },
            {
                "id": "clan_hp_silverstream", "name": "Семья Сильверстрим", "tier": 4,
                "color": "FF4DD0E1", "color2": "FFE1BEE7", "emblem": 516,
                "heroes": [
                    ("sky_beak", "Скай Бик", "m", 48, "Отец Сильверстрим и Террамара, гиппогриф."),
                    ("ocean_flow", "Оушен Флоу", "f", 46, "Мать Сильверстрим, выбравшая жизнь морской пони."),
                    ("silverstream", "Сильверстрим", "f", 19, "Любопытная ученица Школы Дружбы, в восторге от лестниц."),
                    ("terramar", "Террамар", "m", 16, "Брат Сильверстрим, живущий меж двух миров."),
                ],
                "marriages": [("sky_beak", "ocean_flow")],
                "children": [
                    ("silverstream", "sky_beak", "ocean_flow"),
                    ("terramar", "sky_beak", "ocean_flow"),
                ],
            },
            {
                "id": "clan_hp_seaspray", "name": "Дом Сиспрея", "tier": 4,
                "color": "FF1565C0", "color2": "FFFFFFFF", "emblem": 316,
                "heroes": [
                    ("seaspray", "Генерал Сиспрей", "m", 50, "Командующий войском королевы Ново."),
                    ("coral_wing", "Корал Винг", "f", 33, "Командир летучей стражи горы Арис."),
                ],
            },
        ],
        "relations": [
            ("queen_novo", "skystar", 90), ("silverstream", "terramar", 95), ("queen_novo", "seaspray", 70),
            ("silverstream", "yona", 80), ("silverstream", "smolder", 75), ("celestia", "queen_novo", 40),
        ],
        # OLE - the fan-made Olenia of EaW (deer), absent in canon: hippogriffs and deer share the coast
        "eaw": ["OLE"],
        "capital": "Хьёртланд",
        "power": 0.88,
        "anchors": ["Хьёртланд", "Цервус", "Сакара", "Эндрект", "Вейверфронт"],
    },
    # Olenia (EaW, kingdom OLE): northern deer forests. Previously qilins on pony meshes stood here -
    # a test race without its own model. We now have our own deer (tools/make_deer_model.py),
    # so the kingdom moved to them entirely, together with clans and lords (decided 24.09.2026).
    {
        "culture": "nord",
        "kingdom": "kingdom_olenia",
        "name": "Оления",
        "short": "Оления",
        "title": "Королевство Оления",
        "ruler_title": "Король",
        "color": "FF2E7D32",
        "color2": "FFD7CCC8",
        "emblem": 518,
        "text": "Северные леса и озёра оленей. Трон занял бастард, законная наследница собирает "
                "сторонников, а рогатые дружины стерегут границы от драконов.",
        "clans": [
            {
                "id": "clan_ol_jelzek", "name": "Дом Йельцека", "tier": 5, "ruling": True,
                "color": "FF2E7D32", "color2": "FFD7CCC8", "emblem": 518,
                "heroes": [
                    ("johan_jelzek", "Йохан Йельцек", "m", 45, "Бастард, силой взявший оленийский трон."),
                    ("aslaug_jelzek", "Аслауг Йельцек", "f", 40, "Сестра короля, его главная опора при дворе."),
                ],
            },
            {
                "id": "clan_ol_velvet", "name": "Дом Вельвет", "tier": 4,
                "color": "FF6A1B9A", "color2": "FFFFE0B2", "emblem": 524,
                "heroes": [
                    ("queen_velvet", "Королева Вельвет", "f", 38, "Законная наследница, оспаривающая трон у бастарда."),
                    ("hjalmar_velvet", "Хьялмар Вельвет", "m", 44, "Её дядя и воевода, водит сторонников королевы."),
                ],
            },
            {
                "id": "clan_ol_kudlinen", "name": "Дом Кудлинен", "tier": 3,
                "color": "FF795548", "color2": "FFFFCC80", "emblem": 211,
                "heroes": [
                    ("benjen_kudlinen", "Бенджен Кудлинен", "m", 52, "Старейшина Совета Семи, хранитель лесных законов."),
                    ("ilta_kudlinen", "Ильта Кудлинен", "f", 29, "Лучшая следопытка оленьих троп."),
                ],
            },
        ],
        "relations": [
            ("johan_jelzek", "queen_velvet", -60), ("queen_velvet", "hjalmar_velvet", 90),
            ("benjen_kudlinen", "johan_jelzek", 10),
        ],
        "eaw": ["OLE"],
        "capital": "Хирвикаупунки",
        "power": 0.85,
        "anchors": ["Хирвикаупунки", "Сольгуд", "Талвиваара", "Элксбург", "Гриллоблатод"],
    },
    {
        "culture": "sturgia",
        "kingdom": "kingdom_dragons",
        "name": "Драконьи Земли",
        "short": "Драконы",
        "title": "Драконьи Земли",
        "ruler_title": "Лорд драконов",
        "color": "FFB71C1C",
        "color2": "FFFFAB00",
        "emblem": 524,
        "text": "Раскалённые юго-восточные земли вулканов и джунглей. Драконы признают только силу, "
                "но их лорд Эмбер учится, что у дружбы тоже бывают когти.",
        "clans": [
            {
                "id": "clan_dr_ember", "name": "Род Торча", "tier": 5, "ruling": True,
                "color": "FFB71C1C", "color2": "FFFFAB00", "emblem": 524,
                "heroes": [
                    ("ember", "Эмбер", "f", 24, "Лорд драконов, получившая Скипетр в Состязании."),
                    ("torch", "Торч", "m", 70, "Бывший лорд драконов, отец Эмбер."),
                ],
                "children": [("ember", "torch", None)],
            },
            {
                "id": "clan_dr_garble", "name": "Шайка Гарбла", "tier": 4,
                "color": "FFD84315", "color2": "FF263238", "emblem": 316,
                "heroes": [
                    ("garble", "Гарбл", "m", 22, "Задира, втайне сочиняющий стихи."),
                    ("clump", "Кламп", "m", 20, "Приятель Гарбла, силач."),
                    ("fume", "Фьюм", "m", 21, "Ещё один дружок Гарбла, мастер дымовых колец."),
                ],
            },
            {
                "id": "clan_dr_smolder", "name": "Гнездо Смолдер", "tier": 3,
                "color": "FFFF7043", "color2": "FF6A1B9A", "emblem": 516,
                "heroes": [
                    ("smolder", "Смолдер", "f", 19, "Ученица Школы Дружбы, тайком любящая чаепития."),
                    ("sludge", "Сладж", "m", 60, "Хитрый старый дракон, мастер уговоров."),
                ],
            },
        ],
        "relations": [
            ("ember", "torch", 70), ("ember", "spike", 90), ("garble", "smolder", 30),
            ("garble", "ember", -20), ("sludge", "spike", -40),
        ],
        # DRG - the Dragon Lands of EaW (a single mountain); the south-eastern jungles of Equestria are added
        "eaw": ["DRG", "EQS"],
        "capital": "Теночтитлан",
        "power": 0.90,
        "anchors": ["Теночтитлан", "Гора", "Стейблсайд", "Саутпойнт"],
    },
    {
        "culture": "khuzait",
        "kingdom": "kingdom_yakyakistan",
        "name": "Якьякистан",
        "short": "Якьякистан",
        "title": "Царство Якьякистан",
        "ruler_title": "Принц",
        "color": "FF8D6E63",
        "color2": "FFD7CCC8",
        "text": "Горное царство яков. Здесь ценят прямоту, крепкий мороз и умение сломать "
                "то, что сделано неправильно.",
        "clans": [
            {
                "id": "clan_yk_rutherford", "name": "Род Резерфорда", "tier": 5, "ruling": True,
                "heroes": [
                    ("rutherford", "Резерфорд", "m", 48, "Принц яков, громкий и честный."),
                    ("yona", "Йона", "f", 21, "Юная якесса, учившаяся в Эквестрии."),
                ],
                "children": [("yona", "rutherford", None)],
            },
            {
                "id": "clan_yk_thyra", "name": "Род Тиры", "tier": 4,
                "heroes": [
                    ("thyra", "Тира", "f", 44, "Предводительница горных стад."),
                    ("yngvar", "Ингвар", "m", 50, "Старейшина, помнящий все обиды яков наперечёт."),
                ],
                "marriages": [("thyra", "yngvar")],
            },
            {
                "id": "clan_yk_jaki", "name": "Джаки-клан", "tier": 3,
                "heroes": [
                    ("bradford", "Брэдфорд", "m", 39, "Принц отколовшейся ветви яков."),
                    ("kerr", "Хан Керр", "m", 43, "Степной вождь, союзник Брэдфорда."),
                ],
            },
        ],
        # PLB - the fan-made Polaria of EaW (bears), absent in canon: the icy north is given to the yaks
        "eaw": ["YAK", "JAK", "PLB"],
        "capital": "Яктаун",
        "power": 0.96,
        "anchors": ["Яктаун", "Сайхан Толгод", "Махарь-Фьяранн", "Вессландия"],
    },
    {
        "culture": "aserai",
        "kingdom": "kingdom_changeling",
        "name": "Земли чейнджлингов",
        "short": "Ульи",
        "title": "Улей чейнджлингов",
        "ruler_title": "Королева",
        # Hive chitin: the first colour is almost black with a green tint, the second is the teal of Chrysalis's mane.
        # The engine tints with them the armour areas marked in the _c mask (on Aserai armour these are
        # cloth and trims), so the whole look of the swarm depends on these two numbers.
        "color": "FF101A16",
        "color2": "FF1FA9A0",
        "text": "Бесплодные земли на юго-востоке, изрытые ульями оборотней. Питаются чужой "
                "любовью и готовят поход на соседей.",
        "clans": [
            {
                "id": "clan_ch_chrysalis", "name": "Улей Кризалис", "tier": 5, "ruling": True,
                "heroes": [
                    ("chrysalis", "Кризалис", "f", 44, "Королева ульев, мастерица подмены."),
                    ("synovial", "Синовиал", "m", 40, "Хивесмаршал, полководец роя."),
                ],
            },
            {
                "id": "clan_ch_thorax", "name": "Улей Торакса", "tier": 4,
                "heroes": [
                    ("thorax", "Торакс", "m", 30, "Вождь отколовшихся чейнджлингов, выбравших дружбу."),
                    ("pharynx", "Фаринкс", "m", 33, "Брат Торакса, начальник дозоров."),
                ],
            },
            {
                "id": "clan_ch_muffin", "name": "Дом Гольд Маффин", "tier": 3,
                "heroes": [
                    ("gold_muffin", "Гольд Маффин", "f", 36, "Купеческая королева ульев."),
                    ("vraks", "Вракс", "m", 41, "Хранитель южных троп."),
                ],
            },
        ],
        "eaw": ["CHN"],
        "capital": "Весалиполис",
        "power": 1.12,
        "anchors": ["Весалиполис", "Дитрисиум", "Сориф", "Вракс", "Аглоссата"],
    },
]


# How many settlements an "average" kingdom (power 1.0) gets. Strong ones get more, weak ones
# fewer - in proportion to "power". In the vanilla campaign a kingdom has 5–8 towns, 8–9 castles
# and 31–40 villages; the whole map comes to ~400 settlements, roughly one per 900 m² of land.
SETTLEMENT_BASE = {"town": 6.0, "castle": 7.0, "village": 28.0}

# Names for towns and castles we had to invent: in lands where Equestria at War had
# no cities (the yak north, the griffon cliffs, the hives), yet settlements are needed to avoid empty areas.
FORT_NAMES = {
    "empire": ["Сиэддл", "Уиннияполис", "Полые Тени", "Ниагра Фоллс", "Сильвер Шоалс",
               "Винсом Фоллс", "Сомнамбула", "Кантерхорн", "Сэддл Лейк", "Мэйнфорд", "Солнцепад"],
    "aserai": ["Хитиновая Гряда", "Чёрный Кокон", "Улей Синовиала", "Кислые Топи",
               "Смоляная Впадина", "Пустые Пески", "Мёртвый Улей", "Жужжащий Провал"],
    "battania": ["Штормовой Утёс", "Тритонья Мель", "Морская Арка", "Раковинная Бухта",
                 "Жемчужный Риф", "Коралловый Грот", "Пенный Мыс", "Солёный Кряж"],
    "sturgia": ["Вулкан Состязания", "Пепельный Кряж", "Лавовые Врата", "Обсидиановая Пасть",
                "Дымная Долина", "Огненный Кратер", "Чешуйчатый Хребет", "Клугтаун",
                "Драконий Клык"],
    "khuzait": ["Ледяная Ставка", "Снежный Рог", "Мохнатый Перевал", "Громовой Утёс",
                "Белый Ледник", "Каменное Стойбище", "Морозный Рог", "Полярный Дол"],
    "vlandia": ["Когтевой Утёс", "Орлиное Гнездо", "Золотой Насест", "Ветреный Кряж",
                "Идоловы Скалы", "Грифоний Перевал", "Клюворог", "Высокий Насест"],
    "nord": ["Тлеющий Ключ", "Кленовый Перевал", "Пепел Нирика", "Молчаливая Роща",
             "Тихий Омут", "Осенний Кряж", "Уголёк", "Багряный Дол"],
}


# Canon MLP cities that the Equestria at War map gave a low weight: in the mod they must be
# towns or at least strongholds, not villages. The key is the city name on the EaW map.
CITY_VALUE = {
    "Клаудсдейл": 35.0,       # the pegasus city where the weather is made
    "Эпплуза": 18.0,          # apple town in the south
    "Додж-Сити": 18.0,
    "Наш Городок": 18.0,      # Starlight's village of "equals"
    "Цервус": 30.0,           # Seaquestria, the underwater city
    "Сольгуд": 18.0,          # the Peaks of Peril, a deer stronghold
    "Сайхан Толгод": 18.0,    # the old seat of the mountain yaks
    "Махарь-Фьяранн": 18.0,   # the Ice Port
}


# Cities we moved by hand. On the Equestria at War map Canterlot, Ponyville and
# Cloudsdale stand in one cluster (all three within 25 m of each other), and on the world map this looks
# cramped. Canterlot moved west - into the pass between two mountain ranges (as it should be
# by the lore, a city in the mountains), and Ponyville with Cloudsdale south-west, into the open steppe, where
# there was room to spare. The key is the city name on the EaW map, the value is the new coordinates.
CITY_MOVE = {
    "Кантерлот": (552.0, 512.0),     # the pass between two ranges
    "Понивилль": (530.0, 446.0),     # south of the river, in the middle of the free steppe
    "Клаудсдейл": (570.0, 470.0),    # right by the river, it runs to the left of the city
}

# Which kingdoms exist in the world. The others are described above but do not get into the game:
# neither their clans, nor lords, nor settlements. To bring one back, add its id here.
ACTIVE_KINGDOMS = [
    "kingdom_equestria",
    "kingdom_lunar",
    "kingdom_friendship",
    "kingdom_crystal",
    "kingdom_changeling",
    "kingdom_yakyakistan",
    "kingdom_griffonia",
    "kingdom_hippogriffia",
    "kingdom_olenia",
    "kingdom_dragons",
]

# Diplomacy at campaign start - otherwise all kingdoms start at peace with everyone (written to
# equestria_diplomacy.xml, applied by src/EquestriaDiplomacy.cs when a new campaign is created).
#   ("war", a, b)            - war
#   ("alliance", a, b)       - alliance
#   ("trade", a, b)          - trade agreement (for a year)
#   ("tribute", a, b, gold) - truce: a pays b that much gold per day (100 days)
DIPLOMACY = [
    # wars: changelings against both Equestrias (Chrysalis's invasion), dragons raid the griffons,
    # yaks argue with the Crystal Empire over the northern passes
    ("war", "kingdom_changeling", "kingdom_friendship"),
    ("war", "kingdom_changeling", "kingdom_equestria"),
    ("war", "kingdom_dragons", "kingdom_griffonia"),
    ("war", "kingdom_yakyakistan", "kingdom_crystal"),
    # alliances: Celestia with Twilight and Cadance, Twilight with the hippogriffs after the Storm King
    ("alliance", "kingdom_equestria", "kingdom_friendship"),
    ("alliance", "kingdom_equestria", "kingdom_crystal"),
    ("alliance", "kingdom_friendship", "kingdom_hippogriffia"),
    # trade
    ("trade", "kingdom_equestria", "kingdom_griffonia"),
    ("trade", "kingdom_friendship", "kingdom_yakyakistan"),
    ("trade", "kingdom_lunar", "kingdom_olenia"),
    ("trade", "kingdom_crystal", "kingdom_griffonia"),
    ("trade", "kingdom_lunar", "kingdom_hippogriffia"),
    # truces with tribute: the deer buy off the dragons, the hives buy off Luna, the griffons pay the yaks
    ("tribute", "kingdom_olenia", "kingdom_dragons", 150),
    ("tribute", "kingdom_changeling", "kingdom_lunar", 200),
    ("tribute", "kingdom_griffonia", "kingdom_yakyakistan", 100),
]

# EaW lands without a kingdom of their own (fan-made or too small): their cities go to the kingdom
# whose settlement is nearest. Their peoples became mercenary clans (MINOR_CLANS).
ORPHAN_EAW = ["BUF", "STL"]

# Canon or fitting-in-spirit names instead of the fan-made EaW names.
RENAMES = {
    # Hippogriffia (former Olenia)
    "Хьёртланд": "Гора Арис",
    "Цервус": "Сиквестрия",
    "Сакара": "Жемчужная Бухта",
    "Вейверфронт": "Приливная Гавань",
    "Эндрект": "Коралловый Мыс",
    "Свенхольм": "Перьевой Утёс",
    "Голденшор": "Золотой Берег",
    "Яльгстад": "Ракушечный Причал",
    # Olenia
    "Хирвикаупунки": "Оленья Роща",
    "Сиддл": "Тихий Ручей",
    "Сольгуд": "Пики Опасности",
    "Вихерлааксо": "Долина Безмолвия",
    "Талвиваара": "Огненный Перевал",
    # Crystal Empire (former Stalliongrad)
    "Сталлионград": "Кристальный Пик",
    "Петерсхуф": "Северная Гавань",
    "Карамель Маркс": "Сапфировый Брод",
    "Коньзань": "Аметистовый Дол",
    "Звездопадово": "Звездопад",
    "Северохолм": "Северный Холм",
    "Ставропонь": "Хрустальные Ключи",
    "Заятск": "Морозный Лес",
    "Златоцвет": "Златоцвет",
    "Красивск": "Сияющий Бор",
    "Равенское": "Ледяная Гавань",
    "Комсомольск": "Кварцевая Бухта",
    "Черриабинск": "Вишнёвый Хутор",
    "Копытобойск": "Подкова Севера",
    "Лошадск": "Санный Путь",
    # Dragon Lands
    "Теночтитлан": "Логово Лорда Драконов",
    "Гора": "Вулкан Состязания",
    # Griffonstone
    "Уэтер": "Грифонстоун",
    # Yakyakistan (former Polaria)
    "Махарь-Фьяранн": "Ледяной Порт",
    "Гейрфугльвидда": "Гнездо Буревестника",
}
KINGDOMS = [k for k in ALL_KINGDOMS if k["kingdom"] in ACTIVE_KINGDOMS]

# Inhabitant names. The game takes them from the culture lists for EVERYONE: townsfolk, peasants, nobles,
# children, tavern companions. While the lists are vanilla, the world is populated by Calradians with Greek names.
#
# Two kinds of lists:
#   ("compound", [first parts], [second parts]) - like real pony names: Sunny Dash, Star Heart.
#   ("simple", [names])                          - where compound ones do not fit.
NAMES = {
    "empire": {
        "m": ("составное",
              ["Санни", "Мун", "Стар", "Эппл", "Клауд", "Свифт", "Голден", "Брайт", "Сильвер", "Дасти",
               "Коппер", "Айрон", "Ноубл", "Стил"],   # reserve for added clans (tools/world_fill.py)
              ["Дэш", "Харт", "Мейн", "Лайт", "Сонг", "Хуф", "Брэйв", "Филд",
               "Винд", "Стоун", "Флейм", "Скай", "Ридж", "Гроув"],
              # second-tier lore names - whole, on top of the compound ones
              ["Кэррамел", "Дэвенпорт", "Лаки Кловер", "Ноутворти", "Мистер Кейк", "Хойти Тойти",
               "Джет Сет", "Бёрнт Оук", "Голден Харвест", "Шайнинг Стар", "Комет Тейл",
               "Стар Хантер", "Мидлайт", "Найт Глайдер", "Дабл Даймонд", "Парти Фейвор",
               "Санни Дейз", "Кранки Дудл", "Фезервейт", "Пипсквик", "Сноуфлейк", "Булк Бицепс",
               "Трендерхуф", "Тандер Клэп", "Рамбл", "Снипс", "Снейлс", "Файрболл", "Флим", "Флэм"]),
        "f": ("составное",
              ["Санни", "Мун", "Стар", "Эппл", "Хани", "Роуз", "Свит", "Лили", "Мисти", "Пинки",
               "Лавендер", "Черри", "Дейзи", "Виолет"],   # reserve for added clans
              ["Спаркл", "Блум", "Харт", "Свирл", "Дэш", "Белль", "Сонг", "Шайн",
               "Лиф", "Мист", "Глоу", "Флауэр", "Дью", "Винд"],
              # second-tier lore names - whole, on top of the compound ones
              ["Роузлак", "Лили Вэлли", "Берри Панч", "Миссис Кейк", "Эмбер Уэйвс", "Мэйн Гудолл",
               "Сапфир Шорс", "Колоратура", "Уайт Лайтнинг", "Клауд Кикер", "Блоссомфорт",
               "Флиттер", "Клаудчейзер", "Медли", "Черри Берри", "Голди Делишес",
               "Апл Фриттер", "Апл Сайдер", "Черри Джубили", "Хани Лемон", "Ноктюрн",
               "Бланкет", "Дитзи Ду", "Твист", "Даймонд Минт", "Лотус Блоссом", "Алоэ",
               "Сирена", "Тандер Флэш", "Мэй", "Рэйндропс", "Лайтнинг Болт", "Сасси Свит"]),
    },
    # Griffons: names starting with "G" in a Germanic style, like Gilda, Grover and Gustave
    "vlandia": {
        "m": ("составное",
              ["Гровер", "Гюнтер", "Грифф", "Генрих", "Вильгельм", "Эрвин", "Гюстав", "Готфрид"],
              ["Айронкло", "Сильвервинг", "Редтейл", "Голдкрест", "Блэкпик", "Хайхилл", "Стормфезер", "Роккло"]),
        "f": ("составное",
              ["Гильда", "Эрика", "Улла", "Грета", "Хельга", "Ильза", "Марта", "Лизель"],
              ["Роузталон", "Уайтфезер", "Сильвервинг", "Голдкрест", "Редтейл", "Брайтвинг", "Сноуфезер", "Эшклоу"]),
    },
    # Hippogriffs and sea ponies: "sea" and "sky" names, like Skystar and Silverstream
    "battania": {
        "m": ("составное",
              ["Скай", "Оушен", "Тайд", "Корал", "Си", "Шторм", "Вейв", "Перл"],
              ["Бик", "Винг", "Спрей", "Стрим", "Фезер", "Ривер", "Глайд", "Мар"]),
        "f": ("составное",
              ["Скай", "Оушен", "Сильвер", "Корал", "Перл", "Си", "Мист", "Шелл"],
              ["Стар", "Стрим", "Флоу", "Блум", "Вейв", "Фезер", "Глоу", "Лайт"]),
    },
    # Dragons: short "fiery" names, like Ember, Garble and Smolder
    "sturgia": {
        "m": ("простое",
              ["Торч", "Гарбл", "Кламп", "Фьюм", "Сладж", "Скорч", "Клинкер", "Флинт",
               "Бласт", "Гриммер", "Сажень", "Рокот", "Уголь", "Шлак", "Зольник", "Жар",
               # reserve for added clans (tools/world_fill.py)
               "Бэйзальт", "Игнис", "Крэг", "Молтен", "Обсидиан", "Пирит", "Смог", "Тиндер",
               "Фёрнас", "Чар", "Шейл", "Эмбер-Кло", "Брэйзер", "Кальдер", "Слэг", "Фьюри"]),
        "f": ("простое",
              ["Эмбер", "Смолдер", "Пламя", "Искра", "Синдра", "Лава", "Зола", "Магма",
               "Фларэ", "Опалина", "Вспышка", "Пепелина", "Руби", "Гарнет", "Жарина", "Тлея",
               "Ашера", "Бласта", "Глоуин", "Дрейка", "Кальдера", "Кармина", "Пирра", "Сцинтилла",
               "Тефра", "Файра", "Хэйз", "Эмберли", "Ардора", "Вулкана", "Игнита", "Скарлет"]),
    },
    # Deer: northern names with a family nickname, like Johan Jeltsek and Benjen Kudlinen.
    # The second list is surnames: the names of added houses (CLAN_STYLE) are taken from it too.
    "nord": {
        "m": ("составное",
              ["Йохан", "Бенджен", "Хьялмар", "Эйнар", "Торвин", "Свейн", "Ярве", "Алмо",
               "Рейно", "Тапио", "Вилле", "Ансси", "Урхо", "Кауко", "Лаури", "Ээро"],
              ["Йельцек", "Кудлинен", "Хьорт", "Сарвинен", "Метсола", "Ярвинен", "Лехто",
               "Салонен", "Корпи", "Виронен", "Аалто", "Хирви"]),
        "f": ("составное",
              ["Вельвет", "Аслауг", "Ильта", "Сигне", "Хелми", "Айно", "Кайса", "Мерья",
               "Тууликки", "Пихла", "Веса", "Марьятта", "Сату", "Элина", "Кирси", "Линнеа"],
              ["Йельцек", "Кудлинен", "Хьорт", "Сарвинен", "Метсола", "Ярвинен", "Лехто",
               "Салонен", "Корпи", "Виронен", "Аалто", "Хирви"]),
    },
    "khuzait": {
        "m": ("простое",
              ["Йорд", "Гурт", "Торвальд", "Бьёрн", "Хрольф", "Свен", "Рагнар", "Магнус",
               "Одд", "Хакон", "Эйнар", "Гримм", "Снорри", "Ульф", "Хродгар", "Барди",
               # reserve for added clans (tools/world_fill.py)
               "Арвид", "Балдур", "Вигго", "Гуннар", "Дагфинн", "Ивар", "Кетиль", "Лейф",
               "Орм", "Ролло", "Сигурд", "Стейн", "Тормод", "Хальвар", "Эгиль", "Ярл"]),
        "f": ("простое",
              ["Хельга", "Ингрид", "Сигрид", "Астрид", "Гунхильд", "Фрейя", "Тордис", "Свана",
               "Ярдис", "Бергдис", "Хильда", "Руна", "Сольвейг", "Идунн", "Гудрун", "Аста",
               "Альва", "Боргни", "Вигдис", "Гейра", "Дагни", "Ингунн", "Йорунн", "Лив",
               "Ода", "Ранвейг", "Сигне", "Торунн", "Ульва", "Хердис", "Эйдис", "Эмбла"]),
    },
    "aserai": {
        "m": ("простое",
              ["Криксус", "Зуммер", "Хитин", "Вракс", "Сорит", "Ликтид", "Мимик", "Скарабей",
               "Дрон", "Пантер", "Молт", "Кокон", "Жужжа", "Стрёкот", "Прорезь", "Шелест",
               # reserve for added clans (tools/world_fill.py)
               "Апис", "Бомбус", "Веспа", "Глосс", "Карапакс", "Ларвус", "Мандибул", "Нектарис",
               "Оцеллус", "Прокрис", "Спиракл", "Тарсус", "Феромон", "Хиазм", "Цикад", "Элитрон"]),
        "f": ("простое",
              ["Кризи", "Мирра", "Шелла", "Нимфа", "Эхо", "Вуаль", "Дымка", "Морок",
               "Личина", "Обмана", "Тень", "Сеть", "Смола", "Прядь", "Роса", "Чара",
               "Аглая", "Ванесса", "Гема", "Долия", "Имаго", "Кризанта", "Ламия", "Мелисса",
               "Нимфея", "Оцелла", "Пупа", "Селена", "Тития", "Фасма", "Хризанта", "Эфира"]),
    },
}

# Tavern companions. The game distributes them across towns itself; we set nicknames, and it fills in the name
# from the culture lists above. Vanilla templates (spc_wanderer_<culture>_<number>) are overridden by id.
# Canon companions: MLP characters who are not among the lords. From a companion template the game makes
# a hero with this name (without {FIRSTNAME} - the name is fixed) and puts them in a tavern of a town of their
# culture. The template is a copy of the vanilla spc_wanderer_<culture>_N (skills, equipment, traits).
#   (id, name, gender, age)
CANON_COMPANIONS = {
    "empire": [
        ("lyra", "Лира Хартстрингс", "f", 24), ("bon_bon", "Бон Бон", "f", 24),
        ("octavia", "Октавия Мелоди", "f", 26), ("vinyl", "Винил Скрэтч", "f", 25),
        ("derpy", "Дерпи Хувс", "f", 27), ("doctor", "Доктор Хувз", "m", 38),
        ("cheerilee", "Чирайли", "f", 32), ("zecora", "Зекора", "f", 40),
        ("cheese", "Чиз Сэндвич", "m", 27), ("daring_do", "Дэринг Ду", "f", 33),
        ("coco", "Коко Помель", "f", 23), ("sassy", "Сасси Сэддлс", "f", 35),
        ("minuette", "Минуэтт", "f", 24), ("lemon_hearts", "Лемон Хартс", "f", 24),
        ("twinkleshine", "Твинклшайн", "f", 24), ("sunset", "Сансет Шиммер", "f", 25),
        ("tempest", "Темпест Шадоу", "f", 30), ("quibble", "Квиббл Пэнтс", "m", 29),
        ("wind_rider", "Винд Райдер", "m", 52), ("sky_stinger", "Скай Стингер", "m", 22),
        ("vapor_trail", "Вейпор Трейл", "f", 22), ("carrot_top", "Кэррот Топ", "f", 26),
        ("nurse_redheart", "Нёрс Редхарт", "f", 34), ("mayor_mare", "Мэр Мэйр", "f", 50),
    ],
    "vlandia": [("gallus", "Гэллус", "m", 19), ("gimme_moar", "Джимми Мор", "m", 40)],
    "battania": [("haven_bay", "Хейвен Бэй", "f", 30), ("salina_blue", "Салина Блу", "f", 28)],
    "sturgia": [("billy", "Билли", "m", 24), ("crackle", "Крэкл", "f", 35)],
    "aserai": [("ocellus", "Оцеллус", "f", 19)],
}

COMPANION_TITLES = {
    "empire": ["Книжница", "Следопыт", "Табунщица", "Небесный Курьер", "Садовод", "Летописец",
               "Заклинательница", "Гонец", "Певунья", "Столичный Щёголь", "Сборщица Яблок",
               "Ветеран Гвардии", "Пекарь", "Звездочёт", "Швея", "Дозорный", "Пастух"],
    "vlandia": ["Небесный Рыцарь", "Наёмный Коготь", "Почтальон", "Горный Егерь", "Стражница Перевала",
                "Кузнец", "Картограф", "Сказительница", "Меняла", "Следопыт Фронтира", "Шериф",
                "Лётчица", "Охотник за Сокровищами", "Изобретатель", "Хранитель Идола",
                "Кондитер", "Ледовая Разведчица", "Трактирщица", "Оружейник", "Вестница",
                "Звездочёт", "Сборщик Податей", "Ловчий", "Лекарь", "Зодчий", "Дозорный"],
    "battania": ["Небесная Стражница", "Ловец Жемчуга", "Морской Разведчик", "Штормовой Лётчик",
                 "Певица Прибоя", "Хранитель Раковин", "Корабельщица", "Лекарь Приливов",
                 "Следопыт Облаков", "Рыбак", "Картограф Рифов", "Кузнец Перьев",
                 "Сказительница", "Ныряльщик", "Вестница", "Дозорный Утёсов"],
    "sturgia": ["Собиратель Самоцветов", "Огнедышащий Наёмник", "Хранитель Сокровищ", "Вулканолог",
                "Поэт Пламени", "Задира", "Лётчица над Лавой", "Кузнец Чешуи", "Сказитель", "Страж Логова"],
    "khuzait": ["Ледоруб", "Погонщица Стад", "Скальный Проводник", "Резчик по Рогу",
                "Хранительница Саг", "Снежный Охотник", "Кузнец Гор", "Знахарка",
                "Перевальный Дозорный", "Пивовар", "Сказитель"],
    "aserai": ["Подражатель", "Ловчая Чувств", "Разведчик Роя", "Хранительница Кладки",
               "Лазутчик", "Толмач", "Пряха Морока", "Смотритель Троп", "Собирательница",
               "Часовой Улья", "Меняла", "Дозорная", "Заготовщик", "Лекарь Роя",
               "Плетельщица", "Слухач", "Проводник", "Тихая Тень", "Сборщик Смолы",
               "Копательница", "Страж Кокона"],
}

# Minor factions - bandits and mercenaries. We do not delete them: hideouts, bandit parties
# and tavern hiring depend on them. But their names and descriptions are Calradian, so we override by id:
# (name, encyclopedia description, the same text in English).
# Much of it maps onto the lore directly: forest bandits are timberwolves, mountain ones are diamond dogs,
# sea raiders are the Storm King's army, steppe ones are buffalo raids.
MINOR_CLANS = {
    # bandits
    "looters": (
        "Мародёры",
        "Сброд, что идёт следом за любой войной: разорённые торговцы, беглые батраки и просто "
        "лентяи с дубинами. Поодиночке они трусливы, но оголодавшая толпа не боится и патруля.",
        "The rabble that follows every war: ruined traders, runaway farmhands and plain idlers "
        "with clubs. Alone they are cowards, but a starving mob will face even a patrol."),
    "deserters": (
        "Дезертиры",
        "Стражники и ополченцы, бросившие знамя посреди похода. Оружие у них доброе, совесть "
        "нечиста, а дороги назад нет: за дезертирство в Эквестрии судят строго.",
        "Guardsponies and militia who dropped their banner mid-campaign. Their weapons are good, "
        "their conscience is not, and there is no way back: Equestria judges desertion harshly."),
    "sea_raiders": (
        "Воинство Короля Шторма",
        "Остатки армии Короля Шторма, не сложившие оружие после его падения. Они приходят с моря "
        "на чёрных кораблях и берут то, что когда-то обещал им хозяин.",
        "Remnants of the Storm King's army that never laid down their arms after his fall. They "
        "come from the sea in black ships and take what their master once promised them."),
    "mountain_bandits": (
        "Алмазные Псы",
        "Псы роют самоцветы в горных норах и считают, что чужая работа приятнее своей. Пони они "
        "ловят не со зла, а ради нюха на драгоценные камни.",
        "The dogs dig gems in mountain burrows and find another's labour sweeter than their own. "
        "They snatch ponies not from malice but for their nose for precious stones."),
    "forest_bandits": (
        "Тимбервульфы",
        "Стаи из коряг и лозы, что собираются сами собой в чаще Вечнодикого леса. Разруби такого "
        "надвое — и через день по лесу бегают двое.",
        "Packs of deadwood and vine that assemble themselves in the Everfree thickets. Cut one in "
        "half and a day later two of them run the woods."),
    "desert_bandits": (
        "Стервятники Бесплодных Земель",
        "Падальщики пустошей за ульями чейнджлингов. Они не нападают на сильных: ждут, пока "
        "караван ослабеет от жажды, и подбирают то, что останется.",
        "Scavengers of the wastes beyond the changeling hives. They do not attack the strong: "
        "they wait until a caravan weakens from thirst and pick up what is left."),
    "steppe_bandits": (
        "Степные Шакалы",
        "Конные шайки с равнин, живущие набегом на стада и обозы. Они знают степь лучше любого "
        "разъезда и растворяются в траве раньше, чем подойдёт помощь.",
        "Mounted gangs of the plains who live by raiding herds and wagon trains. They know the "
        "steppe better than any patrol and melt into the grass before help arrives."),
    # mercenaries and outcasts: the name and description are chosen for the RACE the clan actually has - it is
    # set by the vanilla hero templates (spspecialcharacters.xml), not by the clan's own culture. Otherwise the
    # encyclopedia gets a mismatch: "Zebras of Zebrica", where everyone is called Kokon and Bombus.
    "jawwal": (
        "Верные Хризалиде",
        "Чейнджлинги, не принявшие мира между ульями и не простившие королеве поражения — но и "
        "без неё жить не умеющие. Дерутся зло и за любые деньги, лишь бы против тех, кто сверг "
        "Хризалиду.",
        "Changelings who never accepted the peace between the hives, nor forgave their queen her "
        "defeat, yet cannot live without her either. They fight bitterly and for any coin, so "
        "long as it is against those who deposed Chrysalis."),
    "eleftheroi": (
        "Равные из городка Старлайт",
        "Община, где все метки одинаковы, а таланты объявлены причиной раздора. Кто уходит "
        "наёмничать, обычно уже усомнился в равенстве, но привычку держать строй не потерял.",
        "A commune where every cutie mark is the same and talent is declared the root of discord. "
        "Those who leave to sell their swords have usually come to doubt equality, but kept the "
        "habit of holding formation."),
    "hidden_hand": (
        "Предприятие Флима и Флэма",
        "Братья-единороги продают сидр, снадобья и чудеса, а когда обман вскрывается — уводят "
        "повозку в соседнее графство. Наёмники им нужны, чтобы выручка доехала до следующей "
        "ярмарки.",
        "The unicorn brothers sell cider, tonics and miracles, and when the fraud comes out they "
        "wheel their cart to the next county. They hire swords so the takings reach the next fair."),
    "lakepike": (
        "Драконье Пламя",
        "Молодые драконы, которым не досталось ни пещеры, ни клада, и они добывают золото чужой "
        "войной. Воюют жадно и коротко: набрал на первую горку сокровищ — и домой.",
        "Young dragons left without a cave or a hoard, earning their gold in other people's wars. "
        "They fight greedily and briefly: enough for a first pile of treasure, and home they go."),
    "legion_of_the_betrayed": (
        "Лунные Волки",
        "Ночные пони и фестралы, служившие в Ночной страже, а теперь продающие свои крылья. Они "
        "бьются в темноте так же уверенно, как другие при свете дня.",
        "Night ponies and thestrals who once served in the Night Guard and now sell their wings. "
        "They fight in the dark as surely as others fight by daylight."),
    "ghilman": (
        "Абиссинские наёмники",
        "Рота, начатая котами-абиссинцами из Клюгтауна, нынче берёт кого придётся, а больше всего "
        "чейнджлингов из ближних ульев: те и облик сменят, и работают за чужие чувства. Старое имя "
        "оставили нарочно — под ним платят дороже.",
        "A company started by Abyssinian cats out of Klugetown now takes whoever comes, and most "
        "of all changelings from the nearby hives: they will change shape and work for the "
        "feelings of others. The old name is kept on purpose — it commands a higher fee."),
    "skolderbrotva": (
        "Вольные клинки Клюгтауна",
        "Портовый сброд, в котором верх взяли молодые драконы: чешуя держит удар лучше всякой "
        "брони, а жадность до золота сходит за дисциплину. Имени своего города они не позорят — "
        "там тоже не спрашивают, кто ты.",
        "Harbour rabble where young dragons have taken the upper hand: scales stop a blow better "
        "than any armour, and greed for gold passes for discipline. They are no shame to their "
        "town — there, too, no one asks who you are."),
    "beni_zilal": (
        "Тени Улья",
        "Чейнджлинги, которым после примирения ульев стало тесно дома. Они продают то, что умеют "
        "лучше всех: пройти куда угодно под чужим лицом и ударить первыми.",
        "Changelings who found home too small after the hives made their peace. They sell what "
        "they do best: walk in anywhere behind a borrowed face and strike first."),
    "embers_of_flame": (
        "Рота Золотой Подковы",
        "Старая наёмная рота земных пони с добрым именем и высокой ценой. Они не бегут первыми и "
        "не нарушают договора — на этом и держится их слава.",
        "An old earth pony mercenary company with a good name and a high price. They are not the "
        "first to run and they do not break a contract — that is what their fame rests on."),
    "karakhuzaits": (
        "Чёрные Яки",
        "Яки, изгнанные из Яководья за буйство даже по яковским меркам. Ломать они умеют лучше "
        "всех, а строй держат, пока есть кого ломать.",
        "Yaks banished from Yakyakistan for rowdiness even by yak standards. No one smashes "
        "better, and they hold the line as long as there is something to smash."),
    "company_of_the_boar": (
        "Небесные пираты капитана Келено",
        "Команда грифоньего корабля, что ходит под облаками и берёт мзду с воздушных путей. "
        "Келено помнит службу Королю Шторма и больше никому не кланяется.",
        "The crew of a griffon airship that sails below the clouds and levies toll on the sky "
        "roads. Celaeno remembers serving the Storm King and bows to no one now."),
    "wolfskins": (
        "Клинки Горы Арис",
        "Гиппогрифам тесно и на суше, и под водой, поэтому они нанимаются туда, где платят за оба "
        "умения. Сегодня отряд идёт берегом, завтра уходит в море и выныривает у врага в тылу.",
        "Hippogriffs find both the land and the sea too narrow, so they hire out where both "
        "skills are paid for. Today the band marches along the shore, tomorrow it takes to the "
        "water and surfaces behind the enemy."),
    "brotherhood_of_woods": (
        "Братство Вечнодикого Леса",
        "Грифоны-следопыты, осевшие по краю Вечнодикого леса и знающие его лучше любого пони. За "
        "деньги они проведут войско чащей там, где карты кончаются, и не спросят зачем.",
        "Griffon rangers settled along the edge of the Everfree who know it better than any pony. "
        "For coin they will lead an army through the thickets where the maps run out, and will "
        "not ask why."),
    "forest_people": (
        "Ватага Гарбла",
        "Подростки-драконы, которых в Драконьих землях считают шпаной, а в чужих войнах — дорогой "
        "ударной силой. Дисциплины у них нет, зато есть когти, крылья и охота показать себя.",
        "Teenage dragons whom the Dragon Lands write off as louts and other people's wars value "
        "as expensive shock troops. They have no discipline, but they have claws, wings and a "
        "keen wish to show off."),
}

# Clan short name (short_name). The game labels parties on the map with it - "Party ... of clan X",
# - and it is a SEPARATE string from name: while we did not override it, mercenaries on the map still had
# the vanilla Russian clan name with the clan already renamed (noticed in game 2026-09-23).
MINOR_SHORT = {
    "sea_raiders": "Воинство Шторма",
    "desert_bandits": "Стервятники",
    "eleftheroi": "Равные",
    "hidden_hand": "Флим и Флэм",
    "ghilman": "Абиссинцы",
    "skolderbrotva": "Вольные клинки",
    "embers_of_flame": "Золотая Подкова",
    "company_of_the_boar": "Небесные пираты",
    "wolfskins": "Клинки Арис",
    "brotherhood_of_woods": "Братство Леса",
}

# Where mercenary clans live: at the town nearest to this point (metres of our map).
# The other minor clans spread over towns in a round-robin.
MINOR_HOMES = {
    # Home matches who is actually in the clan: changelings at the hives, dragons in the Dragon
    # Lands, griffons in Griffonia, hippogriffs at Mount Aris.
    "ghilman": (316.0, 769.0),                 # Vraks, near the nearer hives
    "beni_zilal": (282.0, 809.0),              # Vesalipolis
    "jawwal": (236.0, 855.0),                  # Ditrisium, the far hive
    "eleftheroi": (798.0, 727.0),              # Starlight's town
    "hidden_hand": (802.0, 506.0),             # Flim and Flam trade in Manehattan
    "embers_of_flame": (552.0, 512.0),         # the Golden Horseshoe Company near Canterlot
    "legion_of_the_betrayed": (332.0, 628.0),  # the Lunar Wolves in Vanhoover
    "lakepike": (588.0, 268.0),                # Dragon Flame near Stableside
    "skolderbrotva": (528.0, 368.0),           # the port rabble of Dodge City
    "company_of_the_boar": (925.0, 765.0),     # Celaeno's pirates near Nuevo Aquila
    "wolfskins": (185.0, 572.0),               # Mount Aris
    "forest_people": (730.0, 304.0),           # a band near the Dragon Lord's Lair
    "karakhuzaits": (707.0, 780.0),            # the former Yaki Clan
}

# Vanilla kingdoms that do not exist in our world. Removed by an XSLT transform.
DROP_KINGDOMS = ["empire_w", "empire_s", "battania"]

# Vanilla cultures left without a kingdom: rename them so that Calradian names do not show up
# on the map and in the encyclopedia. Currently all six cultures are taken by kingdoms.
SPARE_CULTURES = {}
