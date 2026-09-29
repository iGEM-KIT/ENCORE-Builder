# Optionaler Sidecar fuer Biosicherheits-Screening via COMMEC ("Common
# Mechanism", IBBIS: https://github.com/ibbis-bio/common-mechanism). Bewusst
# NICHT Teil des Haupt-Images: commec braucht Conda und BLAST/HMMER — siehe
# README.md "Biosecurity screening" fuer wann/ob sich das lohnt.
#
# Datenbankumfang (verifiziert am echten `commec setup`, Version 1.0.4, nicht
# nur aus der Doku uebernommen — siehe commec-service/README.md fuer Details):
#   - Biorisk + Low-concern (kuratiert):  ~1.2 GB  <- das hier, per Default
#   - Protein-NR-Datenbank (Taxonomie):  ~530 GB   <- NICHT heruntergeladen
#   - Nukleotid-NT-Datenbank (Taxonomie): ~580 GB  <- NICHT heruntergeladen
# `commec setup -a` (voll automatisch) wuerde ALLES laden (~1.1TB) — bewusst
# nicht verwendet. Stattdessen wird die interaktive CLI hier mit einer festen
# Antwortsequenz gefuettert, die nur den kuratierten Biorisk/Low-concern-Satz
# waehlt. Ohne die NR/NT-Taxonomie-Datenbanken erkennt commec direkte
# Sequenztreffer gegen bekannte Toxine/Virulenzfaktoren/regulierte Organismen
# aus der kuratierten Liste, aber keine Taxonomie-Bestmatches gegen beliebige
# Organismen — siehe commec-service/README.md fuer die Kompromisse.
FROM condaforge/miniforge3:latest

RUN conda config --add channels bioconda \
    && conda config --add channels conda-forge \
    && conda config --set channel_priority strict \
    && conda create -y -n commec-env commec \
    && conda clean -afy

ENV PATH=/opt/conda/envs/commec-env/bin:$PATH
ENV COMMEC_DB_DIR=/databases

# `commec setup` hat KEIN -d/--databases Flag (anders als `commec screen`) —
# es fragt interaktiv nach dem Zielverzeichnis und den zu ladenden
# Datenbanken. Die Antwortsequenz hier (per stdin durchgereicht, verifiziert
# gegen den echten Ablauf):
#   1. Zielverzeichnis            -> ${COMMEC_DB_DIR}
#   2. Biorisk+Benign laden? (y/n) -> y   (~1.2 GB)
#   3. Biorisk-Download-URL        -> <Enter> (Standard-URL beibehalten)
#   4. Protein-NR laden? (y/n)     -> n   (~530 GB, bewusst uebersprungen)
#   5. Nukleotid-NT laden? (y/n)   -> n   (~580 GB, bewusst uebersprungen)
#   6. Taxonomie-DB laden? (y/n)   -> n   (<500 MB, hier bewusst weggelassen,
#                                          da ohne NR/NT kaum Mehrwert)
#   7. Bestaetigen                 -> <Enter>
RUN printf '%s\ny\n\nn\nn\nn\n\n' "${COMMEC_DB_DIR}" | commec setup

WORKDIR /app
COPY app.py ./app.py

EXPOSE 8787
CMD ["python3", "app.py"]
