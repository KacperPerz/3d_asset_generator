# llm_service/Dockerfile
FROM python:3.10-slim

# Set environment variables for Python
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8

WORKDIR /app

# Create a non-root user and group
RUN groupadd --system appuser && useradd --system --gid appuser appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Change ownership of the app directory to the appuser
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# FastAPI will run on port 8000 as configured in docker-compose.yml
EXPOSE 8000

# Default command, can be overridden by docker-compose
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]