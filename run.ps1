# Quick mod test: XML check -> build -> launch the game straight into the last save.
#   .\run.ps1              build, check and launch
#   .\run.ps1 -NoLaunch    only build and check
#   .\run.ps1 -NewGame     launch into the main menu instead of the save
#   .\run.ps1 -QuickStart  a new sandbox without a single click (the mod presses "Equestria: quick test" itself)
#   .\run.ps1 -Helmets     helmet fitting room: 16 into the inventory, one worn, the window open
#   .\run.ps1 -Helmets -HelmetKind open   the same, but wear an open helmet (closed by default)
#   .\run.ps1 -Helmets -Battle            wear a helmet and go straight into battle with bandits
#   .\run.ps1 -Helmets -BigBattle         a 500 vs 500 battle of dragons in full armour (also: -Battle2)
#   .\run.ps1 -Battle      magic test: in battle hold Q — the spell wheel, release — cast
#   .\run.ps1 -Races       race review: a new sandbox, 3 companions of each race in the party
#   .\run.ps1 -Races -PerRace 5           the same, but five per race
#   .\run.ps1 -Prisoners   a new sandbox, 5 soldiers of each race as prisoners (test of butchering
#                          into meat, equestria.butcher_prisoners)
#   .\run.ps1 -Prisoners -PerPrisoner 10  the same, but ten prisoners per race
#   .\run.ps1 -DismemberTest              a new sandbox, straight into battle: 100 vs 100 Golden Horseshoe
#                          Veterans (ponies) with two-handed swords — dismemberment test
#   .\run.ps1 -DismemberTest -DismemberCount 100   the same, but a hundred per side
#   .\run.ps1 -DismemberTest -DismemberRace yak    the same, but with yaks instead of ponies (see the list
#                          of races in DismemberRace below — arms/legs cut into _l/_r are required)
#   .\run.ps1 -DefaultStart                a new game with the REAL character creation wizard
#                          (not skipped — race choice at the "Appearance" stage, as for the player);
#                          after the wizard our own popup: beggar start / mercenary / vassal / ruler
#                          of the chosen kingdom (EquestriaDefaultStart)
#   .\run.ps1 -Days 200    a new sandbox, time runs at x32 right away up to day 200, a summary
#                          in eq_exceptions.log every 10 days, at the end the save eq_longrun
#   .\run.ps1 -Hideout     a new sandbox: the party is placed right next to the nearest bandit hideout
#                          (it is marked as discovered) and walks to it
#   .\run.ps1 -MixedBirths a new sandbox: pairs of heroes of different races marry, each has a child at once,
#                          then the wives get pregnant and time runs 45 days at x32 — normal births.
#                          Result in eq_exceptions.log, lines "mixed births"
#   .\run.ps1 -MixedBirths -MixedPairs 30   the same, but 30 pairs (20 by default)
#   .\run.ps1 -Flight      a new sandbox, the flight scroll worn in the horse slot, straight into a 100 vs 100
#                          battle of Wonderbolts on scrolls (all cavalry flies — EquestriaFlightArmy)
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

# Official modules + our mod. The list must match the save's modules,
# otherwise the game warns about a mismatch.
$Modules = @("Native", "SandBoxCore", "BirthAndDeath", "CustomBattle", "Sandbox", "StoryMode", "EquestriaMod")

# 1. XML check: every Item.xxx must exist in the game or in the mod.
#    Commented-out items do not count: the game silently skips nonexistent ids.
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

# 2. Close the game BEFORE building: a running one holds EquestriaMod.dll, the copy into the game
#    folder silently fails (only warning MSB3021 in the build), and the test runs on old code.
if (-not $NoLaunch) {
    Get-Process Bannerlord -ErrorAction SilentlyContinue | Stop-Process -Force
}

# 3. Build (also copies the mod into the game folder) — only if the XML has no errors
Write-Host "== Сборка" -ForegroundColor Cyan
dotnet build "$ModRoot\src\EquestriaMod.csproj" -c Release -nologo -v q
if ($LASTEXITCODE -ne 0) { throw "Сборка не удалась" }

if ($NoLaunch) { return }

# 4. Launch bypassing the launcher
Write-Host "== Запуск игры" -ForegroundColor Cyan

# The game sets safely_exited = 0 at startup and puts back 1 on a normal exit. We kill its
# process, so the flag stays zero, and on the next launch the window
# "Game shut down unexpectedly. Enable safe mode?" pops up — you have to press "No". We set the flag ourselves.
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
# Verbose mod log (EquestriaCrashLog.Verbose): regular lines and catching all exceptions.
# A player launching from the launcher has no such switch — eq_exceptions.log has only stages, warnings and errors.
$gameArgs += " /eqverbose"
# /eqhelmets is read by the mod itself (EquestriaHelmetTest): once the map is up, it hands out helmets,
# puts one on and opens the inventory — no in-game console needed.
if ($Helmets) { $gameArgs += " /eqhelmets:$HelmetKind" }
# /eqbattle is read by EquestriaShowcase: once the map is up, it sets three bandit parties on you.
# Together with -Helmets the helmet is put on first, and the inventory is not opened — otherwise the battle won't start.
if ($Battle) { $gameArgs += " /eqbattle" }
# /eqbigbattle is read by EquestriaHelmetTest: 500 vs 500 Sturgian veterans (in the mod this culture is
# dragons), both sides in full armour. The inventory is not opened in this case.
if ($BigBattle) { $gameArgs += " /eqbigbattle" }
# /eqraces is read by EquestriaRaceParty: once the map is up, it recruits that many companions of
# each race into the party, each in random armour, and opens the party screen. It needs a new
# campaign — so the switch goes together with the quick start.
if ($Races) { $gameArgs += " /eqraces:$PerRace" }
# /eqprisoners is read by EquestriaPrisonerButchery: once the map is up, it puts that many soldiers
# of each race into your party's prisoners — ready material for equestria.butcher_prisoners without
# going to battle for live prisoners.
if ($Prisoners) { $gameArgs += " /eqprisoners:$PerPrisoner" }
# /eqdismember is read by EquestriaShowcase: once the map is up, it recruits into your party and creates
# an enemy party — that many soldiers of the chosen race (DismemberRace, see
# EquestriaDebugCommands.DismemberTestTroopByRace) per side, gives everyone a two-handed sword and starts
# the battle right away (EquestriaDebugCommands.DismembermentTestBattle) — a test of EquestriaDismemberment.cs.
if ($DismemberTest) { $gameArgs += " /eqdismember:${DismemberCount}:${DismemberRace}" }
# /eqdefaultstart is read by the mod itself (EquestriaQuickStart + EquestriaDefaultStart): once the
# main menu is up, it starts a new campaign WITHOUT skipping the character creation wizard — unlike
# /eqautostart below, which skips the wizard entirely.
if ($DefaultStart) { $gameArgs += " /eqdefaultstart" }
# /eqflight is read by EquestriaFlightTest: once the map is up, it gives and equips the flight scroll in
# the horse slot and starts a 100 vs 100 battle of Wonderbolts by itself (all campaign cavalry flies on
# scrolls — EquestriaFlightArmy). /eqbattle is not needed here: the test starts the battle itself.
if ($Flight) { $gameArgs += " /eqflight" }
# /eqmixedbirths is read by EquestriaMixedBirthTest: weddings of pairs of heroes of different races (one
# pair per race combination), each has a child at once, then the wives get pregnant; /eqlongrun:45
# (EquestriaLongRun) runs time at x32 so children are also born the normal way. At the end the run
# saves the game as eq_longrun. In eq_exceptions.log — lines "mixed births".
# /eqhideout is read by EquestriaHideoutTest: the nearest bandit hideout is made discovered,
# the party is placed 15 m from it and walks there (a review of hideout models on the map).
if ($Hideout) { $gameArgs += " /eqhideout" }
# /eqlongrun is read by EquestriaLongRun: time at x32 up to the given day, a summary to the log every 10
# days, at the end the save eq_longrun. You may open your own screens (inventory, encyclopedia, save).
if ($Days -gt 0) { $gameArgs += " /eqlongrun:$Days" }
if ($MixedBirths) { $gameArgs += " /eqmixedbirths:$MixedPairs /eqlongrun:45" }
# /eqautostart is read by the mod itself (EquestriaQuickStart): once the main menu is up, it starts
# the quick test. Continuing a save is not needed then — a new campaign begins.
if ($QuickStart -or $Races -or $Prisoners -or $DismemberTest -or $Flight -or $MixedBirths -or $Hideout -or $Days -gt 0) { $gameArgs += " /eqautostart" }
elseif (-not $NewGame -and -not $DefaultStart) { $gameArgs += " /continuegame" }
# Extra switches for self-checks, e.g. /eqset:2 (showing an armour set)
if ($ExtraArgs) { $gameArgs += " " + $ExtraArgs }
Start-Process -FilePath "$Game\bin\Win64_Shipping_Client\Bannerlord.exe" -ArgumentList $gameArgs -WorkingDirectory "$Game\bin\Win64_Shipping_Client"
