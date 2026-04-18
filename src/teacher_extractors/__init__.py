from __future__ import annotations

from typing import List

from teacher_list_core import Rule
from . import sjtu
from . import thu


def get_rules() -> List[Rule]:
    return [
        *sjtu.get_rules(),
        *thu.get_rules(),
    ]
