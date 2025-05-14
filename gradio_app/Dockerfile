# gradio_app/Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies if any (e.g., for image processing if Gradio needs it for previews)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#    some-package \
#    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7860

# Replace main.py with your actual Gradio app's entry point script
CMD ["python", "main.py"] 