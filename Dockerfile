FROM python:3.11-slim

# Installa dipendenze di sistema minime
RUN apt-get update && apt-get install -y curl build-essential libpq-dev

# Installa Poetry
ENV POETRY_VERSION=1.8.2
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Crea directory dell'app
WORKDIR /app

# Copia solo i file necessari per installare le dipendenze
COPY pyproject.toml poetry.lock ./

# Installa le dipendenze senza creare ambiente virtuale interno
RUN poetry config virtualenvs.create false && poetry install --no-root --only main

# Copia il resto del progetto
COPY . .

# Comando di default
CMD ["gunicorn", "myproject.wsgi:application", "--bind", "0.0.0.0:8000"]
