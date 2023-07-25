FROM python:3.11-slim-buster as base
RUN mkdir app
WORKDIR  /app
COPY /pyproject.toml /app
RUN pip3 install poetry
RUN poetry install
COPY . .
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8081"]