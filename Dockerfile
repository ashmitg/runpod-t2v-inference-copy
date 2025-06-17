# Start from a clean base image
FROM runpod/worker-comfyui:5.1.0-base

# Set working directory
WORKDIR /

# Environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_PREFER_BINARY=1 \
    PYTHONUNBUFFERED=1 \
    CMAKE_BUILD_PARALLEL_LEVEL=8 \
    RUNPOD_USE_PYPI=true \
    SUPABASE_SERVICE_KEY="" \
    NEXT_PUBLIC_SUPABASE_URL="" \
    HF_TOKEN=""

# Install custom nodes using comfy-node-install
RUN comfy-node-install \
    https://github.com/ssitu/ComfyUI_UltimateSDUpscale.git \
    https://github.com/kijai/ComfyUI-KJNodes.git \
    https://github.com/rgthree/rgthree-comfy.git \
    https://github.com/JPS-GER/ComfyUI_JPS-Nodes.git \
    https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes.git \
    https://github.com/Jordach/comfy-plasma.git \
    https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git \
    https://github.com/bash-j/mikey_nodes.git \
    https://github.com/ltdrdata/ComfyUI-Impact-Pack.git \
    https://github.com/Fannovel16/comfyui_controlnet_aux.git \
    https://github.com/yolain/ComfyUI-Easy-Use.git \
    https://github.com/kijai/ComfyUI-Florence2.git \
    https://github.com/ShmuelRonen/ComfyUI-LatentSyncWrapper.git \
    https://github.com/WASasquatch/was-node-suite-comfyui.git \
    https://github.com/theUpsider/ComfyUI-Logic.git \
    https://github.com/cubiq/ComfyUI_essentials.git \
    https://github.com/chrisgoringe/cg-image-picker.git \
    https://github.com/chflame163/ComfyUI_LayerStyle.git \
    https://github.com/chrisgoringe/cg-use-everywhere.git \
    https://github.com/welltop-cn/ComfyUI-TeaCache.git \
    https://github.com/Fannovel16/ComfyUI-Frame-Interpolation.git \
    https://github.com/Jonseed/ComfyUI-Detail-Daemon.git \
    https://github.com/kijai/ComfyUI-WanVideoWrapper.git \
    https://github.com/M1kep/ComfyLiterals.git


# Install additional worker dependencies
RUN pip install runpod huggingface-hub requests supabase

# Download models using comfy-cli
RUN comfy model download --url https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp16.safetensors --relative-path models/text_encoders --filename umt5_xxl_fp16.safetensors
RUN comfy model download --url https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors --relative-path models/vae --filename wan_2.1_vae.safetensors
RUN comfy model download --url https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_t2v_14B_bf16.safetensors --relative-path models/diffusion_models --filename wan2.1_t2v_14B_bf16.safetensors
RUN comfy model download --url https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan21_CausVid_14B_T2V_lora_rank32.safetensors --relative-path models/loras --filename Wan21_CausVid_14B_T2V_lora_rank32.safetensors
RUN comfy model download --url https://huggingface.co/datasets/jibopabo/upscalers/resolve/89f2c89b11084729e995912390f8e2acf1c7b1e8/4xLSDIRDAT.pth --relative-path models/upscale_models --filename 4xLSDIR.pth
RUN comfy model download --url https://huggingface.co/Isi99999/Frame_Interpolation_Models/resolve/main/rife49.pth --relative-path custom_nodes/ComfyUI-Frame-Interpolation/ckpts/rife --filename rife49.pth

# Create output directory
RUN mkdir -p /ComfyUI/output/video

# Copy local files to appropriate locations
COPY rp_handler.py /
COPY wan_t2v_workflow_api.json /


# Set the command to run the worker
CMD ["python", "-u", "/rp_handler.py"]