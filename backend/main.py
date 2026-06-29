from fastapi import FastAPI

app = FastAPI(title="BluePrint AI", version="0.1.0")


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "BluePrint AI backend is running",
        "endpoints": {
            "health": "GET /health",
            "design": "POST /design (not implemented yet)",
        },
    }


@app.get("/health")
def health():
    return {"status": "ok"}
