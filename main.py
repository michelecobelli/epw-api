from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from city_to_epw import run_epw_pipeline
import os

app = FastAPI()

# 🔐 Allow requests from Lovable frontend
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


@app.post("/epw")
async def generate_epw(request: Request):
    try:
        body = await request.json()
        city = body.get("city")

        if not city:
            print("❌ Missing city in request")
            return JSONResponse(status_code=400, content={"error": "Missing city"})

        print(f"📍 Generating EPW for city: {city}")
        epw_path = run_epw_pipeline(city)

        if not epw_path:
            print("❌ EPW generation failed")
            return JSONResponse(status_code=500, content={"error": "EPW generation failed"})

        print("✅ EPW file generated at:", epw_path)
        return JSONResponse(content={"epw_path": epw_path})

    except Exception as e:
        print("🔥 Server error:", str(e))
        return JSONResponse(status_code=500, content={"error": "Internal server error", "details": str(e)})
