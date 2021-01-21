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

"""Input-related helpers."""
from typing import Optional


def input_prompt(
    prompt: str, *, input_handler=input, default: Optional[str] = None
) -> str:
    resp = input_handler(prompt)
    if resp == "" and default is not None:
        resp = default

    return resp


def input_prompt_bool(
    prompt: str,
    *,
    input_handler=input,
    default: bool = False,
    retry_invalid: bool = True
) -> bool:
    if default:
        prompt += " [y|N] "
        default_resp = "N"
    else:
        prompt += " [Y|n] "
        default_resp = "Y"

    while True:
        resp = input_prompt(prompt, input_handler=input_handler, default=default_resp)

        if resp.upper() in ["Y", "YE", "YES"]:
            return True

        # Retry if require_valid and answer is not valid "no".
        if retry_invalid and resp.upper() not in ["N", "NO"]:
            continue

        return False
