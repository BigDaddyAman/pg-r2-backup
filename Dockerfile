FROM python:3.13-slim-bookworm AS builder

RUN apt-get update && \
    apt-get install -y gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip setuptools wheel

COPY requirements.txt /app/requirements.txt
RUN pip install --prefix=/install -r /app/requirements.txt

FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y wget gnupg && \
    mkdir -p /etc/apt/keyrings && \
    wget -qO /etc/apt/keyrings/postgres.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc && \
    echo "deb [signed-by=/etc/apt/keyrings/postgres.asc] http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
    apt-get update && \
    apt-get install -y \
        postgresql-client-15 \
        postgresql-client-16 \
        postgresql-client-17 \
        postgresql-client-18 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

COPY main.py /app/main.py

WORKDIR /app

CMD ["python", "main.py"]
