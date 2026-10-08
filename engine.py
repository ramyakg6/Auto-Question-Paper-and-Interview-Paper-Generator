import random
from database import get_connection


def select_questions(subject, units, difficulty_ratio, mcq_count, short_count, long_count,
                     mcq_marks=1, short_marks=4, long_marks=10):
    """
    Selects questions from the database based on given parameters.
    Returns a list of question dicts.
    """
    conn = get_connection()
    cursor = conn.cursor()
    selected = []
    used_ids = set()

    marks_map = {"MCQ": mcq_marks, "Short": short_marks, "Long": long_marks}

    def fetch_questions(q_type, difficulty, count):
        if count <= 0:
            return []
        placeholders = ','.join('?' for _ in units)
        cursor.execute(f'''
            SELECT * FROM questions
            WHERE subject=? AND question_type=? AND difficulty=? AND unit IN ({placeholders})
        ''', [subject, q_type, difficulty] + units)
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        questions = [dict(zip(cols, row)) for row in rows if row[0] not in used_ids]
        random.shuffle(questions)
        chosen = questions[:count]
        for q in chosen:
            used_ids.add(q['id'])
        return chosen

    def fill_remaining(q_type, count):
        if count <= 0:
            return []
        placeholders = ','.join('?' for _ in units)
        cursor.execute(f'''
            SELECT * FROM questions
            WHERE subject=? AND question_type=? AND unit IN ({placeholders})
        ''', [subject, q_type] + units)
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        extras = [dict(zip(cols, row)) for row in rows if row[0] not in used_ids]
        random.shuffle(extras)
        chosen = extras[:count]
        for q in chosen:
            used_ids.add(q['id'])
        return chosen

    def split_by_difficulty(count, ratio):
        easy   = int(count * ratio.get("Easy", 0) / 100)
        hard   = int(count * ratio.get("Hard", 0) / 100)
        medium = count - easy - hard  # absorbs remainder, always sums to count
        return {"Easy": easy, "Medium": max(0, medium), "Hard": hard}

    for q_type, count in [("MCQ", mcq_count), ("Short", short_count), ("Long", long_count)]:
        if count == 0:
            continue
        split = split_by_difficulty(count, difficulty_ratio)
        type_selected = []
        for difficulty, d_count in split.items():
            if d_count > 0:
                type_selected.extend(fetch_questions(q_type, difficulty, d_count))

        # Fallback if not enough questions found
        if len(type_selected) < count:
            type_selected.extend(fill_remaining(q_type, count - len(type_selected)))

        # Apply faculty-specified marks
        for q in type_selected:
            q['marks'] = marks_map[q_type]

        selected.extend(type_selected)

    conn.close()

    actual_marks = sum(q['marks'] for q in selected)
    print(f"[Engine] Selected {len(selected)} questions, Total marks: {actual_marks}")
    return selected


def validate_marks(questions, total_marks):
    """Check if selected questions total marks match expected total."""
    actual = sum(q['marks'] for q in questions)
    return actual, actual == total_marks