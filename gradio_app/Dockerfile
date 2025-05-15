# gradio_app/Dockerfile
FROM python:3.10-slim

# Set environment variables for Python
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8

WORKDIR /app

# Create a non-root user and group
RUN groupadd --system appuser && useradd --system --gid appuser appuser

# System dependencies for Gradio or its dependencies (if any needed beyond wheels)
# For example, if a library needed by Gradio for image processing required libjpeg:
# RUN apt-get update && apt-get install -y --no-install-recommends libjpeg-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Change ownership of the app directory to the appuser
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Gradio typically runs on port 7860
EXPOSE 7860

# Replace main.py with your actual Gradio app's entry point script
CMD ["python", "main.py"] 