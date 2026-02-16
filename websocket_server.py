import asyncio
import websockets
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

clients = set()
clients_map = {} # WebSocket -> PlayerID
next_player_id = 1

async def process_request(path, request_headers):
    """Handle HTTP HEAD requests from health checks"""
    if request_headers.get("Upgrade", "").lower() != "websocket":
        # Return 200 OK for health checks (HEAD, GET without upgrade, etc.)
        return (200, [], b"OK\n")

async def handler(websocket):
    global next_player_id
    player_id = next_player_id
    next_player_id += 1
    clients.add(websocket)
    clients_map[websocket] = player_id
    
    logging.info(f"Player {player_id} connected")
    
    try:
        # Send initial Join Success (as if from Photon)
        # Emulate: window.godotPhotonEvent('join', {success: 1, actorNr: actorNr});
        await websocket.send(json.dumps({
            "event": "join",
            "data": {"success": 1, "actorNr": player_id}
        }))
        
        # Notify others about new player
        # Emulate: window.godotPhotonEvent('actorJoin', {actorNr: actor.actorNr});
        join_msg = json.dumps({
            "event": "actorJoin",
            "data": {"actorNr": player_id}
        })
        for ws in clients:
            if ws != websocket:
                await ws.send(join_msg)
                
        # Notify new player about existing players
        for ws, pid in clients_map.items():
            if ws != websocket:
                await websocket.send(json.dumps({
                    "event": "actorJoin",
                    "data": {"actorNr": pid}
                }))

        async for message in websocket:
            try:
                data = json.loads(message)
                # Ensure sender is correct
                data["sender"] = player_id
                
                # The client sends raw data like {"event": 2, "pos": ...}
                # PhotonManager expects "event" type message with code and data.
                # Construct payload:
                # { "event": "event", "data": { "code": data["event"], "data": data, "sender": player_id } }
                
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
                for ws in clients:
                    if ws != websocket:
                        await ws.send(payload_str)
                        
            except json.JSONDecodeError:
                logging.error("Invalid JSON received")
                
    except websockets.ConnectionClosed:
        logging.info(f"Player {player_id} disconnected")
    finally:
        clients.remove(websocket)
        del clients_map[websocket]
        
        # Notify others
        leave_msg = json.dumps({
            "event": "actorLeave",
            "data": {"actorNr": player_id}
        })
        for ws in clients:
            await ws.send(leave_msg)

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765, process_request=process_request):
        logging.info("WebSocket Server started on port 8765")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

