FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
# This backend only ever runs CPU inference (see backend/main.py) -- the
# default PyPI torch wheel pulls in ~1GB+ of unused NVIDIA CUDA/cuDNN
# dependencies. Installing torch/torchvision from PyTorch's own CPU-only
# index first (then everything else from PyPI as normal) avoids that
# entirely, confirmed against a real build (Month 2 engineering pipeline)
# where the default index pulled a 553MB nvidia_cudnn wheel with nothing
# in this image ever able to use a GPU.
RUN pip install --no-cache-dir torch>=2.2 torchvision>=0.17 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY ml/ ./ml/
COPY configs/ ./configs/

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
