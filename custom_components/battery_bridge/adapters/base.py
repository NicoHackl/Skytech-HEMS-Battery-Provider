"""Gemeinsamer Vertrag aller Hersteller-Adapter.

Coordinator und Platforms kennen ausschließlich dieses Protocol, nie Herstellerdetails
(siehe docs/architektur.md, Invariante 1). Ein neuer Adapter — neuer Hersteller oder neues
Protokoll für einen bestehenden Hersteller (D-006) — ist eine neue Datei unter `adapters/`,
keine Änderung an dieser Datei, am Coordinator oder an den Platforms.
"""

from __future__ import annotations

from typing import Protocol

from ..models import StorageState


class StorageAdapterError(Exception):
    """Ein Adapter-Aufruf ist fehlgeschlagen.

    Einheitliche Exception über alle Adapter hinweg, damit Coordinator und Config-Flow sie
    fangen können, ohne Herstellerdetails zu kennen (Invariante 1 in docs/architektur.md).
    Der Coordinator übersetzt sie in `UpdateFailed`/`ConfigEntryNotReady`.
    """


class StorageAdapter(Protocol):
    """Protocol, das jeder Hersteller-Adapter implementiert."""

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
