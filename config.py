# ── JARVIS Configuration ─────────────────────────────────────────

# AI Model — best for your 4GB VRAM
MODEL = "llama3.2:3b"

# Wake words — say any of these to activate JARVIS
WAKE_WORDS = ["hey jarvis", "jarvis", "hi jarvis", "okay jarvis"]

# How many conversation exchanges to remember (keeps responses fast)
MEMORY_LIMIT = 10

# Voice settings
SPEECH_RATE = 160        # Words per minute (150-180 is natural)
SPEECH_VOLUME = 0.95     # 0.0 to 1.0

# Mic settings
MIC_ENERGY_THRESHOLD = 300    # Higher = less sensitive to background noise
MIC_PAUSE_THRESHOLD = 1.0     # Seconds of silence before stopping listening
MIC_LISTEN_TIMEOUT = 8        # Max seconds to wait for you to start speaking
MIC_PHRASE_LIMIT = 15         # Max seconds for a single phrase

# JARVIS personality prompt
SYSTEM_PROMPT = """You are JARVIS — Just A Rather Very Intelligent System.
You are the AI assistant of the user, modeled after Iron Man's JARVIS.
You are highly intelligent, calm, witty, and efficient.
Keep all responses short and conversational — 1 to 3 sentences unless the user asks for detail.
Occasionally address the user as 'sir'. Never mention you are an AI, Ollama, or a language model.
You have a dry sense of humor and speak with precision and confidence. user is Thisaru Sachintha."""