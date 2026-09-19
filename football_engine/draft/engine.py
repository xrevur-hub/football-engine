"""
Draft Engine — Snake, Auction, and Salary-Cap drafts.

Pure data-driven: works with PlayerSeason records from the normalized dataset.
Enforces uniqueness (a PlayerSeason can be drafted at most once per draft).
Supports multiple formats:
- Snake (alternating pick order each round)
- Auction (budget-based bidding)
- Salary Cap (fixed total salary budget per team)

All PlayerSeason objects come from the data layer; drafts are pure orchestration.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Sequence

from football_engine.core.player_season import PlayerSeason
from football_engine.data_layer import create_possession_source
from football_engine.data_layer.loader import load_all


class DraftFormat(Enum):
    SNAKE = "snake"
    AUCTION = "auction"
    SALARY_CAP = "salary_cap"


@dataclass(frozen=True)
class DraftPick:
    """A single pick in a draft."""
    pick_number: int
    round_number: int
    team_id: str
    player_id: str
    # For auction/salary-cap: price paid
    price: Optional[int] = None


@dataclass
class DraftTeam:
    """A team in the draft (user or AI)."""
    team_id: str
    name: str
    picks: list[DraftPick] = field(default_factory=list)
    # For auction/salary-cap
    budget: int = 0
    spent: int = 0

    def remaining_budget(self) -> int:
        return self.budget - self.spent

    def roster_size(self) -> int:
        return len(self.picks)

    def has_player(self, player_id: str) -> bool:
        return any(p.player_id == player_id for p in self.picks)

    def can_afford(self, price: int) -> bool:
        return self.spent + price <= self.budget


@dataclass
class DraftState:
    """Mutable state of an in-progress draft."""
    format: DraftFormat
    teams: list[DraftTeam]
    available_players: set[str]  # PlayerSeason IDs
    current_round: int = 1
    current_pick_index: int = 0  # 0-based index in snake order
    is_complete: bool = False
    pick_history: list[DraftPick] = field(default_factory=list)

    def roster_limit(self) -> int:
        return 11

    def all_rosters_full(self) -> bool:
        return all(t.roster_size() >= self.roster_limit() for t in self.teams)


class DraftEngine:
    """Orchestrates a draft of PlayerSeasons into teams."""

    def __init__(
        self,
        format: DraftFormat,
        teams: Sequence[DraftTeam],
        available_players: set[str],
        seed: int = 42,
    ) -> None:
        self.format = format
        self.seed = seed
        self._rng = random.Random(seed)

        self.state = DraftState(
            format=format,
            teams=list(teams),
            available_players=set(available_players),
        )

        # Validate
        total_needed = len(teams) * 11
        if len(available_players) < total_needed:
            raise ValueError(
                f"Draft pool has {len(available_players)} players, need {total_needed}"
            )

    def _snake_pick_order(self, round_num: int) -> list[DraftTeam]:
        """Return teams in pick order for this round (snake)."""
        order = self.state.teams[:]
        if round_num % 2 == 0:
            order.reverse()
        return order

    def _available_for_team(self, team: DraftTeam) -> set[str]:
        """Players available for this team (not already picked, affordable)."""
        available = self.state.available_players - {p.player_id for p in team.picks}
        if self.format == DraftFormat.AUCTION or self.format == DraftFormat.SALARY_CAP:
            available = {pid for pid in available if team.can_afford(self._get_player_price(pid))}
        return available

    def _get_player_price(self, player_id: str) -> int:
        """Base price for a player (can be overridden)."""
        # Simple heuristic: based on attack_ability
        # In a real implementation, this would be a configurable table.
        return 5  # placeholder

    def pick(self, team_id: str, player_id: str, price: Optional[int] = None) -> DraftPick:
        """Record a pick for the given team."""
        if self.state.is_complete:
            raise RuntimeError("Draft is complete")

        team = next(t for t in self.state.teams if t.team_id == team_id)
        available = self._available_for_team(team)
        if player_id not in available:
            raise ValueError(f"Player {player_id} not available for {team_id}")

        pick_number = len(self.state.pick_history) + 1
        round_num = (pick_number - 1) // len(self.state.teams) + 1

        pick = DraftPick(
            pick_number=pick_number,
            round_number=round_num,
            team_id=team_id,
            player_id=player_id,
            price=price,
        )
        team.picks.append(pick)
        if price:
            team.spent += price
        self.state.available_players.remove(player_id)
        self.state.pick_history.append(pick)
        self.state.current_pick_index += 1

        # Advance round
        if self.state.current_pick_index >= len(self.state.teams):
            self.state.current_round += 1
            self.state.current_pick_index = 0

        # Check completion
        if self.state.all_rosters_full():
            self.state.is_complete = True

        return pick

    def auto_pick(self, team_id: str) -> Optional[DraftPick]:
        """Auto-pick the best available player for a team (AI)."""
        if self.state.is_complete:
            return None
        team = next(t for t in self.state.teams if t.team_id == team_id)
        available = self._available_for_team(team)
        if not available:
            return None
        # Simple heuristic: pick highest attack_ability among available
        # In reality, this would use the data layer to evaluate
        chosen = self._rng.choice(list(available))
        return self.pick(team_id, chosen)

    def run_snake_draft(self, auto_teams: Optional[set[str]] = None) -> list[DraftPick]:
        """Run a complete snake draft to completion."""
        if self.format != DraftFormat.SNAKE:
            raise ValueError("Not a snake draft")
        auto_teams = auto_teams or set()

        while not self.state.is_complete:
            round_num = self.state.current_round
            pick_order = self._snake_pick_order(round_num)
            for team in pick_order:
                if self.state.is_complete:
                    break
                if team.team_id in auto_teams:
                    self.auto_pick(team.team_id)
                else:
                    # In a real draft, this would block for user input
                    # For simulation, auto-pick
                    self.auto_pick(team.team_id)
        return self.state.pick_history

    def run_auction_draft(self, auto_teams: Optional[set[str]] = None) -> list[DraftPick]:
        """Run an auction draft (simplified: each team nominates, bidding = price)."""
        if self.format != DraftFormat.AUCTION:
            raise ValueError("Not an auction draft")
        auto_teams = auto_teams or set()
        # Simple sequential auction: each team nominates a player in turn
        # and "wins" at the base price. Real auctions would have bidding.
        while not self.state.is_complete:
            for team in self.state.teams:
                if self.state.is_complete:
                    break
                if team.team_id in auto_teams or team.remaining_budget() <= 0:
                    continue
                available = {p for p in self.state.available_players
                             if self._get_player_price(p) <= team.remaining_budget()}
                if not available:
                    continue
                # Auto-pick with price
                chosen = self._rng.choice(list(available))
                price = self._get_player_price(chosen)
                self.pick(team.team_id, chosen, price=price)
        return self.state.pick_history

    def run_salary_cap_draft(self, auto_teams: Optional[set[str]] = None) -> list[DraftPick]:
        """Run a salary-cap draft (simplified: sequential picks with salary)."""
        if self.format != DraftFormat.SALARY_CAP:
            raise ValueError("Not a salary-cap draft")
        auto_teams = auto_teams or set()
        # Sequential salary-cap: each team picks one player per turn,
        # paying the salary. Stops when all rosters full or no budget.
        while not self.state.is_complete:
            for team in self.state.teams:
                if self.state.is_complete:
                    break
                if team.team_id in auto_teams or team.remaining_budget() <= 0:
                    continue
                available = {p for p in self.state.available_players
                             if self._get_player_price(p) <= team.remaining_budget()}
                if not available:
                    continue
                chosen = self._rng.choice(list(available))
                price = self._get_player_price(chosen)
                self.pick(team.team_id, chosen, price=price)
        return self.state.pick_history

    def get_rosters(self) -> dict[str, list[str]]:
        """Return final rosters: team_id -> list of player_ids."""
        return {t.team_id: [p.player_id for p in t.picks] for t in self.state.teams}

    def get_team_rosters_with_players(
        self,
        players_by_id: dict[str, PlayerSeason]
    ) -> dict[str, list[PlayerSeason]]:
        """Return full PlayerSeason objects for each team's roster."""
        return {
            team_id: [players_by_id[pid] for pid in pids if pid in players_by_id]
            for team_id, pids in self.get_rosters().items()
        }


def create_draft_from_data(
    data_dir: Path,
    format: DraftFormat,
    team_names: list[str],
    budget: int = 1000,
    seed: int = 42,
) -> DraftEngine:
    """Create a draft engine loaded with the full dataset."""
    repos = load_all(Path(data_dir))
    available = {p.id for p in repos.players.all(include_placeholder=False)}
    teams = [
        DraftTeam(
            team_id=f"team_{i}",
            name=name,
            budget=budget if format in (DraftFormat.AUCTION, DraftFormat.SALARY_CAP) else 0,
        )
        for i, name in enumerate(team_names)
    ]
    return DraftEngine(format=format, teams=teams, available_players=available, seed=seed)


def run_draft(
    data_dir: Path,
    format: DraftFormat | str,
    num_teams: int = 2,
    seed: int = 42,
) -> dict:
    """Run a complete draft and return results with full PlayerSeason data."""
    if isinstance(format, str):
        format = DraftFormat(format)
    repos = load_all(Path(data_dir))
    available = {p.id for p in repos.players.all(include_placeholder=False)}
    team_names = [f"Team {i+1}" for i in range(num_teams)]
    teams = [
        DraftTeam(
            team_id=f"team_{i}",
            name=name,
            budget=1000 if format in (DraftFormat.AUCTION, DraftFormat.SALARY_CAP) else 0,
        )
        for i, name in enumerate(team_names)
    ]
    engine = DraftEngine(format=format, teams=teams, available_players=available, seed=seed)

    if format == DraftFormat.SNAKE:
        engine.run_snake_draft()
    elif format == DraftFormat.AUCTION:
        engine.run_auction_draft()
    else:
        engine.run_salary_cap_draft()

    rosters = engine.get_team_rosters_with_players(
        {p.id: p for p in repos.players.all(include_placeholder=False)}
    )
    return {
        "format": format.value,
        "teams": [
            {
                "team_id": team_id,
                "name": f"Team {i+1}",
                "roster": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "season": p.season,
                        "role": p.role.value,
                        "attack_ability": p.attack_ability,
                        "creation_ability": p.creation_ability,
                        "defense_ability": p.defense_ability,
                    }
                    for p in roster
                ]
            }
            for i, (team_id, roster) in enumerate(rosters.items())
        ],
        "pick_history": [
            {
                "pick_number": p.pick_number,
                "round": p.round_number,
                "team_id": p.team_id,
                "player_id": p.player_id,
                "price": p.price,
            }
            for p in engine.state.pick_history
        ],
    }


if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=["snake", "auction", "salary_cap"], default="snake")
    parser.add_argument("--teams", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2] / "data" / "normalized"
    res = run_draft(root, DraftFormat(args.format), args.teams, args.seed)
    print(json.dumps(res, indent=2))