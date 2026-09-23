"""Gemeinsamer Vertrag aller Hersteller-Adapter.

Coordinator und Platforms kennen ausschließlich dieses Protocol, nie Herstellerdetails
(siehe docs/architektur.md, Invariante 1). Ein neuer Adapter — neuer Hersteller oder neues
Protokoll für einen bestehenden Hersteller (D-006) — ist eine neue Datei unter `adapters/`,
keine Änderung an dieser Datei, am Coordinator oder an den Platforms.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol

from ..models import StorageState


class StorageAdapterError(Exception):
    """Ein Adapter-Aufruf ist fehlgeschlagen.

    Einheitliche Exception über alle Adapter hinweg, damit Coordinator und Config-Flow sie
    fangen können, ohne Herstellerdetails zu kennen (Invariante 1 in docs/architektur.md).
    Der Coordinator übersetzt sie in `UpdateFailed`/`ConfigEntryNotReady`.
    """


class StorageAdapterAuthError(StorageAdapterError):
    """Das Gerät hat die Zugangsdaten abgelehnt.

    Eigene Unterklasse, damit der Config-Flow „Zugangsdaten falsch" von „nicht erreichbar"
    unterscheiden kann (D-015). Alle anderen Aufrufer behandeln sie wie jede `StorageAdapterError`.
    """


class StorageAdapter(Protocol):
    """Protocol, das jeder Hersteller-Adapter implementiert."""

    # Takt, in dem die HEMS-Anbindung den aktuellen Sollwert erneut sendet (hems_bridge.py,
    # D-012/D-015). Hängt an der Rückfallzeit des jeweiligen Geräts: Marstek hält einen Sollwert
    # 300 s, E3DC nur rund 10 s.
    keepalive_interval: timedelta

    # Obergrenze der Soll-Leistungs-Entities (number.py) in W — geräteabhängig.
    max_power_w: int

    async def connect(self) -> None:
        """Verbindung aufbauen bzw. Transport vorbereiten.

        Wirft `StorageAdapterError`, wenn das Gerät beim Start nicht erreichbar ist.
        """
        ...

    async def read(self) -> StorageState:
        """Aktuellen Zustand abfragen.

        Wirft `StorageAdapterError`, wenn die Abfrage fehlschlägt (Timeout nach Retries,
        ungültige Antwort) — nie ein stillschweigend erratener Ersatzwert.
        """
        ...

    async def write_charge_power(self, watts: float) -> None:
        """Soll-Ladeleistung setzen. Meldet Fehler über eine Exception, nie stillschweigend."""
        ...

    async def write_discharge_power(self, watts: float) -> None:
        """Soll-Entladeleistung setzen. Meldet Fehler über eine Exception, nie stillschweigend."""
        ...

    async def close(self) -> None:
        """Transport sauber schließen."""
        ...
