"""
Layer 1 — data loading/validation exceptions.

All exceptions carry enough context in their message to debug a bad JSON
file without needing to attach a debugger (L1.7: "error message باید
قابل debug باشد"). Each exception type maps to one category of failure
called out explicitly in the Layer 1 requirements (L1.5, L1.7).
"""

from __future__ import annotations


class DataLayerError(Exception):
    """Base class for every Layer 1 data-loading/validation error."""


class DatasetFileError(DataLayerError):
    """Raised when a dataset JSON file is missing, unreadable, or not valid JSON."""


class SchemaValidationError(DataLayerError):
    """
    Raised when a record fails its Pydantic schema (out-of-range
    attribute, wrong type, malformed season string, etc.) — wraps the
    underlying pydantic.ValidationError with the offending file/record
    identified.
    """


class DuplicateIdError(DataLayerError):
    """Raised when two records in the same dataset share an id that must be unique."""


class UnknownReferenceError(DataLayerError):
    """
    Raised when a record references another record by id and that id
    does not exist in the target repository — e.g. a TeamSeason roster
    entry pointing at a PlayerSeason id that was never loaded, or a
    HistoricalPrior referencing an unknown team_season_id.
    """


class InvalidFormationAssignmentError(DataLayerError):
    """
    Raised when a formation-related assignment is invalid — e.g. a
    default_formation reference to a Formation.name that doesn't exist
    in the formation repository, or (Layer 2+ usage) an XI selection
    that assigns a player id not present in the team's roster to a
    formation slot.
    """
