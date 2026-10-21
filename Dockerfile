# ENCORE-Builder: Nuxt frontend/API + the Biologik Python engine it shells out to.
# Node version matches package.json "engines"; Python is required at runtime by
# server/utils/biologik.js (it spawns `python3 -m Biologik.level0_design.cli`).
FROM node:22-slim AS build

RUN corepack enable

WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN corepack install
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

FROM node:22-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# primer3-py (pinned in Biologik/requirements.txt) gives the nearest-neighbor
# Tm/dimer checks. The build fails if it cannot be installed, so that every
# image computes the same primer values. primer3-py has no prebuilt wheel for
# linux/arm64, so it compiles from source: build-essential/python3-dev are
# installed just for this step and purged again in the same layer to keep the
# final image slim.
COPY Biologik/requirements.txt ./Biologik/requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential python3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --break-system-packages -r Biologik/requirements.txt \
    && apt-get purge -y --auto-remove build-essential python3-dev

COPY --from=build /app/.output ./.output
COPY --from=build /app/Biologik ./Biologik

ENV HOST=0.0.0.0
ENV PORT=3000
# server/utils/biologik.js resolves the Biologik package relative to the
# process cwd unless this is set; pin it explicitly since a container's cwd
# is easy to get wrong.
ENV BIOLOGIK_ROOT=/app
# Where the screening container is expected. The Compose files override this with the
# Compose service name; when both containers are started one by one in Docker Desktop
# (each with its published port), the host name below reaches the screening container.
ENV COMMEC_URL=http://host.docker.internal:8787

EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
