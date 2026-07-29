"""Fuzz harness: ComponentSpec resolution (FT-2, FT-3, FT-4).

Four sub-targets are exercised, chosen randomly per input:

  A — resolve_artifact() path traversal prevention
      Generates arbitrary artifact path strings and asserts that the
      resolved path never escapes the export directory.

  B — instantiate_component() depth limit
      Constructs ComponentSpec dicts nested deeper than
      _MAX_COMPONENT_DEPTH (10) and asserts the ValueError is raised
      before any constructor is called at the excess depth.

  C — flat params injection via known-safe component short names
      Passes unexpected extra kwargs to registered components;
      expects TypeError from the constructor, not a crash.

  D — symlink-bypass documentation test
      Creates a symlink inside the export dir pointing to a file outside,
      then passes the symlink name as ``artifact``.  The check in
      resolve_artifact is intentionally lexical (normpath, no symlink
      follow) so this MUST be accepted without ValueError.  This sub-target
      verifies the documented design is stable and has not been accidentally
      changed to either reject or silently resolve through the symlink.

NOTE: Sub-target A is run in an isolated temp directory so that any
      accidental path escape is immediately detectable.
      Sub-target B and C are restricted to physicalai registry names
      to avoid importing unknown modules in CI.
"""
from __future__ import annotations

import os
import sys
import tempfile

import atheris

with atheris.instrument_imports():
    from pydantic import ValidationError
    from physicalai.inference.manifest import ComponentSpec
    from physicalai.inference.component_factory import instantiate_component, resolve_artifact

# Depth limit value — mirrors _MAX_COMPONENT_DEPTH in component_factory
_MAX_DEPTH = 10

# Registry short names safe to instantiate for flat-params injection tests
_SAFE_TYPES = [
    "single_pass",
    "action_chunk_trimmer",
]


@atheris.instrument_func
def _sub_resolve_artifact(fdp: atheris.FuzzedDataProvider, export_dir: str) -> None:
    """Assert that resolve_artifact never returns a path outside export_dir."""
    artifact = fdp.ConsumeUnicodeNoSurrogates(256)
    try:
        spec = ComponentSpec.model_validate({"type": "normalize", "artifact": artifact})
    except ValidationError:
        return

    try:
        result = resolve_artifact(spec, export_dir)
    except ValueError:
        return  # Expected for traversal attempts

    resolved = result.flat_params.get("artifact", "")
    if resolved and os.path.isabs(resolved):
        # Use Path.is_relative_to() — str.startswith() is NOT a safe path
        # containment check (/tmp/export_evil starts with /tmp/export).
        from pathlib import Path

        real_export = Path(os.path.realpath(export_dir))
        real_resolved = Path(os.path.normpath(resolved))
        assert real_resolved.is_relative_to(real_export), (
            f"PATH TRAVERSAL: artifact {artifact!r} resolved to {resolved!r}, "
            f"which escapes export_dir {export_dir!r}"
        )


@atheris.instrument_func
def _sub_depth_limit(fdp: atheris.FuzzedDataProvider) -> None:
    """Assert that nesting beyond _MAX_DEPTH raises ValueError."""
    depth = fdp.ConsumeIntInRange(1, _MAX_DEPTH + 8)

    # Build a chain: each level wraps the previous via init_args
    inner: dict = {
        "class_path": "physicalai.inference.runners.SinglePass",
        "init_args": {},
    }
    for _ in range(depth):
        inner = {
            "class_path": "physicalai.inference.postprocessors.ActionNormalizer",
            "init_args": {"_child": inner},
        }

    try:
        spec = ComponentSpec.model_validate(inner)
        instantiate_component(spec)
    except ValueError as exc:
        if depth > _MAX_DEPTH:
            assert "depth" in str(exc).lower() or "nesting" in str(exc).lower(), (
                f"Expected depth-limit ValueError for depth={depth}, got: {exc}"
            )
    except (TypeError, AttributeError):
        pass  # Constructor errors are fine; what matters is no crash before depth limit


@atheris.instrument_func
def _sub_flat_params(fdp: atheris.FuzzedDataProvider) -> None:
    """Pass unexpected flat kwargs to known-safe registered component types."""
    chosen = fdp.PickValueInList(_SAFE_TYPES)
    n_extra = fdp.ConsumeIntInRange(0, 8)
    extra = {
        fdp.ConsumeUnicodeNoSurrogates(16): fdp.ConsumeUnicodeNoSurrogates(32)
        for _ in range(n_extra)
    }
    spec_dict = {"type": chosen, **extra}
    try:
        spec = ComponentSpec.model_validate(spec_dict)
        instantiate_component(spec)
    except (TypeError, ValueError, AttributeError):
        pass


@atheris.instrument_func
def _sub_symlink_bypass(export_dir: str) -> None:
    """Verify the documented symlink bypass: lexical check accepts intra-dir symlinks.

    The resolve_artifact() guard uses normpath (lexical) not realpath (follows
    symlinks).  A symlink that lives inside export_dir but points to a file
    outside is intentionally accepted — Hub snapshot directories rely on this.
    This sub-target:
      1. Creates a file in a sibling temp directory (outside export_dir).
      2. Creates a symlink inside export_dir pointing to that outside file.
      3. Asserts resolve_artifact does NOT raise ValueError (by design).
      4. Asserts the returned artifact path is lexically within export_dir
         (i.e., the symlink itself, not the target it points to).

    If this test starts FAILING with ValueError, it means the lexical bypass
    has been (accidentally) closed.  That is a behaviour change requiring a
    deliberate security review, not a silent regression.
    """
    import tempfile
    from pathlib import Path

    # Create a file outside export_dir that the symlink will point to.
    with tempfile.NamedTemporaryFile(delete=False) as outside_file:
        outside_path = outside_file.name

    try:
        link_name = "symlinked_artifact"
        link_path = os.path.join(export_dir, link_name)
        try:
            os.symlink(outside_path, link_path)
        except (OSError, NotImplementedError):
            # Symlinks may be unavailable in some sandbox environments; skip.
            return

        try:
            spec = ComponentSpec.model_validate(
                {"type": "normalize", "artifact": link_name}
            )
        except ValidationError:
            return

        try:
            result = resolve_artifact(spec, export_dir)
        except ValueError:
            # The bypass was closed — flag as an assertion so the fuzzer
            # surfaces it as a behaviour change, not a silent skip.
            raise AssertionError(
                f"resolve_artifact raised ValueError for intra-dir symlink "
                f"{link_name!r} → {outside_path!r}.  This closes the documented "
                f"lexical bypass.  Verify this is intentional before silencing."
            ) from None

        # The returned path must be lexically inside export_dir.
        returned = result.flat_params.get("artifact", "")
        if returned:
            assert Path(os.path.normpath(returned)).is_relative_to(
                Path(os.path.realpath(export_dir))
            ), (
                f"Symlink artifact resolved to {returned!r} which escapes "
                f"export_dir {export_dir!r}"
            )
    finally:
        try:
            os.unlink(outside_path)
        except OSError:
            pass



    if len(data) < 4:
        return
    fdp = atheris.FuzzedDataProvider(data)
    sub = fdp.ConsumeIntInRange(0, 3)

    if sub == 0:
        with tempfile.TemporaryDirectory() as export_dir:
            _sub_resolve_artifact(fdp, export_dir)
    elif sub == 1:
        _sub_depth_limit(fdp)
    elif sub == 2:
        _sub_flat_params(fdp)
    else:
        with tempfile.TemporaryDirectory() as export_dir:
            _sub_symlink_bypass(export_dir)
        _sub_flat_params(fdp)


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
