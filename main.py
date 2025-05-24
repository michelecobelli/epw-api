from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from city_to_epw import generate_epw_file
from supabase import create_client
import mimetypes

app = FastAPI()

# Enable CORS for frontend access (like from Lovable)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this to Lovable's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET")

# Create Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


class EPWRequest(BaseModel):
    city: str
    user_id: str
    project_id: str


@app.post("/epw")
async def generate_epw(request: EPWRequest):
    try:
        print(f"🔄 Request received for city: {request.city}")

        epw_path, epw_filename = generate_epw_file(request.city)

        if not os.path.exists(epw_path):
            raise HTTPException(status_code=500, detail="EPW file generation failed.")

        print(f"✅ EPW file saved at: {epw_path}")

        # Upload to Supabase Storage with overwrite enabled
        with open(epw_path, "rb") as file:
            file_data = file.read()
            response = supabase.storage.from_(SUPABASE_BUCKET).upload(
                f"{request.user_id}/{epw_filename}", file_data, {"upsert": True}
            )
            print("📤 Upload response:", response)

        # Construct public URL
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{request.user_id}/{epw_filename}"

        # Update the database with the new URL
        update_response = supabase.table("projects").update(
            {"epw_url": public_url}
        ).eq("id", request.project_id).execute()

        print("📝 DB Update response:", update_response)

        return {"epw_url": public_url}

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Something went wrong.")
