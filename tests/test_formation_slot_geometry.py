"""
Requirement 9 tests for the PositionSlot side/depth contract refinement.

Context: this is an ADDITIVE Layer 0/core contract change (conversation
record — "Option 3" decision, 2026-09-08). `PositionSlot.slot_id` remains
an identifier only; `side`/`depth` are the explicit structural geometry
fields. These tests prove the four properties required by that decision:

1. Every formation slot has explicit side/depth.
2. Formation Engine does not parse slot_id for semantic meaning.
3. Changing slot_id naming does not alter structural semantics /
   validation behavior.
4. Invalid/missing side/depth is rejected.

After the separately verified E-12 migration and Step B implementation,
these guards compare real structural outputs instead of a placeholder error.
The dedicated V1 tests separately verify the six numerical rules.
"""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from football_engine.core.enums import PlayerRole
from football_engine.core.formation import Formation, PositionSlot, SlotDepth, SlotSide
from football_engine.team_model import formation_engine as formation_engine_module
from football_engine.team_model.formation_engine import FormationEngine

from tests.team_model_helpers import make_standard_formation, make_standard_squad


class TestEveryFormationSlotHasExplicitSideDepth:
    def test_standard_formation_slots_all_have_side_and_depth(self):
        formation = make_standard_formation()
        assert len(formation.position_pool) == 11
        for slot in formation.position_pool:
            assert isinstance(slot.side, SlotSide)
            assert isinstance(slot.depth, SlotDepth)


class TestFormationEngineDoesNotParseSlotId:
    def test_source_does_not_string_match_on_slot_id(self):
        """
        Static guard: FormationEngine's module source must never call
        string-inspection methods (startswith/endswith/split/etc.) on
        slot_id or a `.slot_id` attribute access chain. This directly
        guards against reintroducing the rejected "parse the name"
        approach (Option 1 from the conversation record).
        """
        source = inspect.getsource(formation_engine_module)
        forbidden_patterns = [
            "slot_id.startswith",
            "slot_id.endswith",
            "slot_id.split",
            "slot.slot_id[",
            "in slot_id",
        ]
        for pattern in forbidden_patterns:
            assert pattern not in source, f"FormationEngine source appears to parse slot_id via {pattern!r}"

    def test_validation_behavior_identical_regardless_of_slot_id_spelling(self):
        """
        Companion to the static guard above: actually exercise the engine
        with two formations that differ ONLY in slot_id spelling (same
        role/side/depth) and confirm identical behavior end-to-end, i.e.
        slot_id text has zero effect on FormationEngine's decisions.
        """
        formation_a = make_standard_formation(name="4-3-3-A")
        renamed_slots = [
            PositionSlot(
                slot_id=f"totally_renamed_{i}",
                role=slot.role,
                side=slot.side,
                depth=slot.depth,
            )
            for i, slot in enumerate(formation_a.position_pool)
        ]
        formation_b = Formation(name="4-3-3-B", position_pool=renamed_slots)

        players = make_standard_squad()
        engine = FormationEngine()

        features_a = engine.derive(players, formation_a)
        features_b = engine.derive(players, formation_b)
        # Names are descriptive metadata; all computed features must be equal.
        assert features_a.model_dump(exclude={"formation_name"}) == features_b.model_dump(exclude={"formation_name"})
        assert features_a.formation_name == formation_a.name
        assert features_b.formation_name == formation_b.name


class TestSlotIdRenamingDoesNotAlterStructuralSemantics:
    def test_renaming_slot_id_preserves_side_and_depth(self):
        formation = make_standard_formation()
        original = formation.position_pool[0]
        renamed = PositionSlot(
            slot_id="some_completely_different_name",
            role=original.role,
            side=original.side,
            depth=original.depth,
        )
        assert renamed.side == original.side
        assert renamed.depth == original.depth
        assert renamed.role == original.role
        # Only the identifier changed.
        assert renamed.slot_id != original.slot_id


class TestInvalidOrMissingSideDepthIsRejected:
    def test_missing_side_is_rejected(self):
        with pytest.raises(ValidationError):
            PositionSlot(slot_id="LCB", role=PlayerRole.CB, depth=SlotDepth.BACK)  # no side

    def test_missing_depth_is_rejected(self):
        with pytest.raises(ValidationError):
            PositionSlot(slot_id="LCB", role=PlayerRole.CB, side=SlotSide.LEFT)  # no depth

    def test_invalid_side_value_is_rejected(self):
        with pytest.raises(ValidationError):
            PositionSlot(slot_id="LCB", role=PlayerRole.CB, side="north", depth=SlotDepth.BACK)

    def test_invalid_depth_value_is_rejected(self):
        with pytest.raises(ValidationError):
            PositionSlot(slot_id="LCB", role=PlayerRole.CB, side=SlotSide.LEFT, depth="deep")
