# Замечания по проекту

1. Отсутствие покрытия тестами
2. Отсутствие CORS
3. Отсутствие logging middleware
4. Отсутствие rate limiting
```псевдо-код для rate limiting с Redis и TTL
redis_client = redis.from_url(
    "redis://localhost:6379",
    encoding="utf-8",
    decode_responses=True
)

RATE_LIMIT = 5
WINDOW = 60  # секунд


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    ip = request.client.host  # можно заменить на user_id
    key = f"rate_limit:{ip}"

    # увеличиваем счётчик
    current = await redis_client.incr(key)

    # если это первый запрос — ставим TTL
    if current == 1:
        await redis_client.expire(key, WINDOW)

    if current > RATE_LIMIT:
        ttl = await redis_client.ttl(key)

        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Retry in {ttl} seconds"
        )

    response = await call_next(request)
    return response
```

5. datetime.now(tz=UTC).replace(tzinfo=None) — костыль для удаления timezone в UserDelete схеме
(5-ый пункт пофиксил, изменив в базе данных тип на DATETIME WITH TIMEZONE, и в UserDelete схеме изменил фабрику deleted_at на
lambda: datetime.now(UTC), важное уточнение в базе данных время будет ХРАНИТЬСЯ в формате UTC с информацией о таймзоне, если смотреть по СУБД типо pgAdmin4, DBeaver и т.д. там может ОТОБРАЖАТЬ время со смещением от UTC, но по факту мы будем получить время в формате UTC из ORM)

# Инструкция по развертыванию

## 1. Создание .env файла
Создайте в корневой папке проекта файл .env и скопируйте параметры из .env.template в новый файл. Если вы хотите задать свои данные для логина, пароля и имени базы данных, тогда поменяйте соответствующие поля POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, PGPORT

## 2. Генерация приватного и публичного ключей
Вводить команды в корневой папке проекта, не в src.
Приватный ключ:

```shell
# Generate an RSA private key, of size 2048
openssl genrsa -out src/core/auth/certs/jwt-private.pem 2048
```

Публичный ключ:

```shell
# Extract the public key from the key pair, which can be used in a certificate
openssl rsa -in src/core/auth/certs/jwt-private.pem -outform PEM -pubout -out src/core/auth/certs/jwt-public.pem
```

## 3. Поднятие docker-compose
В корневой папке проекта (где лежит docker-compose.yml) пропишите
```
docker compose build --no-cache
docker compose up
```

## 4. Применить alembic миграции
После поднятия контейнеров, пропишите в консоли, чтобы применить миграции
```
docker compose exec app sh -c "cd src && uv run alembic upgrade head" 
```

Чтобы откатить миграции пропишите
```
docker compose exec app sh -c "cd src && uv run alembic downgrade base" 
```

# Архитектура

## Схема базы данных

В проекте используется реляционная база данных PostgreSQL. Основные таблицы:

- `users` — пользователи системы:
  - `id` (PK)
  - `nickname`,
  - `email`, `password` (хэш пароля)
  - `is_active` (статус активности)
  - `banned_at`, `deleted_at` (soft delete / блокировка)

- `session_tokens` — хранение session-токенов, данная таблица сделана для хранения актуальных session токенов, т.к. они являются долгоживущими. Я посчитал, что функционал /logout должен работать по следующему принципу: пользователь дергает этот эндпоинт и его session токен затирается
  - `user_id` (PK для привязки к пользователю)
  - `session_token` (строка)