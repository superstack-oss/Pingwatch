from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# Native query families. 100+ game ids map onto these protocols.
# id|label|protocol|default_port
_CATALOG = """
7d2d|7 Days to Die|a2s|26900
arkse|ARK: Survival Evolved|a2s|27015
asa|ARK: Survival Ascended|a2s|27015
arma2|Arma 2|gamespy4|2302
arma2oa|Arma 2: Operation Arrowhead|gamespy4|2302
arma3|Arma 3|a2s|2303
atlas|ATLAS|a2s|5750
avorion|Avorion|a2s|27000
barotrauma|Barotrauma|a2s|27015
battlegrounds|PUBG|a2s|27015
blackmesa|Black Mesa|a2s|27015
brainbread2|BrainBread 2|a2s|27015
cod|Call of Duty|quake3|28960
cod2|Call of Duty 2|quake3|28960
cod4|Call of Duty 4: Modern Warfare|quake3|28960
coduo|Call of Duty: United Offensive|quake3|28960
codwaw|Call of Duty: World at War|quake3|28960
conanexiles|Conan Exiles|a2s|7778
corekeeper|Core Keeper|a2s|27015
cs16|Counter-Strike 1.6|a2s|27015
cs2|Counter-Strike 2|a2s|27015
cscz|Counter-Strike: Condition Zero|a2s|27015
csgo|Counter-Strike: Global Offensive|a2s|27015
css|Counter-Strike: Source|a2s|27015
dayofinfamy|Day of Infamy|a2s|27015
dayz|DayZ|a2s|27016
dayzmod|DayZ Mod|gamespy4|2302
dod|Day of Defeat|a2s|27015
dods|Day of Defeat: Source|a2s|27015
doom3|Doom 3|quake3|27666
dota2|Dota 2|a2s|27015
dst|Don't Starve Together|a2s|10999
dystopia|Dystopia|a2s|27015
eco|Eco|a2s|3000
empyrion|Empyrion - Galactic Survival|a2s|30000
enemyterritory|Wolfenstein: Enemy Territory|quake3|27960
enshrouded|Enshrouded|a2s|15636
etqw|Enemy Territory: Quake Wars|quake3|27733
factorio|Factorio|factorio|34197
ffow|Fortress Forever|a2s|27015
fivem|FiveM|fivem|30120
fof|Fistful of Frags|a2s|27015
garrysmod|Garry's Mod|a2s|27015
gta5|GTA V (FiveM)|fivem|30120
gtav|Grand Theft Auto V|fivem|30120
hidden|The Hidden: Source|a2s|27015
hl2dm|Half-Life 2: Deathmatch|a2s|27015
hldm|Half-Life Deathmatch|a2s|27015
hldms|Half-Life Deathmatch: Source|a2s|27015
hurtworld|Hurtworld|a2s|12871
insurgency|Insurgency|a2s|27015
insurgencysandstorm|Insurgency: Sandstorm|a2s|27131
jabronibrawl|Jabroni Brawl: Episode 3|a2s|27015
jc2mp|Just Cause 2: Multiplayer|gamespy4|7777
jc3mp|Just Cause 3: Multiplayer|gamespy4|4200
jediknight2|Jedi Knight II|quake3|28070
jediknight3|Jedi Knight: Jedi Academy|quake3|29070
killingfloor|Killing Floor|gamespy4|7708
killingfloor2|Killing Floor 2|a2s|27015
l4d|Left 4 Dead|a2s|27015
l4d2|Left 4 Dead 2|a2s|27015
minecraft|Minecraft|minecraft|25565
minecraftbe|Minecraft Bedrock|bedrock|19132
mohaa|Medal of Honor: Allied Assault|quake3|12203
mordhau|Mordhau|a2s|7777
mta|Multi Theft Auto|gamespy4|22003
mtasa|MTA: San Andreas|gamespy4|22003
mumble|Mumble|mumble|64738
nexuiz|Nexuiz|quake3|26000
nmrih|No More Room in Hell|a2s|27015
ns2|Natural Selection 2|a2s|27015
nucleardawn|Nuclear Dawn|a2s|27015
openarena|OpenArena|quake3|27960
palworld|Palworld|a2s|8211
pixark|PixARK|a2s|27015
projectzomboid|Project Zomboid|a2s|16261
pvkii|Pirates, Vikings, and Knights II|a2s|27015
quake|Quake|quake3|26000
quake2|Quake II|quake3|27910
quake3|Quake III Arena|quake3|27960
quake4|Quake 4|quake3|28004
redm|RedM|fivem|30120
reflex|Reflex Arena|a2s|27015
ricochet|Ricochet|a2s|27015
rtcw|Return to Castle Wolfenstein|quake3|27960
rust|Rust|a2s|28015
samp|SA-MP|samp|7777
satisfactory|Satisfactory|a2s|15777
scum|SCUM|a2s|27015
sof2|Soldier of Fortune 2|quake3|20100
sonsoftheforest|Sons of the Forest|a2s|8766
soulmask|Soulmask|a2s|27015
spaceengineers|Space Engineers|a2s|27016
squad|Squad|a2s|27165
starbound|Starbound|a2s|21025
synergy|Synergy|a2s|27015
tf2|Team Fortress 2|a2s|27015
tfc|Team Fortress Classic|a2s|27015
theforest|The Forest|a2s|27015
theship|The Ship|a2s|27015
tremulous|Tremulous|quake3|30720
unturned|Unturned|a2s|27015
unvanquished|Unvanquished|quake3|27960
urbanterror|Urban Terror|quake3|27960
ut2004|Unreal Tournament 2004|gamespy4|7777
valheim|Valheim|a2s|2456
vrising|V Rising|a2s|27015
warsow|Warsow|quake3|44400
wolfensteinet|Wolfenstein: Enemy Territory|quake3|27960
xonotic|Xonotic|quake3|26000
zps|Zombie Panic! Source|a2s|27015
""".strip()

ALIASES = {
    "7daystodie": "7d2d",
    "ark": "arkse",
    "arksurvivalevolved": "arkse",
    "bedrock": "minecraftbe",
    "counterstrike": "cs2",
    "counterstrike2": "cs2",
    "counterstrike16": "cs16",
    "cssource": "css",
    "dontstarve": "dst",
    "dontstarvetogether": "dst",
    "et": "enemyterritory",
    "fxserver": "fivem",
    "gmod": "garrysmod",
    "hl1": "hldm",
    "left4dead": "l4d",
    "left4dead2": "l4d2",
    "mc": "minecraft",
    "pocketmine": "minecraftbe",
    "source": "css",
    "teamfortress2": "tf2",
    "unrealtournament2004": "ut2004",
}


def _parse_catalog() -> Dict[str, Tuple[str, str, int]]:
    games: Dict[str, Tuple[str, str, int]] = {}
    for line in _CATALOG.splitlines():
        line = line.strip()
        if not line:
            continue
        game_id, label, protocol, port = line.split("|")
        games[game_id] = (label, protocol, int(port))
    return games


GAMES = _parse_catalog()


def normalize_game_id(value: str) -> Optional[str]:
    key = "".join(ch for ch in (value or "").lower() if ch.isalnum())
    if key in GAMES:
        return key
    return ALIASES.get(key)


def game_info(game_id: str) -> Optional[Tuple[str, str, int]]:
    resolved = normalize_game_id(game_id)
    if not resolved:
        return None
    return GAMES[resolved]


def game_choices() -> List[Dict[str, object]]:
    rows = [
        {"id": game_id, "label": info[0], "protocol": info[1], "port": info[2]}
        for game_id, info in GAMES.items()
    ]
    rows.sort(key=lambda item: str(item["label"]).lower())
    return rows
