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
import yaml
from time import sleep

from craft_providers import Executor

logger = logging.getLogger(__name__)



def load_craft_config(
        *, executor: Executor, config_path: pathlib.Path
) -> Optional[Dict[str, Any]]:
    try:
        proc = executor.execute_run(
            command=["cat", "/etc/craft-image.conf"],
            check=True,
            stdout=subprocess.PIPE,
        )
    except subprocess.CalledProcessError:
        return None

    return yaml.load(proc.stdout, Loader=yaml.SafeLoader)

def save_craft_config(*, executor: Executor, config: Dict[str, Any], config_path: pathlib.Path) -> None:
    executor.create_file(
        destination=pathlib.Path("/etc/craft-image.conf"),
        content=yaml.dump(config).encode(),
        file_mode="0644",
    )
