# Optional sidecar for biosecurity screening via COMMEC ("Common
# Mechanism", IBBIS: https://github.com/ibbis-bio/common-mechanism). Deliberately
# NOT part of the main image: commec needs Conda and BLAST/HMMER; see
# README.md "Biosecurity screening" for when/whether that is worth it.
#
# Version: commec 2.1.0, the same as on the server (pip/conda only offers it for
# x86_64; on arm64 conda would silently fall back to the old 1.0.4, which has a different
# `commec setup`). That is why the image is built for linux/amd64 (emulated on Apple Silicon: slower, but the same version everywhere).
#
# Databases: NOT part of the image. The first start of the container downloads them
# (`commec setup -d`, see entrypoint.sh) into the volume /databases, so they survive a recreated
# container. The mandatory set is the curated biorisk + low-concern database plus best_match (about 6 GB download, about 40 GB on disk once unpacked: best_match alone is 36 GB).
# The huge taxonomy databases (protein NR ~530 GB, nucleotide NT ~580 GB) are not downloaded;
# commec screen runs with --skip-tx --skip-nt (see app.py and README.md for the trade-offs).
FROM --platform=linux/amd64 condaforge/miniforge3:latest

RUN conda config --add channels bioconda \
    && conda config --add channels conda-forge \
    && conda config --set channel_priority strict \
    && conda create -y -n commec-env commec=2.1.0 \
    && conda clean -afy

ENV PATH=/opt/conda/envs/commec-env/bin:$PATH
ENV COMMEC_DB_DIR=/databases

WORKDIR /app
COPY app.py entrypoint.sh ./
RUN chmod +x entrypoint.sh

VOLUME /databases
EXPOSE 8787
ENTRYPOINT ["/app/entrypoint.sh"]
