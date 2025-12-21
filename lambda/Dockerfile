# 1) Use AWS’s base image for Python 3.12
FROM public.ecr.aws/lambda/python:3.12-arm64

# 2) System packages as needed (keep minimal)
#   AL2023 uses dnf. Add only if some wheels need libs (often not needed for the packages below)
# RUN dnf install -y <libs> && dnf clean all

# 3) Copy and install deps


# --- Writable paths for AWS Lambda ---
# Redirect any cache/config/model writes to /tmp (the only writable FS)
ENV HOME=/tmp \
    TMPDIR=/tmp \
    XDG_CACHE_HOME=/tmp/.cache \
    XDG_CONFIG_HOME=/tmp/.config \
    TORCH_HOME=/tmp/torch \
    EASYOCR_MODULE_PATH=/tmp/easyocr \
    ULTRALYTICS_CACHE_DIR=/tmp/ultralytics

# Pre-create common writable directories
RUN mkdir -p /tmp/.cache /tmp/.config /tmp/torch /tmp/easyocr /tmp/ultralytics

COPY sa.json .
COPY requirements.txt .


RUN dnf install -y \
      mesa-libGL \
      mesa-libGLU \
      libXext \
      libXrender \
      libX11 \
    && dnf clean all
    
RUN dnf install ffmpeg
# RUN apt-get install ffmpeg
# RUN apt-get install libsm6
RUN pip install --no-cache-dir -r requirements.txt

# Preload models during build
COPY preload_models.py .
RUN python preload_models.py

# 4) Copy your function code
COPY lambda_function.py ${LAMBDA_TASK_ROOT}/
COPY bib_extraction.py ${LAMBDA_TASK_ROOT}/
COPY event.json ${LAMBDA_TASK_ROOT}/
COPY reel_generation.py ${LAMBDA_TASK_ROOT}/
# Note: yolov8n.pt will be downloaded automatically if not present, but it's preloaded above
# 5) Set the handler (module.function)
CMD ["lambda_function.lambda_handler"]
