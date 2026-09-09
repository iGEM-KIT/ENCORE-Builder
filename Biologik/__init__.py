"""ENCORE Biologik — die fachliche Logik des Builders.

Zwei unabhängige Unterpakete:

* ``level0_design`` — Golden-Gate-Design (Level 0/1/2, Order-Liste, FASTA).
  Reine Standardbibliothek, braucht keine externen Pakete.
* ``primer_design``  — Primerauswahl und Thermodynamik. Braucht ``primer3-py``
  (siehe ``Biologik/requirements.txt``).

Hier wird bewusst NICHTS importiert: ``import Biologik`` soll billig bleiben
und darf primer3 nicht voraussetzen, damit ``level0_design`` auch ohne
installiertes primer3 nutzbar ist.
"""
