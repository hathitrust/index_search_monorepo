# The base layer will contain the dependencies shared by the other layers
FROM python:3.11-slim-bookworm AS base

# ENV=dev => development / ENV=prod => production
ARG ENV=dev

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

ENV POETRY_HOME="/opt/poetry"
ENV PATH="$POETRY_HOME/bin:$PATH"
RUN curl -sSL https://install.python-poetry.org | python3 -

# Install the app. Just copy the files needed to install the dependencies
COPY ./pyproject.toml ./poetry.lock ./
COPY ./common_lib /libs/common_lib/
COPY ./ht_search /libs/ht_search/

COPY --chown=app:app --chmod=0755 src/indexing_data.sh ./src/indexing_data.sh

# Poetry cache is used to avoid installing the dependencies every time the code changes, we will keep this folder in development environment and remove it in production
# --no-root, poetry will install only the dependencies avoiding to install the project itself, we will install the project in the final layer
# --without dev to avoid installing dev dependencies, we do not need test and linters in production environment
# --with dev to install dev dependencies, we need test and linters in development environment
# --mount, mount a folder for plugins with poetry cache, this will speed up the process of building the image
RUN if [ "${ENV}" = "dev" ]; then \
  echo "Installing dev dependencies" && \
  poetry config virtualenvs.create false && \
  poetry install --no-root --with dev; \
else \
  echo "Skipping dev dependencies" && \
  poetry config virtualenvs.create false && \
  poetry install --no-root --without dev && rm -rf ${POETRY_CACHE_DIR}; \
fi

# Set up our final runtime layer
FROM python:3.11-slim-bookworm AS runtime

ENV FASTAPI_ENV=runtime

ARG UID=1000
ARG GID=1000

# Create our users here in the last layer or else it will be lost in the previous discarded layers
# Create a system group named "app_user" with the -r flag
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

COPY --chown=${UID}:${GID} src/ src/
COPY --chown=${UID}:${GID} tests/ tests/

# Copy dependencies to the image
COPY --chown=${UID}:${GID} common_lib/ common_lib/

# Copy dependencies to the image
COPY --chown=${UID}:${GID} ht_search/ ht_search/

# Add the code and the dependencies to the PYTHONPATH
ENV PYTHONPATH="/app/src:/app/tests:/app/common_lib:/app/ht_search"

CMD ["tail", "-f", "/dev/null"]
