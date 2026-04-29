from __future__ import annotations

from typing import List

from teacher_list_models import Rule
from . import fdu
from . import nju
from . import pku
from . import ruc
from . import sii
from . import sjtu
from . import thu
from . import zju


def get_rules() -> List[Rule]:
    return [
        *fdu.get_rules(),
        *nju.get_rules(),
        *pku.get_rules(),
        *ruc.get_rules(),
        *sii.get_rules(),
        *sjtu.get_rules(),
        *thu.get_rules(),
        *zju.get_rules(),
    ]
