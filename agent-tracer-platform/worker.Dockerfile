FROM python:3.11-slim
WORKDIR /app

# Install SDK first
COPY agent-tracer-plus/pyproject.toml agent-tracer-plus/README.md ./agent-tracer-plus/
COPY agent-tracer-plus/src/ ./agent-tracer-plus/src/
RUN pip install --no-cache-dir -e "./agent-tracer-plus[postgres,clickhouse]"

# Install dependencies
COPY agent-tracer-platform/apps/worker/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker code
COPY agent-tracer-platform/apps/worker/ ./apps/worker/

CMD ["python", "apps/worker/main.py"]
