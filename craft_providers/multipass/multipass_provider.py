# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2018-2020 Canonical Ltd
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

import logging
import sys
from typing import Optional

from .._base_provider import Provider

logger = logging.getLogger(__name__)


def _get_disk_image(self) -> str:
    return "snapcraft:{}".format(self.project._get_build_base())


class MultipassProviderError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason

    def __str__(self) -> str:
        return self.reason


class MultipassProvider(Provider):
    """Multipass Provider.

    :param auto_clean: Automatically clean LXD instances if required (e.g.
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
        instance: Optional[MultipassInstance] = None,
        instance_cpus: int = 2,
        instance_disk_gb: int = 256,
        instance_mem_gb: int = 2,
        instance_name: str,
        instance_stop_time_mins: int = 10,
        multipass: Optional[Multipass] = None,
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
            self.multipass = Multipass()
        else:
            self.multipass = multipass

    def setup(self, *, input_prompt=input, platform=sys.platform) -> LXDInstance:
        """Create, start, and configure instance as necessary.

        :param input_prompt: Input function with prompt parameter.  Defaults to
            input().
        :param platform: Running platform.  Defaults to sys.platform.

        :returns: Multipass instance.

        :raises MultipassProviderError: If platform unsupported or unable to
            instantiate VM.
        """
        self.instance = self._setup_instance(
            image_configuration=self.image_configuration,
            image_name=self.image_name,
            instance_name=self.instance_name,
        )

        return self.instance

    def _setup_multipass(
        self, *, input_prompt=input, platform=sys.platform
    ) -> pathlib.Path:
        if self.multipass_path.exists():
            return self.multipass_path

        if platform == "win32":
            # Ensure Windows PATH is up to date.
            windows.reload_multipass_path_env()

        multipass_path = path.which("multipass")
        if path.which("multipass") is not None:
            return multipass_path

            windows.install_multipass(input_prompt=input_prompt)
            windows.reload_multipass_path_env()
        elif platform == "linux":
            linux.install_multipass(input_prompt=input_prompt)
        elif platform == "macos":
            macos.install_multipass(input_prompt=input_prompt)
        else:
            raise MultipassProviderError(
                reason="Unsupported platform for Multipass: {platform}"
            )

    def _setup_existing_instance(self, *, instance: LXDInstance) -> None:
        try:
            self.image_configuration.setup(executor=instance)
        except images.CompatibilityError as error:
            if self.auto_clean:
                logger.warning(
                    "Cleaning incompatible instance '%s' (%s).",
                    instance.name,
                    error.reason,
                )
                instance.delete(force=True)
            else:
                raise error

    def _setup_instance(
        self,
        *,
        instance: str,
        image: str,
        image_remote: str,
        ephemeral: bool,
    ) -> MultipassInstance:
        instance = MultipassInstance(
            instance_name=self.instance_name,
            multipass=self.multipass,
        )

        # If instance already exists, special case it
        # to ensure the instance is cleaned if incompatible.
        if instance.exists():
            self._setup_existing_instance(instance=instance)

        if not instance.exists():
            instance.launch(
                name=self.name,
                cpus=self.instance_cpus,
                disk=self.instance_disk,
                image=self.image,
            )

        return instance

    def _setup_project(self) -> None:
        projects = self.lxc.project_list(remote=self.remote)
        if self.project in projects:
            return

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
            self.instance.delete(force=True)
