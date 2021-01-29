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

"""Host provider."""
import logging
from typing import Optional

from .host_executor import HostExecutor

logger = logging.getLogger(__name__)


class HostProvider:
    """Run commands directly on host."""

    def __init__(
        self,
        *,
        sudo_user: Optional[str] = "root",
    ) -> None:
        super().__init__()
        self.sudo_user = sudo_user

    def create_instance(self) -> HostExecutor:
        """Launch environment."""
        return HostExecutor(
            sudo_user=self.sudo_user,
        )
