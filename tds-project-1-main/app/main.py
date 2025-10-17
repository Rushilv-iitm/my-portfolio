# app/main.py

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
import os, json, tempfile  # <-- FIX 1: Import tempfile
from pathlib import Path
from dotenv import load_dotenv
from app.llm_generator import generate_app_code, decode_attachments
from app.github_utils import (
    create_repo,
    create_or_update_file,
    enable_pages,
    generate_mit_license,
    create_or_update_binary_file
)
from app.notify import notify_evaluation_server

load_dotenv()
USER_SECRET = os.getenv("USER_SECRET")
USERNAME = os.getenv("GITHUB_USERNAME")

# -- FIX 2: Use a cross-platform temp directory --
PROCESSED_PATH = Path(tempfile.gettempdir()) / "processed_requests.json"

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "TDS Project API is running!"}

def load_processed():
    if os.path.exists(PROCESSED_PATH):
        try:
            with open(PROCESSED_PATH, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_processed(data):
    with open(PROCESSED_PATH, "w") as f:
        json.dump(data, f, indent=2)

def process_request(data):
    round_num = data.get("round", 1)
    task_id = data["task"]
    print(f"\n⚙️ Starting background process for task {task_id}")

    # --- LLM Generation ---
    gen = generate_app_code(
        brief=data["brief"],
        attachments=data.get("attachments", []),
        checks=data.get("checks", []),
        round_num=round_num
    )
    files = gen.get("files", {})
    
    # --- GitHub Automation ---
    repo = create_repo(task_id)

    for fname, content in files.items():
        create_or_update_file(repo, fname, content, f"feat: Add/update {fname}")

    mit_text = generate_mit_license()
    create_or_update_file(repo, "LICENSE", mit_text, "docs: Add MIT License")

    enable_pages(task_id)
    pages_url = f"https://{USERNAME}.github.io/{task_id}/"
    commit_sha = repo.get_commits()[0].sha

    # --- Notification ---
    payload = {
        "email": data.get("email"), "task": task_id, "round": round_num,
        "nonce": data.get("nonce"), "repo_url": repo.html_url,
        "commit_sha": commit_sha, "pages_url": pages_url,
    }
    notify_evaluation_server(data.get("evaluation_url"), payload)

    # --- Persistence ---
    processed = load_processed()
    key = f"{data.get('email')}::{task_id}::round{round_num}"
    processed[key] = payload
    save_processed(processed)

    print(f"✅ Finished round {round_num} for {task_id}")


@app.post("/api-endpoint")
async def receive_request(request: Request, background_tasks: BackgroundTasks): # <-- FIX 3: Add BackgroundTasks
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON format.")

    if data.get("secret") != USER_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret.")

    # Schedule the long-running job to run in the background
    background_tasks.add_task(process_request, data)

    # Return an immediate response to the client
    return {
        "status": "success",
        "message": "Request accepted and is being processed in the background.",
        "task_received": data.get("task")
    }