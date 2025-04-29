from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI app
app = FastAPI()

# CORS Middleware (allow frontend domain)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://quickestimate.site"],  # ✅ Your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Endpoint 1: Basic Ping (CORS Sanity Test)
# -------------------------
@app.get("/ping")
async def ping():
    return {"message": "CORS is working perfectly!"}

# -------------------------
# Endpoint 2: Test CORS manually (Optional)
# -------------------------
@app.get("/test-cors")
async def test_cors():
    return {"message": "Test CORS endpoint OK"}
