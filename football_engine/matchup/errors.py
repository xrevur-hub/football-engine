"""Layer 3 errors. No Layer 0 model or Layer 2 derivation is changed."""


class Layer3InputError(ValueError):
    """A specified formula cannot accept an input or produce a valid result.

    Undefined divisions, non-finite numbers, and negative rates fail explicitly;
    they are never repaired with an undocumented epsilon, clamp, or multiplier.
    """


class SpecificationGapError(NotImplementedError):
    """A canonical helper equation is absent, not silently approximated."""
