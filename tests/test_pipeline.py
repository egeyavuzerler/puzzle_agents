"""
Uctan uca duman testi: 10 oyun -> bank -> solver maci -> turnuva.
"""
import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bank.build_bank as bb
from agents_examples.baseline import BaselineGenerator, BaselineSolver
from arena.run_match import run_match
from arena.run_tournament import parse_team_spec, run_tournament
from core.registry import _auto_register_defaults, list_games

_auto_register_defaults()


class PipelineTest(unittest.TestCase):
    def test_10_oyun_bank_ve_mac(self):
        self.assertEqual(len(list_games()), 10)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "bank.jsonl")
            result = bb.build_bank(BaselineGenerator(), 5, out)
            self.assertEqual(result["written"], 50)
            self.assertEqual(result["failed_shape"] + result["failed_solution"] + result["failed_error"], 0)
            summary = run_match(BaselineSolver(), out, 3, 6)
            self.assertEqual(summary["total_puzzles"], 50)
            self.assertGreaterEqual(summary["solve_rate"], 0.6)

    def test_turnuva_iki_takim(self):
        spec = "agents_examples.baseline:BaselineGenerator:BaselineSolver"
        teams = [parse_team_spec(f"{n}:{spec}") for n in ("a", "b")]
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                res = run_tournament(teams, 2, tmp, 3, 6, 1024, 60)
        self.assertEqual(set(res["generator_scores"]), {"a", "b"})
        for score in list(res["generator_scores"].values()) + list(res["solver_scores"].values()):
            self.assertTrue(0.0 <= score <= 1.0)


if __name__ == "__main__":
    unittest.main()
