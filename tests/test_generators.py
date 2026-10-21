"""
Referans generator'lar: uretilen her puzzle sekil olarak gecerli ve verilen
witness solution GERCEKTEN puzzle'i cozuyor olmali (unsolvable puzzle korumasinin temeli).
Ayrica zorluk etiketi ile gercek icerik arasindaki iliskiyi (Zip checkpoint yogunlugu) denetler.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents_examples.baseline import BaselineGenerator
from core.registry import _auto_register_defaults, get_validator, list_games

_auto_register_defaults()


class WitnessTest(unittest.TestCase):
    def test_her_oyun_her_zorluk_gecerli_witness(self):
        gen = BaselineGenerator()
        for game in list_games():
            v = get_validator(game)
            for difficulty in (1, 3, 5, 7, 10):
                for seed in (11, 12):
                    with self.subTest(game=game, difficulty=difficulty, seed=seed):
                        puzzle, solution = gen.generate(game=game, difficulty=difficulty, seed=seed)
                        self.assertEqual(puzzle.get("game"), game)
                        ok, err = v.validate_puzzle_shape(puzzle)
                        self.assertTrue(ok, f"sekil gecersiz: {err}")
                        ok, err = v.validate_solution(puzzle, solution)
                        self.assertTrue(ok, f"witness gecersiz: {err}")

    def test_ayni_seed_ayni_puzzle(self):
        gen = BaselineGenerator()
        for game in list_games():
            with self.subTest(game=game):
                a = gen.generate(game=game, difficulty=5, seed=123)
                b = gen.generate(game=game, difficulty=5, seed=123)
                self.assertEqual(a, b, "ayni seed farkli puzzle uretti (tekrar uretilebilirlik bozuk)")


class ZipZorlukTest(unittest.TestCase):
    def test_checkpoint_yogunlugu_zorlukla_azalmaz(self):
        """Zorluk arttikca checkpoint sayisi ORTALAMADA dusmemeli
        (zorluk etiketiyle icerik arasindaki iliski tersine donmus olmasin)."""
        gen = BaselineGenerator()

        def mean_cp(difficulty):
            counts = [len(gen.generate(game="zip", difficulty=difficulty, seed=s)[0]["checkpoints"])
                      for s in range(20)]
            return sum(counts) / len(counts)

        low, high = mean_cp(2), mean_cp(10)
        self.assertGreaterEqual(high, low, f"zorluk 10 ortalama {high} checkpoint, zorluk 2 ortalama {low}")


if __name__ == "__main__":
    unittest.main()
