FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    groupadd -g 10001 oi && useradd -u 10001 -g oi -M oi && \
    mkdir -p /data/documents && chown -R oi:oi /data/documents
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
USER oi
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
