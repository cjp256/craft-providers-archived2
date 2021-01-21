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

"""Multipass Instance."""
import io
import logging
import pathlib
import subprocess
from typing import Any, Dict, List, Optional

from .. import Executor
from .multipass import Multipass

logger = logging.getLogger(__name__)


class MultipassInstanceError(Exception):
    def __init__(self, msg: str) -> None:
        self.msg = msg

    def __str__(self) -> str:
        return self.msg


class MultipassInstance(Executor):
    """Multipass Instance Lifecycle."""

    def __init__(
        self,
        *,
        name: str,
        multipass: Optional[Multipass] = None,
    ):
        super().__init__()

        if multipass is None:
            self.multipass = Multipass()
        else:
            self.multipass = multipass

        self.name = name

    def create_file(
        self,
        *,
        destination: pathlib.Path,
        content: bytes,
        file_mode: str,
        gid: int = 0,
        uid: int = 0,
    ) -> None:
        """Create file with content and file mode.

        :param destination: Path to file.
        :param content: Contents of file.
        :param file_mode: File mode string (e.g. '0644').
        :param gid: File owner group ID.
        :param uid: Filer owner user ID.
        """
        stream = io.BytesIO(content)

        # Multipass makes us do a song and dance because it doesn't support
        # executing / transfering as root.
        tmp_file_path = "/".join("/tmp", destination.as_posix().replace("/", "_"))

        self.multipass.transfer_from_io(
            source=stream,
            destination=f"{self.name}:{tmp_file_path}",
        )

        self.execute_run(
            command=["sudo", "chown", f"{uid!s}:{gid!s}", tmp_file_path],
        )

        self.execute_run(
            command=["sudo", "chmod", file_mode, tmp_file_path],
        )

        self.execute_run(
            command=["sudo", "mv", tmp_file_path, destination.as_posix()],
        )

    def delete(self, purge: bool = True) -> None:
        """Delete instance.

        :param purge: Purge instances immediately.
        """
        return self.multipass.delete(
            instance_name=self.name,
            purge=purge,
        )

    def execute_popen(self, command: List[str], **kwargs) -> subprocess.Popen:
        """Execute process in instance using subprocess.Popen().

        :param command: Command to execute.
        :param kwargs: Additional keyword arguments for subprocess.Popen().

        :returns: Popen instance.
        """
        return self.multipass.exec(
            instance_name=self.name,
            command=command,
            project=self.project,
            remote=self.remote,
            runner=subprocess.Popen,
            **kwargs,
        )

    def execute_run(
        self, command: List[str], check=True, **kwargs
    ) -> subprocess.CompletedProcess:
        """Execute command using subprocess.run().

        :param command: Command to execute.
        :param check: Raise exception on failure.
        :param kwargs: Keyword args to pass to subprocess.run().

        :returns: Completed process.

        :raises subprocess.CalledProcessError: if command fails and check is
            True.
        """

        command = ["sudo", "-H", "/root", "--"]
        return self.multipass.exec(
            instance_name=self.name,
            command=command,
            runner=subprocess.run,
            check=check,
            **kwargs,
        )

    def exists(self) -> bool:
        """Check if instance exists.

        :returns: True if instance exists.
        """
        return self.get_state() is not None

    def get_info(self) -> Optional[Dict[str, Any]]:
        """Get configuration and state for instance.

        :returns: State information parsed from multipass if instance exists, else
            None.
        """
        instance_config = self.multipass.info(instance_name=self.name)
        if instance_config is None:
            return None

        config = instance_config.get("info", dict()).get(self.name)
        if config is None:
            raise MultipassInstanceError(f"Unable to parse VM info for {self.name!r}.")

        return config

    def is_mounted(self, *, source: pathlib.Path, destination: pathlib.Path) -> bool:
        """Check if path is mounted at target.

        :param source: Host path to check.
        :param destination: Instance path to check.

        :returns: True if source is mounted at destination.
        """
        info = self.get_info()
        mounts = info.get("mounts")

        for mount_point, mount_config in mounts.items():
            if key == destination.as_posix() and mount_config.get("source_path") == str(
                source
            ):
                return True

        return False

    def is_running(self) -> bool:
        """Check if instance is running.

        :returns: True if instance is running.
        """
        state = self.get_state()
        if state is None:
            return False

        return state.get("status") == "Running"

    def launch(
        self,
        *,
        image: str,
        instance_cpus: int = 2,
        instance_disk_gb: int = 256,
        instance_mem_gb: int = 2,
        instance_name: str,
    ) -> None:
        """Launch instance.

        :param image: Name of image to create the instance with.
        :param instance_cpus: Number of CPUs.
        :param instance_disk_gb: Disk allocation in gigabytes.
        :param instance_mem_gb: Memory allocation in gigabytes.
        :param instance_name: Name of instance to use/create.
        :param instance_stop_time_mins: Stop time delay in minutes.
        """

        self.multipass.launch(
            instance_name=self.name,
            image=image,
            cpus=str(instance_cpus),
            disk=f"{instance_disk_gb!s}G",
            mem=f"{instance_mem_gb!s}G",
        )

    def mount(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        """Mount host source directory to target mount point.

        Checks first to see if already mounted.

        :param source: Host path to mount.
        :param destination: Instance path to mount to.
        """
        if self.is_mounted(source=source, destination=destination):
            return

        self.multipass.config_device_add_disk(
            instance_name=self.name,
            source=source,
            destination=destination,
            project=self.project,
            remote=self.remote,
        )

    def start(self) -> None:
        """Start instance."""
        self.multipass.start(instance_name=self.name)

    def stop(self) -> None:
        """Stop instance."""
        self.multipass.stop(instance_name=self.name)

    def supports_mount(self) -> bool:
        """Check if instance supports mounting from host.

        :returns: True if mount is supported.
        """
        return True

    def sync_from(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        """Copy source file/directory from environment to host destination.

        Standard "cp -r" rules apply:

            - if source is directory, copy happens recursively.

            - if destination exists, source will be copied into destination.

        Providing this as an abstract method allows the provider to implement
        the most performant option available.

        :param source: Target directory to copy from.
        :param destination: Host destination directory to copy to.

        :raises FileNotFoundError: If source does not exist.
        """
        logger.info("Syncing env:%s -> host:%s...", source, destination)

        # TODO: check if mount makes source == destination, skip if so.
        if self.is_target_file(source):
            destination.parent.mkdir(parents=True, exist_ok=True)
            self.multipass.transfer(
                source=f"{self.name}:{source!s}",
                destination=destination,
            )
        elif self.is_target_directory(target=source):
            self.naive_directory_sync_from(source=source, destination=destination)
        else:
            raise FileNotFoundError(f"Source {source} not found.")

    def sync_to(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        """Copy host source file/directory into environment at destination.

        Standard "cp -r" rules apply:
        - if source is directory, copy happens recursively.
        - if destination exists, source will be copied into destination.

        Providing this as an abstract method allows the provider to implement
        the most performant option available.

        :param source: Host directory to copy.
        :param destination: Target destination directory to copy to.

        :raises FileNotFoundError: If source does not exist.
        """
        # TODO: check if mounted, skip sync if source == destination
        logger.info("Syncing host:%s -> env:%s...", source, destination)
        if source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            self.multipass.transfer(
                source=source,
                destination=f"{self.name}:{destination!s}",
            )
        elif source.is_dir():
            # TODO: use mount() if available
            self.naive_directory_sync_to(
                source=source, destination=destination, delete=True
            )
        else:
            raise FileNotFoundError(f"Source {source} not found.")
