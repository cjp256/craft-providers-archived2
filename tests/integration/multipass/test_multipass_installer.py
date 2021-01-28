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

import os
import subprocess
import sys

import pytest

from craft_providers.multipass import multipass_installer


@pytest.fixture(autouse=True)
def multipass_path():
    """Override shared fixture."""
    yield None


@pytest.fixture(autouse=True)
def uninstalled_multipass():
    """Uninstall Multipass prior to test, if environment allows it.

    CRAFT_PROVIDER_TESTS_ENABLE_MULTIPASS_UNINSTALL=1
    """
    installer = multipass_installer.MultipassInstaller()
    if not installer.is_installed():
        return

    if (
        os.environ.get("CRAFT_PROVIDER_TESTS_ENABLE_MULTIPASS_UNINSTALL") == "1"
        and sys.platform == "linux"
    ):
        subprocess.run(["sudo", "snap", "remove", "multipass", "--purge"], check=True)
    else:
        pytest.skip("not allowed to uninstall multipass, skipped")


def test_install():
    installer = multipass_installer.MultipassInstaller()
    path = installer.install()

    assert path.exists() is True
