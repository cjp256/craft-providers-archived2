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

"""Multipass Provider."""

import logging
import sys
from dataclasses import dataclass

from craft_providers import images

from . import multipass_installer
from .multipass import Multipass
from .multipass_instance import MultipassInstance

logger = logging.getLogger(__name__)


@dataclass
class MultipassProviderOptions:
    """Multipass Provider Options."""


class MultipassProviderError(Exception):
    """Multipass provider error.

    :param msg: Reason for provider error.
    """

    def __init__(self, msg: str) -> None:
        super().__init__()

        self.msg = msg

    def __str__(self) -> str:
        return self.msg


class MultipassProvider:
    """Multipass Provider.

    :param auto_clean: Automatically clean instances if required (e.g. if
        incompatible).
    :param instance_image_name: Multipass image to use [[<remote:>]<image> | <url>].
    :param instance_name: Name of instance to use/create. e.g. "snapcraft:core20"
    :param instance_cpus: Number of CPUs.
    :param instance_disk_gb: Disk allocation in gigabytes.
    :param instance_mem_gb: Memory allocation in gigabytes.
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        *,
        image_configuration: images.Image,
        image_name: str,
        instance_name: str,
        auto_clean: bool = True,
        instance_cpus: int = 2,
        instance_disk_gb: int = 256,
        instance_mem_gb: int = 2,
        instance_stop_delay_mins: int = 0,
        platform: str = sys.platform,
    ) -> None:
        self._image_configuration = image_configuration
        self._image_name = image_name
        self._instance_name = instance_name
        self._auto_clean = auto_clean
        self._instance_cpus = instance_cpus
        self._instance_disk_gb = instance_disk_gb
        self._instance_mem_gb = instance_mem_gb
        self._instance_stop_delay_mins = instance_stop_delay_mins
        self._platform = platform

    def is_installed(self) -> bool:
        """Check if Multipass is installed."""
        return multipass_installer.is_installed()

    def install(self) -> None:
        """Install Multipass."""
        multipass_installer.install(platform=self._platform)

    def setup(
        self,
    ) -> MultipassInstance:
        """Create, start, and configure instance as necessary.

        :param name: Name of instance.

        :returns: Multipass instance.
        """
        # Update API object to utilize discovered path.
        multipass_path = multipass_installer.find_multipass()
        if multipass_path is None:
            raise MultipassProviderError("Multipass not found.")

        multipass = Multipass(multipass_path=multipass_path)

        instance = MultipassInstance(
            name=self._instance_name,
            multipass=multipass,
        )

        if instance.exists():
            self._setup_existing_instance(
                instance=instance,
                auto_clean=self._auto_clean,
                image_configuration=self._image_configuration,
            )

        # Re-check if instance exists as it may been cleaned.
        # If it doesn't exist, launch a fresh instance.
        if not instance.exists():
            instance.launch(
                cpus=self._instance_cpus,
                disk_gb=self._instance_disk_gb,
                mem_gb=self._instance_mem_gb,
                image=self._image_name,
            )

        self._setup_existing_instance(
            instance=instance,
            auto_clean=False,
            image_configuration=self._image_configuration,
        )
        return instance

    def _setup_existing_instance(
        self,
        *,
        instance: MultipassInstance,
        auto_clean: bool,
        image_configuration: images.Image,
    ) -> None:
        # Ensure instance is started and reset any delayed-shutdown request.
        instance.start()

        try:
            image_configuration.setup(executor=instance)
        except images.CompatibilityError as error:
            if auto_clean:
                logger.warning(
                    "Cleaning incompatible instance '%s' (%s).",
                    instance.name,
                    error.reason,
                )
                instance.delete(purge=True)
            else:
                raise error

    def teardown(
        self, *, instance: MultipassInstance, clean: bool, delay_shutdown_mins: int = 10
    ) -> None:
        """Tear down environment.

        :param clean: Purge environment if True.
        :param delay_shutdown_mins: Delay stopping VM for specified time.
        """
        if not instance.exists():
            return

        if instance.is_running():
            instance.stop(delay_mins=delay_shutdown_mins)

        if clean:
            instance.delete(purge=True)
