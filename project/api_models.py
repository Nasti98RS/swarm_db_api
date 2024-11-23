from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class ToolCall(BaseModel):
    id: str
    type: str
    function: Dict[str, Any]


class Message(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    sender: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    context: Dict[str, Any]
    stream: bool = False


class ChatResponse(BaseModel):
    sender: str = "assistant"
    content: str
    agent_switch: Optional[str] = None
    # tool_calls: Optional[List[ToolCall]] = None
