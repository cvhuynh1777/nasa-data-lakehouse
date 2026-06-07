FROM python:3.11-slim

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=300
ENV HF_HOME=/app/.cache/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers
ENV TRANSFORMERS_CACHE=/app/.cache/transformers

RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY rag/ ./rag/
COPY embeddings/ ./embeddings/
COPY ingestion/ ./ingestion/
COPY gold/ ./gold/
COPY query/ ./query/
COPY nl_query/ ./nl_query/
COPY storage/ ./storage/

# create cache dirs and make them world-writable for OpenShift random UID
# create cache dirs and make them world-writable for OpenShift random UID
RUN mkdir -p /app/.cache/huggingface \
             /app/.cache/sentence_transformers \
             /app/.cache/transformers && \
    chmod -R 777 /app/.cache && \
    chmod -R 777 /app/storage/chroma && \
    useradd -m appuser && \
    chown -R appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]