"""
arena/sandboxed_solver.py

Katilimcinin SOLVER'ini hakemden ayri bir ortamda calistiran hakem tarafi
vekil (proxy). Iki mod:

  local  -- ayri bir process (temiz ortam degiskenleri, kendi process grubu).
            Zaman/bellek/CPU sinirlari var; DOSYA ve AG izolasyonu YOK.
            Gelistirme ve protokol testi icin.
  docker -- ayni runner bir container icinde: --network none, salt-okunur
            dosya sistemi, tum capability'ler dusurulmus, root degil, bellek/
            process sayisi sinirli. Katilimci kodu bank'i, baska takimlari,
            validator sonuclarini, solutions dosyasini GOREMEZ. Yarisma
            gunu bu mod kullanilmali.

Her iki modda da solver'in dondurdugu cozum hakemde (burada degil, run_match
icinde) validate_solution ile dogrulanir; solver'a asla bir solution verilmez.
Sure OLCUMU hakemin kendi saatiyle yapilir (solver'in bildirdigi sure
GUVENILMEZ, kendini hizli gosterebilir).
"""

import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.base import SolveResult

ROOT = Path(__file__).resolve().parents[1]
MAX_LINE_BYTES = 5 * 1024 * 1024   # tek cevap satiri ust siniri (hakem belleğini korur)


def _reader(stream, q: "queue.Queue") -> None:
    try:
        while True:
            line = stream.readline(MAX_LINE_BYTES + 1)
            if not line:
                break
            if len(line) > MAX_LINE_BYTES and not line.endswith(b"\n"):
                q.put(("toolong", None))
                break
            q.put(("line", line))
    except Exception:
        pass
    finally:
        q.put(("eof", None))


class SandboxedSolver:
    is_sandboxed = True

    def __init__(self, solver_spec: str, mode: str = "local", docker_image: str = "puzzle-arena",
                 submission_dir: str | None = None, memory_mb: int = 1024, cpu_seconds: int = 60,
                 startup_timeout_s: float = 90.0, child_stderr=None,
                 extra_pythonpath: list[str] | None = None):
        if mode not in ("local", "docker"):
            raise ValueError(f"gecersiz mod: {mode!r}")
        self.name = solver_spec
        self.solver_spec = solver_spec
        self.mode = mode
        self.docker_image = docker_image
        self.submission_dir = submission_dir
        self.memory_mb = memory_mb
        self.cpu_seconds = cpu_seconds
        self.startup_timeout_s = startup_timeout_s
        self.child_stderr = child_stderr   # None: solver'in stderr'i terminale akar
        self.extra_pythonpath = [str(Path(p).resolve()) for p in (extra_pythonpath or [])]  # sadece local mod
        self._proc = None
        self._q = None
        self._container = None
        self._next_id = 0
        self._start_error = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False

    # ---- komut ----
    def build_command(self) -> list[str]:
        runner_args = ["--solver", self.solver_spec, "--memory-mb", str(self.memory_mb),
                       "--cpu-seconds", str(self.cpu_seconds)]
        if self.mode == "local":
            return [sys.executable, str(ROOT / "arena" / "solver_runner.py"), *runner_args]

        self._container = f"puzzle-solver-{uuid.uuid4().hex[:12]}"
        cmd = [
            "docker", "run", "--rm", "-i", "--init", "--name", self._container,
            "--network", "none",
            "--read-only", "--tmpfs", "/tmp:rw,size=64m,noexec,nosuid",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", "128",
            "--memory", f"{self.memory_mb}m", "--memory-swap", f"{self.memory_mb}m",
            "--cpus", "1",
            "--user", "65534:65534",
            "-e", "PYTHONPATH=/submission:/app",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-e", "PYTHONUNBUFFERED=1",
        ]
        if self.submission_dir:
            src = str(Path(self.submission_dir).resolve())
            cmd += ["--mount", f"type=bind,src={src},dst=/submission,readonly"]
        cmd += [self.docker_image, "python", "/app/arena/solver_runner.py", *runner_args]
        return cmd

    # ---- yasam dongusu ----
    def _start(self) -> bool:
        cmd = self.build_command()
        env = None
        if self.mode == "local":
            # Hakemin ortam degiskenlerini (token, anahtar vb.) solver'a SIZDIRMA
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                   "PYTHONPATH": os.pathsep.join([str(ROOT), *self.extra_pythonpath]), "PYTHONUNBUFFERED": "1",
                   "PYTHONDONTWRITEBYTECODE": "1"}
        try:
            self._proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.child_stderr, env=env,
                start_new_session=(os.name == "posix"), cwd=str(ROOT) if self.mode == "local" else None)
        except OSError as e:
            self._proc = None
            self._start_error = f"sandbox baslatilamadi ({self.mode}): {e}"
            return False

        self._q = queue.Queue()
        threading.Thread(target=_reader, args=(self._proc.stdout, self._q), daemon=True).start()

        deadline = time.time() + self.startup_timeout_s
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                self._kill()
                self._start_error = f"sandbox {self.startup_timeout_s}s icinde hazir olmadi"
                return False
            try:
                kind, payload = self._q.get(timeout=remaining)
            except queue.Empty:
                continue
            if kind != "line":
                self._kill()
                self._start_error = "sandbox hazir olmadan kapandi (image/komut hatasi olabilir)"
                return False
            try:
                msg = json.loads(payload)
            except ValueError:
                continue
            if isinstance(msg, dict) and "ready" in msg:
                if msg["ready"]:
                    return True
                self._kill()
                self._start_error = f"solver yuklenemedi: {msg.get('error')}"
                return False

    def _kill(self) -> None:
        p = self._proc
        if p is None:
            return
        if self.mode == "docker" and self._container:
            try:
                subprocess.run(["docker", "kill", self._container], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=15)
            except (OSError, subprocess.SubprocessError):
                pass
        try:
            if os.name == "posix":
                os.killpg(p.pid, signal.SIGKILL)
            else:
                p.kill()
        except (OSError, ProcessLookupError):
            pass
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        for stream in (p.stdin, p.stdout):
            try:
                if stream:
                    stream.close()
            except OSError:
                pass
        self._proc = None

    def close(self) -> None:
        p = self._proc
        if p is None:
            return
        try:
            p.stdin.close()          # runner stdin EOF gorunce temiz cikar
            p.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass
        self._kill()

    # ---- cozum ----
    def solve(self, puzzle: dict, time_limit_s: float, hard_timeout_s: float) -> SolveResult:
        t0 = time.time()
        if self._proc is None or self._proc.poll() is not None:
            self._proc = None
            if not self._start():
                return SolveResult(solved=False, time_seconds=time.time() - t0, error=self._start_error)
            t0 = time.time()  # baslatma suresi solver'a yazilmaz

        self._next_id += 1
        rid = self._next_id
        try:
            payload = json.dumps({"id": rid, "puzzle": puzzle, "time_limit_s": time_limit_s}) + "\n"
            self._proc.stdin.write(payload.encode("utf-8"))
            self._proc.stdin.flush()
        except (OSError, ValueError):
            self._kill()
            return SolveResult(solved=False, time_seconds=time.time() - t0,
                               error="sandbox process kapali (istek gonderilemedi)")

        deadline = t0 + hard_timeout_s
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                self._kill()
                return SolveResult(solved=False, time_seconds=hard_timeout_s,
                                   error=f"HARD TIMEOUT ({hard_timeout_s}s) -- sandbox sonlandirildi")
            try:
                kind, payload = self._q.get(timeout=remaining)
            except queue.Empty:
                continue
            if kind == "eof":
                code = self._proc.poll() if self._proc else None
                self._kill()
                return SolveResult(solved=False, time_seconds=time.time() - t0,
                                   error=f"sandbox cevap vermeden sonlandi (exitcode={code})")
            if kind == "toolong":
                self._kill()
                return SolveResult(solved=False, time_seconds=time.time() - t0,
                                   error=f"cevap cok buyuk (>{MAX_LINE_BYTES // (1024*1024)}MB) -- sonlandirildi")
            try:
                msg = json.loads(payload)
            except ValueError:
                continue
            if not isinstance(msg, dict) or msg.get("id") != rid:
                continue
            err = msg.get("error")
            steps = msg.get("steps_taken")
            return SolveResult(
                solved=bool(msg.get("solved")) and err is None,
                solution=msg.get("solution"),
                time_seconds=time.time() - t0,       # hakemin kendi olcumu
                steps_taken=steps if isinstance(steps, int) else 0,
                error=None if err is None else str(err)[:300],
            )
