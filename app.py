import io
import json
import os
import re
import sqlite3
from datetime import datetime
from functools import wraps
from html import escape
from html.parser import HTMLParser
from pathlib import Path

import docx
import PyPDF2
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

# Render's filesystem is ephemeral by default. Set MM_DB_PATH to a persistent
# disk path such as /var/data/magnolia_margin.db in production.
DB_PATH = os.environ.get(
    "MM_DB_PATH",
    os.path.join(app.instance_path, "magnolia_margin.db"),
)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

ALLOWED_HTML_TAGS = {
    "p",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "strike",
    "br",
    "blockquote",
    "ul",
    "ol",
    "li",
    "a",
}
BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "li"}
WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'’-]{2,}\b")
SENTENCE_RE = re.compile(r"[^.!?\n]+(?:[.!?]+|$)")
PASSIVE_RE = re.compile(
    r"\b(?:am|is|are|was|were|be|been|being|get|gets|got|gotten)"
    r"\s+(?:\w+\s+){0,3}\w+(?:ed|en)\b",
    re.IGNORECASE,
)
STOP_WORDS = {
    "about", "after", "again", "against", "almost", "also", "although", "always",
    "among", "and", "another", "any", "around", "because", "before", "being",
    "between", "both", "but", "could", "did", "does", "doing", "down", "during",
    "each", "even", "every", "few", "first", "for", "from", "further", "had",
    "has", "have", "having", "here", "hers", "him", "himself", "his", "how",
    "into", "its", "itself", "just", "many", "might", "more", "most", "much",
    "must", "myself", "never", "not", "now", "off", "once", "only", "other",
    "our", "ours", "ourselves", "out", "over", "same", "she", "should", "some",
    "such", "than", "that", "their", "theirs", "them", "themselves", "then",
    "there", "these", "they", "this", "those", "through", "too", "under",
    "until", "very", "was", "were", "what", "when", "where", "which", "while",
    "who", "whom", "why", "will", "with", "would", "you", "your", "yours",
}


class Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag not in ALLOWED_HTML_TAGS:
            return

        if tag == "a":
            href = ""
            for key, value in attrs:
                if key.lower() == "href" and value:
                    href = value.strip()
            if href.startswith(("https://", "http://", "mailto:")):
                self.parts.append(f'<a href="{escape(href, quote=True)}" target="_blank" rel="noopener">')
            else:
                self.parts.append("<a>")
            return

        self.parts.append(f"<{tag}>")

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if tag == "br":
            self.parts.append("<br>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ALLOWED_HTML_TAGS and tag not in {"br"}:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(escape(data))


def sanitize_html(value):
    parser = Sanitizer()
    parser.feed(value or "")
    parser.close()
    return "".join(parser.parts).strip()


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.last_block = False

    def _newline(self):
        if self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_starttag(self, tag, attrs):
        if tag.lower() in BLOCK_TAGS:
            self._newline()

    def handle_endtag(self, tag):
        if tag.lower() in BLOCK_TAGS:
            self._newline()

    def handle_data(self, data):
        self.parts.append(data)

    def handle_entityref(self, name):
        self.parts.append(f"&{name};")

    def handle_charref(self, name):
        self.parts.append(f"&#{name};")


def html_to_text(content):
    parser = TextExtractor()
    parser.feed(content or "")
    parser.close()
    value = "".join(parser.parts).replace("\xa0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    return value.strip()


def text_to_html(text):
    paragraphs = re.split(r"\n\s*\n", (text or "").strip())
    paragraphs = paragraphs if paragraphs != [""] else [""]
    return "".join(
        f"<p>{escape(paragraph).replace(chr(10), '<br>')}</p>"
        for paragraph in paragraphs
    )


def inline_docx_run(run):
    text = escape(run.text or "").replace("\n", "<br>")
    if not text:
        return ""
    if run.bold:
        text = f"<strong>{text}</strong>"
    if run.italic:
        text = f"<em>{text}</em>"
    if run.underline:
        text = f"<u>{text}</u>"
    return text


def docx_to_html(raw_bytes):
    document = docx.Document(io.BytesIO(raw_bytes))
    blocks = []

    for paragraph in document.paragraphs:
        parts = [inline_docx_run(run) for run in paragraph.runs]
        body = "".join(parts)
        if not body:
            body = "<br>"

        style_name = (paragraph.style.name if paragraph.style else "") or ""
        heading = re.search(r"Heading\s+([1-6])", style_name, flags=re.IGNORECASE)

        if heading:
            tag = f"h{heading.group(1)}"
            blocks.append(f"<{tag}>{body}</{tag}>")
        elif "List Bullet" in style_name:
            blocks.append(f"<ul><li>{body}</li></ul>")
        elif "List Number" in style_name:
            blocks.append(f"<ol><li>{body}</li></ol>")
        elif style_name.lower().startswith("quote") or "intense quote" in style_name.lower():
            blocks.append(f"<blockquote>{body}</blockquote>")
        else:
            blocks.append(f"<p>{body}</p>")

    return "".join(blocks)


def pdf_to_text(raw_bytes):
    reader = PyPDF2.PdfReader(io.BytesIO(raw_bytes))
    pages = []
    for page in reader.pages:
        value = page.extract_text() or ""
        if value.strip():
            pages.append(value.strip())
    return "\n\n".join(pages)


def parse_uploaded_file(file_storage):
    filename = (file_storage.filename or "").strip()
    lower = filename.lower()
    raw = file_storage.read()

    if lower.endswith(".txt"):
        text = raw.decode("utf-8-sig", errors="replace")
        return filename, text_to_html(text)
    if lower.endswith(".docx"):
        return filename, docx_to_html(raw)
    if lower.endswith(".pdf"):
        return filename, text_to_html(pdf_to_text(raw))

    raise ValueError("Unsupported file type. Please use .txt, .docx, or .pdf.")


def sentence_spans(text):
    spans = []
    for match in SENTENCE_RE.finditer(text):
        snippet = match.group(0).strip()
        if snippet:
            leading = len(match.group(0)) - len(match.group(0).lstrip())
            trailing_end = len(match.group(0).rstrip())
            spans.append(
                (
                    match.start() + leading,
                    match.start() + trailing_end,
                    snippet,
                )
            )
    return spans


def analyze_text(text):
    text = text or ""
    if not text.strip():
        return {"words": [], "passive": [], "pacing": [], "flagged_count": 0}

    sentences = sentence_spans(text)
    counts = {}
    occurrence_map = {}

    for match in WORD_RE.finditer(text):
        raw = match.group(0)
        normalized = raw.lower().replace("’", "'").strip("'")
        if not normalized or normalized in STOP_WORDS or len(normalized) < 4:
            continue
        counts[normalized] = counts.get(normalized, 0) + 1
        occurrence_map.setdefault(normalized, []).append(
            {"start": match.start(), "end": match.end()}
        )

    words = []
    for word, count in counts.items():
        if count < 3:
            continue

        contexts = []
        for start, end in occurrence_map[word][:5]:
            sentence = next(
                (
                    snippet
                    for s_start, s_end, snippet in sentences
                    if s_start <= start <= s_end or s_start <= end <= s_end
                ),
                "",
            )
            if sentence and sentence not in contexts:
                contexts.append(sentence)

        words.append(
            {
                "word": word,
                "count": count,
                "occurrences": occurrence_map[word],
                "contexts": contexts,
            }
        )

    words.sort(key=lambda item: (-item["count"], item["word"]))

    passive = []
    for start, end, snippet in sentences:
        if PASSIVE_RE.search(snippet):
            passive.append(
                {
                    "sentence": snippet,
                    "start": start,
                    "end": end,
                    "reason": "Possible passive construction",
                }
            )

    pacing = []
    short_run = []
    for index, (start, end, snippet) in enumerate(sentences):
        word_count = len(WORD_RE.findall(snippet))
        if word_count > 35:
            pacing.append(
                {
                    "sentence": snippet,
                    "start": start,
                    "end": end,
                    "reason": "Long sentence",
                    "word_count": word_count,
                }
            )

        if word_count <= 7:
            short_run.append((start, end, snippet, word_count))
        else:
            if len(short_run) >= 3:
                for run_start, run_end, run_snippet, run_count in short_run:
                    pacing.append(
                        {
                            "sentence": run_snippet,
                            "start": run_start,
                            "end": run_end,
                            "reason": "Choppy sequence",
                            "word_count": run_count,
                        }
                    )
            short_run = []

        if index == len(sentences) - 1 and len(short_run) >= 3:
            for run_start, run_end, run_snippet, run_count in short_run:
                pacing.append(
                    {
                        "sentence": run_snippet,
                        "start": run_start,
                        "end": run_end,
                        "reason": "Choppy sequence",
                        "word_count": run_count,
                    }
                )

    flagged_count = sum(item["count"] - 1 for item in words)
    flagged_count += len(passive) + len(pacing)

    return {
        "words": words[:80],
        "passive": passive[:120],
        "pacing": pacing[:120],
        "flagged_count": flagged_count,
    }


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                user_id INTEGER PRIMARY KEY,
                content TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                source_filename TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                analysis_json TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        legacy_users = db.execute("SELECT id FROM users").fetchall()
        for user in legacy_users:
            exists = db.execute(
                "SELECT id FROM projects WHERE user_id = ? LIMIT 1",
                (user["id"],),
            ).fetchone()
            if exists:
                continue

            legacy = db.execute(
                "SELECT content FROM documents WHERE user_id = ?",
                (user["id"],),
            ).fetchone()
            legacy_content = legacy["content"] if legacy else ""
            db.execute(
                """
                INSERT INTO projects (user_id, title, content)
                VALUES (?, ?, ?)
                """,
                (user["id"], "My manuscript", sanitize_html(legacy_content)),
            )

        db.commit()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with get_db() as db:
        return db.execute(
            "SELECT id, email FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login_page"))
        return view(*args, **kwargs)

    return wrapped


def api_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return jsonify({"error": "Authentication required."}), 401
        return view(*args, **kwargs)

    return wrapped


def project_for_user(project_id, user_id):
    with get_db() as db:
        return db.execute(
            """
            SELECT id, user_id, title, source_filename, content,
                   analysis_json, created_at, updated_at
            FROM projects
            WHERE id = ? AND user_id = ?
            """,
            (project_id, user_id),
        ).fetchone()


def project_payload(row, include_content=False):
    payload = {
        "id": row["id"],
        "title": row["title"],
        "source_filename": row["source_filename"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_content:
        payload["content"] = row["content"]
        payload["analysis"] = json.loads(row["analysis_json"] or "{}")
    return payload


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
        user = db.execute(
            "SELECT id, email, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        if action == "register":
            if user:
                return jsonify(
                    {"error": "An account with that email already exists. Please sign in."}
                ), 409

            cursor = db.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, generate_password_hash(password)),
            )
            user_id = cursor.lastrowid
            db.execute(
                """
                INSERT INTO projects (user_id, title, content)
                VALUES (?, ?, '')
                """,
                (user_id, "Untitled manuscript"),
            )
            db.commit()

            session.clear()
            session["user_id"] = user_id
            session["email"] = email
            return jsonify(
                {"status": "success", "message": "Account created successfully."}
            )

        if action == "login":
            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = user["id"]
                session["email"] = user["email"]
                return jsonify(
                    {"status": "success", "message": "Logged in successfully."}
                )
            return jsonify({"error": "Invalid email or password."}), 401

    return jsonify({"error": "Unknown authentication action."}), 400


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "success"})


@app.route("/api/projects", methods=["GET"])
@api_login_required
def list_projects():
    user = current_user()
    with get_db() as db:
        rows = db.execute(
            """
            SELECT id, title, source_filename, created_at, updated_at
            FROM projects
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (user["id"],),
        ).fetchall()
    return jsonify({"projects": [project_payload(row) for row in rows]})


@app.route("/api/projects", methods=["POST"])
@api_login_required
def create_project():
    user = current_user()
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "Untitled manuscript").strip()[:160]
    if not title:
        title = "Untitled manuscript"

    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO projects (user_id, title, content)
            VALUES (?, ?, '')
            """,
            (user["id"], title),
        )
        db.commit()
        row = db.execute(
            """
            SELECT id, title, source_filename, created_at, updated_at
            FROM projects WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return jsonify({"project": project_payload(row, include_content=True)}), 201


@app.route("/api/projects/<int:project_id>", methods=["GET"])
@api_login_required
def get_project(project_id):
    user = current_user()
    row = project_for_user(project_id, user["id"])
    if not row:
        return jsonify({"error": "Project not found."}), 404
    return jsonify({"project": project_payload(row, include_content=True)})


@app.route("/api/projects/<int:project_id>", methods=["POST"])
@api_login_required
def save_project(project_id):
    user = current_user()
    row = project_for_user(project_id, user["id"])
    if not row:
        return jsonify({"error": "Project not found."}), 404

    data = request.get_json(silent=True) or {}
    content = sanitize_html(data.get("content", row["content"]))
    title = (data.get("title") or row["title"]).strip()[:160] or "Untitled manuscript"
    analysis = data.get("analysis")
    analysis_json = (
        json.dumps(analysis, ensure_ascii=False)
        if isinstance(analysis, dict)
        else row["analysis_json"]
    )

    with get_db() as db:
        db.execute(
            """
            UPDATE projects
            SET title = ?, content = ?, analysis_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (title, content, analysis_json, project_id, user["id"]),
        )
        db.commit()

    return jsonify({"status": "success", "updated_at": datetime.utcnow().isoformat()})


@app.route("/api/projects/<int:project_id>", methods=["DELETE"])
@api_login_required
def delete_project(project_id):
    user = current_user()
    row = project_for_user(project_id, user["id"])
    if not row:
        return jsonify({"error": "Project not found."}), 404

    with get_db() as db:
        total = db.execute(
            "SELECT COUNT(*) AS count FROM projects WHERE user_id = ?",
            (user["id"],),
        ).fetchone()["count"]
        if total <= 1:
            return jsonify(
                {"error": "Keep at least one project in your writing room."}
            ), 400
        db.execute(
            "DELETE FROM projects WHERE id = ? AND user_id = ?",
            (project_id, user["id"]),
        )
        db.commit()

    return jsonify({"status": "success"})


@app.route("/api/projects/import", methods=["POST"])
@api_login_required
def import_project():
    user = current_user()
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "Choose a manuscript file first."}), 400

    try:
        filename, content = parse_uploaded_file(file)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Failed to read the manuscript: {exc}"}), 500

    content = sanitize_html(content)
    title = Path(filename).stem.strip()[:160] or "Imported manuscript"

    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO projects (user_id, title, source_filename, content)
            VALUES (?, ?, ?, ?)
            """,
            (user["id"], title, filename, content),
        )
        db.commit()
        row = db.execute(
            """
            SELECT id, title, source_filename, content, analysis_json, created_at, updated_at
            FROM projects WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return jsonify({"project": project_payload(row, include_content=True)}), 201


@app.route("/api/projects/<int:project_id>/analyze", methods=["POST"])
@api_login_required
def analyze_project(project_id):
    user = current_user()
    row = project_for_user(project_id, user["id"])
    if not row:
        return jsonify({"error": "Project not found."}), 404

    data = request.get_json(silent=True) or {}
    text = data.get("text")
    if text is None:
        text = html_to_text(row["content"])

    analysis = analyze_text(text)
    with get_db() as db:
        db.execute(
            """
            UPDATE projects
            SET analysis_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (json.dumps(analysis, ensure_ascii=False), project_id, user["id"]),
        )
        db.commit()

    return jsonify(analysis)


def html_to_docx(content):
    class DocumentBuilder(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.document = docx.Document()
            self.paragraph = None
            self.heading_level = None
            self.list_level = 0
            self.bold = False
            self.italic = False
            self.underline = False
            self.strike = False

        def ensure_paragraph(self, style=None):
            if self.paragraph is None:
                self.paragraph = self.document.add_paragraph()
                if style:
                    self.paragraph.style = style
            return self.paragraph

        def finish_paragraph(self):
            self.paragraph = None
            self.heading_level = None

        def handle_starttag(self, tag, attrs):
            tag = tag.lower()
            if tag in {"p", "div", "blockquote"}:
                self.finish_paragraph()
                style = "Intense Quote" if tag == "blockquote" else None
                self.ensure_paragraph(style)
            elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                self.finish_paragraph()
                self.heading_level = int(tag[1])
                self.ensure_paragraph(f"Heading {self.heading_level}")
            elif tag == "li":
                self.finish_paragraph()
                self.ensure_paragraph("List Bullet")
            elif tag == "strong" or tag == "b":
                self.bold = True
            elif tag == "em" or tag == "i":
                self.italic = True
            elif tag == "u":
                self.underline = True
            elif tag in {"s", "strike"}:
                self.strike = True

        def handle_endtag(self, tag):
            tag = tag.lower()
            if tag in {"p", "div", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "li"}:
                self.finish_paragraph()
            elif tag == "strong" or tag == "b":
                self.bold = False
            elif tag == "em" or tag == "i":
                self.italic = False
            elif tag == "u":
                self.underline = False
            elif tag in {"s", "strike"}:
                self.strike = False

        def handle_startendtag(self, tag, attrs):
            if tag.lower() == "br":
                paragraph = self.ensure_paragraph()
                paragraph.add_run().add_break()

        def handle_data(self, data):
            if not data:
                return
            paragraph = self.ensure_paragraph()
            run = paragraph.add_run(data)
            run.bold = self.bold
            run.italic = self.italic
            run.underline = self.underline
            run.font.strike = self.strike

    builder = DocumentBuilder()
    builder.feed(content or "")
    builder.close()
    if not builder.document.paragraphs:
        builder.document.add_paragraph("")
    output = io.BytesIO()
    builder.document.save(output)
    output.seek(0)
    return output


@app.route("/api/projects/<int:project_id>/export/<fmt>", methods=["GET"])
@api_login_required
def export_project(project_id, fmt):
    user = current_user()
    row = project_for_user(project_id, user["id"])
    if not row:
        return jsonify({"error": "Project not found."}), 404

    safe_title = re.sub(r"[^A-Za-z0-9._-]+", "_", row["title"]).strip("_") or "manuscript"
    html_document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{escape(row["title"])}</title>
<style>
body {{ background: #f7f5f2; color: #171411; font-family: Georgia, serif; max-width: 860px; margin: 50px auto; padding: 0 30px; line-height: 1.8; }}
h1, h2, h3, h4, h5, h6 {{ color: #3f3027; }}
blockquote {{ border-left: 3px solid #c0ab9a; padding-left: 18px; color: #7b5c4b; }}
</style>
</head>
<body>{row["content"]}</body>
</html>"""

    if fmt == "html":
        return app.response_class(
            html_document,
            mimetype="text/html",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_title}.html"'
            },
        )

    if fmt == "txt":
        payload = html_to_text(row["content"]).encode("utf-8")
        return send_file(
            io.BytesIO(payload),
            mimetype="text/plain; charset=utf-8",
            as_attachment=True,
            download_name=f"{safe_title}.txt",
        )

    if fmt == "docx":
        payload = html_to_docx(row["content"])
        return send_file(
            payload,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True,
            download_name=f"{safe_title}.docx",
        )

    return jsonify({"error": "Unknown export format."}), 400


# Backwards-compatible analyze endpoint for older clients.
@app.route("/analyze", methods=["POST"])
@api_login_required
def legacy_analyze():
    if "file" in request.files and request.files["file"].filename:
        try:
            _, content = parse_uploaded_file(request.files["file"])
            text = html_to_text(content)
        except Exception as exc:
            return jsonify({"error": f"Failed to read file: {exc}"}), 500
    else:
        text = request.form.get("text", "")
    return jsonify(analyze_text(text))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
