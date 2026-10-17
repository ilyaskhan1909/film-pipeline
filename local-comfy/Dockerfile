FROM pytorch/pytorch:2.13.0-cuda13.0-cudnn9-runtime@sha256:db80a41f8428644cebcb3d75b0b62df334ab6c0e75785951eb25f48bfbd42407

ARG COMFY_COMMIT=6b747c0428c343e1417219641db93a4fb7cb69ae
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/data/cache/home \
    XDG_CACHE_HOME=/data/cache \
    HF_HOME=/data/cache/huggingface \
    TORCH_HOME=/data/cache/torch

COPY build_image.py /opt/build_image.py
RUN python /opt/build_image.py
ENV PATH=/opt/comfy-env/bin:${PATH}
COPY finalize_image.py /opt/finalize_image.py
RUN python /opt/finalize_image.py

WORKDIR /opt/ComfyUI
USER 1000:1000
EXPOSE 8188
CMD ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188", "--disable-auto-launch", "--disable-api-nodes", "--disable-all-custom-nodes", "--reserve-vram", "1.0", "--disable-pinned-memory", "--fast-disk", "--cache-none", "--models-directory", "/data/models", "--input-directory", "/data/input", "--output-directory", "/data/output", "--user-directory", "/data/user", "--temp-directory", "/tmp/comfy"]
