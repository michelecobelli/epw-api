from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from city_to_epw import run_epw_pipeline
import os
import requests

app = FastAPI()

# 🔐 CORS setup for Lovable
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://acc69026-efcc-49c0-9bf2-870ed51b6b57.lovableproject.com",
        "https://*.lovableproject.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# 🔧 Supabase config
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
    try:
        body = await request.json()
        city = body.get("city")
        user_id = body.get("user_id")
        project_id = body.get("project_id")

        if not all([city, user_id, project_id]):
            return JSONResponse(status_code=400, content={"error": "Missing city, user_id, or project_id"})

        print(f"📍 Generating EPW for city: {city}")
        epw_path = run_epw_pipeline(city)
        if not epw_path:
            return JSONResponse(status_code=500, content={"error": "EPW generation failed"})

        file_name = os.path.basename(epw_path)
        folder_path = f"{user_id}/{project_id}"
        object_path = f"{folder_path}/{file_name}"
        upload_url = f"{storage_url}/{SUPABASE_BUCKET}/{object_path}"

        # 🧹 Clean up existing files in the project folder
        list_url = f"{storage_url}/list/{SUPABASE_BUCKET}"
        list_body = { "prefix": folder_path + "/" }

        print("📁 Checking for existing files to delete...")
        list_response = requests.post(list_url, headers=headers, json=list_body)

        if list_response.status_code == 200:
            files = list_response.json()
            paths = [file["name"] for file in files]

            if paths:
                print("🗑️ Deleting files:", paths)
                delete_url = f"{storage_url}/{SUPABASE_BUCKET}"
                delete_response = requests.request(
                    "DELETE", delete_url, headers=headers, json={"paths": paths}
                )
                print("🔁 Delete response:", delete_response.status_code, delete_response.text)
            else:
                print("✅ No existing files found.")
        else:
            print("⚠️ Could not list files for deletion:", list_response.status_code, list_response.text)

        # ⬆️ Upload new EPW file
        with open(epw_path, "rb") as f:
            upload = requests.put(upload_url, headers=headers, data=f)

        if upload.status_code >= 400:
            return JSONResponse(status_code=500, content={
                "error": "Upload to Supabase failed",
                "status": upload.status_code,
                "details": upload.text
            })

        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{object_path}"
        print("✅ EPW file uploaded successfully:", public_url)

        return JSONResponse(content={"epw_url": public_url})

    except Exception as e:
        print("🔥 Server error:", str(e))
        return JSONResponse(status_code=500, content={"error": "Internal server error", "details": str(e)})
