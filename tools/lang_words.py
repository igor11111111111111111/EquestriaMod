# -*- coding: utf-8 -*-
"""English for the mod's Russian strings. The base XML text comes from here (tools/lang.py).

Two dictionaries:
  PHRASES - a whole string: names that have a canon English spelling, and sentences.
  WORDS   - single words: invented names are built from them (e.g. "Honey Creek").

A string is looked up first as a whole in PHRASES, then word by word in WORDS. Whatever is in neither
stays Russian and is printed in the build report - the dictionary is extended from it.
"""

# ------------------------------------------------------------------ words for compound names
# Adjectives of village and fortress names (VILLAGE_WORDS in make_world.py) and the nouns
# for them (VILLAGE_NOUNS, FORT_NOUNS). Gender forms give one and the same English word.
WORDS = {
    # Equestria
    "Клеверный": "Clover", "Медовый": "Honey", "Солнечный": "Sunny", "Яблочный": "Apple",
    "Росистый": "Dewy", "Радужный": "Rainbow", "Тихий": "Quiet", "Ясный": "Clear",
    "Звёздный": "Star", "Ромашковый": "Daisy", "Пряничный": "Gingerbread", "Лунный": "Moon",
    # Changelings
    "Хитиновый": "Chitin", "Сумрачный": "Dusk", "Жужжащий": "Buzzing", "Пустой": "Hollow",
    "Тёмный": "Dark", "Кислый": "Sour", "Зелёный": "Green", "Смоляной": "Tar",
    "Мёртвый": "Dead", "Чёрный": "Black", "Коконный": "Cocoon",
    # Hippogriffs
    "Приливный": "Tide", "Коралловый": "Coral", "Жемчужный": "Pearl", "Туманный": "Misty",
    "Перьевой": "Feather", "Морской": "Sea", "Бирюзовый": "Turquoise", "Солёный": "Salt",
    "Раковинный": "Shell", "Ветреный": "Windy", "Серебряный": "Silver", "Небесный": "Sky",
    # Dragons
    "Угольный": "Coal", "Пепельный": "Ash", "Огненный": "Fire", "Дымный": "Smoke",
    "Серный": "Sulphur", "Лавовый": "Lava", "Каменный": "Stone", "Жаркий": "Scorch",
    "Чешуйчатый": "Scale", "Рубиновый": "Ruby", "Обсидиановый": "Obsidian",
    "Вулканический": "Volcano",
    # Yaks
    "Ячий": "Yak", "Снежный": "Snow", "Ледяной": "Ice", "Громовой": "Thunder",
    "Мшистый": "Moss", "Горный": "Mountain", "Буйный": "Wild", "Рогатый": "Horn",
    "Белый": "White", "Суровый": "Grim", "Высокий": "High",
    # Griffons
    "Грифоний": "Gryphon", "Орлиный": "Eagle", "Золотой": "Gold", "Скалистый": "Cliff",
    "Ледовый": "Frost", "Пограничный": "Border", "Вольный": "Free", "Когтистый": "Talon",
    # Deer (formerly qilin - the realm became Olenia)
    "Осенний": "Autumn", "Кленовый": "Maple", "Янтарный": "Amber", "Цветущий": "Blossom",
    "Молчаливый": "Silent", "Сияющий": "Shining", "Рыжий": "Russet",
    # nouns
    "Луг": "Meadow", "Ручей": "Creek", "Холм": "Hill", "Брод": "Ford", "Дол": "Vale",
    "Бор": "Pinewood", "Яр": "Bluff", "Хутор": "Croft", "Родник": "Spring", "Выселок": "Hamlet",
    "Кряж": "Ridge", "Утёс": "Crag", "Застава": "Watch", "Твердыня": "Hold",
    "Перевал": "Pass", "Оплот": "Bastion",

    # Lands around settlements: the English name is the area type in the XML
    "Закоулок": "Backstreet", "Пустырь": "Clearing", "Набережная": "Waterfront",
    "Выгон": "Pasture", "Чаща": "Thicket", "Топь": "Bog",

    # Syllables of pony names (NAMES in world_data.py): almost all are English words written in Cyrillic
    "Санни": "Sunny", "Мун": "Moon", "Стар": "Star", "Эппл": "Apple", "Клауд": "Cloud",
    "Свифт": "Swift", "Голден": "Golden", "Брайт": "Bright", "Сильвер": "Silver",
    "Дасти": "Dusty", "Хани": "Honey", "Роуз": "Rose", "Свит": "Sweet", "Лили": "Lily",
    "Мисти": "Misty", "Пинки": "Pinkie", "Дэш": "Dash", "Харт": "Heart", "Мейн": "Mane",
    "Лайт": "Light", "Сонг": "Song", "Хуф": "Hoof", "Брэйв": "Brave", "Филд": "Field",
    "Спаркл": "Sparkle", "Блум": "Bloom", "Свирл": "Swirl", "Белль": "Belle",
    "Шайн": "Shine", "Шайнинг": "Shining", "Блейз": "Blaze", "Глоу": "Glow",
    "Флэр": "Flare", "Фолл": "Fall", "Форест": "Forest", "Ферн": "Fern", "Синдер": "Cinder",
    "Смоук": "Smoke", "Пампкин": "Pumpkin", "Отем": "Autumn", "Рейн": "Rain",
    "Твайлайт": "Twilight", "Рэйнбоу": "Rainbow", "Эпплджек": "Applejack",
    "Флаттершай": "Fluttershy", "Рарити": "Rarity", "Пай": "Pie", "Старлайт": "Starlight",
    "Кейденс": "Cadance", "Армор": "Armor", "Армора": "Armor", "Сомбры": "Sombra",
    "Селестии": "Celestia", "Луна": "Luna", "Луны": "Luna", "Кризалис": "Chrysalis",
    "Торакса": "Thorax", "Санбёрста": "Sunburst", "Эмбер": "Ember", "Смолдер": "Smolder",
    "Гарбл": "Garble", "Гарбла": "Garble", "Кламп": "Clump", "Сладж": "Sludge",
    "Торч": "Torch", "Фьюм": "Fume", "Вракс": "Vrax", "Маффин": "Muffin", "Гольд": "Gold",
    "Спитфайр": "Spitfire", "Флэш": "Flash", "Фэнси": "Fancy", "Нуво": "Nouveau",
    "Филти": "Filthy", "Рич": "Rich", "Даймонд": "Diamond", "Биг": "Big",
    "Макинтош": "McIntosh", "Баттер": "Butter", "Скут": "Scoot",
    "Ми": "Mi", "Аморе": "Amore", "Хоуп": "Hope", "Радиант": "Radiant",
    "Сильверстрим": "Silverstream", "Йона": "Yona", "Шай": "Shy", "Пэнтс": "Pants",
    "Мейрпоза": "Mareposa", "Меткоискательница": "Cutie Mark Crusader",

    # Syllables of griffon and hippogriff names
    "Гильда": "Gilda", "Грета": "Greta", "Гровер": "Grover", "Гровера": "Grover",
    "Гюстав": "Gustave", "Гюстава": "Gustave", "Грифф": "Gruff", "Гюнтер": "Gunther",
    "Генрих": "Heinrich", "Вильгельм": "Wilhelm", "Эрвин": "Erwin", "Готфрид": "Gottfried",
    "Хельга": "Helga", "Ильза": "Ilse", "Лизель": "Liesel", "Марта": "Marta",
    "Улла": "Ulla", "Эрика": "Erika", "Астрид": "Astrid",
    "Редтейл": "Redtail", "Голдкрест": "Goldcrest", "Сильвервинг": "Silverwing",
    "Айронкло": "Ironclaw", "Роузталон": "Rosetalon", "Роккло": "Rockclaw",
    "Эшклоу": "Ashclaw", "Блэкпик": "Blackpeak", "Хайхилл": "Highhill",
    "Стормфезер": "Stormfeather", "Сноуфезер": "Snowfeather", "Уайтфезер": "Whitefeather",
    "Брайтвинг": "Brightwing", "Уайтбелл": "Whitebell", "Фейрфланкс": "Fairflank",
    "Винг": "Wing", "Бик": "Beak", "Скай": "Sky", "Мист": "Mist", "Флоу": "Flow",
    "Вейв": "Wave", "Перл": "Pearl", "Ривер": "River", "Си": "Sea", "Стрим": "Stream",
    "Фезер": "Feather", "Корал": "Coral", "Оушен": "Ocean", "Тайд": "Tide",
    "Шелл": "Shell", "Спрей": "Spray", "Глайд": "Glide", "Бриз": "Breeze",
    "Фаер": "Fire", "Флейм": "Flame", "Шторм": "Storm", "Шторма": "Storm", "Эш": "Ash",
    "Стоун": "Stone", "Ридж": "Ridge", "Мар": "Mar", "Лиф": "Leaf", "Бранч": "Branch",
    "Гроув": "Grove", "Мейпл": "Maple", "Сидар": "Cedar", "Спринг": "Spring",
    "Блоссом": "Blossom", "Трейл": "Trail", "Скалл": "Skull", "Идол": "Idol",
    "Фоллс": "Falls", "Холлоу": "Hollow", "Шоалс": "Shoals", "Джанкшн": "Junction",

    # Words from which realm names, titles and descriptions are built
    "Эквестрия": "Equestria", "Эквестрии": "Equestria", "Солнечная": "Solar",
    "Лунная": "Lunar", "Дружбы": "Friendship", "Кристальная": "Crystal",
    "Кристальной": "Crystal", "Кристальное": "Crystal", "Кристальный": "Crystal",
    "Империя": "Empire", "Империи": "Empire", "Грифонстоун": "Griffonstone",
    "Грифонстоуна": "Griffonstone", "Гиппогриффия": "Hippogriffia",
    "Якьякистан": "Yakyakistan", "Оления": "Olenia", "Олении": "Olenia",
    "Драконьи": "Dragon", "Драконы": "Dragons", "драконов": "dragons",
    "Ульи": "Hives", "Улей": "Hive", "ульев": "hives", "Чейнджлинги": "Changelings",
    "чейнджлингов": "changelings", "Яки": "Yaks", "яков": "yaks", "Як": "Yak",
    "Грифоны": "Gryphons", "грифонов": "gryphons", "Гиппогрифы": "Hippogriffs",
    "гиппогрифов": "hippogriffs", "пони": "pony", "Пони": "Pony",
    "Северная": "North", "Берег": "Shore", "Бухта": "Bay", "Гнездо": "Nest",
    "Гряда": "Ridge", "Долина": "Vale", "Роща": "Grove", "Равнина": "Plain",
    "Земли": "Lands", "Земля": "Land", "земли": "lands", "земель": "lands",
    "Порт": "Port", "Форт": "Fort", "Логово": "Lair", "Кокон": "Cocoon",
    "Пламя": "Flame", "Тени": "Shades", "Сердце": "Heart", "Скипетр": "Sceptre",
    "Арка": "Arch", "Венок": "Wreath", "Горное": "Mountain", "Цветочный": "Flower",
    "Ночной": "Night", "Штормовой": "Storm", "Королевская": "Royal",
    "Королевство": "Kingdom", "Король": "King", "Короля": "King", "Королева": "Queen",
    "Принцесса": "Princess", "Принц": "Prince", "Лорд": "Lord", "лорд": "lord",
    "Капитан": "Captain", "Командир": "Commander", "Страж": "Guard",
    "Стражница": "Guard", "стражи": "guard", "стража": "guard", "дозоров": "watch",
    "Хранитель": "Keeper", "Хранительница": "Keeper", "хранительница": "keeper",
    "Старейшина": "Elder", "старейшина": "elder", "Кузнец": "Smith",
    "Следопыт": "Pathfinder", "Разведчик": "Scout", "Охотник": "Hunter",
    "Пилот": "Flyer", "Лётчица": "Flyer", "Меняла": "Trader", "Сказитель": "Storyteller",
    "Задира": "Bully", "Хозяйка": "Mistress", "Предводительница": "Chieftain",
    "Мать": "Mother", "Отец": "Father", "Брат": "Brother", "брат": "brother",
    "Дочь": "Daughter", "Жена": "Wife", "Семья": "Family", "семьи": "family",
    "Род": "House", "Дом": "House", "сестра": "sister", "сестёр": "sisters",
    "Младшая": "the Younger", "Старшая": "the Elder", "Вторая": "the Second", "Третья": "the Third",
    "Бывший": "Former",
    "Пир": "Pear", "Пингвинья": "Penguin", "Арктик": "Arctic",

    # Added clans (tools/world_fill.py): the word before the name and spare name syllables
    "Клан": "Clan", "Коппер": "Copper", "Айрон": "Iron", "Ноубл": "Noble", "Стил": "Steel",
    "Винд": "Wind", "Флауэр": "Flower", "Дью": "Dew",
    # when the names in the pool run out, a nickname is added to the name
    "Младший": "the Younger", "Старший": "the Elder", "Второй": "the Second", "Третий": "the Third",
    "Лавендер": "Lavender", "Черри": "Cherry", "Дейзи": "Daisy", "Виолет": "Violet",
    # dragons
    "Бэйзальт": "Basalt", "Игнис": "Ignis", "Крэг": "Crag", "Молтен": "Molten",
    "Обсидиан": "Obsidian", "Пирит": "Pyrite", "Смог": "Smog", "Тиндер": "Tinder",
    "Фёрнас": "Furnace", "Чар": "Char", "Шейл": "Shale", "Эмбер-Кло": "Ember-Claw",
    "Брэйзер": "Brazier", "Кальдер": "Calder", "Слэг": "Slag", "Фьюри": "Fury",
    "Ашера": "Ashera", "Бласта": "Blasta", "Глоуин": "Glowin", "Дрейка": "Drake",
    "Кальдера": "Caldera", "Кармина": "Carmina", "Пирра": "Pyrra", "Сцинтилла": "Scintilla",
    "Тефра": "Tephra", "Файра": "Fyra", "Хэйз": "Haze", "Эмберли": "Emberly",
    "Ардора": "Ardora", "Вулкана": "Vulcana", "Игнита": "Ignita", "Скарлет": "Scarlet",
    "Скорч": "Scorch", "Клинкер": "Clinker", "Флинт": "Flint", "Бласт": "Blast",
    "Гриммер": "Grimmer", "Сажень": "Soot", "Рокот": "Rumble", "Уголь": "Coal", "Шлак": "Cinderblock",
    "Зольник": "Ashpit", "Жар": "Heat", "Искра": "Spark", "Синдра": "Cindra", "Лава": "Lava",
    "Зола": "Ash", "Магма": "Magma", "Фларэ": "Flare", "Опалина": "Opaline", "Вспышка": "Flash",
    "Пепелина": "Ashlyn", "Руби": "Ruby", "Гарнет": "Garnet", "Жарина": "Zharina", "Тлея": "Smoulder",
    # deer of Olenia: a northern first name, the second word is a family nickname (world_data.NAMES["nord"]).
    # Without these entries names would be spelled letter by letter: the Russian spelling of Jelzek would come out Yeltsek.
    "Йохан": "Johan", "Бенджен": "Benjen", "Хьялмар": "Hjalmar", "Эйнар": "Einar",
    "Торвин": "Torvin", "Свейн": "Svein", "Ярве": "Jarve", "Алмо": "Almo",
    "Рейно": "Reino", "Тапио": "Tapio", "Вилле": "Ville", "Ансси": "Anssi",
    "Урхо": "Urho", "Кауко": "Kauko", "Лаури": "Lauri", "Ээро": "Eero",
    "Вельвет": "Velvet", "Аслауг": "Aslaug", "Ильта": "Ilta", "Сигне": "Signe",
    "Хелми": "Helmi", "Айно": "Aino", "Кайса": "Kaisa", "Мерья": "Merja",
    "Тууликки": "Tuulikki", "Пихла": "Pihla", "Веса": "Vesa", "Марьятта": "Marjatta",
    "Сату": "Satu", "Элина": "Elina", "Кирси": "Kirsi", "Линнеа": "Linnea",
    "Йельцек": "Jelzek", "Кудлинен": "Kudlinen", "Хьорт": "Hjort", "Сарвинен": "Sarvinen",
    "Метсола": "Metsola", "Ярвинен": "Jarvinen", "Лехто": "Lehto", "Салонен": "Salonen",
    "Корпи": "Korpi", "Виронен": "Vironen", "Аалто": "Aalto", "Хирви": "Hirvi",
}

# Canon English spellings. They must be kept here: otherwise the name is spelled in Latin
# letter by letter and comes out Kanterlot instead of Canterlot. What got spelled letter by letter is shown in the
# build report (tools/lang_missing.txt, bottom section).
CANON = {
    # towns and lands
    "Кантерлот": "Canterlot", "Понивилль": "Ponyville", "Клаудсдейл": "Cloudsdale",
    "Мейнхеттен": "Manehattan", "Филлидельфия": "Fillydelphia", "Лас-Пегасус": "Las Pegasus",
    "Балтимейр": "Baltimare", "Ванхувер": "Vanhoover", "Эпплуза": "Appleloosa",
    "Додж-Сити": "Dodge City", "Додж Джанкшн": "Dodge Junction", "Сомнамбула": "Somnambula",
    "Сиэддл": "Seaddle", "Уиннияполис": "Whinnyapolis", "Винниаполис": "Whinnyapolis",
    "Виннисота": "Whinnysota", "Бридлполис": "Bridlepolis", "Кантерхорн": "Canterhorn",
    "Полые Тени": "Hollow Shades", "Ниагра Фоллс": "Neighagara Falls",
    "Сильвер Шоалс": "Silver Shoals", "Винсом Фоллс": "Winsome Falls",
    "Сэддл Лейк": "Saddle Lake", "Мэйнфорд": "Maneford", "Солнцепад": "Sunfall",
    "Вечнодикий Лес": "Everfree Forest", "Гора Арис": "Mount Aris", "Сиквестрия": "Seaquestria",
    "Клугтаун": "Klugetown", "Клюгтаун": "Klugetown", "Яктаун": "Yaktown",
    "Кристальный Город": "Crystal City", "Кристальный Пик": "Crystal Peak",
    "Весалиполис": "Vesalipolis", "Дитрисиум": "Ditrisium", "Грифонстоун": "Griffonstone",
    "Наш Городок": "Our Town", "Горы Макинтоша": "Macintosh Hills",
    "Верхний Макинтош": "Upper Macintosh", "Величественные Сады": "Grand Gardens",
    "Гранд Пир": "Grand Pear", "Акадия Бэй": "Acadia Bay",
    # troops and families
    "Вандерболты": "Wonderbolts", "Алмазные Псы": "Diamond Dogs", "Дезертиры": "Deserters",
    "Мародёры": "Looters", "Тимбервульфы": "Timberwolves",
    "Воинство Короля Шторма": "The Storm King's Host",
    "Братство Вечнодикого Леса": "Brotherhood of the Everfree",
    "Зебры Зебрики": "Zebras of Zebrica", "Драконье Пламя": "Dragonfire",
    "Чёрные Яки": "Black Yaks", "Лунные Волки": "Moon Wolves", "Лесной Народ": "Forest Folk",
    "Рота Золотой Подковы": "The Golden Horseshoe Company",
    # short clan names (short_name): the game labels parties on the map with them
    "Воинство Шторма": "The Storm Host", "Стервятники": "Vultures", "Равные": "The Equals",
    "Флим и Флэм": "Flim and Flam", "Абиссинцы": "Abyssinians",
    "Вольные клинки": "Free Blades", "Золотая Подкова": "Golden Horseshoe",
    "Небесные пираты": "Sky Pirates", "Клинки Арис": "Blades of Aris",
    "Братство Леса": "Brotherhood of the Woods",
    "Тяжёлая местность": "Rough country",
    "Переход реки вброд": "Fording a river",
    "Тени Улья": "Shadows of the Hive", "Верные Хризалиде": "Chrysalis's Faithful",
    "Клинки Горы Арис": "Blades of Mount Aris",
    "Ватага Гарбла": "Garble's Gang",
    "Логово Лорда Драконов": "The Dragon Lord's Lair",
    "Стервятники Бесплодных Земель": "Vultures of the Badlands",
    "Степные Шакалы": "Steppe Jackals", "Стервятники Бесплодных земель": "Badlands Vultures",
    "Земли чейнджлингов": "Changeling Lands",
    "Королевство Оления": "Kingdom of Olenia",
    "Дом Йельцека": "House of Jelzek", "Дом Вельвет": "House of Velvet",
    "Дом Кудлинен": "House of Kudlinen",
    "Эквестрия Дружбы": "Equestria of Friendship",
    "Род Резерфорда": "House of Rutherford", "Род Тиры": "House of Thyra",
    "Род Торча": "House of Torch", "Улей Синовиала": "Hive of Synovial",
    "Улей Жужжа": "Hive Buzz", "Улей Прорезь": "Hive Slit", "Улей Цикад": "Hive Cicada",
    "Клан Лейф": "Clan Leif",
    "Дом Солнца": "House of the Sun", "Дом Ночи": "House of Night",
    "Дом Ново": "House of Novo", "Дом Сиспрея": "House of Seaspray",
    "Грифонстоунский Род": "House of Griffonstone", "Джаки-клан": "Jaki Clan",
    # heroes
    "Селестия": "Celestia", "Луна": "Luna", "Твайлайт Спаркл": "Twilight Sparkle",
    "Кейденс": "Cadance", "Шайнинг Армор": "Shining Armor", "Флурри Харт": "Flurry Heart",
    "Спайк": "Spike", "Рэйнбоу Дэш": "Rainbow Dash", "Эпплджек": "Applejack",
    "Рарити": "Rarity", "Флаттершай": "Fluttershy", "Пинки Пай": "Pinkie Pie",
    "Старлайт Глиммер": "Starlight Glimmer", "Санбёрст": "Sunburst", "Трикси": "Trixie",
    "Бабуля Смит": "Granny Smith", "Биг Макинтош": "Big McIntosh", "Эппл Блум": "Apple Bloom",
    "Брейберн": "Braeburn", "Брайт Мак": "Bright Mac", "Пир Баттер": "Pear Butter",
    "Свити Белль": "Sweetie Belle", "Скуталу": "Scootaloo", "Даймонд Тиара": "Diamond Tiara",
    "Сильвер Спун": "Silver Spoon", "Филти Рич": "Filthy Rich", "Спойлд Рич": "Spoiled Rich",
    "Дерпи": "Derpy", "Зефир Бриз": "Zephyr Breeze", "Джентл Бриз": "Gentle Breeze",
    "Мод Пай": "Maud Pie", "Марбл Пай": "Marble Pie", "Лаймстоун Пай": "Limestone Pie",
    "Фэнси Пэнтс": "Fancy Pants", "Флёр де Лис": "Fleur de Lis", "Блюблад": "Blueblood",
    "Принц Блюблад": "Prince Blueblood", "Спитфайр": "Spitfire", "Сорин": "Soarin",
    "Лайтнинг Даст": "Lightning Dust", "Старсвирл": "Star Swirl",
    "Старсвирл Бородатый": "Star Swirl the Bearded", "Рокхуф": "Rockhoof",
    "Флэш Магнус": "Flash Magnus", "Сомбра": "Sombra", "Кризалис": "Chrysalis",
    "Торакс": "Thorax", "Фаринкс": "Pharynx", "Эмбер": "Ember", "Гарбл": "Garble",
    "Смолдер": "Smolder", "Торч": "Torch", "Лорд Торч": "Lord Torch",
    "Гильда": "Gilda", "Грета": "Greta", "Габби": "Gabby", "Гровер Второй": "Grover II",
    "Дедушка Грифф": "Grandpa Gruff", "Гюстав ле Гранд": "Gustave le Grand",
    "Ново": "Novo", "Королева Ново": "Queen Novo", "Сильверстрим": "Silverstream",
    "Террамар": "Terramar", "Генерал Сиспрей": "General Seaspray",
    "Резерфорд": "Rutherford", "Принц Резерфорд": "Prince Rutherford", "Йона": "Yona",
    "Отем Блейз": "Autumn Blaze", "Рейн Шайн": "Rain Shine", "Даск Шайн": "Dusk Shine",
    "Меткоискатели": "Cutie Mark Crusaders", "Элементы Гармонии": "Elements of Harmony",
    # canon companions (world_data.CANON_COMPANIONS)
    "Лира Хартстрингс": "Lyra Heartstrings", "Бон Бон": "Bon Bon", "Октавия Мелоди": "Octavia Melody",
    "Винил Скрэтч": "Vinyl Scratch", "Дерпи Хувс": "Derpy Hooves", "Доктор Хувз": "Doctor Whooves",
    "Чирайли": "Cheerilee", "Зекора": "Zecora", "Чиз Сэндвич": "Cheese Sandwich",
    "Дэринг Ду": "Daring Do", "Коко Помель": "Coco Pommel", "Сасси Сэддлс": "Sassy Saddles",
    "Минуэтт": "Minuette", "Лемон Хартс": "Lemon Hearts", "Твинклшайн": "Twinkleshine",
    "Сансет Шиммер": "Sunset Shimmer", "Темпест Шадоу": "Tempest Shadow", "Квиббл Пэнтс": "Quibble Pants",
    "Винд Райдер": "Wind Rider", "Скай Стингер": "Sky Stinger", "Вейпор Трейл": "Vapor Trail",
    "Кэррот Топ": "Carrot Top", "Нёрс Редхарт": "Nurse Redheart", "Мэр Мэйр": "Mayor Mare",
    "Гэллус": "Gallus", "Джимми Мор": "Gimme Moar", "Хейвен Бэй": "Haven Bay", "Салина Блу": "Salina Blue",
    "Билли": "Billy", "Крэкл": "Crackle", "Оцеллус": "Ocellus",
    # secondary lore names (NAMES, fourth element)
    "Кэррамел": "Caramel", "Дэвенпорт": "Davenport", "Лаки Кловер": "Lucky Clover", "Ноутворти": "Noteworthy",
    "Мистер Кейк": "Mr. Cake", "Хойти Тойти": "Hoity Toity", "Джет Сет": "Jet Set", "Бёрнт Оук": "Burnt Oak",
    "Голден Харвест": "Golden Harvest", "Шайнинг Стар": "Shining Star", "Комет Тейл": "Comet Tail",
    "Стар Хантер": "Star Hunter", "Мидлайт": "Midlight", "Найт Глайдер": "Night Glider",
    "Дабл Даймонд": "Double Diamond", "Парти Фейвор": "Party Favor", "Санни Дейз": "Sunny Daze",
    "Кранки Дудл": "Cranky Doodle", "Фезервейт": "Featherweight", "Пипсквик": "Pipsqueak",
    "Сноуфлейк": "Snowflake", "Булк Бицепс": "Bulk Biceps", "Трендерхуф": "Trenderhoof",
    "Тандер Клэп": "Thunder Clap", "Рамбл": "Rumble", "Снипс": "Snips", "Снейлс": "Snails",
    "Файрболл": "Fireball", "Флим": "Flim", "Флэм": "Flam",
    "Роузлак": "Roseluck", "Лили Вэлли": "Lily Valley", "Берри Панч": "Berry Punch",
    "Миссис Кейк": "Mrs. Cake", "Эмбер Уэйвс": "Amber Waves", "Мэйн Гудолл": "Mane Goodall",
    "Сапфир Шорс": "Sapphire Shores", "Колоратура": "Coloratura", "Уайт Лайтнинг": "White Lightning",
    "Клауд Кикер": "Cloud Kicker", "Блоссомфорт": "Blossomforth", "Флиттер": "Flitter",
    "Клаудчейзер": "Cloudchaser", "Медли": "Medley", "Черри Берри": "Cherry Berry",
    "Голди Делишес": "Goldie Delicious", "Апл Фриттер": "Apple Fritter", "Апл Сайдер": "Apple Cider",
    "Черри Джубили": "Cherry Jubilee", "Хани Лемон": "Honey Lemon", "Ноктюрн": "Nocturne",
    "Бланкет": "Blanket", "Дитзи Ду": "Ditzy Doo", "Твист": "Twist", "Даймонд Минт": "Diamond Mint",
    "Лотус Блоссом": "Lotus Blossom", "Алоэ": "Aloe", "Сирена": "Sirena", "Тандер Флэш": "Thunder Flash",
    "Мэй": "May", "Рэйндропс": "Raindrops", "Лайтнинг Болт": "Lightning Bolt", "Сасси Свит": "Sassy Sweet",
}


# ------------------------------------------------------------------ whole strings
# Everything that cannot be built from words: hero and realm descriptions, mercenary party names,
# companion nicknames. Canon names are taken in English (Wonderbolts, Idol of Boreas,
# Sweet Apple Acres), not Russian ones spelled in Latin.
PHRASES = {
    # ---- spells (tools/make_spells.py)
    "Огненный шар": "Fireball",
    "Сгусток пламени: взрывается там, куда попал, и обжигает всех вокруг. "
    "Драконы плюются им от рождения, единороги учатся годами.":
        "A ball of flame: it bursts where it lands and scorches everyone nearby. "
        "Dragons spit it from birth; unicorns study for years.",
    "Мана": "Mana",
    "Магия": "Magic",
    "Мана копится в пути по карте и тратится на заклинания.":
        "Mana builds up as you travel the map and is spent on spells.",
    "Не хватает маны": "Not enough mana",
    "Заклинание ещё не готово": "Spell is not ready yet",
    "Заклинаний нет": "No spells known",
    "ЛКМ — пустить, ПКМ — отмена": "Left click to cast, right click to cancel",
    # ---- mercenaries, free companies and other parties
    "Абиссинские наёмники": "Abyssinian Mercenaries",
    "Бизоны вождя Тандерхувса": "Chief Thunderhooves' Buffalo",
    "Вольные клинки Клюгтауна": "Free Blades of Klugetown",
    "Небесные пираты капитана Келено": "Captain Celaeno's Sky Pirates",
    "Предприятие Флима и Флэма": "The Flim Flam Brothers' Enterprise",
    "Равные из городка Старлайт": "The Equals of Our Town",
    "Штормовая гвардия": "The Storm Guard",
    "Кристальные хранители": "Crystal Keepers",
    "Ночная стража": "Night Guard",
    "Королевство горы Арис": "Kingdom of Mount Aris",
    "Гюстав ле Гран": "Gustave le Grand",
    "Флёр де Лис": "Fleur de Lis",
    "Гиацинтовые холмы": "Hyacinth Hills",
    "Обитель отшельника": "Hermit's Retreat",

    # ---- descriptions of added lords (tools/world_fill.py, TEXTS)
    "Знатный пони Эквестрии.": "A noble pony of Equestria.",
    "Знатная пони Эквестрии.": "A noble mare of Equestria.",
    "Жеребёнок из знатного рода.": "A foal of a noble house.",
    "Знатный гиппогриф горы Арис.": "A noble hippogriff of Mount Aris.",
    "Знатная гиппогрифка горы Арис.": "A noble hippogriff of Mount Aris.",
    "Птенец из знатного гнезда.": "A fledgling of a noble nest.",
    "Знатный олень Олении.": "A noble stag of Olenia.",
    "Знатная олениха Олении.": "A noble doe of Olenia.",
    "Оленёнок из знатного дома.": "A fawn of a noble house.",
    "Знатный грифон Грифонстоуна.": "A noble gryphon of Griffonstone.",
    "Знатная грифонша Грифонстоуна.": "A noble gryphon of Griffonstone.",
    "Дракон из знатного клана.": "A dragon of a noble clan.",
    "Драконица из знатного клана.": "A dragoness of a noble clan.",
    "Дракончик из знатного клана.": "A young dragon of a noble clan.",
    "Як из знатного клана.": "A yak of a noble clan.",
    "Якесса из знатного клана.": "A yak of a noble clan.",
    "Ячонок из знатного клана.": "A yak calf of a noble clan.",
    "Чейнджлинг из знатного улья.": "A changeling of a noble hive.",
    "Личинка знатного улья.": "A grub of a noble hive.",

    # ---- hand-written strings (character creation screen, guard, peoples)
    "Вы родились пони — единорогом, пегасом или земным пони. Судьба привела вашу семью в земли "
    "Империи, где вы и выросли: ваше детство и юность пройдут по имперскому укладу.":
        "You were born a pony — a unicorn, a pegasus or an earth pony. Fate brought your family to "
        "the lands of the Empire, and there you grew up: your childhood and youth follow imperial "
        "custom.",
    "Королевский гвардеец Эквестрии": "Royal Guard of Equestria",
    "Чейнджлинг": "Changeling",
    "Олень": "Deer",
    "Грифон": "Gryphon",
    "Дракон": "Dragon",
    "Гиппогриф": "Hippogriff",

    # ---- troops: griffons (Griffonstone)
    "Птенец Грифонстоуна": "Griffonstone Fledgling",
    "Грифон с арбалетом": "Gryphon Crossbowman",
    "Скальный арбалетчик": "Cliff Crossbowman",
    "Бывалый арбалетчик утёсов": "Hardened Cliff Crossbowman",
    "Меткий глаз Бориаса": "Keen Eye of Boreas",
    "Копейщик гнезда": "Nest Spearman",
    "Страж гнезда": "Nest Guard",
    "Крюкастый страж": "Hooked Guard",
    "Секироносец Грифонстоуна": "Griffonstone Axebearer",
    "Пикинёр Хребта": "Ridge Pikeman",
    "Клинок Грифонстоуна": "Blade of Griffonstone",
    "Сержант Идола": "Sergeant of the Idol",
    "Небесный дозорный": "Sky Watcher",
    "Крылатый налётчик": "Winged Raider",
    "Авангард Хребта": "Vanguard of the Ridge",
    "Оруженосец Идола": "Squire of the Idol",
    "Молодой когтеносец": "Young Talonbearer",
    "Когтеносец Грифонстоуна": "Talonbearer of Griffonstone",
    "Поборник Бориаса": "Champion of Boreas",
    "Знаменосец Идола": "Banner Knight of the Idol",
    "Ополченец Грифонстоуна": "Griffonstone Militia",
    "Ополченец-арбалетчик": "Militia Crossbowman",
    "Пехотинец Грифонстоуна": "Griffonstone Infantryman",
    "Бывалый ополченец Грифонстоуна": "Veteran Griffonstone Militia",
    "Бывалый ополченец-арбалетчик": "Veteran Militia Crossbowman",
    # griffons on the khuzait branch (swapped with yaks 10.10.2026, make_troops.SWAP_CULTURES)
    "Грифон-боец": "Gryphon Fighter",
    "Грифон-налётчик": "Gryphon Raider",
    "Небесный стрелок Грифонстоуна": "Griffonstone Sky Archer",
    "Тяжёлый небесный стрелок": "Heavy Sky Archer",
    "Крылатый копейщик Грифонстоуна": "Winged Lancer of Griffonstone",
    "Охотник утёсов": "Cliff Hunter",
    "Лучник Грифонстоуна": "Griffonstone Archer",
    "Опытный копейщик гнезда": "Veteran Nest Spearman",
    "Сын знатного гнезда": "Highborn Nest Son",
    "Стража Идола Бориаса": "Guard of the Idol of Boreas",
    "Ополченец-лучник Грифонстоуна": "Griffonstone Militia Archer",
    "Бывалый ополченец-лучник Грифонстоуна": "Veteran Griffonstone Militia Archer",

    # ---- troops: hippogriffs (Mount Aris and Seaquestria)
    "Доброволец горы Арис": "Mount Aris Volunteer",
    "Воин горы Арис": "Mount Aris Warrior",
    "Обученный воин Ариса": "Trained Warrior of Aris",
    "Отборный воин Ариса": "Picked Warrior of Aris",
    "Присяжный страж королевы Ново": "Queen Novo's Oathsworn",
    "Небесный разведчик": "Sky Scout",
    "Всадник прибоя": "Surf Rider",
    "Бегун по рифам": "Reef Runner",
    "Налётчик Сиквестрии": "Seaquestria Raider",
    "Клинок прибоя": "Blade of the Surf",
    "Ветеран прибоя": "Surf Veteran",
    "Метатель гарпунов": "Harpoon Thrower",
    "Опытный гарпунщик": "Veteran Harpooner",
    "Рифовый буян": "Reef Wildling",
    "Летучий гарпунщик": "Flying Harpooner",
    "Птенец знатного гнезда": "Highborn Fledgling",
    "Знатный воин Ариса": "Highborn Warrior of Aris",
    "Герой горы Арис": "Hero of Mount Aris",
    "Страж Жемчужины": "Warden of the Pearl",
    "Поборник Жемчужины": "Champion of the Pearl",
    "Ополченец горы Арис": "Mount Aris Militia",
    "Ополченец-лучник горы Арис": "Mount Aris Militia Archer",
    "Бывалый ополченец горы Арис": "Veteran Mount Aris Militia",
    "Бывалый ополченец-лучник горы Арис": "Veteran Mount Aris Militia Archer",

    # ---- troops: dragons (Dragon Lands)
    "Юный дракон": "Young Dragon",
    "Драконий боец": "Dragon Fighter",
    "Драконий воин": "Dragon Warrior",
    "Копейщик пепла": "Ash Spearman",
    "Тяжёлый копейщик вулкана": "Heavy Volcano Spearman",
    "Секироносец лавы": "Lava Axebearer",
    "Пламенный буян": "Flame Brawler",
    "Ярость Состязания": "Fury of the Gauntlet",
    "Лазутчик ущелий": "Canyon Prowler",
    "Налётчик бесплодных скал": "Badland Crag Raider",
    "Бывалый налётчик скал": "Hardened Crag Raider",
    "Летучий налётчик": "Flying Raider",
    "Охотник за самоцветами": "Gem Hunter",
    "Драконий лучник": "Dragon Archer",
    "Меткий стрелок вулкана": "Volcano Marksman",
    "Отпрыск драконьего рода": "Scion of a Dragon Clan",
    "Страж Скипетра": "Warden of the Scepter",
    "Ветеран Скипетра": "Veteran of the Scepter",
    "Дружинник лорда драконов": "Dragon Lord's Retainer",
    "Поборник Состязания": "Champion of the Gauntlet",
    "Ополченец Драконьих Земель": "Dragon Lands Militia",
    "Ополченец-лучник Драконьих Земель": "Dragon Lands Militia Archer",
    "Бывалый ополченец Драконьих Земель": "Veteran Dragon Lands Militia",
    "Бывалый ополченец-лучник Драконьих Земель": "Veteran Dragon Lands Militia Archer",

    # ---- troops: yaks (Yakyakistan)
    "Молодой як": "Young Yak",
    "Як-боец": "Yak Fighter",
    "Як-налётчик": "Yak Raider",
    "Верховой стрелок Якьякистана": "Yakyakistan Mounted Archer",
    "Тяжёлый верховой стрелок": "Heavy Mounted Archer",
    "Всадник тундры": "Tundra Rider",
    "Копейщик-всадник Якьякистана": "Yakyakistan Lancer",
    "Тяжёлый всадник Якьякистана": "Heavy Yakyakistan Lancer",
    "Пеший як": "Yak Footman",
    "Охотник ледника": "Glacier Hunter",
    "Лучник Якьякистана": "Yakyakistan Archer",
    "Меткий лучник ледника": "Glacier Marksman",
    "Копейщик Яктауна": "Yakistown Spearman",
    "Опытный копейщик Яктауна": "Veteran Yakistown Spearman",
    "Крушитель": "Smasher",
    "Сын знатного яка": "Highborn Yak's Son",
    "Гвардеец Яктауна": "Yakistown Guard",
    "Старший гвардеец Яктауна": "Senior Yakistown Guard",
    "Телохранитель принца": "Prince's Bodyguard",
    "Стража принца Резерфорда": "Prince Rutherford's Guard",
    "Ополченец Якьякистана": "Yakyakistan Militia",
    "Ополченец-лучник Якьякистана": "Yakyakistan Militia Archer",
    "Бывалый ополченец Якьякистана": "Veteran Yakyakistan Militia",
    "Бывалый ополченец-лучник Якьякистана": "Veteran Yakyakistan Militia Archer",
    # yaks on the vlandian branch (swapped with griffons 10.10.2026, make_troops.SWAP_CULTURES)
    "Як с арбалетом": "Yak Crossbowman",
    "Арбалетчик ледника": "Glacier Crossbowman",
    "Бывалый арбалетчик ледника": "Hardened Glacier Crossbowman",
    "Меткий арбалетчик Якьякистана": "Yakyakistan Sharpshooter",
    "Крюкастый як": "Hooked Yak",
    "Секироносец Якьякистана": "Yakyakistan Axebearer",
    "Пикинёр Яктауна": "Yakistown Pikeman",
    "Клинок Якьякистана": "Blade of Yakyakistan",
    "Авангард Якьякистана": "Vanguard of Yakyakistan",
    "Молодой гвардеец Яктауна": "Young Yakistown Guard",
    "Ополченец-арбалетчик Якьякистана": "Yakyakistan Militia Crossbowman",
    "Бывалый ополченец-арбалетчик Якьякистана": "Veteran Yakyakistan Militia Crossbowman",
    "Пехотинец Якьякистана": "Yakyakistan Infantryman",

    # ---- troops: deer (Olenia)
    "Молодой олень": "Young Stag",
    "Лесной боец": "Woodland Fighter",
    "Оленийский воин": "Olenian Warrior",
    "Копейщик чащи": "Thicket Spearman",
    "Тяжёлый копейщик Олении": "Heavy Olenian Spearman",
    "Секироносец Олении": "Olenian Axebearer",
    "Рогатый таран": "Antlered Batterer",
    "Ярость гона": "Fury of the Rut",
    "Лесовик": "Woodsman",
    "Оленийский разбойник": "Olenian Brigand",
    "Бывалый разбойник чащи": "Hardened Thicket Brigand",
    "Верховой налётчик Олении": "Olenian Mounted Raider",
    "Оленийский охотник": "Olenian Hunter",
    "Лучник Олении": "Olenian Archer",
    "Меткий лучник Олении": "Olenian Marksman",
    "Сын оленьего дома": "Son of a Deer House",
    "Гвардеец Оленьей Рощи": "Guard of Deer Grove",
    "Старший гвардеец Оленьей Рощи": "Senior Guard of Deer Grove",
    "Дружинник короля Олении": "Retainer of the King of Olenia",
    "Поборник Совета Семи": "Champion of the Council of Seven",
    "Ополченец Олении": "Olenian Militia",
    "Ополченец-лучник Олении": "Olenian Militia Archer",
    "Бывалый ополченец Олении": "Veteran Olenian Militia",
    "Бывалый ополченец-лучник Олении": "Veteran Olenian Militia Archer",

    # ---- branch swap 10.10.2026 (make_troops.ROSTER_OF): new names
    "Гарпунщик прибоя": "Surf Harpooner",
    "Тяжёлый гарпунщик Ариса": "Heavy Aris Harpooner",
    "Ярость прибоя": "Fury of the Surf",
    "Бывалый налётчик Сиквестрии": "Hardened Seaquestria Raider",
    "Лучник горы Арис": "Mount Aris Archer",
    "Меткий лучник Ариса": "Aris Marksman",
    "Дракон с арбалетом": "Dragon Crossbowman",
    "Арбалетчик пепла": "Ash Crossbowman",
    "Бывалый арбалетчик пепла": "Hardened Ash Crossbowman",
    "Крюкастый дракон": "Hooked Dragon",
    "Пикинёр вулкана": "Volcano Pikeman",
    "Клинок Драконьих Земель": "Blade of the Dragon Lands",
    "Авангард Состязания": "Vanguard of the Gauntlet",
    "Молодой страж Скипетра": "Young Warden of the Scepter",
    "Ополченец-арбалетчик Драконьих Земель": "Dragon Lands Militia Crossbowman",
    "Бывалый ополченец-арбалетчик Драконьих Земель": "Veteran Dragon Lands Militia Crossbowman",
    "Пехотинец Драконьих Земель": "Dragon Lands Infantryman",
    "Ярость ледника": "Fury of the Glacier",
    "Бывалый налётчик ледника": "Hardened Glacier Raider",
    "Следопыт тундры": "Tundra Tracker",
    "Отборный воин Олении": "Picked Olenian Warrior",
    "Оленийский разведчик": "Olenian Scout",
    "Метатель дротиков Олении": "Olenian Javelineer",
    "Бывалый метатель дротиков Олении": "Veteran Olenian Javelineer",
    "Верховой метатель Олении": "Olenian Mounted Skirmisher",
    "Знатный воин Олении": "Highborn Olenian Warrior",
    "Лучник Совета Семи": "Archer of the Council of Seven",
    "Налётчик тундры": "Tundra Raider",
    "Рогатый налётчик": "Antlered Raider",
    "Застрельщик Олении": "Olenian Skirmisher",

    # ---- troops (tools/make_troops.py)
    "Эквестрийский новобранец": "Equestrian Recruit",
    "Бывалый ополченец": "Seasoned Militia",
    "Бывалый ополченец-стрелок": "Seasoned Militia Archer",
    "Опытный единорог-стрелок": "Veteran Unicorn Archer",
    "Королевский стражник": "Royal Guard",
    "Ветеран Королевской стражи": "Royal Guard Veteran",
    "Солнечный гвардеец": "Solar Guard",
    "Магическая стража принцессы": "Princess's Arcane Guard",
    "Страж Кантерлотских врат": "Warden of the Canterlot Gates",
    "Страж тронного зала": "Throne Room Warden",
    "Ночной страж Луны": "Luna's Night Guard",
    "Кадет лётной академии": "Flight Academy Cadet",
    "Крылатый охотник": "Winged Hunter",
    "Лесной бродяга": "Forest Wanderer",
    "Вольный стрелок Вечнодикого леса": "Everfree Free Archer",
    "Хозяин Вечнодикого леса": "Master of the Everfree",
    "Горный старатель": "Mountain Prospector",
    "Степной разбойник": "Steppe Raider",
    "Пустынный налётчик": "Desert Raider",
    "Бизоний налётчик": "Buffalo Raider",
    "Конный налётчик": "Mounted Raider",
    "Конный грабитель": "Mounted Robber",
    "Вожак набега": "Raid Leader",
    "Молодой трутень": "Young Drone",
    "Трутень роя": "Swarm Drone",
    "Боец роя": "Swarm Fighter",
    "Роевой всадник": "Swarm Rider",
    "Ополченец улья": "Hive Militia",
    "Опытный ополченец улья": "Veteran Hive Militia",
    "Опытный ополченец-плевун": "Veteran Spitter Militia",
    "Воин улья": "Hive Warrior",
    "Ветеран улья": "Hive Veteran",
    "Страж улья": "Hive Warden",
    "Стрелок улья": "Hive Shooter",
    "Всадник улья": "Hive Rider",
    "Старший всадник улья": "Senior Hive Rider",
    "Авангард королевы": "Queen's Vanguard",
    "Крылатый ловчий королевы": "Queen's Winged Catcher",
    "Меткий плевун королевы": "Queen's True Spitter",
    # single-word and hyphenated names would otherwise be spelled in Latin letter by letter
    "Единорог-стрелок": "Unicorn Archer",
    "Единорог-чародей": "Unicorn Spellcaster",
    "Пегас-разведчик": "Pegasus Scout",
    "Пегас-штурмовик": "Pegasus Stormflyer",
    "Вандерболт": "Wonderbolt",
    "Ас Вандерболтов": "Wonderbolt Ace",
    "Стражник Эквестрии": "Equestrian Guard",
    "Ополченец-стрелок": "Militia Archer",
    "Ополченец Понивилля": "Ponyville Militia",
    "Алебардщик Кантерлота": "Canterlot Halberdier",
    "Арбалетчик Мейнхэттена": "Manehattan Crossbowpony",
    "Сержант-арбалетчик Мейнхэттена": "Manehattan Crossbow Sergeant",
    "Плевун": "Spitter",
    "Ополченец-плевун": "Spitter Militia",
    "Лазутчик-рубака": "Infiltrator Chopper",
    "Оборотень-наездник": "Shapeshifter Rider",
    "Оборотень-лазутчик": "Shapeshifter Infiltrator",
    "Личинка-гонец": "Grub Runner",
    "Мародёр": "Looter",
    "Дезертир": "Deserter",
    "Стервятник": "Vulture",
    "Главарь Стервятников": "Vulture Boss",
    "Бродяга Бесплодных Земель": "Badlands Drifter",
    "Атаман Тимбервульфов": "Timberwolf Chieftain",
    "Король Алмазных Псов": "Diamond Dog King",
    "Вожак Алмазных Псов": "Diamond Dog Leader",
    "Громила Алмазных Псов": "Diamond Dog Bruiser",
    "Пират Короля Шторма": "Storm King Pirate",
    "Абордажник Короля Шторма": "Storm King Boarder",
    "Капитан Короля Шторма": "Storm King Captain",
    "Адмирал Короля Шторма": "Storm King Admiral",
    "Вождь Бизоньих Набегов": "Buffalo Raid Chief",

    # ---- race items (mane, tail, horn): they have no vanilla original
    "Пони: грива": "Pony: mane",
    "Пони: хвост": "Pony: tail",
    "Чейнджлинг: рог и гребень": "Changeling: horn and crest",
    "Чейнджлинг: рог": "Changeling: horn",
    "Чейнджлинг: крылья и хвост": "Changeling: wings and tail",
    "Кризалис: рог и корона": "Chrysalis: horn and crown",
    "Олень: хвост": "Deer: tail",
    "Як: хвост": "Yak: tail",

    # ---- companion nicknames in taverns
    "{FIRSTNAME} — Лётчица над Лавой": "{FIRSTNAME} the Lava Flyer",
    "{FIRSTNAME} — Охотник за Сокровищами": "{FIRSTNAME} the Treasure Hunter",
    "{FIRSTNAME} — Резчик по Рогу": "{FIRSTNAME} the Horn Carver",
    "{FIRSTNAME} — Ветеран Гвардии": "{FIRSTNAME} the Guard Veteran",
    "{FIRSTNAME} — Вулканолог": "{FIRSTNAME} the Volcano Watcher",
    "{FIRSTNAME} — Гонец": "{FIRSTNAME} the Courier",
    "{FIRSTNAME} — Горный Егерь": "{FIRSTNAME} the Mountain Ranger",
    "{FIRSTNAME} — Заклинательница": "{FIRSTNAME} the Spellweaver",
    "{FIRSTNAME} — Знахарка": "{FIRSTNAME} the Herbalist",
    "{FIRSTNAME} — Картограф": "{FIRSTNAME} the Mapmaker",
    "{FIRSTNAME} — Книжница": "{FIRSTNAME} the Bookmare",
    "{FIRSTNAME} — Корабельщица": "{FIRSTNAME} the Shipwright",
    "{FIRSTNAME} — Кузнец Гор": "{FIRSTNAME} the Mountain Smith",
    "{FIRSTNAME} — Кузнец Чешуи": "{FIRSTNAME} the Scale Smith",
    "{FIRSTNAME} — Лазутчик": "{FIRSTNAME} the Infiltrator",
    "{FIRSTNAME} — Ледоруб": "{FIRSTNAME} the Icebreaker",
    "{FIRSTNAME} — Лекарь Приливов": "{FIRSTNAME} the Tide Healer",
    "{FIRSTNAME} — Летописец": "{FIRSTNAME} the Chronicler",
    "{FIRSTNAME} — Ловец Жемчуга": "{FIRSTNAME} the Pearl Diver",
    "{FIRSTNAME} — Ловчая Чувств": "{FIRSTNAME} the Feeling Catcher",
    "{FIRSTNAME} — Наёмный Коготь": "{FIRSTNAME} the Hired Talon",
    "{FIRSTNAME} — Небесная Стражница": "{FIRSTNAME} the Sky Guard",
    "{FIRSTNAME} — Небесный Курьер": "{FIRSTNAME} the Sky Courier",
    "{FIRSTNAME} — Небесный Рыцарь": "{FIRSTNAME} the Sky Knight",
    "{FIRSTNAME} — Огнедышащий Наёмник": "{FIRSTNAME} the Firebreathing Sellsword",
    "{FIRSTNAME} — Певица Прибоя": "{FIRSTNAME} the Surf Singer",
    "{FIRSTNAME} — Певунья": "{FIRSTNAME} the Songstress",
    "{FIRSTNAME} — Перевальный Дозорный": "{FIRSTNAME} the Pass Watcher",
    "{FIRSTNAME} — Пивовар": "{FIRSTNAME} the Brewer",
    "{FIRSTNAME} — Погонщица Стад": "{FIRSTNAME} the Herd Driver",
    "{FIRSTNAME} — Подражатель": "{FIRSTNAME} the Mimic",
    "{FIRSTNAME} — Почтальон": "{FIRSTNAME} the Mail Carrier",
    "{FIRSTNAME} — Поэт Пламени": "{FIRSTNAME} the Flame Poet",
    "{FIRSTNAME} — Пряха Морока": "{FIRSTNAME} the Glamour Weaver",
    "{FIRSTNAME} — Разведчик Роя": "{FIRSTNAME} the Swarm Scout",
    "{FIRSTNAME} — Рыбак": "{FIRSTNAME} the Fisher",
    "{FIRSTNAME} — Садовод": "{FIRSTNAME} the Gardener",
    "{FIRSTNAME} — Сборщица Яблок": "{FIRSTNAME} the Apple Picker",
    "{FIRSTNAME} — Сказительница": "{FIRSTNAME} the Storyteller",
    "{FIRSTNAME} — Скальный Проводник": "{FIRSTNAME} the Cliff Guide",
    "{FIRSTNAME} — Следопыт Облаков": "{FIRSTNAME} the Cloud Tracker",
    "{FIRSTNAME} — Следопыт Фронтира": "{FIRSTNAME} the Frontier Tracker",
    "{FIRSTNAME} — Смотритель Троп": "{FIRSTNAME} the Trail Warden",
    "{FIRSTNAME} — Собиратель Самоцветов": "{FIRSTNAME} the Gem Gatherer",
    "{FIRSTNAME} — Собирательница": "{FIRSTNAME} the Gatherer",
    "{FIRSTNAME} — Столичный Щёголь": "{FIRSTNAME} the City Dandy",
    "{FIRSTNAME} — Страж Логова": "{FIRSTNAME} the Lair Guard",
    "{FIRSTNAME} — Стражница Перевала": "{FIRSTNAME} the Pass Guard",
    "{FIRSTNAME} — Табунщица": "{FIRSTNAME} the Herder",
    "{FIRSTNAME} — Толмач": "{FIRSTNAME} the Interpreter",
    "{FIRSTNAME} — Хранитель Раковин": "{FIRSTNAME} the Shell Keeper",
    "{FIRSTNAME} — Хранитель Сокровищ": "{FIRSTNAME} the Hoard Keeper",
    "{FIRSTNAME} — Хранительница Кладки": "{FIRSTNAME} the Brood Keeper",
    "{FIRSTNAME} — Хранительница Саг": "{FIRSTNAME} the Saga Keeper",
    "{FIRSTNAME} — Часовой Улья": "{FIRSTNAME} the Hive Sentry",
    "{FIRSTNAME} — Шериф": "{FIRSTNAME} the Sheriff",
    "{FIRSTNAME} — Штормовой Лётчик": "{FIRSTNAME} the Storm Flyer",

    # ---- realms
    "Пони Эквестрии: земные пони, пегасы и единороги под рукой принцесс-аликорнов.":
        "The ponies of Equestria: earth ponies, pegasi and unicorns under the alicorn princesses.",
    "Сердце Эквестрии под рукой принцессы Селестии, что поднимает солнце. Кантерлот, старая знать "
    "и Королевская стража — самая древняя и гордая из четырёх Эквестрий.":
        "The heart of Equestria under Princess Celestia, who raises the sun. Canterlot, the old "
        "nobility and the Royal Guard — the oldest and proudest of the four Equestrias.",
    "Западные земли принцессы Луны: города ночных огней, фестралы Ночной стражи и герои древности, "
    "вернувшиеся из Лимба. Здесь ночь — не время страха, а время снов.":
        "Princess Luna's western lands: cities of night lights, the thestrals of the Night Guard "
        "and heroes of old returned from Limbo. Here the night is not a time of fear but of dreams.",
    "Земли принцессы Твайлайт и Элементов Гармонии: Понивилль, Замок Дружбы и шумные города "
    "восточного побережья. Здесь верят, что дружба сильнее любой армии, — но армию держат.":
        "The lands of Princess Twilight and the Elements of Harmony: Ponyville, the Castle of "
        "Friendship and the busy cities of the east coast. Here they believe friendship is "
        "stronger than any army — and keep an army all the same.",
    "Северная империя кристальных пони под рукой принцессы Кейденс, союзница Эквестрии. Пока "
    "Кристальное Сердце на месте, холод и тьма Сомбры сюда не вернутся.":
        "The northern empire of the crystal ponies under Princess Cadance, ally of Equestria. "
        "While the Crystal Heart stands, Sombra's cold and darkness will not return.",
    "Чейнджлинги ульев: оборотни, питающиеся чужой любовью.":
        "The changelings of the hives: shapeshifters who feed on the love of others.",
    "Бесплодные земли на юго-востоке, изрытые ульями оборотней. Питаются чужой любовью и готовят "
    "поход на соседей.":
        "The barren south-east, riddled with the hives of the shapeshifters. They feed on the love "
        "of others and are preparing a march on their neighbours.",
    "Грифоны Грифонстоуна: гордые, прижимистые, но верные своему слову.":
        "The gryphons of Griffonstone: proud and tight-fisted, but true to their word.",
    "Горное королевство грифонов, когда-то растерявшее всё из-за утраченного Идола Бориаса. Теперь "
    "Идол возвращён, и грифоны снова учатся быть не только жадными, но и верными.":
        "The mountain kingdom of the gryphons, which once lost everything with the Idol of Boreas. "
        "The Idol is back now, and the gryphons are learning to be loyal as well as greedy.",
    "Гиппогрифы горы Арис и морские пони Сиквестрии.":
        "The hippogriffs of Mount Aris and the seaponies of Seaquestria.",
    "Гиппогрифы горы Арис и морские пони Сиквестрии. Однажды они спрятались от Короля Шторма под "
    "водой, а теперь снова летают над своим западным побережьем.":
        "The hippogriffs of Mount Aris and the seaponies of Seaquestria. Once they hid from the "
        "Storm King beneath the waves; now they fly over their western shore again.",
    "Яки Якьякистана: громкие, честные и очень любят крушить.":
        "The yaks of Yakyakistan: loud, honest and very fond of smashing things.",
    "Горное царство яков. Здесь ценят прямоту, крепкий мороз и умение сломать то, что сделано "
    "неправильно.":
        "The mountain realm of the yaks. Here they prize plain speech, hard frost and the knack of "
        "smashing whatever was done wrong.",
    "Олени северных лесов: молчаливые следопыты и упрямые лучники.":
        "The deer of the northern woods: silent trackers and stubborn archers.",
    "Северные леса и озёра оленей. Трон занял бастард, законная наследница собирает сторонников, "
    "а рогатые дружины стерегут границы от драконов.":
        "The northern woods and lakes of the deer. A bastard holds the throne, the rightful heir "
        "gathers her supporters, and antlered levies watch the border against the dragons.",
    "Драконы вулканических земель: сила, сокровища и Состязание за Скипетр.":
        "The dragons of the volcanic lands: strength, hoards, and the Gauntlet of Fire for the "
        "Bloodstone Scepter.",
    "Раскалённые юго-восточные земли вулканов и джунглей. Драконы признают только силу, но их лорд "
    "Эмбер учится, что у дружбы тоже бывают когти.":
        "The scorched south-east of volcanoes and jungle. Dragons respect only strength, but their "
        "Dragon Lord Ember is learning that friendship has claws too.",

    # ---- towns and fortresses
    "Столица Солнечной Эквестрии, белокаменный город на склоне горы.":
        "Capital of Solar Equestria, a white-stone city on the mountainside.",
    "Город, который не спит.": "The city that never sleeps.",
    "Старая столица торговли и законов.": "The old capital of trade and law.",
    "Город ночных огней, столица Лунной Эквестрии.":
        "A city of night lights, capital of Lunar Equestria.",
    "Портовый город на восточном побережье.": "A port city on the east coast.",
    "Порт среди хвойных лесов.": "A port among the pine forests.",
    "Тихий городок с Замком Дружбы — столица Эквестрии Дружбы.":
        "A quiet town with the Castle of Friendship — capital of the Equestria of Friendship.",
    "Город пегасов на облаках, где делают погоду.":
        "The pegasus city in the clouds, where the weather is made.",
    "Бьющееся сердце Кристальной Империи, хранящее Кристальное Сердце.":
        "The beating heart of the Crystal Empire, home of the Crystal Heart.",
    "Северная твердыня Кристальной Империи.": "The northern stronghold of the Crystal Empire.",
    "Столица яков под ледником.": "The yak capital beneath the glacier.",
    "Северная гавань яков среди льдов.": "The northern yak harbour amid the ice.",
    "Столица ульев чейнджлингов.": "Capital of the changeling hives.",
    "Белый порт чейнджлингов.": "The white port of the changelings.",
    "Столица гиппогрифов, парящая над морем гора.":
        "Capital of the hippogriffs, a mountain soaring above the sea.",
    "Подводный город морских пони.": "The undersea city of the seaponies.",
    "Столица грифонов, где снова хранится Идол Бориаса.":
        "Capital of the gryphons, home once more to the Idol of Boreas.",
    "Вулканическое логово, где лорд драконов держит Скипетр.":
        "The volcanic lair where the Dragon Lord keeps the Scepter.",
    "Столица Олении: дубовые чертоги над озером.":
        "Capital of Olenia: oaken halls above the lake.",
    "Оленья Роща": "Deer Grove",
    "Деревня «равных», где когда-то все носили одинаковые метки.":
        "The village of the Equals, where everypony once wore the same mark.",

    # ---- heroes of Equestria
    "Старшая сестра, поднимающая солнце. Правит Эквестрией тысячу лет.":
        "The elder sister who raises the sun. She has ruled Equestria for a thousand years.",
    "Младшая сестра, хранительница ночи и снов. Вернулась после тысячи лет изгнания.":
        "The younger sister, keeper of night and dreams. Returned after a thousand years of exile.",
    "Принцесса дружбы, ученица Селестии и сильнейшая волшебница поколения.":
        "The Princess of Friendship, Celestia's student and the strongest mage of her generation.",
    "Принцесса любви, правительница Кристальной Империи.":
        "The Princess of Love, ruler of the Crystal Empire.",
    "Дракончик, выращенный Твайлайт. Её помощник и верный друг.":
        "A young dragon raised by Twilight. Her assistant and faithful friend.",
    "Быстрейшая пегаска Эквестрии, воплощение верности.":
        "The fastest pegasus in Equestria, the Element of Loyalty.",
    "Хозяйка Сладкого Яблока, честнейшая пони Эквестрии.":
        "Mistress of Sweet Apple Acres, the most honest pony in Equestria.",
    "Модельер из Понивилля, воплощение щедрости.":
        "A Ponyville fashion designer, the Element of Generosity.",
    "Смотрительница зверей, воплощение доброты.":
        "A keeper of animals, the Element of Kindness.",
    "Устроительница праздников, воплощение смеха.":
        "A thrower of parties, the Element of Laughter.",
    "Бывший капитан Королевской стражи, брат Твайлайт и супруг Кейденс.":
        "Former captain of the Royal Guard, Twilight's brother and Cadance's husband.",
    "Дочь Кейденс и Шайнинг Армора, аликорн от рождения.":
        "Daughter of Cadance and Shining Armor, an alicorn from birth.",
    "Отец Твайлайт и Шайнинг Армора, кантерлотский астроном.":
        "Father of Twilight and Shining Armor, a Canterlot astronomer.",
    "Мать Твайлайт, писательница приключенческих романов.":
        "Twilight's mother, a writer of adventure novels.",
    "Старший брат Эпплджек, тягловая сила фермы.":
        "Applejack's big brother, the muscle of the farm.",
    "Младшая сестра, основательница Меткоискателей.":
        "The younger sister who founded the Cutie Mark Crusaders.",
    "Основательница Понивилля и старейшина семьи Эппл.":
        "Founder of Ponyville and elder of the Apple family.",
    "Отец Эпплджек. Погиб, когда дети были маленькими.":
        "Applejack's father. He died when the children were small.",
    "Мать Эпплджек, из семьи Пир. Погибла вместе с мужем.":
        "Applejack's mother, of the Pear family. She died alongside her husband.",
    "Отец Пир Баттер, давний соперник семьи Эппл.":
        "Pear Butter's father, an old rival of the Apple family.",
    "Кузен Эпплджек из Эпплузы.": "Applejack's cousin from Appleloosa.",
    "Пекарша, жена Биг Макинтоша.": "A baker, Big McIntosh's wife.",
    "Меткоискательница, для которой Рэйнбоу — старшая сестра.":
        "A Cutie Mark Crusader who looks up to Rainbow Dash as a big sister.",
    "Лучшая подруга Даймонд Тиары.": "Diamond Tiara's best friend.",
    "Дочь Ричей, школьная задира.": "The Riches' daughter, the school bully.",
    "Богатейший торговец Понивилля, владелец «Барнис энд Кобл».":
        "Ponyville's richest merchant, owner of Barnyard Bargains.",
    "Жена Филти Рича, заносчивая и властная.":
        "Filthy Rich's wife, haughty and overbearing.",
    "Отец Рэйнбоу Дэш, её самый громкий болельщик.":
        "Rainbow Dash's father, her loudest supporter.",
    "Младший брат Флаттершай, вечный бездельник.":
        "Fluttershy's little brother, an eternal layabout.",
    "Старшая сестра Пинки, знаток камней.": "Pinkie's elder sister, an expert on rocks.",
    "Самая тихая из сестёр Пай.": "The quietest of the Pie sisters.",
    "Отец сестёр Пай, каменный фермер.": "Father of the Pie sisters, a rock farmer.",
    "Хозяйка каменной фермы, суровая и строгая.": "Mistress of the rock farm, harsh and strict.",
    "Весёлая почтальонша, мечтающая о метке.":
        "A cheerful mail mare still dreaming of her cutie mark.",
    "Великая и могущественная фокусница, подруга Старлайт.":
        "The Great and Powerful stage magician, Starlight's friend.",
    "Бывшая предводительница «равных», ученица Твайлайт.":
        "Former leader of the Equals, now Twilight's student.",
    "Кристаллер Империи, учёный-волшебник и друг детства Старлайт.":
        "Crystaller of the Empire, a scholar-mage and Starlight's childhood friend.",
    "Мать Санбёрста, строгая и очень деловая.":
        "Sunburst's mother, strict and very businesslike.",
    "Командир Вандерболтов, лучшая лётчица Эквестрии.":
        "Captain of the Wonderbolts, the finest flyer in Equestria.",
    "Ведомый Спитфайр.": "Spitfire's wingpony.",
    "Пилот пилотажной группы.": "A flyer of the aerobatic team.",
    "Отчисленная кадетка, дерзкая и опасная.":
        "A washed-out cadet, brash and dangerous.",
    "Капитан дворцовой стражи Кантерлота.": "Captain of the Canterlot palace guard.",
    "Офицер стражи, давняя сослуживица Шайнинг Армора.":
        "A guard officer who served beside Shining Armor for years.",
    "Пегас-стражник из Понивилля.": "A pegasus guard from Ponyville.",
    "Кантерлотский аристократ, законодатель мод высшего света.":
        "A Canterlot aristocrat who sets the fashion of high society.",
    "Модель, спутница Фэнси Пэнтса.": "A model, Fancy Pants' companion.",
    "Дальний родственник принцесс, кантерлотский сноб.":
        "A distant relative of the princesses and a Canterlot snob.",
    "Знаменитый шеф-кондитер из Прансии, мастер эклеров.":
        "A famous pastry chef from Prance, a master of eclairs.",
    "Кантерлотская единорожка, ставшая звездочётом при дворе Луны.":
        "A Canterlot unicorn who became stargazer at Luna's court.",
    "Капитан Ночной стражи, фестралка, что ходит тише тени.":
        "Captain of the Night Guard, a thestral quieter than a shadow.",
    "Хранительница Тантабуса, запертого в лунной башне.":
        "Keeper of the Tantabus, locked in the lunar tower.",
    "Страж снов, охотник на кошмары.": "A guardian of dreams, a hunter of nightmares.",
    "Величайший волшебник древности, вернувшийся из Лимба.":
        "The greatest wizard of old, returned from Limbo.",
    "Отважный пегас-воин древней Клаудсдейлской армии.":
        "A bold pegasus warrior of the ancient Cloudsdale army.",
    "Героиня пустынь, воплощение надежды.": "A heroine of the deserts, the spirit of hope.",
    "Волшебница, подарившая свою красоту ради родного края.":
        "A sorceress who gave away her beauty for her homeland.",
    "Целительница из болотных земель.": "A healer from the marshlands.",
    "Советница двора, мастер тайных переговоров.":
        "A court adviser, a master of secret talks.",
    "Её помощница и советница.": "Her assistant and adviser.",
    "Любопытная ученица Школы Дружбы, в восторге от лестниц.":
        "A curious student of the School of Friendship, delighted by staircases.",
    "Ученица Школы Дружбы, тайком любящая чаепития.":
        "A student of the School of Friendship with a secret love of tea parties.",
    "Силач с лопатой, спасший деревню от вулкана.":
        "A strongpony with a shovel who saved his village from a volcano.",
    "Задира, втайне сочиняющий стихи.": "A bully who secretly writes poetry.",

    # ---- Crystal Empire
    "Бывший король-тиран. Его сторонники ждут возвращения.":
        "The former tyrant king. His followers await his return.",
    "Кристальная целительница, подруга детства Сомбры.":
        "A crystal healer, Sombra's childhood friend.",
    "Бывший Пони Теней, ищущий искупления.":
        "A former Shadow Pony seeking redemption.",
    "Хранительница теневых кристаллов.": "Keeper of the shadow crystals.",
    "Предводительница северных кристальных родов.":
        "Chieftain of the northern crystal houses.",

    # ---- changelings
    "Королева ульев, мастерица подмены.": "Queen of the hives, a master of disguise.",
    "Вождь отколовшихся чейнджлингов, выбравших дружбу.":
        "Leader of the breakaway changelings who chose friendship.",
    "Брат Торакса, начальник дозоров.": "Thorax's brother, commander of the patrols.",
    "Купеческая королева ульев.": "The merchant queen of the hives.",
    "Хивесмаршал, полководец роя.": "Hive marshal, war leader of the swarm.",
    "Командующий войском королевы Ново.": "Commander of Queen Novo's host.",

    # ---- griffons
    "Король Грифонстоуна, потомок легендарного короля Гровера.":
        "King of Griffonstone, descendant of the legendary King Grover.",
    "Резкая грифонша, давняя подруга Рэйнбоу Дэш.":
        "A blunt gryphon, an old friend of Rainbow Dash.",
    "Хранитель легенды об Идоле Бориаса, ворчливый старейшина.":
        "Keeper of the legend of the Idol of Boreas, a grumbling elder.",
    "Казначей короны, самый богатый грифон севера.":
        "Treasurer of the crown, the richest gryphon in the north.",
    "Маршал короля, ветеран горных войн.":
        "The king's marshal, a veteran of the mountain wars.",
    "Жена Генриха, правящая Фронтиром в его отсутствие.":
        "Heinrich's wife, who rules the Frontier in his absence.",
    "Племянница Гюстава, лучшая лучница гнезда.":
        "Gustave's niece, the finest archer of the nest.",
    "Разведчица, знающая каждое ущелье Грифонских гор.":
        "A scout who knows every gorge of the Gryphon Mountains.",
    "Командир горных егерей.": "Commander of the mountain rangers.",
    "Лучший следопыт горных троп.": "The best tracker of the mountain trails.",
    "Хранитель южных троп.": "Keeper of the southern trails.",
    "Старый полководец, хозяин восточных перевалов.":
        "An old war leader, master of the eastern passes.",

    # ---- hippogriffs
    "Правительница гиппогрифов и морских пони, хранительница Жемчужины.":
        "Ruler of the hippogriffs and seaponies, keeper of the Pearl.",
    "Принцесса, мечтающая о жизни над волнами.":
        "A princess who dreams of a life above the waves.",
    "Брат Сильверстрим, живущий меж двух миров.":
        "Silverstream's brother, living between two worlds.",
    "Отец Сильверстрим и Террамара, гиппогриф.":
        "Father of Silverstream and Terramar, a hippogriff.",
    "Мать Сильверстрим, выбравшая жизнь морской пони.":
        "Silverstream's mother, who chose the life of a seapony.",
    "Командир летучей стражи горы Арис.":
        "Commander of the flying guard of Mount Aris.",
    "Командир летучих дозоров.": "Commander of the flying patrols.",
    "Командир воздушной кавалерии.": "Commander of the air cavalry.",

    # ---- deer (Olenia)
    "Йохан Йельцек": "Johan Jelzek", "Аслауг Йельцек": "Aslaug Jelzek",
    "Королева Вельвет": "Queen Velvet", "Хьялмар Вельвет": "Hjalmar Velvet",
    "Бенджен Кудлинен": "Benjen Kudlinen", "Ильта Кудлинен": "Ilta Kudlinen",
    "Бастард, силой взявший оленийский трон.":
        "A bastard who took the throne of Olenia by force.",
    "Сестра короля, его главная опора при дворе.":
        "The king's sister and his chief support at court.",
    "Законная наследница, оспаривающая трон у бастарда.":
        "The rightful heir, pressing her claim against the bastard.",
    "Её дядя и воевода, водит сторонников королевы.":
        "Her uncle and warlord, who leads the queen's supporters.",
    "Старейшина Совета Семи, хранитель лесных законов.":
        "Elder of the Council of Seven, keeper of the forest laws.",
    "Лучшая следопытка оленьих троп.": "The finest tracker of the deer trails.",

    # ---- dragons
    "Лорд драконов, получившая Скипетр в Состязании.":
        "The Dragon Lord, who won the Scepter in the Gauntlet of Fire.",
    "Бывший лорд драконов, отец Эмбер.": "The former Dragon Lord, Ember's father.",
    "Юная якесса, учившаяся в Эквестрии.": "A young yak who studied in Equestria.",
    "Приятель Гарбла, силач.": "Garble's mate, a strongarm.",
    "Ещё один дружок Гарбла, мастер дымовых колец.":
        "Another of Garble's friends, a master of smoke rings.",
    "Хитрый старый дракон, мастер уговоров.":
        "A cunning old dragon, a master of persuasion.",

    # ---- yaks
    "Принц яков, громкий и честный.": "A yak prince, loud and honest.",
    "Принц отколовшейся ветви яков.": "Prince of a breakaway yak line.",
    "Старейшина, помнящий все обиды яков наперечёт.":
        "An elder who remembers every yak grievance by name.",
    "Предводительница горных стад.": "Chieftain of the mountain herds.",
    "Степной вождь, союзник Брэдфорда.": "A steppe chieftain, Bradford's ally.",
}


# Canon names are distributed between the dictionaries: a single word is looked up in compound names (WORDS),
# several words - only as a whole string (PHRASES).
for _ru, _en in CANON.items():
    if " " in _ru:
        PHRASES.setdefault(_ru, _en)
    else:
        WORDS.setdefault(_ru, _en)
