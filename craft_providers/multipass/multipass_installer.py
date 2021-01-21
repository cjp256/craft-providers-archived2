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

from craft_providers.util import path, prompt

logger = logging.getLogger(__name__)


def MultipassInstallerError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason

    def __str__(self) -> str:
        return f"Failed to install Multipass: {self.reason}"


class MultipassInstaller:
    """Multipass Interface."""

    def __init__(
        self,
        *,
        input_handler=input,
        multipass_path: Optional[pathlib.Path] = None,
        platform: str = sys.platform,
    ):
        self._input_handler = input_handler

        if multipass_path is None:
            self.multipass_path = self._find_multipass()
        else:
            self.multipass_path = multipass_path

        self._platform = platform

    def _ensure_supported_version(self) -> None:
        """Ensure Multipass meets minimum requirements.

        :raises MultipassInstallerError: if unsupported.
        """
        proc = subprocess.run(
            [str(self.multipass_path), "version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Split should look like ['multipass', '1.5.0', 'multipassd', '1.5.0'].
        output_split = proc.stdout.decode().split()
        if len(output_split) != 4:
            raise MultipassInstallerError(
                "Failed to parse multipass version output: {output_split}."
            )

        version_components = output_split[1].split(".")
        major_minor = ".".join([version_components[0], version_components[1]])

        if float(major_minor) < 1.5:
            raise MultipassInstallerError(
                f"Multipass version {major_minor!r} is unsupported. Must be >= 1.5."
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

    def _setup_wait_ready(
        self, retry_interval: float = 1.0, retry_count: int = 120
    ) -> None:
        while retry_count > 0:
            proc = subprocess.run(
                [self.multipass_path, "version"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

            if "multipass" in proc.stdout.decode():
                return

            retry_count -= 1
            sleep(retry_interval)

    def _setup_darwin(self) -> None:
        try:
            subprocess.run(["brew", "cask", "install", "multipass"], check=True)
        except subprocess.CalledProcessError as error:
            raise MultipassInstallerError("error during brew installation") from error

    def _setup_linux(self) -> None:
        try:
            subprocess.run(["sudo", "snap", "install", "multipass"], check=True)
        except subprocess.CalledProcessError as error:
            raise MultipassInstallerError("error during snap installation") from error

    def _setup_windows(self) -> None:
        raise MultipassInstallerError("Windows not yet supported")

    def setup(self) -> None:
        """Ensure Multipass is installed with required version.

        :raises MultipassInstallerError: if unsupported.
        """
        if not self.multipass_path.exists():
            if not prompt.input_bool(
                "Multipass needs to be installed.  Install now?",
                default=False,
                require_valid=True,
            ):
                raise MultipassInstallerError("user declined to install")

            subprocess.run(["sudo", "snap", "install", "multipass"], check=True)

            self.multipass_path = self._find_multipass()
            if self.multipass_path is None or not self.multipass_path.exists():
                raise MultipassInstallerError("multipass not found")

            subprocess.run(
                ["sudo", str(self.multipass_path), "waitready", "--timeout=30"],
                check=True,
            )
            subprocess.run(
                ["sudo", str(self.multipass_path), "init", "--auto"], check=True
            )

        self._ensure_supported_version()
