
from fastapi import FastAPI

app = FastAPI(
    title="VisionGuard API",
    description="Backend API for the VisionGuard model evaluation platform",
    version="0.1.0",
)


@app.get("/")
def home():
    return {"message": "VisionGuard backend is running"}


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "VisionGuard API",
    }
