# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2018 Canonical Ltd
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
import logging
import pathlib
import shlex
import subprocess
from typing import IO, Dict, List, Optional

logger = logging.getLogger(__name__)


class MultipassError:
    def __init__(self, *, command: str, returncode: int, reason: str) -> None:
        self.command = command
        self.returncode = returncode
        self.reason = reason

    def __str__(self) -> str:
        return self.reason


class Multipass:
    """Wrapper for multipass command.

    :param multipass_path: Path to multipass command to use.
    """

    def __init__(
        self, *, multipass_path: pathlib.Path = pathlib.Path("multipass")
    ) -> None:
        self.multipass_path = multipass_path

    def _run(  # pylint: disable=redefined-builtin
        self,
        *,
        command: List[str],
        check: bool = True,
        input=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ) -> subprocess.CompletedProcess:
        """Execute command in instance, allowing output to console."""
        command = [str(self.multipass_path), *command]
        quoted = " ".join([shlex.quote(c) for c in command])

        logger.warning("Executing on host: %s", quoted)

        try:
            if input is not None:
                proc = subprocess.run(
                    command, check=check, input=input, stderr=stderr, stdout=stdout
                )
            else:
                proc = subprocess.run(
                    command, check=check, stderr=stderr, stdout=stdout
                )
        except subprocess.CalledProcessError as error:
            logger.warning("Failed to execute: %s", error.output)
            raise error

        return proc

    def delete(self, *, instance: str, purge=True) -> None:
        """Passthrough for running multipass delete.

        :param instance: The name of the instance to delete.
        :param purge: Flag to purge the instance's image after deleting.

        :raises subprocess.CalledProcessError: on error.

        """
        command = ["delete", instance]
        if purge:
            command.append("--purge")

        self._run(command)

    def execute(
        self,
        *,
        command: List[str],
        instance: str,
        runner=subprocess.run,
        **kwargs,
    ):
        """Execute command in instance with specified runner."""
        run_command = [str(self.multipass_path), "exec", instance, "--", *command]

        quoted = " ".join([shlex.quote(c) for c in command])
        logger.warning("Executing in VM: %s", quoted)

        return runner(run_command, **kwargs)  # pylint: disable=subprocess-run-check

    def info(self, *, instance: str, output_format: str = None) -> Optional[bytes]:
        """Passthrough for running multipass info.

        :returns: Data from stdout if instance exists, else None.

        :raises MultipassError: On error.
        """
        command = ["info", instance]
        if output_format is not None:
            command.extend(["--format", output_format])

        try:
            proc = self._run(command)
        except subprocess.CalledProcessError as error:
            if "does not exist" in error.stdout.decode():
                return None

            raise MultipassError(
                command=error.command,
                exit_code=error.returncode,
                reason=f"Failed to query info for VM {instance!r}.",
            ) from error

        return proc.stdout

    def launch(
        self,
        *,
        instance: str,
        image: str,
        cpus: str = None,
        mem: str = None,
        disk: str = None,
        remote: str = None,
    ) -> None:
        """Launch multipass VM.

        :param instance: the name the launched instance will have.
        :param image: the image to create the instance with.
        :param cpus: amount of virtual CPUs to assign to the launched instance.
        :param mem: amount of RAM to assign to the launched instance.
        :param disk: amount of disk space the instance will see.
        :param remote: the remote server to retrieve the image from.

        :raises subprocess.CalledProcessError: on error.
        """
        if remote is not None:
            image = "{}:{}".format(remote, image)

        command = ["launch", image, "--name", instance]
        if cpus is not None:
            command.extend(["--cpus", cpus])
        if mem is not None:
            command.extend(["--mem", mem])
        if disk is not None:
            command.extend(["--disk", disk])

        try:
            self._run(command, check=True)
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                command=error.command,
                exit_code=error.returncode,
                reason=f"Failed to launch VM {instance!r}.",
            ) from error

    def start(self, *, instance: str) -> None:
        """Passthrough for running multipass start.

        :param instance: the name of the instance to start.

        :raises subprocess.CalledProcessError: on error.
        """
        command = ["start", instance]

        try:
            self._run(command, check=True)
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                command=error.command,
                exit_code=error.returncode,
                reason=f"Failed to start VM {instance!r}.",
            ) from error

    def stop(self, *, instance: str, time: int = None) -> None:
        """Passthrough for running multipass stop.

        :param instance: the name of the instance to stop.
        :param time: time from now, in minutes, to delay shutdown of the
            instance.

        :raises subprocess.CalledProcessError: on error.
        """
        command = ["stop"]

        if time:
            command.extend(["--time", str(time)])
        command.append(instance)

        try:
            self._run(command)
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                command=error.command,
                exit_code=error.returncode,
                reason=f"Failed to stop VM {instance!r}.",
            ) from error

    def mount(
        self,
        *,
        source: str,
        target: str,
        uid_map: Dict[str, str] = None,
        gid_map: Dict[str, str] = None,
    ) -> None:
        """Passthrough for running multipass mount.

        :param source: path to the local directory to mount.
        :param target: mountpoint inside the instance in the form of
                           <instance-name>:path.
        :param uid_map: A mapping of user IDs for use in the mount of the form
                             <host-id> -> <instance-id>.
                             File and folder ownership will be mapped from
                             <host> to <instance-name> inside the instance.
        :param gid_map: A mapping of group IDs for use in the mount of the form
                             <host-id> -> <instance-id>.
                             File and folder ownership will be mapped from
                             <host> to <instance-name> inside the instance.
        """
        command = ["mount", source, target]
        if uid_map is None:
            uid_map = dict()
        for host_map, instance_map in uid_map.items():
            command.extend(["--uid-map", "{}:{}".format(host_map, instance_map)])
        if gid_map is None:
            gid_map = dict()
        for host_map, instance_map in gid_map.items():
            command.extend(["--gid-map", "{}:{}".format(host_map, instance_map)])

        try:
            self._run(command)
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                command=error.command,
                exit_code=error.returncode,
                reason=f"Failed to mount {source!r} to {target!r}.",
            ) from error

    def shell(self, *, instance: str) -> None:
        """Passthrough for running multipass shell.

        :param instance: the name of the instance to execute command.

        :raises MultipassError: On error.
        """
        try:
            self._run(["shell", instance], stdin=None, stdout=None, stderr=None)
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                command=error.command,
                exit_code=error.returncode,
                reason="Failed to execute shell.",
            ) from error

    def umount(self, *, mount: str) -> None:
        """Passthrough for running multipass mount.

        :param mount: mountpoint inside the instance in the form of
                           <instance-name>:path to unmount.

        :raises MultipassError: On error.
        """
        try:
            self._run(["umount", mount])
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                command=error.command,
                exit_code=error.returncode,
                reason=f"Failed to unmount {mount!r}.",
            ) from error

    def transfer_from_io(
        self, *, source: IO, destination: str, bufsize: int = 1024
    ) -> None:
        """Transer to destination path with source IO.

        :param source: a file-like object to read from
        :param destination: the destination of the copied file, using syntax
            expected by multipass

        :raises MultipassError: On error.
        """
        assert isinstance(source, io.IOBase)

        # Cannot use std{in,out}=open(...) due to LP #1849753.
        command = [str(self.multipass_command), "transfer", "-", destination]
        proc = subprocess.Popen(command, stdin=subprocess.PIPE)

        while True:
            read = source.read(bufsize)
            if read:
                proc.stdin.write(read)
            if len(read) < bufsize:
                logger.debug("Finished streaming source file")
                break

        while True:
            try:
                out, err = proc.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                pass

            if proc.returncode == 0:
                logger.debug("Process completed")
                break
            elif proc.returncode is not None:
                raise MultipassError(
                    command=command,
                    exit_code=proc.returncode,
                    reason=f"Failed to transer file {destination!r} to source.",
                )

    def transfer_to_io(
        self, *, source: str, destination: IO, bufsize: int = 1024
    ) -> None:
        """Transer from source file to destination IO.

        :param source: The source file to copy, using syntax expected by
            multipass.
        :param destination: File-like object to write to.

        :raises MultipassError: On error.
        """
        assert isinstance(destination, io.IOBase)

        # can't use std{in,out}=open(...) due to LP#1849753
        command = ([str(self.multipass_path), "transfer", source, "-"],)
        proc = subprocess.Popen(
            command=command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
        )

        while True:
            written = proc.stdout.read(bufsize)
            if written:
                destination.write(written)

            if len(written) < bufsize:
                logger.debug("Finished streaming standard output")
                break

        while True:
            try:
                out, err = proc.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                continue

            if out:
                destination.write(out)

            if proc.returncode == 0:
                logger.debug("Process completed")
                break
            elif proc.returncode is not None:
                raise MultipassError(
                    command=command,
                    exit_code=proc.returncode,
                    reason=f"Failed to transer file {source!r} to destination.",
                )
