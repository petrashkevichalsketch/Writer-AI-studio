from .registry import REGISTRY, StageSpec, register, get
from .runner import run_stage
from . import phase1_world   # noqa: F401  — стадии Фазы 1
from . import phase2_story   # noqa: F401  — стадии Фазы 2

__all__ = ["REGISTRY", "StageSpec", "register", "get", "run_stage"]