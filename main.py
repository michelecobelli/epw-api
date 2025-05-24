from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from city_to_epw import run_epw_pipeline
import os
import requests
import traceback

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


@app.get("/")
async def root():
    return {"message": "EPW API is live. Use POST /epw to generate files."}


@app.post("/epw")
async def generate_epw(request: Request):
    try:
        body = await request.json()
        city = body.get("city")
        user_id = body.get("user_id")
        project_id = body.get("project_id")
        force = body.get("force", False)

        if not all([city, user_id, project_id]):
            return JSONResponse(status_code=400, content={"error": "Missing fields"})

        # Step 1: Check if project already has epw_url
        get_project_url = f"{rest_url}/projects?id=eq.{project_id}&select=epw_url"
        project_response = requests.get(get_project_url, headers=headers)
        if project_response.status_code == 200:
            data = project_response.json()
            if data and data[0].get("epw_url") and not force:
                existing_url = data[0]["epw_url"]
                file_path = existing_url.split(f"/{SUPABASE_BUCKET}/")[-1]
                check_url = f"{storage_url}/{SUPABASE_BUCKET}/{file_path}"
                check = requests.head(check_url, headers=headers)
                if check.status_code == 200:
                    return JSONResponse(content={"epw_url": existing_url})
                else:
                    print("🟡 File missing in bucket, regenerating...")

        # Step 2: Generate EPW
        epw_path = run_epw_pipeline(city)
        if not epw_path:
            return JSONResponse(status_code=500, content={"error": "EPW generation failed"})

        file_name = os.path.basename(epw_path)
        object_path = f"{user_id}/{file_name}"
        upload_url = f"{storage_url}/{SUPABASE_BUCKET}/{object_path}?upsert=true"

        # Step 3: Upload EPW to Supabase
        with open(epw_path, "rb") as f:
            upload = requests.post(upload_url, headers=headers, data=f)
        if upload.status_code >= 400:
            print("❌ Upload failed:", upload.status_code, upload.text)
            return JSONResponse(status_code=500, content={"error": "Upload failed"})

        # Step 4: Store public URL and update database
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{object_path}"
        patch_url = f"{rest_url}/projects?id=eq.{project_id}"
        patch_headers = headers.copy()
        patch_headers["Content-Type"] = "application/json"
        patch = requests.patch(patch_url, headers=patch_headers, json={"epw_url": public_url})

        if patch.status_code >= 400:
            print("❌ Database update failed:", patch.status_code, patch.text)
            return JSONResponse(status_code=500, content={"error": "Failed to update database"})

        return JSONResponse(content={"epw_url": public_url})

    except Exception as e:
        print("❌ Unhandled exception:")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "details": str(e)}
        )
