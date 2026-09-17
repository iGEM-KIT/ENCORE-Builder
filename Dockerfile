# ENCORE Builder — Nuxt frontend/API + the Biologik Python engine it shells out to.
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

# primer3-py gives real nearest-neighbor Tm/dimer checks. It is optional —
# Biologik falls back to a Wallace-rule estimate (with a warning in the API
# response) when it is missing, so a failed install here must not break the
# image build.
COPY Biologik/requirements.txt ./Biologik/requirements.txt
RUN pip install --no-cache-dir --break-system-packages -r Biologik/requirements.txt \
    || echo "primer3-py install failed — Biologik will fall back to Wallace Tm estimates"

COPY --from=build /app/.output ./.output
COPY --from=build /app/Biologik ./Biologik

ENV HOST=0.0.0.0
ENV PORT=3000
# server/utils/biologik.js resolves the Biologik package relative to the
# process cwd unless this is set — pin it explicitly since a container's cwd
# is easy to get wrong.
ENV BIOLOGIK_ROOT=/app

EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
