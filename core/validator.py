"""
core/validator.py

Validator = HAKEM. Katılımcı yazmaz, sabittir. Görevi iki şey:

1. validate_puzzle_shape(puzzle)   -> bir generator'ın ürettiği puzzle
   formatça / kuralca tutarlı mı? (örn. checkpoint'ler grid içinde mi,
   blocked_cells checkpoint'lerle çakışmıyor mu?)

2. validate_solution(puzzle, solution) -> bir solver'ın verdiği çözüm
   gerçekten geçerli mi? (örn. Zip'te her hücreden tam 1 kez geçildi mi?)

Bu iki fonksiyon ayrı çünkü "kötü puzzle" (generator hatası) ile
"kötü çözüm" (solver hatası) birbirine karışmamalı -- benchmark'ta
ayrı ayrı raporlanacak.
"""

import functools
from abc import ABC, abstractmethod


def _crash_safe(fn):
    """
    Validator metodunu sarar: icinde herhangi bir istisna (TypeError,
    IndexError, KeyError, ...) olursa process'i dusurmek yerine
    (False, hata_mesaji) dondurur. Katilimci ciktisi (puzzle ya da solution)
    beklenmedik tipte degerler (ornegin sayi yerine string) icerebilir;
    hakem bunlar yuzunden asla cokmemeli, sadece "gecersiz" demeli.
    """
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except Exception as e:
            return False, (f"gecersiz girdi/format ({type(e).__name__}: {e}) -- degerlerin dogru tipte "
                           f"oldugundan emin olun (ornegin hucre koordinatlari tam sayi olmali)")
    return wrapper


class BasePuzzleValidator(ABC):
    game_name: str = "unnamed_game"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for name in ("validate_puzzle_shape", "validate_solution"):
            if name in cls.__dict__:
                setattr(cls, name, _crash_safe(cls.__dict__[name]))

    @abstractmethod
    def validate_puzzle_shape(self, puzzle: dict) -> tuple[bool, str | None]:
        """(is_valid, error_message_or_None)"""
        raise NotImplementedError

    @abstractmethod
    def validate_solution(self, puzzle: dict, solution) -> tuple[bool, str | None]:
        """(is_valid, error_message_or_None)"""
        raise NotImplementedError
