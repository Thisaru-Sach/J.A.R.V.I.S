import os
import sys
import json
import wave
import platform
import datetime
import psutil
import pyaudio
import subprocess
import tempfile
import time
import numpy as np
import pyttsx3
import whisper
import sounddevice as sd
import ollama
from config import (
    MODEL, WAKE_WORDS, MEMORY_LIMIT, SPEECH_RATE, SPEECH_VOLUME,
    MIC_ENERGY_THRESHOLD, MIC_PAUSE_THRESHOLD, MIC_LISTEN_TIMEOUT,
    MIC_PHRASE_LIMIT, SYSTEM_PROMPT
)

MEMORY_FILE  = "memory.json"
PIPER_EXE    = r"C:\JARVIS\piper\piper.exe"
VOICE_MODEL  = r"C:\JARVIS\voice\jarvis-medium.onnx"
VOICE_CONFIG = r"C:\JARVIS\voice\jarvis-medium.onnx.json"

USE_PIPER = os.path.exists(PIPER_EXE) and os.path.exists(VOICE_MODEL)

# ── Load Whisper STT Model (runs locally, no internet) ────────────
print("\n  Loading Whisper speech recognition model...")
print("  (first run downloads ~140MB — after that it's fully offline)\n")
stt_model = whisper.load_model("base.en")   # base.en = fast + English-only
print("  Whisper loaded.\n")

pa = pyaudio.PyAudio()

SAMPLE_RATE    = 16000   # Whisper expects 16kHz
CHANNELS       = 1
DTYPE          = "float32"

# ── Speak ─────────────────────────────────────────────────────────
def speak(text):
    print(f"\n  [JARVIS] {text}\n")

    if USE_PIPER:
        tmp_path = None
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_path = tmp.name
            tmp.close()

            result = subprocess.run(
                [
                    PIPER_EXE,
                    "--model",            VOICE_MODEL,
                    "--config",           VOICE_CONFIG,
                    "--output_file",      tmp_path,
                    "--sentence_silence", "0.2"
                ],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30
            )

            if result.returncode != 0:
                raise RuntimeError(result.stderr.decode())

            with wave.open(tmp_path, "rb") as wf:
                stream = pa.open(
                    format=pa.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True
                )
                chunk = wf.readframes(4096)
                while chunk:
                    stream.write(chunk)
                    chunk = wf.readframes(4096)
                stream.stop_stream()
                stream.close()

            os.unlink(tmp_path)
            return

        except Exception as e:
            print(f"  [Piper error: {e}] — falling back to pyttsx3")
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except:
                    pass

    # pyttsx3 fallback
    engine = pyttsx3.init()
    for v in engine.getProperty("voices"):
        if "david" in v.name.lower():
            engine.setProperty("voice", v.id)
            break
    engine.setProperty("rate", SPEECH_RATE)
    engine.setProperty("volume", SPEECH_VOLUME)
    engine.say(text)
    engine.runAndWait()

# ── Record Audio from Mic ─────────────────────────────────────────
def record_audio(duration=None, silence_timeout=None):
    """
    Record from microphone until:
    - silence_timeout seconds of silence detected (voice-activated stop), OR
    - duration seconds elapsed (fixed-length recording)

    Returns numpy float32 array at 16kHz, or None if nothing was heard.
    """
    CHUNK          = 1024
    SILENCE_THRESH = 0.01     # RMS below this = silence
    MIN_SPEECH_SEC = 0.4      # ignore recordings shorter than this
    max_silence    = silence_timeout or MIC_PAUSE_THRESHOLD
    max_duration   = duration or MIC_LISTEN_TIMEOUT

    frames      = []
    silent_time = 0.0
    total_time  = 0.0
    speech_detected = False
    chunk_duration  = CHUNK / SAMPLE_RATE

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        blocksize=CHUNK
    )

    with stream:
        while total_time < max_duration:
            chunk_data, _ = stream.read(CHUNK)
            rms = float(np.sqrt(np.mean(chunk_data ** 2)))

            if rms > SILENCE_THRESH:
                speech_detected = True
                silent_time = 0.0
                frames.append(chunk_data.copy())
            else:
                if speech_detected:
                    silent_time += chunk_duration
                    frames.append(chunk_data.copy())
                    if silent_time >= max_silence:
                        break  # natural end of speech
                # If no speech heard yet, just wait (don't add silence frames)

            total_time += chunk_duration

    if not speech_detected or len(frames) == 0:
        return None

    audio = np.concatenate(frames, axis=0).flatten()

    # Filter out very short recordings (mic noise, accidental sounds)
    if len(audio) / SAMPLE_RATE < MIN_SPEECH_SEC:
        return None

    return audio

# ── Listen (record + transcribe with Whisper) ─────────────────────
def listen(short=False):
    """
    Capture voice and transcribe offline with Whisper.
    short=True uses tighter silence threshold for standby polling.
    Returns lowercase text string or None.
    """
    silence_timeout = 1.2 if short else MIC_PAUSE_THRESHOLD
    duration        = 5   if short else MIC_LISTEN_TIMEOUT

    print("  [Listening...]", end="", flush=True)

    audio = record_audio(duration=duration, silence_timeout=silence_timeout)

    if audio is None:
        print(" (silence)")
        return None

    print(" Transcribing...", end="", flush=True)

    try:
        result = stt_model.transcribe(
            audio,
            language="en",
            fp16=False,         # set True if you want GPU speed (requires CUDA)
            condition_on_previous_text=False
        )
        text = result["text"].strip().lower()

        if not text or len(text) < 2:
            print(" (empty)")
            return None

        print(f"\n  [You] {text}")
        return text

    except Exception as e:
        print(f"\n  [Whisper error: {e}]")
        return None

# ── Memory ────────────────────────────────────────────────────────
def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, "r") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("Bad format")
        cleaned = [
            m for m in data
            if isinstance(m, dict)
            and m.get("role") in ("user", "assistant")
            and isinstance(m.get("content"), str)
            and m["content"].strip()
        ]
        return cleaned
    except Exception as e:
        print(f"  [Memory] Could not load ({e}). Starting fresh.")
        try:
            os.rename(MEMORY_FILE, MEMORY_FILE + ".corrupt")
        except:
            pass
        return []

def save_memory(history):
    with open(MEMORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def trim_memory(history):
    cleaned = []
    for msg in history:
        if msg["role"] == "assistant" and len(msg["content"]) > 1200:
            msg = {"role": "assistant", "content": msg["content"][:1200] + "..."}
        cleaned.append(msg)
    max_messages = MEMORY_LIMIT * 2
    return cleaned[-max_messages:] if len(cleaned) > max_messages else cleaned

# ── Built-in Commands ─────────────────────────────────────────────
def get_date_response():
    now  = datetime.datetime.now()
    return (
        f"Today is {now.strftime('%A')}, {now.strftime('%B %d, %Y')}. "
        f"The current time is {now.strftime('%I:%M %p')}, sir."
    )

def get_specs_response():
    cpu_cores   = psutil.cpu_count(logical=False)
    cpu_threads = psutil.cpu_count(logical=True)
    cpu_freq    = psutil.cpu_freq()
    freq_str    = f"{cpu_freq.current:.0f} MHz" if cpu_freq else "unknown frequency"
    ram         = psutil.virtual_memory()
    disk        = psutil.disk_usage("C:\\")
    return (
        f"Current system status, sir. "
        f"Operating system: {platform.system()} {platform.release()}. "
        f"Processor: {cpu_cores} cores and {cpu_threads} threads at {freq_str}. "
        f"Memory: {ram.used/(1024**3):.1f} GB used of {ram.total/(1024**3):.1f} GB total, "
        f"at {ram.percent:.0f} percent capacity. "
        f"Storage drive C: {disk.free/(1024**3):.0f} GB free of {disk.total/(1024**3):.0f} GB total."
    )

# ── Command Matchers ──────────────────────────────────────────────
def is_date_command(text):
    return any(k in text for k in [
        "what day", "what's today", "whats today", "today's date",
        "todays date", "what date", "current date", "what time",
        "current time", "what is the date", "what is the time",
        "what's the time", "whats the time", "tell me the time",
        "tell me the date"
    ])

def is_specs_command(text):
    return any(k in text for k in [
        "system specs", "machine specs", "computer specs",
        "system status", "how much ram", "memory usage",
        "cpu info", "cpu usage", "disk space", "storage space",
        "system info", "system information", "hardware info",
        "check my system", "check system"
    ])

def has_wake_word(text):
    return text and any(wake in text for wake in WAKE_WORDS)

def is_standby_command(text):
    return any(p in text for p in [
        "that's it jarvis", "thats it jarvis",
        "that's all jarvis", "thats all jarvis",
        "that is all jarvis", "that is it jarvis",
        "stand by", "standby",
        "go to sleep", "sleep mode",
        "thank you jarvis", "thanks jarvis",
        "that will be all", "that'll be all",
        "rest jarvis", "go standby",
        "enough jarvis", "stop listening",
        "take a break", "quiet jarvis"
    ])

def is_exit_command(text):
    return any(p in text for p in [
        "shut down jarvis", "shutdown jarvis",
        "jarvis shut down", "jarvis shutdown",
        "power off jarvis", "jarvis power off",
        "turn off jarvis", "jarvis turn off",
        "goodbye jarvis", "bye jarvis",
        "exit jarvis", "jarvis exit",
        "close jarvis", "jarvis close",
        "terminate jarvis", "jarvis terminate",
        "jarvis power down", "power down jarvis",
        "stop jarvis", "jarvis stop"
    ])

def is_clear_command(text):
    return any(p in text for p in [
        "clear memory", "forget everything",
        "reset memory", "wipe memory"
    ])

# ── AI Brain ──────────────────────────────────────────────────────
conversation_history = load_memory()

def ask_jarvis(user_input):
    global conversation_history
    conversation_history.append({"role": "user", "content": user_input})
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history

    try:
        print("  [Thinking...]", end="", flush=True)
        response = ollama.chat(model=MODEL, messages=messages)
        reply = response["message"]["content"].strip()
        print(" Done.")
        conversation_history.append({"role": "assistant", "content": reply})
        conversation_history = trim_memory(conversation_history)
        save_memory(conversation_history)
        return reply
    except Exception as e:
        print(f"\n  [ERROR] {e}")
        if conversation_history and conversation_history[-1]["role"] == "user":
            conversation_history.pop()
        return "My core systems encountered an issue. Please ensure Ollama is running."

# ── Shutdown ──────────────────────────────────────────────────────
def shutdown():
    save_memory(conversation_history)
    speak("Understood. Shutting down. Goodbye, sir.")
    try:
        pa.terminate()
    except:
        pass
    os._exit(0)

# ── Banner ────────────────────────────────────────────────────────
def print_banner():
    voice_label = "jgkawell/jarvis (Piper)" if USE_PIPER else "pyttsx3 (fallback — Piper not found)"
    print("\n" + "="*56)
    print("   J.A.R.V.I.S  —  Local AI Assistant")
    print(f"   Model  : {MODEL}")
    print(f"   Voice  : {voice_label}")
    print(f"   STT    : Whisper base.en  (100% offline)")
    print(f"   Memory : last {MEMORY_LIMIT} exchanges")
    print("="*56)
    print("  Wake    : 'Hey JARVIS'")
    print("  Standby : 'That's all JARVIS' / 'Thank you JARVIS'")
    print("  Exit    : 'Shut down JARVIS' / 'Goodbye JARVIS'")
    print("  Date    : 'What time is it?' / 'What day is it?'")
    print("  Specs   : 'System specs' / 'How much RAM?'")
    print("  Memory  : 'Clear memory'")
    print("="*56)
    print("  Everything runs offline. No internet required.")
    print("="*56 + "\n")
    if not USE_PIPER:
        print("  !! WARNING: piper.exe not found — using pyttsx3 fallback.")
        print("  !! Place piper.exe at C:\\JARVIS\\piper\\piper.exe\n")

# ── Main ──────────────────────────────────────────────────────────
def main():
    print_banner()
    speak("All systems online. Good day sir. J.A.R.V.I.S. is ready.")
    active = True

    while True:
        if active:
            user_input = listen(short=False)

            if user_input is None:
                active = False
                speak("Standing by. Say Hey JARVIS when you need me.")
                continue

            if is_exit_command(user_input):
                shutdown()
            elif is_standby_command(user_input):
                active = False
                speak("Of course, sir. Say Hey JARVIS when you need me.")
            elif is_date_command(user_input):
                speak(get_date_response())
            elif is_specs_command(user_input):
                speak(get_specs_response())
            elif is_clear_command(user_input):
                conversation_history.clear()
                save_memory([])
                speak("Memory wiped clean, sir. Starting fresh.")
            else:
                response = ask_jarvis(user_input)
                speak(response)

        else:
            # Standby — short poll for wake word only
            user_input = listen(short=True)

            if user_input is None:
                continue

            if is_exit_command(user_input):
                shutdown()
            elif has_wake_word(user_input):
                active = True
                speak("Yes sir, I am listening.")

if __name__ == "__main__":
    main()