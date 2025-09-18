FROM python:3.12-slim AS builder

RUN apt-get update && \
    apt-get install -y gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip setuptools wheel

COPY requirements.txt /app/requirements.txt
RUN pip install --prefix=/install -r /app/requirements.txt

FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y postgresql-client gzip && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

COPY main.py /app/main.py

WORKDIR /app

CMD ["python", "main.py"]
