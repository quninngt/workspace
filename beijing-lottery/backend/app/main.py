"""FastAPI app for Beijing Lottery Simulator."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.router import router

app = FastAPI(title="北京摇号模拟器", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {"app": "北京摇号模拟器", "version": "0.1.0"}
