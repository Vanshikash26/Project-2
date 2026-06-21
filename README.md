# Library Management System

A role-based library system where Members browse and borrow books, and
Librarians manage inventory and process returns — including **automatic
late-fine calculation**, the kind of real business logic interviewers
love to ask about.

This is a classic, instantly-recognizable project for resumes targeting
Software Developer / Junior Developer roles at any company.

---

## Features

- **Authentication** with securely hashed passwords
- **Two roles:**
  - **Member** — browse/search books, borrow available copies, view
    personal borrow history with due dates
  - **Librarian** — add/remove books, view all active borrows, mark
    books as returned (auto-calculates late fines)
- **Relational database design** — `books`, `users`, and `borrow_records`
  tables connected via foreign keys (a classic many-to-many-through-a-
  junction-table pattern)
- **Business logic:** 14-day borrow period, ₹5/day late fine,
  automatically calculated when a librarian marks a book returned
- **Search** books by title or author
- **Pre-seeded** with 5 sample books so the app isn't empty on first run

---

## How to Run

```bash
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000**

### Try it out:

1. Register as a **Member** (leave the signup code blank)
2. Register as a **Librarian** (type `LIBRARIAN2026` as the signup code)
3. Log in as the Member — browse the seeded books, borrow one
4. Log out, log in as the Librarian — see the active borrow, mark it returned
5. (If returned before the 14-day due date, no fine. If you want to test
   the fine logic, you'd need to wait — or, for a demo, mention in your
   interview that you tested this by manually adjusting a due date in the
   database to simulate an overdue scenario.)

---

## The Business Logic (Practice Explaining This)

```python
def calculate_fine(due_date_str, return_datetime):
    due_date = datetime.fromisoformat(due_date_str)
    if return_datetime > due_date:
        days_late = (return_datetime - due_date).days
        return days_late * FINE_PER_DAY
    return 0
```

This is a small but real piece of business logic — exactly the kind of
thing interviewers ask you to "walk me through your code" on. Be ready
to explain: why we compare dates, how `timedelta` gives us a day count,
and what would break if `due_date` were stored as the wrong data type.

---

## Sample Resume Bullet Points

```
Library Management System | Python, Flask, SQLite, Werkzeug
- Designed a relational database schema (books, users, borrow_records)
  with foreign key relationships to model real-world borrowing behavior.
- Implemented role-based access (Member/Librarian) with secure
  authentication and session management.
- Built automated due-date tracking and late-fine calculation logic,
  reducing manual tracking effort for library staff.
- Added search functionality to filter books by title or author.
```

## Likely Interview Questions (Practice These)

- "Walk me through your database schema — why three tables?"
  → Books and Users are separate entities; borrow_records is a
  junction table linking them, because one book can be borrowed many
  times and one user can borrow many books (many-to-many relationship).
- "What happens if two members try to borrow the last copy at the same
  time?" → Honest answer: this simple version doesn't fully handle
  race conditions — a production system would use database transactions
  or row locking. (Mentioning this awareness is actually a GOOD sign to
  an interviewer — it shows you understand the limitation.)
- "Why hash passwords instead of encrypting them?" → Hashing is one-way;
  even if the database is leaked, passwords can't be reversed. Encryption
  is reversible and not appropriate for password storage.

---

## Tech Stack

- **Backend:** Python, Flask
- **Database:** SQLite (3 tables with foreign key relationships)
- **Security:** Werkzeug password hashing, Flask sessions
- **Frontend:** HTML, CSS, Jinja2 templating

---

## Possible Future Improvements (mention in interviews — shows depth)

- Email/SMS reminder before due date
- Book reservation system (queue if all copies are borrowed)
- Pagination for large book catalogs
- Export borrow history as PDF/CSV report
- Handle concurrent borrow requests safely (database transactions)
