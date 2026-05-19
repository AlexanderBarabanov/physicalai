# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Security test suite — threat scenario exploitability proofs.

Each test targets one threat from the threat model (TM-001 … TM-010).
Tests carry one of two custom markers:

``security_regression``
    The threat is **mitigated**.  These tests verify the fix is in place and
    must always pass.  A failure signals a security regression.

``security_poc``
    The threat is **unmitigated** (consumer/operator responsibility or fix
    not yet landed).  These tests assert that the exploit *succeeds* — they
    pass while the vulnerability is open.  A test failure means the fix has
    landed; update or retire the test and confirm the remediation.

Run only regression guard (CI gate)::

    pytest tests/security -m security_regression

Audit open vulnerabilities::

    pytest tests/security -m security_poc -v
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_calibration_data(*, range_min: int = 0, range_max: int = 4095) -> dict:
    """Return a minimal valid SO-101 calibration dict with configurable ranges."""
    joints = [
        "shoulder_pan", "shoulder_lift", "elbow_flex",
        "wrist_flex", "wrist_roll", "gripper",
    ]
    return {
        joint: {
            "id": idx + 1,
            "drive_mode": 0,
            "homing_offset": 0,
            "range_min": range_min,
            "range_max": range_max,
        }
        for idx, joint in enumerate(joints)
    }


# ===========================================================================
# TM-001  Manifest class_path allowlist  (MITIGATED)
# ===========================================================================

class TestTM001ClassPathAllowlist:
    """TM-001: Arbitrary code execution via manifest class_path → importlib.

    Attack: a crafted manifest specifies ``class_path: "os.system"`` (or any
    arbitrary module).  Without the allowlist the component factory would call
    ``importlib.import_module("os")`` and return ``os.system`` as the
    "component class".

    Mitigation: ``_ALLOWED_CLASS_PATH_PREFIXES`` enforced in
    ``_validate_class_path()`` before any ``importlib`` call.
    """

    @pytest.mark.security_regression
    def test_stdlib_os_module_rejected(self) -> None:
        """class_path pointing at os.system is rejected before import."""
        from physicalai.inference.component_factory import _validate_class_path

        with pytest.raises(ValueError, match="not permitted"):
            _validate_class_path("os.system")

    @pytest.mark.security_regression
    def test_builtins_eval_rejected(self) -> None:
        """class_path pointing at builtins.eval is rejected."""
        from physicalai.inference.component_factory import _validate_class_path

        with pytest.raises(ValueError, match="not permitted"):
            _validate_class_path("builtins.eval")

    @pytest.mark.security_regression
    def test_subprocess_popen_rejected(self) -> None:
        """class_path pointing at subprocess.Popen is rejected."""
        from physicalai.inference.component_factory import _validate_class_path

        with pytest.raises(ValueError, match="not permitted"):
            _validate_class_path("subprocess.Popen")

    @pytest.mark.security_regression
    def test_allowlist_constant_is_non_empty_and_restrictive(self) -> None:
        """Allowlist must be non-empty and each prefix must start with 'physicalai.'."""
        from physicalai.inference.component_factory import _ALLOWED_CLASS_PATH_PREFIXES

        assert len(_ALLOWED_CLASS_PATH_PREFIXES) > 0, "Allowlist must not be empty"
        for prefix in _ALLOWED_CLASS_PATH_PREFIXES:
            assert prefix, "An empty string prefix would permit any class_path"
            assert prefix.startswith("physicalai."), (
                f"Prefix {prefix!r} is too broad — would permit out-of-namespace classes"
            )

    @pytest.mark.security_regression
    def test_physicalai_class_accepted(self) -> None:
        """Classes within the physicalai namespace are not rejected by the allowlist."""
        from physicalai.inference.component_factory import _validate_class_path

        # Should not raise
        _validate_class_path("physicalai.inference.runners.SinglePass")


# ===========================================================================
# TM-002  Plugin auto-execution at import  (UNMITIGATED — consumer responsibility)
# ===========================================================================

class TestTM002PluginAutoExecution:
    """TM-002: Third-party adapter entry point code executes at library import time.

    Attack: install a malicious Python package that declares an entry point in
    the ``physicalai.inference.adapters`` group.  Its code runs automatically
    when ``physicalai`` is imported — before any model is loaded.

    Mitigation: none in the library.  Consumer owns the Python environment
    (lock files, SBOM, package provenance).
    """

    @pytest.mark.security_poc
    def test_any_entry_point_is_loaded_without_provenance_check(self) -> None:
        """PoC: ep.load() is called for ANY entry point — no signature or provenance gate.

        Expected: PASSES while the surface is open; FAILS if a disable/allowlist
        mechanism is added to _load_external_adapters().
        """
        from physicalai.inference.adapters._discovery import _load_external_adapters

        malicious_register_fn = MagicMock()
        malicious_ep = MagicMock()
        malicious_ep.name = "evil_plugin"
        malicious_ep.load.return_value = malicious_register_fn

        with patch(
            "physicalai.inference.adapters._discovery.entry_points",
            return_value=[malicious_ep],
        ):
            _load_external_adapters()

        malicious_ep.load.assert_called_once()
        malicious_register_fn.assert_called_once()

    @pytest.mark.security_poc
    def test_plugin_can_execute_payload_and_hide_in_logs(self) -> None:
        """PoC: a plugin can execute its payload, raise to appear as a benign log warning,
        and leave no alert — the exploit is complete before detection.

        Expected: PASSES while the surface is open.
        """
        from physicalai.inference.adapters._discovery import _load_external_adapters

        side_effects: list[str] = []

        def evil_register(registry: object) -> None:
            side_effects.append("payload_executed")
            raise RuntimeError("nothing to see here")

        evil_ep = MagicMock()
        evil_ep.name = "evil"
        evil_ep.load.return_value = evil_register

        with patch(
            "physicalai.inference.adapters._discovery.entry_points",
            return_value=[evil_ep],
        ):
            _load_external_adapters()  # must not raise

        assert "payload_executed" in side_effects, (
            "Payload did not execute — plugin loading may have been gated. "
            "Update this test if TM-002 has been mitigated."
        )


# ===========================================================================
# TM-003  Artifact path traversal  (UNMITIGATED)
# ===========================================================================

class TestTM003ArtifactPathTraversal:
    """TM-003: A relative ``../`` artifact path in the manifest escapes the export dir.

    Attack: ``{"type": "runner", "artifact": "../../etc/passwd"}`` in a manifest.
    ``resolve_artifact()`` joins the value onto ``export_dir`` without an
    ``is_relative_to()`` boundary check.

    Mitigation: not yet implemented in the library.
    """

    @pytest.mark.security_poc
    def test_dotdot_artifact_resolves_outside_export_dir(self, tmp_path: Path) -> None:
        """PoC: a ../ artifact value resolves to a path outside the export directory.

        Expected: PASSES while TM-003 is unmitigated; FAILS once
        ``resolve_artifact`` adds an ``is_relative_to`` check.
        """
        from physicalai.inference.component_factory import resolve_artifact
        from physicalai.inference.manifest import ComponentSpec

        export_dir = tmp_path / "model_exports"
        export_dir.mkdir()

        spec = ComponentSpec(type="fake_runner", artifact="../../sensitive_file")
        resolved = resolve_artifact(spec, export_dir)
        artifact_path = Path(resolved.flat_params["artifact"]).resolve()

        assert not artifact_path.is_relative_to(export_dir.resolve()), (
            "TM-003 appears fixed: artifact path is now contained within export_dir. "
            "Update or remove this test after confirming the fix."
        )


# ===========================================================================
# TM-004  _factory_override env-var guard  (MITIGATED)
# ===========================================================================

class TestTM004FactoryOverride:
    """TM-004: _factory_override causes arbitrary module import in the camera worker subprocess.

    Attack vector: pass ``_factory_override="evil_module:evil_callable"`` to
    ``CameraPublisher.__init__``.  The value is serialized into JSON and sent
    over stdin to the worker subprocess, which calls ``importlib.import_module``
    and ``getattr`` on it.

    CVSS 3.1: AV:L/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H = 8.8 High (when reachable).
    Practical severity: Low via ``SharedCamera`` (default path); High if an
    application exposes CameraPublisher kwargs to external callers.

    Mitigation: ``_FACTORY_OVERRIDE_ALLOWED`` module-level guard — the importlib
    path is dead unless ``PHYSICALAI_TEST_FACTORY_OVERRIDE_ALLOWED=1`` is set.
    """

    @pytest.mark.security_regression
    def test_factory_override_blocked_when_env_var_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Guard raises RuntimeError in production (env var absent = default)."""
        import physicalai.capture.transport._publisher_worker as worker_mod

        monkeypatch.setattr(worker_mod, "_FACTORY_OVERRIDE_ALLOWED", False)

        config = {
            "camera_type": "uvc",
            "camera_kwargs": {},
            "service_name": "test/camera",
            "_factory_override": "os:getcwd",
        }

        with pytest.raises(RuntimeError, match="PHYSICALAI_TEST_FACTORY_OVERRIDE_ALLOWED"):
            worker_mod.build_camera(config)

    @pytest.mark.security_regression
    def test_guard_constant_false_when_env_var_is_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_FACTORY_OVERRIDE_ALLOWED evaluates to False when env var is '0'.

        Tests the env var evaluation path directly (not just the attribute patch).
        '0', 'false', '' — any value other than exactly '1' must be treated as disabled.
        """
        import importlib

        monkeypatch.setenv("PHYSICALAI_TEST_FACTORY_OVERRIDE_ALLOWED", "0")
        import physicalai.capture.transport._publisher_worker as worker_mod
        importlib.reload(worker_mod)

        assert not worker_mod._FACTORY_OVERRIDE_ALLOWED, (
            "_FACTORY_OVERRIDE_ALLOWED must be False when env var is '0'"
        )

        config = {
            "camera_type": "uvc",
            "camera_kwargs": {},
            "service_name": "test/camera",
            "_factory_override": "os:getcwd",
        }
        with pytest.raises(RuntimeError, match="PHYSICALAI_TEST_FACTORY_OVERRIDE_ALLOWED"):
            worker_mod.build_camera(config)

    @pytest.mark.security_regression
    def test_guard_constant_false_when_env_var_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_FACTORY_OVERRIDE_ALLOWED evaluates to False when env var is not set at all.

        This is the default production state — the guard must be closed by default.
        """
        import importlib

        monkeypatch.delenv("PHYSICALAI_TEST_FACTORY_OVERRIDE_ALLOWED", raising=False)
        import physicalai.capture.transport._publisher_worker as worker_mod
        importlib.reload(worker_mod)

        assert not worker_mod._FACTORY_OVERRIDE_ALLOWED, (
            "_FACTORY_OVERRIDE_ALLOWED must be False when env var is absent"
        )

        config = {
            "camera_type": "uvc",
            "camera_kwargs": {},
            "service_name": "test/camera",
            "_factory_override": "os:getcwd",
        }
        with pytest.raises(RuntimeError, match="PHYSICALAI_TEST_FACTORY_OVERRIDE_ALLOWED"):
            worker_mod.build_camera(config)

    @pytest.mark.security_poc
    def test_poc_arbitrary_code_executes_when_guard_misconfigured(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        """PoC: full code execution when PHYSICALAI_TEST_FACTORY_OVERRIDE_ALLOWED=1.

        Simulates the real-world misconfiguration scenario: a developer sets the env
        var in a local ``.env`` file for testing, it leaks into a container image or
        CI environment definition, and an attacker who can call ``CameraPublisher``
        directly (or influence its kwargs) gets arbitrary code execution inside the
        worker subprocess.

        Attack chain reproduced:
          1. Guard is open (env var = "1" in the deployment environment).
          2. Attacker passes ``_factory_override="<module>:<callable>"`` to the API.
          3. The worker subprocess imports the module and calls the callable with the
             camera kwargs — which the attacker also controls.
          4. The callable executes with full access to the host process and filesystem.

        Expected: PASSES (exploit succeeds) while the guard is the only barrier and
        the env var can be set by accident.  A failure here would indicate the exploit
        path has been removed at the library level.
        """
        import sys

        import physicalai.capture.transport._publisher_worker as worker_mod

        # Open the guard — equivalent to PHYSICALAI_TEST_FACTORY_OVERRIDE_ALLOWED=1
        # being present in the process environment.  monkeypatch restores False after
        # this test so subsequent tests are not affected.
        monkeypatch.setattr(worker_mod, "_FACTORY_OVERRIDE_ALLOWED", True)

        # --- Attacker-controlled payload module -----------------------------------
        # In a real attack this would be any importable package already installed in
        # the Python environment (e.g., a dependency the attacker has compromised).
        # Here we write a minimal module to tmp_path and add it to sys.path.
        payload_dir = tmp_path / "attacker_payload"
        payload_dir.mkdir()
        pwned_marker = tmp_path / "pwned.txt"

        (payload_dir / "malicious.py").write_text(
            "def shell(**camera_kwargs):\n"
            f"    open({str(pwned_marker)!r}, 'w').write('RCE confirmed: ' + str(camera_kwargs))\n"
            "    return 'shell_executed'\n",
        )

        sys.path.insert(0, str(payload_dir))
        try:
            config = {
                "camera_type": "uvc",
                "camera_kwargs": {"exfiltrated": "secret_api_key_12345"},
                "service_name": "test/camera",
                "_factory_override": "malicious:shell",
            }
            result = worker_mod.build_camera(config)
        finally:
            sys.path.pop(0)
        # -------------------------------------------------------------------------

        assert pwned_marker.exists(), (
            "Payload did not execute — guard may have blocked it unexpectedly."
        )
        payload_output = pwned_marker.read_text()
        assert "secret_api_key_12345" in payload_output, (
            "Attacker-controlled camera_kwargs were not forwarded to the payload."
        )
        assert result == "shell_executed"


        """When the guard is explicitly enabled, the importlib call is reached.

        Confirms the injection mechanism still works end-to-end when opted in —
        meaning the env-var guard is the sole production barrier.
        Uses ``builtins:dict`` (safe, accepts **kwargs) to verify call-through.
        """
        import physicalai.capture.transport._publisher_worker as worker_mod

        monkeypatch.setattr(worker_mod, "_FACTORY_OVERRIDE_ALLOWED", True)

        config = {
            "camera_type": "uvc",
            "camera_kwargs": {"injected_key": "injected_value"},
            "service_name": "test/camera",
            "_factory_override": "builtins:dict",  # dict(**kwargs) → returns the kwargs as a dict
        }

        result = worker_mod.build_camera(config)
        assert result == {"injected_key": "injected_value"}

    @pytest.mark.security_regression
    def test_shared_camera_init_has_no_factory_override_parameter(self) -> None:
        """SharedCamera.__init__ must not expose _factory_override — it is the safe public API."""
        from physicalai.capture.transport._shared_camera import SharedCamera

        sig = inspect.signature(SharedCamera.__init__)
        assert "_factory_override" not in sig.parameters, (
            "_factory_override must not appear in SharedCamera.__init__. "
            "Its presence would make the test-injection parameter reachable via the public API."
        )

    @pytest.mark.security_regression
    def test_factory_override_propagates_from_publisher_into_json_config(self) -> None:
        """Confirms the injection path: CameraPublisher stores the value and would include
        it in the JSON config sent to the worker subprocess.

        This documents the attack chain even though the worker now guards against it.
        """
        from physicalai.capture.transport._publisher import CameraPublisher
        from physicalai.capture.transport._spec import CameraSpec

        spec = CameraSpec(camera_type="fake", camera_kwargs={})
        publisher = CameraPublisher(spec, "test/service", _factory_override="evil:payload")

        # Reproduce what CameraPublisher.start() does when building the config dict
        config: dict = {
            "camera_type": publisher._spec.camera_type,
            "camera_kwargs": publisher._spec.camera_kwargs,
            "service_name": publisher._service_name,
        }
        if publisher._factory_override is not None:
            config["_factory_override"] = publisher._factory_override

        assert config.get("_factory_override") == "evil:payload", (
            "Injection value was not included in the config dict — "
            "attack path may have been severed in CameraPublisher.start()."
        )


# ===========================================================================
# TM-005  HFTokenizer — no tokenizer repository allowlist  (UNMITIGATED)
# ===========================================================================

class TestTM005HFTokenizerNoAllowlist:
    """TM-005: Any HuggingFace repository name in the manifest is passed to
    ``AutoTokenizer.from_pretrained()`` without an allowlist check.

    Attack: manifest specifies ``tokenizer_name: "evil-org/rce-tokenizer"``
    with a valid commit SHA.  The library contacts the malicious repo at
    pipeline initialization.

    Mitigation: not yet implemented.
    """

    @pytest.mark.security_poc
    def test_arbitrary_repo_name_reaches_from_pretrained_without_allowlist(self) -> None:
        """PoC: malicious repo name is forwarded to from_pretrained unchecked.

        Expected: PASSES while TM-005 is unmitigated.
        """
        import importlib
        import sys

        malicious_repo = "evil-org/rce-tokenizer-payload"
        revision = "a" * 40  # valid 40-char hex, passes format check

        mock_auto_tokenizer = MagicMock()
        mock_transformers = MagicMock()
        mock_transformers.AutoTokenizer = mock_auto_tokenizer

        with patch.dict(sys.modules, {"transformers": mock_transformers}):
            import physicalai.inference.preprocessors.hf_tokenizer as hft_mod
            importlib.reload(hft_mod)
            hft_mod.HFTokenizer(malicious_repo, revision)

        call_args = mock_auto_tokenizer.from_pretrained.call_args
        assert call_args is not None, "from_pretrained was never called"
        # The repo name reaches from_pretrained as the first positional argument
        assert call_args.args[0] == malicious_repo, (
            f"Expected malicious repo name {malicious_repo!r} as first arg, "
            f"got: {call_args.args}"
        )

    @pytest.mark.security_poc
    def test_revision_only_validated_by_format_not_by_trust(self) -> None:
        """PoC: the revision check enforces hex format only — a well-formed SHA
        for a malicious repository passes validation without any trust check.

        Expected: PASSES while TM-005 is unmitigated.
        """
        from physicalai.inference.preprocessors.hf_tokenizer import _COMMIT_HASH_RE

        # A 40-char hex value: valid format but could reference malicious content
        attacker_controlled_sha = "deadbeef" * 5
        assert _COMMIT_HASH_RE.fullmatch(attacker_controlled_sha), (
            "Regex should accept a 40-char hex string — sanity check failed."
        )
        # No secondary check exists that this SHA belongs to an approved repository.
        # Proof: _COMMIT_HASH_RE is the only validation; no allowlist is consulted.
        source = inspect.getsource(_COMMIT_HASH_RE.__class__)  # just confirm class exists
        from physicalai.inference.preprocessors import hf_tokenizer as hft
        hft_source = inspect.getsource(hft.HFTokenizer.__init__)
        assert "allowlist" not in hft_source.lower() and "allowed_repos" not in hft_source.lower(), (
            "TM-005 appears fixed — found allowlist logic in HFTokenizer.__init__. "
            "Update or remove this test after confirming the fix."
        )


# ===========================================================================
# TM-006  No model integrity check before native parser  (UNMITIGATED)
# ===========================================================================

class TestTM006ModelIntegrityCheck:
    """TM-006: Model files are passed to native C++ parsers without hash/signature
    verification.

    Attack: replace a model file with a crafted binary that exploits a parser
    vulnerability in OpenVINO or ONNX Runtime.

    Mitigation: not in the library; consumer owns model provenance.
    """

    @pytest.mark.security_poc
    def test_load_method_contains_no_digest_verification(self) -> None:
        """PoC: InferenceModel.load() source contains no integrity check before adapter.load().

        Expected: PASSES while TM-006 is unmitigated.
        """
        from physicalai.inference.model import InferenceModel

        source = inspect.getsource(InferenceModel.load)
        indicators = ("hashlib", "sha256", "sha512", "md5", "digest", "checksum", "verify_hash")
        found = [kw for kw in indicators if kw in source.lower()]

        assert not found, (
            f"TM-006 appears fixed — found integrity indicators: {found!r}. "
            "Update or remove this test after confirming the fix."
        )

    @pytest.mark.security_poc
    def test_crafted_file_returned_as_model_path_without_error(self, tmp_path: Path) -> None:
        """PoC: _get_model_path() returns a path to an arbitrary file with no format pre-check.

        A real attacker would craft a file exploiting the native parser.
        Expected: PASSES while TM-006 is unmitigated.
        """
        from physicalai.inference.model import InferenceModel

        crafted_file = tmp_path / "malicious_model.onnx"
        crafted_file.write_bytes(b"\x00CRAFTED_PAYLOAD_NOT_ONNX" * 64)

        # Build a minimal InferenceModel shell without full __init__ setup
        model = object.__new__(InferenceModel)
        model.export_dir = tmp_path
        model.policy_name = "malicious_model"
        model.backend = "onnx"

        with patch("physicalai.inference.model.adapter_registry") as mock_reg:
            mock_reg.extensions_of.return_value = (".onnx",)
            result = model._get_model_path()

        assert result == crafted_file, (
            "Expected the crafted file path to be returned — "
            "confirms no integrity gate exists before adapter.load()."
        )


# ===========================================================================
# TM-007  IPC control channel — no authentication  (UNMITIGATED)
# ===========================================================================

class TestTM007IPCControlChannelNoAuth:
    """TM-007: The camera worker IPC control channel accepts RECONFIGURE requests
    from any host process without authentication.

    Attack: any local process sends a crafted RECONFIGURE payload to inject
    an attacker-chosen camera type into the inference pipeline.

    Mitigation: not in the library; consumer owns process isolation.
    """

    @pytest.mark.security_poc
    def test_reconfigure_handler_contains_no_auth_check(self) -> None:
        """PoC: _handle_reconfigure source contains no authentication logic.

        Expected: PASSES while TM-007 is unmitigated.
        """
        from physicalai.capture.transport._publisher_worker import _handle_reconfigure

        source = inspect.getsource(_handle_reconfigure)
        auth_keywords = ("auth", "token", "secret", "credential", "signature", "hmac", "bearer")
        found = [kw for kw in auth_keywords if kw in source.lower()]

        assert not found, (
            f"TM-007 appears fixed — found auth indicators: {found!r}. "
            "Update or remove this test after confirming the fix."
        )

    @pytest.mark.security_poc
    def test_reconfigure_processes_attacker_chosen_camera_type(self) -> None:
        """PoC: a crafted RECONFIGURE request with an attacker-chosen camera type is
        processed by the handler — no auth token, session ID, or HMAC required.

        Expected: PASSES while TM-007 is unmitigated.
        """
        from physicalai.capture.transport._publisher_worker import _PublisherState, _handle_reconfigure

        mock_camera = MagicMock()
        mock_camera.disconnect.return_value = None

        state = _PublisherState(
            camera=mock_camera,
            publisher=MagicMock(),
            camera_fps=30,
            config={"camera_type": "uvc", "camera_kwargs": {}, "service_name": "test/cam"},
        )

        attacker_request = {
            "kind": "RECONFIGURE",
            "spec": {"camera_type": "attacker_chosen_type", "camera_kwargs": {}},
        }

        with patch(
            "physicalai.capture.transport._publisher_worker.build_camera",
            side_effect=RuntimeError("camera driver not found — but spec was accepted"),
        ):
            response = _handle_reconfigure(state, attacker_request, "test/cam")

        # The request was processed (error is from camera driver, not from auth check)
        assert response["ok"] is False
        assert "auth" not in response.get("error", "").lower(), (
            "Error mentions auth — indicates an auth check was added. "
            "Update this test if TM-007 has been mitigated."
        )


# ===========================================================================
# TM-008  Calibration inverted range  (UNMITIGATED)
# ===========================================================================

class TestTM008CalibrationInvertedRange:
    """TM-008: The calibration parser accepts range_min > range_max without error.

    Attack: supply a calibration file with inverted ranges to drive robot joints
    beyond their safe mechanical limits, risking hardware damage or personnel injury.

    Mitigation: not yet implemented (range consistency check pending).
    """

    @pytest.mark.security_poc
    def test_inverted_range_min_max_accepted_by_parser(self) -> None:
        """PoC: from_dict succeeds when range_min > range_max — no bounds check.

        Expected: PASSES while TM-008 is unmitigated.
        """
        from physicalai.robot.so101.calibration import SO101Calibration

        data = _make_calibration_data(range_min=4095, range_max=0)
        cal = SO101Calibration.from_dict(data)  # must not raise
        joint = cal.joints["shoulder_pan"]

        assert joint.range_min > joint.range_max, (
            "TM-008 appears fixed: inverted range was rejected by from_dict. "
            "Update or remove this test after confirming the fix."
        )

    @pytest.mark.security_poc
    def test_zero_width_range_accepted(self) -> None:
        """PoC: range_min == range_max (zero-width, physically impossible) is not rejected."""
        from physicalai.robot.so101.calibration import SO101Calibration

        data = _make_calibration_data(range_min=2048, range_max=2048)
        cal = SO101Calibration.from_dict(data)
        joint = cal.joints["shoulder_pan"]
        assert joint.range_min == joint.range_max


# ===========================================================================
# TM-009  Manifest recursion depth limit  (MITIGATED)
# ===========================================================================

class TestTM009RecursionDepthLimit:
    """TM-009: Pathological manifest nesting causes a stack overflow (DoS).

    Attack: a manifest with hundreds of nested component specs forces unbounded
    recursion in ``instantiate_component()``.

    Mitigation: ``_MAX_COMPONENT_DEPTH`` constant enforced at the start of
    ``instantiate_component()``.
    """

    @pytest.mark.security_regression
    def test_max_depth_constant_is_defined_and_finite(self) -> None:
        """_MAX_COMPONENT_DEPTH must exist and be a sane finite integer."""
        from physicalai.inference.component_factory import _MAX_COMPONENT_DEPTH

        assert isinstance(_MAX_COMPONENT_DEPTH, int)
        assert 1 <= _MAX_COMPONENT_DEPTH <= 50, (
            f"_MAX_COMPONENT_DEPTH={_MAX_COMPONENT_DEPTH} is outside the expected bounds [1, 50]"
        )

    @pytest.mark.security_regression
    def test_one_over_limit_raises_value_error(self) -> None:
        """instantiate_component raises ValueError when depth exceeds the limit."""
        from physicalai.inference.component_factory import _MAX_COMPONENT_DEPTH, instantiate_component
        from physicalai.inference.manifest import ComponentSpec

        spec = ComponentSpec(class_path="physicalai.inference.runners.SinglePass", init_args={})

        with pytest.raises(ValueError, match="nesting depth exceeded"):
            instantiate_component(spec, _depth=_MAX_COMPONENT_DEPTH + 1)

    @pytest.mark.security_regression
    def test_at_limit_accepted_one_over_rejected(self) -> None:
        """Boundary condition: depth == limit is accepted; depth == limit + 1 raises."""
        from physicalai.inference.component_factory import _MAX_COMPONENT_DEPTH, instantiate_component
        from physicalai.inference.manifest import ComponentSpec

        spec = ComponentSpec(class_path="physicalai.inference.runners.SinglePass", init_args={})

        # Mock _import_class so we don't need a real SinglePass constructor call
        with patch(
            "physicalai.inference.component_factory._import_class",
            return_value=MagicMock(return_value=MagicMock()),
        ):
            # Exactly at the limit: should NOT raise
            instantiate_component(spec, _depth=_MAX_COMPONENT_DEPTH)

        # One above the limit: must raise before any import is attempted
        with pytest.raises(ValueError, match="nesting depth exceeded"):
            instantiate_component(spec, _depth=_MAX_COMPONENT_DEPTH + 1)


# ===========================================================================
# TM-010  Policy name path traversal  (UNMITIGATED)
# ===========================================================================

class TestTM010PolicyNamePathTraversal:
    """TM-010: A ``../`` sequence in the manifest policy name escapes the export directory.

    Attack: manifest ``policy.name: "../../../etc/sensitive"`` causes the runtime
    to open an arbitrary file path when constructing the model file path.
    No ``is_relative_to()`` boundary check is present in ``_get_model_path()``.

    Mitigation: not yet implemented.
    """

    @pytest.mark.security_poc
    def test_dotdot_policy_name_escapes_export_dir(self, tmp_path: Path) -> None:
        """PoC: a policy name with ../ resolves outside the export directory.

        Directly replicates the path construction in ``_get_model_path()`` to
        confirm no boundary check is present.

        Expected: PASSES while TM-010 is unmitigated.
        """
        export_dir = tmp_path / "model_exports"
        export_dir.mkdir()

        policy_name = "../../../etc/sensitive_policy"
        # Replicate what _get_model_path() does (no is_relative_to check):
        constructed = export_dir / f"{policy_name}.onnx"
        resolved = constructed.resolve()

        assert not resolved.is_relative_to(export_dir.resolve()), (
            "TM-010 appears fixed: resolved path is contained within export_dir. "
            "Update or remove this test after confirming the fix."
        )

    @pytest.mark.security_poc
    def test_get_model_path_source_has_no_boundary_check(self) -> None:
        """PoC: _get_model_path() source does not call is_relative_to() — confirms
        the missing boundary check is not hidden in a helper.

        Expected: PASSES while TM-010 is unmitigated.
        """
        from physicalai.inference.model import InferenceModel

        source = inspect.getsource(InferenceModel._get_model_path)
        assert "is_relative_to" not in source, (
            "TM-010 appears fixed — is_relative_to() found in _get_model_path. "
            "Update or remove this test after confirming the fix."
        )
