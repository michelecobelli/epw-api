from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from city_to_epw import run_epw_pipeline
import os
import requests

app = FastAPI()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET")

storage_url = f"{SUPABASE_URL}/storage/v1/object"
rest_url = f"{SUPABASE_URL}/rest/v1"

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

@app.post("/epw")
async def generate_epw(request: Request):
    body = await request.json()
    city = body.get("city")
    user_id = body.get("user_id")
    project_id = body.get("project_id")

    if not all([city, user_id, project_id]):
        return JSONResponse(status_code=400, content={"error": "Missing fields"})

    epw_path = run_epw_pipeline(city)
    if not epw_path:
        return JSONResponse(status_code=500, content={"error": "EPW generation failed"})

    file_name = os.path.basename(epw_path)
    object_path = f"{user_id}/{file_name}"
    upload_url = f"{storage_url}/{SUPABASE_BUCKET}/{object_path}"

    with open(epw_path, "rb") as f:
        upload = requests.post(upload_url, headers=headers, data=f)

    if upload.status_code >= 400:
        return JSONResponse(status_code=500, content={"error": "Upload failed"})

    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{object_path}"

    # ✅ PATCH the projects table
    patch_url = f"{rest_url}/projects?id=eq.{project_id}"
    patch_headers = headers.copy()
    patch_headers["Content-Type"] = "application/json"
    patch = requests.patch(patch_url, headers=patch_headers, json={"epw_url": public_url})

    if patch.status_code >= 400:
        return JSONResponse(status_code=500, content={"error": "Failed to update database"})

    return JSONResponse(content={"epw_url": public_url})
