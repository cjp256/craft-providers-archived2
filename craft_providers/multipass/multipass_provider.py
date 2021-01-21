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
import os
import sys
from typing import Dict, Optional

from .. import errors
from .._base_provider import Provider
from ._instance_info import InstanceInfo
from ._multipass_command import MultipassCommand

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

    def _setup_existing_instance(self, *, lxd_instance: LXDInstance) -> None:
        try:
            self.image_configuration.setup(executor=lxd_instance)
        except images.CompatibilityError as error:
            if self.auto_clean:
                logger.warning(
                    "Cleaning incompatible instance '%s' (%s).",
                    lxd_instance.name,
                    error.reason,
                )
                lxd_instance.delete(force=True)
            else:
                raise error

    def _setup_instance(
        self,
        *,
        instance: str,
        image: str,
        image_remote: str,
        ephemeral: bool,
    ) -> LXDInstance:
        lxd_instance = LXDInstance(
            name=instance,
            project=self.project,
            remote=self.remote,
            lxc=self.lxc,
        )
        multipass_instance = MultipassInstance(
            instance_name=self.instance_name,
            cpus=self.instance_cpus,
            disk=self.instance_disk,
            image=self.image_name,
            multipass=self.multipass,
        )

        # If instance already exists, special case it
        # to ensure the instance is cleaned if incompatible.
        if lxd_instance.exists():
            self._setup_existing_instance(lxd_instance=lxd_instance)

        if not lxd_instance.exists():
            lxd_instance.launch(
                image=image,
                image_remote=image_remote,
                ephemeral=ephemeral,
            )

        return lxd_instance

    def _setup_intermediate_image(self) -> str:
        intermediate_name = "-".join(
            [
                self.image_remote_name,
                f"r{self.image.compatibility_tag}",
            ]
        )

        image_list = self.lxc.image_list(project=self.project, remote=self.remote)
        for image in image_list:
            for alias in image["aliases"]:
                if intermediate_name == alias["name"]:
                    logger.info("Using intermediate image.")
                    return intermediate_name

        # Intermediate instances cannot be ephemeral. Publishing may fail.
        intermediate_instance = self._setup_instance(
            instance=intermediate_name,
            image=self.image.name,
            image_remote=self.image_remote_name,
            ephemeral=False,
        )

        # Publish intermediate image.
        self.lxc.publish(
            alias=intermediate_name,
            instance=intermediate_name,
            project=self.project,
            remote=self.remote,
            force=True,
        )

        # Nuke it.
        intermediate_instance.delete(force=True)
        return intermediate_name

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


class Multipass(Provider):
    """A multipass provider for snapcraft to execute its lifecycle."""

    def _start(self):
        try:
            self._get_instance_info()
        except errors.ProviderInfoError as instance_error:
            # Until we have proper multipass error codes to know if this
            # was a communication error we should keep this error tracking
            # and generation here.
            raise errors.ProviderInstanceNotFoundError(
                instance_name=self.instance_name
            ) from instance_error

        self._multipass_cmd.start(instance_name=self.instance_name)

    def _umount(self, *, mountpoint: str) -> None:
        mount = "{}:{}".format(self.instance_name, mountpoint)
        self._multipass_cmd.umount(mount=mount)

    def _push_file(self, *, source: str, destination: str) -> None:
        destination = "{}:{}".format(self.instance_name, destination)
        with open(source, "rb") as file:
            self._multipass_cmd.push_file(source=file, destination=destination)

    def __init__(
        self,
        *,
        project,
        echoer,
        is_ephemeral: bool = False,
        build_provider_flags: Dict[str, str] = None,
    ) -> None:
        super().__init__(
            project=project,
            echoer=echoer,
            is_ephemeral=is_ephemeral,
            build_provider_flags=build_provider_flags,
        )
        self._multipass_cmd = MultipassCommand(platform=sys.platform)
        self._instance_info: Optional[InstanceInfo] = None

    def create(self) -> None:
        """Create the multipass instance and setup the build environment."""
        self.echoer.info("Launching a VM.")
        self.launch_instance()
        self._instance_info = self._get_instance_info()
        self._mount_project()

    def destroy(self) -> None:
        """Destroy the instance, trying to stop it first."""
        try:
            instance_info = self._instance_info = self._get_instance_info()
        except errors.ProviderInfoError:
            return

        if instance_info.is_stopped():
            return

        stop_time = _get_stop_time()
        if stop_time > 0:
            try:
                self._multipass_cmd.stop(
                    instance_name=self.instance_name, time=stop_time
                )
            except errors.ProviderStopError:
                self._multipass_cmd.stop(instance_name=self.instance_name)
        else:
            self._multipass_cmd.stop(instance_name=self.instance_name)

        if self._is_ephemeral:
            self.clean_project()

    def _is_mounted(self, target: str) -> bool:
        """Query if there is a mount at target mount point."""
        if self._instance_info is None:
            return False

        return self._instance_info.is_mounted(target)

    def _mount(self, host_source: str, target: str) -> None:
        """Mount host source directory to target mount point."""
        if self._is_mounted(target):
            # Nothing to do if already mounted.
            return

        target = "{}:{}".format(self.instance_name, target)
        if sys.platform != "win32":
            uid_map = {str(os.getuid()): "0"}
            gid_map = {str(os.getgid()): "0"}
        else:
            uid_map = {"0": "0"}
            gid_map = {"0": "0"}
        self._multipass_cmd.mount(
            source=host_source, target=target, uid_map=uid_map, gid_map=gid_map
        )

    def clean_project(self) -> bool:
        was_cleaned = super().clean_project()
        if self._multipass_cmd.exists(instance_name=self.instance_name):
            self._multipass_cmd.delete(instance_name=self.instance_name, purge=True)
            return True
        return was_cleaned

    def pull_file(self, name: str, destination: str, delete: bool = False) -> None:
        # TODO add instance check.

        # check if file exists in instance
        self._run(command=["test", "-f", name])

        # copy file from instance
        source = "{}:{}".format(self.instance_name, name)
        with open(destination, "wb") as file:
            self._multipass_cmd.pull_file(source=source, destination=file)
        if delete:
            self._run(command=["rm", name])

    def shell(self) -> None:
        self._run(command=["/bin/bash", "-i"])

    def _get_instance_info(self):
        instance_info_raw = self._multipass_cmd.info(
            instance_name=self.instance_name, output_format="json"
        )
        return InstanceInfo.from_json(
            instance_name=self.instance_name, json_info=instance_info_raw.decode()
        )
