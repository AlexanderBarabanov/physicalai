#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Generate a mutation-based seed corpus for the manifest fuzzer.

Each mutation targets a specific code path or threat-model finding.
Run from the repository root:

    python tests/fuzz/generate_corpus.py

Existing seed files in ``tests/fuzz/corpus/manifests/`` are never
overwritten; only new names are written.
"""

from __future__ import annotations

import json
from pathlib import Path

CORPUS_DIR = Path("tests/fuzz/corpus/manifests")
CORPUS_DIR.mkdir(parents=True, exist_ok=True)

_RUNNER_TYPE = {"type": "single_pass"}
_RUNNER_CLASS_PATH = {
    "class_path": "physicalai.inference.runners.SinglePass",
    "init_args": {},
}


def _write(name: str, obj: object) -> None:
    path = CORPUS_DIR / f"{name}.json"
    if path.exists():
        return
    path.write_text(json.dumps(obj), encoding="utf-8")
    print(f"  + {path.name}")


def _nested_runner(depth: int) -> dict:
    """Return a runner spec nested *depth* init_args levels deep."""
    spec: dict = {**_RUNNER_CLASS_PATH}
    for _ in range(depth):
        spec = {
            "class_path": "physicalai.inference.runners.SinglePass",
            "init_args": {"_sub": spec},
        }
    return spec


# ---------------------------------------------------------------------------
# Baseline — valid manifests the fuzzer can mutate from
# ---------------------------------------------------------------------------
BASELINE_MUTATIONS: dict[str, object] = {
    "valid_minimal": {
        "format": "policy_package",
        "version": "1.0",
        "policy": {"name": "act"},
        "model": {"runner": _RUNNER_TYPE},
        "hardware": {},
        "metadata": {},
    },
    "valid_class_path_style": {
        "policy": {"name": "act"},
        "model": {"runner": _RUNNER_CLASS_PATH},
    },
    "valid_with_hardware": {
        "policy": {"name": "act"},
        "model": {
            "runner": _RUNNER_TYPE,
            "preprocessors": [{"type": "normalize"}],
            "postprocessors": [{"type": "denormalize"}],
        },
        "hardware": {
            "robots": [{"name": "main", "state": {"shape": [6], "dtype": "float32"}, "action": {"shape": [6], "dtype": "float32"}}],
            "cameras": [{"name": "top", "shape": [3, 480, 640], "dtype": "uint8"}],
        },
    },
}

# ---------------------------------------------------------------------------
# TM-001 — class_path passthrough (arbitrary dotted path, no allowlist)
# ---------------------------------------------------------------------------
CLASS_PATH_MUTATIONS: dict[str, object] = {
    # Standard-library modules reachable via passthrough
    "cp_os_system": {"model": {"runner": {"class_path": "os.system", "init_args": {}}}},
    "cp_subprocess_popen": {"model": {"runner": {"class_path": "subprocess.Popen", "init_args": {}}}},
    "cp_builtins_eval": {"model": {"runner": {"class_path": "builtins.eval", "init_args": {}}}},
    # Structural edge cases that hit rsplit / getattr paths
    "cp_single_segment": {"model": {"runner": {"class_path": "nodot", "init_args": {}}}},
    "cp_many_segments": {"model": {"runner": {"class_path": "a.b.c.d.e.f.g.h.Cls", "init_args": {}}}},
    "cp_empty_string": {"model": {"runner": {"type": "single_pass", "class_path": ""}}},
    "cp_nonexistent": {"model": {"runner": {"class_path": "nonexistent_xyz.Class", "init_args": {}}}},
    # flat_params forwarded as constructor kwargs (ComponentSpec.flat_params)
    "cp_extra_flat_params": {
        "model": {
            "runner": {
                "class_path": "physicalai.inference.runners.SinglePass",
                "init_args": {},
                "injected_kwarg": "value",
                "numeric_kwarg": 42,
            }
        }
    },
    # type + class_path both set (class_path takes precedence)
    "cp_both_type_and_class_path": {
        "model": {
            "runner": {
                "type": "single_pass",
                "class_path": "os.getcwd",
                "init_args": {},
            }
        }
    },
}

# ---------------------------------------------------------------------------
# TM-010 — manifest.policy.name path traversal into model_path
# ---------------------------------------------------------------------------
POLICY_NAME_MUTATIONS: dict[str, object] = {
    "pn_unix_traversal": {"policy": {"name": "../../../etc/passwd"}, "model": {"runner": _RUNNER_TYPE}},
    "pn_deep_unix_traversal": {"policy": {"name": "../../../../../../../../etc/shadow"}, "model": {"runner": _RUNNER_TYPE}},
    "pn_windows_traversal": {"policy": {"name": "..\\..\\Windows\\System32\\cmd"}, "model": {"runner": _RUNNER_TYPE}},
    "pn_absolute_unix": {"policy": {"name": "/etc/shadow"}, "model": {"runner": _RUNNER_TYPE}},
    "pn_absolute_windows": {"policy": {"name": "C:\\Windows\\System32\\drivers\\etc\\hosts"}, "model": {"runner": _RUNNER_TYPE}},
    "pn_null_byte": {"policy": {"name": "act\x00injected"}, "model": {"runner": _RUNNER_TYPE}},
    "pn_very_long": {"policy": {"name": "a" * 4096}, "model": {"runner": _RUNNER_TYPE}},
    "pn_dots_only": {"policy": {"name": "..."}, "model": {"runner": _RUNNER_TYPE}},
    "pn_special_chars": {"policy": {"name": '<>:"/\\|?*'}, "model": {"runner": _RUNNER_TYPE}},
    "pn_url_encoded": {"policy": {"name": "..%2F..%2Fetc%2Fpasswd"}, "model": {"runner": _RUNNER_TYPE}},
    "pn_unicode_traversal": {"policy": {"name": "модель/../../../etc"}, "model": {"runner": _RUNNER_TYPE}},
    "pn_with_extension": {"policy": {"name": "../../etc/shadow.xml"}, "model": {"runner": _RUNNER_TYPE}},
    "pn_empty": {"policy": {"name": ""}, "model": {"runner": _RUNNER_TYPE}},
}

# ---------------------------------------------------------------------------
# TM-003 — artifact field path traversal in preprocessor specs
# ---------------------------------------------------------------------------
ARTIFACT_MUTATIONS: dict[str, object] = {
    "artifact_unix_traversal": {"model": {"runner": _RUNNER_TYPE, "preprocessors": [{"type": "normalize", "artifact": "../../etc/passwd"}]}},
    "artifact_absolute": {"model": {"runner": _RUNNER_TYPE, "preprocessors": [{"type": "normalize", "artifact": "/etc/shadow"}]}},
    "artifact_windows_traversal": {"model": {"runner": _RUNNER_TYPE, "preprocessors": [{"type": "normalize", "artifact": "..\\..\\sensitive"}]}},
}

# ---------------------------------------------------------------------------
# TM-009 — nested init_args at escalating depths (parse-layer probe)
# ---------------------------------------------------------------------------
NESTED_MUTATIONS: dict[str, object] = {
    f"nested_depth_{d:03d}": {"model": {"runner": _nested_runner(d)}}
    for d in [1, 2, 5, 10, 20, 50]
}

# ---------------------------------------------------------------------------
# General schema edge cases (type mismatches, boundary values, extras)
# ---------------------------------------------------------------------------
EDGE_CASE_MUTATIONS: dict[str, object] = {
    "empty_object": {},
    "null_policy": {"policy": None},
    "null_runner": {"model": {"runner": None}},
    "integer_as_policy_name": {"policy": {"name": 42}},
    "array_as_runner": {"model": {"runner": []}},
    "boolean_as_runner": {"model": {"runner": True}},
    "very_large_n_obs_steps": {"model": {"n_obs_steps": 2**31 - 1, "runner": _RUNNER_TYPE}},
    "negative_n_obs_steps": {"model": {"n_obs_steps": -1, "runner": _RUNNER_TYPE}},
    "zero_n_obs_steps": {"model": {"n_obs_steps": 0, "runner": _RUNNER_TYPE}},
    "many_preprocessors": {
        "model": {
            "runner": _RUNNER_TYPE,
            "preprocessors": [{"type": "normalize"}] * 100,
        }
    },
    "extra_top_level_keys": {
        "policy": {"name": "act"},
        "model": {"runner": _RUNNER_TYPE},
        "unknown_key": "value",
        "deeply_nested_extra": {"a": {"b": {"c": True}}},
    },
    "wrong_version": {"format": "policy_package", "version": "99.99", "model": {"runner": _RUNNER_TYPE}},
    "wrong_format": {"format": "unknown_format", "version": "1.0", "model": {"runner": _RUNNER_TYPE}},
    "tensor_shape_zero_dim": {
        "hardware": {"robots": [{"name": "r", "state": {"shape": [0], "dtype": "float32"}}]},
        "model": {"runner": _RUNNER_TYPE},
    },
    "tensor_shape_negative": {
        "hardware": {"robots": [{"name": "r", "state": {"shape": [-1, 6], "dtype": "float32"}}]},
        "model": {"runner": _RUNNER_TYPE},
    },
    "camera_shape_wrong_dims": {
        "hardware": {"cameras": [{"name": "top", "shape": [640, 480]}]},
        "model": {"runner": _RUNNER_TYPE},
    },
    "duplicate_robot_names": {
        "hardware": {
            "robots": [
                {"name": "arm", "state": {"shape": [6], "dtype": "float32"}},
                {"name": "arm", "state": {"shape": [6], "dtype": "float32"}},
            ]
        },
        "model": {"runner": _RUNNER_TYPE},
    },
    "hf_tokenizer_traversal": {
        "model": {
            "runner": _RUNNER_TYPE,
            "preprocessors": [
                {
                    "class_path": "physicalai.inference.preprocessors.HFTokenizer",
                    "init_args": {
                        "tokenizer_name": "../../../../etc/passwd",
                        "revision": "abc1234567890abc1234567890abc1234567890ab",
                    },
                }
            ],
        }
    },
}


def main() -> None:
    all_mutations: dict[str, object] = {
        **BASELINE_MUTATIONS,
        **CLASS_PATH_MUTATIONS,
        **POLICY_NAME_MUTATIONS,
        **ARTIFACT_MUTATIONS,
        **NESTED_MUTATIONS,
        **EDGE_CASE_MUTATIONS,
    }

    print(f"Writing corpus to {CORPUS_DIR}/")
    written = 0
    for name, obj in all_mutations.items():
        before = (CORPUS_DIR / f"{name}.json").exists()
        _write(name, obj)
        if not before:
            written += 1

    total = len(list(CORPUS_DIR.glob("*.json")))
    print(f"\nDone — {written} new file(s) written, {total} total in corpus.")


if __name__ == "__main__":
    main()
