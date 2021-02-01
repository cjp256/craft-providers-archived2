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
import subprocess
from time import sleep

from craft_providers import Executor

logger = logging.getLogger(__name__)


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
