FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.30" \
    "pydantic>=2.0" \
    "jinja2>=3.1" \
    "python-multipart>=0.0.9" \
    "mcp[cli]" \
    "python-dotenv>=1.0"

COPY src       ./src
COPY scripts   ./scripts
COPY dashboard_main.py ./

ENV PYTHONPATH=/app \
    PROTOCOL_DATA_DIR=/data \
    PERSISTENCE_BACKEND=sqlite \
    PYTHONUNBUFFERED=1

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

CMD ["/docker-entrypoint.sh"]
