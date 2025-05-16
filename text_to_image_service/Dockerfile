FROM python:3.10-slim-bullseye

# Set environment variables to prevent interactive prompts during installations
ENV DEBIAN_FRONTEND=noninteractive

# Install sudo, procps, git, and other essentials.
# git is often useful for pip installs from repos or if any packages need it.
RUN apt-get update && \
    apt-get install -y --no-install-recommends sudo procps git ca-certificates && \
    rm -rf /var/lib/apt/lists/* && \
    useradd --create-home --uid 1002 --gid 0 appuser_image_gen && \
    echo "appuser_image_gen ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

USER appuser_image_gen
WORKDIR /home/appuser_image_gen/app
ENV PATH="/home/appuser_image_gen/.local/bin:${PATH}"
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8

# Ensure the Hugging Face cache directory exists and is writable by the user
# This is important for when a volume is mounted here.
RUN mkdir -p /home/appuser_image_gen/.cache/huggingface

COPY --chown=appuser_image_gen:root requirements.txt .

# Upgrade pip.
RUN python3 -m pip install --upgrade pip

# Install PyTorch and torchvision separately using the CPU-specific index.
RUN python3 -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchvision

# Install other dependencies from requirements.txt using the default PyPI index.
# Pip will skip torch and torchvision if they are already satisfied by the previous step.
RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser_image_gen:root . .

# Port for this service (e.g., 5003)
EXPOSE 5003

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5003"] 