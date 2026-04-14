import speech_recognition as sr
import pyttsx3
import ollama
import json
import os
import sys
import wave
import platform
import datetime
import psutil
import pyaudio
import subprocess
import tempfile
from config import (
    MODEL, WAKE_WORDS, MEMORY_LIMIT, SPEECH_RATE, SPEECH_VOLUME,
    MIC_ENERGY_THRESHOLD, MIC_PAUSE_THRESHOLD, MIC_LISTEN_TIMEOUT,
    MIC_PHRASE_LIMIT, SYSTEM_PROMPT
)

MEMORY_FILE  = "memory.json"
PIPER_EXE    = r"C:\JARVIS\piper\piper.exe"
VOICE_MODEL  = r"C:\JARVIS\voice\jarvis-medium.onnx"
VOICE_CONFIG = r"C:\JARVIS\voice\jarvis-medium.onnx.json"

# ── Check Piper Executable ────────────────────────────────────────
USE_PIPER = os.path.exists(PIPER_EXE) and os.path.exists(VOICE_MODEL)

pa = pyaudio.PyAudio()

# ── Speak Function ────────────────────────────────────────────────
def speak(text):
    """Speak using Piper exe → WAV → PyAudio. Falls back to pyttsx3."""
    print(f"\n  [JARVIS] {text}\n")

    if USE_PIPER:
        try:
            # Write to a temp WAV file
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_path = tmp.name
            tmp.close()

            # Run piper.exe: echo text | piper --model voice.onnx --output_file out.wav
            result = subprocess.run(
                [
                    PIPER_EXE,
                    "--model", VOICE_MODEL,
                    "--config", VOICE_CONFIG,
                    "--output_file", tmp_path,
                    "--sentence_silence", "0.3"
                ],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30
            )

            if result.returncode != 0:
                raise RuntimeError(result.stderr.decode())

            # Play the WAV with PyAudio
            with wave.open(tmp_path, 'rb') as wf:
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
            try:
                os.unlink(tmp_path)
            except:
                pass

    # ── pyttsx3 fallback ─────────────────────────────────────────
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    for v in voices:
        if 'david' in v.name.lower():
            engine.setProperty('voice', v.id)
            break
    engine.setProperty('rate', SPEECH_RATE)
    engine.setProperty('volume', SPEECH_VOLUME)
    engine.say(text)
    engine.runAndWait()

# ── Speech Recognition ────────────────────────────────────────────
recognizer = sr.Recognizer()
recognizer.energy_threshold        = MIC_ENERGY_THRESHOLD
recognizer.pause_threshold         = MIC_PAUSE_THRESHOLD
recognizer.dynamic_energy_threshold = True

def listen():
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.4)
        print("  [Listening...]", end="", flush=True)
        try:
            audio = recognizer.listen(
                source,
                timeout=MIC_LISTEN_TIMEOUT,
                phrase_time_limit=MIC_PHRASE_LIMIT
            )
            print(" Processing...", end="", flush=True)
            text = recognizer.recognize_google(audio)
            print(f"\n  [You] {text}")
            return text.lower().strip()
        except sr.WaitTimeoutError:
            print(" (no input)")
            return None
        except sr.UnknownValueError:
            print(" (unclear audio)")
            return None
        except sr.RequestError:
            speak("Speech service is unavailable. Please check your internet.")
            return None

# ── Memory ────────────────────────────────────────────────────────
def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def save_memory(history):
    with open(MEMORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def trim_memory(history):
    max_messages = MEMORY_LIMIT * 2
    if len(history) > max_messages:
        history = history[-max_messages:]
    return history

# ── Built-in Commands ────────────────────────────────────────────
def get_date_response():
    now  = datetime.datetime.now()
    day  = now.strftime("%A")
    date = now.strftime("%B %d, %Y")
    time = now.strftime("%I:%M %p")
    return f"Today is {day}, {date}. The current time is {time}, sir."

def get_specs_response():
    cpu_cores   = psutil.cpu_count(logical=False)
    cpu_threads = psutil.cpu_count(logical=True)
    cpu_freq    = psutil.cpu_freq()
    freq_str    = f"{cpu_freq.current:.0f} MHz" if cpu_freq else "unknown frequency"
    ram         = psutil.virtual_memory()
    ram_total   = f"{ram.total  / (1024**3):.1f} GB"
    ram_used    = f"{ram.used   / (1024**3):.1f} GB"
    ram_pct     = f"{ram.percent:.0f} percent"
    disk        = psutil.disk_usage('C:\\')
    disk_total  = f"{disk.total / (1024**3):.0f} GB"
    disk_free   = f"{disk.free  / (1024**3):.0f} GB"
    os_name     = f"{platform.system()} {platform.release()}"
    return (
        f"Current system status, sir. "
        f"Operating system: {os_name}. "
        f"Processor: {cpu_cores} cores and {cpu_threads} threads at {freq_str}. "
        f"Memory: {ram_used} used of {ram_total} total, at {ram_pct} capacity. "
        f"Storage drive C: {disk_free} free of {disk_total} total."
    )

# ── Command Matchers ──────────────────────────────────────────────
def is_date_command(text):
    keywords = [
        "what day", "what's today", "whats today", "today's date",
        "todays date", "what date", "current date", "what time",
        "current time", "what is the date", "what is the time",
        "what's the time", "whats the time", "tell me the time",
        "tell me the date"
    ]
    return any(k in text for k in keywords)

def is_specs_command(text):
    keywords = [
        "system specs", "machine specs", "computer specs",
        "system status", "how much ram", "memory usage",
        "cpu info", "cpu usage", "disk space", "storage space",
        "system info", "system information", "hardware info",
        "check my system", "check system"
    ]
    return any(k in text for k in keywords)

def has_wake_word(text):
    if not text:
        return False
    return any(wake in text for wake in WAKE_WORDS)

def is_standby_command(text):
    phrases = [
        "that's it jarvis", "thats it jarvis",
        "stand by", "standby",
        "go to sleep", "sleep mode",
        "thank you jarvis", "thanks jarvis",
        "that will be all", "that'll be all",
        "rest jarvis", "go standby"
    ]
    return any(p in text for p in phrases)

def is_exit_command(text):
    phrases = [
        "shut down", "shutdown", "power off",
        "turn off", "goodbye jarvis", "bye jarvis",
        "exit jarvis", "terminate", "close jarvis",
        "stop jarvis", "jarvis exit", "jarvis shutdown",
        "power down", "jarvis power off", "jarvis turn off"
    ]
    return any(p in text for p in phrases)

def is_clear_command(text):
    return any(p in text for p in [
        "clear memory", "forget everything", "reset memory", "wipe memory"
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
        reply = response['message']['content'].strip()
        print(" Done.")
        conversation_history.append({"role": "assistant", "content": reply})
        conversation_history = trim_memory(conversation_history)
        save_memory(conversation_history)
        return reply
    except Exception as e:
        print(f"\n  [ERROR] {e}")
        return "My core systems encountered an issue. Please ensure Ollama is running."

# ── Shutdown ──────────────────────────────────────────────────────
def shutdown():
    speak("Understood. Saving memory and initiating shutdown. Goodbye, sir.")
    save_memory(conversation_history)
    try:
        pa.terminate()
    except:
        pass
    sys.exit(0)

# ── Startup Banner ────────────────────────────────────────────────
def print_banner():
    voice_status = "jgkawell/jarvis (Piper exe)" if USE_PIPER else "pyttsx3 (fallback)"
    print("\n" + "="*54)
    print("   J.A.R.V.I.S  —  Local AI Assistant")
    print(f"   Model : {MODEL}")
    print(f"   Voice : {voice_status}")
    print(f"   Memory: last {MEMORY_LIMIT} exchanges loaded")
    print("="*54)
    print("  Wake    : 'Hey JARVIS' / 'JARVIS'")
    print("  Standby : 'That's it JARVIS' / 'Thank you JARVIS'")
    print("  Exit    : 'Shut down' / 'Power off' / 'Goodbye JARVIS'")
    print("  Date    : 'What time is it?' / 'What day is it?'")
    print("  Specs   : 'System specs' / 'CPU info' / 'How much RAM'")
    print("="*54 + "\n")

    if not USE_PIPER:
        print("  !! WARNING: Piper exe not found at C:\\JARVIS\\piper\\piper.exe")
        print("  !! Using pyttsx3 voice instead.")
        print("  !! Download: github.com/rhasspy/piper/releases\n")

# ── Main ──────────────────────────────────────────────────────────
def main():
    print_banner()
    speak("All systems online sir. JARVIS is ready and standing by.")
    active = True

    while True:
        if active:
            user_input = listen()

            if not user_input:
                active = False
                speak("No input detected. Entering standby. Say Hey JARVIS to resume.")
                continue

            if is_exit_command(user_input):
                shutdown()
            elif is_standby_command(user_input):
                speak("Of course sir. I will be here when you need me. Say Hey JARVIS to resume.")
                active = False
            elif is_date_command(user_input):
                speak(get_date_response())
            elif is_specs_command(user_input):
                speak(get_specs_response())
            elif is_clear_command(user_input):
                conversation_history.clear()
                save_memory([])
                speak("Memory wiped clean sir. Starting with a fresh slate.")
            else:
                response = ask_jarvis(user_input)
                speak(response)

        else:
            user_input = listen()
            if not user_input:
                continue
            if is_exit_command(user_input):
                shutdown()
            elif has_wake_word(user_input):
                speak("Yes sir, I am listening.")
                active = True

if __name__ == "__main__":
    main()