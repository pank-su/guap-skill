from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/guap-pro/scripts/remote_relay.py"


def load_remote_relay():
    spec = importlib.util.spec_from_file_location("guap_remote_relay", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeProcess:
    def __init__(self) -> None:
        self.returncode = None
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


class RemoteRelayTests(unittest.TestCase):
    def test_cli_help_documents_remote_relay_parameters(self) -> None:
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--ssh-host", result.stdout)
        self.assertIn("--public-url", result.stdout)
        self.assertIn("--approval-scope", result.stdout)

    def test_run_with_tunnel_always_terminates_ssh(self) -> None:
        module = load_remote_relay()
        process = FakeProcess()
        with (
            patch.object(module.subprocess, "Popen", return_value=process),
            patch.object(
                module.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, stderr=""),
            ),
        ):
            result = module.run_with_tunnel(
                ["ssh", "student@relay.example.com"],
                lambda abort_event: 7,
                control_path=Path("/tmp/relay-control"),
            )
        self.assertEqual(result, 7)
        self.assertTrue(process.terminated)
        self.assertFalse(process.killed)

    def test_run_with_tunnel_waits_for_control_master_readiness(self) -> None:
        module = load_remote_relay()
        process = FakeProcess()
        checks = [
            subprocess.CompletedProcess([], 1, stderr="not ready"),
            subprocess.CompletedProcess([], 0, stderr=""),
        ]
        with (
            patch.object(module.subprocess, "Popen", return_value=process),
            patch.object(module.subprocess, "run", side_effect=checks) as run,
            patch.object(module.time, "sleep"),
        ):
            result = module.run_with_tunnel(
                ["ssh", "student@relay.example.com"],
                lambda abort_event: 7,
                control_path=Path("/tmp/relay-control"),
                readiness_timeout=1,
            )
        self.assertEqual(result, 7)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(
            run.call_args_list[0].args[0],
            ["ssh", "-S", "/tmp/relay-control", "-O", "check", "student@relay.example.com"],
        )

    def test_run_with_tunnel_bounds_hung_control_check_and_aborts(self) -> None:
        module = load_remote_relay()
        process = FakeProcess()
        with (
            patch.object(module.subprocess, "Popen", return_value=process),
            patch.object(
                module.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(["ssh"], 0.25),
            ) as run,
        ):
            with self.assertRaisesRegex(RuntimeError, "readiness timed out"):
                module.run_with_tunnel(
                    ["ssh", "student@relay.example.com"],
                    lambda abort_event: 7,
                    control_path=Path("/tmp/relay-control"),
                    readiness_timeout=0.25,
                )
        self.assertLessEqual(run.call_args.kwargs["timeout"], 0.25)

    def test_run_with_tunnel_does_not_pipe_long_lived_ssh_stderr(self) -> None:
        module = load_remote_relay()
        process = FakeProcess()
        with (
            patch.object(module.subprocess, "Popen", return_value=process) as popen,
            patch.object(
                module.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, stderr=""),
            ),
        ):
            self.assertEqual(
                module.run_with_tunnel(
                    ["ssh", "student@relay.example.com"],
                    lambda abort_event: 7,
                    control_path=Path("/tmp/relay-control"),
                ),
                7,
            )
        self.assertIsNot(popen.call_args.kwargs["stderr"], subprocess.PIPE)
        self.assertTrue(hasattr(popen.call_args.kwargs["stderr"], "read"))

    def test_run_with_tunnel_aborts_relay_when_ssh_exits(self) -> None:
        module = load_remote_relay()
        process = FakeProcess()

        def serve(abort_event) -> int:
            process.returncode = 255
            self.assertTrue(abort_event.wait(1))
            return 3

        with (
            patch.object(module.subprocess, "Popen", return_value=process),
            patch.object(
                module.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, stderr=""),
            ),
        ):
            result = module.run_with_tunnel(
                ["ssh", "student@relay.example.com"],
                serve,
                control_path=Path("/tmp/relay-control"),
                monitor_interval=0.01,
            )
        self.assertEqual(result, 3)

    def test_main_uses_control_master_and_expands_ssh_key_before_check(self) -> None:
        module = load_remote_relay()
        fake_relay = types.SimpleNamespace(relay_cookie_path=lambda: Path("/tmp/cookie"), serve=lambda **kwargs: 0)
        with tempfile.TemporaryDirectory() as directory:
            key = Path(directory) / "relay-key"
            key.touch()
            with (
                patch.dict(sys.modules, {"relay": fake_relay}),
                patch.object(module.Path, "expanduser", return_value=key),
                patch.object(module, "run_with_tunnel", return_value=0) as run,
            ):
                result = module.main(
                    [
                        "--ssh-host", "relay.example.com",
                        "--ssh-user", "student",
                        "--ssh-key", "~/relay-key",
                        "--public-url", "https://relay.example.com/guap",
                        "--approval-scope", "GUAP read-only access",
                    ]
                )
        self.assertEqual(result, 0)
        command = run.call_args.args[0]
        self.assertIn("ControlMaster=yes", command)
        self.assertEqual(command[command.index("-i") + 1], str(key))
        self.assertIsInstance(run.call_args.kwargs["control_path"], Path)

    def test_validate_public_url_rejects_http(self) -> None:
        module = load_remote_relay()
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            module.validate_public_url("http://relay.example.com/guap")

    def test_validate_public_url_rejects_userinfo(self) -> None:
        module = load_remote_relay()
        with self.assertRaisesRegex(ValueError, "credentials"):
            module.validate_public_url("https://user:password@relay.example.com/guap")

    def test_validate_public_url_rejects_query(self) -> None:
        module = load_remote_relay()
        with self.assertRaisesRegex(ValueError, "query"):
            module.validate_public_url("https://relay.example.com/guap?token=secret")

    def test_validate_public_url_rejects_fragment(self) -> None:
        module = load_remote_relay()
        with self.assertRaisesRegex(ValueError, "fragment"):
            module.validate_public_url("https://relay.example.com/guap#login")

    def test_validate_public_url_rejects_empty_delimiters_and_malformed_port(self) -> None:
        module = load_remote_relay()
        for value in (
            "https://relay.example.com/guap?",
            "https://relay.example.com/guap#",
            "https://relay.example.com:bad/guap",
            "https:///guap",
            "https://relay.example.com/guap\n",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.validate_public_url(value)

    def test_build_ssh_command_rejects_invalid_ports_and_ambiguous_endpoint_parts(self) -> None:
        module = load_remote_relay()
        for local_port, remote_port in ((0, 18765), (8765, 65536), (8765, -1)):
            with self.subTest(local_port=local_port, remote_port=remote_port), self.assertRaises(ValueError):
                module.build_ssh_command(
                    ssh_binary="ssh",
                    host="relay.example.com",
                    user="student",
                    key=Path("/tmp/relay-key"),
                    remote_port=remote_port,
                    local_port=local_port,
                    control_path=Path("/tmp/relay-control"),
                )
        for user, host in (("-oProxyCommand=bad", "relay.example.com"), ("student\n", "relay.example.com"), ("student", "-oProxyCommand=bad"), ("student", "relay@example.com")):
            with self.subTest(user=user, host=host), self.assertRaises(ValueError):
                module.build_ssh_command(
                    ssh_binary="ssh",
                    host=host,
                    user=user,
                    key=Path("/tmp/relay-key"),
                    remote_port=18765,
                    local_port=8765,
                    control_path=Path("/tmp/relay-control"),
                )

    def test_build_ssh_command_uses_loopback_reverse_forward(self) -> None:
        module = load_remote_relay()
        command = module.build_ssh_command(
            ssh_binary="ssh",
            host="relay.example.com",
            user="student",
            key=Path("/tmp/relay-key"),
            remote_port=18765,
            local_port=8765,
            control_path=Path("/tmp/relay-control"),
        )
        self.assertEqual(
            command,
            [
                "ssh",
                "-N",
                "-T",
                "-o",
                "ControlMaster=yes",
                "-o",
                "ControlPath=/tmp/relay-control",
                "-i",
                "/tmp/relay-key",
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
                "127.0.0.1:18765:127.0.0.1:8765",
                "student@relay.example.com",
            ],
        )


if __name__ == "__main__":
    unittest.main()
