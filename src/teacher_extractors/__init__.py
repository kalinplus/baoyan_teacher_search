from __future__ import annotations

from typing import List

from teacher_list_core import Rule
from . import thu


def get_rules() -> List[Rule]:
    return [
        *thu.get_rules(),
    ]
