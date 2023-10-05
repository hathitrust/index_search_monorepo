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
    # Disable pip's cache, then reduce the size of the image
    PIP_NO_CACHE_DIR=off \
    # Save runtime because it is not look for updating pip version
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

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
    # Install dependencies
    && pip install -r requirements.txt \
    # Clean up
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

FROM python-base as development
ENV FASTAPI_ENV=development

WORKDIR /app

COPY . .

#RUN chown appuser:appuser -R /app
USER appuser