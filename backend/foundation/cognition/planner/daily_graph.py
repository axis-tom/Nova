GRAPH = {
    "start": "email",
    "nodes": {
        "email": {
            "agent": "email_agent",
            "next": "ai_analyzer"
        },
        "ai_analyzer": {
            "agent": "ai_analyzer",
            "next": "briefing"
        },
        "briefing": {
            "agent": "briefing_agent",
            "next": None
        }
    }
}
