FROM python:3.12-slim

# Системные зависимости для psycopg2 и Pillow
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Сначала копируем requirements — чтобы Docker кешировал слой
COPY mysite/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Потом копируем остальной код
COPY mysite/ .

EXPOSE 8000

# collectstatic и migrate теперь в docker-compose command,
# а не здесь — чтобы не падало при сборке без БД
CMD ["gunicorn", "mysite.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]