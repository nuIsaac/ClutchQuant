import re

import httpx
from bs4 import BeautifulSoup

from app.database import SessionLocal
from app.models import (
    Match,
    MatchMap,
    Player,
    PlayerMapStat,
)


TEST_MATCH_ID = 734305

TEST_MATCH_URL = (
    "https://www.vlr.gg/734305/"
    "100-thieves-vs-leviat-n-vct-2026-americas-stage-2-ubsf"
)


def fetch_page(url):
    response = httpx.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20.0,
        follow_redirects=True,
    )

    response.raise_for_status()

    return BeautifulSoup(
        response.text,
        "html.parser",
    )


def extract_vlr_id(href):
    if not href:
        return None

    match = re.search(r"/(\d+)/", href)

    if match:
        return int(match.group(1))

    return None


def parse_triplet(text, converter=float):
    values = text.replace("%", "").split()

    if len(values) != 3:
        return [None, None, None]

    try:
        return [
            converter(values[0]),
            converter(values[1]),
            converter(values[2]),
        ]

    except ValueError:
        return [None, None, None]


def parse_duration(text):
    if not text:
        return None

    parts = text.strip().split(":")

    try:
        values = [
            int(part)
            for part in parts
        ]
    except ValueError:
        return None

    if len(values) == 2:
        minutes, seconds = values

        return (
            minutes * 60
            + seconds
        )

    if len(values) == 3:
        hours, minutes, seconds = values

        return (
            hours * 3600
            + minutes * 60
            + seconds
        )

    return None


def parse_player_row(row, team_number):
    player_link = row.select_one(
        ".ovw-cell.mod-player a"
    )

    player_name = row.select_one(
        ".ovw-player-name"
    )

    cells = row.find_all(
        "div",
        recursive=False,
    )

    rating = parse_triplet(
        cells[1].get_text(" ", strip=True),
        float,
    )

    acs = parse_triplet(
        cells[2].get_text(" ", strip=True),
        int,
    )

    kda_groups = (
        cells[3]
        .get_text(" ", strip=True)
        .split("/")
    )

    kills = parse_triplet(
        kda_groups[0],
        int,
    )

    deaths = parse_triplet(
        kda_groups[1],
        int,
    )

    assists = parse_triplet(
        kda_groups[2],
        int,
    )

    kill_diff = parse_triplet(
        cells[4].get_text(" ", strip=True),
        int,
    )

    kast = parse_triplet(
        cells[5].get_text(" ", strip=True),
        float,
    )

    adr = parse_triplet(
        cells[6].get_text(" ", strip=True),
        float,
    )

    hs_pct = parse_triplet(
        cells[7].get_text(" ", strip=True),
        float,
    )

    first_kills = parse_triplet(
        cells[8].get_text(" ", strip=True),
        int,
    )

    first_deaths = parse_triplet(
        cells[9].get_text(" ", strip=True),
        int,
    )

    first_kill_diff = parse_triplet(
        cells[10].get_text(" ", strip=True),
        int,
    )

    agents = []

    for image in row.select(
        ".ovw-agents img"
    ):
        agent = (
            image.get("title")
            or image.get("alt")
        )

        if agent:
            agents.append(agent)

    return {
        "vlr_player_id": extract_vlr_id(
            player_link.get("href")
            if player_link
            else None
        ),
        "player_name": (
            player_name.get_text(strip=True)
            if player_name
            else None
        ),
        "team_number": team_number,
        "agents": agents,
        "rating": rating,
        "acs": acs,
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "kill_diff": kill_diff,
        "kast": kast,
        "adr": adr,
        "hs_pct": hs_pct,
        "first_kills": first_kills,
        "first_deaths": first_deaths,
        "first_kill_diff": first_kill_diff,
    }


def parse_maps(soup):
    map_nav = {}

    for nav in soup.select(
        "a.vm-stats-gamesnav-item[data-game-id]"
    ):
        game_id = nav.get("data-game-id")

        if game_id == "all":
            continue

        if "mod-disabled" in nav.get(
            "class",
            [],
        ):
            continue

        text = nav.get_text(
            " ",
            strip=True,
        )

        parts = text.split(
            " ",
            1,
        )

        if len(parts) != 2:
            continue

        map_nav[game_id] = {
            "map_number": int(parts[0]),
            "map_name": parts[1],
        }

    maps = []

    for section in soup.select(
        "div.vm-stats-game[data-game-id]"
    ):
        game_id = section.get(
            "data-game-id"
        )

        if game_id == "all":
            continue

        if game_id not in map_nav:
            continue

        header = section.select_one(
            ".vm-stats-game-header"
        )

        teams = header.select(".team")

        if len(teams) < 2:
            continue

        team1_score_element = (
            teams[0].select_one(".score")
        )

        team2_score_element = (
            teams[1].select_one(".score")
        )

        duration_element = header.select_one(
            ".map-duration"
        )

        players = []

        stat_tables = section.select(
            ".ovw-table"
        )

        for table_index, table in enumerate(
            stat_tables[:2],
            start=1,
        ):
            player_rows = [
                row
                for row in table.select(
                    ".ovw-row"
                )
                if row.select_one(
                    ".ovw-cell.mod-player"
                )
            ]

            for row in player_rows:
                players.append(
                    parse_player_row(
                        row,
                        table_index,
                    )
                )

        maps.append(
            {
                "vlr_game_id": int(game_id),
                "map_number": map_nav[
                    game_id
                ]["map_number"],
                "map_name": map_nav[
                    game_id
                ]["map_name"],
                "team1_score": int(
                    team1_score_element
                    .get_text(strip=True)
                ),
                "team2_score": int(
                    team2_score_element
                    .get_text(strip=True)
                ),
                "duration_seconds": (
                    parse_duration(
                        duration_element
                        .get_text(strip=True)
                    )
                    if duration_element
                    else None
                ),
                "players": players,
            }
        )

    return maps


def get_or_create_player(db, player_data):
    player = (
        db.query(Player)
        .filter(
            Player.vlr_id
            == player_data["vlr_player_id"]
        )
        .first()
    )

    if player is None:
        player = Player(
            vlr_id=player_data[
                "vlr_player_id"
            ],
            handle=player_data[
                "player_name"
            ],
        )

        db.add(player)
        db.flush()

    else:
        player.handle = player_data[
            "player_name"
        ]

    return player


def save_maps(db, match, maps):
    for map_data in maps:
        match_map = (
            db.query(MatchMap)
            .filter(
                MatchMap.vlr_game_id
                == map_data["vlr_game_id"]
            )
            .first()
        )

        if match_map is None:
            match_map = MatchMap(
                vlr_game_id=map_data[
                    "vlr_game_id"
                ],
                match_id=match.id,
                map_number=map_data[
                    "map_number"
                ],
                map_name=map_data[
                    "map_name"
                ],
            )

            db.add(match_map)
            db.flush()

        match_map.match_id = match.id
        match_map.map_number = map_data[
            "map_number"
        ]
        match_map.map_name = map_data[
            "map_name"
        ]
        match_map.team1_score = map_data[
            "team1_score"
        ]
        match_map.team2_score = map_data[
            "team2_score"
        ]
        match_map.duration_seconds = map_data[
            "duration_seconds"
        ]

        for player_data in map_data[
            "players"
        ]:
            player = get_or_create_player(
                db,
                player_data,
            )

            if player_data["team_number"] == 1:
                team_id = match.team1_id
            else:
                team_id = match.team2_id

            stat = (
                db.query(PlayerMapStat)
                .filter(
                    PlayerMapStat.match_map_id
                    == match_map.id,
                    PlayerMapStat.player_id
                    == player.id,
                )
                .first()
            )

            if stat is None:
                stat = PlayerMapStat(
                    match_map_id=match_map.id,
                    player_id=player.id,
                    team_id=team_id,
                )

                db.add(stat)

            stat.team_id = team_id

            stat.agents = (
                ",".join(
                    player_data["agents"]
                )
                if player_data["agents"]
                else None
            )

            stat.rating_all = player_data[
                "rating"
            ][0]
            stat.rating_attack = player_data[
                "rating"
            ][1]
            stat.rating_defense = player_data[
                "rating"
            ][2]

            stat.acs_all = player_data["acs"][0]
            stat.acs_attack = player_data["acs"][1]
            stat.acs_defense = player_data["acs"][2]

            stat.kills_all = player_data[
                "kills"
            ][0]
            stat.kills_attack = player_data[
                "kills"
            ][1]
            stat.kills_defense = player_data[
                "kills"
            ][2]

            stat.deaths_all = player_data[
                "deaths"
            ][0]
            stat.deaths_attack = player_data[
                "deaths"
            ][1]
            stat.deaths_defense = player_data[
                "deaths"
            ][2]

            stat.assists_all = player_data[
                "assists"
            ][0]
            stat.assists_attack = player_data[
                "assists"
            ][1]
            stat.assists_defense = player_data[
                "assists"
            ][2]

            stat.kill_diff_all = player_data[
                "kill_diff"
            ][0]
            stat.kill_diff_attack = player_data[
                "kill_diff"
            ][1]
            stat.kill_diff_defense = player_data[
                "kill_diff"
            ][2]

            stat.kast_all = player_data[
                "kast"
            ][0]
            stat.kast_attack = player_data[
                "kast"
            ][1]
            stat.kast_defense = player_data[
                "kast"
            ][2]

            stat.adr_all = player_data[
                "adr"
            ][0]
            stat.adr_attack = player_data[
                "adr"
            ][1]
            stat.adr_defense = player_data[
                "adr"
            ][2]

            stat.hs_pct_all = player_data[
                "hs_pct"
            ][0]
            stat.hs_pct_attack = player_data[
                "hs_pct"
            ][1]
            stat.hs_pct_defense = player_data[
                "hs_pct"
            ][2]

            stat.first_kills_all = player_data[
                "first_kills"
            ][0]
            stat.first_kills_attack = player_data[
                "first_kills"
            ][1]
            stat.first_kills_defense = player_data[
                "first_kills"
            ][2]

            stat.first_deaths_all = player_data[
                "first_deaths"
            ][0]
            stat.first_deaths_attack = player_data[
                "first_deaths"
            ][1]
            stat.first_deaths_defense = player_data[
                "first_deaths"
            ][2]

            stat.first_kill_diff_all = player_data[
                "first_kill_diff"
            ][0]
            stat.first_kill_diff_attack = player_data[
                "first_kill_diff"
            ][1]
            stat.first_kill_diff_defense = player_data[
                "first_kill_diff"
            ][2]


def main():
    soup = fetch_page(TEST_MATCH_URL)

    maps = parse_maps(soup)

    db = SessionLocal()

    try:
        match = (
            db.query(Match)
            .filter(
                Match.vlr_id == TEST_MATCH_ID
            )
            .first()
        )

        if match is None:
            raise RuntimeError(
                "Test match is not in the database."
            )

        save_maps(
            db,
            match,
            maps,
        )

        db.commit()

        print(
            f"Saved {len(maps)} maps."
        )

        print(
            "Player stat rows:",
            sum(
                len(map_data["players"])
                for map_data in maps
            ),
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()