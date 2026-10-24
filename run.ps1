# Быстрый тест мода: проверка XML -> сборка -> запуск игры сразу в последнее сохранение.
#   .\run.ps1              собрать, проверить и запустить
#   .\run.ps1 -NoLaunch    только собрать и проверить
#   .\run.ps1 -NewGame     запустить в главное меню, а не в сохранение
#   .\run.ps1 -QuickStart  новая песочница без единого клика (мод сам жмёт "Эквестрия: быстрый тест")
#   .\run.ps1 -Helmets     примерочная шлемов: 16 штук в инвентарь, один надет, окно открыто
#   .\run.ps1 -Helmets -HelmetKind open   то же, но надеть открытый шлем (по умолчанию закрытый)
#   .\run.ps1 -Helmets -Battle            надеть шлем и сразу в бой с разбойниками
#   .\run.ps1 -Helmets -BigBattle         бой 500 на 500 драконов в полном доспехе (то же: -Battle2)
#   .\run.ps1 -Battle      проверка магии: в бою удерживать Q — колесо заклинаний, отпустить — каст
#   .\run.ps1 -Races       смотр рас: новая песочница, в отряде по 3 спутника каждой расы
#   .\run.ps1 -Races -PerRace 5           то же, но по пять на расу
#   .\run.ps1 -Prisoners   новая песочница, в плену по 5 бойцов каждой расы (проверка переработки
#                          в мясо, equestria.butcher_prisoners)
#   .\run.ps1 -Prisoners -PerPrisoner 10  то же, но по десять пленных на расу
#   .\run.ps1 -DismemberTest              новая песочница, сразу бой: 100 на 100 Ветеранов Золотой
#                          Подковы (пони) с двуручными мечами — проверка отрубания конечностей
#   .\run.ps1 -DismemberTest -DismemberCount 100   то же, но по сто на сторону
#   .\run.ps1 -DismemberTest -DismemberRace yak    то же, но расой яков вместо пони (см. список
#                          рас в DismemberRace ниже — нужны разрезанные на _l/_r руки/ноги)
#   .\run.ps1 -DefaultStart                новая игра с НАСТОЯЩИМ мастером создания персонажа
#                          (не пропускается — на этапе «Внешность» выбор расы, как у игрока);
#                          после мастера свой попап: нищий старт / наёмник / вассал / правитель
#                          выбранной державы (EquestriaDefaultStart)
#   .\run.ps1 -Days 200    новая песочница, время сразу крутится на x32 до 200-го дня, сводка
#                          в eq_exceptions.log каждые 10 дней, в конце сохранение eq_longrun
#   .\run.ps1 -Hideout     новая песочница: отряд сразу ставится у ближайшего логова разбойников
#                          (оно помечено обнаруженным) и идёт к нему
#   .\run.ps1 -MixedBirths новая песочница: пары героев разных рас женятся, сразу рожают по ребёнку,
#                          потом жёны беременеют и время крутится 45 дней на x32 — обычные роды.
#                          Итог в eq_exceptions.log, строки «смешанные роды: …»
#   .\run.ps1 -MixedBirths -MixedPairs 30   то же, но 30 пар (по умолчанию 20)
#   .\run.ps1 -Flight      новая песочница, свиток полёта надет в слот коня, сразу бой 100 на 100
#                          Wonderbolt'ов на свитках (вся конница летает — EquestriaFlightArmy)
param([switch]$NoLaunch, [switch]$NewGame, [switch]$QuickStart, [switch]$DefaultStart, [switch]$Helmets, [switch]$Battle,
      [Alias("Battle2")][switch]$BigBattle, [switch]$Races, [ValidateRange(1, 20)][int]$PerRace = 3,
      [switch]$Prisoners, [ValidateRange(1, 50)][int]$PerPrisoner = 5,
      [switch]$DismemberTest, [ValidateRange(1, 200)][int]$DismemberCount = 100,
      [ValidateSet("pony", "changeling", "dragon", "griffon", "hippogriff", "yak", "deer")]
      [string]$DismemberRace = "pony", [switch]$Flight,
      [switch]$Hideout, [ValidateRange(0, 5000)][int]$Days = 0, [switch]$MixedBirths, [ValidateRange(1, 60)][int]$MixedPairs = 20,
      [ValidateSet("closed", "open")][string]$HelmetKind = "closed", [string]$ExtraArgs = "")

$ErrorActionPreference = "Stop"
$Game = "D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"
$ModRoot = $PSScriptRoot

# Официальные модули + наш мод. Список должен совпадать с модулями сохранения,
# иначе игра предупредит о несовпадении.
$Modules = @("Native", "SandBoxCore", "BirthAndDeath", "CustomBattle", "Sandbox", "StoryMode", "EquestriaMod")

# 1. Проверка XML: каждый Item.xxx должен существовать в игре или в моде.
#    Закомментированные предметы не считаются: игра молча пропускает несуществующие id.
Write-Host "== Проверка XML" -ForegroundColor Cyan
function Read-ActiveXml($path) {
    $text = [IO.File]::ReadAllText($path) -replace '(?s)<!--.*?-->', ''
    try { [void][xml]$text } catch { throw "Ошибка в XML ${path}: $($_.Exception.Message)" }
    return $text
}

$known = New-Object 'System.Collections.Generic.HashSet[string]'
$itemFiles = @(Get-ChildItem "$Game\Modules\*\ModuleData\items\*.xml" -ErrorAction SilentlyContinue) +
             @(Get-ChildItem "$ModRoot\Module\ModuleData" -Recurse -Filter *.xml)
foreach ($f in $itemFiles) {
    $t = [IO.File]::ReadAllText($f.FullName) -replace '(?s)<!--.*?-->', ''
    foreach ($m in [regex]::Matches($t, '<(?:Item|CraftedItem)\s[^>]*?\bid="([^"]+)"')) { [void]$known.Add($m.Groups[1].Value) }
}

$errors = 0
foreach ($f in Get-ChildItem "$ModRoot\Module" -Recurse -Filter *.xml) {
    $t = Read-ActiveXml $f.FullName
    foreach ($m in [regex]::Matches($t, 'id="Item\.([^"]+)"')) {
        if (-not $known.Contains($m.Groups[1].Value)) {
            Write-Host "  Нет такого предмета: $($m.Groups[1].Value)  ($($f.Name))" -ForegroundColor Red
            $errors++
        }
    }
}
if ($errors -gt 0) { throw "Найдено ошибок: $errors" }
Write-Host "  OK" -ForegroundColor Green

# 2. Игру закрываем ДО сборки: запущенная держит EquestriaMod.dll, копия в папку игры молча не
#    проходит (в сборке только предупреждение MSB3021), и тест идёт на старом коде.
if (-not $NoLaunch) {
    Get-Process Bannerlord -ErrorAction SilentlyContinue | Stop-Process -Force
}

# 3. Сборка (заодно копирует мод в папку игры) — только если XML без ошибок
Write-Host "== Сборка" -ForegroundColor Cyan
dotnet build "$ModRoot\src\EquestriaMod.csproj" -c Release -nologo -v q
if ($LASTEXITCODE -ne 0) { throw "Сборка не удалась" }

if ($NoLaunch) { return }

# 4. Запуск в обход лаунчера
Write-Host "== Запуск игры" -ForegroundColor Cyan

# Игра ставит safely_exited = 0 при старте и возвращает 1 при нормальном выходе. Мы её убиваем
# процессом, поэтому флаг остаётся нулевым, и при следующем запуске вылезает окно
# "Game shut down unexpectedly. Enable safe mode?" — приходится жать "Нет". Ставим флаг сами.
$engineConfig = "$env:USERPROFILE\Documents\Mount and Blade II Bannerlord\Configs\engine_config.txt"
if (Test-Path $engineConfig) {
    $text = [IO.File]::ReadAllText($engineConfig)
    $fixed = $text -replace 'safely_exited\s*=\s*0', 'safely_exited = 1'
    if ($fixed -ne $text) {
        [IO.File]::WriteAllText($engineConfig, $fixed)
        Write-Host "  снят вопрос про безопасный режим" -ForegroundColor DarkGray
    }
}
$gameArgs = "/singleplayer _MODULES_*" + ($Modules -join "*") + "*_"
# Подробный журнал мода (EquestriaCrashLog.Verbose): обычные строки и перехват всех исключений.
# У игрока из лаунчера этого ключа нет — в eq_exceptions.log только этапы, предупреждения и ошибки.
$gameArgs += " /eqverbose"
# /eqhelmets читает сам мод (EquestriaHelmetTest): дождавшись карты, он выдаёт шлемы, надевает
# один и открывает инвентарь — консоль в игре не нужна.
if ($Helmets) { $gameArgs += " /eqhelmets:$HelmetKind" }
# /eqbattle читает EquestriaShowcase: дождавшись карты, натравливает три отряда разбойников.
# Вместе с -Helmets шлем сначала надевается, а инвентарь не открывается — иначе бой не начнётся.
if ($Battle) { $gameArgs += " /eqbattle" }
# /eqbigbattle читает EquestriaHelmetTest: 500 на 500 стургийских ветеранов (у мода эта культура —
# драконы), обе стороны в полном доспехе. Инвентарь при этом не открывается.
if ($BigBattle) { $gameArgs += " /eqbigbattle" }
# /eqraces читает EquestriaRaceParty: дождавшись карты, набирает в отряд по столько спутников
# каждой расы, каждого в случайной броне, и открывает экран отряда. Кампания нужна новая —
# поэтому ключ идёт вместе с быстрым стартом.
if ($Races) { $gameArgs += " /eqraces:$PerRace" }
# /eqprisoners читает EquestriaPrisonerButchery: дождавшись карты, сажает в плен своего отряда
# по столько бойцов каждой расы — готовый материал для equestria.butcher_prisoners без похода
# в бой за живыми пленными.
if ($Prisoners) { $gameArgs += " /eqprisoners:$PerPrisoner" }
# /eqdismember читает EquestriaShowcase: дождавшись карты, набирает в свой отряд и создаёт
# вражеский отряд — по столько бойцов выбранной расы (DismemberRace, см.
# EquestriaDebugCommands.DismemberTestTroopByRace) на сторону, всем раздаёт двуручный меч и сразу
# начинает бой (EquestriaDebugCommands.DismembermentTestBattle) — проверка EquestriaDismemberment.cs.
if ($DismemberTest) { $gameArgs += " /eqdismember:${DismemberCount}:${DismemberRace}" }
# /eqdefaultstart читает сам мод (EquestriaQuickStart + EquestriaDefaultStart): дождавшись
# главного меню, запускает новую кампанию БЕЗ пропуска мастера создания персонажа — в отличие
# от /eqautostart ниже, который мастер целиком пропускает.
if ($DefaultStart) { $gameArgs += " /eqdefaultstart" }
# /eqflight читает EquestriaFlightTest: дождавшись карты, выдаёт и надевает свиток полёта в слот
# коня и сам начинает бой 100 на 100 Wonderbolt'ов (вся конница кампании летает на свитках —
# EquestriaFlightArmy). /eqbattle тут уже не нужен: бой запускает сам тест.
if ($Flight) { $gameArgs += " /eqflight" }
# /eqmixedbirths читает EquestriaMixedBirthTest: свадьбы пар героев разных рас (по паре на
# сочетание рас), каждая сразу рожает ребёнка, затем жёны беременеют; /eqlongrun:45
# (EquestriaLongRun) крутит время на x32, чтобы дети родились и обычным путём. В конце прогон
# сохраняет игру как eq_longrun. В eq_exceptions.log — строки «смешанные роды: …».
# /eqhideout читает EquestriaHideoutTest: ближайшее логово разбойников делается обнаруженным,
# отряд ставится в 15 м от него и идёт туда (смотр моделей логов на карте).
if ($Hideout) { $gameArgs += " /eqhideout" }
# /eqlongrun читает EquestriaLongRun: время на x32 до указанного дня, сводка в журнал каждые 10 дней,
# в конце сохранение eq_longrun. Свои экраны (инвентарь, энциклопедия, сохранение) открывать можно.
if ($Days -gt 0) { $gameArgs += " /eqlongrun:$Days" }
if ($MixedBirths) { $gameArgs += " /eqmixedbirths:$MixedPairs /eqlongrun:45" }
# /eqautostart читает сам мод (EquestriaQuickStart): дождавшись главного меню, он запускает
# быстрый тест. Продолжение сохранения при этом не нужно — начинается новая кампания.
if ($QuickStart -or $Races -or $Prisoners -or $DismemberTest -or $Flight -or $MixedBirths -or $Hideout -or $Days -gt 0) { $gameArgs += " /eqautostart" }
elseif (-not $NewGame -and -not $DefaultStart) { $gameArgs += " /continuegame" }
# Дополнительные ключи для самопроверки, например /eqset:2 (показ комплекта брони)
if ($ExtraArgs) { $gameArgs += " " + $ExtraArgs }
Start-Process -FilePath "$Game\bin\Win64_Shipping_Client\Bannerlord.exe" -ArgumentList $gameArgs -WorkingDirectory "$Game\bin\Win64_Shipping_Client"
