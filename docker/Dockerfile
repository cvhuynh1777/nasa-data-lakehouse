FROM python:3.11-slim

WORKDIR /app

# increase pip timeout for large packages
ENV PIP_DEFAULT_TIMEOUT=300

# install torch separately first with extended timeout
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# install remaining dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy source code
COPY api/ ./api/
COPY rag/ ./rag/
COPY embeddings/ ./embeddings/
COPY ingestion/ ./ingestion/
COPY gold/ ./gold/
COPY query/ ./query/
COPY nl_query/ ./nl_query/
COPY storage/ ./storage/

# non-root user for OpenShift compatibility
RUN useradd -m appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]