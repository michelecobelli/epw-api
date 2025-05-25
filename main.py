from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from city_to_epw import run_epw_pipeline
import os
import requests

app = FastAPI()

# 🔐 Allow requests from Lovable frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "https://acc69026-efcc-49c0-9bf2-870ed51b6b57.lovableproject.com",
    "https://my-climate-app.lovable.so"
],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Supabase config from environment
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET")

storage_url = f"{SUPABASE_URL}/storage/v1/object"

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

@app.post("/epw")
async def generate_epw(request: Request):
    body = await request.json()
    city = body.get("city")
    user_id = body.get("user_id")

    if not all([city, user_id]):
        return JSONResponse(status_code=400, content={"error": "Missing city or user_id"})

    epw_path = run_epw_pipeline(city)
    if not epw_path:
        return JSONResponse(status_code=500, content={"error": "EPW generation failed"})

    file_name = os.path.basename(epw_path)
    object_path = f"{user_id}/{file_name}"
    upload_url = f"{storage_url}/{SUPABASE_BUCKET}/{object_path}"

    print("Uploading EPW to Supabase Storage...")
    with open(epw_path, "rb") as f:
        upload = requests.put(upload_url, headers=headers, data=f)
    print("Upload response:", upload.status_code, upload.text)

    if upload.status_code >= 400:
        return JSONResponse(status_code=500, content={"error": "Upload to Supabase Storage failed"})

    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{object_path}"
    return JSONResponse(content={"epw_url": public_url})
