"""
core/registry.py

Yeni oyun eklerken buraya 2 satir eklemek yeterli.
"""

from core.validator import BasePuzzleValidator

_REGISTRY: dict[str, BasePuzzleValidator] = {}


def register_game(name: str, validator: BasePuzzleValidator) -> None:
    if name in _REGISTRY:
        raise ValueError(f"'{name}' zaten kayitli bir oyun.")
    _REGISTRY[name] = validator


def get_validator(name: str) -> BasePuzzleValidator:
    if name not in _REGISTRY:
        raise KeyError(f"'{name}' kayitli degil. Kayitli oyunlar: {list(_REGISTRY)}")
    return _REGISTRY[name]


def list_games() -> list[str]:
    return list(_REGISTRY.keys())


def _auto_register_defaults() -> None:
    from games.zip.validator import ZipValidator
    from games.queens.validator import QueensValidator
    from games.tango.validator import TangoValidator
    from games.patches.validator import PatchesValidator
    from games.slitherlink.validator import SlitherlinkValidator
    from games.numberlink.validator import NumberlinkValidator
    from games.hashi.validator import HashiValidator
    from games.lits.validator import LitsValidator
    from games.yinyang.validator import YinYangValidator
    from games.tapa.validator import TapaValidator

    if "zip" not in _REGISTRY:
        register_game("zip", ZipValidator())
    if "queens" not in _REGISTRY:
        register_game("queens", QueensValidator())
    if "tango" not in _REGISTRY:
        register_game("tango", TangoValidator())
    if "patches" not in _REGISTRY:
        register_game("patches", PatchesValidator())
    if "slitherlink" not in _REGISTRY:
        register_game("slitherlink", SlitherlinkValidator())
    if "numberlink" not in _REGISTRY:
        register_game("numberlink", NumberlinkValidator())
    if "hashi" not in _REGISTRY:
        register_game("hashi", HashiValidator())
    if "lits" not in _REGISTRY:
        register_game("lits", LitsValidator())
    if "yinyang" not in _REGISTRY:
        register_game("yinyang", YinYangValidator())
    if "tapa" not in _REGISTRY:
        register_game("tapa", TapaValidator())
