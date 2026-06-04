from pydantic import BaseModel


class MessageSend(BaseModel):
    conversation_id: int
    content: str
    scene_id: str
    function_id: str
    model_id: str


class MessageResponse(BaseModel):
    reply: str