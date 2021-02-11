#!/usr/bin/env python3
#
# Copyright 2021 Canonical Ltd.
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
from craft_providers.multipass import MultipassProvider


def test_multipass_provider():
    # Use 20.04 Image.
    alias = BuilddImageAlias.FOCAL
    image_name = "snapcraft:core20"

    # Use buildd image configuration.
    image_configuration = BuilddImage(alias=alias)
    instance_name = "starcraft-fun"

    provider = MultipassProvider()

    print("Installing Multipass...")
    provider.install()

    print("Creating build environment...")
    instance = provider.create_instance(
        image_configuration=image_configuration,
        image_name=image_name,
        name=instance_name,
        auto_clean=True,
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
    test_multipass_provider()
