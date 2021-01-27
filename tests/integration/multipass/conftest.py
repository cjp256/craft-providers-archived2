# Copyright (C) 2020 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Fixtures for MULTIPASS integration tests."""
import pathlib
import random
import string
import subprocess
import tempfile
import time

import pytest

from craft_providers.multipass import Multipass, MultipassInstance


def run(cmd, check=True, **kwargs):
    return subprocess.run(
        cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, check=check, **kwargs
    )


@pytest.fixture()
def home_tmp_path():
    """Multipass doesn't have access """
    with tempfile.TemporaryDirectory(
        suffix=".tmp-pytest", dir=pathlib.Path.home()
    ) as temp_dir:
        yield pathlib.Path(temp_dir)


@pytest.fixture()
def multipass_snap():
    multipass_path = pathlib.Path("/snap/bin/multipass")
    if multipass_path.exists():
        already_installed = True
    else:
        already_installed = False
        run(["sudo", "snap", "install", "multipass"])

    yield multipass_path

    if not already_installed:
        run(["sudo", "snap", "remove", "multipass"])


@pytest.fixture()
def multipass(multipass_snap):  # pylint: disable=unused-argument
    yield Multipass(multipass_path=pathlib.Path("/snap/bin/multipass"))


@pytest.fixture()
def instance_name():
    return "itest-" + "".join(random.choices(string.ascii_uppercase, k=8))


@pytest.fixture()
def instance_launcher(multipass, instance_name):
    def launcher(
        *,
        instance_name=instance_name,
        image_name="snapcraft:core20",
        cpus="2",
        mem="1G",
        disk="128G",
    ) -> MultipassInstance:
        multipass.launch(
            instance_name=instance_name,
            image=image_name,
            cpus=cpus,
            mem=mem,
            disk=disk,
        )

        # Make sure container is ready
        for _ in range(0, 2400):
            proc = multipass.exec(
                instance_name=instance_name,
                command=["systemctl", "is-system-running"],
                stdout=subprocess.PIPE,
            )

            running_state = proc.stdout.decode().strip()
            if running_state in ["running", "degraded"]:
                break
            time.sleep(0.1)

        return MultipassInstance(name=instance_name, multipass=multipass)

    yield launcher


@pytest.fixture()
def instance(instance_launcher, instance_name):
    yield instance_launcher(
        instance_name=instance_name,
        image="snapcraft:core20",
        cpus="2",
        mem="1G",
        disk="128G",
    )

    run(["multipass", "delete", "--purge", instance_name], check=False)
