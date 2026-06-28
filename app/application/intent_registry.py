from __future__ import annotations

import logging
from typing import Callable

from app.application.app_state import AppState
from app.core.intents.base import Intent

_log = logging.getLogger("kartograph.intent_registry")

Handler = Callable[[Intent, AppState], AppState]


class IntentRegistry:
    """Ordnet Intent-Typen ihren Handlern zu und dispatcht eingehende Intents.

    Handler werden mit 2-wertiger Signatur registriert (intent, state).
    Der HandlerContext wird von Aufruferseite per Closure gebunden, bevor
    der Handler hier eingetragen wird.
    """

    def __init__(self) -> None:
        self._handlers: dict[type[Intent], Handler] = {}

    def register(self, intent_type: type[Intent], handler: Handler) -> None:
        """Registriert *handler* für *intent_type*.

        Ein bereits registrierter Handler wird überschrieben.

        Args:
            intent_type: Intent-Klasse, für die *handler* zuständig ist.
            handler: Callable mit Signatur ``(intent, state) -> state``.
        """
        self._handlers[intent_type] = handler

    def dispatch(self, intent: Intent, state: AppState) -> AppState:
        """Ruft den registrierten Handler für *intent* auf.

        Gibt *state* unverändert zurück, wenn kein Handler registriert ist
        oder der Handler eine Exception wirft.

        Args:
            intent: Auszuführender Intent.
            state: Aktueller AppState, der dem Handler übergeben wird.
        """
        handler = self._handlers.get(type(intent))
        if handler is None:
            _log.warning("Kein Handler für %s registriert", type(intent).__name__)
            return state
        try:
            return handler(intent, state)
        except Exception:
            _log.exception("Handler für %s hat eine Exception geworfen", type(intent).__name__)
            return state

    def registered_types(self) -> list[type[Intent]]:
        """Gibt alle registrierten Intent-Typen zurück (für Tests und Debug)."""
        return list(self._handlers)
