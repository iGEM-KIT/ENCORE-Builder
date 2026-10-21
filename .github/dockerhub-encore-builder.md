# ENCORE-Builder

Design tool for planning an encapsulin cargo construct with the Golden Gate toolKIT of iGEM KIT, plus the
Open NC Database to find the matching shell. It runs on your own computer inside Docker.

This image needs its partner image [`igemkit/encore-builder-commec`](https://hub.docker.com/r/igemkit/encore-builder-commec)
(biosecurity screening). Without the screening the Builder does not calculate any construct.

**Step by step instructions with Docker Desktop:**
[github.com/iGEM-KIT/ENCORE-Builder](https://github.com/iGEM-KIT/ENCORE-Builder#readme)

Short version for the terminal: download
[docker-compose.pull.yml](https://github.com/iGEM-KIT/ENCORE-Builder/blob/main/docker-compose.pull.yml) and run

```
docker compose -f docker-compose.pull.yml up -d
```

Then open http://localhost:3000. The first start takes several minutes, because the screening downloads its databases once.
