# Optionaler Sidecar fuer Biosicherheits-Screening via COMMEC v2 ("Common
# Mechanism", IBBIS: https://github.com/ibbis-bio/common-mechanism). Bewusst
# NICHT Teil des Haupt-Images: commec braucht Conda, BLAST/HMMER und ~40GB
# Referenzdatenbanken (~7-8GB Download) — siehe README.md "Biosecurity
# screening" fuer wann/ob sich das lohnt.
#
# `commec setup` laeuft HIER beim Image-Build und laedt die Datenbanken direkt
# ins Image — das macht das Image gross (~40GB+), aber der Container startet
# danach sofort screening-bereit, ohne bei jedem `docker compose up` erneut
# herunterzuladen. Wer die Datenbanken stattdessen in einem Volume halten will
# (kleineres Image, Download beim ersten Start statt beim Build), kann den
# `RUN commec setup` Schritt hier entfernen und ihn per `docker compose run`
# einmalig gegen ein gemountetes Volume ausfuehren.
FROM condaforge/miniforge3:latest

RUN conda config --add channels bioconda \
    && conda config --add channels conda-forge \
    && conda config --set channel_priority strict \
    && conda create -y -n commec-env commec \
    && conda clean -afy

ENV PATH=/opt/conda/envs/commec-env/bin:$PATH
ENV COMMEC_DB_DIR=/databases

# Datenbanken bereits beim Build herunterladen (siehe Kommentar oben) — das ist
# der Schritt, der in diesem Sandbox-Repo NICHT ausgefuehrt/verifiziert werden
# konnte (kein Netzwerkzugriff auf databases.commec.io von hier aus). Beim
# ersten echten `docker build` dieses Images passiert der eigentliche
# ~7-8GB-Download.
RUN commec setup -d ${COMMEC_DB_DIR}

WORKDIR /app
COPY app.py ./app.py

EXPOSE 8787
CMD ["python3", "app.py"]
