FROM python:3.12-slim-bookworm AS base

ARG ENV=dev

# Create the user in the base stage, so all later stages inherit the user setup.
ARG UID=1000
ARG GID=1000

# Create our users here in the last layer or else it will be lost in the previous discarded layers
# Create a system group named "app_user" with the -r flag
RUN groupadd -g ${GID} -o app
RUN useradd -m -d /app -u ${UID} -g ${GID} -o -s /bin/bash app

ENV POETRY_HOME="/opt/poetry"
ENV PATH="$POETRY_HOME/bin:$PATH"

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

RUN curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /app
COPY --chown=${UID}:${GID} ./pyproject.toml ./poetry.lock /app/
# Copy the common libraries
COPY --chown=${UID}:${GID} ./libs ../libs/

# Installing dependencies
RUN if [ "${ENV}" = "dev" ]; then \
    echo "Installing dev dependencies" && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --with dev; \
    else \
    echo "Skipping dev dependencies" && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --without dev && rm -rf ${POETRY_CACHE_DIR}; \
    fi

# Clean up
RUN apt-get update \
    && apt-get -y autoremove \
    && apt-get -y clean \
    && rm -rf /var/lib/apt/lists/*

# Builder indexer stage
FROM base AS indexer

# document_generator_services uses /sdr folder to read zip and mets files
RUN for i in $(seq 1 24); do ln -s /sdr/$i /sdr$i; done

WORKDIR /app

# Switch to the non-root user "app"
COPY --chown=${UID}:${GID} /app/ht_indexer/ .

# Installing ht_indexer package and its dependencies
RUN if [ "${ENV}" = "dev" ]; then \
    echo "Installing dev dependencies" && \
    poetry config virtualenvs.create false && \
    poetry install  --with dev; \
    else \
    echo "Skipping dev dependencies" && \
    poetry config virtualenvs.create false && \
    poetry install  --without dev && rm -rf ${POETRY_CACHE_DIR}; \
    fi

USER app

WORKDIR /app

# Add the code and the dependencies to the PYTHONPATH
ENV PYTHONPATH="/app/ht_indexer/src:/app/ht_indexer/tests:/libs/common_lib:/libs/ht_search"

CMD ["tail", "-f", "/dev/null"]

# Builder solr_query stage
FROM base AS solr_query

ENV FASTAPI_ENV=runtime

WORKDIR /app

COPY --chown=${UID}:${GID} app/solr_query/ .

# Installing solr_query package and its dependencies
RUN if [ "${ENV}" = "dev" ]; then \
    echo "Installing dev dependencies" && \
    poetry config virtualenvs.create false && \
    poetry install  --with dev; \
    else \
    echo "Skipping dev dependencies" && \
    poetry config virtualenvs.create false && \
    poetry install  --without dev && rm -rf ${POETRY_CACHE_DIR}; \
    fi

USER app

WORKDIR /app

# Add the code and the dependencies to the PYTHONPATH
ENV PYTHONPATH="/app/solr_query/src:/app/solr_query/tests:/libs/common_lib:/libs/ht_search"

CMD ["tail", "-f", "/dev/null"]
