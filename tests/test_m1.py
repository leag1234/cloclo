"""Lifecycle tests: provider doubles never enter runtime code."""

import contextlib
import importlib.util
import os
from pathlib import Path
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch


def load_gpu() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gpu", "infra/gpu.py")
    assert spec and spec.loader
    gpu = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gpu)
    return gpu


class GPUContract(unittest.TestCase):
    def test_down_propagates_provider_error(self) -> None:
        import subprocess

        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "scw"
            executable.write_text("#!/bin/sh\nexit 9\n")
            executable.chmod(0o755)
            result = subprocess.run(
                ["bash", "infra/gpu-down.sh"],
                env={**os.environ, "PATH": directory + ":" + os.environ["PATH"]},
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_lifecycle(self) -> None:
        gpu = load_gpu()
        with tempfile.TemporaryDirectory() as directory, contextlib.chdir(directory):
            Path("BRAIN").mkdir()
            owned = {"id": "server", "tags": ["atlas-m1"], "name": "atlas-gpu"}
            with patch.dict(
                os.environ,
                {"SCW_DEFAULT_PROJECT_ID": "project", "SCW_DEFAULT_ZONE": "fr-par-2"},
            ):
                with patch.object(
                    gpu, "call", return_value=[owned, {"id": "foreign", "tags": []}]
                ):
                    self.assertEqual(gpu.owned("instance", "server"), [owned])
                with patch.object(gpu, "call", side_effect=RuntimeError("provider")):
                    self.assertRaises(RuntimeError, gpu.down)
                with patch.object(gpu, "owned", return_value=[owned, owned]):
                    self.assertRaises(RuntimeError, gpu.down)
                with (
                    patch.object(gpu, "owned", return_value=[]),
                    patch.object(gpu, "call") as call,
                ):
                    gpu.down()
                    call.assert_not_called()
            cloud = gpu.bootstrap("weights", "org/model", True)
            self.assertIn("mkfs.ext4", cloud)
            self.assertNotIn("mkfs.ext4", gpu.bootstrap("weights", "org/model", False))
            self.assertIn("enable-prefix-caching", cloud)
            self.assertIn("/root/.cache/huggingface", cloud)
            self.assertIn("scsi-0SCW_sbs_volume-weights", cloud)

    def test_create_and_destroy(self) -> None:
        from typing import Any

        gpu = load_gpu()
        requests: list[tuple[str, ...]] = []
        servers: list[dict[str, Any]] = []
        volumes: list[dict[str, Any]] = []
        groups: list[dict[str, Any]] = []

        def provider(*args: str) -> Any:
            requests.append(args)
            if args[2] == "list":
                return {
                    "server": servers,
                    "volume": volumes,
                    "security-group": groups,
                    "server-type": [
                        {
                            "name": "L40S-1-48G",
                            "availability": "scarce",
                            "hourly_price": {"units": 1, "nanos": 0},
                        }
                    ],
                }[args[1]]
            if args[2] == "create":
                self.assertIn("project-id=project", args)
                obj = {
                    "id": args[1],
                    "tags": ["atlas-m1"],
                    "volumes": {"0": {"id": "root"}},
                }
                if args[1] == "server":
                    self.assertIn("additional-volumes.0=volume", args)
                    self.assertTrue(any(a.startswith("cloud-init=@") for a in args))
                    servers.append(obj)
                    return {
                        **obj,
                        "public_ips": [{"address": "192.0.2.3", "family": "inet"}],
                    }
                (volumes if args[1] == "volume" else groups).append(obj)
                return {"security_group": obj} if args[1] == "security-group" else obj
            if args[2] == "terminate":
                self.assertIn("with-block=false", args)
                self.assertIn("with-ip=true", args)
                servers.clear()
            return None

        with tempfile.TemporaryDirectory() as directory, contextlib.chdir(directory):
            Path("BRAIN").mkdir()
            with (
                patch.dict(
                    os.environ,
                    {
                        "SCW_DEFAULT_PROJECT_ID": "project",
                        "SCW_DEFAULT_ZONE": "fr-par-2",
                        "LOCAL_MODEL": "org/model",
                        "GPU_CLIENT_IP": "192.0.2.2",
                        "GPU_MAX_EUR_H": "1.47",
                    },
                ),
                patch.object(gpu, "call", side_effect=provider),
            ):
                gpu.up()
                self.assertEqual(
                    Path("BRAIN/gpu_ip.txt").read_text().strip(), "192.0.2.3"
                )
                self.assertRaises(RuntimeError, gpu.up)
                gpu.down()
                self.assertFalse(Path("BRAIN/gpu_ip.txt").exists())
                self.assertEqual(len(volumes), 1)
                self.assertFalse(
                    any(a[:3] == ("block", "volume", "delete") for a in requests)
                )
                with patch.dict(os.environ, {"GPU_MAX_EUR_H": "0"}):
                    self.assertRaises(RuntimeError, gpu.up)
                with patch.dict(os.environ, {"LOCAL_MODEL": "$(unsafe)"}):
                    self.assertRaises(ValueError, gpu.up)

    def test_provider_boundary(self) -> None:
        import subprocess

        gpu = load_gpu()
        with patch.dict(os.environ, {"SCW_DEFAULT_ZONE": "fr-par-2"}):
            with patch.object(
                gpu.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, "[]"),
            ):
                self.assertEqual(gpu.call("instance", "server", "list"), [])
            with patch.object(
                gpu.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 1, "sensitive data"),
            ):
                with self.assertRaisesRegex(RuntimeError, "exit 1"):
                    gpu.call("instance", "server", "list")
            with patch.dict(os.environ, {"GPU_SSH_PUBLIC_KEY": "invalid\nkey"}):
                self.assertRaises(
                    ValueError, gpu.bootstrap, "volume", "org/model", True
                )
