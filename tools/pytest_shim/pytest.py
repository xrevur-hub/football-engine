"""Minimal pytest-compatible shim.

The sandbox has no network access, so the real pytest package cannot be
installed. This shim implements just enough of pytest's public surface
(raises, approx, fixture, mark) to actually execute the project's test
suite with real Python semantics, instead of only statically analyzing it.
"""
from __future__ import annotations

import re
import math


class _RaisesContext:
    def __init__(self, expected_exception, match=None):
        if not isinstance(expected_exception, tuple):
            expected_exception = (expected_exception,)
        self.expected_exception = expected_exception
        self.match_pattern = match
        self.exc_info = None
        self.value = None  # pytest.ExceptionInfo compatibility, not a test override

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if exc_type is None:
            raise AssertionError("DID NOT RAISE " + repr(self.expected_exception))
        if not issubclass(exc_type, self.expected_exception):
            return False
        if self.match_pattern is not None:
            if not re.search(self.match_pattern, str(exc_value)):
                raise AssertionError(
                    "Pattern " + repr(self.match_pattern) + " does not match " + repr(str(exc_value))
                )
        self.exc_info = exc_value
        self.value = exc_value
        return True


def raises(expected_exception, *, match=None):
    return _RaisesContext(expected_exception, match=match)


class _Approx:
    def __init__(self, value, rel=1e-6, abs=1e-12):
        self.value = value
        self.rel = rel
        self.abs = abs

    def __eq__(self, other):
        try:
            return math.isclose(other, self.value, rel_tol=self.rel, abs_tol=self.abs)
        except TypeError:
            return NotImplemented

    def __repr__(self):
        return "approx(" + repr(self.value) + ")"


def approx(value, rel=1e-6, abs=1e-12):
    return _Approx(value, rel=rel, abs=abs)


def fixture(func=None, *, scope="function", params=None, autouse=False):
    def decorator(f):
        f._pytest_fixture = True
        f._pytest_fixture_scope = scope
        return f
    if func is not None:
        return decorator(func)
    return decorator


class _Mark:
    def parametrize(self, argnames, argvalues):
        def decorator(f):
            f._pytest_parametrize = (argnames, argvalues)
            return f
        return decorator

    def __getattr__(self, name):
        def decorator(*a, **k):
            def wrap(f):
                return f
            return wrap
        return decorator


mark = _Mark()


class ExceptionInfo:
    pass
