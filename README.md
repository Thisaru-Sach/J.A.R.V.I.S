# J.A.R.V.I.S — Just A Rather Very Intelligent System


A fully local AI assistant that runs entirely on your machine — no cloud, no subscriptions, no sending your conversations to anyone. Just you, your GPU, and your own personal JARVIS.

Built with Python, powered by Ollama, and voiced by a community-trained neural model that actually sounds like the guy from the movies.

---

## What it does

You talk. JARVIS listens, thinks, and talks back. It's that simple.

- Wakes up when you say *"Hey JARVIS"*
- Goes quiet when you say *"That's it JARVIS"* or *"Thank you JARVIS"*
- Shuts down cleanly when you say *"Power off"* or *"Goodbye JARVIS"*
- Tells you the date and time instantly
- Reports your CPU, RAM, and disk usage on demand
- Remembers your last 10 conversations across sessions
- Runs 100% offline after setup — no internet needed during use

---

## The voice

This project uses a community-trained neural voice model by [jgkawell](https://huggingface.co/jgkawell/jarvis) that mimics the JARVIS voice from the Iron Man films. It's run locally through the [Piper TTS](https://github.com/rhasspy/piper) engine — not a cloud API, not pyttsx3 robot voice. The actual JARVIS sound.

---

## What you need

- Windows 11
- Python 3.11 (for some packages later versions are not supporting yet)
- [Ollama](https://ollama.com) installed
- An NVIDIA GPU with at least 2GB VRAM 
- A microphone
- Internet only for the first-time setup and voice recognition

The whole thing was built and tested on an i5 laptop with 16GB RAM and an RTX 2050 (4GB VRAM). It runs smoothly.

---

## Setup

**1. Install Ollama and pull the model**

Download Ollama from [ollama.com](https://ollama.com), install it, then open a terminal and run:

```
ollama pull llama3.2:3b
```

This downloads about 2GB and only happens once.

**2. Download the Piper voice engine**

Download `piper_windows_amd64.zip` from the [Piper releases page](https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip), extract it, and place the folder at `C:\JARVIS\piper\`.

**3. Download the JARVIS voice model**

Download these two files from [jgkawell/jarvis on Hugging Face](https://huggingface.co/jgkawell/jarvis/tree/main/en/en_GB/jarvis/medium) and place them in `C:\JARVIS\voice\`:

- `jarvis-medium.onnx`
- `jarvis-medium.onnx.json`

**4. Set up the Python environment**

```
cd C:\JARVIS
py -3.11 -m venv venv
venv\Scripts\activate
pip install SpeechRecognition pyttsx3 ollama pyaudio psutil
```

If PyAudio gives trouble, try `pip install PyAudio==0.2.14` directly.

**5. Run it**

```
python jarvis.py
```

Or just double-click `start_jarvis.bat`.

---

## Project structure

```
C:\JARVIS\
|- jarvis.py          — the main script
|- config.py          — all settings in one place
|- memory.json        — conversation memory (auto-created)
|- start_jarvis.bat   — double-click launcher
|- piper\             — Piper TTS engine (piper.exe + dlls)
|- voice\             — JARVIS voice model files
```
|
---

## Voice commands

| Say this | What happens |
|---|---|
| `Hey JARVIS` | Wakes up from standby |
| `That's it JARVIS` | Goes back to standby |
| `Thank you JARVIS` | Goes back to standby |
| `What time is it?` | Tells the current time instantly |
| `What day is it?` | Tells today's date |
| `System specs` | Reports CPU, RAM, disk usage |
| `How much RAM?` | Same as above |
| `Clear memory` | Wipes conversation history |
| `Shut down` / `Power off` | Exits the program |
| `Goodbye JARVIS` | Exits the program |

---

## Changing the AI model

Open `config.py` and change the `MODEL` line. These all work well depending on your GPU:

| Model | VRAM needed | Feel |
|---|---|---|
| `llama3.2:3b` | ~2 GB | Fast, conversational — default |
| `phi4-mini` | ~2.5 GB | Smarter reasoning |
| `mistral:7b` | ~4.1 GB | Best quality, needs 6GB+ VRAM |

---

## How memory works

JARVIS saves your last 10 conversation exchanges to `memory.json` when it shuts down. Next time you start it, it picks up where it left off. If you want to wipe it, just say *"Clear memory"* or delete the file.

It doesn't train on your conversations. It just reads them each time like context — same way you'd catch someone up on a conversation by showing them the chat history.

---

## Known limitations

- Voice recognition requires an internet connection (uses Google's STT API). For fully offline recognition you'd need to swap in something like Whisper.
- The Piper voice takes about 1-2 seconds to generate audio per response. That's normal — it's a neural model running locally.
- Works on Windows only right now.

---

## Credits

- [Ollama](https://ollama.com) — local LLM server
- [Piper TTS](https://github.com/rhasspy/piper) — neural text-to-speech engine
- [jgkawell/jarvis](https://huggingface.co/jgkawell/jarvis) — the community-trained JARVIS voice model
- [Meta LLaMA 3.2](https://ollama.com/library/llama3.2) — the brain

---

*For personal and educational use only. The JARVIS voice model is not licensed for commercial use.*