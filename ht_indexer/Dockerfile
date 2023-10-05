#PYTHON image
#Given the speed improvements in 3.11, more important than the base image is making sure you’re on an up-to-date release of Python.
# I will choose the official Docker Python image because it has
# the absolute latest bugfix version of Python
# it has the absolute latest system packages, the official Docker Python image is still your best bet, since it’s based on Debian Bookworm, released June 2023
# Debian 12 and the size is 51MB

#I abandonded alpine image because it lacks the package installer pip and the support for installing wheel packages, which are both needed for installing applications like Pandas and Numpy.
# Build the image takes time because I have to compile source files
# using some compiler packages like GCC
FROM python:3.11-slim-bookworm as python-base

# Use this page as a reference for python and poetry environment variables: https://docs.python.org/3/using/cmdline.html#envvar-PYTHONUNBUFFERED
#Ensure the stdout and stderr streams are sent straight to terminal, then you can see the output of your application
ENV PYTHONUNBUFFERED=1\
    # Avoid the generation of .pyc files during package install
    #PYTHONDONTWRITEBYTECODE=1 \
    # Disable pip's cache, then reduce the size of the image
    PIP_NO_CACHE_DIR=off \
    # Save runtime because it is not look for updating pip version
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    #
    PIP_DEFAULT_TIMEOUT=100
    #POETRY_HOME="/opt/poetry" \
    #POETRY_VIRTUALENVS_IN_PROJECT=true \
    #POETRY_NO_INTERACTION=1 \
    #PYSETUP_PATH="/opt/pysetup" \
    # I decided to use a virtual environment inside the docker file to be able to use multi stage builds in the future (https://docs.docker.com/build/building/multi-stage/)
    #VENV_PATH="/opt/pysetup/.venv"

#POETRY_VERSION=1.5.1

#RUN set -ex \
#    # Create a non-root user
#    && addgroup --system --gid 1001 appgroup \
#    && adduser --system --uid 1001 --gid 1001 --no-create-home appuser \

#RUN chown -R appuser:appuser /app

#ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

# building dependencies
#RUN set -ex \
#    && apt-get update \
#    && apt-get upgrade -y \
#    && apt-get install mariadb-server

USER root

WORKDIR /app

COPY requirements.txt ./

RUN set -ex \
    # Create a non-root user
    && addgroup --system --gid 1001 appgroup \
    && adduser --system --uid 1001 --gid 1001 --no-create-home appuser

    # Upgrade the package index and install security upgrades
RUN apt-get update -y \
    && apt-get upgrade -y \
    && apt-get -y install build-essential \
    curl \
    gcc \
    pkgconf \
    default-libmysqlclient-dev \
    #&& apt-get install mariadb-server \
    # Install dependencies
    && pip install -r requirements.txt #
    # Clean up
    #&& apt-get autoremove -y \
    #&& apt-get clean -y \
    #&& rm -rf /var/lib/apt/lists/*

#FROM python-base as builder-base
#RUN apk update \
#    && apk add build-base \
#    && apk add gcc musl-dev libffi-dev openssl-dev cargo \
#    && apk add python3-dev \
#    && apk add curl \
#    && apk add --no-cache mariadb-dev \
#    && apk add pkgconfig \
#    && apk del -r /var/lib/apt/lists/* \
#    && apk add bash \
#    && apk add openssh

# Install Poetry - respects $POETRY_VERSION & $POETRY_HOME
# Specify POETRY_VERSION to avoid poetry might get an update and it will break your build. Installer will respect it

#RUN curl -sSL https://install.python-poetry.org | python3 -

#RUN SETUPTOOLS_USE_DISTUTILS=stdlib poetry install --no-ansi --no-interaction

# We copy our Python requirements here to cache them
# and install only runtime deps using poetry.
# The requeriments will only be reinstall when poetry.lock or pyproject.toml files change.
# This also prevent the buils won't be slow.
#WORKDIR $PYSETUP_PATH
#COPY ./poetry.lock ./pyproject.toml ./
#RUN poetry install --no-dev  # respects

#We could use the same  for development and production.
#For use it in production environment, $ENVIRONMENT will control which dependencies set
# will be installed: all (default) or production only with --no-dev flag
# --no-interaction not to ask any interactive questions
# --no-ansi flag to make your output more log friendly
# I dediced to install dependencies with poetry instead than pip because pip doesn't actually solve your dependencies
#RUN SETUPTOOLS_USE_DISTUTILS=stdlib poetry install $(test "$ENVIRONMENT" == production && echo "--no-dev") --no-interaction --no-ansi # respects
#RUN poetry install -vvv
# 'development' stage installs all dev deps and can be used to develop code.
# For example using docker-compose to mount local volume under /app
FROM python-base as development
ENV FASTAPI_ENV=development

# Copying poetry and venv into image
#COPY --from=builder-base $POETRY_HOME $POETRY_HOME
#COPY --from=builder-base $PYSETUP_PATH $PYSETUP_PATH

# venv already has runtime deps installed we get a quicker install
#WORKDIR $PYSETUP_PATH
#RUN poetry install

WORKDIR /app

COPY . .

#RUN pip install

#RUN mkdir -p /tmp/indexing_data

#RUN chown appuser:appuser -R /tmp/indexing_data/ /app/
USER appuser


#RUN pip install -r requirements.txt