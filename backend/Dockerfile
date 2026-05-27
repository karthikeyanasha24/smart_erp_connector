# Render / Linux: FreeTDS + pymssql (no Microsoft ODBC required).
# Dashboard: set Runtime = Docker, Root Directory = backend.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends freetds-dev freetds-bin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV MSSQL_DRIVER=pymssql
ENV NODE_ENV=production

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-3000}
