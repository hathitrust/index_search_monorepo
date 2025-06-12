FROM python:3.11-slim-bookworm AS base

ARG ENV=dev

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
COPY ./pyproject.toml ./poetry.lock /app/
COPY ./libs .

RUN if [ "${ENV}" = "dev" ]; then \
    echo "Installing dev dependencies" && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --with dev; \
    else \
    echo "Skipping dev dependencies" && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --without dev && rm -rf ${POETRY_CACHE_DIR}; \
    fi

FROM base AS ht_indexer

# document_generator_services uses /sdr folder to read zip and mets files
RUN for i in $(seq 1 24); do ln -s /sdr/$i /sdr$i; done


ARG UID=1000
ARG GID=1000

# Create our users here in the last layer or else it will be lost in the previous discarded layers
# Create a system group named "app_user" with the -r flag
RUN groupadd -g ${GID} -o app
RUN useradd -m -d /app -u ${UID} -g ${GID} -o -s /bin/bash app

# Clean up
RUN apt-get update \
    && apt-get -y autoremove \
    && apt-get -y clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the installed packages from the builder image
COPY --chown=${UID}:${GID} --from=base /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Switch to the non-root user "user"
USER app

WORKDIR /app

COPY --chown=${UID}:${GID} /app/ht_indexer/ .

# Add the code and the dependencies to the PYTHONPATH

#### Does this path need to be updated?
ENV PYTHONPATH="/app/ht_indexer/src:/app/libs/common_lib:/app/libs/ht_search"

CMD ["tail", "-f", "/dev/null"]


FROM base AS solr_query

ENV FASTAPI_ENV=runtime

ARG UID=1000
ARG GID=1000

RUN groupadd -g ${GID} -o app
RUN useradd -m -d /app -u ${UID} -g ${GID} -o -s /bin/bash app
RUN apt-get update && apt-get install -y curl

# Clean up
RUN apt-get update \
    && apt-get -y autoremove \
    && apt-get -y clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the installed packages from the builder image
COPY --chown=${UID}:${GID} --from=base /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Switch to the non-root user "user"
USER app

WORKDIR /app

COPY --chown=${UID}:${GID} app/solr_query/ .


# Add the code and the dependencies to the PYTHONPATH
ENV PYTHONPATH="/app/solr_query/src:/app/solr_query/tests:/app/libs/common_lib:/app/libs/ht_search"

CMD ["tail", "-f", "/dev/null"]
