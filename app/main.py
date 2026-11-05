from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import logging

# (Assuming run_call is imported or defined above this in the same file)
# from your_module import run_call 

logger = logging.getLogger(__name__)

#Create the FastAPI app
app = FastAPI()

#GET /health route
@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Voice Agent Server is running"}

#WebSocket route with Disconnect handling
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Formally answer the incoming phone call
    await websocket.accept()
    
    logger.info("New WebSocket connection accepted.")
    
    try:
        # Hand the connected call over to your Factory Manager (run_call)
        await run_call(websocket)
        
    except WebSocketDisconnect:
        # Catch the hangup so it doesn't crash the whole server
        logger.info("Client disconnected from the WebSocket route.")