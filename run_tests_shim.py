"""Local pytest-compatible runner: original tests + isolated Layer 3 tests.

Run from the repository root. This is not the real pytest distribution: the
bundled minimal shim supports raises/approx/fixture, and this runner resolves
only the existing tmp_path/tmp_dataset_dir/seed_data_dir fixtures. No skip,
xfail, plugins, or parametrized collection is silently claimed as supported.

Layer 3 adds automatic test-module discovery, machine-readable reports, and a
nonzero exit status on failure (including collection failures). Original tests
are unchanged. The bundled shim is the existing local shim with its missing
ExceptionInfo.value compatibility property restored.
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import json
import pathlib
import sys
import tempfile
import traceback

REPO_ROOT = pathlib.Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO_ROOT))
BUNDLED_SHIM = REPO_ROOT / "tools" / "pytest_shim"
SHIM_ROOT = BUNDLED_SHIM if (BUNDLED_SHIM / "pytest.py").is_file() else pathlib.Path("/data/pytest_shim")
sys.path.insert(0, str(SHIM_ROOT))

import pytest  # noqa: E402 -- deliberately the local compatibility shim
from tests import conftest  # noqa: E402


def make_tmp_path() -> pathlib.Path:
    return pathlib.Path(tempfile.mkdtemp(prefix="fe_test_"))


def resolve_fixture(name: str):
    if name == "tmp_path":
        return make_tmp_path()
    if name == "tmp_dataset_dir":
        return conftest.tmp_dataset_dir(make_tmp_path())
    if name == "seed_data_dir":
        return conftest.seed_data_dir()
    raise LookupError(f"No fixture registered for '{name}'")


def call_with_fixtures(func):
    sig = inspect.signature(func)
    kwargs = {}
    for pname in sig.parameters:
        if pname == "self":
            continue
        kwargs[pname] = resolve_fixture(pname)
    func(**kwargs)


def run_module(module_name: str, results: list):
    module = importlib.import_module(module_name)
    for obj_name, obj in sorted(vars(module).items()):
        if inspect.isclass(obj) and obj_name.startswith("Test") and obj.__module__ == module_name:
            instance = obj()
            for meth_name, meth in sorted(vars(obj).items()):
                if meth_name.startswith("test_") and callable(meth):
                    full_name = f"{module_name}.{obj_name}.{meth_name}"
                    _run_one(full_name, lambda m=meth, i=instance: call_with_fixtures(m.__get__(i)), results)
        elif inspect.isfunction(obj) and obj_name.startswith("test_") and obj.__module__ == module_name:
            full_name = f"{module_name}.{obj_name}"
            _run_one(full_name, lambda f=obj: call_with_fixtures(f), results)


def _run_one(full_name: str, thunk, results: list):
    try:
        thunk()
        results.append((full_name, "PASS", None))
    except Exception as error:
        results.append((full_name, "FAIL", f"{type(error).__name__}: {error}\n{traceback.format_exc(limit=3)}"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", action="append", dest="modules", help="Run an explicit module; repeat to select several")
    parser.add_argument("--json", type=pathlib.Path, dest="json_path", help="Write the actual results to a JSON report")
    args = parser.parse_args()
    module_names = args.modules or [f"tests.{path.stem}" for path in sorted((REPO_ROOT / "tests").glob("test_*.py"))]
    results: list = []
    for module_name in module_names:
        try:
            run_module(module_name, results)
        except Exception as error:
            # Collection errors count as failures, rather than disappearing
            # behind a misleading all-green summary or successful exit status.
            results.append((f"{module_name}.<collection>", "FAIL", f"{type(error).__name__}: {error}\n{traceback.format_exc(limit=3)}"))

    passed = [r for r in results if r[1] == "PASS"]
    failed = [r for r in results if r[1] == "FAIL"]
    print(f"\n=== RESULTS: {len(passed)} passed, {len(failed)} failed, {len(results)} total ===\n")
    for name, status, error in results:
        if status == "FAIL":
            print(f"FAIL: {name}")
            print(error)
            print("-" * 60)
    print("\nPassed tests:")
    for name, status, _ in results:
        if status == "PASS":
            print(f"  PASS: {name}")

    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "runner": "local pytest-compatible harness (not real pytest)",
            "python": sys.version.split()[0],
            "shim_path": str(SHIM_ROOT / "pytest.py"),
            "modules": module_names,
            "passed": len(passed),
            "failed": len(failed),
            "total": len(results),
            "results": [{"name": name, "status": status, "error": error} for name, status, error in results],
        }
        args.json_path.write_text(json.dumps(report, indent=2) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
