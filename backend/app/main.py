import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.protocol.models import (
    A2UIMessage,
    UpdateDataModelPayload,
    DeleteSurfacePayload,
    ClientMessage
)
from app.agent.gemini_agent import A2UIAgent
from app.agent.project_store import (
    list_saved_apps,
    load_saved_app,
    delete_saved_app,
    export_app_to_dart
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("a2ui.server")

app = FastAPI(
    title="A2UI Multi-Turn App Builder Server",
    description="Conversational Agent-to-UI streaming backend for Flutter App Studio",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = A2UIAgent()

class PromptRequest(BaseModel):
    prompt: str
    sessionId: str = "default_session"

class SaveAppRequest(BaseModel):
    sessionId: str
    name: str

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "protocol": "A2UI v0.9 (Multi-Turn Studio)",
        "gemini_active": agent.client is not None,
        "saved_apps_count": len(list_saved_apps())
    }

@app.get("/api/apps")
def get_apps():
    """Lists all saved apps on disk."""
    return {"apps": list_saved_apps()}

@app.get("/api/apps/{app_id}")
def get_app(app_id: str):
    app_data = load_saved_app(app_id)
    if not app_data:
        raise HTTPException(status_code=404, detail="App not found")
    return app_data

@app.delete("/api/apps/{app_id}")
def remove_app(app_id: str):
    success = delete_saved_app(app_id)
    if not success:
        raise HTTPException(status_code=404, detail="App not found")
    return {"status": "deleted", "id": app_id}

@app.get("/api/apps/{app_id}/export")
def export_app(app_id: str):
    dart_code = export_app_to_dart(app_id)
    if not dart_code:
        raise HTTPException(status_code=404, detail="App not found")
    return {"dart_code": dart_code}

@app.post("/api/prompt")
async def generate_from_prompt(req: PromptRequest):
    messages = await agent.process_user_turn(req.prompt, req.sessionId)
    return [m.model_dump(exclude_none=True) for m in messages]

@app.websocket("/ws/a2ui")
async def a2ui_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = f"client_{id(websocket)}"
    session = agent.get_or_create_session(session_id)
    logger.info(f"Flutter client connected. Allocated session: {session_id}")

    try:
        # Send initial welcome message with saved apps list
        initial_apps = list_saved_apps()
        welcome_msg = A2UIMessage(
            sessionId=session_id,
            assistantMessage="👋 Welcome to A2UI App Studio! Describe an app to build, or load an existing project from the 'Saved Apps' menu."
        )
        await websocket.send_text(welcome_msg.model_dump_json(exclude_none=True))

        # Send saved apps catalogue to client
        await websocket.send_text(json.dumps({
            "type": "saved_apps_list",
            "apps": initial_apps
        }))

        # Main message loop
        while True:
            raw_data = await websocket.receive_text()
            try:
                payload = json.loads(raw_data)
            except Exception:
                continue

            msg_type = payload.get("type", "prompt")
            client_session_id = payload.get("sessionId", session_id)

            # Case 1: Load a saved app from disk
            if msg_type == "load_app":
                app_id = payload.get("appId")
                logger.info(f"Loading saved app '{app_id}' into session {client_session_id}")
                load_messages = agent.load_saved_app_into_session(client_session_id, app_id)
                if load_messages:
                    for msg in load_messages:
                        await websocket.send_text(msg.model_dump_json(exclude_none=True))
                        await asyncio.sleep(0.03)
                continue

            # Case 2: User requested save/rename
            if msg_type == "save_app":
                app_name = payload.get("name", "My App")
                saved = agent.save_app_with_name(client_session_id, app_name)
                # Refresh saved apps for all clients
                await websocket.send_text(json.dumps({
                    "type": "saved_apps_list",
                    "apps": list_saved_apps(),
                    "currentApp": saved
                }))
                continue

            # Case 3: List saved apps
            if msg_type == "list_apps":
                await websocket.send_text(json.dumps({
                    "type": "saved_apps_list",
                    "apps": list_saved_apps()
                }))
                continue

            # Case 4: Reset / New App
            if msg_type == "reset":
                session.reset()
                reset_msg = A2UIMessage(
                    sessionId=client_session_id,
                    assistantMessage="Canvas reset! What would you like to build next?",
                    deleteSurface=DeleteSurfacePayload(surfaceId=session.surface_id)
                )
                await websocket.send_text(reset_msg.model_dump_json(exclude_none=True))
                continue

            # Case 5: Prompt (Build or Modify)
            if "prompt" in payload and payload["prompt"]:
                prompt_text = payload["prompt"]
                logger.info(f"[{session_id}] User prompt: {prompt_text}")
                
                messages = await agent.process_user_turn(prompt_text, client_session_id)
                for msg in messages:
                    await websocket.send_text(msg.model_dump_json(exclude_none=True))
                    await asyncio.sleep(0.04)

                # Broadcast updated saved apps list
                await websocket.send_text(json.dumps({
                    "type": "saved_apps_list",
                    "apps": list_saved_apps()
                }))
                continue

            # Case 6: Direct answer clarification message
            if msg_type == "answer_clarification":
                answers = payload.get("answers", {})
                logger.info(f"[{session_id}] Answering clarification: {answers}")
                messages = await agent.process_clarification_answer(answers, client_session_id)
                for msg in messages:
                    await websocket.send_text(msg.model_dump_json(exclude_none=True))
                    await asyncio.sleep(0.04)

                await websocket.send_text(json.dumps({
                    "type": "saved_apps_list",
                    "apps": list_saved_apps()
                }))
                continue

            # Case 7: Confirm plan & build
            if msg_type == "confirm_build":
                data = payload.get("data", {})
                logger.info(f"[{session_id}] Direct confirm_build with: {data}")
                messages = await agent.process_confirmation(data, client_session_id)
                for msg in messages:
                    await websocket.send_text(msg.model_dump_json(exclude_none=True))
                    await asyncio.sleep(0.04)

                await websocket.send_text(json.dumps({
                    "type": "saved_apps_list",
                    "apps": list_saved_apps()
                }))
                continue

            # Case 8: Action interaction from running app or A2UI form
            elif "userAction" in payload or msg_type == "action":
                action_data = payload.get("userAction", payload)
                action_name = action_data.get("action")
                surface_id = action_data.get("surfaceId", session.surface_id)
                data = action_data.get("data", {})
                logger.info(f"[{session_id}] Action '{action_name}' on surface '{surface_id}' with: {data}")

                # Handle clarification submission from A2UI button
                if action_name == "submit_clarification":
                    logger.info(f"[{session_id}] Processing clarification submission with: {data}")
                    messages = await agent.process_clarification_answer(data, client_session_id)
                    for msg in messages:
                        await websocket.send_text(msg.model_dump_json(exclude_none=True))
                        await asyncio.sleep(0.04)

                    await websocket.send_text(json.dumps({
                        "type": "saved_apps_list",
                        "apps": list_saved_apps()
                    }))
                    continue

                # Handle plan confirmation & build from A2UI button
                if action_name == "confirm_build":
                    logger.info(f"[{session_id}] Processing confirm_build action with: {data}")
                    messages = await agent.process_confirmation(data, client_session_id)
                    for msg in messages:
                        await websocket.send_text(msg.model_dump_json(exclude_none=True))
                        await asyncio.sleep(0.04)

                    await websocket.send_text(json.dumps({
                        "type": "saved_apps_list",
                        "apps": list_saved_apps()
                    }))
                    continue

                # Handle Tic Tac Toe Moves
                if action_name == "play_cell":
                    row = int(data.get("row", 0))
                    col = int(data.get("col", 0))
                    board = session.current_data.get("board", [
                        ["[ - ]", "[ - ]", "[ - ]"],
                        ["[ - ]", "[ - ]", "[ - ]"],
                        ["[ - ]", "[ - ]", "[ - ]"]
                    ])
                    game_state = session.current_data.get("game", {})
                    turn = game_state.get("turn", "X")
                    winner = game_state.get("winner", "")

                    if not winner and board[row][col] == "[ - ]":
                        board[row][col] = f"[ {turn} ]"
                        
                        def check_win(b, p):
                            mark = f"[ {p} ]"
                            for r in range(3):
                                if b[r][0] == b[r][1] == b[r][2] == mark:
                                    return True
                            for c in range(3):
                                if b[0][c] == b[1][c] == b[2][c] == mark:
                                    return True
                            if b[0][0] == b[1][1] == b[2][2] == mark:
                                return True
                            if b[0][2] == b[1][1] == b[2][0] == mark:
                                return True
                            return False

                        if check_win(board, turn):
                            game_state["status"] = f"🎉 Player {turn} Wins!"
                            game_state["winner"] = turn
                        elif all(board[r][c] != "[ - ]" for r in range(3) for c in range(3)):
                            game_state["status"] = "🤝 It's a Draw!"
                        else:
                            next_turn = "O" if turn == "X" else "X"
                            game_state["turn"] = next_turn
                            game_state["status"] = f"Player {next_turn}'s Turn"

                        session.current_data["board"] = board
                        session.current_data["game"] = game_state
                        agent.save_app_with_name(client_session_id, session.app_name)

                        await websocket.send_text(A2UIMessage(
                            sessionId=client_session_id,
                            updateDataModel=UpdateDataModelPayload(
                                surfaceId=surface_id,
                                path="/",
                                value=session.current_data
                            )
                        ).model_dump_json(exclude_none=True))
                        continue

                elif action_name == "reset_game":
                    session.current_data["board"] = [
                        ["[ - ]", "[ - ]", "[ - ]"],
                        ["[ - ]", "[ - ]", "[ - ]"],
                        ["[ - ]", "[ - ]", "[ - ]"]
                    ]
                    session.current_data["game"] = {
                        "status": "Player X's Turn",
                        "turn": "X",
                        "winner": ""
                    }
                    agent.save_app_with_name(client_session_id, session.app_name)
                    await websocket.send_text(A2UIMessage(
                        sessionId=client_session_id,
                        updateDataModel=UpdateDataModelPayload(
                            surfaceId=surface_id,
                            path="/",
                            value=session.current_data
                        )
                    ).model_dump_json(exclude_none=True))
                    continue

                if isinstance(data, dict):
                    session.current_data.update(data)
                    agent.save_app_with_name(client_session_id, session.app_name)

                feedback_msg = A2UIMessage(
                    sessionId=client_session_id,
                    updateDataModel=UpdateDataModelPayload(
                        surfaceId=surface_id,
                        path="/status",
                        value=f"Action '{action_name}' executed at {asyncio.get_event_loop().time():.1f}s"
                    )
                )
                await websocket.send_text(feedback_msg.model_dump_json(exclude_none=True))

    except WebSocketDisconnect:
        logger.info(f"Flutter client {session_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error in {session_id}: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
