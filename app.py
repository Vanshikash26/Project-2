"""
app.py
------
Library Management System — demonstrates relational database design
(foreign keys, joins) and real business logic (due dates, fine calculation),
on top of the authentication/RBAC pattern from the Helpdesk project.

Two roles:
- Member:     can search/browse books and borrow available ones
- Librarian:  can add/remove books and process returns (which calculates
              a late fine automatically if the book is overdue)

How to run:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000
"""

import sqlite3
import functools
from datetime import datetime, timedelta

from flask import Flask, request, redirect, url_for, render_template, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-secret-key-before-deploying"

DB_FILE = "library.db"

LIBRARIAN_SIGNUP_CODE = "LIBRARIAN2026"
BORROW_DURATION_DAYS = 14
FINE_PER_DAY = 5  # rupees per day late


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member'
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            category TEXT NOT NULL,
            total_copies INTEGER NOT NULL DEFAULT 1,
            available_copies INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    # A borrow_record links a book to the user who borrowed it.
    # This is a classic "many-to-many through a junction table" pattern --
    # a book can be borrowed many times, a user can borrow many books.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS borrow_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            borrowed_at TEXT NOT NULL,
            due_date TEXT NOT NULL,
            returned_at TEXT,
            fine_amount INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (book_id) REFERENCES books (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )

    conn.commit()

    # Seed a few books so the app isn't empty on first run
    existing = cursor.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    if existing == 0:
        sample_books = [
            ("Clean Code", "Robert C. Martin", "Programming", 3, 3),
            ("The Pragmatic Programmer", "David Thomas", "Programming", 2, 2),
            ("Atomic Habits", "James Clear", "Self-Help", 4, 4),
            ("Sapiens", "Yuval Noah Harari", "History", 2, 2),
            ("Wings of Fire", "A.P.J. Abdul Kalam", "Biography", 3, 3),
        ]
        cursor.executemany(
            "INSERT INTO books (title, author, category, total_copies, available_copies) VALUES (?, ?, ?, ?, ?)",
            sample_books,
        )
        conn.commit()

    conn.close()


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def login_required(view_func):
    @functools.wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped


def librarian_required(view_func):
    @functools.wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "librarian":
            flash("Only librarians can do that.")
            return redirect(url_for("dashboard"))
        return view_func(*args, **kwargs)
    return wrapped


def calculate_fine(due_date_str, return_datetime):
    """
    Core business logic: if a book is returned after its due date,
    charge FINE_PER_DAY for every day late. This is the kind of small
    calculation interviewers love asking you to walk through.
    """
    due_date = datetime.fromisoformat(due_date_str)
    if return_datetime > due_date:
        days_late = (return_datetime - due_date).days
        # if returned a few hours late on the same day it's still "1 day late"
        if (return_datetime - due_date).seconds > 0 and days_late == 0:
            days_late = 1
        return days_late * FINE_PER_DAY
    return 0


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        signup_code = request.form.get("signup_code", "").strip()

        if not username or not password:
            flash("Username and password are required.")
            return redirect(url_for("register"))

        role = "librarian" if signup_code == LIBRARIAN_SIGNUP_CODE else "member"
        password_hash = generate_password_hash(password)

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, password_hash, role),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            flash("That username is already taken.")
            return redirect(url_for("register"))
        finally:
            conn.close()

        flash("Account created! Please log in.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]

        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    search = request.args.get("search", "").strip()

    if search:
        books = conn.execute(
            "SELECT * FROM books WHERE title LIKE ? OR author LIKE ? ORDER BY title",
            (f"%{search}%", f"%{search}%"),
        ).fetchall()
    else:
        books = conn.execute("SELECT * FROM books ORDER BY title").fetchall()

    if session["role"] == "member":
        # A member's own borrow history, joined with book details so we
        # can show the title instead of just a book_id number.
        my_borrows = conn.execute(
            """
            SELECT borrow_records.*, books.title, books.author
            FROM borrow_records
            JOIN books ON borrow_records.book_id = books.id
            WHERE borrow_records.user_id = ?
            ORDER BY borrow_records.borrowed_at DESC
            """,
            (session["user_id"],),
        ).fetchall()
        conn.close()
        now_str = datetime.now().isoformat(timespec="seconds")
        return render_template("dashboard.html", books=books, my_borrows=my_borrows, search=search, now=now_str)

    else:  # librarian
        active_borrows = conn.execute(
            """
            SELECT borrow_records.*, books.title AS book_title, users.username
            FROM borrow_records
            JOIN books ON borrow_records.book_id = books.id
            JOIN users ON borrow_records.user_id = users.id
            WHERE borrow_records.returned_at IS NULL
            ORDER BY borrow_records.due_date ASC
            """
        ).fetchall()
        conn.close()
        now_str = datetime.now().isoformat(timespec="seconds")
        return render_template("dashboard.html", books=books, active_borrows=active_borrows, search=search, now=now_str)


@app.route("/books/add", methods=["POST"])
@librarian_required
def add_book():
    title = request.form["title"].strip()
    author = request.form["author"].strip()
    category = request.form["category"].strip()
    copies = int(request.form["copies"])

    conn = get_db()
    conn.execute(
        "INSERT INTO books (title, author, category, total_copies, available_copies) VALUES (?, ?, ?, ?, ?)",
        (title, author, category, copies, copies),
    )
    conn.commit()
    conn.close()

    flash(f'Book "{title}" added to the library.')
    return redirect(url_for("dashboard"))


@app.route("/books/<int:book_id>/delete", methods=["POST"])
@librarian_required
def delete_book(book_id):
    conn = get_db()
    conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()
    flash("Book removed from the library.")
    return redirect(url_for("dashboard"))


@app.route("/borrow/<int:book_id>", methods=["POST"])
@login_required
def borrow_book(book_id):
    if session["role"] != "member":
        flash("Only members can borrow books.")
        return redirect(url_for("dashboard"))

    conn = get_db()
    book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()

    if book is None or book["available_copies"] <= 0:
        flash("This book is not available right now.")
        conn.close()
        return redirect(url_for("dashboard"))

    now = datetime.now()
    due_date = now + timedelta(days=BORROW_DURATION_DAYS)

    conn.execute(
        "INSERT INTO borrow_records (book_id, user_id, borrowed_at, due_date) VALUES (?, ?, ?, ?)",
        (book_id, session["user_id"], now.isoformat(timespec="seconds"), due_date.isoformat(timespec="seconds")),
    )
    conn.execute(
        "UPDATE books SET available_copies = available_copies - 1 WHERE id = ?",
        (book_id,),
    )
    conn.commit()
    conn.close()

    flash(f'You borrowed "{book["title"]}". Due back on {due_date.strftime("%d %b %Y")}.')
    return redirect(url_for("dashboard"))


@app.route("/return/<int:record_id>", methods=["POST"])
@librarian_required
def return_book(record_id):
    conn = get_db()
    record = conn.execute("SELECT * FROM borrow_records WHERE id = ?", (record_id,)).fetchone()

    if record is None or record["returned_at"] is not None:
        flash("Invalid borrow record.")
        conn.close()
        return redirect(url_for("dashboard"))

    now = datetime.now()
    fine = calculate_fine(record["due_date"], now)

    conn.execute(
        "UPDATE borrow_records SET returned_at = ?, fine_amount = ? WHERE id = ?",
        (now.isoformat(timespec="seconds"), fine, record_id),
    )
    conn.execute(
        "UPDATE books SET available_copies = available_copies + 1 WHERE id = ?",
        (record["book_id"],),
    )
    conn.commit()
    conn.close()

    if fine > 0:
        flash(f"Book returned. Late fine charged: Rs.{fine}")
    else:
        flash("Book returned on time. No fine.")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="127.0.0.1", port=5000)
