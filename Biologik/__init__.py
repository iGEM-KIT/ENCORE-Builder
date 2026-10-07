"""ENCORE Biologik: the scientific logic of the builder.

Two independent subpackages:

* ``level0_design``: Golden Gate design (Level 0/1/2, order list, GenBank export).
  Standard library only, needs no external packages.
* ``primer_design``: primer selection and thermodynamics. Needs ``primer3-py``
  (see ``Biologik/requirements.txt``).

Nothing is imported here on purpose: ``import Biologik`` should stay cheap and must not
require primer3, so that ``level0_design`` stays usable without primer3 installed.
"""
