import io
import json
import os
import re
import zipfile
from datetime import datetime
from functools import wraps
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from lxml import etree
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
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    inspect,
    select,
    text as sql_text,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
    elif DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
else:
    DB_PATH = os.environ.get(
        "MM_DB_PATH",
        os.path.join(app.instance_path, "magnolia_margin.db"),
    )
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    DATABASE_URL = "sqlite:///" + DB_PATH

engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite:"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()

PROJECT_DOMAIN = os.environ.get("PROJECT_DOMAIN", "").strip().lower().rstrip(".")
PROJECT_SUBDOMAIN_PREFIX = os.environ.get("PROJECT_SUBDOMAIN_PREFIX", "").strip().lower()
if PROJECT_DOMAIN:
    app.config.update(
        SESSION_COOKIE_DOMAIN="." + PROJECT_DOMAIN,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
else:
    app.config.update(
        SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER")),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(320), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP"))

    projects = relationship(
        "Project",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("user_id", "slug", name="uq_project_user_slug"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    slug = Column(String(180), nullable=True)
    source_filename = Column(String(255), nullable=False, default="")
    content = Column(Text, nullable=False, default="")
    analysis_json = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=sql_text("CURRENT_TIMESTAMP"),
    )

    user = relationship("User", back_populates="projects")


ALLOWED_HTML_TAGS = {
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "b", "em", "i", "u", "s", "strike", "br",
    "blockquote", "ul", "ol", "li", "a", "hr", "span", "mark",
}
BLOCK_TAGS = {
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "li", "hr",
}
WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'’-]{2,}\b")
SENTENCE_RE = re.compile(r"[^.!?\n]+(?:[.!?]+|$)")
PASSIVE_RE = re.compile(
    r"\b(?:am|is|are|was|were|be|been|being|get|gets|got|gotten)"
    r"\s+\w+(?:\s+\w+){0,3}\s+(?:ed|en)\b",
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


def slugify(value, fallback="project"):
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:150] or fallback


def unique_slug(db, user_id, title, project_id=None):
    base = slugify(title)
    candidate = base
    n = 2
    while True:
        query = select(Project.id).where(
            Project.user_id == user_id,
            Project.slug == candidate,
        )
        if project_id:
            query = query.where(Project.id != project_id)
        if db.execute(query).first() is None:
            return candidate
        candidate = f"{base}-{n}"
        n += 1


def project_host_slug():
    if not PROJECT_DOMAIN:
        return None
    host = request.host.split(":", 1)[0].lower()
    suffix = "." + PROJECT_DOMAIN
    if not host.endswith(suffix):
        return None
    prefix = host[: -len(suffix)]
    if PROJECT_SUBDOMAIN_PREFIX:
        expected = PROJECT_SUBDOMAIN_PREFIX + "-"
        if not prefix.startswith(expected):
            return None
        prefix = prefix[len(expected):]
    if re.fullmatch(r"[a-z0-9-]{1,150}", prefix):
        return prefix
    return None


def project_link(project):
    if PROJECT_DOMAIN:
        prefix = (PROJECT_SUBDOMAIN_PREFIX + "-") if PROJECT_SUBDOMAIN_PREFIX else ""
        return f"https://{prefix}{project.slug}.{PROJECT_DOMAIN}/"
    return url_for("project_editor", slug=project.slug)


class Sanitizer(HTMLParser):
    SAFE_STYLE_PROPERTIES = {
        "color", "background-color", "font-size", "text-align",
        "font-family", "letter-spacing", "margin-left", "margin-right",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def safe_style(self, style):
        safe = []
        for declaration in (style or "").split(";"):
            if ":" not in declaration:
                continue
            name, value = declaration.split(":", 1)
            name = name.strip().lower()
            value = value.strip()
            if name not in self.SAFE_STYLE_PROPERTIES:
                continue
            if re.fullmatch(r"(?:#[0-9a-f]{3,8}|[a-zA-Z ]+|[0-9.]+(?:px|pt|em|rem|%)?)", value):
                safe.append(f"{name}:{value}")
        return ";".join(safe)

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
                self.parts.append(
                    f'<a href="{escape(href, quote=True)}" target="_blank" rel="noopener">'
                )
            else:
                self.parts.append("<a>")
            return

        if tag == "span":
            styles = ""
            for key, value in attrs:
                if key.lower() == "style":
                    styles = self.safe_style(value)
            if styles:
                self.parts.append(f'<span style="{escape(styles, quote=True)}">')
            else:
                self.parts.append("<span>")
            return

        if tag in {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6"}:
            styles = ""
            for key, value in attrs:
                if key.lower() == "style":
                    styles = self.safe_style(value)
            self.parts.append(f"<{tag}{(' style=' + chr(34) + escape(styles, quote=True) + chr(34)) if styles else ''}>")
            return

        self.parts.append(f"<{tag}>")

    def handle_startendtag(self, tag, attrs):
        if tag.lower() == "br":
            self.parts.append("<br>")
        elif tag.lower() == "hr":
            self.parts.append("<hr>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ALLOWED_HTML_TAGS and tag not in {"br", "hr"}:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(escape(data))


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

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


def sanitize_html(value):
    parser = Sanitizer()
    parser.feed(value or "")
    parser.close()
    return "".join(parser.parts).strip()


def html_to_text(content):
    parser = TextExtractor()
    parser.feed(content or "")
    parser.close()
    value = "".join(parser.parts).replace("\xa0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    return value.strip()


def text_to_html(value):
    paragraphs = re.split(r"\n\s*\n", (value or "").strip())
    if paragraphs == [""]:
        return "<p></p>"
    return "".join(
        f"<p>{escape(paragraph).replace(chr(10), '<br>')}</p>"
        for paragraph in paragraphs
    )


def _xml_hex_color(node, xpath):
    value = node.find(xpath, namespaces={"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"})
    return value.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val") if value is not None else None


def _run_html(run):
    text = "".join(run.itertext())
    if not text:
        return ""
    output = escape(text).replace("\n", "<br>")

    rpr = run.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr")
    styles = []
    if rpr is not None:
        color = rpr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}color")
        if color is not None and color.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val"):
            value = color.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val")
            if re.fullmatch(r"[0-9A-Fa-f]{6}", value):
                styles.append(f"color:#{value}")

        size = rpr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sz")
        if size is not None and size.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val"):
            try:
                points = int(size.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val")) / 2
                styles.append(f"font-size:{points:g}pt")
            except ValueError:
                pass

        highlight = rpr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}highlight")
        if highlight is not None and highlight.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val"):
            highlight_value = highlight.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val")
            palette = {
                "yellow": "#fff3a3", "green": "#d8ead8", "cyan": "#d7f0f2",
                "magenta": "#f0d8e9", "blue": "#dbe8f7", "red": "#f4d6d1",
            }
            if highlight_value in palette:
                styles.append(f"background-color:{palette[highlight_value]}")

        if rpr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}b") is not None:
            output = f"<strong>{output}</strong>"
        if rpr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}i") is not None:
            output = f"<em>{output}</em>"
        if rpr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}u") is not None:
            output = f"<u>{output}</u>"
        if rpr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}strike") is not None:
            output = f"<s>{output}</s>"

    if styles:
        output = f'<span style="{";".join(styles)}">{output}</span>'
    return output


def docx_to_html(raw_bytes):
    # Parse the DOCX XML directly: it avoids the repeated Python object creation
    # that python-docx performs and is noticeably faster on large manuscripts.
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))

    blocks = []
    for paragraph in root.xpath(".//w:body/w:p", namespaces=ns):
        ppr = paragraph.find("w:pPr", ns)
        style_name = ""
        if ppr is not None:
            pstyle = ppr.find("w:pStyle", ns)
            if pstyle is not None:
                style_name = pstyle.get("{%s}val" % ns["w"], "") or ""

        heading = re.search(r"(?:heading|titre)([1-6])", style_name, flags=re.IGNORECASE)
        body = "".join(_run_html(run) for run in paragraph.xpath("./w:r", namespaces=ns))
        if not body:
            body = "<br>"

        paragraph_styles = []
        if ppr is not None:
            jc = ppr.find("w:jc", ns)
            if jc is not None:
                align = jc.get("{%s}val" % ns["w"], "")
                if align in {"left", "center", "right", "both", "justify"}:
                    paragraph_styles.append("text-align:" + ("justify" if align == "both" else align))

            shd = ppr.find("w:shd", ns)
            fill = shd.get("{%s}fill" % ns["w"], "") if shd is not None else ""
            if re.fullmatch(r"[0-9A-Fa-f]{6}", fill or ""):
                paragraph_styles.append(f"background-color:#{fill}")

            borders = ppr.find("w:pBdr", ns)
            if borders is not None:
                for side_name in ("bottom", "top"):
                    side = borders.find(f"w:{side_name}", ns)
                    if side is not None:
                        val = side.get("{%s}val" % ns["w"], "")
                        if val and val != "nil":
                            blocks.append("<hr>")
                            break

        style_attr = f' style="{";".join(paragraph_styles)}"' if paragraph_styles else ""
        if heading:
            tag = "h" + heading.group(1)
        elif "quote" in style_name.lower():
            tag = "blockquote"
        else:
            tag = "p"

        blocks.append(f"<{tag}{style_attr}>{body}</{tag}>")

    return "".join(blocks)


def pdf_to_html(raw_bytes):
    reader = PyPDF2.PdfReader(io.BytesIO(raw_bytes))
    pages = []
    for page in reader.pages:
        value = page.extract_text() or ""
        if value.strip():
            pages.append(value.strip())
    return text_to_html("\n\n".join(pages))


def parse_uploaded_file(file_storage):
    filename = (file_storage.filename or "").strip()
    lower = filename.lower()
    raw = file_storage.read()

    if lower.endswith(".txt"):
        return filename, text_to_html(raw.decode("utf-8-sig", errors="replace"))
    if lower.endswith(".docx"):
        return filename, docx_to_html(raw)
    if lower.endswith(".pdf"):
        return filename, pdf_to_html(raw)
    raise ValueError("Unsupported file type. Please use .txt, .docx, or .pdf.")


def sentence_spans(value):
    output = []
    for match in SENTENCE_RE.finditer(value or ""):
        snippet = match.group(0).strip()
        if not snippet:
            continue
        leading = len(match.group(0)) - len(match.group(0).lstrip())
        trailing = len(match.group(0).rstrip())
        output.append((match.start() + leading, match.start() + trailing, snippet))
    return output


def analyse_text(value):
    value = value or ""
    if not value.strip():
        return {"words": [], "passive": [], "pacing": [], "flagged_count": 0}

    # One linear scan for word frequencies. Do not return every occurrence
    # position to the browser; the editor can locate occurrences on demand.
    counts = {}
    contexts = {}
    sentence_ranges = sentence_spans(value)

    for match in WORD_RE.finditer(value):
        word = match.group(0).lower().replace("’", "'").strip("'")
        if len(word) < 4 or word in STOP_WORDS:
            continue
        counts[word] = counts.get(word, 0) + 1

    frequent = [(word, count) for word, count in counts.items() if count >= 3]
    frequent.sort(key=lambda pair: (-pair[1], pair[0]))
    frequent = frequent[:60]

    frequent_set = {word for word, _ in frequent}
    if frequent_set:
        seen = {word: 0 for word in frequent_set}
        for start, end, snippet in sentence_ranges:
            for match in WORD_RE.finditer(snippet):
                word = match.group(0).lower().replace("’", "'").strip("'")
                if word in frequent_set and seen[word] < 3:
                    contexts.setdefault(word, []).append(snippet[:260])
                    seen[word] += 1

    words = [
        {
            "word": word,
            "count": count,
            "contexts": contexts.get(word, []),
        }
        for word, count in frequent
    ]

    passive = []
    pacing = []
    short_run = []

    for index, (start, end, snippet) in enumerate(sentence_ranges):
        word_count = len(WORD_RE.findall(snippet))

        if len(snippet) <= 500 and PASSIVE_RE.search(snippet):
            passive.append({
                "sentence": snippet[:500],
                "start": start,
                "end": end,
                "reason": "Possible passive construction",
            })

        if word_count > 40:
            pacing.append({
                "sentence": snippet[:500],
                "start": start,
                "end": end,
                "reason": "Long sentence",
                "word_count": word_count,
            })

        if word_count <= 8:
            short_run.append((start, end, snippet, word_count))
        else:
            if len(short_run) >= 3:
                pacing.extend(
                    {
                        "sentence": item[2][:500],
                        "start": item[0],
                        "end": item[1],
                        "reason": "Choppy sequence",
                        "word_count": item[3],
                    }
                    for item in short_run
                )
            short_run = []

        if index == len(sentence_ranges) - 1 and len(short_run) >= 3:
            pacing.extend(
                {
                    "sentence": item[2][:500],
                    "start": item[0],
                    "end": item[1],
                    "reason": "Choppy sequence",
                    "word_count": item[3],
                }
                for item in short_run
            )

        if len(passive) >= 120 and len(pacing) >= 120:
            break

    words_repeats = sum(max(0, item["count"] - 2) for item in words)
    flagged_count = words_repeats + len(passive) + len(pacing)

    return {
        "words": words,
        "passive": passive[:120],
        "pacing": pacing[:120],
        "flagged_count": flagged_count,
    }


def get_db():
    return SessionLocal()


def migrate_schema():
    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    # The previous version used SQLite/SQL statements directly. Add the new
    # slug column to that schema if an existing local database is reused.
    if "projects" in tables:
        columns = {column["name"] for column in inspector.get_columns("projects")}
        if "slug" not in columns:
            with engine.begin() as connection:
                connection.execute(sql_text("ALTER TABLE projects ADD COLUMN slug VARCHAR(180)"))

    db = get_db()
    try:
        users = db.execute(select(User)).scalars().all()
        for user in users:
            legacy_projects = db.execute(
                select(Project)
                .where(Project.user_id == user.id)
                .order_by(Project.id)
            ).scalars().all()

            if not legacy_projects and "documents" in tables:
                # Best-effort migration from the previous single-document schema.
                rows = db.execute(
                    sql_text(
                        "SELECT content FROM documents WHERE user_id = :user_id"
                    ),
                    {"user_id": user.id},
                ).fetchall()
                legacy_content = rows[0][0] if rows else ""
                project = Project(
                    user_id=user.id,
                    title="My manuscript",
                    slug=None,
                    content=sanitize_html(legacy_content),
                )
                db.add(project)
                db.flush()
                legacy_projects = [project]

            for project in legacy_projects:
                if not project.slug:
                    project.slug = unique_slug(db, user.id, project.title, project.id)

        db.commit()
    finally:
        db.close()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    db = get_db()
    try:
        return db.get(User, int(user_id))
    finally:
        db.close()


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


def project_for_user(db, project_id, user_id):
    return db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id,
        )
    ).scalar_one_or_none()


def project_for_slug(db, slug, user_id):
    return db.execute(
        select(Project).where(
            Project.slug == slug,
            Project.user_id == user_id,
        )
    ).scalar_one_or_none()


def project_payload(project, include_content=False):
    payload = {
        "id": project.id,
        "title": project.title,
        "slug": project.slug,
        "source_filename": project.source_filename or "",
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
        "url": project_link(project),
    }
    if include_content:
        payload["content"] = project.content or ""
        payload["analysis"] = json.loads(project.analysis_json or "{}")
    return payload


@app.route("/")
def index():
    host_slug = project_host_slug()
    if host_slug:
        user = current_user()
        if not user:
            return redirect(url_for("login_page"))
        db = get_db()
        try:
            project = project_for_slug(db, host_slug, user.id)
            if not project:
                return render_template("not_found.html"), 404
            return render_template("editor.html", email=user.email, project_slug=project.slug)
        finally:
            db.close()
    return render_template("index.html")


@app.route("/login/")
@app.route("/login")
def login_page():
    if current_user():
        return redirect(url_for("projects"))
    return render_template("login.html")


@app.route("/projects/")
@app.route("/projects")
@login_required
def projects():
    return render_template("projects.html", email=current_user().email)


@app.route("/editor/")
@app.route("/editor")
@login_required
def editor():
    db = get_db()
    try:
        first_project = db.execute(
            select(Project).where(Project.user_id == current_user().id).order_by(Project.updated_at.desc(), Project.id.desc())
        ).scalars().first()
        if not first_project:
            first_project = Project(
                user_id=current_user().id,
                title="Untitled manuscript",
                slug=None,
                content="",
            )
            db.add(first_project)
            db.flush()
            first_project.slug = unique_slug(db, current_user().id, first_project.title, first_project.id)
            db.commit()
        return redirect(project_link(first_project))
    finally:
        db.close()


@app.route("/project/<slug>/")
@app.route("/project/<slug>")
@login_required
def project_editor(slug):
    db = get_db()
    try:
        project = project_for_slug(db, slug, current_user().id)
        if not project:
            return render_template("not_found.html"), 404
        return render_template("editor.html", email=current_user().email, project_slug=project.slug)
    finally:
        db.close()


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

    db = get_db()
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()

        if action == "register":
            if user:
                return jsonify({"error": "An account with that email already exists. Please sign in."}), 409

            user = User(
                email=email,
                password_hash=generate_password_hash(password),
            )
            db.add(user)
            db.flush()

            project = Project(
                user_id=user.id,
                title="Untitled manuscript",
                slug=unique_slug(db, user.id, "Untitled manuscript"),
                content="",
            )
            db.add(project)
            db.commit()

            session.clear()
            session["user_id"] = user.id
            session["email"] = user.email
            return jsonify({"status": "success", "message": "Account created successfully."})

        if action == "login":
            if user and check_password_hash(user.password_hash, password):
                session.clear()
                session["user_id"] = user.id
                session["email"] = user.email
                return jsonify({"status": "success", "message": "Logged in successfully."})
            return jsonify({"error": "Invalid email or password."}), 401

        return jsonify({"error": "Unknown authentication action."}), 400
    finally:
        db.close()


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "success"})


@app.route("/api/account/delete", methods=["POST"])
@api_login_required
def delete_account():
    user = current_user()
    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    confirmation = (data.get("confirmation") or "").strip()

    if confirmation != "DELETE":
        return jsonify({"error": "Type DELETE to confirm permanent account removal."}), 400
    if not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Your password is incorrect."}), 401

    db = get_db()
    try:
        db.delete(db.get(User, user.id))
        db.commit()
    finally:
        db.close()

    session.clear()
    return jsonify({"status": "deleted"})


@app.route("/api/projects", methods=["GET"])
@api_login_required
def list_projects():
    user = current_user()
    db = get_db()
    try:
        projects = db.execute(
            select(Project)
            .where(Project.user_id == user.id)
            .order_by(Project.updated_at.desc(), Project.id.desc())
        ).scalars().all()
        return jsonify({"projects": [project_payload(project) for project in projects]})
    finally:
        db.close()


@app.route("/api/projects", methods=["POST"])
@api_login_required
def create_project():
    user = current_user()
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "Untitled manuscript").strip()[:160] or "Untitled manuscript"

    db = get_db()
    try:
        project = Project(
            user_id=user.id,
            title=title,
            slug=unique_slug(db, user.id, title),
            content="",
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return jsonify({"project": project_payload(project, include_content=True)}), 201
    finally:
        db.close()


@app.route("/api/projects/<int:project_id>", methods=["GET"])
@api_login_required
def get_project(project_id):
    user = current_user()
    db = get_db()
    try:
        project = project_for_user(db, project_id, user.id)
        if not project:
            return jsonify({"error": "Project not found."}), 404
        return jsonify({"project": project_payload(project, include_content=True)})
    finally:
        db.close()


@app.route("/api/projects/by-slug/<slug>", methods=["GET"])
@api_login_required
def get_project_by_slug(slug):
    user = current_user()
    db = get_db()
    try:
        project = project_for_slug(db, slug, user.id)
        if not project:
            return jsonify({"error": "Project not found."}), 404
        return jsonify({"project": project_payload(project, include_content=True)})
    finally:
        db.close()


@app.route("/api/projects/<int:project_id>", methods=["POST"])
@api_login_required
def save_project(project_id):
    user = current_user()
    db = get_db()
    try:
        project = project_for_user(db, project_id, user.id)
        if not project:
            return jsonify({"error": "Project not found."}), 404

        data = request.get_json(silent=True) or {}
        title = (data.get("title") or project.title).strip()[:160] or "Untitled manuscript"
        content = sanitize_html(data.get("content", project.content or ""))
        analysis = data.get("analysis")
        if isinstance(analysis, dict):
            project.analysis_json = json.dumps(analysis, ensure_ascii=False)

        if title != project.title:
            project.title = title
            project.slug = unique_slug(db, user.id, title, project.id)

        project.content = content
        project.updated_at = datetime.utcnow()
        db.commit()

        return jsonify({
            "status": "success",
            "updated_at": project.updated_at.isoformat(),
            "slug": project.slug,
            "url": project_link(project),
        })
    finally:
        db.close()


@app.route("/api/projects/<int:project_id>/analysis", methods=["POST"])
@api_login_required
def save_analysis(project_id):
    user = current_user()
    db = get_db()
    try:
        project = project_for_user(db, project_id, user.id)
        if not project:
            return jsonify({"error": "Project not found."}), 404
        data = request.get_json(silent=True) or {}
        analysis = data.get("analysis") or {}
        if not isinstance(analysis, dict):
            return jsonify({"error": "Invalid analysis payload."}), 400
        project.analysis_json = json.dumps(analysis, ensure_ascii=False)
        project.updated_at = datetime.utcnow()
        db.commit()
        return jsonify({"status": "success"})
    finally:
        db.close()


@app.route("/api/projects/<int:project_id>", methods=["DELETE"])
@api_login_required
def delete_project(project_id):
    user = current_user()
    db = get_db()
    try:
        project = project_for_user(db, project_id, user.id)
        if not project:
            return jsonify({"error": "Project not found."}), 404

        count = db.execute(
            select(Project.id).where(Project.user_id == user.id)
        ).all()
        if len(count) <= 1:
            return jsonify({"error": "Keep at least one project in your writing room."}), 400

        db.delete(project)
        db.commit()
        return jsonify({"status": "success"})
    finally:
        db.close()


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

    db = get_db()
    try:
        project = Project(
            user_id=user.id,
            title=title,
            slug=unique_slug(db, user.id, title),
            source_filename=filename,
            content=content,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return jsonify({"project": project_payload(project, include_content=True)}), 201
    finally:
        db.close()


@app.route("/api/projects/<int:project_id>/analyze", methods=["POST"])
@api_login_required
def analyse_project(project_id):
    user = current_user()
    db = get_db()
    try:
        project = project_for_user(db, project_id, user.id)
        if not project:
            return jsonify({"error": "Project not found."}), 404
        data = request.get_json(silent=True) or {}
        manuscript_text = data.get("text")
        if manuscript_text is None:
            manuscript_text = html_to_text(project.content)
        analysis = analyse_text(manuscript_text)
        project.analysis_json = json.dumps(analysis, ensure_ascii=False)
        project.updated_at = datetime.utcnow()
        db.commit()
        return jsonify(analysis)
    finally:
        db.close()


def html_to_docx(content):
    class DocumentBuilder(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.document = docx.Document()
            self.paragraph = None
            self.bold = False
            self.italic = False
            self.underline = False
            self.strike = False

        def ensure_paragraph(self, style=None):
            if self.paragraph is None:
                self.paragraph = self.document.add_paragraph()
                if style:
                    try:
                        self.paragraph.style = style
                    except Exception:
                        pass
            return self.paragraph

        def finish(self):
            self.paragraph = None

        def handle_starttag(self, tag, attrs):
            tag = tag.lower()
            if tag in {"p", "div"}:
                self.finish()
                self.ensure_paragraph()
            elif tag == "blockquote":
                self.finish()
                self.ensure_paragraph("Intense Quote")
            elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                self.finish()
                self.ensure_paragraph("Heading " + tag[1])
            elif tag == "li":
                self.finish()
                self.ensure_paragraph("List Bullet")
            elif tag in {"strong", "b"}:
                self.bold = True
            elif tag in {"em", "i"}:
                self.italic = True
            elif tag == "u":
                self.underline = True
            elif tag in {"s", "strike"}:
                self.strike = True

        def handle_endtag(self, tag):
            tag = tag.lower()
            if tag in {"p", "div", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "li"}:
                self.finish()
            elif tag in {"strong", "b"}:
                self.bold = False
            elif tag in {"em", "i"}:
                self.italic = False
            elif tag == "u":
                self.underline = False
            elif tag in {"s", "strike"}:
                self.strike = False

        def handle_startendtag(self, tag, attrs):
            if tag.lower() == "br":
                self.ensure_paragraph().add_run().add_break()
            elif tag.lower() == "hr":
                p = self.ensure_paragraph()
                p.paragraph_format.space_after = 0
                p.add_run("────────────────────────").italic = True
                self.finish()

        def handle_data(self, data):
            if not data:
                return
            run = self.ensure_paragraph().add_run(data)
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
    db = get_db()
    try:
        project = project_for_user(db, project_id, user.id)
        if not project:
            return jsonify({"error": "Project not found."}), 404
        safe_title = re.sub(r"[^A-Za-z0-9._-]+", "_", project.title).strip("_") or "manuscript"
        if fmt == "txt":
            return send_file(
                io.BytesIO(html_to_text(project.content).encode("utf-8")),
                mimetype="text/plain; charset=utf-8",
                as_attachment=True,
                download_name=f"{safe_title}.txt",
            )
        if fmt == "docx":
            return send_file(
                html_to_docx(project.content),
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                as_attachment=True,
                download_name=f"{safe_title}.docx",
            )
        if fmt == "html":
            document = (
                "<!doctype html><html><head><meta charset='utf-8'><title>"
                + escape(project.title)
                + "</title><style>body{max-width:860px;margin:50px auto;padding:0 30px;background:#f7f5f2;color:#171411;font:17px/1.8 Georgia,serif}"
                "h1,h2,h3{color:#3f3027}hr{border:0;border-top:1px solid #c0ab9a;margin:2em 0}</style></head><body>"
                + project.content
                + "</body></html>"
            )
            return app.response_class(
                document,
                mimetype="text/html",
                headers={"Content-Disposition": f'attachment; filename="{safe_title}.html"'},
            )
        return jsonify({"error": "Unknown export format."}), 400
    finally:
        db.close()


@app.route("/analyze", methods=["POST"])
@api_login_required
def legacy_analyse():
    if "file" in request.files and request.files["file"].filename:
        try:
            _, content = parse_uploaded_file(request.files["file"])
            value = html_to_text(content)
        except Exception as exc:
            return jsonify({"error": f"Failed to read file: {exc}"}), 500
    else:
        value = request.form.get("text", "")
    return jsonify(analyse_text(value))


migrate_schema()

if __name__ == "__main__":
    app.run(debug=True)
