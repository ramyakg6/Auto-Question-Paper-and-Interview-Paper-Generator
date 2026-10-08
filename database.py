import sqlite3
import os

DB_PATH = "question_paper.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'faculty'))
        )
    ''')

    # Questions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            unit TEXT NOT NULL,
            question_text TEXT NOT NULL,
            question_type TEXT NOT NULL CHECK(question_type IN ('MCQ', 'Short', 'Long')),
            difficulty TEXT NOT NULL CHECK(difficulty IN ('Easy', 'Medium', 'Hard')),
            marks INTEGER NOT NULL,
            option_a TEXT,
            option_b TEXT,
            option_c TEXT,
            option_d TEXT,
            answer TEXT
        )
    ''')

    # Generated papers history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS generated_papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            exam_type TEXT NOT NULL,
            total_marks INTEGER NOT NULL,
            duration INTEGER NOT NULL,
            generated_on TEXT NOT NULL,
            filename TEXT NOT NULL
        )
    ''')

    # Default admin user
    cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)",
                   ("admin", "admin123", "admin"))
    cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)",
                   ("faculty", "faculty123", "faculty"))

    conn.commit()
    conn.close()
    print("[DB] Database initialized successfully.")


def seed_sample_questions():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM questions")
    count = cursor.fetchone()[0]
    if count > 0:
        conn.close()
        return

    questions = [
        # Python - Unit 1 - Easy MCQ
        ("Python", "Unit 1", "What is the output of print(type([]))?", "MCQ", "Easy", 1,
         "<class 'list'>", "<class 'tuple'>", "<class 'dict'>", "<class 'set'>", "A"),
        ("Python", "Unit 1", "Which keyword is used to define a function in Python?", "MCQ", "Easy", 1,
         "func", "def", "function", "define", "B"),
        ("Python", "Unit 1", "What does len() function return?", "MCQ", "Easy", 1,
         "Sum of elements", "Number of elements", "Last element", "First element", "B"),
        ("Python", "Unit 1", "Which of the following is a mutable data type?", "MCQ", "Easy", 1,
         "Tuple", "String", "List", "Integer", "C"),
        ("Python", "Unit 1", "What is the correct file extension for Python files?", "MCQ", "Easy", 1,
         ".pt", ".pyt", ".py", ".python", "C"),

        # Python - Unit 1 - Medium Short
        ("Python", "Unit 1", "Explain the difference between list and tuple in Python.", "Short", "Medium", 4,
         None, None, None, None, None),
        ("Python", "Unit 1", "What are Python decorators? Give an example.", "Short", "Medium", 4,
         None, None, None, None, None),
        ("Python", "Unit 1", "Explain list comprehension with an example.", "Short", "Medium", 4,
         None, None, None, None, None),

        # Python - Unit 1 - Hard Long
        ("Python", "Unit 1", "Explain Object Oriented Programming concepts in Python with examples.", "Long", "Hard", 10,
         None, None, None, None, None),
        ("Python", "Unit 1", "Write a Python program to implement a stack using a list.", "Long", "Hard", 10,
         None, None, None, None, None),

        # Python - Unit 2 - Easy MCQ
        ("Python", "Unit 2", "Which module is used for regular expressions in Python?", "MCQ", "Easy", 1,
         "regex", "re", "regexp", "rx", "B"),
        ("Python", "Unit 2", "What does the 'pass' statement do in Python?", "MCQ", "Easy", 1,
         "Exits the loop", "Does nothing", "Skips iteration", "Returns None", "B"),
        ("Python", "Unit 2", "Which function converts a string to integer?", "MCQ", "Easy", 1,
         "str()", "float()", "int()", "num()", "C"),
        ("Python", "Unit 2", "What is the default return value of a function with no return statement?", "MCQ", "Easy", 1,
         "0", "False", "None", "Empty string", "C"),
        ("Python", "Unit 2", "Which operator is used for floor division?", "MCQ", "Easy", 1,
         "/", "%", "//", "**", "C"),

        # Python - Unit 2 - Medium Short
        ("Python", "Unit 2", "Explain exception handling in Python with try, except, finally.", "Short", "Medium", 4,
         None, None, None, None, None),
        ("Python", "Unit 2", "What are lambda functions? How are they different from regular functions?", "Short", "Medium", 4,
         None, None, None, None, None),
        ("Python", "Unit 2", "Explain file handling operations in Python.", "Short", "Medium", 4,
         None, None, None, None, None),

        # Python - Unit 2 - Hard Long
        ("Python", "Unit 2", "Explain multithreading in Python with a suitable example program.", "Long", "Hard", 10,
         None, None, None, None, None),
        ("Python", "Unit 2", "Write a Python program to read a CSV file and display its contents using pandas.", "Long", "Hard", 10,
         None, None, None, None, None),

        # DBMS - Unit 1 - Easy MCQ
        ("DBMS", "Unit 1", "What does DBMS stand for?", "MCQ", "Easy", 1,
         "Data Base Monitoring System", "Database Management System", "Data Backup Management System", "None", "B"),
        ("DBMS", "Unit 1", "Which of the following is a DDL command?", "MCQ", "Easy", 1,
         "SELECT", "INSERT", "CREATE", "UPDATE", "C"),
        ("DBMS", "Unit 1", "What is a primary key?", "MCQ", "Easy", 1,
         "A key that can be null", "A key that uniquely identifies a record", "A foreign key", "A composite key", "B"),
        ("DBMS", "Unit 1", "Which normal form removes partial dependencies?", "MCQ", "Easy", 1,
         "1NF", "2NF", "3NF", "BCNF", "B"),
        ("DBMS", "Unit 1", "SQL stands for?", "MCQ", "Easy", 1,
         "Structured Query Language", "Simple Query Language", "Standard Query Language", "Sequential Query Language", "A"),

        # DBMS - Unit 1 - Medium Short
        ("DBMS", "Unit 1", "Explain the different types of keys in a relational database.", "Short", "Medium", 4,
         None, None, None, None, None),
        ("DBMS", "Unit 1", "What is normalization? Explain 1NF and 2NF.", "Short", "Medium", 4,
         None, None, None, None, None),
        ("DBMS", "Unit 1", "Differentiate between DELETE, DROP and TRUNCATE commands.", "Short", "Medium", 4,
         None, None, None, None, None),

        # DBMS - Unit 1 - Hard Long
        ("DBMS", "Unit 1", "Explain the ER model and how it is converted to a relational schema.", "Long", "Hard", 10,
         None, None, None, None, None),
        ("DBMS", "Unit 1", "Explain transaction management and ACID properties with examples.", "Long", "Hard", 10,
         None, None, None, None, None),

        # DBMS - Unit 2 - Easy MCQ
        ("DBMS", "Unit 2", "Which JOIN returns all records from both tables?", "MCQ", "Easy", 1,
         "INNER JOIN", "LEFT JOIN", "FULL OUTER JOIN", "CROSS JOIN", "C"),
        ("DBMS", "Unit 2", "What is a view in SQL?", "MCQ", "Easy", 1,
         "A physical table", "A virtual table", "A stored procedure", "An index", "B"),
        ("DBMS", "Unit 2", "Which aggregate function returns the number of rows?", "MCQ", "Easy", 1,
         "SUM()", "AVG()", "COUNT()", "MAX()", "C"),
        ("DBMS", "Unit 2", "What is a stored procedure?", "MCQ", "Easy", 1,
         "A query saved as a view", "A precompiled set of SQL statements", "A trigger", "An index", "B"),
        ("DBMS", "Unit 2", "Which clause is used to filter groups in SQL?", "MCQ", "Easy", 1,
         "WHERE", "HAVING", "GROUP BY", "ORDER BY", "B"),

        # DBMS - Unit 2 - Medium Short
        ("DBMS", "Unit 2", "Explain indexing in databases and its advantages.", "Short", "Medium", 4,
         None, None, None, None, None),
        ("DBMS", "Unit 2", "What are triggers in SQL? Give an example.", "Short", "Medium", 4,
         None, None, None, None, None),
        ("DBMS", "Unit 2", "Explain the concept of concurrency control in DBMS.", "Short", "Medium", 4,
         None, None, None, None, None),

        # DBMS - Unit 2 - Hard Long
        ("DBMS", "Unit 2", "Explain different types of joins with examples and SQL queries.", "Long", "Hard", 10,
         None, None, None, None, None),
        ("DBMS", "Unit 2", "Explain deadlock in DBMS and the methods used to handle it.", "Long", "Hard", 10,
         None, None, None, None, None),
    ]

    cursor.executemany('''
        INSERT INTO questions (subject, unit, question_text, question_type, difficulty, marks,
        option_a, option_b, option_c, option_d, answer)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', questions)

    conn.commit()
    conn.close()
    print("[DB] Sample questions seeded successfully.")