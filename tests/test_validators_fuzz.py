"""
Validator dayanikliligi: bozuk girdi (string, None, float, bos liste/dict)
ASLA exception firlatmamali; bozuk COZUM ASLA gecerli sayilmamali.
(Arkadasimizin buldugu "sayi yerine string yazinca oyun coker" hatasinin regresyon testi.)
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents_examples.baseline import BaselineGenerator
from core.registry import _auto_register_defaults, get_validator, list_games

_auto_register_defaults()
BAD_VALUES = ("abc", None, 1.5, [], {})
SEEDS = (7, 8, 9)


def _leaves(node, path, out):
    if isinstance(node, list):
        for i, v in enumerate(node):
            _leaves(v, path + [i], out)
    elif isinstance(node, dict):
        for k, v in node.items():
            _leaves(v, path + [k], out)
    else:
        out.append(path)


def _set(obj, path, value):
    cur = obj
    for p in path[:-1]:
        cur = cur[p]
    cur[path[-1]] = value


class ValidatorFuzzTest(unittest.TestCase):
    def test_bozuk_girdi_cokertmez(self):
        gen = BaselineGenerator()
        for game in list_games():
            v = get_validator(game)
            for seed in SEEDS:
                puzzle, sol = gen.generate(game=game, difficulty=4, seed=seed)
                for target, base in (("puzzle", puzzle), ("solution", sol)):
                    paths = []
                    _leaves(base, [], paths)
                    for path in paths[:40]:
                        for bad in BAD_VALUES:
                            mutated = copy.deepcopy(base)
                            _set(mutated, path, bad)
                            with self.subTest(game=game, target=target, path=path, bad=repr(bad)):
                                if target == "puzzle":
                                    result = v.validate_puzzle_shape(mutated)
                                else:
                                    result = v.validate_solution(puzzle, mutated)
                                self.assertIsInstance(result, tuple)
                                self.assertEqual(len(result), 2)

    def test_string_iceren_cozum_gecersiz(self):
        gen = BaselineGenerator()
        for game in list_games():
            v = get_validator(game)
            for seed in SEEDS:
                puzzle, sol = gen.generate(game=game, difficulty=4, seed=seed)
                paths = []
                _leaves(sol, [], paths)
                for path in paths[:40]:
                    mutated = copy.deepcopy(sol)
                    _set(mutated, path, "abc")
                    with self.subTest(game=game, path=path):
                        ok, _err = v.validate_solution(puzzle, mutated)
                        self.assertFalse(ok, "string iceren cozum GECERLI sayildi")

    def test_komple_anlamsiz_girdiler(self):
        gen = BaselineGenerator()
        for game in list_games():
            v = get_validator(game)
            puzzle, sol = gen.generate(game=game, difficulty=3, seed=1)
            for junk in (None, "abc", 5, 1.5, [], {}, [[]], {"a": 1}, True):
                with self.subTest(game=game, junk=repr(junk)):
                    ok, _ = v.validate_solution(puzzle, junk)
                    self.assertFalse(ok)
                    ok, _ = v.validate_puzzle_shape(junk)
                    self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
