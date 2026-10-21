"""
arena/check_submission.py: saglikli gonderim gecer, bozuk gonderim anlasilir hatalarla yakalanir.
"""
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from arena.check_submission import run_checks

BAD_AGENT = textwrap.dedent('''
    from agents_examples.baseline import BaselineGenerator, BaselineSolver
    from core.base import SolveResult

    class BadGen(BaselineGenerator):
        def generate(self, game, difficulty, seed=None):
            if game == "queens":
                puzzle, _ = super().generate(game, difficulty, seed)
                return puzzle, None                      # witness yok
            if game == "tapa":
                raise ValueError("tapa generator'u henuz yazilmadi")
            return super().generate(game, difficulty, seed)

    class BadSolver(BaselineSolver):
        def solve(self, puzzle, time_limit_s=30.0):
            if puzzle["game"] == "queens":
                return SolveResult(solved=True, solution={(0, 0), (1, 2)})   # set: JSON'a cevrilemez
            if puzzle["game"] == "tapa":
                return SolveResult(solved=True, solution=[["abc", "def"]])    # gecersiz cevap
            return super().solve(puzzle, time_limit_s)
''')


class CheckSubmissionTest(unittest.TestCase):
    def _run(self, *args, **kw):
        lines = []
        report = run_checks(*args, out=lines.append, **kw)
        return report, "\n".join(lines)

    def test_starter_sablonu_gecer(self):
        report, text = self._run("starter.my_agent:MyGenerator", "starter.my_agent:MySolver",
                                 games=["queens", "tapa"], per_type=2)
        self.assertEqual(report["errors"], 0, text)
        self.assertIn("gonderime hazir", text)

    def test_bozuk_gonderim_nedenleriyle_yakalanir(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "bad_agent.py").write_text(BAD_AGENT, encoding="utf-8")
            report, text = self._run("bad_agent:BadGen", "bad_agent:BadSolver",
                                     games=["queens", "tapa", "zip"], per_type=2, extra_paths=[tmp])
        self.assertGreaterEqual(report["errors"], 4, text)
        self.assertIn("tapa generator'u henuz yazilmadi", text)      # generator hatasi gorunur
        self.assertIn("JSON", text)                                  # set: JSON'a cevrilemez
        self.assertIn("GECERSIZ", text)                              # yanlis cevap
        self.assertIn("gondermeden once duzeltin", text)
        # saglikli oyun (zip) etkilenmez
        self.assertRegex(text, r"\[OK\]\s+zip\s+2/2 havuza girdi")

    def test_olmayan_modul(self):
        report, text = self._run("yok_boyle_modul:Yok", None, games=["queens"], per_type=1)
        self.assertGreaterEqual(report["errors"], 1)
        self.assertIn("yuklenemedi", text)

    def test_cli_cikis_kodlari(self):
        def run(*args):
            return subprocess.run([sys.executable, str(ROOT / "arena" / "check_submission.py"), *args],
                                  cwd=str(ROOT), capture_output=True, text=True, timeout=120)
        ok = run("--generator", "starter.my_agent:MyGenerator", "--games", "queens", "--per-type", "2")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        bad = run("--solver", "yok_boyle_modul:Yok", "--games", "queens", "--per-type", "1")
        self.assertEqual(bad.returncode, 1)
        usage = run()                                                # ne generator ne solver
        self.assertEqual(usage.returncode, 2)
        unknown = run("--generator", "starter.my_agent:MyGenerator", "--games", "yok_oyun")
        self.assertEqual(unknown.returncode, 2)


if __name__ == "__main__":
    unittest.main()
