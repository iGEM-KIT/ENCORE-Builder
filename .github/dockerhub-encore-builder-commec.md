# ENCORE-Builder: biosecurity screening

Screening container (COMMEC by IBBIS) of the ENCORE-Builder. It checks every gene sequence you enter against a list of known
toxins, virulence factors and regulated pathogens. It is started together with
[`igemkit/encore-builder`](https://hub.docker.com/r/igemkit/encore-builder).

**Step by step instructions with Docker Desktop:**
[github.com/iGEM-KIT/ENCORE-Builder](https://github.com/iGEM-KIT/ENCORE-Builder#readme)

The databases (about 1.2 GB) are downloaded on the first start into the volume `/databases`.
