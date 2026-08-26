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

from abc import ABC, abstractmethod


class BasePuzzleValidator(ABC):
    game_name: str = "unnamed_game"

    @abstractmethod
    def validate_puzzle_shape(self, puzzle: dict) -> tuple[bool, str | None]:
        """(is_valid, error_message_or_None)"""
        raise NotImplementedError

    @abstractmethod
    def validate_solution(self, puzzle: dict, solution) -> tuple[bool, str | None]:
        """(is_valid, error_message_or_None)"""
        raise NotImplementedError
