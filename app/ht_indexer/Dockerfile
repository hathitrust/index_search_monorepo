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

# document_generator_services uses /sdr folder to read zip and mets files
RUN for i in $(seq 1 24); do ln -s /sdr/$i /sdr$i; done


ARG UID=1000
ARG GID=1000

# Create our users here in the last layer or else it will be lost in the previous discarded layers
# Create a system group named "app_user" with the -r flag
RUN groupadd -g ${GID} -o app
RUN useradd -m -d /app -u ${UID} -g ${GID} -o -s /bin/bash app

# RUN which pip && sleep 10
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

# Copy dependencies to the image
COPY --chown=${UID}:${GID} common_lib/ common_lib/

# Copy dependencies to the image
COPY --chown=${UID}:${GID} ht_search/ ht_search/

# Add the code and the dependencies to the PYTHONPATH
ENV PYTHONPATH="/app/src:/app/common_lib:/app/ht_search"

CMD ["tail", "-f", "/dev/null"]


