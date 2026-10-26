# Python Backend Implementation Guide for A2UI

This guide explains how to build a Python-based AI Agent server that speaks the **A2UI protocol** and streams interfaces to Flutter clients.

---

## 1. Architecture Overview

The backend consists of:
1. **FastAPI Application** hosting a WebSocket endpoint `/ws/a2ui`.
2. **Gemini AI Agent Engine** using `google-genai` SDK with Structured Output / JSON schema matching the A2UI Catalog.
3. **Session & Surface Manager** tracking active surfaces, data models, and pending actions per client connection.
4. **Tool Execution Engine** enabling the agent to execute real Python functions (e.g. searching hotels, booking tables) and stream results as UI updates.

---

## 2. Dependencies (`requirements.txt`)

```txt
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
google-genai>=0.1.0
pydantic>=2.9.0
websockets>=13.0
python-dotenv>=1.0.0
```

---

## 3. A2UI Protocol Models (`protocol/models.py`)

```python
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

class CreateSurfacePayload(BaseModel):
    surfaceId: str
    catalogId: str = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"

class ComponentChildren(BaseModel):
    explicitList: List[str]

class ComponentDefinition(BaseModel):
    id: str
    component: str  # e.g., "Column", "Text", "Button", "Card"
    children: Optional[ComponentChildren] = None
    text: Optional[Dict[str, Any]] = None
    usageHint: Optional[str] = None
    action: Optional[Dict[str, Any]] = None
    options: Optional[List[Dict[str, Any]]] = None
    value: Optional[Dict[str, Any]] = None

class UpdateComponentsPayload(BaseModel):
    surfaceId: str
    components: List[ComponentDefinition]

class UpdateDataModelPayload(BaseModel):
    surfaceId: str
    path: str = "/"
    value: Any

class A2UIMessage(BaseModel):
    version: str = "v0.9"
    createSurface: Optional[CreateSurfacePayload] = None
    updateComponents: Optional[UpdateComponentsPayload] = None
    updateDataModel: Optional[UpdateDataModelPayload] = None

class UserActionPayload(BaseModel):
    surfaceId: str
    action: str
    timestamp: Optional[int] = None
    data: Optional[Dict[str, Any]] = None

class ClientMessage(BaseModel):
    version: Optional[str] = "v0.9"
    userAction: Optional[UserActionPayload] = None
    query: Optional[str] = None
```

---

## 4. FastAPI WebSocket Server (`main.py`)

```python
import asyncio
import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from protocol.models import A2UIMessage, CreateSurfacePayload, UpdateComponentsPayload, UpdateDataModelPayload, ComponentDefinition, ComponentChildren

app = FastAPI(title="A2UI Agent Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/a2ui")
async def a2ui_endpoint(websocket: WebSocket):
    await websocket.accept()
    surface_id = "main_surface"

    try:
        # Step 1: Send createSurface message
        create_msg = A2UIMessage(
            createSurface=CreateSurfacePayload(surfaceId=surface_id)
        )
        await websocket.send_text(create_msg.model_dump_json(exclude_none=True))

        # Step 2: Stream mock or LLM generated UI components
        comp_msg = A2UIMessage(
            updateComponents=UpdateComponentsPayload(
                surfaceId=surface_id,
                components=[
                    ComponentDefinition(
                        id="root_col",
                        component="Column",
                        children=ComponentChildren(explicitList=["header_text", "status_card", "book_button"])
                    ),
                    ComponentDefinition(
                        id="header_text",
                        component="Text",
                        text={"path": "/app/title"},
                        usageHint="h1"
                    ),
                    ComponentDefinition(
                        id="status_card",
                        component="Text",
                        text={"path": "/app/status"},
                        usageHint="body"
                    ),
                    ComponentDefinition(
                        id="book_button",
                        component="Button",
                        text={"literalString": "Tap to Book"},
                        action={"name": "trigger_booking", "contextPath": "/app"}
                    )
                ]
            )
        )
        await websocket.send_text(comp_msg.model_dump_json(exclude_none=True))

        # Step 3: Stream initial data model
        data_msg = A2UIMessage(
            updateDataModel=UpdateDataModelPayload(
                surfaceId=surface_id,
                path="/",
                value={
                    "app": {
                        "title": "Welcome to A2UI on Flutter",
                        "status": "Ready for your prompt"
                    }
                }
            )
        )
        await websocket.send_text(data_msg.model_dump_json(exclude_none=True))

        # Listen for client interactions
        while True:
            raw_text = await websocket.receive_text()
            data = json.loads(raw_text)
            
            if "userAction" in data:
                action = data["userAction"]
                action_name = action.get("action")
                
                # Handle interactive response
                if action_name == "trigger_booking":
                    # Update state dynamically
                    update_msg = A2UIMessage(
                        updateDataModel=UpdateDataModelPayload(
                            surfaceId=surface_id,
                            path="/app",
                            value={
                                "title": "Welcome to A2UI on Flutter",
                                "status": "Booking Confirmed! 🎉"
                            }
                        )
                    )
                    await websocket.send_text(update_msg.model_dump_json(exclude_none=True))

    except WebSocketDisconnect:
        print("Client disconnected")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

---

## 5. Gemini 2.0 / 1.5 System Prompt for A2UI

To have Google Gemini output A2UI compliant JSON:

```python
A2UI_SYSTEM_PROMPT = """
You are an AI Agent speaking the A2UI (Agent-to-User Interface) protocol.
Whenever the user makes a request that requires a visual interface, you must output a valid sequence of A2UI JSON messages in JSON Lines format:
1. createSurface: Initialize the surface ID.
2. updateComponents: Output an adjacency list of flat components (Column, Row, Text, Button, TextField, ChoicePicker, Card). Components must reference children by IDs.
3. updateDataModel: Output the initial data payload bound via JSON pointer paths.

Strict Rules:
- NEVER output raw HTML or executable Javascript.
- Use explicit IDs for all components.
- Bind variable values using {"path": "/pointer/path"}.
- Use {"literalString": "..."} only for static labels.
"""
```
