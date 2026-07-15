# Stage 1: Build the React Dashboard
FROM node:18-alpine AS frontend-builder
WORKDIR /app/dashboard
COPY agent-tracer-platform/apps/ui/package.json agent-tracer-platform/apps/ui/package-lock.json* ./
RUN npm install
COPY agent-tracer-platform/apps/ui/ ./
RUN npm run build

# Stage 2: Build the Python Server
FROM python:3.11-slim
WORKDIR /app

# Install SDK first
COPY agent-tracer-plus/pyproject.toml agent-tracer-plus/README.md ./agent-tracer-plus/
COPY agent-tracer-plus/src/ ./agent-tracer-plus/src/
RUN pip install --no-cache-dir -e "./agent-tracer-plus[postgres,clickhouse]"

# Install API requirements
COPY agent-tracer-platform/apps/api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && pip install gunicorn uvicorn

# Copy API source code
COPY agent-tracer-platform/apps/api/ ./apps/api/

# Copy built frontend
COPY --from=frontend-builder /app/dashboard/dist ./apps/ui/dist

# Copy Alembic files
COPY agent-tracer-platform/alembic/ ./alembic/
COPY agent-tracer-platform/alembic.ini ./

# Expose port and run server
EXPOSE 3000
CMD ["sh", "-c", "alembic upgrade head && gunicorn apps.api.app:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:3000"]
