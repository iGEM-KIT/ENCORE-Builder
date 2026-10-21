# Optional sidecar for biosecurity screening via COMMEC ("Common
# Mechanism", IBBIS: https://github.com/ibbis-bio/common-mechanism). Deliberately
# NOT part of the main image: commec needs Conda and BLAST/HMMER, which do not fit
# into the slim main image. See commec-service/README.md for the trade-offs.
#
# Version: commec 1.0.4, the newest version that installs on every platform (Windows and
# Linux amd64, Mac and Linux arm64). commec itself is noarch, but 1.0.5 and 2.x need
# blast >=2.17, and bioconda has no blast 2.17 for linux-aarch64 (the architecture of Docker
# on Apple Silicon), so conda cannot solve them there. 1.0.4 needs blast >=2.16, which exists
# for linux-64 and linux-aarch64. No platform pin, so the image is built natively everywhere.
#
# Databases: NOT part of the image. The first start of the container downloads them
# (`commec setup`, see entrypoint.sh) into the volume /databases, so they survive a recreated
# container. The set is the curated biorisk + low-concern database (about 1.2 GB).
# The huge taxonomy databases (protein NR ~530 GB, nucleotide NT ~580 GB) are not downloaded;
# commec screen runs with --skip-tx --skip-nt (see app.py and README.md for the trade-offs).
FROM condaforge/miniforge3:latest

RUN conda config --add channels bioconda \
    && conda config --add channels conda-forge \
    && conda config --set channel_priority strict \
    && conda create -y -n commec-env commec=1.0.4 \
    && conda clean -afy

ENV PATH=/opt/conda/envs/commec-env/bin:$PATH
ENV COMMEC_DB_DIR=/databases

WORKDIR /app
COPY app.py entrypoint.sh ./
RUN chmod +x entrypoint.sh

VOLUME /databases
EXPOSE 8787
ENTRYPOINT ["/app/entrypoint.sh"]
