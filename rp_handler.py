import os
import json
import uuid
import time
import requests
import shutil
import subprocess
from glob import glob
from typing import Dict
from huggingface_hub import hf_hub_download
from supabase import create_client, Client
import runpod

# ------------------------------- Configuration ------------------------------- #
COMFYUI_URL = "http://127.0.0.1:8188"
COMFYUI_PATH = "/ComfyUI"
LORA_FILENAME = "epoch_500.safetensors"
LORA_PATH = os.path.join(COMFYUI_PATH, "models", "loras")
LORA_FULL_PATH = os.path.join(LORA_PATH, LORA_FILENAME)
OUTPUT_VIDEO_DIR = os.path.join(COMFYUI_PATH, "output", "video")
WORKFLOW_FILE = os.path.join("/", "wan_t2v_workflow_api.json")

HF_TOKEN = os.environ.get("HF_TOKEN")
SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ------------------------------ ComfyUI Helpers ------------------------------ #
def start_comfyui():
    os.chdir(COMFYUI_PATH)
    process = subprocess.Popen(["python", "main.py", "--listen", "127.0.0.1", "--port", "8188"])
    print("Starting ComfyUI...")
    while True:
        try:
            res = requests.get(f"{COMFYUI_URL}/queue")
            if res.status_code == 200:
                print("ComfyUI is ready.")
                break
        except requests.ConnectionError:
            time.sleep(0.5)
    return process

def queue_prompt(prompt_workflow):
    res = requests.post(f"{COMFYUI_URL}/prompt", json={"prompt": prompt_workflow})
    res.raise_for_status()
    return res.json()['prompt_id']

def get_history(prompt_id):
    res = requests.get(f"{COMFYUI_URL}/history/{prompt_id}")
    res.raise_for_status()
    return res.json()

def wait_for_prompt(prompt_id):
    while True:
        history = get_history(prompt_id)
        if prompt_id in history and 'outputs' in history[prompt_id]:
            return
        time.sleep(1)

# ------------------------------- Video Handling ------------------------------- #
def list_mp4_files() -> set:
    return set(glob(os.path.join(OUTPUT_VIDEO_DIR, "*.mp4")))

def detect_new_video(before_files: set) -> str:
    after_files = list_mp4_files()
    new_files = after_files - before_files
    if not new_files:
        raise FileNotFoundError("No new video file found.")
    return max(new_files, key=os.path.getmtime)

def upload_to_supabase(file_path: str, organization_id: str, file_uuid: str) -> str:
    bucket_path = f"{organization_id}/videos/{file_uuid}.mp4"
    with open(file_path, 'rb') as f:
        supabase.storage.from_('content').upload(bucket_path, f)  # No upsert
    return f"{SUPABASE_URL}/storage/v1/object/public/content/{bucket_path}"

def cleanup_lora_file():
    try:
        if os.path.exists(LORA_FULL_PATH):
            os.remove(LORA_FULL_PATH)
            print(f"Deleted LoRA file: {LORA_FULL_PATH}")
    except Exception as e:
        print(f"Failed to delete LoRA file: {e}")

# ------------------------------ Job Processing ------------------------------ #
def process_single_video(workflow: dict, positive_prompt: str, negative_prompt: str,
                         organization_id: str, video_uuid: str, lora_filename: str) -> Dict:
    try:
        # NOTE: The following node IDs are hardcoded and will break if the workflow is changed.
        # A more robust solution would be to find nodes by their title or type.
        workflow["6"]["inputs"]["text"] = positive_prompt
        workflow["7"]["inputs"]["text"] = negative_prompt
        workflow["75"]["inputs"]["lora_02"] = lora_filename

        before_files = list_mp4_files()

        prompt_id = queue_prompt(workflow)
        wait_for_prompt(prompt_id)

        video_path = detect_new_video(before_files)
        url = upload_to_supabase(video_path, organization_id, video_uuid)

        return {"uuid": video_uuid, "url": url}
    except Exception as e:
        return {"uuid": video_uuid, "error": str(e)}

def process_job(job):
    job_input = job.get("input", {})
    required_fields = ['batch', 'organization_id', 'lora_repo_id']
    if not all(field in job_input for field in required_fields):
        return {"error": f"Missing required inputs: {', '.join(required_fields)}"}

    org_id = job_input["organization_id"]
    lora_repo = job_input["lora_repo_id"]

    # Download LoRA from Hugging Face
    # NOTE: This assumes the repo contains a LoRA file named exactly "epoch_500.safetensors".
    # This might be brittle if you use different LoRA models.
    try:
        hf_hub_download(
            repo_id=lora_repo,
            filename=LORA_FILENAME,
            local_dir=LORA_PATH,
            token=HF_TOKEN,
            force_filename=LORA_FILENAME
        )
        print(f"Downloaded LoRA: {LORA_FILENAME}")
    except Exception as e:
        return {"error": f"Failed to download LoRA: {str(e)}"}

    # Load workflow
    try:
        with open(WORKFLOW_FILE, 'r') as f:
            workflow_template = json.load(f)
    except Exception as e:
        return {"error": f"Failed to load workflow JSON: {str(e)}"}

    results = []
    for video in job_input["batch"]:
        if not all(k in video for k in ['positive_prompt', 'negative_prompt', 'uuid']):
            results.append({"error": f"Invalid video request: {video}"})
            continue

        # Deep copy to ensure independence per video
        workflow_copy = json.loads(json.dumps(workflow_template))

        result = process_single_video(
            workflow=workflow_copy,
            positive_prompt=video["positive_prompt"],
            negative_prompt=video["negative_prompt"],
            organization_id=org_id,
            video_uuid=video["uuid"],
            lora_filename=LORA_FILENAME
        )
        results.append(result)

    cleanup_lora_file()
    return {"batch_results": results}

# ----------------------------- RunPod Entry Point ----------------------------- #
def handler(event):
    try:
        print(f"Processing job: {event.get('id')}")
        return process_job(event)
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

# ----------------------------- Start Serverless Runtime ----------------------------- #
if __name__ == "__main__":
    comfyui_process = start_comfyui()
    print("Starting RunPod serverless handler...")
    runpod.serverless.start({"handler": handler})
    comfyui_process.terminate()
    print("ComfyUI process terminated.")
