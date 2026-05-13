# backend/models/message.py（扩展）
class MessageSend(BaseModel):
    conversation_id: int
    content: str
    scene_id: str
    function_id: str
    model_id: str

class MessageResponse(BaseModel):
    reply: str


# backend/api/v1/conversation.py（扩展）
@router.post("/message", response_model=MessageResponse)
async def send_message_with_context(data: MessageSend, user_id: int = 1):
    """发送消息（带场景、功能、模型参数）"""
    # 1. 保存用户消息（包含场景、功能信息）
    # 2. 调用智能体群生成回复
    # 3. 保存助手回复
    # 4. 更新对话的默认场景和模型
    
    # 模拟实现
    reply = f"收到消息「{data.content}」，场景：{data.scene_id}，功能：{data.function_id}，模型：{data.model_id}"
    
    # 更新对话的默认场景和模型
    conv_repo = ConversationRepository()
    await conv_repo.update(
        data.conversation_id, user_id,
        ConversationUpdate(scene_id=data.scene_id, model_id=data.model_id)
    )
    
    return MessageResponse(reply=reply)


@router.get("/{conv_id}/messages")
async def get_conversation_messages_with_context(conv_id: int, user_id: int = 1):
    """获取对话消息（带场景和模型信息）"""
    # 获取对话信息
    conv_repo = ConversationRepository()
    conv = await conv_repo.get(conv_id, user_id)
    
    # 获取消息列表
    msg_repo = MessageRepository()
    messages = await msg_repo.list_by_conversation(conv_id, user_id)
    
    return {
        "messages": messages,
        "scene": conv.scene_id if conv else None,
        "modelId": conv.model_id if conv else None
    }