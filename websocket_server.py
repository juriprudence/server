from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import logging
import os
from typing import Dict, Set

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

app = FastAPI()

# Add CORS middleware for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

clients: Set[WebSocket] = set()
clients_map: Dict[WebSocket, int] = {}
next_player_id = 1

@app.get("/", response_class=PlainTextResponse)
@app.head("/", response_class=PlainTextResponse)
async def health_check():
    """Health check endpoint for Render"""
    return "OK"

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global next_player_id
    
    await websocket.accept()
    
    player_id = next_player_id
    next_player_id += 1
    clients.add(websocket)
    clients_map[websocket] = player_id
    
    logging.info(f"Player {player_id} connected")
    
    try:
        # Send initial Join Success
        await websocket.send_text(json.dumps({
            "event": "join",
            "data": {"success": 1, "actorNr": player_id}
        }))
        
        # Notify others about new player
        join_msg = json.dumps({
            "event": "actorJoin",
            "data": {"actorNr": player_id}
        })
        for ws in list(clients):
            if ws != websocket:
                try:
                    await ws.send_text(join_msg)
                except:
                    pass
                    
        # Notify new player about existing players
        for ws, pid in clients_map.items():
            if ws != websocket:
                try:
                    await websocket.send_text(json.dumps({
                        "event": "actorJoin",
                        "data": {"actorNr": pid}
                    }))
                except:
                    pass

        # Handle incoming messages
        while True:
            # Use receive_json() which handles both text and binary frames automatically
            data = await websocket.receive_json()
            
            # Ensure sender is correct
            data["sender"] = player_id
            
            # Construct payload
            payload = {
                "event": "event",
                "data": {
                    "code": data.get("event"),
                    "data": data,
                    "sender": player_id
                }
            }
            payload_str = json.dumps(payload)
            
            # Broadcast to others
            for ws in list(clients):
                if ws != websocket:
                    try:
                        await ws.send_text(payload_str)
                    except:
                        pass
                            
    except WebSocketDisconnect:
        logging.info(f"Player {player_id} disconnected")
    except Exception as e:
        logging.error(f"Error processing messages for Player {player_id}: {e}")
    finally:
        if websocket in clients:
            clients.remove(websocket)
        if websocket in clients_map:
            del clients_map[websocket]
        
        # Notify others
        leave_msg = json.dumps({
            "event": "actorLeave",
            "data": {"actorNr": player_id}
        })
        for ws in list(clients):
            try:
                await ws.send_text(leave_msg)
            except:
                pass

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8765))
    uvicorn.run(app, host="0.0.0.0", port=port)


