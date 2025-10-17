# app/llm_generator.py

import os
import base64
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import tempfile # Use tempfile for cross-platform compatibility

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# Create a temp directory that works on all operating systems (including Windows)
TMP_DIR = Path(tempfile.gettempdir()) / "llm_attachments"
TMP_DIR.mkdir(parents=True, exist_ok=True)

def decode_attachments(attachments):
    """
    Decodes attachments and saves them to the temporary directory.
    """
    saved = []
    for att in attachments or []:
        name = att.get("name") or "attachment"
        url = att.get("url", "")
        if not url.startswith("data:"):
            continue
        try:
            header, b64data = url.split(",", 1)
            data = base64.b64decode(b64data)
            path = TMP_DIR / name
            with open(path, "wb") as f:
                f.write(data)
            saved.append({"name": name, "path": str(path)})
        except Exception as e:
            print(f"Failed to decode attachment {name}: {e}")
    return saved

def summarize_attachment_meta(saved):
    """
    Creates a text summary of attachments for the LLM prompt.
    """
    if not saved:
        return "No attachments."
    # ... (this function can be expanded as before)
    return f"{len(saved)} attachment(s) included."

def _strip_code_block(text: str) -> str:
    """
    Removes markdown code block formatting (```) from a string.
    """
    if "```" in text:
        parts = text.split("```")
        block = parts[1]
        # remove first line if it's a language hint (e.g., 'html')
        if '\n' in block:
            first_line, rest = block.split('\n', 1)
            if first_line.strip().isalpha():
                return rest.strip()
        return block.strip()
    return text.strip()

def generate_readme_fallback(brief: str):
    """Generates a simple fallback README.md."""
    return f"# README for Project\n\n**Brief:** {brief}"

def generate_app_code(brief: str, attachments=None, checks=None, round_num=1, prev_readme=None):
    """
    Generates an 'index.html' and 'README.md' using the OpenAI API.
    """
    saved_attachments = decode_attachments(attachments)
    attachments_meta = summarize_attachment_meta(saved_attachments)

    user_prompt = f"""
    You are an expert web developer.
    Task: {brief}
    Attachments summary: {attachments_meta}
    Output format rules:
    1.  Produce a complete, self-contained `index.html` file.
    2.  After the code, on a new line, write exactly: ---README.md---
    3.  After that, write a professional `README.md`.
    4.  Do not include any other commentary.
    """

    try:
        print(">>> Preparing to call OpenAI API...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # Use a valid, available model
            messages=[
                {"role": "system", "content": "You are a helpful coding assistant."},
                {"role": "user", "content": user_prompt}
            ]
        )
        text = response.choices[0].message.content or ""
        print("✅ Code generated successfully.")
    except Exception as e:
        print(f"⚠️ OpenAI API failed. Using fallback code. Error: {e}")
        text = f"<html><body><h1>Fallback App</h1><p>{brief}</p></body></html>\n---README.md---\n{generate_readme_fallback(brief)}"

    if "---README.md---" in text:
        code_part, readme_part = text.split("---README.md---", 1)
    else:
        code_part = text
        readme_part = generate_readme_fallback(brief)

    files = {
        "index.html": _strip_code_block(code_part),
        "README.md": _strip_code_block(readme_part)
    }
    return {"files": files, "attachments": saved_attachments}