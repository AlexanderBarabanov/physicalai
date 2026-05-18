# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Fuzz harness for ``instantiate_component()`` recursion depth (TM-009).

Threat model target
-------------------
TM-009  ``instantiate_component()`` calls itself recursively for every
        ``init_args`` value whose dict contains ``class_path`` or ``type``.
        There is no depth guard.  Python's default recursion limit (~1000
        frames) is the only backstop.  A ``manifest.json`` with ~500 levels
        of nested ``init_args`` triggers ``RecursionError``, crashing the
        operator process during ``InferenceModel.__init__``.

Design
------
To avoid importing arbitrary modules during fuzzing this harness installs a
private no-op class into ``sys.modules`` under a synthetic module name.  The
``_safe_registry`` maps the no-op class path as its only entry, so
``instantiate_component()`` never executes ``importlib.import_module()`` on
any real module beyond retrieving the pre-loaded no-op.

The FuzzedDataProvider consumes one integer in [0, _MAX_DEPTH] from the
input bytes to select the nesting level.  The harness then builds a synthetic
``ComponentSpec`` tree of that depth and calls ``instantiate_component()``.

RecursionError is intentionally NOT caught.  Atheris records any uncaught
exception as a crash, writes the triggering input to an artifact file, and
exits non-zero.  This is the TM-009 detection signal.

Running
-------
    python tests/fuzz/fuzz_component_instantiate.py \
        tests/fuzz/corpus/component \
        -max_total_time=600 -artifact_prefix=crashes/component-

Crash interpretation
--------------------
A ``RecursionError`` crash file confirms TM-009.  The depth printed in the
atheris output indicates the number of nested ``init_args`` levels required
to exhaust the stack.
"""

import sys
import types

import atheris

# ---------------------------------------------------------------------------
# Install a safe no-op module into sys.modules BEFORE any instrumentation.
# This prevents importlib from touching the filesystem during fuzzing.
# ---------------------------------------------------------------------------
_NOOP_MODULE_NAME = "_physicalai_fuzz_noop"
_noop_module = types.ModuleType(_NOOP_MODULE_NAME)


class _NoOp:
    """Stub class — accepts any kwargs and does nothing."""

    def __init__(self, **kwargs: object) -> None:
        pass


_noop_module._NoOp = _NoOp  # type: ignore[attr-defined]
sys.modules[_NOOP_MODULE_NAME] = _noop_module

_NOOP_CLASS_PATH = f"{_NOOP_MODULE_NAME}._NoOp"

# ---------------------------------------------------------------------------
# Import physicalai modules under atheris instrumentation.
# ---------------------------------------------------------------------------
with atheris.instrument_imports():
    from pydantic import ValidationError

    from physicalai.inference.component_factory import ComponentRegistry, instantiate_component
    from physicalai.inference.manifest import ComponentSpec

# ---------------------------------------------------------------------------
# Restricted registry: only resolves to the safe no-op class.
# ---------------------------------------------------------------------------
_safe_registry = ComponentRegistry()
_safe_registry.register("_noop", _NOOP_CLASS_PATH)

# Maximum nesting depth the fuzzer may request.  Depths above ~500 reliably
# trigger RecursionError in CPython 3.12 given the call-frame overhead of
# instantiate_component() + ComponentSpec.model_validate().
_MAX_DEPTH = 1000


def _build_nested_spec(depth: int) -> dict:
    """Return a ComponentSpec dict nested *depth* levels deep.

    Each level adds one ``init_args`` key pointing to the next level.
    At depth 0 the spec is a flat ``{"class_path": ..., "init_args": {}}``.
    """
    spec: dict = {"class_path": _NOOP_CLASS_PATH, "init_args": {}}
    for _ in range(depth):
        spec = {"class_path": _NOOP_CLASS_PATH, "init_args": {"_child": spec}}
    return spec


@atheris.instrument_func
def test_one_input(data: bytes) -> None:
    """Atheris entry point — called with mutated byte sequences."""
    fdp = atheris.FuzzedDataProvider(data)
    depth = fdp.ConsumeIntInRange(0, _MAX_DEPTH)

    spec_dict = _build_nested_spec(depth)

    try:
        component_spec = ComponentSpec.model_validate(spec_dict)
    except (ValueError, ValidationError):
        return

    # RecursionError is NOT caught — atheris records it as a crash (TM-009).
    try:
        instantiate_component(component_spec, registry=_safe_registry)
    except (ValueError, TypeError):
        pass


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
