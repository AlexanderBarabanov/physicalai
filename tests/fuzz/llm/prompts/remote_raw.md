# Task

You write fuzz-test seeds for a binary protocol decoder. Each seed is a JSON object. A converter turns it into
MessagePack bytes, and the fuzzer then feeds those bytes to `decode_message`, `decode_predict_request`, and
`decode_predict_reply`. Good seeds pass the first checks (version, keys, types) and then sit exactly on a
boundary of the deeper checks, so the fuzzer can mutate them into new code paths.

Reply with ONE JSON object `{"seeds": [<seed>, ...]}` and nothing else. Each seed is a JSON object. Keep each
seed under 2 KiB. Make every seed different from the others.

# JSON to MessagePack rules

- Every JSON value maps to the same MessagePack value, except for one special form.
- `{"$bytes": "<base64>"}` becomes MessagePack binary data (`bytes`). Use it for array data and image data.
  Base64 must be valid (standard alphabet, with `=` padding).
- Do not put any other key next to `"$bytes"`.

# Wire format

A tagged NumPy array is a map: `{"__np__": true, "dtype": "float32", "shape": [2], "data": {"$bytes": "..."}}`.
Rules: `dtype` must be numeric or bool (`float32`, `float64`, `int8`, `int16`, `int32`, `int64`, `uint8`,
`uint16`, `bool`, `complex64`); `shape` is a list of non-negative ints; the decoded length of `data` must equal
`product(shape) * itemsize` exactly (an empty shape `[]` is a 0-d array with `itemsize` bytes). For example,
`float32` `[0.0, 1.0]` is 8 bytes: `{"$bytes": "AAAAAAAAgD8="}`. All arrays together may not exceed the byte
budget (`max_bytes`, 32 MiB = 33554432). Containers (maps and lists) nested deeper than 64 levels are rejected.

Predict request, keys must be exactly these five:

```json
{"protocol_version": 1, "seq": 0, "budget_ms": 1000, "inputs": {}, "images": {}}
```

- `protocol_version` must be the integer 1 (not a bool, float, or string). `seq` is an integer >= 0.
  `budget_ms` is an integer from 1 to 60000.
- `inputs` maps a string name to a tagged array or a list of strings. Names starting with `images` are not
  allowed here.
- `images` maps `"images"` or `"images.<name>"` to an image entry
  `{"codec": "raw" | "jpeg", "shape": [H, W, 3] or [1, H, W, 3], "dtype": "uint8", "data": {"$bytes": "..."}}`.
  Every shape dimension must be a positive int, the last one must be 3, and a 4-D shape must start with 1.
  For `raw`, the data length must equal `H*W*3`. For `jpeg`, the data must start with the bytes `FF D8`
  (base64 starts with `/9j/`), and the width and height in its frame header must match the declared shape.
  The size gate runs before decoding: if `H*W*3` plus the bytes already used exceeds 33554432, the request is
  rejected without reading the data. For example `[5461, 2048, 3]` is 33552384 bytes (just under) and
  `[5462, 2048, 3]` is 33558528 bytes (just over).

Predict reply, keys must be exactly these seven:

```json
{"protocol_version": 1, "seq": 3, "server_id": "server", "outputs": {"action": <tagged array>},
 "server_queue_s": 0.0, "server_compute_s": 0.01, "server_decode_s": 0.0}
```

- `server_id` is a non-empty string. `outputs` maps strings to tagged arrays only. The three timing values are
  finite numbers >= 0 (int or float).

Invariants: I-22, the decoders may raise only `RemoteInferenceProtocolError` for any input. I-24, image
decoding must validate shape and size before it allocates anything.

# Examples of valid seeds

Minimal request:

```json
{"protocol_version": 1, "seq": 0, "budget_ms": 1000, "inputs": {}, "images": {}}
```

Request with one array input:

```json
{"protocol_version": 1, "seq": 1, "budget_ms": 1000,
 "inputs": {"state": {"__np__": true, "dtype": "float32", "shape": [2], "data": {"$bytes": "AAAAAAAAgD8="}}},
 "images": {}}
```

Valid reply:

```json
{"protocol_version": 1, "seq": 3, "server_id": "server",
 "outputs": {"action": {"__np__": true, "dtype": "float32", "shape": [1, 2], "data": {"$bytes": "AAAAAAAAgD8="}}},
 "server_queue_s": 0.0, "server_compute_s": 0.01, "server_decode_s": 0.0}
```

A raw image entry of 1x2 pixels (6 bytes): `{"codec": "raw", "shape": [1, 2, 3], "dtype": "uint8", "data": {"$bytes": "AAECAwQF"}}`.

# What to aim for

Mix valid messages with ones that are wrong by exactly one thing. Mostly write requests and replies, and a few
plain maps for the generic decoder.

- `protocol_version`: 0, 2, -1, 1.0, "1", true. `seq`: -1, 0, 2^31-1, 2^63, 2^64. `budget_ms`: 0, 1, 60000, 60001.
- Missing, extra, or renamed keys; `inputs` or `images` that are a list, null, or a string.
- 0-d arrays; zero-size arrays (`shape` with a 0); `data` one byte too short or too long; `shape` with a huge
  dimension and tiny data; negative or non-int shape entries; dtype `"O"`, `"U4"`, `""`, `"float16"`.
- Image shapes just under and just over the 33554432-byte budget; 4-D shapes starting with 2; 2 or 5 dimensions;
  last dimension 1 or 4; `dtype` other than `"uint8"`; unknown codec; `jpeg` data that is empty, one byte,
  starts with `/9j/` but is cut off, or declares a different size than the shape.
- Image names: `"images"`, `"images.front"`, `"image.front"`, `"state"`.
- Nesting: build values nested 62, 63, 64, 65, and 66 levels deep (for example inside `inputs` as lists of
  lists).
- Timings: 0, 0.5, -1, 1e308, a string, true. Empty `server_id`.
- Strings and names with Unicode, empty strings, and very long keys.
