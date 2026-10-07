"""Tests für die Lebenszeichen-Regeln (heartbeat.py, D-016) — ohne Home Assistant."""

from __future__ import annotations

from custom_components.battery_bridge.heartbeat import FALLBACK_TIMEOUT_S, HemsHeartbeat


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _beat(clock: _Clock | None = None, factor: float = 3) -> tuple[HemsHeartbeat, _Clock]:
    clock = clock or _Clock()
    return HemsHeartbeat(factor, clock), clock


def test_vorgefundener_wert_beim_start_ist_nicht_frisch() -> None:
    hb, _ = _beat()
    hb.observe("57", {"zyklus_intervall_s": 30})
    assert hb.is_fresh() is False


def test_aenderung_nach_dem_start_ist_frisch() -> None:
    hb, _ = _beat()
    hb.observe("57", {"zyklus_intervall_s": 30})
    hb.observe("58", {"zyklus_intervall_s": 30})
    assert hb.is_fresh() is True


def test_erscheinen_nach_fehlender_entitaet_zaehlt_als_frischer_zyklus() -> None:
    # Nach einem HA-Neustart fehlt die Entität; der erste Wert des HEMS ist ein neuer Zyklus.
    hb, _ = _beat()
    hb.observe(None)
    hb.observe("1", {"zyklus_intervall_s": 30})
    assert hb.is_fresh() is True


def test_gleicher_wert_ist_keine_aenderung() -> None:
    hb, _ = _beat()
    hb.observe("5")
    hb.observe("5")
    assert hb.is_fresh() is False


def test_frist_ist_faktor_mal_intervall() -> None:
    hb, clock = _beat(factor=3)
    hb.observe("1", {"zyklus_intervall_s": 30})
    hb.observe("2", {"zyklus_intervall_s": 30})
    clock.now += 90
    assert hb.is_fresh() is True
    clock.now += 0.5
    assert hb.is_fresh() is False


def test_ohne_gueltiges_intervall_gelten_90_s() -> None:
    for attrs in ({}, {"zyklus_intervall_s": "abc"}, {"zyklus_intervall_s": 0},
                  {"zyklus_intervall_s": float("nan")}):
        hb, clock = _beat()
        hb.observe("1", attrs)
        hb.observe("2", attrs)
        assert hb.timeout_s == FALLBACK_TIMEOUT_S
        clock.now += FALLBACK_TIMEOUT_S + 1
        assert hb.is_fresh() is False


def test_unavailable_ist_nicht_frisch() -> None:
    hb, _ = _beat()
    hb.observe("1")
    hb.observe("2")
    hb.observe("unavailable")
    assert hb.is_fresh() is False


def test_zaehler_neustart_des_hems_ist_eine_aenderung() -> None:
    hb, _ = _beat()
    hb.observe("41")
    hb.observe("1")
    assert hb.is_fresh() is True
