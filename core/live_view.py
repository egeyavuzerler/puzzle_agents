"""
core/live_view.py

GERÇEK ZAMANLI görünüm: GIF/video KAYDETMEZ, solver çalışırken doğrudan
ekranda bir matplotlib penceresi açıp CANLI günceller.
"""

import time
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

_NON_GUI_BACKENDS = {"agg", "pdf", "svg", "ps", "cairo", "template"}


def _has_gui_backend() -> bool:
    return matplotlib.get_backend().lower() not in _NON_GUI_BACKENDS


CHECKPOINT_DONE = "#1a1a1a"
CHECKPOINT_PENDING = "#bbbbbb"
PATH_COLOR = "#ff7a3d"
BLOCKED_COLOR = "#2b2b2b"
GRID_COLOR = "#999999"
QUEEN_MARKER = "♛"
REGION_CMAP = plt.get_cmap("tab20")


class LiveZipView:
    def __init__(self, puzzle, redraw_every=25, pause=0.001, min_redraw_interval=0.0):
        self.puzzle = puzzle
        self.rows, self.cols = puzzle["size"]
        self.blocked = {tuple(c) for c in puzzle.get("blocked_cells", [])}
        self.checkpoints = puzzle["checkpoints"]
        self.free_total = self.rows * self.cols - len(self.blocked)
        self.redraw_every = max(1, redraw_every)
        self.pause = pause
        self.min_redraw_interval = min_redraw_interval
        self._step_count = 0
        self._last_draw_time = 0.0
        self._last_terminal_print = 0.0

        self._gui = _has_gui_backend()
        if not self._gui:
            print(f"[UYARI] GUI backend yok ({matplotlib.get_backend()}), sadece ilerleme yazdirilacak.")
            self.fig = self.ax = None
            self._line = self._head = None
            self._cp_patches = {}
            return

        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(self.cols * 0.7 + 1, self.rows * 0.7 + 1))
        self.fig.canvas.manager.set_window_title("Zip -- canli cozum")
        ax = self.ax
        ax.set_xlim(0, self.cols)
        ax.set_ylim(0, self.rows)
        ax.invert_yaxis()
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])

        for r in range(self.rows):
            for c in range(self.cols):
                face = BLOCKED_COLOR if (r, c) in self.blocked else "white"
                ax.add_patch(Rectangle((c, r), 1, 1, facecolor=face, edgecolor=GRID_COLOR, linewidth=1))

        (self._line,) = ax.plot([], [], color=PATH_COLOR, linewidth=6, alpha=0.6, solid_capstyle="round", zorder=2)
        self._head = Circle((0.5, 0.5), 0.22, facecolor="#c0392b", zorder=4)
        ax.add_patch(self._head)

        self._cp_patches = {}
        for cp in self.checkpoints:
            r, c = cp["pos"]
            patch = Circle((c + 0.5, r + 0.5), 0.32, facecolor=CHECKPOINT_PENDING, zorder=3)
            ax.add_patch(patch)
            ax.text(c + 0.5, r + 0.5, str(cp["order"]), color="white", ha="center", va="center",
                    fontsize=11, fontweight="bold", zorder=4)
            self._cp_patches[tuple(cp["pos"])] = patch

        self._title = ax.set_title("basliyor...", fontsize=10)
        self.fig.canvas.draw()
        plt.show(block=False)

    def _redraw(self, state, title):
        r, c = state[-1]
        xs = [cc + 0.5 for rr, cc in state]
        ys = [rr + 0.5 for rr, cc in state]
        self._line.set_data(xs, ys)
        self._head.set_center((c + 0.5, r + 0.5))

        visited_set = {tuple(p) for p in state}
        for pos, patch in self._cp_patches.items():
            patch.set_facecolor(CHECKPOINT_DONE if pos in visited_set else CHECKPOINT_PENDING)

        self._title.set_text(title)
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def on_step(self, state, event):
        self._step_count += 1
        now = time.time()
        if now - self._last_terminal_print >= 1.0:
            print(f"  ...adim {self._step_count}, su an {len(state)}/{self.free_total} hucre ziyaret edilmis", flush=True)
            self._last_terminal_print = now

        if not self._gui:
            return
        if self._step_count % self.redraw_every != 0:
            return
        if now - self._last_draw_time < self.min_redraw_interval:
            return
        self._last_draw_time = now

        self._redraw(state, title=f"adim {self._step_count} | ziyaret: {len(state)}/{self.free_total} | {event}")
        plt.pause(self.pause)

    def finish(self, result):
        state = [tuple(c) for c in result.solution] if result.solved else None
        status = "COZULDU" if result.solved else f"COZULEMEDI ({result.error})"
        print(f"\n{status} -- toplam {self._step_count} adim")

        if not self._gui:
            return

        if state:
            self._redraw(state, title=f"{status} | {self._step_count} adimda")
        else:
            self._title.set_text(f"{status} | {self._step_count} adimda")
            self.fig.canvas.draw_idle()

        plt.ioff()
        print("Pencereyi kapatmak icin uzerine tiklayip kapatabilir ya da Ctrl+C ile cikabilirsin.")
        plt.show(block=True)


class LiveQueensView:
    def __init__(self, puzzle, redraw_every=1, pause=0.05):
        self.puzzle = puzzle
        self.rows, self.cols = puzzle["size"]
        self.regions = puzzle["regions"]
        self.redraw_every = max(1, redraw_every)
        self.pause = pause
        self._step_count = 0

        self._gui = _has_gui_backend()
        if not self._gui:
            print(f"[UYARI] GUI backend yok ({matplotlib.get_backend()}), sadece ilerleme yazdirilacak.")
            self.fig = self.ax = None
            self._texts = []
            return

        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(self.cols * 0.7 + 1, self.rows * 0.7 + 1))
        self.fig.canvas.manager.set_window_title("Queens -- canli cozum")
        ax = self.ax
        ax.set_xlim(0, self.cols)
        ax.set_ylim(0, self.rows)
        ax.invert_yaxis()
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])

        for r in range(self.rows):
            for c in range(self.cols):
                color = REGION_CMAP(self.regions[r][c] % 20)
                ax.add_patch(Rectangle((c, r), 1, 1, facecolor=color, edgecolor=GRID_COLOR, linewidth=1))

        self._texts = []
        self._title = ax.set_title("basliyor...", fontsize=10)
        self.fig.canvas.draw()
        plt.show(block=False)

    def _redraw(self, placement, title):
        for t in self._texts:
            t.remove()
        self._texts = []
        for r, c in placement:
            t = self.ax.text(c + 0.5, r + 0.5, QUEEN_MARKER, ha="center", va="center", fontsize=22, zorder=3)
            self._texts.append(t)
        self._title.set_text(title)
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def on_step(self, placement, event):
        self._step_count += 1
        if not self._gui:
            return
        if self._step_count % self.redraw_every != 0:
            return
        self._redraw(placement, title=f"adim {self._step_count} | yerlesen: {len(placement)}/{self.rows} | {event}")
        plt.pause(self.pause)

    def finish(self, result):
        placement = [tuple(p) for p in result.solution] if result.solved else []
        status = "COZULDU" if result.solved else f"COZULEMEDI ({result.error})"
        print(f"\n{status} -- toplam {self._step_count} adim")

        if not self._gui:
            return

        self._redraw(placement, title=f"{status} | {self._step_count} adimda")
        plt.ioff()
        print("Pencereyi kapatmak icin uzerine tiklayip kapatabilir ya da Ctrl+C ile cikabilirsin.")
        plt.show(block=True)


class LiveTangoView:
    def __init__(self, puzzle, redraw_every=5, pause=0.02):
        self.puzzle = puzzle
        self.rows, self.cols = puzzle["size"]
        self.blocked = {tuple(c) for c in puzzle.get("blocked_cells", [])}
        self.prefilled = {tuple(c["pos"]): c["value"] for c in puzzle.get("prefilled", [])}
        self.constraints = puzzle.get("constraints", [])
        self.redraw_every = max(1, redraw_every)
        self.pause = pause
        self._step_count = 0

        self._gui = _has_gui_backend()
        if not self._gui:
            print(f"[UYARI] GUI backend yok ({matplotlib.get_backend()}), sadece ilerleme yazdirilacak.")
            self.fig = self.ax = None
            self._texts = []
            return

        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(self.cols * 0.55 + 1, self.rows * 0.55 + 1))
        self.fig.canvas.manager.set_window_title("Tango -- canli cozum")
        ax = self.ax
        ax.set_xlim(0, self.cols)
        ax.set_ylim(0, self.rows)
        ax.invert_yaxis()
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])

        for r in range(self.rows):
            for c in range(self.cols):
                is_blocked = (r, c) in self.blocked
                is_clue = (r, c) in self.prefilled
                face = BLOCKED_COLOR if is_blocked else ("#fff3d6" if is_clue else "white")
                ax.add_patch(Rectangle((c, r), 1, 1, facecolor=face, edgecolor=GRID_COLOR, linewidth=1))

        for con in self.constraints:
            r1, c1 = con["cell1"]
            r2, c2 = con["cell2"]
            mx, my = (c1 + c2) / 2 + 0.5, (r1 + r2) / 2 + 0.5
            symbol = "=" if con["type"] == "equal" else "x"
            ax.text(mx, my, symbol, ha="center", va="center", fontsize=10, fontweight="bold",
                    color="#c0392b", zorder=5,
                    bbox=dict(boxstyle="circle,pad=0.12", facecolor="white", edgecolor="#c0392b", linewidth=1))

        self._texts = []
        self._title = ax.set_title("basliyor...", fontsize=10)
        self.fig.canvas.draw()
        plt.show(block=False)

    def _redraw(self, grid, title):
        for t in self._texts:
            t.remove()
        self._texts = []
        for r in range(self.rows):
            for c in range(self.cols):
                if (r, c) in self.blocked:
                    continue
                val = grid[r][c]
                if val == "sun":
                    t = self.ax.text(c + 0.5, r + 0.5, "\u2600", ha="center", va="center",
                                      fontsize=14, color="#e6a700", zorder=3)
                    self._texts.append(t)
                elif val == "moon":
                    t = self.ax.text(c + 0.5, r + 0.5, "\u263D", ha="center", va="center",
                                      fontsize=14, color="#4a4a8a", zorder=3)
                    self._texts.append(t)
        self._title.set_text(title)
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def on_step(self, grid, event):
        self._step_count += 1
        if not self._gui:
            return
        if self._step_count % self.redraw_every != 0:
            return
        total_free = self.rows * self.cols - len(self.blocked)
        filled = sum(1 for r in range(self.rows) for c in range(self.cols)
                     if (r, c) not in self.blocked and grid[r][c] is not None)
        self._redraw(grid, title=f"adim {self._step_count} | dolu: {filled}/{total_free} | {event}")
        plt.pause(self.pause)

    def finish(self, result):
        status = "COZULDU" if result.solved else f"COZULEMEDI ({result.error})"
        print(f"\n{status} -- toplam {self._step_count} adim")
        if not self._gui:
            return
        grid = result.solution if result.solved else [[None] * self.cols for _ in range(self.rows)]
        self._redraw(grid, title=f"{status} | {self._step_count} adimda")
        plt.ioff()
        print("Pencereyi kapatmak icin uzerine tiklayip kapatabilir ya da Ctrl+C ile cikabilirsin.")
        plt.show(block=True)


class LivePatchesView:
    def __init__(self, puzzle, redraw_every=3, pause=0.03):
        self.puzzle = puzzle
        self.rows, self.cols = puzzle["size"]
        self.clues = puzzle["clues"]
        self.redraw_every = max(1, redraw_every)
        self.pause = pause
        self._step_count = 0

        self._gui = _has_gui_backend()
        if not self._gui:
            print(f"[UYARI] GUI backend yok ({matplotlib.get_backend()}), sadece ilerleme yazdirilacak.")
            self.fig = self.ax = None
            self._rect_patches = [None] * len(self.clues)
            return

        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(self.cols * 0.6 + 1, self.rows * 0.6 + 1))
        self.fig.canvas.manager.set_window_title("Patches -- canli cozum")
        ax = self.ax
        ax.set_xlim(0, self.cols)
        ax.set_ylim(0, self.rows)
        ax.invert_yaxis()
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])

        for r in range(self.rows + 1):
            ax.plot([0, self.cols], [r, r], color="#dddddd", linewidth=0.5, zorder=1)
        for c in range(self.cols + 1):
            ax.plot([c, c], [0, self.rows], color="#dddddd", linewidth=0.5, zorder=1)

        shape_symbol = {"square": "\u25a1", "wide": "\u25ac", "tall": "\u25ae", "any": "?"}
        for clue in self.clues:
            r, c = clue["pos"]
            ax.text(c + 0.5, r + 0.5, f"{clue['area']}\n{shape_symbol[clue['shape']]}",
                    ha="center", va="center", fontsize=8, fontweight="bold", zorder=5,
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="black", linewidth=0.8))

        self._rect_patches = [None] * len(self.clues)
        self._title = ax.set_title("basliyor...", fontsize=10)
        self.fig.canvas.draw()
        plt.show(block=False)

    def _redraw(self, result, title):
        for i, rect in enumerate(result):
            if rect is None:
                if self._rect_patches[i] is not None:
                    self._rect_patches[i].remove()
                    self._rect_patches[i] = None
                continue
            r0, c0, r1, c1 = rect["r0"], rect["c0"], rect["r1"], rect["c1"]
            if self._rect_patches[i] is not None:
                self._rect_patches[i].remove()
            color = REGION_CMAP(i % 20)
            p = Rectangle((c0, r0), c1 - c0 + 1, r1 - r0 + 1, facecolor=color, edgecolor="black",
                          linewidth=1.2, alpha=0.75, zorder=2)
            self.ax.add_patch(p)
            self._rect_patches[i] = p
        self._title.set_text(title)
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def on_step(self, result, event):
        self._step_count += 1
        if not self._gui:
            return
        if self._step_count % self.redraw_every != 0:
            return
        placed = sum(1 for r in result if r is not None)
        self._redraw(result, title=f"adim {self._step_count} | yerlesen: {placed}/{len(self.clues)} | {event}")
        plt.pause(self.pause)

    def finish(self, solve_result):
        status = "COZULDU" if solve_result.solved else f"COZULEMEDI ({solve_result.error})"
        print(f"\n{status} -- toplam {self._step_count} adim")
        if not self._gui:
            return
        result = solve_result.solution if solve_result.solved else [None] * len(self.clues)
        self._redraw(result, title=f"{status} | {self._step_count} adimda")
        plt.ioff()
        print("Pencereyi kapatmak icin uzerine tiklayip kapatabilir ya da Ctrl+C ile cikabilirsin.")
        plt.show(block=True)
class LiveSlitherlinkView:
    def __init__(self, puzzle, redraw_every=150, pause=0.01):
        self.puzzle = puzzle
        self.rows, self.cols = puzzle["size"]
        self.clues = puzzle["clues"]
        self.redraw_every = max(1, redraw_every)
        self.pause = pause
        self._step_count = 0

        self._gui = _has_gui_backend()
        if not self._gui:
            print(f"[UYARI] GUI backend yok ({matplotlib.get_backend()}), sadece ilerleme yazdirilacak.")
            self.fig = self.ax = None
            self._line = None
            return

        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(self.cols * 0.6 + 1, self.rows * 0.6 + 1))
        self.fig.canvas.manager.set_window_title("Slitherlink -- canli cozum")
        ax = self.ax
        ax.set_xlim(-0.5, self.cols + 0.5)
        ax.set_ylim(-0.5, self.rows + 0.5)
        ax.invert_yaxis()
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])

        for r in range(self.rows + 1):
            ax.plot([0, self.cols], [r, r], color="#dddddd", linewidth=0.5, zorder=1)
        for c in range(self.cols + 1):
            ax.plot([c, c], [0, self.rows], color="#dddddd", linewidth=0.5, zorder=1)

        for r in range(self.rows):
            for c in range(self.cols):
                if self.clues[r][c] is not None:
                    ax.text(c + 0.5, r + 0.5, str(self.clues[r][c]), ha="center", va="center",
                            fontsize=11, fontweight="bold", color="#333333", zorder=3)

        (self._line,) = ax.plot([], [], color=PATH_COLOR, linewidth=4, zorder=2, solid_capstyle="round")
        self._title = ax.set_title("basliyor...", fontsize=10)
        self.fig.canvas.draw()
        plt.show(block=False)

    def _redraw(self, edges, title):
        xs, ys = [], []
        for e in edges:
            (r1, c1), (r2, c2) = e[0], e[1]
            xs += [c1, c2, float("nan")]
            ys += [r1, r2, float("nan")]
        self._line.set_data(xs, ys)
        self._title.set_text(title)
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def on_step(self, edges, event):
        self._step_count += 1
        if not self._gui:
            return
        if self._step_count % self.redraw_every != 0:
            return
        self._redraw(edges, title=f"adim {self._step_count} | kenar: {len(edges)} | {event}")
        plt.pause(self.pause)

    def finish(self, result):
        status = "COZULDU" if result.solved else f"COZULEMEDI ({result.error})"
        print(f"\n{status} -- toplam {self._step_count} adim")
        if not self._gui:
            return
        edges = result.solution if result.solved else []
        self._redraw(edges, title=f"{status} | {self._step_count} adimda")
        plt.ioff()
        print("Pencereyi kapatmak icin uzerine tiklayip kapatabilir ya da Ctrl+C ile cikabilirsin.")
        plt.show(block=True)


class LiveNumberlinkView:
    _PALETTE = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4",
                "#46f0f0", "#f032e6", "#bcf60c", "#fabebe", "#008080", "#e6beff"]

    def __init__(self, puzzle, redraw_every=10, pause=0.02):
        self.puzzle = puzzle
        self.rows, self.cols = puzzle["size"]
        self.endpoints = puzzle["endpoints"]
        self.redraw_every = max(1, redraw_every)
        self.pause = pause
        self._step_count = 0

        self._gui = _has_gui_backend()
        if not self._gui:
            print(f"[UYARI] GUI backend yok ({matplotlib.get_backend()}), sadece ilerleme yazdirilacak.")
            self.fig = self.ax = None
            self._cell_patches = {}
            return

        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(self.cols * 0.55 + 1, self.rows * 0.55 + 1))
        self.fig.canvas.manager.set_window_title("Numberlink -- canli cozum")
        ax = self.ax
        ax.set_xlim(0, self.cols)
        ax.set_ylim(0, self.rows)
        ax.invert_yaxis()
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])

        for r in range(self.rows):
            for c in range(self.cols):
                ax.add_patch(Rectangle((c, r), 1, 1, facecolor="white", edgecolor=GRID_COLOR, linewidth=0.5))

        for e in self.endpoints:
            r, c = e["pos"]
            color = self._PALETTE[e["color"] % len(self._PALETTE)]
            circ = Circle((c + 0.5, r + 0.5), 0.32, facecolor=color, edgecolor="black", linewidth=1, zorder=4)
            ax.add_patch(circ)

        self._cell_patches = {}
        self._title = ax.set_title("basliyor...", fontsize=10)
        self.fig.canvas.draw()
        plt.show(block=False)

    def _redraw(self, grid, title):
        for (r, c), patch in list(self._cell_patches.items()):
            patch.remove()
        self._cell_patches = {}
        for r in range(self.rows):
            for c in range(self.cols):
                color_id = grid[r][c]
                if color_id is None:
                    continue
                color = self._PALETTE[color_id % len(self._PALETTE)]
                p = Rectangle((c + 0.08, r + 0.08), 0.84, 0.84, facecolor=color, alpha=0.55, zorder=2)
                self.ax.add_patch(p)
                self._cell_patches[(r, c)] = p
        self._title.set_text(title)
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def on_step(self, grid, event):
        self._step_count += 1
        if not self._gui:
            return
        if self._step_count % self.redraw_every != 0:
            return
        filled = sum(1 for row in grid for v in row if v is not None)
        self._redraw(grid, title=f"adim {self._step_count} | dolu: {filled} | {event}")
        plt.pause(self.pause)

    def finish(self, result):
        status = "COZULDU" if result.solved else f"COZULEMEDI ({result.error})"
        print(f"\n{status} -- toplam {self._step_count} adim")
        if not self._gui:
            return
        grid = result.solution if result.solved else [[None] * self.cols for _ in range(self.rows)]
        self._redraw(grid, title=f"{status} | {self._step_count} adimda")
        plt.ioff()
        print("Pencereyi kapatmak icin uzerine tiklayip kapatabilir ya da Ctrl+C ile cikabilirsin.")
        plt.show(block=True)


class LiveHashiView:
    def __init__(self, puzzle, redraw_every=5, pause=0.02):
        self.puzzle = puzzle
        self.rows, self.cols = puzzle["size"]
        self.islands = {tuple(i["pos"]): i["value"] for i in puzzle["islands"]}
        self.redraw_every = max(1, redraw_every)
        self.pause = pause
        self._step_count = 0

        self._gui = _has_gui_backend()
        if not self._gui:
            print(f"[UYARI] GUI backend yok ({matplotlib.get_backend()}), sadece ilerleme yazdirilacak.")
            self.fig = self.ax = None
            self._edge_lines = []
            return

        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(self.cols * 0.6 + 1, self.rows * 0.6 + 1))
        self.fig.canvas.manager.set_window_title("Hashi -- canli cozum")
        ax = self.ax
        ax.set_xlim(-0.5, self.cols - 0.5)
        ax.set_ylim(-0.5, self.rows - 0.5)
        ax.invert_yaxis()
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])

        for (r, c), val in self.islands.items():
            circ = Circle((c, r), 0.35, facecolor="white", edgecolor="black", linewidth=1.5, zorder=4)
            ax.add_patch(circ)
            ax.text(c, r, str(val), ha="center", va="center", fontsize=11, fontweight="bold", zorder=5)

        self._edge_lines = []
        self._title = ax.set_title("basliyor...", fontsize=10)
        self.fig.canvas.draw()
        plt.show(block=False)

    def _redraw(self, edges, title):
        for line in self._edge_lines:
            line.remove()
        self._edge_lines = []
        for e in edges:
            (r1, c1), (r2, c2) = e["from"], e["to"]
            cnt = e["count"]
            if cnt == 1:
                (line,) = self.ax.plot([c1, c2], [r1, r2], color="#555555", linewidth=2, zorder=2)
                self._edge_lines.append(line)
            else:
                off = 0.06
                if r1 == r2:
                    (l1,) = self.ax.plot([c1, c2], [r1 - off, r2 - off], color="#555555", linewidth=2, zorder=2)
                    (l2,) = self.ax.plot([c1, c2], [r1 + off, r2 + off], color="#555555", linewidth=2, zorder=2)
                else:
                    (l1,) = self.ax.plot([c1 - off, c2 - off], [r1, r2], color="#555555", linewidth=2, zorder=2)
                    (l2,) = self.ax.plot([c1 + off, c2 + off], [r1, r2], color="#555555", linewidth=2, zorder=2)
                self._edge_lines.extend([l1, l2])
        self._title.set_text(title)
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def on_step(self, edges, event):
        self._step_count += 1
        if not self._gui:
            return
        if self._step_count % self.redraw_every != 0:
            return
        self._redraw(edges, title=f"adim {self._step_count} | kopru: {len(edges)} | {event}")
        plt.pause(self.pause)

    def finish(self, result):
        status = "COZULDU" if result.solved else f"COZULEMEDI ({result.error})"
        print(f"\n{status} -- toplam {self._step_count} adim")
        if not self._gui:
            return
        edges = result.solution if result.solved else []
        self._redraw(edges, title=f"{status} | {self._step_count} adimda")
        plt.ioff()
        print("Pencereyi kapatmak icin uzerine tiklayip kapatabilir ya da Ctrl+C ile cikabilirsin.")
        plt.show(block=True)


class LiveLitsView:
    def __init__(self, puzzle, redraw_every=20, pause=0.02):
        self.puzzle = puzzle
        self.rows, self.cols = puzzle["size"]
        self.regions = puzzle["regions"]
        self.redraw_every = max(1, redraw_every)
        self.pause = pause
        self._step_count = 0

        self._gui = _has_gui_backend()
        if not self._gui:
            print(f"[UYARI] GUI backend yok ({matplotlib.get_backend()}), sadece ilerleme yazdirilacak.")
            self.fig = self.ax = None
            self._shaded_patches = {}
            return

        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(self.cols * 0.55 + 1, self.rows * 0.55 + 1))
        self.fig.canvas.manager.set_window_title("LITS -- canli cozum")
        ax = self.ax
        ax.set_xlim(0, self.cols)
        ax.set_ylim(0, self.rows)
        ax.invert_yaxis()
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])

        for r in range(self.rows):
            for c in range(self.cols):
                color = REGION_CMAP(self.regions[r][c] % 20)
                ax.add_patch(Rectangle((c, r), 1, 1, facecolor=color, alpha=0.25, edgecolor=GRID_COLOR, linewidth=0.5))

        self._shaded_patches = {}
        self._title = ax.set_title("basliyor...", fontsize=10)
        self.fig.canvas.draw()
        plt.show(block=False)

    def _redraw(self, shaded_cells, title):
        for patch in self._shaded_patches.values():
            patch.remove()
        self._shaded_patches = {}
        for (r, c) in shaded_cells:
            p = Rectangle((c, r), 1, 1, facecolor="#2b2b2b", alpha=0.85, zorder=3)
            self.ax.add_patch(p)
            self._shaded_patches[(r, c)] = p
        self._title.set_text(title)
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def on_step(self, shaded_cells, event):
        self._step_count += 1
        if not self._gui:
            return
        if self._step_count % self.redraw_every != 0:
            return
        self._redraw(shaded_cells, title=f"adim {self._step_count} | golgeli: {len(shaded_cells)} | {event}")
        plt.pause(self.pause)

    def finish(self, result):
        status = "COZULDU" if result.solved else f"COZULEMEDI ({result.error})"
        print(f"\n{status} -- toplam {self._step_count} adim")
        if not self._gui:
            return
        cells = [tuple(c) for c in result.solution] if result.solved else []
        self._redraw(cells, title=f"{status} | {self._step_count} adimda")
        plt.ioff()
        print("Pencereyi kapatmak icin uzerine tiklayip kapatabilir ya da Ctrl+C ile cikabilirsin.")
        plt.show(block=True)


class LiveYinYangView:
    def __init__(self, puzzle, redraw_every=3, pause=0.05):
        self.puzzle = puzzle
        self.rows, self.cols = puzzle["size"]
        self.prefilled = {tuple(c["pos"]): c["color"] for c in puzzle.get("prefilled", [])}
        self.redraw_every = max(1, redraw_every)
        self.pause = pause
        self._step_count = 0

        self._gui = _has_gui_backend()
        if not self._gui:
            print(f"[UYARI] GUI backend yok ({matplotlib.get_backend()}), sadece ilerleme yazdirilacak.")
            self.fig = self.ax = None
            self._cell_patches = {}
            return

        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(self.cols * 0.7 + 1, self.rows * 0.7 + 1))
        self.fig.canvas.manager.set_window_title("YinYang -- canli cozum")
        ax = self.ax
        ax.set_xlim(0, self.cols)
        ax.set_ylim(0, self.rows)
        ax.invert_yaxis()
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for r in range(self.rows):
            for c in range(self.cols):
                ax.add_patch(Rectangle((c, r), 1, 1, facecolor="#dddddd", edgecolor=GRID_COLOR, linewidth=0.5))
        for (r, c), color in self.prefilled.items():
            ax.add_patch(Circle((c + 0.5, r + 0.5), 0.12, facecolor="#c0392b", zorder=5))

        self._cell_patches = {}
        self._title = ax.set_title("basliyor...", fontsize=10)
        self.fig.canvas.draw()
        plt.show(block=False)

    def _redraw(self, grid, title):
        for patch in self._cell_patches.values():
            patch.remove()
        self._cell_patches = {}
        for r in range(self.rows):
            for c in range(self.cols):
                val = grid[r][c]
                if val is None:
                    continue
                p = Rectangle((c, r), 1, 1, facecolor=val, edgecolor=GRID_COLOR, linewidth=0.5, zorder=2)
                self.ax.add_patch(p)
                self._cell_patches[(r, c)] = p
        self._title.set_text(title)
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def on_step(self, grid, event):
        self._step_count += 1
        if not self._gui:
            return
        if self._step_count % self.redraw_every != 0:
            return
        filled = sum(1 for row in grid for v in row if v is not None)
        self._redraw(grid, title=f"adim {self._step_count} | dolu: {filled} | {event}")
        plt.pause(self.pause)

    def finish(self, result):
        status = "COZULDU" if result.solved else f"COZULEMEDI ({result.error})"
        print(f"\n{status} -- toplam {self._step_count} adim")
        if not self._gui:
            return
        grid = result.solution if result.solved else [[None] * self.cols for _ in range(self.rows)]
        self._redraw(grid, title=f"{status} | {self._step_count} adimda")
        plt.ioff()
        print("Pencereyi kapatmak icin uzerine tiklayip kapatabilir ya da Ctrl+C ile cikabilirsin.")
        plt.show(block=True)


class LiveTapaView:
    def __init__(self, puzzle, redraw_every=10, pause=0.02):
        self.puzzle = puzzle
        self.rows, self.cols = puzzle["size"]
        self.clues = {tuple(c["pos"]): c["numbers"] for c in puzzle["clues"]}
        self.redraw_every = max(1, redraw_every)
        self.pause = pause
        self._step_count = 0

        self._gui = _has_gui_backend()
        if not self._gui:
            print(f"[UYARI] GUI backend yok ({matplotlib.get_backend()}), sadece ilerleme yazdirilacak.")
            self.fig = self.ax = None
            self._shaded_patches = {}
            return

        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(self.cols * 0.55 + 1, self.rows * 0.55 + 1))
        self.fig.canvas.manager.set_window_title("Tapa -- canli cozum")
        ax = self.ax
        ax.set_xlim(0, self.cols)
        ax.set_ylim(0, self.rows)
        ax.invert_yaxis()
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])

        for r in range(self.rows + 1):
            ax.plot([0, self.cols], [r, r], color="#dddddd", linewidth=0.5, zorder=1)
        for c in range(self.cols + 1):
            ax.plot([c, c], [0, self.rows], color="#dddddd", linewidth=0.5, zorder=1)

        for (r, c), nums in self.clues.items():
            ax.add_patch(Rectangle((c, r), 1, 1, facecolor="#f0f0f0", edgecolor="black", linewidth=1, zorder=3))
            label = ",".join(str(n) for n in nums)
            ax.text(c + 0.5, r + 0.5, label, ha="center", va="center", fontsize=8, fontweight="bold", zorder=4)

        self._shaded_patches = {}
        self._title = ax.set_title("basliyor...", fontsize=10)
        self.fig.canvas.draw()
        plt.show(block=False)

    def _redraw(self, shaded_cells, title):
        for patch in self._shaded_patches.values():
            patch.remove()
        self._shaded_patches = {}
        for (r, c) in shaded_cells:
            p = Rectangle((c, r), 1, 1, facecolor="#2b2b2b", zorder=2)
            self.ax.add_patch(p)
            self._shaded_patches[(r, c)] = p
        self._title.set_text(title)
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def on_step(self, shaded_cells, event):
        self._step_count += 1
        if not self._gui:
            return
        if self._step_count % self.redraw_every != 0:
            return
        self._redraw(shaded_cells, title=f"adim {self._step_count} | golgeli: {len(shaded_cells)} | {event}")
        plt.pause(self.pause)

    def finish(self, result):
        status = "COZULDU" if result.solved else f"COZULEMEDI ({result.error})"
        print(f"\n{status} -- toplam {self._step_count} adim")
        if not self._gui:
            return
        cells = [tuple(c) for c in result.solution] if result.solved else []
        self._redraw(cells, title=f"{status} | {self._step_count} adimda")
        plt.ioff()
        print("Pencereyi kapatmak icin uzerine tiklayip kapatabilir ya da Ctrl+C ile cikabilirsin.")
        plt.show(block=True)
