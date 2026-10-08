import threading
import queue
import time
import pyttsx3

# ── Voice Assistant Module ────────────────────────────────────
# Uses pyttsx3 for text-to-speech (offline, no API needed)
# Uses SpeechRecognition for voice commands


class VoiceAssistant:
    def __init__(self):
        self.enabled = True
        self.speech_queue = queue.Queue()
        self._on_command_heard = None
        self._speaking_lock = threading.Lock()
        self._start_worker()
        print("[Voice] VoiceAssistant ready.")

    def set_command_callback(self, callback):
        """Register a callback to show heard text in the UI (visual feedback)."""
        self._on_command_heard = callback

    def _speak_now(self, text):
        """Speak a single phrase in a fresh pyttsx3 engine instance.
        pyttsx3 is NOT thread-safe with a shared engine — creating a new
        instance per utterance is the standard fix for background-thread use."""
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 155)
            engine.setProperty('volume', 0.9)
            voices = engine.getProperty('voices')
            for voice in voices:
                if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                    engine.setProperty('voice', voice.id)
                    break
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"[Voice] Speak error: {e}")

    def _start_worker(self):
        """Background thread that processes the speech queue one item at a time."""
        def worker():
            while True:
                try:
                    text = self.speech_queue.get(timeout=0.5)
                    if text is None:
                        break
                    if self.enabled:
                        with self._speaking_lock:
                            self._speak_now(text)
                    self.speech_queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"[Voice] Worker error: {e}")

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def speak(self, text):
        """Queue text for speaking."""
        if not self.enabled:
            return
        self.speech_queue.put(text)

    def speak_interrupt(self, text):
        """Clear any pending queued speech and say this instead."""
        if not self.enabled:
            return
        # Drain pending items (not the one currently being spoken)
        while True:
            try:
                self.speech_queue.get_nowait()
                self.speech_queue.task_done()
            except queue.Empty:
                break
        self.speech_queue.put(text)

    def toggle(self):
        self.enabled = not self.enabled
        return self.enabled

    def stop(self):
        """Drain the queue so no further items are spoken."""
        while True:
            try:
                self.speech_queue.get_nowait()
                self.speech_queue.task_done()
            except queue.Empty:
                break


class VoiceCommandListener:
    """Listens for voice commands using microphone."""
    def __init__(self, assistant, command_callback):
        self.assistant = assistant
        self.callback = command_callback
        self.active = False

    def start_listening(self):
        self.active = True
        t = threading.Thread(target=self._listen_loop, daemon=True)
        t.start()

    def stop_listening(self):
        self.active = False

    def _listen_loop(self):
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            recognizer.energy_threshold = 300
            recognizer.dynamic_energy_threshold = True
            mic = sr.Microphone()

            with mic as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.8)
                print("[Voice] Ambient noise adjusted. Listening...")

            while self.active:
                try:
                    with mic as source:
                        audio = recognizer.listen(source, timeout=4, phrase_time_limit=6)
                    text = recognizer.recognize_google(audio).lower()
                    print(f"[Voice] Heard: {text}")

                    if self.assistant._on_command_heard:
                        self.assistant._on_command_heard(f'🎙 Heard: "{text}"')

                    self._process_command(text)

                except sr.WaitTimeoutError:
                    pass
                except sr.UnknownValueError:
                    if self.assistant._on_command_heard:
                        self.assistant._on_command_heard("🎙 Listening... (couldn't understand)")
                except Exception as e:
                    print(f"[Voice] Listen error: {e}")
                    if self.assistant._on_command_heard:
                        self.assistant._on_command_heard(f"🎙 Error: {e}")

        except ImportError:
            print("[Voice] SpeechRecognition not installed. Run: pip install SpeechRecognition pyaudio")

    def _process_command(self, text):
        commands = {
            # Navigation
            "generate paper":       "nav_generate",
            "open generate":        "nav_generate",
            "go to generate":       "nav_generate",
            "ai generate":          "nav_ai",
            "open ai":              "nav_ai",
            "go to ai":             "nav_ai",
            "question bank":        "nav_bank",
            "open bank":            "nav_bank",
            "go to bank":           "nav_bank",
            "show history":         "nav_history",
            "open history":         "nav_history",
            "go to history":        "nav_history",
            # Actions
            "generate":             "action_generate",
            "create paper":         "action_generate",
            "make paper":           "action_generate",
            "show preview":         "action_preview",
            "preview":              "action_preview",
            "save":                 "action_save",
            "clear":                "action_clear",
            "reset":                "action_clear",
            "logout":               "action_logout",
            "log out":              "action_logout",
            "sign out":             "action_logout",
            # Voice control
            "stop listening":       "voice_stop",
            "stop voice":           "voice_stop",
            "mute":                 "voice_mute",
            "mute voice":           "voice_mute",
            "unmute":               "voice_unmute",
            "unmute voice":         "voice_unmute",
            "enable voice":         "voice_unmute",
            # Help
            "help":                 "action_help",
            "what can you do":      "action_help",
            "commands":             "action_help",
        }

        for phrase, action in commands.items():
            if phrase in text:
                self.callback(action)
                return

        self.assistant.speak("Sorry, I didn't catch that. Say help for a list of commands.")


# ── Global assistant instance ─────────────────────────────────
_assistant = None

def get_assistant():
    global _assistant
    if _assistant is None:
        _assistant = VoiceAssistant()
    return _assistant

def speak(text):
    get_assistant().speak(text)