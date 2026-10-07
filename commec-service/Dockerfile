# Optional sidecar for biosecurity screening via COMMEC ("Common
# Mechanism", IBBIS: https://github.com/ibbis-bio/common-mechanism). Deliberately
# NOT part of the main image: commec needs Conda and BLAST/HMMER; see
# README.md "Biosecurity screening" for when/whether that is worth it.
#
# Database scope (verified against a real `commec setup`, version 1.0.4, not
# just taken from the docs; see commec-service/README.md for details):
#   - Biorisk + low-concern (curated):  ~1.2 GB  <- this one, by default
#   - Protein NR database (taxonomy):  ~530 GB   <- NOT downloaded
#   - Nucleotide NT database (taxonomy): ~580 GB  <- NOT downloaded
# `commec setup -a` (fully automatic) would download EVERYTHING (~1.1TB); deliberately
# not used. Instead the interactive CLI is fed here with a fixed
# answer sequence that only selects the curated biorisk/low-concern set.
# Without the NR/NT taxonomy databases commec detects direct
# sequence hits against known toxins/virulence factors/regulated organisms
# from the curated list, but no taxonomy best matches against arbitrary
# organisms; see commec-service/README.md for the trade-offs.
FROM condaforge/miniforge3:latest

RUN conda config --add channels bioconda \
    && conda config --add channels conda-forge \
    && conda config --set channel_priority strict \
    && conda create -y -n commec-env commec \
    && conda clean -afy

ENV PATH=/opt/conda/envs/commec-env/bin:$PATH
ENV COMMEC_DB_DIR=/databases

# `commec setup` has NO -d/--databases flag (unlike `commec screen`);
# it asks interactively for the target directory and the databases to
# download. The answer sequence here (passed through on stdin, verified
# against the real flow):
#   1. target directory            -> ${COMMEC_DB_DIR}
#   2. download biorisk+benign? (y/n) -> y   (~1.2 GB)
#   3. biorisk download URL        -> <Enter> (keep the default URL)
#   4. download protein NR? (y/n)  -> n   (~530 GB, deliberately skipped)
#   5. download nucleotide NT? (y/n) -> n   (~580 GB, deliberately skipped)
#   6. download taxonomy DB? (y/n) -> n   (<500 MB, deliberately left out here,
#                                          as it adds little without NR/NT)
#   7. confirm                     -> <Enter>
RUN printf '%s\ny\n\nn\nn\nn\n\n' "${COMMEC_DB_DIR}" | commec setup

WORKDIR /app
COPY app.py ./app.py

EXPOSE 8787
CMD ["python3", "app.py"]
