# =========================================
# 1. Base image (share by all apps)
# =========================================
ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.11.5

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM python:${PYTHON_VERSION}-slim-bookworm AS base

# Create the user in the base stage, so all later stages inherit the user setup.
ARG UID=1000
ARG GID=1000

# Create our users here in the last layer or else it will be lost in the previous discarded layers
# Create a system group named "app_user" with the -r flag
RUN groupadd -g ${GID} -o app
RUN useradd -m -d /workspace -u ${UID} -g ${GID} -o -s /bin/bash app

# Create workspace directory to keep the same repo layout inside the container and set permissions for the app user
WORKDIR /workspace

# install uv (https://github.com/astral-sh/uv)
# docs for using uv with Docker: https://docs.astral.sh/uv/guides/integration/docker/
# ghcr.io/astral-sh/uv:latest is a small image with uv installed, we can copy the uv binary from there to our image
COPY --from=uv /uv /bin/uv

# UV_PROJECT_ENVIRONMENT configures the environment for the uv project interface
# UV_COMPILE_BYTECODE  Enable bytecode compilation
# UV_LINK_MODE Copy from the cache instead of linking since it's a mounted volume
# UV_FROZEN Enable frozen mode to make the virtual environment relocatable and not contain absolute paths
# PYTHONDONTWRITEBYTECODE prevents Python from writing .pyc files.
ENV UV_PROJECT_ENVIRONMENT=/workspace/.venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_FROZEN=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update -y \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    pkgconf \
    default-libmysqlclient-dev \
    openssh-client \
    git \
    gcc

# Clean up
RUN apt-get update \
    && apt-get -y autoremove \
    && apt-get -y clean \
    && rm -rf /var/lib/apt/lists/*


# =========================================
# 2. Python dependencies layer (per app, cached)
# =========================================
FROM base AS deps

# options: prod,dev
ARG ENV=dev
ARG APP_NAME
ARG APP_DIR

# RUN mkdir -p /tmp/uv-cache &&  chmod -R 777 /tmp/uv-cache

# Copy only dependency metadata
COPY --chown=${UID}:${GID} pyproject.toml uv.lock /workspace/

# Copy the libs to the workspace so they are available for the uv sync command to install them in the virtual environment
COPY --chown=${UID}:${GID} libs /workspace/libs

# Copy ONLY the app's pyproject (not full source)
COPY app/${APP_DIR}/pyproject.toml /workspace/app/${APP_DIR}/

# Install dependencies in a virtual environment using uv (cached unless lockfiles change)
# uv sync command is runing with root user. .venv will be created with root ownership, but we will change the ownership to the app user in the final image.
# The cache is mounted with root ownership, but uv will handle permissions correctly when copying from the cache to the virtual environment.
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$ENV" = "prod" ]; then \
        uv sync --package ${APP_NAME} --all-extras --no-dev; \
    else \
        uv sync --package ${APP_NAME} --all-extras; \
    fi


# =========================================
# 3. Final runtime image (per app)
# =========================================
FROM base AS runtime

ARG APP_NAME
ARG APP_DIR

# Runtime user is app, so in this stage we switch to the app user and set permissions for the workspace directory, app,
# venv and tmp/cache directories.

# Copy installed environment from deps stage
COPY --from=deps /workspace/.venv /workspace/.venv

# The owner of the files in the workspace should be the non-root user "app" to avoid permission issues when running as non-root in the final image
RUN chown -R ${UID}:${GID} /workspace/.venv

# Copy app code and Switch to the non-root user "app"
COPY --chown=${UID}:${GID} /app/${APP_DIR} /workspace/app/${APP_DIR}
COPY --chown=${UID}:${GID} libs /workspace/libs

# Ensure uv cache directory exists inside the app space with the correct permissions for the app user
ENV UV_CACHE_DIR=/workspace/.cache/uv
RUN mkdir -p /workspace/.cache/uv \
    && chown -R ${UID}:${GID} /workspace/.cache

# Add especific setup for each apps if need it.
RUN if [ "$APP_NAME" = "ht-indexer" ]; then \
    # document_generator_services uses /sdr folder to read zip and mets files \
      for i in $(seq 1 24); do ln -s /sdr/$i /sdr$i; done \
    fi

# Optional, it is valid for solr-query application.
ENV FASTAPI_ENV=runtime

USER app
WORKDIR /workspace/app/${APP_DIR}

# Add the code and the dependencies to the PYTHONPATH
ENV PYTHONPATH="/workspace/app/${APP_DIR}/src:/workspace/app/${APP_DIR}/tests:/workspace/libs/common_lib:/workspace/libs/ht_search"

CMD ["tail", "-f", "/dev/null"]