FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd -g 10001 app && useradd -u 10001 -g app -M -s /usr/sbin/nologin app \
    && mkdir -p /data /documents && chown -R app:app /data /documents
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
