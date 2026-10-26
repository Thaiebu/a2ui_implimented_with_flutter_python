from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator

class CreateSurfacePayload(BaseModel):
    surfaceId: str
    catalogId: str = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"

class ComponentChildren(BaseModel):
    explicitList: List[str] = Field(default_factory=list)

class DynamicValue(BaseModel):
    literalString: Optional[str] = None
    path: Optional[str] = None

class ActionDefinition(BaseModel):
    name: str
    contextPath: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

class PickerOption(BaseModel):
    label: str
    value: Any

class ComponentDefinition(BaseModel):
    id: str
    component: str  # Column, Row, Card, Text, Button, TextField, ChoicePicker, Slider, Divider, Icon, Image
    children: Optional[ComponentChildren] = None

    @field_validator("children", mode="before")
    @classmethod
    def normalize_children(cls, v):
        if isinstance(v, list):
            return ComponentChildren(explicitList=[str(x) for x in v])
        if isinstance(v, dict) and "explicitList" in v:
            return ComponentChildren(**v)
        return v

    @field_validator("text", "label", "value", mode="before")
    @classmethod
    def normalize_dynamic_value(cls, v):
        if isinstance(v, str):
            if v.startswith("/"):
                return {"path": v}
            return {"literalString": v}
        return v

    @field_validator("options", mode="before")
    @classmethod
    def normalize_options(cls, v):
        if isinstance(v, list):
            res = []
            for item in v:
                if isinstance(item, str):
                    res.append({"label": item, "value": item.lower().replace(" ", "_")})
                elif isinstance(item, dict):
                    res.append(item)
            return res
        return v

    @field_validator("action", mode="before")
    @classmethod
    def normalize_action(cls, v):
        if isinstance(v, str):
            return {"name": v, "contextPath": "/"}
        return v

    text: Optional[Dict[str, Any]] = None
    label: Optional[Dict[str, Any]] = None
    value: Optional[Dict[str, Any]] = None
    usageHint: Optional[str] = None  # h1, h2, body, caption
    action: Optional[ActionDefinition] = None
    options: Optional[List[PickerOption]] = None
    min: Optional[float] = None
    max: Optional[float] = None
    placeholder: Optional[str] = None
    iconName: Optional[str] = None
    imageUrl: Optional[str] = None

class UpdateComponentsPayload(BaseModel):
    surfaceId: str
    components: List[ComponentDefinition]

class UpdateDataModelPayload(BaseModel):
    surfaceId: str
    path: str = "/"
    value: Any

class DeleteSurfacePayload(BaseModel):
    surfaceId: str

class A2UIMessage(BaseModel):
    version: str = "v0.9"
    sessionId: Optional[str] = None
    phase: Optional[str] = None  # "idle", "clarifying", "building"
    assistantMessage: Optional[str] = None
    createSurface: Optional[CreateSurfacePayload] = None
    updateComponents: Optional[UpdateComponentsPayload] = None
    updateDataModel: Optional[UpdateDataModelPayload] = None
    deleteSurface: Optional[DeleteSurfacePayload] = None

class UserActionPayload(BaseModel):
    surfaceId: str
    action: str
    timestamp: Optional[int] = None
    data: Optional[Dict[str, Any]] = None

class ClientMessage(BaseModel):
    version: Optional[str] = "v0.9"
    sessionId: Optional[str] = None
    type: Optional[str] = None  # "prompt", "action", "reset"
    prompt: Optional[str] = None
    userAction: Optional[UserActionPayload] = None
