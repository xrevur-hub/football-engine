"""Layer 2 contract and orchestration tests.

FormationEngine now implements the approved six rules after E-12 migration.
D1 dimensions are implemented; identity retains an explicit missing-possession
source boundary. Existing historical-prior wiring remains unchanged.
The separate tests/test_formation_engine_v1.py exercises the approved math.
"""

from __future__ import annotations

import pytest

from football_engine.core.enums import HistoricalTier, PlayerRole
from football_engine.core.team_dimensions import StructuralFeatures, TeamDimensions
from football_engine.core.team_identity import TeamIdentity
from football_engine.team_model import (
    FormationEngine,
    FormationEngineError,
    TeamDimensionEngine,
    TeamDimensionEngineError,
    TeamIdentityEngine,
    TeamIdentityEngineError,
    TeamModel,
    TeamModelBuilder,
)

from tests.team_model_helpers import (
    make_historical_prior,
    make_standard_formation,
    make_standard_squad,
    make_structural_features,
    make_test_player,
)


# ============================================================================
# Module 1 — FormationEngine
# ============================================================================


class TestFormationEngineContract:
    def test_valid_input_returns_structural_features(self):
        engine = FormationEngine()
        result = engine.derive(make_standard_squad(), make_standard_formation())
        assert isinstance(result, StructuralFeatures)
        assert result.formation_name == "4-3-3"
        assert "formation_type" not in result.model_dump()
        assert result.width_feature == pytest.approx(0.8)

    def test_wrong_squad_size_rejected_before_derivation(self):
        engine = FormationEngine()
        squad = make_standard_squad()[:10]  # only 10 players
        formation = make_standard_formation()
        with pytest.raises(FormationEngineError, match="exactly 11"):
            engine.derive(squad, formation)

    def test_duplicate_player_id_rejected(self):
        engine = FormationEngine()
        squad = make_standard_squad()
        squad[1] = squad[0]  # duplicate id
        formation = make_standard_formation()
        with pytest.raises(FormationEngineError, match="duplicate"):
            engine.derive(squad, formation)

    def test_role_count_mismatch_rejected(self):
        """A squad whose role multiset doesn't match the formation's
        position pool must be rejected — Module 1 does not do
        partial/best-effort slotting."""
        engine = FormationEngine()
        squad = make_standard_squad()
        # Replace the sole GK with an extra CM -> role counts no longer match.
        squad[0] = make_test_player("extra_cm", PlayerRole.CM)
        formation = make_standard_formation()
        with pytest.raises(FormationEngineError, match="role counts"):
            engine.derive(squad, formation)

    def test_deterministic_failure(self):
        """Calling derive() twice with the same invalid input raises the
        same exception type both times (no hidden randomness)."""
        engine = FormationEngine()
        squad = make_standard_squad()[:5]
        formation = make_standard_formation()
        for _ in range(3):
            with pytest.raises(FormationEngineError):
                engine.derive(squad, formation)


# ============================================================================
# Module 2 — TeamDimensionEngine
# ============================================================================


class TestTeamDimensionEngineContract:
    def test_valid_input_returns_four_dimensions(self):
        engine = TeamDimensionEngine()
        squad = make_standard_squad()
        features = make_structural_features()
        result = engine.derive(squad, features)
        assert isinstance(result, TeamDimensions)
        assert result.model_dump() == dict(attack=50.0, creation=50.0, defense=50.0, goalkeeping=50.0)

    def test_wrong_squad_size_rejected(self):
        engine = TeamDimensionEngine()
        squad = make_standard_squad()[:3]
        features = make_structural_features()
        with pytest.raises(TeamDimensionEngineError, match="exactly 11"):
            engine.derive(squad, features)

    def test_duplicate_player_id_rejected(self):
        engine = TeamDimensionEngine()
        squad = make_standard_squad()
        squad[3] = squad[2]
        features = make_structural_features()
        with pytest.raises(TeamDimensionEngineError, match="duplicate"):
            engine.derive(squad, features)

    def test_dependency_boundary_no_formation_object_required(self):
        """Module 2's contract is (PlayerSeason[], StructuralFeatures) ->
        TeamDimensions — it must not require a Formation object, only
        the already-derived StructuralFeatures. This is checked by
        confirming derive()'s signature needs no Formation import/usage
        and that a bare StructuralFeatures instance (built with no
        Formation in scope) is accepted for actual D1 calculation."""
        engine = TeamDimensionEngine()
        squad = make_standard_squad()
        features = StructuralFeatures(formation_name="not-a-real-formation-object")
        assert isinstance(engine.derive(squad, features), TeamDimensions)

    def test_deterministic_failure(self):
        engine = TeamDimensionEngine()
        squad = make_standard_squad()[:1]
        features = make_structural_features()
        for _ in range(3):
            with pytest.raises(TeamDimensionEngineError):
                engine.derive(squad, features)


# ============================================================================
# Module 3 — TeamIdentityEngine
# ============================================================================


class TestTeamIdentityEngineContract:
    def test_valid_input_reaches_not_implemented(self):
        engine = TeamIdentityEngine()
        squad = make_standard_squad()
        features = make_structural_features()
        prior = make_historical_prior()
        with pytest.raises(NotImplementedError, match="pre-prior TeamIdentity"):
            engine.derive(squad, features, prior)

    def test_none_historical_prior_is_accepted_shape(self):
        """Tier 3 / fully-generic teams pass historical_prior=None — this
        must be a valid call shape (rejected only by the not-yet-built
        derivation step, never by input validation)."""
        engine = TeamIdentityEngine()
        squad = make_standard_squad()
        features = make_structural_features()
        with pytest.raises(NotImplementedError):
            engine.derive(squad, features, None)

    def test_wrong_squad_size_rejected(self):
        engine = TeamIdentityEngine()
        squad = make_standard_squad()[:2]
        features = make_structural_features()
        with pytest.raises(TeamIdentityEngineError, match="exactly 11"):
            engine.derive(squad, features, None)

    def test_duplicate_player_id_rejected(self):
        engine = TeamIdentityEngine()
        squad = make_standard_squad()
        squad[5] = squad[4]
        features = make_structural_features()
        with pytest.raises(TeamIdentityEngineError, match="duplicate"):
            engine.derive(squad, features, None)

    def test_deterministic_failure(self):
        engine = TeamIdentityEngine()
        squad = make_standard_squad()[:1]
        features = make_structural_features()
        for _ in range(3):
            with pytest.raises(TeamIdentityEngineError):
                engine.derive(squad, features, None)


# ============================================================================
# Already-locked historical-prior blend wiring (NOT behind NotImplementedError)
# ============================================================================


class TestHistoricalPriorBlendWiring:
    """
    These tests confirm the ALREADY-LOCKED Section 30 blend functions
    (apply_historical_prior_to_dimensions / _to_identity) are reachable
    and correct in isolation — they do not touch the unimplemented
    pre-prior derivation steps at all, since those functions take an
    already-derived value as input.
    """

    def test_dimensions_blend_is_noop_for_tier3_or_none(self):
        from football_engine.core.team_season import apply_historical_prior_to_dimensions

        dims = TeamDimensions(attack=70, creation=60, defense=65, goalkeeping=55)

        # None prior -> pass-through
        assert apply_historical_prior_to_dimensions(dims, None) == dims

        # Tier 3 (alpha=1.0) -> pass-through
        tier3_prior = make_historical_prior(tier=HistoricalTier.TIER_3, alpha=1.0)
        assert apply_historical_prior_to_dimensions(dims, tier3_prior) == dims

    def test_identity_blend_is_noop_for_none(self):
        from football_engine.core.team_season import apply_historical_prior_to_identity

        identity = TeamIdentity(
            possession_tendency=0.6,
            press_tendency=0.5,
            transition_tendency=0.5,
            tempo=0.5,
            risk_tolerance=0.5,
            compactness=0.5,
            build_up_control_score=0.5,
            attack_pace_factor=0.5,
        )
        assert apply_historical_prior_to_identity(identity, None) == identity

    def test_identity_blend_applies_tier1_prior(self):
        """Sanity check that the already-locked blend math actually
        moves the value toward the prior when alpha < 1.0 — this is
        testing EXISTING Section 30 code (team_season.py), not anything
        new added in Layer 2."""
        from football_engine.core.team_season import IdentityPriors, apply_historical_prior_to_identity

        identity = TeamIdentity(
            possession_tendency=0.5,
            press_tendency=0.5,
            transition_tendency=0.5,
            tempo=0.5,
            risk_tolerance=0.5,
            compactness=0.5,
            build_up_control_score=0.5,
            attack_pace_factor=0.5,
        )
        prior = make_historical_prior(
            tier=HistoricalTier.TIER_1,
            alpha=0.5,
            identity_priors=IdentityPriors(possession_tendency=0.9),
        )
        blended = apply_historical_prior_to_identity(identity, prior)
        # final = 0.5*0.5 + 0.5*0.9 = 0.70
        assert blended.possession_tendency == pytest.approx(0.70)
        # fields with no prior value fall back to derived-only
        assert blended.press_tendency == 0.5


# ============================================================================
# TeamModelBuilder — orchestration / dependency graph wiring
# ============================================================================


class TestTeamModelBuilderOrchestration:
    def test_build_calls_formation_engine_first(self):
        """The orchestrator must fail at Module 1 (FormationEngine) first
        if Module 1's input is invalid, before ever reaching Module 2/3 —
        proving the locked dependency order (Formation -> Dimensions/Identity)
        is respected, not short-circuited or reordered."""
        builder = TeamModelBuilder()
        bad_squad = make_standard_squad()[:5]  # invalid for Module 1 too
        formation = make_standard_formation()
        with pytest.raises(FormationEngineError):
            builder.build(bad_squad, formation, historical_prior=None)

    def test_build_reaches_possession_source_gap_after_dimension_success(self):
        """Modules 1/2 succeed; default identity still lacks a possession source."""
        builder = TeamModelBuilder()
        with pytest.raises(NotImplementedError, match="possession_tendency"):
            builder.build(make_standard_squad(), make_standard_formation(), historical_prior=None)

    def test_build_accepts_optional_historical_prior(self):
        """historical_prior=None must be a valid TeamModelBuilder.build()
        call (Tier 3 / fully generic team) — rejected only downstream by
        NotImplementedError, never by an input-shape error."""
        builder = TeamModelBuilder()
        squad = make_standard_squad()
        formation = make_standard_formation()
        with pytest.raises(NotImplementedError):
            builder.build(squad, formation, historical_prior=None)

    def test_team_model_dataclass_shape(self):
        """TeamModel must expose exactly the three fields a Layer 5
        match build needs (structural_features, dimensions, identity) —
        confirmed structurally; full builds with an explicit synthetic
        possession source are separately tested."""
        import dataclasses

        field_names = {f.name for f in dataclasses.fields(TeamModel)}
        assert field_names == {"structural_features", "dimensions", "identity"}


# ============================================================================
# Dependency boundary: Module 2/3 engines never import Formation directly
# ============================================================================


class TestDependencyBoundaries:
    def test_team_dimension_engine_module_has_no_formation_import(self):
        """Module 2's locked contract input is (PlayerSeason[],
        StructuralFeatures) — it must not import football_engine.core.formation
        at all, confirming Formation collapsing to StructuralFeatures
        happens only in Module 1, never re-entering downstream."""
        import ast

        tree = ast.parse(open("football_engine/team_model/team_dimension_engine.py").read())
        imported_modules = {
            node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
        }
        assert "football_engine.core.formation" not in imported_modules

    def test_team_identity_engine_module_has_no_formation_import(self):
        import ast

        tree = ast.parse(open("football_engine/team_model/team_identity_engine.py").read())
        imported_modules = {
            node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
        }
        assert "football_engine.core.formation" not in imported_modules

    def test_no_module_in_team_model_uses_randomness(self):
        """Layer 2 contract: RANDOMNESS = NO for all three modules. Static
        guarantee: no team_model source file imports football_engine's
        SeededRNG or Python's random/secrets modules."""
        import ast
        import pathlib

        forbidden = {"random", "secrets", "football_engine.rng.seeded_rng", "football_engine.rng"}
        for path in pathlib.Path("football_engine/team_model").glob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name not in forbidden, f"{path} imports {alias.name}"
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert node.module not in forbidden, f"{path} imports from {node.module}"

    def test_no_module_in_team_model_mutates_runtime_state(self):
        """Layer 2 contract: CAN_CHANGE_STATE = NO for all three modules.
        Static guarantee: no team_model source file imports TeamRuntimeState
        or MatchRuntime (the only mutable runtime containers, per Layer 0)."""
        import ast
        import pathlib

        forbidden = {"football_engine.core.team_runtime_state", "football_engine.core.match_runtime"}
        for path in pathlib.Path("football_engine/team_model").glob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert node.module not in forbidden, f"{path} imports from {node.module}"
