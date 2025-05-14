# llm_service/Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Create a non-root user and group
RUN groupadd --system appuser && useradd --system --gid appuser appuser

# For python-slim (Debian-based), system dependencies are installed with apt-get.
# Usually not needed for fastapi, uvicorn, openai as wheels are often available.
# If a package did need compilation, you might install e.g.:
# RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev libffi-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Change ownership of the app directory to the appuser
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# FastAPI will run on port 5001 by default with uvicorn
EXPOSE 5001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5001"] 