"""
Layer 6 — Player Events & Attribution.

This package implements Modules 9/10: goal attribution, shot generation,
save generation, card generation, and substitution generation.

All events emerge probabilistically from the existing match model.
"""

from __future__ import annotations

from football_engine.events.attribution import (
    EventGenerationCoefficients,
    DEFAULT_EVENT_COEFFICIENTS,
    EventGenerator,
    create_event_generator,
    attribute_goals_for_team,
    generate_shots,
    generate_saves,
    generate_cards,
    generate_substitutions,
)

__all__ = [
    "EventGenerationCoefficients",
    "DEFAULT_EVENT_COEFFICIENTS",
    "EventGenerator",
    "create_event_generator",
    "attribute_goals_for_team",
    "generate_shots",
    "generate_saves",
    "generate_cards",
    "generate_substitutions",
]