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

import io
import pathlib
import subprocess


def test_exec(instance, multipass):
    proc = multipass.exec(
        instance_name=instance,
        command=["echo", "this is a test"],
        capture_output=True,
    )

    assert proc.stdout == b"this is a test\n"


def test_delete(instance, multipass):
    multipass.delete(instance_name=instance, purge=False)

    instances = multipass.list()

    assert instance not in instances


def test_delete_purge(instance, multipass):
    multipass.delete(instance_name=instance, purge=True)

    instances = multipass.list()

    assert instance not in instances


def test_list(instance, multipass):
    instances = multipass.list()

    assert instance in instances


def test_transfer_push(instance, multipass, tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("this is a test")

    multipass.transfer(
        instance_name=instance,
        source=str(test_file),
        destination=f"{instance}:/tmp/foo",
    )

    proc = multipass.exec(
        command=["cat", "/tmp/foo"],
        instance_name=instance,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )

    assert proc.stdout == b"this is a test"

def test_transfer_from_io(instance, multipass, tmp_path):
    test_file = tmp_path / "test.txt"
    test_io = io.StringIO("this is a test")

    multipass.transfer_from_io(
        instance_name=instance,
        source=test_io,
        destination=f"{instance}:/tmp/foo",
    )

    proc = multipass.transfer(
        command=["cat", "/tmp/foo"],
        instance_name=instance,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )

    assert proc.stdout == b"this is a test"

def test_transfer_pull(instance, multipass, tmp_path):
    out_path = tmp_path / "out.txt"
    test_file = tmp_path / "test.txt"
    test_file.write_text("this is a test")

    multipass.transfer(
        instance_name=instance,
        source=str(test_file),
        destination=f"{instance}:/tmp/foo",
    )

    multipass.transfer(
        instance_name=instance,
        source=f"{instance}:/tmp/foo",
        destination=str(out_path),
    )

    assert out_path.read_text() == "this is a test"
