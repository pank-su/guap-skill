#!/usr/bin/env python3
"""Run the GUAP credential relay through an approved reverse SSH endpoint."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

try:
    from relay_validation import validate_port, validate_public_url, validate_ssh_part
except ImportError:  # pragma: no cover - supports package and file-style imports
    try:
        from .relay_validation import validate_port, validate_public_url, validate_ssh_part
    except ImportError:  # pragma: no cover - tests load this script by path
        import importlib.util

        _validation_spec = importlib.util.spec_from_file_location(
            "guap_relay_validation", Path(__file__).with_name("relay_validation.py")
        )
        if _validation_spec is None or _validation_spec.loader is None:
            raise
        _validation_module = importlib.util.module_from_spec(_validation_spec)
        _validation_spec.loader.exec_module(_validation_module)
        validate_port = _validation_module.validate_port
        validate_public_url = _validation_module.validate_public_url
        validate_ssh_part = _validation_module.validate_ssh_part


def build_ssh_command(
    *,
    ssh_binary: str,
    host: str,
    user: str,
    key: Path,
    remote_port: int,
    local_port: int,
    control_path: Path,
) -> list[str]:
    """Build a shell-free reverse-forward command bound to server loopback."""
    validate_ssh_part(host, "host")
    validate_ssh_part(user, "user")
    validate_port(remote_port, "remote_port")
    validate_port(local_port, "local_port")
    return [
        ssh_binary,
        "-N",
        "-T",
        "-o",
        "ControlMaster=yes",
        "-o",
        f"ControlPath={control_path}",
        "-i",
        str(key),
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "BatchMode=yes",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=3",
        "-R",
        f"127.0.0.1:{remote_port}:127.0.0.1:{local_port}",
        f"{user}@{host}",
    ]


def _read_stderr_tail(stream: object, limit: int = 8192) -> str:
    """Read only a bounded tail from the non-piped SSH stderr file."""
    try:
        stream.seek(0, 2)  # type: ignore[attr-defined]
        size = stream.tell()  # type: ignore[attr-defined]
        stream.seek(max(0, size - limit))  # type: ignore[attr-defined]
        data = stream.read(limit)  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace").strip()
    return str(data).strip()


def run_with_tunnel(
    command: list[str],
    serve: Callable[[threading.Event], int],
    *,
    control_path: Path,
    readiness_timeout: float = 10,
    check_interval: float = 0.1,
    monitor_interval: float = 0.1,
) -> int:
    """Run a relay callback after the SSH control master reports ready."""
    with tempfile.TemporaryFile(mode="w+b") as ssh_stderr:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=ssh_stderr)
        try:
            check_command = [command[0], "-S", str(control_path), "-O", "check", command[-1]]
            deadline = time.monotonic() + readiness_timeout
            while True:
                returncode = process.poll()
                if returncode is not None:
                    error = _read_stderr_tail(ssh_stderr)
                    raise RuntimeError(f"SSH tunnel failed with exit code {returncode}: {error}")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError("SSH tunnel readiness timed out")
                try:
                    check = subprocess.run(
                        check_command,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False,
                        timeout=remaining,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise RuntimeError("SSH tunnel readiness timed out") from exc
                if check.returncode == 0:
                    if time.monotonic() > deadline:
                        raise RuntimeError("SSH tunnel readiness timed out")
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    error = (check.stderr or "").strip()
                    raise RuntimeError(f"SSH tunnel readiness timed out: {error}")
                time.sleep(min(check_interval, remaining))
            returncode = process.poll()
            if returncode is not None:
                error = _read_stderr_tail(ssh_stderr)
                raise RuntimeError(f"SSH tunnel failed with exit code {returncode}: {error}")

            abort_event = threading.Event()
            monitor_stop = threading.Event()

            def monitor_tunnel() -> None:
                while not monitor_stop.wait(monitor_interval):
                    if process.poll() is not None:
                        abort_event.set()
                        return

            monitor = threading.Thread(target=monitor_tunnel, daemon=True)
            monitor.start()
            try:
                return serve(abort_event)
            finally:
                monitor_stop.set()
                monitor.join()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def main(argv: list[str] | None = None) -> int:
    from relay import relay_cookie_path, serve

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-host", required=True)
    parser.add_argument("--ssh-user", required=True)
    parser.add_argument("--ssh-key", required=True, type=Path)
    parser.add_argument("--ssh-binary", default="ssh")
    parser.add_argument("--remote-port", type=int, default=18765)
    parser.add_argument("--local-port", type=int, default=8765)
    parser.add_argument("--public-url", required=True)
    parser.add_argument("--ttl", type=int, default=300)
    parser.add_argument("--user-label", default="telegram-user")
    parser.add_argument("--approval-scope", required=True)
    parser.add_argument("--cookie-path", type=Path, default=relay_cookie_path())
    args = parser.parse_args(argv)

    try:
        public_url = validate_public_url(args.public_url)
        ssh_key = args.ssh_key.expanduser()
        if not ssh_key.is_file():
            raise ValueError(f"SSH private key does not exist: {ssh_key}")
        with tempfile.TemporaryDirectory(prefix="guap-relay-") as directory:
            control_path = Path(directory) / "ssh-control"
            command = build_ssh_command(
                ssh_binary=args.ssh_binary,
                host=args.ssh_host,
                user=args.ssh_user,
                key=ssh_key,
                remote_port=args.remote_port,
                local_port=args.local_port,
                control_path=control_path,
            )
            return run_with_tunnel(
                command,
                lambda abort_event: serve(
                    bind="127.0.0.1",
                    port=args.local_port,
                    public_url=public_url,
                    ttl=args.ttl,
                    user_label=args.user_label,
                    approval_scope=args.approval_scope,
                    cookie_path=args.cookie_path,
                    abort_event=abort_event,
                ),
                control_path=control_path,
            )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
