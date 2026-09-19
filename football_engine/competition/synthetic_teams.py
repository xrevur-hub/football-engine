"""
Synthetic team generator — data-driven scaffolding for exercising the UCL engine.

Generates additional, clearly-labeled SYNTHETIC TeamSeasons + PlayerSeasons so
the 36-team league phase is runnable end to end. These are NOT researched
historical estimates: they are neutral-rated template clubs intended only to
exercise the competition engine. Status=IMPORTED with source="synthetic_template".
Real historical teams can be swapped in later without engine changes.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

# Clubs (short labels) synthesized into team seasons
SYNTHETIC_CLUBS = [
    "Porto", "Benfica", "Sporting", "Ajax", "PSV", "Galatasaray", "Fenerbahce",
    "Olympiacos", "Panathinaikos", "Celtic", "Rangers", "Anderlecht", "Club Brugge",
    "Dinamo Zagreb", "Red Star", "Partizan", "Shakhtar", "Dynamo Kyiv", "Basaksehir",
    "Copenhagen", "Midtjylland", "Salzburg", "Bodoe", "Ferencvaros", "Slavia Prague",
    "Sparta Prague", "Legia", "Malmo", "Young Boys", "Basel", "Steaua", "Rapid",
    "Besiktas", "FC Copenhagen",
]

# Role templates with ballpark neutral abilities (50-65) — clearly synthetic.
ROLE_TEMPLATES = [
    ("GK", 8, 12, 10, 78),
    ("FB", 50, 48, 52, 0),
    ("CB", 25, 30, 68, 0),
    ("CB", 28, 32, 65, 0),
    ("FB", 48, 45, 55, 0),
    ("DM", 35, 52, 58, 0),
    ("CM", 45, 58, 48, 0),
    ("CM", 48, 60, 45, 0),
    ("WM", 60, 52, 30, 0),
    ("FW", 62, 50, 20, 0),
    ("WM", 58, 50, 28, 0),
]


def _team_season_block(club: str) -> dict:
    """Build a (players_payload, team_payload, possessions) block for one synthetic club."""
    base = club.lower().replace(" ", "_").replace("é", "e")
    season = "2015/16"

    players = []
    possession = {}
    roster = []
    for idx, (role, atk, cre, de, gk) in enumerate(ROLE_TEMPLATES):
        pid = f"{base}_{idx}_2015_16"
        roster.append(pid)
        players.append({
            "id": pid,
            "name": f"{club} Player {idx + 1}",
            "season": season,
            "role": role,
            "attack_ability": float(atk),
            "creation_ability": float(cre),
            "defense_ability": float(de),
            "gk_ability": float(gk),
            "shot_tendency": 0.5,
            "press_tendency": 0.5,
            "transition_tendency": 0.5,
            "pace": 0.5,
            "discipline_score": 0.5,
            "impact_score": 0.5,
            "metadata": {
                "status": "IMPORTED",
                "source": "synthetic_template",
                "retrieved_at": "2026-09-19T00:00:00Z",
                "confidence": 0.10,
                "notes": f"Synthetic template player for {club}; not a researched historical estimate.",
            },
        })
        possession[pid] = 0.5

    team_id = f"{base}_2015_16"
    team = {
        "id": team_id,
        "club": club,
        "season": season,
        "roster": roster,
        "default_formation": "4-3-3",
        "metadata": {
            "status": "IMPORTED",
            "source": "synthetic_template",
            "retrieved_at": "2026-09-19T00:00:00Z",
            "confidence": 0.10,
            "notes": f"Synthetic {club} 2015/16 (neutral-rated) for UCL engine exercise.",
        },
    }
    return {"players": players, "team": team, "possession": possession, "team_id": team_id}


def extend_dataset(data_dir: Path) -> dict:
    """
    Append synthetic teams to the existing normalized dataset files.

    Returns summary counts. Idempotent: skips club ids already present.
    """
    players_path = data_dir / "players" / "player_seasons.json"
    teams_path = data_dir / "teams" / "team_seasons.json"
    possession_path = data_dir / "possession" / "possession_tendencies.json"

    # Load existing
    players_data = json.loads(players_path.read_text(encoding="utf-8"))
    teams_data = json.loads(teams_path.read_text(encoding="utf-8"))
    poss_data = json.loads(possession_path.read_text(encoding="utf-8"))

    existing_team_ids = {t["id"] for t in teams_data["teams"]}
    existing_player_ids = {p["id"] for p in players_data["players"]}

    added_players = 0
    added_teams = 0
    added_possession = 0

    for club in SYNTHETIC_CLUBS:
        block = _team_season_block(club)
        if block["team_id"] in existing_team_ids:
            continue

        for player in block["players"]:
            if player["id"] not in existing_player_ids:
                players_data["players"].append(player)
                existing_player_ids.add(player["id"])
                added_players += 1

        teams_data["teams"].append(block["team"])
        added_teams += 1

        for pid, val in block["possession"].items():
            if pid not in poss_data["possession_tendencies"]:
                poss_data["possession_tendencies"][pid] = val
                added_possession += 1

    players_path.write_text(json.dumps(players_data, indent=2), encoding="utf-8")
    teams_path.write_text(json.dumps(teams_data, indent=2), encoding="utf-8")
    possession_path.write_text(json.dumps(poss_data, indent=2), encoding="utf-8")

    return {
        "added_teams": added_teams,
        "added_players": added_players,
        "added_possession": added_possession,
        "total_teams": len(teams_data["teams"]),
        "total_players": len(players_data["players"]),
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2] / "data" / "normalized"
    result = extend_dataset(root)
    print(json.dumps(result, indent=2))