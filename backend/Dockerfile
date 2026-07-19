FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Healthcheck uses curl. The PostgreSQL client is required by the in-Railway
# backup worker; the current slim base provides a client compatible with prod.
RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates curl postgresql-client \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /app

EXPOSE 8000

CMD ["bash", "-lc", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
