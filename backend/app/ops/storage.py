"""Storage policy of backup sets (ADR-024, A3): never let backups exhaust the disk.

Pure decisions (no I/O) so they can be tested for small and large volumes:

- **cap**: the managed backup folder may hold at most `max_total_gb` (default 10 GB);
- **reserve** (P1-E): after writing, the disk keeps free a *minimum reserve* (`min_free_gb`,
  default 10 GB) plus an *operational margin*: `margin_percent` % of the disk (default 5 %),
  capped at `margin_max_gb` (default 20 GB) but never less than twice the database (its growth
  and SQLite's temporary copy). The former 15 % of the whole disk suspended every backup on large
  disks that were merely busy (1 TB needed 150 GB free);
- **estimate before writing**: the peak of a new set is the temporary database copy plus the set
  itself; nothing starts unless that peak fits;
- **safe retention under pressure**: to make room, regular sets are removed oldest first, the
  intermediate ones (not the newest of their day) before the daily ones; the newest regular set,
  the safety copies taken before a restore and the imported sets are never removed here.

Recovery is never blocked by the cap, only by the reserve: the safety copy before a restore and
an imported set may exceed the cap, but never the free-space reserve.
"""

from dataclasses import dataclass, field

GB = 1024**3
LIMIT_DEFAULTS = {"max_total_gb": 10, "min_free_gb": 10, "margin_percent": 5, "margin_max_gb": 20}


def limits(config: dict) -> dict:
    """The storage limits of a configuration; a row saved with the former `min_free_percent`
    (P1-C) keeps that percentage as the operational margin."""
    values = {key: config.get(key) for key in LIMIT_DEFAULTS}
    if values["margin_percent"] is None and config.get("min_free_percent") is not None:
        values["margin_percent"] = config["min_free_percent"]
    return {key: int(LIMIT_DEFAULTS[key] if v is None else v) for key, v in values.items()}


def reserve_bytes(disk_total: int, config: dict, database: int = 0) -> int:
    """Free space that must remain on the disk: minimum reserve + operational margin."""
    values = limits(config)
    margin = min(disk_total * values["margin_percent"] // 100, values["margin_max_gb"] * GB)
    return values["min_free_gb"] * GB + max(margin, 2 * database)


def cap_bytes(config: dict) -> int:
    return limits(config)["max_total_gb"] * GB


@dataclass
class Plan:
    fits: bool
    remove: list[str] = field(default_factory=list)
    reason: str = ""
    estimate: int = 0
    peak: int = 0
    free_after: int = 0
    managed_after: int = 0


def gb(value: int) -> str:
    return f"{value / GB:.1f} GB".replace(".", ",")


def plan(
    *,
    estimate: int,
    peak: int,
    free: int,
    disk_total: int,
    managed: int,
    removable: list[tuple[str, int]],
    config: dict,
    bounded: bool = True,
    database: int = 0,
) -> Plan:
    """Decides whether a set of `estimate` bytes (peak `peak` while writing) can be written.

    `removable` lists (name, size) in the order they may be removed to make room. `bounded`
    is False for recovery copies, which only need the free-space reserve.
    """
    reserve = reserve_bytes(disk_total, config, database)
    cap = cap_bytes(config)
    remove, freed = [], 0

    def ok():
        room = free + freed - peak >= reserve
        under_cap = not bounded or managed - freed + estimate <= cap
        return room and under_cap

    for name, size in removable:
        if ok():
            break
        remove.append(name)
        freed += size
    result = Plan(
        fits=ok(),
        remove=remove,
        estimate=estimate,
        peak=peak,
        free_after=free + freed - estimate,
        managed_after=managed - freed + estimate,
    )
    if result.fits:
        return result
    result.remove = []  # nothing is removed when the set still would not fit
    if free + sum(size for _, size in removable) - peak < reserve:
        result.reason = (
            f"Espaço insuficiente no disco dos backups: o próximo backup precisa de cerca de "
            f"{gb(peak)} e o disco deve manter pelo menos {gb(reserve)} livres "
            f"(livres agora: {gb(free)}). Libere espaço ou escolha outra pasta."
        )
    else:
        result.reason = (
            f"O limite de {gb(cap)} para backups seria ultrapassado (o próximo precisa de cerca "
            f"de {gb(estimate)}, e os backups que não podem ser apagados automaticamente já "
            f"ocupam {gb(managed - sum(size for _, size in removable))}). Aumente o limite, "
            "apague cópias antigas de restauração ou importadas, ou escolha outra pasta."
        )
    return result


def removal_order(regular: list[tuple[str, int, str, bool]]) -> list[tuple[str, int]]:
    """Regular sets as (name, size, moment_text, newest_of_its_day), newest overall excluded.

    Intermediate sets go first, then daily ones; oldest first in each group.
    """
    ordered = sorted(regular, key=lambda item: item[2])
    if ordered:
        ordered = ordered[:-1]  # the newest regular set is never removed here
    intermediate = [(n, s) for n, s, _, daily in ordered if not daily]
    daily = [(n, s) for n, s, _, is_daily in ordered if is_daily]
    return intermediate + daily
