#PYTHON image
#Given the speed improvements in 3.11, more important than the base image is making sure you're on an up-to-date release of Python.
# I will choose the official Docker Python image because it has
# the absolute latest bugfix version of Python
# it has the absolute latest system packages, the official Docker Python image is still your best bet, since it's based on Debian Bookworm, released June 2023
# Debian 12 and the size is 51MB

#I abandonded alpine image because it lacks the package installer pip and the support for installing wheel packages, which are both needed for installing applications like Pandas and Numpy.
# Build the image takes time because I have to compile source files
# using some compiler packages like GCC
FROM python:3.11-slim-bookworm AS base

# Allowing the argumenets to be read into the dockerfile. Ex:  .env > compose.yml > Dockerfile
ARG POETRY_VERSION=2.1.1
# ENV=dev => development / ENV=prod => production
ARG ENV=dev

WORKDIR /app

# Use this page as a reference for python and poetry environment variables: https://docs.python.org/3/using/cmdline.html#envvar-PYTHONUNBUFFERED
#Ensure the stdout and stderr streams are sent straight to terminal, then you can see the output of your application
ENV PYTHONUNBUFFERED=1\
    # Avoid the generation of .pyc files during package install
    # Disable pip's cache, then reduce the size of the image
    PIP_NO_CACHE_DIR=off \
    # Save runtime because it is not look for updating pip version
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    # Disable poetry interaction
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

RUN pip install poetry==${POETRY_VERSION}

# Upgrade the package index and install security upgrades
RUN apt-get update -y \
    && apt-get upgrade -y \
    && apt-get -y install build-essential \
    curl \
    pkgconf \
    default-libmysqlclient-dev \
    openssh-client \
    git \
    # Clean up
    && apt-get -y autoremove \
    && apt-get -y clean \
    && rm -rf /var/lib/apt/lists/*

# Install the app. Just copy the files needed to install the dependencies
COPY pyproject.toml poetry.lock README.md ./

# Poetry cache is used to avoid installing the dependencies every time the code changes, we will keep this folder in development environment and remove it in production
# --no-root, poetry will install only the dependencies avoiding to install the project itself, we will install the project in the final layer
# --without dev to avoid installing dev dependencies, we do not need test and linters in production environment
# --with dev to install dev dependencies, we need test and linters in development environment
# --mount, mount a folder for plugins with poetry cache, this will speed up the process of building the image
RUN if [ "${ENV}" = "dev" ]; then \
  echo "Installing dev dependencies" && \
  poetry install --no-root --with dev; \
else \
  echo "Skipping dev dependencies" && \
  poetry install --no-root --without dev && rm -rf ${POETRY_CACHE_DIR}; \
fi


# Set up our final runtime layer
FROM python:3.11-slim-bookworm AS runtime

ENV FASTAPI_ENV=runtime

RUN for i in $(seq 1 24); do ln -s /sdr/$i /sdr$i; done

ARG UID=1000
ARG GID=1000

# Create our users here in the last layer or else it will be lost in the previous discarded layers
# Create a system group named "app_user" with the -r flag
RUN groupadd -g ${GID} -o app
RUN useradd -m -d /app -u ${UID} -g ${GID} -o -s /bin/bash app
RUN mkdir -p /venv && chown ${UID}:${GID} /venv
RUN which pip && sleep 10
RUN apt-get update && apt-get install -y curl

# By adding /venv/bin to the PATH the dependencies in the virtual environment
# are used
ENV VIRTUAL_ENV=/venv \
  PATH="/venv/bin:$PATH"

COPY --chown=${UID}:${GID} --from=base "/app/.venv" ${VIRTUAL_ENV}

# Switch to the non-root user "user"
USER app

WORKDIR /app

ENV PYTHONPATH=/app

COPY --chown=${UID}:${GID} . /app



CMD ["tail", "-f", "/dev/null"]
