FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y postgresql-client gcc libpq-dev gzip && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY main.py /app/main.py

WORKDIR /app

CMD ["python", "main.py"]