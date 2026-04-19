from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass(frozen=True)
class TeacherProfile:
    name: str
    profile_url: Optional[str]
    email: Optional[str]
    interests: List[str] = field(default_factory=list)
    title: Optional[str] = None
    source_url: str = ""


@dataclass(frozen=True)
class SourceRecord:
    school: str
    college: str
    url: str


@dataclass(frozen=True)
class Rule:
    name: str
    matcher: Callable[[str], bool]
    extractor: Callable[[str], List[str]]
    profile_extractor: Optional[Callable[[str, str], List[TeacherProfile]]] = None
