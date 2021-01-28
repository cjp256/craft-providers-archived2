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

"""Multipass manager."""

import logging
import pathlib
import subprocess
import sys
from time import sleep
from typing import Optional

from craft_providers.util import path

logger = logging.getLogger(__name__)


class MultipassInstallerError(Exception):
    """Multipass Installation Error.

    :param reason: Reason for install failure.
    """

    def __init__(self, reason: str) -> None:
        super().__init__()

        self.reason = reason

    def __str__(self) -> str:
        return f"Failed to install Multipass: {self.reason}"


class MultipassInstaller:
    """Multipass Interface."""

    def __init__(
        self,
        *,
        platform: str = sys.platform,
    ):
        self._platform = platform

    def _ensure_supported_version(self, *, multipass_path: pathlib.Path) -> None:
        """Ensure Multipass meets minimum requirements.

        :raises MultipassInstallerError: if unsupported.
        """
        # Make sure Multipass is ready first.
        self._install_wait_ready(multipass_path=multipass_path)

        proc = subprocess.run(
            [str(multipass_path), "version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Split should look like ['multipass', '1.5.0', 'multipassd', '1.5.0'].
        output_split = proc.stdout.decode().split()
        if len(output_split) != 4:
            raise MultipassInstallerError(
                f"unable to parse version output {proc.stdout.decode()!r}"
            )

        version_components = output_split[1].split(".")
        major_minor = ".".join([version_components[0], version_components[1]])

        if float(major_minor) < 1.5:
            raise MultipassInstallerError(
                f"version {major_minor!r} unsupported (must be >= 1.5)"
            )

    def _find_multipass(self) -> Optional[pathlib.Path]:
        """Find multipass executable.

        Check PATH for executable, falling back to platform-specific path if not
        found.

        :returns: Path to multipass executable.  If executable not found, path
                  is /snap/bin/multipass.
        """
        if sys.platform == "win32":
            bin_name = "multipass.exe"
        else:
            bin_name = "multipass"

        # TODO: platform-specific sane options
        fallback = pathlib.Path("/snap/bin/multipass")

        bin_path = path.which(bin_name)
        if bin_path is None and fallback.exists():
            return fallback

        if bin_path is not None and bin_path.exists():
            return bin_path

        return None

    def _install_wait_ready(
        self,
        *,
        multipass_path: pathlib.Path,
        retry_interval: float = 1.0,
        retry_count: int = 120,
    ) -> None:
        while retry_count > 0:
            proc = subprocess.run(
                [str(multipass_path), "version"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

            # "multipass" may show up before "multipassd".
            if "multipassd" in proc.stdout.decode():
                return

            retry_count -= 1
            sleep(retry_interval)

    def _install_darwin(self) -> None:
        try:
            subprocess.run(["brew", "cask", "install", "multipass"], check=True)
        except subprocess.CalledProcessError as error:
            raise MultipassInstallerError("error during brew installation") from error

    def _install_linux(self) -> None:
        try:
            subprocess.run(["sudo", "snap", "install", "multipass"], check=True)
        except subprocess.CalledProcessError as error:
            raise MultipassInstallerError("error during snap installation") from error

    def _install_windows(self) -> None:
        # Ensure Windows PATH is up to date.
        # windows.reload_multipass_path_env()
        raise MultipassInstallerError("Windows not yet supported")

    def is_installed(self) -> bool:
        """Check if Multipass is installed (found valid multipass executable)."""
        multipass_path = self._find_multipass()

        return multipass_path is not None and multipass_path.exists()

    def install(self) -> pathlib.Path:
        """Ensure Multipass is installed with required version.

        :raises MultipassInstallerError: if unsupported.
        """
        if not self.is_installed():
            if self._platform == "darwin":
                self._install_darwin()
            elif self._platform == "linux":
                self._install_linux()
            elif self._platform == "win32":
                self._install_windows()
            else:
                raise MultipassInstallerError(
                    f"platform {self._platform} not supported"
                )

        multipass_path = self._find_multipass()
        if multipass_path is None:
            raise MultipassInstallerError("multipass not found")

        self._ensure_supported_version(multipass_path=multipass_path)
        return multipass_path
