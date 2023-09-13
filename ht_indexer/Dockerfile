FROM python:alpine as python-base

# Use this page as a reference for python and poetry environment variables: https://docs.python.org/3/using/cmdline.html#envvar-PYTHONUNBUFFERED
#Ensure the stdout and stderr streams are sent straight to terminal, then you can see the output of your application
ENV PYTHONUNBUFFERED=1\
    # Avoid the generation of .pyc files during package install
    PYTHONDONTWRITEBYTECODE=1 \
    # Disable pip's cache, then reduce the size of the image
    PIP_NO_CACHE_DIR=off \
    # Save runtime because it is not look for updating pip version
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    #
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PYSETUP_PATH="/opt/pysetup" \
    # I decided to use a virtual environment inside the docker file to be able to use multi stage builds in the future (https://docs.docker.com/build/building/multi-stage/)
    VENV_PATH="/opt/pysetup/.venv"

ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

# building dependencies
FROM python-base as builder-base
RUN apk update \
    && apk add build-base \
    && apk add gcc musl-dev libffi-dev openssl-dev cargo \
    && apk add python3-dev \
    && apk add curl \
    && apk add --no-cache mariadb-dev \
    && apk add pkgconfig \
    && apk del -r /var/lib/apt/lists/*

# Install Poetry - respects $POETRY_VERSION & $POETRY_HOME
# Specify POETRY_VERSION to avoid poetry might get an update and it will break your build. Installer will respect it
ENV POETRY_VERSION=1.5.1
RUN curl -sSL https://install.python-poetry.org | python3 -

#RUN SETUPTOOLS_USE_DISTUTILS=stdlib poetry install --no-ansi --no-interaction

# We copy our Python requirements here to cache them
# and install only runtime deps using poetry.
# The requeriments will only be reinstall when poetry.lock or pyproject.toml files change.
# This also prevent the buils won't be slow.
WORKDIR $PYSETUP_PATH
COPY ./poetry.lock ./pyproject.toml ./
#RUN poetry install --no-dev  # respects

#We could use the same Dockerfile for development and production.
#For use it in production environment, $ENVIRONMENT will control which dependencies set
# will be installed: all (default) or production only with --no-dev flag
# --no-interaction not to ask any interactive questions
# --no-ansi flag to make your output more log friendly
# I dediced to install dependencies with poetry instead than pip because pip doesn't actually solve your dependencies
RUN SETUPTOOLS_USE_DISTUTILS=stdlib poetry install $(test "$ENVIRONMENT" == production && echo "--no-dev") --no-interaction --no-ansi # respects

# 'development' stage installs all dev deps and can be used to develop code.
# For example using docker-compose to mount local volume under /app
FROM python-base as development
ENV FASTAPI_ENV=development

# Copying poetry and venv into image
COPY --from=builder-base $POETRY_HOME $POETRY_HOME
COPY --from=builder-base $PYSETUP_PATH $PYSETUP_PATH

# venv already has runtime deps installed we get a quicker install
WORKDIR $PYSETUP_PATH
RUN poetry install

WORKDIR /app
COPY . .

#Use this command to load the API with uvicorn, difficult to pass parameters
#CMD ["poetry", "run", "uvicorn", "main:app", "--reload"]
#CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8081", "--solr_host", "host.docker.internal", "--solr_port", "8983"]

CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8081", "--solr_url", "http://host.docker.internal:9033/solr/#/catalog/"]

CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8082", "--solr_url", "http://host.docker.internal:8983/solr/#/core-x/"]