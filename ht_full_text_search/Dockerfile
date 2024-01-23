FROM python:3.11-slim-bookworm as python-base

ENV PYTHONUNBUFFERED=1\
    # Avoid the generation of .pyc files during package install
    # Disable pip's cache, then reduce the size of the image
    PIP_NO_CACHE_DIR=off \
    # Save runtime because it is not look for updating pip version
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

USER root

WORKDIR /app

ENV PYTHONPATH "${PYTHONPATH}:/app"

RUN set -ex \
    # Create a non-root user
    && addgroup --system --gid 1001 appgroup \
    && adduser --system --uid 1001 --gid 1001 --no-create-home appuser

RUN --mount=type=cache,target=/var/lib/apt/lists \
    --mount=type=cache,target=/var/cache,sharing=locked \
    apt-get update \
    && apt-get upgrade --assume-yes \
    && apt-get install --assume-yes --no-install-recommends python3-pip

# Upgrade the package index and install security upgrades
#RUN apt-get update -y \
#    && apt-get upgrade -y \
#    && apt-get -y install build-essential \
#    curl \
#    pkgconf \
#    default-libmysqlclient-dev \
#    git \
#    # Clean up
#    && apt-get -y autoremove \
#    && apt-get -y clean \
#    && rm -rf /var/lib/apt/lists/*

FROM python-base as poetry

WORKDIR /app
# that contains poetry=<version> to install a specific version of Poetry.
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache python3.11 -m pip install --disable-pip-version-check --requirement=requirements.txt

# Do the conversion
COPY poetry.lock pyproject.toml ./
RUN poetry export --output=requirements.txt

FROM python-base as development

RUN --mount=type=cache,target=/root/.cache --mount=type=bind,from=poetry,source=/app,target=/poetry python3.11 -m pip install --disable-pip-version-check --no-deps --requirement=/poetry/requirements.txt

WORKDIR /app

COPY . .

ENTRYPOINT ["python3", "ht_full_text_search/ht_full_text_searcher.py", "--env", "dev", "--query_string", "\"chief justice\"", "--operator", "AND", "--query_config", "all"]

USER appuser