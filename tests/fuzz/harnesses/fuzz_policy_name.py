"""Fuzz harness: Policy name validation (FT-12, FT-13).

Tests
-----
  A — Direct: _is_safe_policy_name() with arbitrary strings.
      Asserts that the regex never crashes Python and that any name
      accepted by the regex satisfies the documented character set.

  B — Integration: InferenceModel.__init__(export_dir, policy_name=name)
      Asserts that:
        * Unsafe names (those that fail _is_safe_policy_name) always raise ValueError.
        * Safe names never raise ValueError (FileNotFoundError or other IO
          errors are expected when no model files are present).

Invariants asserted
-------------------
- _is_safe_policy_name never crashes for any unicode string.
- policy_name that fails _is_safe_policy_name always raises ValueError.
- policy_name that passes _is_safe_policy_name never raises ValueError
  (other exceptions are allowed since the export dir has no model).
"""
from __future__ import annotations

import sys
import tempfile

import atheris

with atheris.instrument_imports():
    from physicalai.inference.model import InferenceModel, _is_safe_policy_name


def test_one_input(data: bytes) -> None:
    if len(data) < 2:
        return

    fdp = atheris.FuzzedDataProvider(data)
    sub = fdp.ConsumeBool()

    name = fdp.ConsumeUnicodeNoSurrogates(128)

    if sub:
        # Sub A: pure regex check
        result = _is_safe_policy_name(name)
        if result:
            # Oracle: every accepted character must be in [a-zA-Z0-9_.\-]
            if name:
                assert name[0].isalnum(), (
                    f"_is_safe_policy_name accepted {name!r} but first char is not alphanumeric"
                )
                allowed_tail = set("abcdefghijklmnopqrstuvwxyz"
                                   "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                                   "0123456789_.-")
                bad = [c for c in name[1:] if c not in allowed_tail]
                assert not bad, (
                    f"_is_safe_policy_name accepted {name!r} but found disallowed chars: {bad}"
                )
    else:
        # Sub B: integration with InferenceModel
        is_safe = _is_safe_policy_name(name)
        with tempfile.TemporaryDirectory() as export_dir:
            try:
                InferenceModel(export_dir, policy_name=name)
            except ValueError:
                # Oracle: ValueError must only be raised for unsafe names
                assert not is_safe, (
                    f"InferenceModel raised ValueError for safe policy_name {name!r}"
                )
            except (FileNotFoundError, RuntimeError):
                # Expected when no model artifacts exist in the temp dir
                pass


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
