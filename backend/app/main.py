# FastAPI main application
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import os

# 确保数据目录存在
os.makedirs('data', exist_ok=True)

from .api import router as api_router
from .services.task_queue import task_queue
from .core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await task_queue.start()
    yield
    # Shutdown
    await task_queue.stop()

app = FastAPI(
    title="DramaGen API",
    description="AI Short Drama Generation Workbench API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api")

@app.get("/")
def root():
    return {
        "name": "DramaGen API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# WebSocket endpoint for real-time updates (kept for backward compatibility)
@app.websocket("/ws/updates")
async def websocket_updates(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Send periodic status updates
            await websocket.send_json({
                "type": "heartbeat",
                "timestamp": asyncio.get_event_loop().time()
            })
            await asyncio.sleep(5)
    except Exception:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
