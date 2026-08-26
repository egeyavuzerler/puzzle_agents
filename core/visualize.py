"""
core/visualize.py

Zip ve Queens puzzle'larını (ve varsa bir solver'ın ürettiği çözümü)
PNG resim olarak çizer. Hem "hızlı görsel kontrol" için (üretilen puzzle
mantıklı mı?) hem de ileride turnuva sonu görsel leaderboard / demo
sunumu için temel oluşturur.

Kullanım:
    from core.visualize import render_zip, render_queens
    render_zip(puzzle, solution, "out.png")
    render_queens(puzzle, solution, "out.png")
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch

CHECKPOINT_COLOR = "#1a1a1a"
PATH_COLOR = "#ff7a3d"
BLOCKED_COLOR = "#2b2b2b"
GRID_COLOR = "#999999"
QUEEN_MARKER = "♛"
REGION_CMAP = plt.get_cmap("tab20")


def render_zip(puzzle: dict, solution: list | None = None, out_path: str = "zip.png",
                title: str | None = None) -> str:
    rows, cols = puzzle["size"]
    blocked = {tuple(c) for c in puzzle.get("blocked_cells", [])}
    checkpoints = puzzle["checkpoints"]

    fig, ax = plt.subplots(figsize=(cols * 0.7 + 1, rows * 0.7 + 1))
    ax.set_xlim(0, cols)
    ax.set_ylim(0, rows)
    ax.invert_yaxis()
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])

    # ızgara + bloklu hücreler
    for r in range(rows):
        for c in range(cols):
            face = BLOCKED_COLOR if (r, c) in blocked else "white"
            ax.add_patch(Rectangle((c, r), 1, 1, facecolor=face, edgecolor=GRID_COLOR, linewidth=1))

    # çözüm yolu (varsa) -- hücre merkezlerini sırayla çizgiyle bağla
    if solution:
        xs = [c + 0.5 for r, c in solution]
        ys = [r + 0.5 for r, c in solution]
        ax.plot(xs, ys, color=PATH_COLOR, linewidth=6, alpha=0.55, solid_capstyle="round", zorder=2)

    # checkpoint'ler (numaralı daireler)
    for cp in checkpoints:
        r, c = cp["pos"]
        circle = plt.Circle((c + 0.5, r + 0.5), 0.32, facecolor=CHECKPOINT_COLOR, zorder=3)
        ax.add_patch(circle)
        ax.text(c + 0.5, r + 0.5, str(cp["order"]), color="white", ha="center", va="center",
                fontsize=12, fontweight="bold", zorder=4)

    ax.set_title(title or f"ZIP {rows}x{cols}" + (" (çözümlü)" if solution else ""), fontsize=11)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def render_queens(puzzle: dict, solution: list | None = None, out_path: str = "queens.png",
                    title: str | None = None) -> str:
    rows, cols = puzzle["size"]
    regions = puzzle["regions"]

    fig, ax = plt.subplots(figsize=(cols * 0.7 + 1, rows * 0.7 + 1))
    ax.set_xlim(0, cols)
    ax.set_ylim(0, rows)
    ax.invert_yaxis()
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])

    for r in range(rows):
        for c in range(cols):
            region_id = regions[r][c]
            color = REGION_CMAP(region_id % 20)
            ax.add_patch(Rectangle((c, r), 1, 1, facecolor=color, edgecolor=GRID_COLOR, linewidth=1))

    if solution:
        for r, c in solution:
            ax.text(c + 0.5, r + 0.5, QUEEN_MARKER, ha="center", va="center",
                     fontsize=22, color="black", zorder=3)

    ax.set_title(title or f"QUEENS {rows}x{cols}" + (" (çözümlü)" if solution else ""), fontsize=11)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def render_puzzle(record: dict, solution: list | None = None, out_path: str = "puzzle.png") -> str:
    """record = bank.jsonl'dan okunan {'game': ..., 'puzzle': ...} satırı."""
    game = record["game"]
    puzzle = record["puzzle"]
    if game == "zip":
        return render_zip(puzzle, solution, out_path)
    elif game == "queens":
        return render_queens(puzzle, solution, out_path)
    raise NotImplementedError(f"'{game}' için görselleştirme henüz yok")


def animate_zip_trace(puzzle: dict, trace: list[list[tuple]], out_path: str = "zip_solve.gif",
                        fps: int = 12, max_frames: int = 220) -> str:
    """
    Solver'ın adım adım (push/backtrack dahil) izlediği yolu GIF animasyonuna
    çevirir. `trace`, solve_zip_warnsdorff(..., record_trace=True)'dan gelen
    liste: her eleman o ana kadar ziyaret edilmiş hücrelerin sıralı listesi.

    trace çok uzunsa (binlerce adım) max_frames'e göre eşit aralıklarla
    örnekler -- son kare (nihai/başarısız durum) her zaman korunur.
    """
    import matplotlib.animation as animation

    rows, cols = puzzle["size"]
    blocked = {tuple(c) for c in puzzle.get("blocked_cells", [])}
    checkpoints = puzzle["checkpoints"]

    # çok uzun iz'i seyrelt
    if len(trace) > max_frames:
        step = len(trace) / max_frames
        indices = sorted({int(i * step) for i in range(max_frames)} | {len(trace) - 1})
        frames = [trace[i] for i in indices]
    else:
        frames = trace

    fig, ax = plt.subplots(figsize=(cols * 0.7 + 1, rows * 0.7 + 1))

    def draw_frame(indexed_state):
        step_i, path_state = indexed_state
        ax.clear()
        ax.set_xlim(0, cols)
        ax.set_ylim(0, rows)
        ax.invert_yaxis()
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])

        for r in range(rows):
            for c in range(cols):
                face = BLOCKED_COLOR if (r, c) in blocked else "white"
                ax.add_patch(Rectangle((c, r), 1, 1, facecolor=face, edgecolor=GRID_COLOR, linewidth=1))

        if len(path_state) > 1:
            xs = [c + 0.5 for r, c in path_state]
            ys = [r + 0.5 for r, c in path_state]
            ax.plot(xs, ys, color=PATH_COLOR, linewidth=6, alpha=0.6, solid_capstyle="round", zorder=2)

        # şu anki uç nokta (kalem ucu) vurgusu
        if path_state:
            r, c = path_state[-1]
            ax.add_patch(plt.Circle((c + 0.5, r + 0.5), 0.22, facecolor="#c0392b", zorder=4))

        for cp in checkpoints:
            r, c = cp["pos"]
            visited = tuple(cp["pos"]) in {tuple(p) for p in path_state}
            color = CHECKPOINT_COLOR if visited else "#bbbbbb"
            circle = plt.Circle((c + 0.5, r + 0.5), 0.32, facecolor=color, zorder=3)
            ax.add_patch(circle)
            ax.text(c + 0.5, r + 0.5, str(cp["order"]), color="white", ha="center", va="center",
                    fontsize=11, fontweight="bold", zorder=4)

        ax.set_title(f"adım {step_i + 1}/{len(frames)}  |  ziyaret: {len(path_state)} hücre",
                     fontsize=10)

    anim = animation.FuncAnimation(fig, draw_frame, frames=list(enumerate(frames)), interval=1000 / fps)
    anim.save(out_path, writer=animation.PillowWriter(fps=fps))
    plt.close(fig)
    return out_path
