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
import pathlib
import sys
from typing import Optional

from craft_providers import Provider, images

from .multipass import Multipass
from .multipass_installer import MultipassInstaller
from .multipass_instance import MultipassInstance

logger = logging.getLogger(__name__)


class MultipassProviderError(Exception):
    """Multipass provider error.

    :param msg: Reason for provider error.
    """

    def __init__(self, msg: str) -> None:
        super().__init__()

        self.msg = msg

    def __str__(self) -> str:
        return self.msg


class MultipassProvider(Provider):
    """Multipass Provider.

    :param auto_clean: Automatically clean instances if required (e.g.
        incompatible).
    :param image_configuration: Image configuration.
    :param image_name: Image to use: [[<remote:>]<image> | <url>].
    :param instance: Specify MultipassInstance to use, rather than create.
    :param instance_cpus: Number of CPUs.
    :param instance_disk_gb: Disk allocation in gigabytes.
    :param instance_mem_gb: Memory allocation in gigabytes.
    :param instance_name: Name of instance to use/create.
    :param instance_stop_time_mins: Stop time delay in minutes.
    :param multipass: Multipass client API provider.
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        *,
        auto_clean: bool = True,
        image_configuration: images.Image,
        image_name: str = "snapcraft:core20",
        instance: Optional[MultipassInstance] = None,
        instance_cpus: int = 2,
        instance_disk_gb: int = 256,
        instance_mem_gb: int = 2,
        instance_name: str,
        instance_stop_time_mins: int = 10,
        input_handler=input,
        multipass: Optional[Multipass] = None,
        multipass_installer: Optional[MultipassInstaller] = None,
        platform: str = sys.platform,
    ):
        super().__init__()

        self.auto_clean = auto_clean
        self.image_configuration = image_configuration
        self.image_name = image_name
        self.instance = instance
        self.instance_cpus = instance_cpus
        self.instance_disk_gb = instance_disk_gb
        self.instance_mem_gb = instance_mem_gb
        self.instance_name = instance_name
        self.instance_stop_time_mins = instance_stop_time_mins

        if multipass is None:
            self._multipass = Multipass(multipass_path=pathlib.Path("multipass"))
        else:
            self._multipass = multipass

        if multipass_installer is None:
            self._multipass_installer = MultipassInstaller(
                input_handler=input_handler, platform=platform
            )
        else:
            self._multipass_installer = multipass_installer

        self._platform = platform

    def setup(
        self,
    ) -> MultipassInstance:
        """Create, start, and configure instance as necessary.

        :param input_handler: Input function with prompt parameter.  Defaults to
            input().
        :param platform: Running platform.  Defaults to sys.platform.

        :returns: Multipass instance.

        :raises MultipassProviderError: If platform unsupported or unable to
            instantiate VM.
        """
        multipass_path = self._multipass_installer.install()

        # Update API object to utilize discovered path.
        self._multipass.multipass_path = multipass_path

        return self._setup_instance()

    def _setup_existing_instance(self, *, instance: MultipassInstance) -> None:
        try:
            self.image_configuration.setup(executor=instance)
        except images.CompatibilityError as error:
            if self.auto_clean:
                logger.warning(
                    "Cleaning incompatible instance '%s' (%s).",
                    instance.name,
                    error.reason,
                )
                instance.delete(purge=True)
            else:
                raise error

    def _setup_instance(self) -> MultipassInstance:
        """Launch, start and configure instance, ensuring existing instances are compatible."""
        instance = MultipassInstance(
            name=self.instance_name,
            multipass=self._multipass,
        )

        if instance.exists():
            self._setup_existing_instance(instance=instance)

        if not instance.exists():
            instance.launch(
                cpus=self.instance_cpus,
                disk_gb=self.instance_disk_gb,
                mem_gb=self.instance_mem_gb,
                image=self.image_name,
            )

        return instance

    def teardown(self, *, clean: bool = False) -> None:
        """Tear down environment.

        :param clean: Purge environment if True.
        """
        if self.instance is None:
            return

        if not self.instance.exists():
            return

        if self.instance.is_running():
            self.instance.stop()

        if clean:
            self.instance.delete(purge=True)
