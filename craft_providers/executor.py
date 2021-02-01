# Copyright (C) 2021 Canonical Ltd
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

"""Executor module."""
import logging
import pathlib
import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import List

from .util import path

logger = logging.getLogger(__name__)


class Executor(ABC):
    """Interfaces to execute commands and move data in/out of an environment.

    :param tar_path: Path to tar command.

    """

    def __init__(self, *, tar_path: pathlib.Path = None) -> None:
        if tar_path is None:
            self.tar_path = path.which_required("tar")
        else:
            self.tar_path = tar_path

    @abstractmethod
    def create_file(
        self,
        *,
        destination: pathlib.Path,
        content: bytes,
        file_mode: str,
        group: str = "root",
        user: str = "root",
    ) -> None:
        """Create file with content and file mode."""
        ...

    @abstractmethod
    def execute_popen(self, command: List[str], **kwargs) -> subprocess.Popen:
        """Execute command in instance, using subprocess.Popen().

        If `env` is in kwargs, it will be applied to the target runtime
        environment, not the host's.

        :param command: Command to execute.
        :param kwargs: Additional keyword arguments to pass.

        :returns: Popen instance.
        """
        ...

    @abstractmethod
    def execute_run(
        self, command: List[str], check=True, **kwargs
    ) -> subprocess.CompletedProcess:
        """Execute command using subprocess.run().

        :param command: Command to execute.
        :param kwargs: Keyword args to pass to subprocess.run().
        :param check: Raise exception on failure.

        :returns: Completed process.

        :raises subprocess.CalledProcessError: if command fails and check is
            True.
        """
        ...

    @abstractmethod
    def sync_from(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        """Copy source file/directory from environment to host destination.

        Standard "cp -r" rules apply:

            - if source is directory, copy happens recursively.

            - if destination exists, source will be copied into destination.

        Providing this as an abstract method allows the provider to implement
        the most performant option available.

        :param source: Target directory to copy from.
        :param destination: Host destination directory to copy to.
        """
        ...

    @abstractmethod
    def sync_to(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        """Copy host source file/directory into environment at destination.

        Standard "cp -r" rules apply:
        - if source is directory, copy happens recursively.
        - if destination exists, source will be copied into destination.

        Providing this as an abstract method allows the provider to implement
        the most performant option available.

        :param source: Host directory to copy.
        :param destination: Target destination directory to copy to.
        """
        ...

    def is_target_directory(self, target: pathlib.Path) -> bool:
        """Check if path is directory.

        :param target: Path to check.

        :returns: True if directory, False otherwise.
        """
        proc = self.execute_run(command=["test", "-d", target.as_posix()])
        return proc.returncode == 0

    def is_target_file(self, target: pathlib.Path) -> bool:
        """Check if path is file.

        :param target: Path to check.

        :returns: True if file, False otherwise.
        """
        proc = self.execute_run(command=["test", "-f", target.as_posix()])
        return proc.returncode == 0

