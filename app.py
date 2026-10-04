import io
import os
import sqlite3
from functools import wraps

import docx
import PyPDF2
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Use an environment secret in production. The fallback keeps local development simple.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

# Render's filesystem is ephemeral by default. Point MM_DB_PATH at a persistent disk
# (for example /var/data/magnolia_margin.db) or use DATABASE_URL in a future migration.
DB_PATH = os.environ.get("MM_DB_PATH", os.path.join(app.instance_path, "magnolia_margin.db"))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                user_id INTEGER PRIMARY KEY,
                content TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        db.commit()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with get_db() as db:
        return db.execute("SELECT id, email FROM users WHERE id = ?", (user_id,)).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login_page"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login/")
@app.route("/login")
def login_page():
    if current_user():
        return redirect(url_for("editor"))
    return render_template("login.html")


@app.route("/editor/")
@app.route("/editor")
@login_required
def editor():
    user = current_user()
    return render_template("editor.html", email=user["email"])


@app.route("/auth", methods=["POST"])
def auth():
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    action = data.get("action", "login")

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    if len(password) < 8:
        return jsonify({"error": "Your password must be at least 8 characters."}), 400

    with get_db() as db:
        user = db.execute("SELECT id, email, password_hash FROM users WHERE email = ?", (email,)).fetchone()

        if action == "register":
            if user:
                return jsonify({"error": "An account with that email already exists. Please sign in."}), 409

            password_hash = generate_password_hash(password)
            cursor = db.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, password_hash),
            )
            user_id = cursor.lastrowid
            db.execute("INSERT INTO documents (user_id, content) VALUES (?, '')", (user_id,))
            db.commit()

            session.clear()
            session["user_id"] = user_id
            session["email"] = email
            return jsonify({"status": "success", "message": "Account created successfully."})

        if action == "login":
            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = user["id"]
                session["email"] = user["email"]
                return jsonify({"status": "success", "message": "Logged in successfully."})
            return jsonify({"error": "Invalid email or password."}), 401

    return jsonify({"error": "Unknown authentication action."}), 400


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "success"})


@app.route("/analyze", methods=["POST"])
@login_required
def analyze():
    text = ""

    if "file" in request.files and request.files["file"].filename != "":
        file = request.files["file"]
        filename = file.filename.lower()

        try:
            if filename.endswith(".txt"):
                text = file.read().decode("utf-8")
            elif filename.endswith(".docx"):
                file_stream = io.BytesIO(file.read())
                doc = docx.Document(file_stream)
                text = "\n".join(para.text for para in doc.paragraphs)
            elif filename.endswith(".pdf"):
                file_stream = io.BytesIO(file.read())
                pdf_reader = PyPDF2.PdfReader(file_stream)
                for page in pdf_reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + " "
            else:
                return jsonify({"error": "Unsupported file type. Please use .txt, .docx, or .pdf"}), 400
        except Exception as exc:
            return jsonify({"error": f"Failed to read file: {str(exc)}"}), 500
    else:
        text = request.form.get("text", "")

    if not text.strip():
        return jsonify({"words": [], "passive": [], "pacing": [], "flagged_count": 0})

    # Placeholder for NLP processing logic.
    return jsonify({"words": [], "passive": [], "pacing": []})


@app.route("/save", methods=["POST"])
@login_required
def save_progress():
    data = request.get_json(silent=True) or {}
    content = data.get("content", "")
    user = current_user()

    with get_db() as db:
        db.execute(
            """
            INSERT INTO documents (user_id, content, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                content = excluded.content,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user["id"], content),
        )
        db.commit()

    return jsonify({"status": "success"})


@app.route("/load", methods=["GET"])
@login_required
def load_progress():
    user = current_user()
    with get_db() as db:
        row = db.execute("SELECT content FROM documents WHERE user_id = ?", (user["id"],)).fetchone()
    return jsonify({"content": row["content"] if row else ""})


init_db()

if __name__ == "__main__":
    app.run(debug=True)
