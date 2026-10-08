from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file, flash
import os, json, re, random, threading
from datetime import datetime
from werkzeug.utils import secure_filename

# ── Import shared modules instead of duplicating logic ────────
from database import get_connection, initialize_db, seed_sample_questions
from engine import select_questions
from ai_generator import (
    extract_text_from_file,
    clean_extracted_text,
    is_duplicate,
    generate_questions_with_ai,
    blooms_to_difficulty
)

app = Flask(__name__)
app.secret_key = "aqpg_secret_key_2024"
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ── Auth helpers ─────────────────────────────────────────────
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ── Auth ─────────────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "").strip()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p))
        user = cursor.fetchone()
        conn.close()
        if user:
            session["user"] = {
                "id": user[0], "username": user[1],
                "password": user[2], "role": user[3]
            }
            return redirect(url_for("dashboard"))
        error = "Invalid username or password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Dashboard ────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_connection()
    cursor = conn.cursor()
    total_q = cursor.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    total_p = cursor.execute("SELECT COUNT(*) FROM generated_papers").fetchone()[0]
    subjects = [r[0] for r in cursor.execute("SELECT DISTINCT subject FROM questions").fetchall()]
    recent   = cursor.execute("SELECT * FROM generated_papers ORDER BY id DESC LIMIT 5").fetchall()
    conn.close()
    return render_template("dashboard.html",
        total_q=total_q, total_p=total_p,
        subjects=subjects, recent=recent)


# ── Generate Paper ───────────────────────────────────────────
@app.route("/generate", methods=["GET", "POST"])
@login_required
def generate():
    conn = get_connection()
    cursor = conn.cursor()
    subjects = [r[0] for r in cursor.execute("SELECT DISTINCT subject FROM questions").fetchall()]
    conn.close()
    return render_template("generate.html", subjects=subjects)


@app.route("/api/units/<subject>")
@login_required
def get_units(subject):
    conn = get_connection()
    cursor = conn.cursor()
    units = [r[0] for r in cursor.execute(
        "SELECT DISTINCT unit FROM questions WHERE subject=?", (subject,)).fetchall()]
    conn.close()
    return jsonify(units)


@app.route("/api/question_stats/<subject>")
@login_required
def get_question_stats(subject):
    """Return per-unit and overall counts broken down by question type and difficulty."""
    conn = get_connection()
    cursor = conn.cursor()
    rows = cursor.execute("""
        SELECT unit, question_type, difficulty, COUNT(*) as cnt
        FROM questions
        WHERE subject=?
        GROUP BY unit, question_type, difficulty
        ORDER BY unit, question_type, difficulty
    """, (subject,)).fetchall()
    conn.close()

    # Build structure: { unit: { type: { difficulty: count, _total: n }, _total: n }, _overall: {...} }
    stats = {}
    overall = {"MCQ": 0, "Short": 0, "Long": 0, "total": 0}
    for unit, qtype, diff, cnt in rows:
        if unit not in stats:
            stats[unit] = {"MCQ": {}, "Short": {}, "Long": {}, "_totals": {"MCQ": 0, "Short": 0, "Long": 0}}
        if qtype in stats[unit]:
            stats[unit][qtype][diff] = cnt
            stats[unit]["_totals"][qtype] = stats[unit]["_totals"].get(qtype, 0) + cnt
        if qtype in overall:
            overall[qtype] += cnt
            overall["total"] += cnt
    return jsonify({"units": stats, "overall": overall})


@app.route("/api/select_questions", methods=["POST"])
@login_required
def api_select_questions():
    data        = request.json
    subject     = data.get("subject")
    units       = data.get("units", [])
    mcq_count   = int(data.get("mcq_count", 0))
    short_count = int(data.get("short_count", 0))
    long_count  = int(data.get("long_count", 0))
    mcq_marks   = int(data.get("mcq_marks", 1))
    short_marks = int(data.get("short_marks", 4))
    long_marks  = int(data.get("long_marks", 10))
    easy_pct    = int(data.get("easy_pct", 40))
    med_pct     = int(data.get("med_pct", 40))
    hard_pct    = int(data.get("hard_pct", 20))

    if not subject or not units:
        return jsonify({"error": "Subject and units are required."}), 400

    difficulty_ratio = {"Easy": easy_pct, "Medium": med_pct, "Hard": hard_pct}

    # Use engine.py's select_questions — no duplicated logic
    questions = select_questions(
        subject, units, difficulty_ratio,
        mcq_count, short_count, long_count,
        mcq_marks=mcq_marks, short_marks=short_marks, long_marks=long_marks
    )

    # Convert to plain dicts for JSON serialisation
    questions_list = [dict(q) if not isinstance(q, dict) else q for q in questions]
    expected_count = mcq_count + short_count + long_count
    return jsonify({
        "questions": questions_list,
        "total_marks": sum(q["marks"] for q in questions_list),
        "selected_count": len(questions_list),
        "expected_count": expected_count,
    })


@app.route("/api/generate_pdf", methods=["POST"])
@login_required
def api_generate_pdf():
    from pdf_generator import generate_pdf

    data      = request.json
    config    = data.get("config", {})
    questions = data.get("questions", [])

    if not questions:
        return jsonify({"error": "No questions provided."}), 400

    filename = f"QuestionPaper_{config.get('subject','X')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    # Use pdf_generator.py — no duplicated ReportLab code
    generate_pdf(filepath, config, questions)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO generated_papers (subject,exam_type,total_marks,duration,generated_on,filename) VALUES (?,?,?,?,?,?)",
        (config.get("subject"), config.get("exam_type"), config.get("total_marks"),
         config.get("duration"), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), filename)
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "filename": filename, "url": f"/static/uploads/{filename}"})


# ── AI Generate ──────────────────────────────────────────────
@app.route("/ai_generate")
@login_required
def ai_generate():
    return render_template("ai_generate.html")


@app.route("/api/ai_generate", methods=["POST"])
@login_required
def api_ai_generate():
    api_key   = request.form.get("api_key", "").strip()
    subject   = request.form.get("subject", "").strip()
    unit      = request.form.get("unit", "").strip()
    levels    = request.form.getlist("levels")
    mcq_per   = int(request.form.get("mcq_per", 5))
    short_per = int(request.form.get("short_per", 2))
    long_per  = int(request.form.get("long_per", 1))
    file      = request.files.get("topic_file")

    if not api_key:
        return jsonify({"error": "Groq API key is required."}), 400
    if not file or not subject or not unit:
        return jsonify({"error": "Missing required fields (file, subject, unit)."}), 400
    if not levels:
        return jsonify({"error": "Please select at least one Bloom's level."}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    # Use ai_generator.py's extract — handles PDF/DOCX/TXT with table text too
    text = extract_text_from_file(filepath)
    if text.startswith("[ERROR]") or len(text.strip()) < 50:
        return jsonify({"error": "Could not extract text. Try a TXT file."}), 400

    # Use ai_generator.py's generate — includes cleaning + dedup (the missing fix)
    questions = generate_questions_with_ai(
        text, subject, unit, levels,
        mcq_per, short_per, long_per, api_key
    )

    if not questions:
        return jsonify({"error": "No questions generated. Check your API key and file content."}), 400

    # Save with dedup check against existing DB questions
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT question_text FROM questions")
    existing_in_db = [{"question_text": row[0]} for row in cursor.fetchall()]

    saved   = 0
    skipped = 0
    for q in questions:
        if is_duplicate(q, existing_in_db, threshold=0.80):
            skipped += 1
            continue
        try:
            cursor.execute('''
                INSERT INTO questions
                (subject, unit, question_text, question_type, difficulty, marks,
                 option_a, option_b, option_c, option_d, answer, blooms_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (subject, unit, q.get("question_text", ""),
                 q.get("question_type", "MCQ"),
                 blooms_to_difficulty(q.get("blooms_level", "Remember")),
                 q.get("marks", 1), q.get("option_a"), q.get("option_b"),
                 q.get("option_c"), q.get("option_d"), q.get("answer"),
                 q.get("blooms_level", "Remember"))
            )
            existing_in_db.append({"question_text": q.get("question_text", "")})
            saved += 1
        except Exception as e:
            print(f"[DB] Insert error: {e}")

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "saved": saved,
        "skipped": skipped,
        "questions": questions
    })


# ── Question Bank ────────────────────────────────────────────
@app.route("/question_bank")
@login_required
def question_bank():
    conn       = get_connection()
    cursor     = conn.cursor()
    subjects   = ["All"] + [r[0] for r in cursor.execute("SELECT DISTINCT subject FROM questions").fetchall()]
    filter_sub = request.args.get("subject", "All")
    if filter_sub == "All":
        rows = cursor.execute("SELECT * FROM questions ORDER BY id DESC").fetchall()
    else:
        rows = cursor.execute(
            "SELECT * FROM questions WHERE subject=? ORDER BY id DESC", (filter_sub,)).fetchall()
    conn.close()
    # Convert rows to dicts for the template
    questions = [dict(zip([
        "id","subject","unit","question_text","question_type",
        "difficulty","marks","option_a","option_b","option_c","option_d","answer","blooms_level"
    ], r)) for r in rows]
    return render_template("question_bank.html",
        questions=questions, subjects=subjects, filter_sub=filter_sub)


@app.route("/api/delete_question/<int:q_id>", methods=["DELETE"])
@login_required
def delete_question(q_id):
    if session["user"]["role"] != "admin":
        return jsonify({"error": "Admin only"}), 403
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM questions WHERE id=?", (q_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/delete_questions_bulk", methods=["POST"])
@login_required
def delete_questions_bulk():
    if session["user"]["role"] != "admin":
        return jsonify({"error": "Admin only"}), 403
    ids = request.json.get("ids", [])
    if not ids:
        return jsonify({"success": False, "error": "No IDs provided"}), 400
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executemany("DELETE FROM questions WHERE id=?", [(i,) for i in ids])
    conn.commit()
    conn.close()
    return jsonify({"success": True, "deleted": len(ids)})


@app.route("/api/edit_question/<int:q_id>", methods=["PUT"])
@login_required
def edit_question(q_id):
    data = request.json
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE questions SET question_text=?, question_type=?, difficulty=?,
        marks=?, option_a=?, option_b=?, option_c=?, option_d=?, answer=?
        WHERE id=?''',
        (data.get("question_text"), data.get("question_type"), data.get("difficulty"),
         data.get("marks"), data.get("option_a"), data.get("option_b"),
         data.get("option_c"), data.get("option_d"), data.get("answer"), q_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ── History ──────────────────────────────────────────────────
@app.route("/history")
@login_required
def history():
    conn = get_connection()
    cursor = conn.cursor()
    papers = cursor.execute("SELECT * FROM generated_papers ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("history.html", papers=papers)




# ── Voice Assistant ───────────────────────────────────────────
@app.route("/api/voice_command", methods=["POST"])
@login_required
def voice_command():
    data = request.json or {}
    text = data.get("text", "").lower().strip()

    COMMANDS = {
        # Navigation
        "dashboard":        ("redirect", "/dashboard",     "Opening Dashboard"),
        "home":             ("redirect", "/dashboard",     "Going to Dashboard"),
        "generate paper":   ("redirect", "/generate",      "Opening Generate Paper"),
        "generate":         ("redirect", "/generate",      "Opening Generate Paper"),
        "create paper":     ("redirect", "/generate",      "Opening Generate Paper"),
        "ai generate":      ("redirect", "/ai_generate",   "Opening AI Generate"),
        "ai":               ("redirect", "/ai_generate",   "Opening AI Generate"),
        "question bank":    ("redirect", "/question_bank", "Opening Question Bank"),
        "bank":             ("redirect", "/question_bank", "Opening Question Bank"),
        "history":          ("redirect", "/history",       "Opening History"),
        "show history":     ("redirect", "/history",       "Opening History"),
        "logout":           ("redirect", "/logout",        "Logging you out"),
        "log out":          ("redirect", "/logout",        "Logging you out"),
        "sign out":         ("redirect", "/logout",        "Logging you out"),
        # Info
        "help":             ("speak",    None, "You can say: dashboard, generate paper, AI generate, question bank, history, or logout."),
        "what can you do":  ("speak",    None, "I can navigate pages. Try saying: go to dashboard, generate paper, question bank, or history."),
        "commands":         ("speak",    None, "Available commands: dashboard, generate paper, AI generate, question bank, history, logout."),
        "who are you":      ("speak",    None, "I am your question paper assistant. Say help to hear what I can do."),
        "hello":            ("speak",    None, "Hello! How can I help? Say help for available commands."),
        "hi":               ("speak",    None, "Hi there! Say help for available commands."),
    }

    for phrase, (action, url, message) in COMMANDS.items():
        if phrase in text:
            return jsonify({"action": action, "url": url, "message": message})

    return jsonify({
        "action": "speak",
        "url": None,
        "message": "Sorry, I didn't understand that. Say help for available commands."
    })

# ── Entry point ──────────────────────────────────────────────
if __name__ == "__main__":
    initialize_db()
    seed_sample_questions()
    app.run(debug=True, port=5000)