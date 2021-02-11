#!/usr/bin/env python3
#
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

import subprocess

from craft_providers.images import BuilddImage, BuilddImageAlias
from craft_providers.lxd import LXDProvider, lxc


def test_lxd_provider():
    instance_name = "xcraft-fun"
    remote = "local"
    project = "xcraft"

    # Use 20.04 Image.
    alias = BuilddImageAlias.FOCAL

    # Use buildd image configuration.
    image_configuration = BuilddImage(alias=alias)
    provider = LXDProvider()

    print("Installing LXD...")
    provider.install()

    print("Creating fresh project...")
    lxc.purge_project(lxc=lxc.LXC(), project="xcraft", remote="local")
    provider.create_project(
        name=project,
        remote=remote,
    )

    if not provider.is_image_remote_installed(name="buildd"):
        print("Adding remote for buildd images...")
        provider.create_image_remote(
            name="buildd",
            addr="https://cloud-images.ubuntu.com/buildd/releases",
            protocol="simplestreams",
        )

    print("Creating build environment...")
    instance = provider.create_instance(
        image_configuration=image_configuration,
        image_name="core20",
        image_remote="buildd",
        name=instance_name,
        auto_clean=True,
        project=project,
        remote=remote,
    )

    print("Installing Snapcraft into build environment...")
    instance.execute_run(["snap", "install", "snapcraft", "--classic"], check=True)

    instance.stop()
    instance.start()

    proc = instance.execute_run(
        ["snapcraft", "version"], check=True, stdout=subprocess.PIPE
    )
    version = proc.stdout.decode().strip()
    print("Running:", version)

    print("Cleaning up build environment...")
    instance.delete()


if __name__ == "__main__":
    test_lxd_provider()
