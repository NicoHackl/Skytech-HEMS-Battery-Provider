"""Tests für den Soll/Ist-Vergleich (response_check.py, D-018/D-019) — ohne Home Assistant.

Ist kommt seit D-019 aus `sensor.hems_schnittstelle`; hier direkt als Argument.
"""

from __future__ import annotations

import pytest

from custom_components.battery_bridge.response_check import CHARGE, DISCHARGE, ResponseCheck


def _check(**kwargs) -> ResponseCheck:
    values = {"name": "Marstek", "time_s": 30, "min_request_w": 100, "max_actual_w": 20}
    values.update(kwargs)
    return ResponseCheck(**values)


def _run(check: ResponseCheck, steps: int, *, start: float = 0.0, step_s: float = 5.0, **kw):
    """`steps` HEMS-Zyklen im Abstand `step_s`; liefert die Endzeit."""
    now = start
    for _ in range(steps):
        now += step_s
        check.update(now, interval_s=3, **kw)
    return now


_DISCHARGE_REFUSED = {"requested_w": 528, "charge_w": 0.0, "discharge_w": 0.0, "soc": 12}


def test_verweigerte_entladung_sperrt_nach_erkennungszeit() -> None:
    """Vorfall 19.10.2026: SoC 12 %, Sollwert bestätigt, Ist bleibt 0 W."""
    check = _check()
    check.update(0.0, interval_s=5, **_DISCHARGE_REFUSED)  # Startpunkt, zählt noch nichts
    now = _run(check, 5, **_DISCHARGE_REFUSED)
    assert not check.locked(DISCHARGE)  # 25 s
    changed = check.update(now + 5, interval_s=5, **_DISCHARGE_REFUSED)  # 30 s
    assert changed is True
    assert check.locked(DISCHARGE)
    assert check.lock_reason(DISCHARGE) == "keine_reaktion_entladen"
    assert check.release_soc(DISCHARGE) == 13
    assert not check.locked(CHARGE)


def test_fehlzeit_summiert_ueber_mehrere_anforderungen() -> None:
    """Pendeln wie am 18.10.2026: kurze Entladeanforderungen, dazwischen Laden."""
    check = _check()
    now = 0.0
    check.update(now, requested_w=0, charge_w=0, discharge_w=0, soc=12, interval_s=5)
    for _ in range(3):
        for _ in range(2):  # 10 s Entladen verweigert
            now += 5
            check.update(now, requested_w=1400, charge_w=0, discharge_w=0, soc=12, interval_s=5)
        now += 5  # Laden funktioniert
        check.update(now, requested_w=-400, charge_w=400, discharge_w=0, soc=12, interval_s=5)
    assert check.locked(DISCHARGE)
    assert not check.locked(CHARGE)


def test_lieferung_setzt_fehlzeit_zurueck() -> None:
    check = _check()
    check.update(0.0, interval_s=5, **_DISCHARGE_REFUSED)
    now = _run(check, 5, **_DISCHARGE_REFUSED)  # 25 s
    now += 5
    check.update(now, requested_w=528, charge_w=0, discharge_w=480, soc=12, interval_s=5)
    _run(check, 5, start=now, **_DISCHARGE_REFUSED)
    assert not check.locked(DISCHARGE)


def test_ohne_istwert_pausiert_der_vergleich() -> None:
    """Vom User festgelegt: fehlt der HEMS-Istwert, zählt keine Fehlzeit."""
    check = _check()
    check.update(0.0, requested_w=528, charge_w=None, discharge_w=None, soc=12, interval_s=5)
    _run(check, 20, requested_w=528, charge_w=None, discharge_w=None, soc=12)
    assert not check.locked(DISCHARGE)
    assert check.missed_s[DISCHARGE] == 0


def test_entladesperre_faellt_bei_soc_plus_ein_prozent() -> None:
    check = _check()
    check.update(0.0, interval_s=5, **_DISCHARGE_REFUSED)
    now = _run(check, 6, **_DISCHARGE_REFUSED)
    assert check.locked(DISCHARGE)

    now += 5
    check.update(now, requested_w=-300, charge_w=300, discharge_w=0, soc=12, interval_s=5)
    assert check.locked(DISCHARGE)
    now += 5
    changed = check.update(now, requested_w=-300, charge_w=300, discharge_w=0, soc=13, interval_s=5)
    assert changed is True
    assert not check.locked(DISCHARGE)
    assert check.missed_s[DISCHARGE] == 0  # nächste Anforderung wird neu geprüft


def test_ladesperre_faellt_bei_soc_minus_ein_prozent() -> None:
    check = _check()
    refused = {"requested_w": -800, "charge_w": 0, "discharge_w": 0, "soc": 60}
    check.update(0.0, interval_s=5, **refused)
    now = _run(check, 6, **refused)
    assert check.locked(CHARGE)
    assert check.release_soc(CHARGE) == 59
    check.update(now + 5, requested_w=0, charge_w=0, discharge_w=0, soc=59, interval_s=5)
    assert not check.locked(CHARGE)


def test_ohne_soc_bleibt_die_sperre() -> None:
    check = _check()
    check.update(0.0, interval_s=5, **_DISCHARGE_REFUSED)
    now = _run(check, 6, **_DISCHARGE_REFUSED)
    check.update(now + 5, requested_w=0, charge_w=0, discharge_w=0, soc=None, interval_s=5)
    assert check.locked(DISCHARGE)


@pytest.mark.parametrize("requested_w", [80, -80, 0])
def test_kleiner_sollwert_wird_nicht_geprueft(requested_w: float) -> None:
    check = _check()
    kw = {"requested_w": requested_w, "charge_w": 0, "discharge_w": 0, "soc": 12}
    check.update(0.0, interval_s=5, **kw)
    _run(check, 20, **kw)
    assert not check.locked(DISCHARGE)
    assert not check.locked(CHARGE)


def test_erkennungszeit_null_schaltet_ab() -> None:
    check = _check(time_s=0)
    check.update(0.0, interval_s=5, **_DISCHARGE_REFUSED)
    _run(check, 20, **_DISCHARGE_REFUSED)
    assert not check.locked(DISCHARGE)


def test_luecke_zaehlt_nicht_auf_einmal() -> None:
    """Nach einer Pause zählt höchstens das Doppelte des HEMS-Intervalls."""
    check = _check()
    check.update(0.0, interval_s=5, **_DISCHARGE_REFUSED)
    check.update(300.0, interval_s=5, **_DISCHARGE_REFUSED)
    assert check.missed_s[DISCHARGE] == 10
    assert not check.locked(DISCHARGE)
