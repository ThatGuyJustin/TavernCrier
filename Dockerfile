ARG PYTHON_VERSION=3.12-alpine
FROM python:$PYTHON_VERSION

RUN apk update && \
    apk upgrade && \
    apk add git g++ bash

RUN python -m pip install poetry

COPY ./Docker/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint
COPY ./Docker/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start

ARG APP_HOME=/app
WORKDIR ${APP_HOME}

COPY poetry.lock /app/poetry.lock
COPY pyproject.toml /app/pyproject.toml

RUN poetry install --no-root

COPY . /app

#ENV DISCORD_TOKEN=${DISCORD_TOKEN}
#ENV FREE_KEYS_CHANNEL=${DISCORD_TOKEN}

ENTRYPOINT ["/start"]