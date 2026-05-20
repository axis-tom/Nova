import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getConversations,
  getConversationMessages,
  deleteConversation as apiDeleteConversation,
  renameConversation as apiRenameConversation,
  type ConversationItem,
  type Message,
} from '@/api/agentChat'

export const useAgentChatStore = defineStore('agentChat', () => {
  const conversations = ref<ConversationItem[]>([])
  const currentConversationId = ref<string | null>(null)
  const messages = ref<Message[]>([])
  const loading = ref(false)

  const currentConversation = computed(() =>
    conversations.value.find(c => c.id === currentConversationId.value) || null
  )

  async function loadConversations() {
    try {
      conversations.value = await getConversations()
    } catch (e) {
      console.error('[AgentChatStore] Failed to load conversations', e)
    }
  }

  async function selectConversation(convId: string) {
    currentConversationId.value = convId
    loading.value = true
    try {
      const data = await getConversationMessages(convId)
      messages.value = data.messages.map((m, i) => ({
        id: String(m.id),
        role: m.role as Message['role'],
        content: m.content,
        createdAt: m.created_at,
      }))
    } catch (e) {
      console.error('[AgentChatStore] Failed to load messages', e)
      messages.value = []
    } finally {
      loading.value = false
    }
  }

  function newConversation() {
    currentConversationId.value = null
    messages.value = []
  }

  function setCurrentConversationId(id: string) {
    currentConversationId.value = id
  }

  function addMessage(msg: Message) {
    messages.value.push(msg)
  }

  function updateLastAssistantMessage(content: string) {
    const last = [...messages.value].reverse().find(m => m.role === 'assistant')
    if (last) {
      last.content = content
    }
  }

  async function removeConversation(convId: string) {
    try {
      await apiDeleteConversation(convId)
      conversations.value = conversations.value.filter(c => c.id !== convId)
      if (currentConversationId.value === convId) {
        newConversation()
      }
    } catch (e) {
      console.error('[AgentChatStore] Failed to delete conversation', e)
    }
  }

  async function renameConversation(convId: string, title: string) {
    try {
      await apiRenameConversation(convId, title)
      const conv = conversations.value.find(c => c.id === convId)
      if (conv) conv.title = title
    } catch (e) {
      console.error('[AgentChatStore] Failed to rename conversation', e)
    }
  }

  return {
    conversations,
    currentConversationId,
    currentConversation,
    messages,
    loading,
    loadConversations,
    selectConversation,
    newConversation,
    setCurrentConversationId,
    addMessage,
    updateLastAssistantMessage,
    removeConversation,
    renameConversation,
  }
})
