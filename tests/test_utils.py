# Copyright 2022 TIER IV, INC. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for shared utils (stdlib only, no third-party deps)."""

import errno
import os
import subprocess
import sys

import pytest

from offline_ota_image_builder.utils import (
    RUN_AS_PYINSTALLER_BUNDLE,
    exit_with_err_msg,
    pyinstaller_aware_subprocess_run,
    subprocess_run_wrapper,
)


def test_run_list_command():
    result = subprocess_run_wrapper(["echo", "hello"])
    assert result.returncode == 0
    assert result.stdout == b"hello\n"


def test_run_str_command_is_shlex_split():
    result = subprocess_run_wrapper("echo hello world")
    assert result.stdout == b"hello world\n"


def test_run_check_false_does_not_raise_on_failure():
    result = subprocess_run_wrapper(["false"], check=False)
    assert result.returncode != 0


def test_run_check_true_raises_on_failure():
    with pytest.raises(subprocess.CalledProcessError):
        subprocess_run_wrapper(["false"])  # check=True by default


def test_run_without_check_output_captures_no_stdout():
    result = subprocess_run_wrapper(["echo", "x"], check_output=False)
    assert result.stdout is None


def test_run_passes_env_to_child():
    result = subprocess_run_wrapper(
        [
            sys.executable,
            "-c",
            "import os; print(os.environ.get('OFFLINE_OTA_TEST', ''))",
        ],
        env={**os.environ, "OFFLINE_OTA_TEST": "42"},
    )
    assert result.stdout.strip() == b"42"


def test_run_timeout_raises():
    with pytest.raises(subprocess.TimeoutExpired):
        subprocess_run_wrapper(
            [sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.2
        )


# ------ pyinstaller_aware_subprocess_run ------ #

_PRINT_LD_PATH = [
    sys.executable,
    "-c",
    "import os; print(os.environ.get('LD_LIBRARY_PATH', '<UNSET>'))",
]


def test_pyinstaller_restores_original_ld_library_path():
    env = {
        **os.environ,
        "LD_LIBRARY_PATH": "/pyinstaller/lib",
        "LD_LIBRARY_PATH_ORIG": "/orig/lib",
    }
    result = pyinstaller_aware_subprocess_run(
        _PRINT_LD_PATH, env=env, check=True, stdout=subprocess.PIPE
    )
    assert result.stdout.strip() == b"/orig/lib"


def test_pyinstaller_removes_ld_library_path_when_no_orig():
    env = {**os.environ, "LD_LIBRARY_PATH": "/pyinstaller/lib"}
    env.pop("LD_LIBRARY_PATH_ORIG", None)
    result = pyinstaller_aware_subprocess_run(
        _PRINT_LD_PATH, env=env, check=True, stdout=subprocess.PIPE
    )
    assert result.stdout.strip() == b"<UNSET>"


def test_pyinstaller_does_not_mutate_input_env():
    env = {
        **os.environ,
        "LD_LIBRARY_PATH": "/pyinstaller/lib",
        "LD_LIBRARY_PATH_ORIG": "/orig/lib",
    }
    snapshot = dict(env)
    pyinstaller_aware_subprocess_run(
        [sys.executable, "-c", "pass"], env=env, check=False
    )
    assert env == snapshot


# ------ exit_with_err_msg ------ #


def test_exit_with_err_msg_default_code(capsys):
    with pytest.raises(SystemExit) as exc_info:
        exit_with_err_msg("boom")
    assert exc_info.value.code == 1
    assert "ERR: boom" in capsys.readouterr().out


def test_exit_with_err_msg_custom_code():
    with pytest.raises(SystemExit) as exc_info:
        exit_with_err_msg("bad input", exit_code=errno.EINVAL)
    assert exc_info.value.code == errno.EINVAL


def test_not_running_as_pyinstaller_bundle_during_tests():
    assert RUN_AS_PYINSTALLER_BUNDLE is False
