import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
import threading
from datetime import datetime

from database import initialize_db, seed_sample_questions, get_connection
from engine import select_questions, validate_marks
from pdf_generator import generate_pdf
from ai_generator import extract_text_from_file, generate_questions_with_ai, save_ai_questions_to_db
from voice_assistant import VoiceAssistant, VoiceCommandListener, speak

# ─── COLORS & FONTS ─────────────────────────────────────────
BG        = "#f0f4f8"
PRIMARY   = "#1a1a2e"
ACCENT    = "#4a90d9"
WHITE     = "#ffffff"
LIGHT     = "#e8edf2"
SUCCESS   = "#27ae60"
FONT      = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE= ("Segoe UI", 16, "bold")
FONT_SUB  = ("Segoe UI", 11)

BLOOMS_LEVELS = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]
BLOOMS_COLORS = {
    "Remember":   "#e74c3c",
    "Understand": "#e67e22",
    "Apply":      "#f1c40f",
    "Analyze":    "#2ecc71",
    "Evaluate":   "#3498db",
    "Create":     "#9b59b6",
}


# ─── LOGIN ───────────────────────────────────────────────────
class LoginWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("Auto Question Paper Generator — Login")
        self.root.geometry("420x500")
        self.root.resizable(False, False)
        self.root.configure(bg=PRIMARY)
        self.assistant = VoiceAssistant()
        self.build_ui()
        self.assistant.speak("Welcome to Auto Question Paper Generator. Please login to continue.")

    def build_ui(self):
        tk.Label(self.root, text="📄", font=("Segoe UI", 40), bg=PRIMARY, fg=WHITE).pack(pady=(40, 5))
        tk.Label(self.root, text="Question Paper Generator", font=FONT_TITLE, bg=PRIMARY, fg=WHITE).pack()
        tk.Label(self.root, text="Please login to continue", font=FONT_SUB, bg=PRIMARY, fg="#aaaacc").pack(pady=(5, 30))

        card = tk.Frame(self.root, bg=WHITE, padx=30, pady=30)
        card.pack(padx=30, fill="x")

        tk.Label(card, text="Username", font=FONT_BOLD, bg=WHITE, anchor="w").pack(fill="x")
        self.username_var = tk.StringVar()
        tk.Entry(card, textvariable=self.username_var, font=FONT, relief="flat", bg=LIGHT).pack(
            fill="x", pady=(4, 12), ipady=6)

        tk.Label(card, text="Password", font=FONT_BOLD, bg=WHITE, anchor="w").pack(fill="x")
        self.password_var = tk.StringVar()
        tk.Entry(card, textvariable=self.password_var, font=FONT, relief="flat", bg=LIGHT, show="*").pack(
            fill="x", pady=(4, 20), ipady=6)

        tk.Button(card, text="LOGIN", font=FONT_BOLD, bg=ACCENT, fg=WHITE,
                  relief="flat", pady=10, cursor="hand2", command=self.login).pack(fill="x")

        tk.Label(self.root, text="Default: admin/admin123  |  faculty/faculty123",
                 font=("Segoe UI", 8), bg=PRIMARY, fg="#888899").pack(pady=(15, 0))

    def login(self):
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        if not username or not password:
            self.assistant.speak("Please enter your username and password.")
            messagebox.showerror("Error", "Please enter username and password.")
            return
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            self.assistant.speak(f"Welcome, {user[1]}! Login successful.")
            self.root.destroy()
            main_root = tk.Tk()
            MainApp(main_root, user, self.assistant)
            main_root.mainloop()
        else:
            self.assistant.speak("Login failed. Invalid username or password. Please try again.")
            messagebox.showerror("Login Failed", "Invalid username or password.")


# ─── EDIT QUESTION POPUP ─────────────────────────────────────
class EditQuestionDialog:
    """Popup dialog to edit an existing question."""
    def __init__(self, parent, question_data, on_save_callback):
        self.on_save = on_save_callback
        self.q = question_data

        self.win = tk.Toplevel(parent)
        self.win.title("Edit Question")
        self.win.geometry("700x560")
        self.win.configure(bg=BG)
        self.win.grab_set()  # Modal
        self.build_ui()

    def build_ui(self):
        tk.Label(self.win, text="Edit Question", font=FONT_TITLE, bg=BG, fg=PRIMARY).pack(pady=(15, 5), padx=20, anchor="w")
        ttk.Separator(self.win, orient="horizontal").pack(fill="x", padx=20, pady=5)

        form = tk.Frame(self.win, bg=WHITE, padx=20, pady=15)
        form.pack(fill="both", expand=True, padx=20, pady=5)
        form.columnconfigure(1, weight=1)

        # Question text
        tk.Label(form, text="Question Text", font=FONT_BOLD, bg=WHITE).grid(row=0, column=0, sticky="nw", pady=6, padx=(0,10))
        self.q_text = tk.Text(form, font=FONT, bg=LIGHT, relief="flat", height=3, wrap="word")
        self.q_text.grid(row=0, column=1, columnspan=3, sticky="ew", pady=6, ipady=4)
        self.q_text.insert("1.0", self.q.get("question_text", ""))

        # Type, Difficulty, Marks
        tk.Label(form, text="Type", font=FONT_BOLD, bg=WHITE).grid(row=1, column=0, sticky="w", pady=6, padx=(0,10))
        self.type_var = tk.StringVar(value=self.q.get("question_type", "MCQ"))
        ttk.Combobox(form, textvariable=self.type_var, values=["MCQ", "Short", "Long"],
                     state="readonly", font=FONT, width=10).grid(row=1, column=1, sticky="w", pady=6)

        tk.Label(form, text="Difficulty", font=FONT_BOLD, bg=WHITE).grid(row=1, column=2, sticky="w", padx=(15,10))
        self.diff_var = tk.StringVar(value=self.q.get("difficulty", "Medium"))
        ttk.Combobox(form, textvariable=self.diff_var, values=["Easy", "Medium", "Hard"],
                     state="readonly", font=FONT, width=10).grid(row=1, column=3, sticky="w", pady=6)

        tk.Label(form, text="Marks", font=FONT_BOLD, bg=WHITE).grid(row=2, column=0, sticky="w", pady=6, padx=(0,10))
        self.marks_var = tk.IntVar(value=self.q.get("marks", 1))
        tk.Spinbox(form, from_=1, to=20, textvariable=self.marks_var,
                   font=FONT, bg=LIGHT, relief="flat", width=8).grid(row=2, column=1, sticky="w", pady=6)

        # MCQ Options
        tk.Label(form, text="Option A", font=FONT_BOLD, bg=WHITE).grid(row=3, column=0, sticky="w", pady=4, padx=(0,10))
        self.opt_a = tk.StringVar(value=self.q.get("option_a") or "")
        tk.Entry(form, textvariable=self.opt_a, font=FONT, bg=LIGHT, relief="flat").grid(
            row=3, column=1, columnspan=3, sticky="ew", pady=4, ipady=4)

        tk.Label(form, text="Option B", font=FONT_BOLD, bg=WHITE).grid(row=4, column=0, sticky="w", pady=4, padx=(0,10))
        self.opt_b = tk.StringVar(value=self.q.get("option_b") or "")
        tk.Entry(form, textvariable=self.opt_b, font=FONT, bg=LIGHT, relief="flat").grid(
            row=4, column=1, columnspan=3, sticky="ew", pady=4, ipady=4)

        tk.Label(form, text="Option C", font=FONT_BOLD, bg=WHITE).grid(row=5, column=0, sticky="w", pady=4, padx=(0,10))
        self.opt_c = tk.StringVar(value=self.q.get("option_c") or "")
        tk.Entry(form, textvariable=self.opt_c, font=FONT, bg=LIGHT, relief="flat").grid(
            row=5, column=1, columnspan=3, sticky="ew", pady=4, ipady=4)

        tk.Label(form, text="Option D", font=FONT_BOLD, bg=WHITE).grid(row=6, column=0, sticky="w", pady=4, padx=(0,10))
        self.opt_d = tk.StringVar(value=self.q.get("option_d") or "")
        tk.Entry(form, textvariable=self.opt_d, font=FONT, bg=LIGHT, relief="flat").grid(
            row=6, column=1, columnspan=3, sticky="ew", pady=4, ipady=4)

        tk.Label(form, text="Answer", font=FONT_BOLD, bg=WHITE).grid(row=7, column=0, sticky="w", pady=4, padx=(0,10))
        self.answer_var = tk.StringVar(value=self.q.get("answer") or "")
        tk.Entry(form, textvariable=self.answer_var, font=FONT, bg=LIGHT, relief="flat", width=10).grid(
            row=7, column=1, sticky="w", pady=4, ipady=4)
        tk.Label(form, text="(A/B/C/D for MCQ)", font=("Segoe UI", 9), bg=WHITE, fg="#999").grid(
            row=7, column=2, sticky="w", padx=5)

        # Buttons
        btn_frame = tk.Frame(self.win, bg=BG)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="💾  Save Changes", font=FONT_BOLD, bg=SUCCESS, fg=WHITE,
                  relief="flat", padx=20, pady=8, cursor="hand2",
                  command=self.save).pack(side="left", padx=10)
        tk.Button(btn_frame, text="Cancel", font=FONT, bg="#95a5a6", fg=WHITE,
                  relief="flat", padx=20, pady=8, cursor="hand2",
                  command=self.win.destroy).pack(side="left", padx=10)

    def save(self):
        q_text = self.q_text.get("1.0", "end").strip()
        if not q_text:
            messagebox.showerror("Error", "Question text cannot be empty.", parent=self.win)
            return

        updated = {
            "id": self.q["id"],
            "question_text": q_text,
            "question_type": self.type_var.get(),
            "difficulty": self.diff_var.get(),
            "marks": self.marks_var.get(),
            "option_a": self.opt_a.get().strip() or None,
            "option_b": self.opt_b.get().strip() or None,
            "option_c": self.opt_c.get().strip() or None,
            "option_d": self.opt_d.get().strip() or None,
            "answer": self.answer_var.get().strip() or None,
        }

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE questions SET question_text=?, question_type=?, difficulty=?,
            marks=?, option_a=?, option_b=?, option_c=?, option_d=?, answer=?
            WHERE id=?
        ''', (updated["question_text"], updated["question_type"], updated["difficulty"],
              updated["marks"], updated["option_a"], updated["option_b"],
              updated["option_c"], updated["option_d"], updated["answer"], updated["id"]))
        conn.commit()
        conn.close()

        messagebox.showinfo("Saved", "Question updated successfully!", parent=self.win)
        self.win.destroy()
        self.on_save()


# ─── PREVIEW WINDOW ──────────────────────────────────────────
class PreviewWindow:
    """Shows selected questions before generating PDF. Allows proceeding or cancelling."""
    def __init__(self, parent, questions, config, on_confirm_callback):
        self.parent = parent
        self.questions = questions
        self.config = config
        self.on_confirm = on_confirm_callback

        self.win = tk.Toplevel(parent)
        self.win.title("Preview — Question Paper")
        self.win.geometry("820x620")
        self.win.configure(bg=BG)
        self.win.grab_set()
        self.build_ui()

    def build_ui(self):
        # Header
        header = tk.Frame(self.win, bg=PRIMARY, padx=20, pady=12)
        header.pack(fill="x")
        tk.Label(header, text="📋 Question Paper Preview", font=FONT_TITLE, bg=PRIMARY, fg=WHITE).pack(side="left")
        total = sum(q['marks'] for q in self.questions)
        tk.Label(header, text=f"Total: {len(self.questions)} Qs | {total} Marks",
                 font=FONT_BOLD, bg=PRIMARY, fg="#aaaacc").pack(side="right")

        # Summary bar
        summary = tk.Frame(self.win, bg=LIGHT, padx=20, pady=8)
        summary.pack(fill="x")
        mcq   = len([q for q in self.questions if q['question_type'] == 'MCQ'])
        short = len([q for q in self.questions if q['question_type'] == 'Short'])
        long  = len([q for q in self.questions if q['question_type'] == 'Long'])
        tk.Label(summary, text=f"Subject: {self.config['subject']}   |   "
                               f"MCQ: {mcq}   Short: {short}   Long: {long}   |   "
                               f"Exam: {self.config['exam_type']}   Duration: {self.config['duration']} min",
                 font=FONT, bg=LIGHT, fg=PRIMARY).pack(anchor="w")

        # Question list
        list_frame = tk.Frame(self.win, bg=BG)
        list_frame.pack(fill="both", expand=True, padx=15, pady=10)

        canvas = tk.Canvas(list_frame, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self.scroll_frame = tk.Frame(canvas, bg=BG)
        self.scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        sections = [("SECTION A — MCQ", "MCQ"), ("SECTION B — Short Answer", "Short"), ("SECTION C — Long Answer", "Long")]
        for section_title, q_type in sections:
            qs = [q for q in self.questions if q['question_type'] == q_type]
            if not qs:
                continue
            tk.Label(self.scroll_frame, text=section_title, font=FONT_BOLD,
                     bg=PRIMARY, fg=WHITE, padx=10, pady=5).pack(fill="x", pady=(10, 3))
            for i, q in enumerate(qs, 1):
                q_frame = tk.Frame(self.scroll_frame, bg=WHITE, padx=12, pady=8)
                q_frame.pack(fill="x", pady=2)
                header_row = tk.Frame(q_frame, bg=WHITE)
                header_row.pack(fill="x")
                tk.Label(header_row, text=f"Q{i}. {q['question_text']}", font=FONT,
                         bg=WHITE, anchor="w", wraplength=560, justify="left").pack(side="left", fill="x", expand=True)
                tk.Label(header_row, text=f"[{q['marks']} mark{'s' if q['marks']>1 else ''}]",
                         font=("Segoe UI", 9, "italic"), bg=WHITE, fg=ACCENT).pack(side="right", padx=(5,0))
                tk.Button(header_row, text="✏️", font=("Segoe UI", 9), bg=LIGHT,
                          relief="flat", cursor="hand2", padx=4,
                          command=lambda qdata=q: self.edit_question_in_preview(qdata)).pack(side="right")
                if q_type == "MCQ":
                    opts = tk.Frame(q_frame, bg=WHITE)
                    opts.pack(fill="x", padx=15, pady=2)
                    for label, key in [("A", "option_a"), ("B", "option_b"), ("C", "option_c"), ("D", "option_d")]:
                        val = q.get(key)
                        if val:
                            tk.Label(opts, text=f"({label}) {val}", font=("Segoe UI", 9),
                                     bg=WHITE, fg="#555", anchor="w").pack(anchor="w")

        # Bottom buttons
        btn_frame = tk.Frame(self.win, bg=BG, pady=12)
        btn_frame.pack(fill="x", padx=20)
        tk.Button(btn_frame, text="✅  Generate PDF", font=FONT_BOLD, bg=SUCCESS, fg=WHITE,
                  relief="flat", padx=25, pady=10, cursor="hand2",
                  command=self.confirm).pack(side="right", padx=5)
        tk.Button(btn_frame, text="✖  Cancel", font=FONT, bg="#95a5a6", fg=WHITE,
                  relief="flat", padx=20, pady=10, cursor="hand2",
                  command=self.win.destroy).pack(side="right", padx=5)

    def edit_question_in_preview(self, q_data):
        """Open edit dialog from preview; refresh preview after saving."""
        def on_save_refresh():
            # Reload the updated question from DB and update in self.questions list
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM questions WHERE id=?", (q_data["id"],))
            row = cursor.fetchone()
            columns = [desc[0] for desc in cursor.description]
            conn.close()
            if row:
                updated = dict(zip(columns, row))
                for idx, q in enumerate(self.questions):
                    if q["id"] == updated["id"]:
                        self.questions[idx] = updated
                        break
            # Rebuild preview content
            self.win.destroy()
            PreviewWindow(self.parent, self.questions, self.config, self.on_confirm)

        EditQuestionDialog(self.win, q_data, on_save_refresh)

    def confirm(self):
        self.win.destroy()
        self.on_confirm(self.questions, self.config)


# ─── MAIN APP ────────────────────────────────────────────────
class MainApp:
    def __init__(self, root, user, assistant):
        self.root = root
        self.user = user
        self.assistant = assistant
        self.voice_listening = False
        self.root.title(f"Auto Question Paper Generator — {user[1]} ({user[3]})")
        self.root.geometry("980x700")
        self.root.configure(bg=BG)
        self.build_ui()
        self.assistant.speak("Dashboard loaded. You can navigate using the sidebar or use voice commands.")
        # Auto-start voice listening after greeting finishes
        self.root.after(1500, self._auto_start_listening)

    def build_ui(self):
        sidebar = tk.Frame(self.root, bg=PRIMARY, width=210)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="📄 QPG", font=("Segoe UI", 14, "bold"), bg=PRIMARY, fg=WHITE).pack(pady=(20, 5))
        tk.Label(sidebar, text="AI Question Paper\nGenerator", font=("Segoe UI", 9),
                 bg=PRIMARY, fg="#aaaacc", justify="center").pack(pady=(0, 15))
        ttk.Separator(sidebar, orient="horizontal").pack(fill="x", padx=10)

        nav = [
            ("🏠  Generate Paper",    self.show_generate),
            ("🤖  AI Generate (New)", self.show_ai_generate),
            ("📚  Question Bank",     self.show_question_bank),
            ("📋  History",           self.show_history),
        ]
        for text, cmd in nav:
            btn = tk.Button(sidebar, text=text, font=("Segoe UI", 10),
                            bg=PRIMARY, fg=WHITE, relief="flat", anchor="w",
                            padx=15, pady=12, cursor="hand2",
                            activebackground="#2a2a4e", activeforeground=WHITE,
                            command=cmd)
            btn.pack(fill="x")

        ttk.Separator(sidebar, orient="horizontal").pack(fill="x", padx=10, pady=5)

        tk.Label(sidebar, text="🎙 Voice Assistant", font=("Segoe UI", 9, "bold"),
                 bg=PRIMARY, fg="#aaaacc").pack(pady=(5, 3))

        self.voice_btn = tk.Button(sidebar, text="🎙 Start Listening",
                                   font=("Segoe UI", 9), bg="#27ae60", fg=WHITE,
                                   relief="flat", padx=10, pady=8, cursor="hand2",
                                   command=self.toggle_listening)
        self.voice_btn.pack(fill="x", padx=10, pady=2)

        self.mute_btn = tk.Button(sidebar, text="🔊 Mute Voice",
                                  font=("Segoe UI", 9), bg="#7f8c8d", fg=WHITE,
                                  relief="flat", padx=10, pady=8, cursor="hand2",
                                  command=self.toggle_mute)
        self.mute_btn.pack(fill="x", padx=10, pady=2)

        # FIX 1: Visual command status bar
        self.voice_status_label = tk.Label(sidebar, text="🎙 Ready",
                                           font=("Segoe UI", 8), bg=PRIMARY,
                                           fg="#aaaacc", wraplength=180, justify="center")
        self.voice_status_label.pack(fill="x", padx=8, pady=(4, 0))

        tk.Button(sidebar, text="🚪  Logout", font=("Segoe UI", 10),
                  bg="#c0392b", fg=WHITE, relief="flat", anchor="w",
                  padx=15, pady=12, cursor="hand2",
                  command=self.logout).pack(side="bottom", fill="x")

        self.content = tk.Frame(self.root, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)

        # FIX 1: Register visual feedback callback
        self.assistant.set_command_callback(self._update_voice_status)
        self.show_generate()

    # ── VOICE CONTROLS ───────────────────────────────────────
    def _auto_start_listening(self):
        """Auto-start voice listening on dashboard load."""
        try:
            import speech_recognition as sr  # noqa: F401
            import pyaudio  # noqa: F401
            self.toggle_listening()
        except ImportError as e:
            missing = "pyaudio" if "pyaudio" in str(e) else "SpeechRecognition"
            print(f"[Voice] Cannot auto-start: {missing} not installed. "
                  f"Run: pip install SpeechRecognition pyaudio")
            self._update_voice_status(f"⚠ {missing} not installed")

    def toggle_listening(self):
        if not self.voice_listening:
            self.voice_listening = True
            self.voice_btn.config(text="🔴 Stop Listening", bg="#e74c3c")
            self.listener = VoiceCommandListener(self.assistant, self.handle_voice_command)
            self.listener.start_listening()
            self.assistant.speak("Voice commands activated.")
        else:
            self.voice_listening = False
            self.voice_btn.config(text="🎙 Start Listening", bg="#27ae60")
            self.listener.stop_listening()
            self.assistant.speak("Voice commands deactivated.")

    def toggle_mute(self):
        enabled = self.assistant.toggle()
        if enabled:
            self.mute_btn.config(text="🔊 Mute Voice", bg="#7f8c8d")
            self.assistant.speak("Voice assistant unmuted.")
        else:
            self.mute_btn.config(text="🔇 Unmuted", bg="#e74c3c")

    def _update_voice_status(self, text):
        """FIX 1: Update visual voice status label in sidebar."""
        try:
            self.root.after(0, lambda: self.voice_status_label.config(text=text))
            # Auto-clear after 4 seconds
            self.root.after(4000, lambda: self.voice_status_label.config(text="🎙 Ready"))
        except:
            pass

    def handle_voice_command(self, action):
        self.root.after(0, lambda: self._execute_command(action))

    def _execute_command(self, action):
        if action == "nav_generate":
            self.assistant.speak("Opening Generate Paper.")
            self.show_generate(announce=False)
            self.assistant.speak("Configure settings then click Generate Question Paper.")
        elif action == "nav_ai":
            self.assistant.speak("Opening AI Generate.")
            self.show_ai_generate(announce=False)
            self.assistant.speak("Upload your topic file, enter subject and unit, then click Generate with AI.")
        elif action == "nav_bank":
            self.assistant.speak("Opening Question Bank.")
            self.show_question_bank(announce=False)
            self.assistant.speak("Showing all stored questions.")
        elif action == "nav_history":
            self.assistant.speak("Opening History.")
            self.show_history(announce=False)
            self.assistant.speak("Showing all previously generated question papers.")
        elif action == "action_generate":
            self.assistant.speak("Generating question paper.")
            try: self.generate_paper()
            except: self.assistant.speak("Please go to Generate Paper screen first.")
        elif action == "action_logout":
            self.assistant.speak("Logging out. Goodbye!")
            self.root.after(1500, self.logout)
        elif action == "voice_stop":
            self.toggle_listening()
        elif action == "voice_mute":
            if self.assistant.enabled: self.toggle_mute()
        elif action == "voice_unmute":
            if not self.assistant.enabled: self.toggle_mute()
        elif action == "action_preview":
            # FIX 2: trigger preview if on generate screen
            self.assistant.speak("Showing preview.")
            try: self.generate_paper()
            except: self.assistant.speak("Please go to the Generate Paper screen first.")
        elif action == "action_clear":
            # FIX 2: clear current screen and reload
            self.assistant.speak("Screen cleared.")
            self.show_generate()
        elif action == "action_help":
            # FIX 2: read out available commands
            self.assistant.speak(
                "Available commands: generate paper, A I generate, question bank, "
                "show history, preview, clear, mute, unmute, logout, stop listening."
            )

    def clear_content(self):
        for w in self.content.winfo_children():
            w.destroy()

    def page_title(self, title, subtitle=""):
        tk.Label(self.content, text=title, font=FONT_TITLE, bg=BG, fg=PRIMARY).pack(anchor="w", padx=20, pady=(20, 2))
        if subtitle:
            tk.Label(self.content, text=subtitle, font=FONT_SUB, bg=BG, fg="#666").pack(anchor="w", padx=20)
        ttk.Separator(self.content, orient="horizontal").pack(fill="x", padx=20, pady=8)

    # ── AI GENERATE ──────────────────────────────────────────
    def show_ai_generate(self, announce=True):
        self.clear_content()
        self.page_title("🤖 AI Question Generator", "Upload topic file → AI generates Bloom's Taxonomy questions")
        if announce:
            self.assistant.speak_interrupt("AI Generate screen. Upload your topic file, enter subject and unit, then click Generate with AI.")

        scroll = tk.Frame(self.content, bg=BG)
        scroll.pack(fill="both", expand=True, padx=20, pady=5)

        # API Key
        api_card = tk.Frame(scroll, bg=WHITE, padx=20, pady=15)
        api_card.pack(fill="x", pady=5)
        tk.Label(api_card, text="Groq API Key", font=FONT_BOLD, bg=WHITE).grid(row=0, column=0, sticky="w", pady=5)
        self.api_key_var = tk.StringVar()
        tk.Entry(api_card, textvariable=self.api_key_var, font=FONT, bg=LIGHT,
                 relief="flat", show="*", width=50).grid(row=0, column=1, sticky="ew", padx=10, ipady=5)
        tk.Label(api_card, text="gsk_...", font=("Segoe UI", 9), bg=WHITE, fg="#999").grid(
            row=1, column=1, sticky="w", padx=10)
        api_card.columnconfigure(1, weight=1)

        # File upload
        file_card = tk.Frame(scroll, bg=WHITE, padx=20, pady=15)
        file_card.pack(fill="x", pady=5)
        tk.Label(file_card, text="Upload Topic File", font=FONT_BOLD, bg=WHITE).grid(row=0, column=0, sticky="w", pady=5)
        self.file_path_var = tk.StringVar(value="No file selected")
        tk.Label(file_card, textvariable=self.file_path_var, font=FONT, bg=LIGHT,
                 relief="flat", anchor="w", padx=8).grid(row=0, column=1, sticky="ew", padx=10, ipady=5)
        tk.Button(file_card, text="Browse", font=FONT_BOLD, bg=ACCENT, fg=WHITE,
                  relief="flat", padx=10, cursor="hand2",
                  command=self.browse_file).grid(row=0, column=2, padx=5)
        tk.Label(file_card, text="Supported: PDF, TXT, DOCX", font=("Segoe UI", 9),
                 bg=WHITE, fg="#999").grid(row=1, column=1, sticky="w", padx=10)
        file_card.columnconfigure(1, weight=1)

        # Config
        config_card = tk.Frame(scroll, bg=WHITE, padx=20, pady=15)
        config_card.pack(fill="x", pady=5)
        tk.Label(config_card, text="Subject", font=FONT_BOLD, bg=WHITE).grid(row=0, column=0, sticky="w", pady=6)
        self.ai_subject_var = tk.StringVar()
        tk.Entry(config_card, textvariable=self.ai_subject_var, font=FONT, bg=LIGHT,
                 relief="flat").grid(row=0, column=1, sticky="ew", padx=10, ipady=4)
        tk.Label(config_card, text="Unit / Topic", font=FONT_BOLD, bg=WHITE).grid(row=0, column=2, sticky="w", pady=6, padx=(10, 0))
        self.ai_unit_var = tk.StringVar()
        tk.Entry(config_card, textvariable=self.ai_unit_var, font=FONT, bg=LIGHT,
                 relief="flat").grid(row=0, column=3, sticky="ew", padx=10, ipady=4)
        config_card.columnconfigure(1, weight=1)
        config_card.columnconfigure(3, weight=1)

        # Bloom's levels
        blooms_card = tk.Frame(scroll, bg=WHITE, padx=20, pady=15)
        blooms_card.pack(fill="x", pady=5)
        tk.Label(blooms_card, text="Bloom's Taxonomy Levels", font=FONT_BOLD, bg=WHITE).pack(anchor="w")
        levels_frame = tk.Frame(blooms_card, bg=WHITE)
        levels_frame.pack(fill="x", pady=5)
        self.blooms_vars = {}
        for i, level in enumerate(BLOOMS_LEVELS):
            var = tk.BooleanVar(value=True)
            self.blooms_vars[level] = var
            color = BLOOMS_COLORS[level]
            cb_frame = tk.Frame(levels_frame, bg=color, padx=8, pady=5)
            cb_frame.grid(row=0, column=i, padx=5)
            tk.Checkbutton(cb_frame, text=level, variable=var,
                           font=FONT_BOLD, bg=color, fg=WHITE,
                           selectcolor=color, activebackground=color).pack()

        # Questions per level
        count_card = tk.Frame(scroll, bg=WHITE, padx=20, pady=15)
        count_card.pack(fill="x", pady=5)
        tk.Label(count_card, text="Questions per Level", font=FONT_BOLD, bg=WHITE).grid(
            row=0, column=0, columnspan=6, sticky="w", pady=(0, 8))
        tk.Label(count_card, text="MCQ (Remember):", font=FONT, bg=WHITE).grid(row=1, column=0, sticky="w")
        self.ai_mcq_var = tk.IntVar(value=5)
        tk.Spinbox(count_card, from_=1, to=20, textvariable=self.ai_mcq_var,
                   font=FONT, bg=LIGHT, relief="flat", width=5).grid(row=1, column=1, padx=10)
        tk.Label(count_card, text="Short Ans:", font=FONT, bg=WHITE).grid(row=1, column=2, sticky="w", padx=(10, 0))
        self.ai_short_var = tk.IntVar(value=2)
        tk.Spinbox(count_card, from_=1, to=10, textvariable=self.ai_short_var,
                   font=FONT, bg=LIGHT, relief="flat", width=5).grid(row=1, column=3, padx=10)
        tk.Label(count_card, text="Long Ans:", font=FONT, bg=WHITE).grid(row=1, column=4, sticky="w", padx=(10, 0))
        self.ai_long_var = tk.IntVar(value=1)
        tk.Spinbox(count_card, from_=1, to=5, textvariable=self.ai_long_var,
                   font=FONT, bg=LIGHT, relief="flat", width=5).grid(row=1, column=5, padx=10)

        # Generate button
        btn_frame = tk.Frame(scroll, bg=BG)
        btn_frame.pack(pady=15)
        self.ai_gen_btn = tk.Button(btn_frame, text="🤖  GENERATE WITH AI",
                                    font=FONT_BOLD, bg="#9b59b6", fg=WHITE,
                                    relief="flat", pady=12, padx=30, cursor="hand2",
                                    command=self.run_ai_generation)
        self.ai_gen_btn.pack()
        self.ai_status = tk.Label(scroll, text="", font=FONT, bg=BG, fg=SUCCESS, wraplength=600)
        self.ai_status.pack(pady=5)

    def browse_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Supported Files", "*.pdf *.txt *.docx"), ("All Files", "*.*")])
        if path:
            self.file_path_var.set(path)
            self.assistant.speak("File selected. Ready to generate questions.")

    def run_ai_generation(self):
        api_key = self.api_key_var.get().strip()
        file_path = self.file_path_var.get().strip()
        subject = self.ai_subject_var.get().strip()
        unit = self.ai_unit_var.get().strip()

        if file_path == "No file selected" or not os.path.exists(file_path):
            self.assistant.speak("Please select a valid topic file.")
            messagebox.showerror("Error", "Please select a valid topic file.")
            return
        if not subject or not unit:
            self.assistant.speak("Please enter subject and unit name.")
            messagebox.showerror("Error", "Please enter Subject and Unit.")
            return

        selected_levels = [l for l, v in self.blooms_vars.items() if v.get()]
        if not selected_levels:
            messagebox.showerror("Error", "Please select at least one Bloom's level.")
            return

        self.ai_gen_btn.config(state="disabled")
        self.ai_status.config(text="⏳ Extracting text from file...", fg=ACCENT)
        self.assistant.speak("Generating questions. Please wait.")
        self.root.update()

        def task():
            try:
                text = extract_text_from_file(file_path)
                if text.startswith("[ERROR]") or len(text.strip()) < 50:
                    def err():
                        self.ai_status.config(text="❌ Could not extract text. Try a TXT file.", fg="#e74c3c")
                        self.ai_gen_btn.config(state="normal")
                        self.assistant.speak("Could not extract text from file.")
                    self.root.after(0, err)
                    return

                questions = generate_questions_with_ai(
                    text, subject, unit, selected_levels,
                    self.ai_mcq_var.get(), self.ai_short_var.get(),
                    self.ai_long_var.get(), api_key)

                if not questions:
                    def no_q():
                        self.ai_status.config(text="❌ No questions generated. Check API key.", fg="#e74c3c")
                        self.ai_gen_btn.config(state="normal")
                        self.assistant.speak("No questions were generated. Please check your API key.")
                    self.root.after(0, no_q)
                    return

                conn = get_connection()
                saved = save_ai_questions_to_db(questions, conn)
                conn.close()

                def on_success(s=saved):
                    try:
                        self.ai_status.config(text=f"✅ {s} questions generated and saved!", fg=SUCCESS)
                        self.ai_gen_btn.config(state="normal")
                        self.assistant.speak(f"Success! {s} questions saved to the question bank.")
                        messagebox.showinfo("Success", f"✅ {s} questions generated!\n\nGo to Generate Paper to create your exam paper.")
                    except Exception: pass
                self.root.after(0, on_success)

            except Exception as e:
                def on_error(err=str(e)):
                    try:
                        self.ai_status.config(text=f"❌ Error: {err}", fg="#e74c3c")
                        self.ai_gen_btn.config(state="normal")
                        self.assistant.speak(f"An error occurred.")
                    except Exception: pass
                self.root.after(0, on_error)

        threading.Thread(target=task, daemon=True).start()

    # ── GENERATE PAPER ───────────────────────────────────────
    def show_generate(self, announce=True):
        self.clear_content()
        self.page_title("Generate Question Paper", "Configure and auto-generate a balanced exam paper")
        if announce:
            self.assistant.speak_interrupt("Generate Paper screen. Configure settings then click Generate Question Paper.")

        scroll_frame = tk.Frame(self.content, bg=BG)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT subject FROM questions")
        subjects = [r[0] for r in cursor.fetchall()]
        conn.close()

        def get_units(subject):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT unit FROM questions WHERE subject=?", (subject,))
            units = [r[0] for r in cursor.fetchall()]
            conn.close()
            return units

        fields_frame = tk.Frame(scroll_frame, bg=WHITE, padx=20, pady=20)
        fields_frame.pack(fill="x", pady=5)
        fields_frame.columnconfigure(1, weight=1)
        fields_frame.columnconfigure(3, weight=1)

        tk.Label(fields_frame, text="College Name", font=FONT_BOLD, bg=WHITE).grid(row=0, column=0, sticky="w", pady=6, padx=(0, 10))
        self.college_var = tk.StringVar(value="New Horizon College of Engineering")
        tk.Entry(fields_frame, textvariable=self.college_var, font=FONT, bg=LIGHT, relief="flat").grid(
            row=0, column=1, columnspan=3, sticky="ew", pady=6)

        tk.Label(fields_frame, text="Subject", font=FONT_BOLD, bg=WHITE).grid(row=1, column=0, sticky="w", pady=6, padx=(0, 10))
        self.subject_var = tk.StringVar()
        subject_cb = ttk.Combobox(fields_frame, textvariable=self.subject_var, values=subjects, state="readonly", font=FONT)
        subject_cb.grid(row=1, column=1, sticky="ew", pady=6, padx=(0, 20))
        if subjects: subject_cb.set(subjects[0])

        tk.Label(fields_frame, text="Exam Type", font=FONT_BOLD, bg=WHITE).grid(row=1, column=2, sticky="w", pady=6, padx=(0, 10))
        self.exam_type_var = tk.StringVar(value="Mid Semester")
        ttk.Combobox(fields_frame, textvariable=self.exam_type_var,
                     values=["Mid Semester", "End Semester", "Unit Test", "Internal Assessment"],
                     state="readonly", font=FONT).grid(row=1, column=3, sticky="ew", pady=6)

        tk.Label(fields_frame, text="Total Marks", font=FONT_BOLD, bg=WHITE).grid(row=2, column=0, sticky="w", pady=6, padx=(0, 10))
        self.total_marks_var = tk.IntVar(value=50)
        tk.Spinbox(fields_frame, from_=10, to=200, textvariable=self.total_marks_var,
                   font=FONT, bg=LIGHT, relief="flat", width=10).grid(row=2, column=1, sticky="w", pady=6)

        tk.Label(fields_frame, text="Duration (min)", font=FONT_BOLD, bg=WHITE).grid(row=2, column=2, sticky="w", pady=6, padx=(0, 10))
        self.duration_var = tk.IntVar(value=90)
        tk.Spinbox(fields_frame, from_=30, to=300, textvariable=self.duration_var,
                   font=FONT, bg=LIGHT, relief="flat", width=10).grid(row=2, column=3, sticky="w", pady=6)

        # ── FIX 1: Marks per question type ──────────────────
        marks_frame = tk.Frame(scroll_frame, bg=WHITE, padx=20, pady=15)
        marks_frame.pack(fill="x", pady=5)
        tk.Label(marks_frame, text="Question Counts & Marks per Question",
                 font=FONT_BOLD, bg=WHITE).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 8))

        tk.Label(marks_frame, text="MCQ Count", font=FONT, bg=WHITE).grid(row=1, column=0, sticky="w", padx=(0, 5))
        self.mcq_count_var = tk.IntVar(value=10)
        tk.Spinbox(marks_frame, from_=0, to=50, textvariable=self.mcq_count_var,
                   font=FONT, bg=LIGHT, relief="flat", width=6).grid(row=1, column=1, padx=5)
        tk.Label(marks_frame, text="Marks each", font=("Segoe UI", 9), bg=WHITE, fg="#666").grid(row=1, column=2, sticky="w")
        self.mcq_marks_var = tk.IntVar(value=1)
        tk.Spinbox(marks_frame, from_=1, to=10, textvariable=self.mcq_marks_var,
                   font=FONT, bg=LIGHT, relief="flat", width=5).grid(row=1, column=3, padx=5)

        tk.Label(marks_frame, text="Short Count", font=FONT, bg=WHITE).grid(row=2, column=0, sticky="w", padx=(0, 5), pady=6)
        self.short_count_var = tk.IntVar(value=5)
        tk.Spinbox(marks_frame, from_=0, to=30, textvariable=self.short_count_var,
                   font=FONT, bg=LIGHT, relief="flat", width=6).grid(row=2, column=1, padx=5)
        tk.Label(marks_frame, text="Marks each", font=("Segoe UI", 9), bg=WHITE, fg="#666").grid(row=2, column=2, sticky="w")
        self.short_marks_var = tk.IntVar(value=4)
        tk.Spinbox(marks_frame, from_=1, to=20, textvariable=self.short_marks_var,
                   font=FONT, bg=LIGHT, relief="flat", width=5).grid(row=2, column=3, padx=5)

        tk.Label(marks_frame, text="Long Count", font=FONT, bg=WHITE).grid(row=3, column=0, sticky="w", padx=(0, 5))
        self.long_count_var = tk.IntVar(value=2)
        tk.Spinbox(marks_frame, from_=0, to=10, textvariable=self.long_count_var,
                   font=FONT, bg=LIGHT, relief="flat", width=6).grid(row=3, column=1, padx=5)
        tk.Label(marks_frame, text="Marks each", font=("Segoe UI", 9), bg=WHITE, fg="#666").grid(row=3, column=2, sticky="w")
        self.long_marks_var = tk.IntVar(value=10)
        tk.Spinbox(marks_frame, from_=1, to=30, textvariable=self.long_marks_var,
                   font=FONT, bg=LIGHT, relief="flat", width=5).grid(row=3, column=3, padx=5)

        # Live total marks preview
        self.calc_label = tk.Label(marks_frame, text="", font=FONT_BOLD, bg=WHITE, fg=ACCENT)
        self.calc_label.grid(row=4, column=0, columnspan=6, sticky="w", pady=(8, 0))

        def update_calc(*args):
            try:
                total = (self.mcq_count_var.get() * self.mcq_marks_var.get() +
                         self.short_count_var.get() * self.short_marks_var.get() +
                         self.long_count_var.get() * self.long_marks_var.get())
                self.calc_label.config(text=f"📊 Calculated Total: {total} marks")
            except: pass

        for var in [self.mcq_count_var, self.mcq_marks_var, self.short_count_var,
                    self.short_marks_var, self.long_count_var, self.long_marks_var]:
            var.trace("w", update_calc)
        update_calc()

        # Difficulty ratio
        diff_frame = tk.Frame(scroll_frame, bg=WHITE, padx=20, pady=15)
        diff_frame.pack(fill="x", pady=5)
        tk.Label(diff_frame, text="Difficulty Ratio", font=FONT_BOLD, bg=WHITE).pack(side="left", padx=(0, 10))
        tk.Label(diff_frame, text="Easy%", font=FONT, bg=WHITE).pack(side="left")
        self.easy_var = tk.IntVar(value=40)
        tk.Spinbox(diff_frame, from_=0, to=100, textvariable=self.easy_var, font=FONT, bg=LIGHT, relief="flat", width=5).pack(side="left", padx=3)
        tk.Label(diff_frame, text="Med%", font=FONT, bg=WHITE).pack(side="left")
        self.med_var = tk.IntVar(value=40)
        tk.Spinbox(diff_frame, from_=0, to=100, textvariable=self.med_var, font=FONT, bg=LIGHT, relief="flat", width=5).pack(side="left", padx=3)
        tk.Label(diff_frame, text="Hard%", font=FONT, bg=WHITE).pack(side="left")
        self.hard_var = tk.IntVar(value=20)
        tk.Spinbox(diff_frame, from_=0, to=100, textvariable=self.hard_var, font=FONT, bg=LIGHT, relief="flat", width=5).pack(side="left", padx=3)

        # Units
        units_frame = tk.Frame(scroll_frame, bg=WHITE, padx=20, pady=15)
        units_frame.pack(fill="x", pady=5)
        tk.Label(units_frame, text="Select Units to Cover", font=FONT_BOLD, bg=WHITE).pack(anchor="w")
        self.unit_vars = {}
        self.units_container = tk.Frame(units_frame, bg=WHITE)
        self.units_container.pack(fill="x", pady=5)

        def refresh_units(*args):
            for w in self.units_container.winfo_children(): w.destroy()
            self.unit_vars = {}
            for u in get_units(self.subject_var.get()):
                var = tk.BooleanVar(value=True)
                self.unit_vars[u] = var
                tk.Checkbutton(self.units_container, text=u, variable=var,
                               font=FONT, bg=WHITE).pack(side="left", padx=10)

        self.subject_var.trace("w", refresh_units)
        refresh_units()

        tk.Button(scroll_frame, text="🔍  PREVIEW & GENERATE", font=FONT_BOLD,
                  bg=ACCENT, fg=WHITE, relief="flat", pady=12, padx=30,
                  cursor="hand2", command=self.generate_paper).pack(pady=10)

        self.status_label = tk.Label(scroll_frame, text="", font=FONT, bg=BG, fg="green")
        self.status_label.pack()

    def generate_paper(self):
        subject = self.subject_var.get()
        if not subject:
            messagebox.showerror("Error", "Please select a subject.")
            return
        selected_units = [u for u, v in self.unit_vars.items() if v.get()]
        if not selected_units:
            messagebox.showerror("Error", "Please select at least one unit.")
            return

        difficulty_ratio = {"Easy": self.easy_var.get(), "Medium": self.med_var.get(), "Hard": self.hard_var.get()}

        # FIX 1: Pass marks per type to engine
        questions = select_questions(
            subject, selected_units, difficulty_ratio,
            self.mcq_count_var.get(), self.short_count_var.get(), self.long_count_var.get(),
            mcq_marks=self.mcq_marks_var.get(),
            short_marks=self.short_marks_var.get(),
            long_marks=self.long_marks_var.get()
        )

        if not questions:
            messagebox.showerror("Error", "No questions found. Use AI Generate to create questions first!")
            return

        # Marks validation warning
        actual_marks = sum(q['marks'] for q in questions)
        expected_marks = self.total_marks_var.get()
        if actual_marks != expected_marks:
            diff = actual_marks - expected_marks
            direction = f"exceeds by {diff}" if diff > 0 else f"is short by {abs(diff)}"
            msg = (f"Warning: Calculated marks ({actual_marks}) {direction} mark(s) "
                   f"compared to your Total Marks setting ({expected_marks}).\n\n"
                   f"This usually happens due to rounding in difficulty ratio.\n\n"
                   f"Do you want to proceed with {actual_marks} marks?")
            proceed = messagebox.askyesno("Marks Mismatch", msg)
            if not proceed:
                return

        config = {
            "college_name": self.college_var.get(),
            "subject": subject,
            "exam_type": self.exam_type_var.get(),
            "total_marks": actual_marks,
            "duration": self.duration_var.get(),
            "date": datetime.now().strftime("%d-%m-%Y"),
            "units": selected_units,
        }

        # FIX 2: Show preview before generating PDF
        self.assistant.speak(f"Preview ready. {len(questions)} questions selected. Review and click Generate PDF.")
        PreviewWindow(self.root, questions, config, self.finalize_paper)

    def finalize_paper(self, questions, config):
        """Called after user confirms preview — saves PDF."""
        filename = f"QuestionPaper_{config['subject']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        save_path = filedialog.asksaveasfilename(defaultextension=".pdf",
                                                  filetypes=[("PDF files", "*.pdf")],
                                                  initialfile=filename)
        if not save_path:
            return

        generate_pdf(save_path, config, questions)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO generated_papers (subject, exam_type, total_marks, duration, generated_on, filename)
                          VALUES (?, ?, ?, ?, ?, ?)''',
                       (config['subject'], config['exam_type'], config['total_marks'], config['duration'],
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), os.path.basename(save_path)))
        conn.commit()
        conn.close()

        self.status_label.config(text=f"✅ Paper saved! Marks: {config['total_marks']}, Questions: {len(questions)}")
        # FIX 5: Detailed confirmation speak
        mcq_c  = len([q for q in questions if q['question_type'] == 'MCQ'])
        sht_c  = len([q for q in questions if q['question_type'] == 'Short'])
        lng_c  = len([q for q in questions if q['question_type'] == 'Long'])
        self.assistant.speak(
            f"Question paper saved successfully! "
            f"{mcq_c} multiple choice, {sht_c} short answer, and {lng_c} long answer questions. "
            f"Total marks: {config['total_marks']}."
        )
        messagebox.showinfo("Success", f"Question paper saved!\n{save_path}")

    # ── QUESTION BANK ────────────────────────────────────────
    def show_question_bank(self, announce=True):
        self.clear_content()
        self.page_title("Question Bank", "View, edit and manage all questions")
        if announce:
            self.assistant.speak_interrupt("Question Bank. Showing all stored questions.")

        toolbar = tk.Frame(self.content, bg=BG)
        toolbar.pack(fill="x", padx=20, pady=5)
        tk.Label(toolbar, text="Filter:", font=FONT, bg=BG).pack(side="left")
        self.filter_subject_var = tk.StringVar(value="All")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT subject FROM questions")
        subjects = ["All"] + [r[0] for r in cursor.fetchall()]
        conn.close()
        filter_cb = ttk.Combobox(toolbar, textvariable=self.filter_subject_var,
                                  values=subjects, state="readonly", font=FONT, width=15)
        filter_cb.pack(side="left", padx=5)
        filter_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_question_table())

        # FIX 3: Edit button for all users
        tk.Button(toolbar, text="✏️ Edit Selected", font=FONT, bg=ACCENT, fg=WHITE,
                  relief="flat", padx=10, pady=5, cursor="hand2",
                  command=self.edit_question).pack(side="left", padx=5)

        if self.user[3] == "admin":
            tk.Button(toolbar, text="🗑 Delete Selected", font=FONT, bg="#c0392b", fg=WHITE,
                      relief="flat", padx=10, pady=5, cursor="hand2",
                      command=self.delete_question).pack(side="left", padx=5)

        cols = ("ID", "Subject", "Unit", "Type", "Bloom's Level", "Difficulty", "Marks", "Question")
        tree_frame = tk.Frame(self.content, bg=BG)
        tree_frame.pack(fill="both", expand=True, padx=20, pady=10)
        self.q_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=20)
        for col, w in zip(cols, [40, 80, 70, 60, 90, 70, 50, 300]):
            self.q_tree.heading(col, text=col)
            self.q_tree.column(col, width=w, minwidth=w)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.q_tree.yview)
        self.q_tree.configure(yscrollcommand=scrollbar.set)
        self.q_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.q_tree.bind("<Double-Button-1>", lambda e: self.edit_question())  # Double click to edit
        self.refresh_question_table()

    def refresh_question_table(self):
        for row in self.q_tree.get_children(): self.q_tree.delete(row)
        conn = get_connection()
        cursor = conn.cursor()
        subject = self.filter_subject_var.get()
        if subject == "All":
            cursor.execute("SELECT id, subject, unit, question_type, COALESCE(blooms_level,'—'), difficulty, marks, question_text FROM questions")
        else:
            cursor.execute("SELECT id, subject, unit, question_type, COALESCE(blooms_level,'—'), difficulty, marks, question_text FROM questions WHERE subject=?", (subject,))
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            self.q_tree.insert("", "end", values=row)

    def edit_question(self):
        """FIX 3: Open edit dialog for selected question."""
        selected = self.q_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a question to edit.")
            return
        q_id = self.q_tree.item(selected[0])['values'][0]
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions WHERE id=?", (q_id,))
        row = cursor.fetchone()
        columns = [desc[0] for desc in cursor.description]
        conn.close()
        if row:
            q_data = dict(zip(columns, row))
            EditQuestionDialog(self.root, q_data, self.refresh_question_table)

    def delete_question(self):
        selected = self.q_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a question to delete.")
            return
        if messagebox.askyesno("Confirm", "Delete selected question?"):
            q_id = self.q_tree.item(selected[0])['values'][0]
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM questions WHERE id=?", (q_id,))
            conn.commit()
            conn.close()
            # FIX 5: Confirmation with remaining count
            conn2 = get_connection()
            cur2 = conn2.cursor()
            cur2.execute("SELECT COUNT(*) FROM questions")
            remaining = cur2.fetchone()[0]
            conn2.close()
            self.assistant.speak(f"Question deleted. {remaining} questions remaining in the bank.")
            self.refresh_question_table()

    # ── HISTORY ─────────────────────────────────────────────
    def show_history(self, announce=True):
        self.clear_content()
        self.page_title("Generated Papers History")
        if announce:
            self.assistant.speak_interrupt("History screen. Showing all previously generated question papers.")
        cols = ("ID", "Subject", "Exam Type", "Total Marks", "Duration", "Generated On", "Filename")
        frame = tk.Frame(self.content, bg=BG)
        frame.pack(fill="both", expand=True, padx=20, pady=10)
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=20)
        for col, w in zip(cols, [40, 80, 120, 90, 80, 140, 200]):
            tree.heading(col, text=col)
            tree.column(col, width=w)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM generated_papers ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            tree.insert("", "end", values=row)

    def logout(self):
        self.assistant.speak("Logging out. Goodbye!")
        self.root.destroy()
        login_root = tk.Tk()
        LoginWindow(login_root)
        login_root.mainloop()


# ─── ENTRY POINT ────────────────────────────────────────────
if __name__ == "__main__":
    initialize_db()
    seed_sample_questions()
    root = tk.Tk()
    LoginWindow(root)
    root.mainloop()