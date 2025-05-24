from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from city_to_epw import run_epw_pipeline
from supabase import create_client
import os

app = FastAPI()

# Read Supabase config from environment
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.post("/epw")
async def generate_epw(request: Request):
    body = await request.json()
    city = body.get("city")
    user_id = body.get("user_id")
    project_id = body.get("project_id")

    if not all([city, user_id, project_id]):
        return JSONResponse(status_code=400, content={"error": "Missing city, user_id, or project_id"})

    epw_path = run_epw_pipeline(city)
    if not epw_path:
        return JSONResponse(status_code=500, content={"error": "EPW generation failed"})

    file_name = os.path.basename(epw_path)
    object_path = f"{user_id}/{file_name}"

    with open(epw_path, "rb") as f:
        supabase.storage.from_(SUPABASE_BUCKET).upload(object_path, f)

    public_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(object_path)

    # Save the EPW link in the projects table
    supabase.table("projects").update({"epw_url": public_url}).eq("id", project_id).execute()

    return JSONResponse(content={"epw_url": public_url})

# Local use
if __name__ == "__main__":
    city_name = input("Enter city name: ")
    result = run_epw_pipeline(city_name)
    print(result)
