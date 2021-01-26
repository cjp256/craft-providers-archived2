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

import io
import os
import subprocess
import sys

import pytest

from craft_providers.multipass import multipass_installer


@pytest.fixture(autouse=True)
def multipass_uninstaller():
    installer = multipass_installer.MultipassInstaller()
    if not installer.is_installed():
        return

    if (
        os.environ.get("CRAFT_PROVIDER_TESTS_ENABLE_MULTIPASS_UNINSTALL") == "1"
        and sys.platform == "linux"
    ):
        subprocess.run(["sudo", "snap", "remove", "multipass"], check=True)
    else:
        pytest.skip("not allowed to uninstall multipass, skipped")


@pytest.mark.parametrize("input_str", ["n", "N", "no", "NO"])
def test_install_no(monkeypatch, input_str):
    """Test Multipass installation.

    We cannot forcibly uninstall Multipass from host, work with what we have.
    """
    monkeypatch.setattr("sys.stdin", io.StringIO(input_str))

    installer = multipass_installer.MultipassInstaller()
    with pytest.raises(multipass_installer.MultipassInstallerError) as error:
        installer.install()

    assert str(error.value) == "Failed to install Multipass: user declined to install"


@pytest.mark.parametrize("input_str", ["y", "YES"])
def test_install_yes(monkeypatch, input_str):
    """Test Multipass installation.

    We cannot forcibly uninstall Multipass from host, work with what we have.
    """
    monkeypatch.setattr("sys.stdin", io.StringIO(input_str))

    installer = multipass_installer.MultipassInstaller()
    installer.install()
