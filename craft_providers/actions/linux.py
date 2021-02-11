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

"""Linux executor actions."""
import logging
import pathlib
import shutil
import subprocess
from textwrap import dedent
from time import sleep
from typing import Any, Dict, Optional

from craft_providers import Executor
from craft_providers.util.os_release import parse_os_release

logger = logging.getLogger(__name__)


def directory_sync_from_remote(
    *,
    executor: Executor,
    source: pathlib.Path,
    destination: pathlib.Path,
    delete: bool = False,
    host_tar_cmd: str = "tar",
    target_tar_cmd: str = "tar",
) -> None:
    """Naive sync from remote using tarball.

    Relies on only the required Executor.interfaces.

    :param source: Target directory to copy from.
    :param destination: Host destination directory to copy to.
    """
    destination_path = destination.as_posix()

    if delete and destination.exists():
        shutil.rmtree(destination)

    destination.mkdir(parents=True)

    archive_proc = executor.execute_popen(
        [host_tar_cmd, "cpf", "-", "-C", source.as_posix(), "."],
        stdout=subprocess.PIPE,
    )

    target_proc = subprocess.Popen(
        [target_tar_cmd, "xpvf", "-,", "-C", destination_path],
        stdin=archive_proc.stdout,
    )

    # Allow archive_proc to receive a SIGPIPE if destination_proc exits.
    if archive_proc.stdout:
        archive_proc.stdout.close()

    # Waot until done.
    target_proc.communicate()


def directory_sync_to_remote(
    *,
    executor: Executor,
    source: pathlib.Path,
    destination: pathlib.Path,
    delete=True,
    host_tar_cmd: str = "tar",
    target_tar_cmd: str = "tar",
) -> None:
    """Naive sync to remote using tarball.

    :param source: Host directory to copy.
    :param destination: Target destination directory to copy to.
    :param delete: Flag to delete existing destination, if exists.
    """
    destination_path = destination.as_posix()

    if delete is True:
        executor.execute_run(["rm", "-rf", destination_path], check=True)

    executor.execute_run(["mkdir", "-p", destination_path], check=True)

    archive_proc = subprocess.Popen(
        [host_tar_cmd, "cpf", "-", "-C", str(source), "."],
        stdout=subprocess.PIPE,
    )

    target_proc = executor.execute_popen(
        [target_tar_cmd, "xpvf", "-", "-C", destination_path],
        stdin=archive_proc.stdout,
    )

    # Allow archive_proc to receive a SIGPIPE if destination_proc exits.
    if archive_proc.stdout:
        archive_proc.stdout.close()

    # Waot until done.
    target_proc.communicate()


def configure_apt(self, *, executor: Executor) -> None:
    """Configure apt & update cache.

    :param executor: Executor for target container.
    """
    executor.execute_run(command=["apt-get", "update"], check=True)
    executor.execute_run(command=["apt-get", "install", "-y", "apt-utils"], check=True)


def configure_hostname(*, executor: Executor, hostname: str) -> None:
    """Configure hostname, installing /etc/hostname.

    :param executor: Executor for target container.
    """
    executor.create_file(
        destination=pathlib.Path("/etc/hostname"),
        content=hostname.encode(),
        file_mode="0644",
    )


def configure_networkd(*, executor: Executor, interface_name: str = "eth0") -> None:
    """Configure networkd and start it.

    Installs eth0 network configuration using ipv4.

    :param executor: Executor for target container.
    """
    executor.create_file(
        destination=pathlib.Path(f"/etc/systemd/network/10-{interface_name}.network"),
        content=dedent(
            f"""
            [Match]
            Name={interface_name}

            [Network]
            DHCP=ipv4
            LinkLocalAddressing=ipv6

            [DHCP]
            RouteMetric=100
            UseMTU=true
            """
        ).encode(),
        file_mode="0644",
    )

    executor.execute_run(
        command=["systemctl", "enable", "systemd-networkd"], check=True
    )

    executor.execute_run(
        command=["systemctl", "restart", "systemd-networkd"], check=True
    )


def configure_resolved(self, *, executor: Executor) -> None:
    """Configure system-resolved to manage resolve.conf.

    :param executor: Executor for target container.
    :param timeout_secs: Timeout in seconds.
    """
    executor.execute_run(
        command=[
            "ln",
            "-sf",
            "/run/systemd/resolve/resolv.conf",
            "/etc/resolv.conf",
        ],
        check=True,
    )

    executor.execute_run(
        command=["systemctl", "enable", "systemd-resolved"], check=True
    )

    executor.execute_run(
        command=["systemctl", "restart", "systemd-resolved"], check=True
    )


def configure_snapd(self, *, executor: Executor) -> None:
    """Install snapd and dependencies and wait until ready.

    :param executor: Executor for target container.
    :param timeout_secs: Timeout in seconds.
    """
    executor.execute_run(
        command=[
            "apt-get",
            "install",
            "fuse",
            "udev",
            "--yes",
        ],
        check=True,
    )

    executor.execute_run(command=["systemctl", "enable", "systemd-udevd"], check=True)
    executor.execute_run(command=["systemctl", "start", "systemd-udevd"], check=True)
    executor.execute_run(command=["apt-get", "install", "snapd", "--yes"], check=True)
    executor.execute_run(command=["systemctl", "start", "snapd.socket"], check=True)
    executor.execute_run(command=["systemctl", "start", "snapd.service"], check=True)
    executor.execute_run(command=["snap", "wait", "system", "seed.loaded"], check=True)


def is_target_directory(*, executor: Executor, target: pathlib.Path) -> bool:
    """Check if path is directory in executed environment.

    :param target: Path to check.

    :returns: True if directory, False otherwise.
    """
    proc = executor.execute_run(command=["test", "-d", target.as_posix()])
    return proc.returncode == 0


def is_target_file(*, executor: Executor, target: pathlib.Path) -> bool:
    """Check if path is file in executed environment.

    :param target: Path to check.

    :returns: True if file, False otherwise.
    """
    proc = executor.execute_run(command=["test", "-f", target.as_posix()])
    return proc.returncode == 0


def read_os_release(*, executor: Executor) -> Optional[Dict[str, Any]]:
    """Read & parse /etc/os-release.

    :param executor: Executor for target.

    :returns: Dictionary of parsed /etc/os-release, if present. Otherwise None.
    """
    try:
        proc = executor.execute_run(
            command=["cat", "/etc/os-release"],
            check=False,
            stdout=subprocess.PIPE,
        )
    except subprocess.CalledProcessError:
        return None

    return parse_os_release(proc.stdout.decode())


def wait_for_networking_ready(*, executor: Executor, timeout_secs: int = 60) -> None:
    """Wait until networking is ready.

    :param executor: Executor for target container.
    :param timeout_secs: Timeout in seconds.
    """
    logger.info("Waiting for networking to be ready...")
    for _ in range(timeout_secs * 2):
        proc = executor.execute_run(
            command=["getent", "hosts", "snapcraft.io"], stdout=subprocess.DEVNULL
        )
        if proc.returncode == 0:
            break

        sleep(0.5)
    else:
        logger.warning("Failed to setup networking.")


def wait_for_system_ready(
    *, executor: Executor, retry_count=120, retry_interval: float = 0.5
) -> None:
    """Wait until system is ready as defined by sysemctl is-system-running.

    :param executor: Executor for target container.
    :param retry_count: Number of times to check systemctl.
    :param retry_interval: Time between checks to systemctl.
    """
    logger.info("Waiting for container to be ready...")
    for _ in range(retry_count):
        proc = executor.execute_run(
            command=["systemctl", "is-system-running"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

        running_state = proc.stdout.decode().strip()
        if proc.returncode == 0:
            if running_state in ["running", "degraded"]:
                break

            logger.warning(
                "Unexpected state for systemctl is-system-running: %s",
                running_state,
            )

        sleep(retry_interval)
    else:
        logger.warning("System exceeded timeout to get ready.")
