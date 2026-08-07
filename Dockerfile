# FleetPulse — single image serving the API and the built dashboard.
# Final Term Project · Hafsa Aqeel (53317)
#
# Two stages: Node builds the React bundle, Python runs everything. The Node
# toolchain does not ship in the final image — only the ~170 kB of built assets.

# ---------------------------------------------------------------- stage 1: SPA
FROM node:22-alpine AS frontend

WORKDIR /build

# Copy manifests first so `npm ci` is cached until a dependency actually changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ------------------------------------------------------------ stage 2: runtime
FROM python:3.13-slim AS runtime

# PYTHONUNBUFFERED so uvicorn and the simulator log in real time through docker logs.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    FLEETPULSE_SERVE_STATIC=1 \
    FLEETPULSE_STATIC_DIR=/app/static \
    FLEETPULSE_DATABASE_URL=sqlite:////data/fleetpulse.db

WORKDIR /app

# curl is used by the compose healthcheck and is handy for demonstrating the API.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY backend/app ./app
COPY backend/tests ./tests
COPY backend/pytest.ini ./pytest.ini
COPY --from=frontend /build/dist ./static
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# The SQLite file lives on a volume so the database survives a container restart
# and so the simulator container can read the fleet the API container seeded.
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["api"]
