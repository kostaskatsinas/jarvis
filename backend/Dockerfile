FROM python:3.12-slim
# git powers the dev agent's workspace tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e .
COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn jarvis.main:app --host 0.0.0.0 --port 8000"]
