"""JSON stdin/stdout adapter for the Nitro backend."""

from __future__ import annotations

import json
import sys

from .design import build_fasta, design_construct


def main() -> int:
    """
    Hauptfunktion, die JSON-Daten von stdin einliest, verarbeitet und das Ergebnis auf stdout ausgibt.
    
    Returns:
        int: 0 bei erfolgreicher Verarbeitung, 1 bei Fehler
    """
    try:
        # JSON-Daten von der Standardeingabe (stdin) einlesen
        payload = json.load(sys.stdin)
        
        # Die Nutzlast an die design_construct-Funktion übergeben, um den genetischen Konstrukt zu entwerfen
        result = design_construct(payload)
        
        # Wenn der Nutzer FASTA-Format angefordert hat ("fasta" Flag in der Eingabe),
        # das Ergebnis in FASTA-Format konvertieren und zum result-Dictionary hinzufügen
        if payload.get("fasta"):
            result["fasta"] = build_fasta(result)
    
    # Fehlerbehandlung für verschiedene Fehlertypen während der Verarbeitung
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        # Bei einem Fehler eine Fehlermeldung als JSON auf stdout ausgeben
        json.dump({"ok": False, "error": str(error)}, sys.stdout)
        return 1

    # Erfolgreiche Verarbeitung: Ergebnis als JSON auf stdout ausgeben
    json.dump({"ok": True, "design": result}, sys.stdout)
    return 0


if __name__ == "__main__":
    # Das Programm starten und den Rückgabewert als Exit-Code weitergeben
    raise SystemExit(main())
