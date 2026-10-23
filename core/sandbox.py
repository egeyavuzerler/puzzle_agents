"""
core/sandbox.py

Katilimci kodunu (generate() / solve()) hakemin process'inden AYIRAN
yardimcilar. Katilimci kodu kotu niyetli ya da hatali olabilir:
sonsuz dongu, asiri bellek, process'i oldurme (os._exit), anlamsiz donus
degeri... Hakem bunlardan hicbiri yuzunden dusmemeli, sadece o cagriyi
"basarisiz" saymali.

  - apply_resource_limits(): worker process'ine bellek/CPU limiti koyar.
  - IsolatedWorker: bir nesneyi (ornegin bir generator) AYRI bir process'te
    tutar; metod cagrilari Pipe uzerinden gider. Her cagri icin duvar-saati
    timeout'u vardir; asarsa ya da worker olurse process oldurulur ve bir
    sonraki cagri icin YENI bir worker baslatilir. (Her puzzle icin ayri
    process acmaktan cok daha hizli: process bir kez baslar, binlerce cagriya
    hizmet eder.)

NOT: Bu izolasyon bellek/CPU/sure sinirlar; AG ve DOSYA SISTEMI erisimini
KISITLAMAZ. Yarisma gunu bunun icin container (ag kapali, salt-okunur dosya
sistemi) gerekir.
"""

import multiprocessing as mp
import os
import time

try:
    import resource  # Unix/macOS only
    _HAS_RESOURCE = True
except ImportError:
    _HAS_RESOURCE = False


def apply_resource_limits(memory_mb: int, cpu_seconds: int) -> None:
    """
    Worker process basinda cagrilir.
      - RLIMIT_AS:  adres alani (bellek) limiti -- asilirsa MemoryError
      - RLIMIT_CPU: CPU saniyesi limiti -- asilirsa SIGXCPU ile olur
    Windows'ta resource modulu yok; o durumda sadece dis timeout korur.
    """
    if not _HAS_RESOURCE:
        return
    try:
        mem_bytes = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    except (ValueError, OSError):
        pass  # macOS bazi surumlerde RLIMIT_AS'i desteklemeyebilir
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    except (ValueError, OSError):
        pass


def set_memory_limit(memory_mb: int) -> None:
    """Process'in adres alani (bellek) limitini koyar. Desteklenmiyorsa sessizce gecer."""
    if not _HAS_RESOURCE:
        return
    try:
        mem_bytes = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    except (ValueError, OSError):
        pass


def drop_privileges(uid: int = 65534, gid: int = 65534) -> None:
    """
    Process root olarak calisiyorsa (ornegin container icinde) 'nobody'ye duser.
    Boylece worker in kodu HAKEMIN (ana process'in) root-sahipli dosyalarina
    -- bank.jsonl, solutions dosyasi -- yazamaz/okuyamaz ve ona ptrace yapamaz.
    Root degilse hicbir sey yapmaz. Dusurme BASARISIZ olursa istisna firlatir
    (fail closed): yetkili halde katilimci kodu calistirilmaz.
    """
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        return
    os.setgroups([])
    os.setgid(gid)
    os.setuid(uid)
    if os.geteuid() == 0:
        raise RuntimeError("yetki dusurulemedi")


def set_cpu_budget(cpu_seconds_per_call: int) -> None:
    """Worker uzun omurlu oldugu icin CPU limiti HER CAGRI icin yeniden kurulur."""
    if not _HAS_RESOURCE:
        return
    try:
        used = resource.getrusage(resource.RUSAGE_SELF)
        soft = int(used.ru_utime + used.ru_stime) + cpu_seconds_per_call
        resource.setrlimit(resource.RLIMIT_CPU, (soft, resource.RLIM_INFINITY))
    except (ValueError, OSError):
        pass


def _worker_loop(obj, conn, memory_mb: int, cpu_seconds_per_call: int) -> None:
    """Ayri process icinde calisir: (metod, kwargs) alir, ("ok"/"err", deger) yollar."""
    drop_privileges()
    set_memory_limit(memory_mb)
    while True:
        try:
            msg = conn.recv()
        except (EOFError, OSError):
            return
        if msg is None:
            return
        method, kwargs = msg
        set_cpu_budget(cpu_seconds_per_call)
        try:
            result = getattr(obj, method)(**kwargs)
            conn.send(("ok", result))
        except MemoryError:
            conn.send(("err", f"BELLEK LIMITI ASILDI ({memory_mb}MB)"))
        except Exception as e:  # katilimci kodu her turlu hata verebilir
            try:
                conn.send(("err", f"{type(e).__name__}: {e}"))
            except Exception:
                return


class IsolatedWorker:
    def __init__(self, obj, memory_mb: int = 1024, cpu_seconds_per_call: int = 60):
        self._obj = obj
        self._memory_mb = memory_mb
        self._cpu_seconds_per_call = cpu_seconds_per_call
        self._proc = None
        self._conn = None

    # ---- yasam dongusu ----
    def _start(self) -> None:
        parent_conn, child_conn = mp.Pipe()
        proc = mp.Process(
            target=_worker_loop,
            args=(self._obj, child_conn, self._memory_mb, self._cpu_seconds_per_call),
            daemon=True,
        )
        proc.start()
        child_conn.close()
        self._proc, self._conn = proc, parent_conn

    def _stop(self) -> None:
        if self._proc is not None:
            if self._proc.is_alive():
                try:
                    self._proc.terminate()
                    self._proc.join(2)
                    if self._proc.is_alive():
                        self._proc.kill()
                        self._proc.join(2)
                except PermissionError:
                    # worker baska kullaniciya dustu (nobody) ve bu process'in oldurme yetkisi yok.
                    # Docker'da --cap-add KILL gerekir. Cokmek yerine uyar ve devam et.
                    import sys
                    print("[sandbox] UYARI: worker oldurulemedi (PermissionError). Container'da "
                          "--cap-add KILL verin; aksi halde takilan worker'lar artik process olarak kalir.",
                          file=sys.stderr, flush=True)
        if self._conn is not None:
            try:
                self._conn.close()
            except OSError:
                pass
        self._proc = self._conn = None

    def close(self) -> None:
        if self._conn is not None and self._proc is not None and self._proc.is_alive():
            try:
                self._conn.send(None)
                self._proc.join(2)
            except (OSError, ValueError):
                pass
        self._stop()

    # ---- cagri ----
    def call(self, method: str, timeout_s: float, **kwargs):
        """
        (basarili_mi, deger_ya_da_hata_mesaji) dondurur. ASLA exception firlatmaz.
        Timeout / crash durumunda worker oldurulur, sonraki cagri yenisini baslatir.
        """
        try:
            if self._proc is None or not self._proc.is_alive():
                self._stop()
                self._start()
            self._conn.send((method, kwargs))
        except Exception as e:
            self._stop()
            return False, f"worker baslatilamadi/mesaj gonderilemedi ({type(e).__name__}: {e})"

        t0 = time.time()
        try:
            if not self._conn.poll(timeout_s):
                self._stop()
                return False, f"TIMEOUT ({timeout_s}s) -- process sonlandirildi"
            kind, value = self._conn.recv()
        except (EOFError, OSError):
            code = self._proc.exitcode if self._proc is not None else None
            self._stop()
            return False, f"worker sonuc vermeden olu (exitcode={code}, {time.time()-t0:.1f}s)"
        except Exception as e:  # ornegin donen deger unpickle edilemedi
            self._stop()
            return False, f"sonuc okunamadi ({type(e).__name__}: {e})"
        return (kind == "ok"), value
