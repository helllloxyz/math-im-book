#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from math_im_book.services.provider_probe import (
    ProbeStatus,
    build_credential_record,
    build_probe_http_client,
    build_profile_from_credentials,
    run_provider_probe,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe a configured provider credential with a minimal request."
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        default=Path("data/credentials/credentials.json"),
        help="Path to credentials.json",
    )
    parser.add_argument(
        "--credential-id",
        default=None,
        help="Credential ID to test. Defaults to the first Gemini credential.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the model used for the probe request.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Request timeout in seconds.",
    )
    parser.add_argument(
        "--ipv4-only",
        action="store_true",
        help="Force the probe request to use IPv4 only.",
    )
    parser.add_argument(
        "--no-env-proxy",
        action="store_true",
        help="Disable HTTP_PROXY/HTTPS_PROXY for the probe request.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        profile = build_profile_from_credentials(
            credentials_path=args.credentials,
            credential_id=args.credential_id,
            model=args.model,
        )
        credential = build_credential_record(
            credentials_path=args.credentials,
            credential_id=profile.credential_id,
        )
    except (OSError, ValueError) as exc:
        print(f"probe status: {ProbeStatus.CONFIG_ERROR.value}")
        print(f"message: {exc}")
        return 2

    http_client = build_probe_http_client(
        timeout_seconds=args.timeout,
        ipv4_only=args.ipv4_only,
        trust_env=not args.no_env_proxy,
    )
    try:
        result = run_provider_probe(
            profile=profile,
            credential=credential,
            timeout_seconds=args.timeout,
            http_client=http_client,
        )
    finally:
        http_client.close()
    print(f"probe status: {result.status.value}")
    print(f"provider: {result.provider_name}")
    print(f"credential_id: {result.credential_id}")
    print(f"model: {result.model}")
    print(f"message: {result.message}")
    if result.output_preview:
        print(f"output preview: {result.output_preview}")

    if result.status is ProbeStatus.OK:
        return 0
    if result.status is ProbeStatus.TIMEOUT:
        return 3
    if result.status is ProbeStatus.AUTH_ERROR:
        return 4
    if result.status is ProbeStatus.UPSTREAM_ERROR:
        return 5
    return 2


if __name__ == "__main__":
    sys.exit(main())
