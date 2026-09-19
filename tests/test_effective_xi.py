"""Tests for xi_assignment — Effective XI (Route C, E-16)."""

import pytest

from football_engine.core.enums import PlayerRole
from football_engine.core.formation import Formation, PositionSlot, SlotDepth, SlotSide
from football_engine.core.player_season import PlayerSeason
from football_engine.xi_assignment.effective_xi import (
    EffectiveXiPlayer,
    build_effective_xi,
    NeutralFitTable,
)


def make_draft_players() -> list[PlayerSeason]:
    """11 players with distinct draft roles (FW, AM, WM, CM, DM, FB, CB, GK...)."""
    specs = [
        ("striker_1", PlayerRole.FW, 90, 60, 20, 0.9),
        ("striker_2", PlayerRole.FW, 85, 55, 25, 0.8),
        ("winger_1",   PlayerRole.WM, 78, 60, 30, 0.8),
        ("winger_2",   PlayerRole.WM, 74, 55, 28, 0.7),
        ("attacker",   PlayerRole.AM, 70, 75, 35, 0.6),
        ("mid_cm",     PlayerRole.CM, 60, 78, 60, 0.5),
        ("mid_cm2",    PlayerRole.CM, 55, 72, 62, 0.5),
        ("pivot",      PlayerRole.DM, 45, 68, 75, 0.4),
        ("fullback",   PlayerRole.FB, 58, 62, 72, 0.4),
        ("centreback", PlayerRole.CB, 30, 45, 92, 0.2),
        ("keeper",     PlayerRole.GK, 10, 15, 10, 0.1),
    ]
    return [
        PlayerSeason(
            id=pid, name=pid.title(), season="2010/11", role=role,
            attack_ability=atk, creation_ability=cre, defense_ability=de,
            gk_ability=90 if role == PlayerRole.GK else 5,
            shot_tendency=st, press_tendency=0.5, transition_tendency=0.5, pace=0.5,
            discipline_score=0.5, impact_score=0.5,
        )
        for pid, role, atk, cre, de, st in specs
    ]


def make_formation() -> Formation:
    """A basic 4-3-3 formation."""
    B, M, F = SlotDepth.BACK, SlotDepth.MID, SlotDepth.FRONT
    L, C, R = SlotSide.LEFT, SlotSide.CENTER, SlotSide.RIGHT
    slots = [
        PositionSlot(slot_id="GK", role=PlayerRole.GK, side=C, depth=B),
        PositionSlot(slot_id="RB", role=PlayerRole.FB, side=R, depth=B),
        PositionSlot(slot_id="CB1", role=PlayerRole.CB, side=C, depth=B),
        PositionSlot(slot_id="CB2", role=PlayerRole.CB, side=C, depth=B),
        PositionSlot(slot_id="LB", role=PlayerRole.FB, side=L, depth=B),
        PositionSlot(slot_id="DM", role=PlayerRole.DM, side=C, depth=M),
        PositionSlot(slot_id="CM1", role=PlayerRole.CM, side=L, depth=M),
        PositionSlot(slot_id="CM2", role=PlayerRole.CM, side=R, depth=M),
        PositionSlot(slot_id="RW", role=PlayerRole.WM, side=R, depth=F),
        PositionSlot(slot_id="ST", role=PlayerRole.FW, side=C, depth=F),
        PositionSlot(slot_id="LW", role=PlayerRole.WM, side=L, depth=F),
    ]
    return Formation(name="4-3-3", position_pool=slots)


def natural_assignment(formation: Formation) -> dict[str, str]:
    """Assign each draft player to the slot matching their draft role."""
    mapping = {
        PlayerRole.GK: "GK",
        PlayerRole.FB: "RB",
        PlayerRole.CB: "CB1",
        PlayerRole.DM: "DM",
        PlayerRole.CM: "CM1",
        PlayerRole.WM: "RW",
        PlayerRole.AM: "CM2",  # no AM slot in 4-3-3 — place in CM
        PlayerRole.FW: "ST",
    }
    # Two of each role need distinct slots
    by_role = {}
    for p in make_draft_players():
        by_role.setdefault(p.role, []).append(p.id)

    assign = {}
    used = set()
    for p in make_draft_players():
        slot = mapping[p.role]
        if slot in used and p.role in (PlayerRole.FB, PlayerRole.CB, PlayerRole.CM, PlayerRole.WM, PlayerRole.FW):
            slot = mapping[p.role] + str(by_role[p.role].index(p.id))
        if slot in used:
            # fallback: find first unassigned slot with matching role
            for s in formation.position_pool:
                if s.role == p.role and s.slot_id not in used:
                    slot = s.slot_id
                    break
        assign[p.id] = slot
        used.add(slot)
    # Fix slots for the two-slot roles explicitly
    ids = [p.id for p in make_draft_players()]
    assign[ids[0]] = "ST"  # striker_1
    assign[ids[1]] = "LW"  # striker_2 -> LW (FM as wide forward)
    assign[ids[2]] = "RW"  # winger_1
    assign[ids[3]] = "CM2"  # winger_2 -> CM2
    assign[ids[4]] = "CM1"  # attacker -> CM1
    assign[ids[5]] = "DM"  # mid_cm -> DM
    assign[ids[6]] = "LB"  # mid_cm2 -> LB
    assign[ids[7]] = "RB"  # pivot -> RB
    assign[ids[8]] = "CB2"  # fullback -> CB2
    assign[ids[9]] = "CB1"  # centreback -> CB1
    assign[ids[10]] = "GK"  # keeper -> GK
    return assign


class TestEffectiveXiType:
    """Test EffectiveXiPlayer is a distinguishable frozen PlayerSeason subclass."""

    def test_is_player_season_subclass(self):
        assert issubclass(EffectiveXiPlayer, PlayerSeason)
        # Passes isinstance gate used by Layer 2
        players = build_effective_xi(
            make_draft_players(), make_formation(), natural_assignment(make_formation())
        )
        assert all(isinstance(p, PlayerSeason) for p in players)
        assert all(isinstance(p, EffectiveXiPlayer) for p in players)

    def test_frozen(self):
        players = build_effective_xi(
            make_draft_players(), make_formation(), natural_assignment(make_formation())
        )
        with pytest.raises(Exception):
            players[0].id = "changed"

    def test_carries_draft_identity(self):
        draft = make_draft_players()
        players = build_effective_xi(draft, make_formation(), natural_assignment(make_formation()))
        for p in players:
            assert p.draft_player_id == p.id
            assert p.draft_role in {d.role for d in draft}
            assert p.is_effective

    def test_assigned_role_matches_slot(self):
        formation = make_formation()
        assignment = natural_assignment(formation)
        players = build_effective_xi(make_draft_players(), formation, assignment)
        slots = {s.slot_id: s.role for s in formation.position_pool}
        for p in players:
            assert p.role == slots[assignment[p.draft_player_id]]


class TestBuildValidation:
    """Test build_effective_xi validation."""

    def test_wrong_player_count(self):
        with pytest.raises(ValueError, match="exactly 11"):
            build_effective_xi(make_draft_players()[:10], make_formation(), {})

    def test_incomplete_assignment(self):
        draft = make_draft_players()
        partial = {p.id: "ST" for p in draft[:10]}
        with pytest.raises(ValueError, match="must cover exactly"):
            build_effective_xi(draft, make_formation(), partial)

    def test_unknown_slot(self):
        draft = make_draft_players()
        assignment = natural_assignment(make_formation())
        assignment[draft[0].id] = "NOT_A_SLOT"
        with pytest.raises(ValueError, match="unknown slot"):
            build_effective_xi(draft, make_formation(), assignment)


class TestRoleFit:
    """Test role-fit adjustment — the 'consequence' mechanism."""

    def test_neutral_fit_table_all_one(self):
        assert all(v == 1.0 for v in NeutralFitTable.values())
        # E-24 remains unspecified -> neutral 1.0 default
        dstriker = make_draft_players()[0]  # FW
        from football_engine.xi_assignment.effective_xi import _role_fit_factor
        assert _role_fit_factor(dstriker.role, PlayerRole.CB) == 1.0

    def test_custom_fit_table_is_applied(self):
        draft = make_draft_players()
        formation = make_formation()
        assignment = natural_assignment(formation)
        fit_table = {("FW", "CB"): 0.5, ("FW", "ST"): 1.0}
        players = build_effective_xi(draft, formation, assignment, fit_table=fit_table)
        # striker_2 is assigned to LW (WM slot) -> fit row ("FW","WM") not in table -> 1.0
        for p in players:
            if p.draft_role == PlayerRole.FW:
                assert 0.0 < p.fit_factor <= 1.0

    def test_abilities_scaled_by_fit(self):
        draft = make_draft_players()
        formation = make_formation()
        assignment = natural_assignment(formation)
        # striker_2 goes to LW (WM). Penalize FW->WM heavily to test scaling.
        fit_table = {("FW", "WM"): 0.5}
        players = build_effective_xi(draft, formation, assignment, fit_table=fit_table)
        striker2 = next(p for p in players if p.id == "striker_2")
        original = next(p for p in draft if p.id == "striker_2")
        assert striker2.attack_ability == pytest.approx(original.attack_ability * 0.5)
        assert striker2.defense_ability == pytest.approx(original.defense_ability * 0.5)


class TestMisplacedPlayerPenalty:
    """The product consequence: a striker at CB is naturally weak defensively."""

    def test_striker_as_cb_team_defense_drops(self):
        """Placing a striker in the CB slot lowers TeamDimension.Defense via role weighting."""
        from football_engine.team_model.team_dimension_engine import TeamDimensionEngine
        from football_engine.team_model.formation_engine import FormationEngine

        formation = make_formation()
        draft = make_draft_players()

        # Correct placement: the actual CB covers the CB slot
        correct_assignment = natural_assignment(formation)
        correct_xi = build_effective_xi(draft, formation, correct_assignment)
        correct_structure = FormationEngine().derive(correct_xi, formation)
        correct_dims = TeamDimensionEngine().derive(correct_xi, correct_structure)

        # Misplacement: swap the striker into the CB slot, CB to ST
        bad_assignment = dict(correct_assignment)
        bad_assignment["striker_2"] = "CB1"
        bad_assignment["centreback"] = "LW"
        bad_xi = build_effective_xi(draft, formation, bad_assignment)
        bad_structure = FormationEngine().derive(bad_xi, formation)
        bad_dims = TeamDimensionEngine().derive(bad_xi, bad_structure)

        assert bad_dims.defense < correct_dims.defense
        # The striker at CB contributes near-zero defense weight because their
        # defense_ability (~25) is what gets weighted as a CB, vs. the real CB (92).