# Task

You write fuzz-test seeds for a JSON parser. Each seed is one JSON object that is fed verbatim to
`Manifest.model_validate(json.loads(data))`. Good seeds are valid enough to get past the first checks and then
sit exactly on a boundary of the schema, so the fuzzer can mutate them into new code paths.

Reply with ONE JSON object `{"seeds": [<seed>, ...]}` and nothing else. Each seed is a JSON object. Keep each
seed under 2 KiB. Make every seed different from the others.

# Target (pydantic models, `physicalai.inference.manifest`)

```python
class Manifest(BaseModel):          # extra keys allowed
    format: str = "policy_package"
    version: str = "1.0"
    policy: PolicySpec = {}         # {"name": str, "source": {"repo_id": str, "class_path": str}}
    model: ModelSpec = {}
    hardware: HardwareSpec = {}
    metadata: MetadataSpec = {}     # {"created_at": str, "created_by": str}

class ModelSpec(BaseModel):
    n_obs_steps: int = 1
    runner: ComponentSpec | None = None
    artifacts: dict[str, str] = {}
    preprocessors: list[ComponentSpec] = []
    postprocessors: list[ComponentSpec] = []
    callbacks: list[ComponentSpec] = []
    input_features: list[ComponentSpec] = []
    output_features: list[ComponentSpec] = []

class ComponentSpec(BaseModel):     # extra keys allowed (flat params)
    type: str = ""
    class_path: str = ""
    init_args: dict[str, Any] = {}
    # validator: rejects the spec unless `type` or `class_path` is non-empty

class HardwareSpec(BaseModel):
    robots: list[RobotSpec] = []    # {"name": str, "type": str, "state": OrderedTensorSpec, "action": OrderedTensorSpec}
    cameras: list[CameraSpec] = []  # {"name": str, "shape": list[int], "dtype": str = "uint8"}

class TensorSpec(BaseModel):        # OrderedTensorSpec adds "order": list[str]
    shape: list[int]                # validator: every dimension must be > 0
    dtype: str = "float32"          # validator: must be non-empty

# CameraSpec.shape validator: if the list is non-empty it must have exactly 3 elements (C, H, W)
```

Invariant I-3: validation must never raise anything except a pydantic `ValidationError`. Any other exception
is a bug, so seeds that sit next to a validator are the most useful.

# Examples of valid seeds

```json
{"format": "policy_package", "version": "1.0"}
```

```json
{"format": "policy_package", "version": "1.0", "policy": {"name": "smolvla"},
 "model": {"n_obs_steps": 1, "runner": {"class_path": "physicalai.inference.runners.SinglePass", "init_args": {}},
  "preprocessors": [{"type": "resize", "image_layout": "BCHW", "image_resolution": [224, 224]}]},
 "hardware": {"robots": [{"name": "main", "state": {"shape": [6], "dtype": "float32", "order": ["a", "b"]}}],
  "cameras": [{"name": "top", "shape": [3, 480, 640], "dtype": "uint8"}]}}
```

# What to aim for

Mix valid manifests with seeds that are wrong by exactly one thing:

- `n_obs_steps` at 0, -1, 1, 2, 2^31-1, 2^63-1, 2^63, a float such as 1.0, and a string.
- Tensor and camera shapes with 0, -1, or a huge dimension (2^31, 2^63); empty shapes; camera shapes with 2, 3,
  and 4 elements.
- Components with only `type`, only `class_path`, both, neither, `init_args` that is a list or null, and extra
  flat keys.
- Empty-string and very long strings for `dtype`, `name`, `type`, `class_path`.
- `null`, wrong container types, and extra unknown keys at every level.
- Nested `init_args` 5, 10, and 50 levels deep.
- Unicode in keys and values (accents, emoji, `\u0000`).

Return a mix of about half valid-looking seeds and half boundary seeds.
