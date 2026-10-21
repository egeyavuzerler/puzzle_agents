"""
Katilimci kodu (generator / solver) kotu davransa hakem DUSMEZ; sadece o cagri basarisiz sayilir.
"""
import json
import multiprocessing as mp
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bank.build_bank as bb
from agents_examples import evil_generators as eg
from agents_examples.baseline import BaselineGenerator
from arena.run_match import run_match
from arena.sandboxed_solver import SandboxedSolver
from agents_examples.baseline import BaselineSolver
from agents_examples import evil_solvers as es

GAMES = ["zip", "queens"]


class GeneratorIzolasyonTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch("bank.build_bank.list_games", return_value=GAMES)
        p.start()
        self.addCleanup(p.stop)

    def _build(self, generator, retries=2, timeout=1.5):
        out = os.path.join(self.tmp.name, "bank.jsonl")
        return bb.build_bank(generator, 2, out, max_retries_per_puzzle=retries, gen_timeout_s=timeout)

    def test_kotu_generatorlar_hakemi_dusurmez(self):
        n = 2 * len(GAMES)
        cases = [
            (eg.HangingGenerator, "failed_error"),
            (eg.CrashingGenerator, "failed_error"),
            (eg.RaisingGenerator, "failed_error"),
            (eg.MemoryHogGenerator, "failed_error"),
            (eg.GarbageGenerator, "failed_shape"),
            (eg.NotADictGenerator, "failed_shape"),
            (eg.NonSerializableGenerator, "failed_shape"),
        ]
        for cls, counter in cases:
            with self.subTest(generator=cls.__name__):
                result = self._build(cls())
                self.assertEqual(result["written"], 0)
                self.assertEqual(result[counter], n)

    def test_takilan_cagri_sonrasi_devam_eder(self):
        result = self._build(eg.FlakyGenerator())
        self.assertEqual(result["written"], 2 * len(GAMES))

    def test_artik_process_kalmaz(self):
        self._build(eg.HangingGenerator())
        self.assertEqual(mp.active_children(), [])


class SolverIzolasyonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.bank = os.path.join(cls.tmp.name, "bank.jsonl")
        with mock.patch("bank.build_bank.list_games", return_value=GAMES):
            bb.build_bank(BaselineGenerator(), 4, cls.bank)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _match(self, solver, **kw):
        try:
            return run_match(solver, self.bank, kw.get("time_limit", 3), kw.get("hard", 5))
        finally:
            if hasattr(solver, "close"):
                solver.close()

    def test_local_sandbox_eski_modla_ayni_sonuc(self):
        eski = self._match(BaselineSolver())
        yeni = self._match(SandboxedSolver("agents_examples.baseline:BaselineSolver", mode="local"))
        self.assertEqual(eski["total_solved"], yeni["total_solved"])
        self.assertGreater(yeni["total_solved"], 0)

    def test_kotu_solverlar_hakemi_dusurmez(self):
        cases = [es.InfiniteLoopSolver, es.MemoryBombSolver, es.CrashingSolver, es.BigAnswerSolver]
        for cls in cases:
            with self.subTest(solver=cls.__name__):
                spec = f"agents_examples.evil_solvers:{cls.__name__}"
                with SandboxedSolver(spec, mode="local", child_stderr=subprocess.DEVNULL) as solver:
                    result = run_match(solver, self.bank, 1, 2, max_puzzles=3)
                self.assertEqual(result["total_puzzles"], 3)
                self.assertEqual(result["total_solved"], 0)

    def test_stdout_spam_protokolu_bozmaz(self):
        spec = "agents_examples.evil_solvers:StdoutSpamSolver"
        spam = self._match(SandboxedSolver(spec, mode="local", child_stderr=subprocess.DEVNULL))
        temiz = self._match(SandboxedSolver("agents_examples.baseline:BaselineSolver", mode="local"))
        self.assertEqual(spam["total_solved"], temiz["total_solved"])

    def test_string_cozum_cokertmez_gecersiz_sayilir(self):
        """Eski hata: validator TypeError firlatip tum maci dusuruyordu."""
        result = self._match(es.StringAnswerSolver())
        self.assertEqual(result["total_solved"], 0)
        self.assertEqual(result["per_game"]["zip"]["invalid_solution"], 4)

    def test_olmayan_solver_modulu_hata_verir_dusmez(self):
        with SandboxedSolver("yok_boyle_modul:Yok", mode="local", child_stderr=subprocess.DEVNULL) as solver:
            result = run_match(solver, self.bank, 1, 2, max_puzzles=2)
        self.assertEqual(result["total_solved"], 0)


if __name__ == "__main__":
    unittest.main()
