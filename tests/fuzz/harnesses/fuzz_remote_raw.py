# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Fuzz the remote inference protocol decoders on verbatim MessagePack bytes (no ``FuzzedDataProvider``).

Unlike ``fuzz_remote_protocol`` and ``fuzz_remote_images``, the input is the wire payload itself, so a
seed file is a MessagePack message and mutation edits it directly. The same bytes go through the
message, predict-request (including images), and predict-reply decoders with production default limits.
"""

from __future__ import annotations

import sys

import atheris

with atheris.instrument_imports():
    from physicalai.inference.remote._protocol import (
        RemoteInferenceProtocolError,
        decode_message,
        decode_predict_reply,
        decode_predict_request,
    )

# Decoders document RemoteInferenceProtocolError for every rejection (see fuzz_remote_protocol);
# any other exception is a finding -- do not widen this tuple to `Exception`.
_EXPECTED_DECODE_EXCEPTIONS = (RemoteInferenceProtocolError,)


def test_one_input(data: bytes) -> None:
    try:
        decode_message(data)
    except _EXPECTED_DECODE_EXCEPTIONS:
        pass
    try:
        decode_predict_request(data)
    except _EXPECTED_DECODE_EXCEPTIONS:
        pass
    try:
        decode_predict_reply(data)
    except _EXPECTED_DECODE_EXCEPTIONS:
        pass


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
