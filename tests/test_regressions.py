"""
Daha once yakalanmis hatalarin tekrar girmesini onleyen testler.
"""
import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arena.run_tournament import print_leaderboard


class LeaderboardTest(unittest.TestCase):
    def test_siralamalar_yuksekten_dusuge(self):
        result = {
            "teams": ["a", "b", "c"],
            "matrix": {t: {s: 0.5 for s in "abc"} for t in "abc"},
            "solver_scores": {"a": 0.2, "b": 0.9, "c": 0.5},
            "generator_scores": {"a": 0.1, "b": 0.8, "c": 0.4},
        }
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            print_leaderboard(result)
        text = buf.getvalue()
        solver_part = text.split("SOLVER SIRALAMASI")[1].split("GENERATOR SIRALAMASI")[0]
        gen_part = text.split("GENERATOR SIRALAMASI")[1].split("TAM MATRIS")[0]
        order = lambda part: [ln.split()[0] for ln in part.splitlines() if ln.startswith("  ") and ln.strip()]
        self.assertEqual(order(solver_part), ["b", "c", "a"])
        self.assertEqual(order(gen_part), ["b", "c", "a"])


@unittest.skipUnless(importlib.util.find_spec("matplotlib"), "matplotlib yok")
class LiveViewTest(unittest.TestCase):
    def test_serbest_hucre_sayisi(self):
        import matplotlib
        matplotlib.use("Agg")
        from core.live_view import LiveZipView
        puzzle = {"game": "zip", "size": [5, 5],
                  "checkpoints": [{"order": 1, "pos": [0, 0]}, {"order": 2, "pos": [4, 4]}],
                  "blocked_cells": [[2, 2], [1, 3]]}
        with contextlib.redirect_stdout(io.StringIO()):
            view = LiveZipView(puzzle)
        self.assertEqual(view.free_total, 5 * 5 - 2)


if __name__ == "__main__":
    unittest.main()
