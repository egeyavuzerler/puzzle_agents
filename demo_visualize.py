import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.visualize import render_zip, render_queens
from agents_examples.baseline import BaselineSolver

solver = BaselineSolver()

records = [json.loads(l) for l in open("bank/test_bank.jsonl")]
zip_record = next(r for r in records if r["game"] == "zip" and r["id"] == 0)  # en küçük/kolay olan (5x5)
queens_record = next(r for r in records if r["game"] == "queens")

Path("demo_out").mkdir(exist_ok=True)

# çözümsüz haliyle
render_zip(zip_record["puzzle"], None, "demo_out/zip_unsolved.png")
render_queens(queens_record["puzzle"], None, "demo_out/queens_unsolved.png")

# baseline solver'ın çözümüyle
zip_result = solver.solve(zip_record["puzzle"])
render_zip(zip_record["puzzle"], zip_result.solution if zip_result.solved else None,
           "demo_out/zip_solved.png", title=f"ZIP -- solved={zip_result.solved}")

queens_result = solver.solve(queens_record["puzzle"])
render_queens(queens_record["puzzle"], queens_result.solution if queens_result.solved else None,
              "demo_out/queens_solved.png", title=f"QUEENS -- solved={queens_result.solved}")

print("zip solved:", zip_result.solved, "queens solved:", queens_result.solved)
print("dosyalar demo_out/ içinde")
