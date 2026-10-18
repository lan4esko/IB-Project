# Planning catalog only. "staged" does not mean the model has been downloaded.
# Model artifact sizes vary with tags/quantization and may change upstream.
MODEL_CATALOG = [
    {"tag": "qwen3:0.6b", "role": "chat", "tier": "dev", "note": "Текущий стенд; проверка API"},
    {"tag": "qwen3-embedding:0.6b", "role": "embedding", "tier": "dev", "note": "Тестовый RAG"},
    {"tag": "qwen3:4b", "role": "chat", "tier": "intermediate", "note": "Требует проверки свободной RAM"},
    {"tag": "qwen3.5:9b", "role": "chat-multimodal", "tier": "closed", "note": "Целевая мультимодальная модель"},
    {"tag": "qwen3:14b", "role": "chat", "tier": "closed", "note": "Альтернатива для текста"},
    {"tag": "gpt-oss:20b", "role": "reasoning", "tier": "closed", "note": "Рассуждения, проверка качества"},
    {"tag": "qwen3.5:27b", "role": "chat-multimodal", "tier": "closed", "note": "Тяжёлая модель для закрытого контура"},
    {"tag": "qwen3:32b", "role": "chat", "tier": "closed", "note": "Тяжёлая текстовая модель"},
    {"tag": "qwen3-embedding:4b", "role": "embedding", "tier": "closed", "note": "Качественный поиск"},
]
