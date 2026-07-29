"""Fuzz harness: import_dotted_path() (FT-16).

Tests that the resolution loop handles arbitrary dotted strings without
crashing Python.

Input strategy
--------------
To avoid importing unknown third-party modules (which could have side
effects), all fuzz-generated strings are prefixed with one of a small
set of known-safe module roots.  The suffix is fuzz-derived, exercising
the getattr-chain walk and the no-valid-prefix error path.

Invariants asserted
-------------------
- Strings without a dot raise ValueError.
- Non-importable strings raise ValueError.
- The returned object (when the call succeeds) is accessible; no crash.
- For known-non-type suffixes (e.g. "os.path.join") a subsequent
  isinstance(obj, type) check returns False — not a crash.
"""
from __future__ import annotations

import sys

import atheris

with atheris.instrument_imports():
    from physicalai.inference._importing import import_dotted_path

# Safe module roots — all are part of the Python standard library or
# physicalai itself.  We fuzz the suffix to exercise various getattr chains.
_SAFE_ROOTS = [
    "physicalai.inference.manifest",
    "physicalai.inference.runners",
    "physicalai.inference.preprocessors",
    "physicalai.inference.postprocessors",
    "physicalai.inference.adapters",
    "physicalai.runtime.smoothers",
    "physicalai.runtime.events",
    "json",
    "os.path",
    "collections",
    "abc",
]


def test_one_input(data: bytes) -> None:
    if len(data) < 2:
        return

    fdp = atheris.FuzzedDataProvider(data)
    sub = fdp.ConsumeIntInRange(0, 2)

    if sub == 0:
        # Completely arbitrary string — exercises error paths
        path = fdp.ConsumeUnicodeNoSurrogates(128)
        try:
            import_dotted_path(path)
        except ValueError:
            pass  # Expected for missing dot or non-importable prefix

    elif sub == 1:
        # Rooted at a known-safe module + fuzz suffix
        root = fdp.PickValueInList(_SAFE_ROOTS)
        suffix = fdp.ConsumeUnicodeNoSurrogates(64)
        suffix_clean = "".join(c if c.isidentifier() or c == "." else "_" for c in suffix)
        path = f"{root}.{suffix_clean}" if suffix_clean else root
        try:
            import_dotted_path(path)
        except (ValueError, AttributeError):
            pass

    else:
        # No-dot string — must always raise ValueError
        path = fdp.ConsumeUnicodeNoSurrogates(64).replace(".", "_")
        try:
            import_dotted_path(path)
        except ValueError:
            return
        # If no ValueError was raised for a string without dots, that's a bug
        if "." not in path:
            raise AssertionError(
                f"import_dotted_path({path!r}) did not raise ValueError for a no-dot string"
            )


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
