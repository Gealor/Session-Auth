FROM python:3.12-slim-trixie

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_NO_DEV=1 \
    PYTHONPATH=/app 
# в каком каталоге искать модули и пакеты при импорте, пути указанные в PYTHONPATH добавляются в sys.path (вот где их можно посмотреть)

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project

COPY . /app
RUN uv sync --locked

CMD ["uv", "run", "src/main.py"]