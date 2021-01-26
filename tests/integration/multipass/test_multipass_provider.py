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

import pathlib
import subprocess
import textwrap

import pytest

from craft_providers import images, multipass
from craft_providers.images import BuilddImage, BuilddImageAlias


@pytest.mark.parametrize(
    "alias,image_name",
    [
        (BuilddImageAlias.XENIAL, "snapcraft:core"),
        (BuilddImageAlias.BIONIC, "snapcraft:core18"),
        (BuilddImageAlias.FOCAL, "snapcraft:core20"),
    ],
)
def test_multipass_provider(instance_name, alias, image_name):
    image_configuration = BuilddImage(alias=alias)
    provider = multipass.MultipassProvider(
        image_configuration=image_configuration,
        image_name=image_name,
        instance_cpus=2,
        instance_disk_gb=128,
        instance_name=instance_name,
        instance_stop_time_mins=0,
    )

    instance = provider.setup()

    assert isinstance(instance, multipass.MultipassInstance)
    assert instance.exists() is True
    assert instance.is_running() is True

    proc = instance.execute_run(["echo", "hi"], check=True, stdout=subprocess.PIPE)

    assert proc.stdout == b"hi\n"

    provider.teardown(clean=False)

    assert instance.exists() is True
    assert instance.is_running() is False

    provider.teardown(clean=True)

    assert instance.exists() is False
    assert instance.is_running() is False


def test_incompatible_instance_compatibility_tag(
    multipass, instance_launcher, instance_name, home_tmp_path
):
    alias = BuilddImageAlias.XENIAL
    image = BuilddImage(alias=alias)
    instance = instance_launcher(
        instance_name=instance_name,
        image_name="snapcraft:core",
    )

    # Insert incompatible config.
    instance.create_file(
        destination=pathlib.Path("/etc/craft-image.conf"),
        content="compatibility_tag: craft-buildd-image-vX".encode(),
        file_mode="0644",
    )

    with pytest.raises(images.CompatibilityError) as exc_info:
        provider = multipass.MultipassProvider(
            image_configuration=image,
            instance_name=instance_name,
        )
        provider.setup()

    assert (
        exc_info.value.reason
        == "Expected image compatibility tag 'craft-buildd-image-v0', found 'craft-buildd-image-vX'"
    )


def test_incompatible_instance_os(
    lxc, project, instance_name, instance_launcher, tmp_path
):
    alias = BuilddImageAlias.XENIAL
    instance_launcher(
        config_keys=dict(),
        instance_name=instance_name,
        image_remote="ubuntu",
        image=str(alias.value),
        project=project,
        ephemeral=False,
    )

    # Insert incompatible config.
    test_file = tmp_path / "os-release"
    test_file.write_text(
        textwrap.dedent(
            """
            NAME="Ubuntu"
            VERSION="20.10 (Groovy Gorilla)"
            ID=ubuntu
            ID_LIKE=debian
            PRETTY_NAME="Ubuntu 20.10"
            VERSION_ID="20.10"
            HOME_URL="https://www.ubuntu.com/"
            SUPPORT_URL="https://help.ubuntu.com/"
            BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
            PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
            VERSION_CODENAME=groovy
            UBUNTU_CODENAME=groovy
            """
        )
    )
    lxc.file_push(
        instance=instance_name,
        project=project,
        source=test_file,
        destination=pathlib.Path("/etc/os-release"),
    )

    image = BuilddImage(alias=alias)

    with pytest.raises(images.CompatibilityError) as exc_info:
        provider = multipass.MultipassProvider(
            instance_name=instance_name,
            image=image,
            image_remote_addr="https://cloud-images.ubuntu.com/buildd/releases",
            image_remote_name="ubuntu",
            image_remote_protocol="simplestreams",
            lxc=lxc,
            use_ephemeral_instances=False,
            use_intermediate_image=False,
            project=project,
            remote="local",
            auto_clean=False,
        )
        provider.setup()

    assert (
        exc_info.value.reason == f"Expected OS version '{alias.value!s}', found '20.10'"
    )

    multipass.MultipassProvider(
        instance_name=instance_name,
        image=image,
        image_remote_addr="https://cloud-images.ubuntu.com/buildd/releases",
        image_remote_name="ubuntu",
        image_remote_protocol="simplestreams",
        lxc=lxc,
        use_ephemeral_instances=False,
        use_intermediate_image=False,
        project=project,
        remote="local",
        auto_clean=True,
    )
