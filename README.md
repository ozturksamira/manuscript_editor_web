<p align="center">
<img width="1366" height="768" alt="magnolia margin" src="https://github.com/user-attachments/assets/c44ed85e-837e-45b6-9aa9-ec8302d95e4e" />
    </p>

# Magnolia Margin | Manuscript Analyser & Editor

A professional, full-stack manuscript analysis and editing web application built for writers who want editorial help without generative writing.

* **Live Web App:** [Magnolia Margin](https://magnoliamargin.onrender.com/) *(Hosted via Render)*
* **GitHub Repository:** [ozturksamira/manuscript_editor_web](https://github.com/ozturksamira/manuscript_editor_web)

---

## Interactive Interface & User Experience

The application features a modern, full-screen **snap-scrolling slideshow layout** utilizing a custom warm color palette (Pearl, Platinum, Tuscany, Raw Umber, Old Burgundy, and Eerie Black):

1. **Welcome Slide (Hero Section):** A light, welcoming introduction screen featuring a smooth animated down arrow (`↓`) that snaps users directly into the core editor.
2. **Main Editor Slide:** Houses the multi-format file uploader (`.txt`, `.docx`, `.pdf`) and raw text pasting interface, connected to a dynamic tabbed dashboard:
* **Overused Words Tab:** Displays word frequencies, count totals, and direct context-location sentence links, enhanced with a live custom search bar and multi-sorting filters (Most/Least Used, A-Z, Z-A).
* **Passive Voice Tab:** Dynamically flags and isolates sentences containing passive constructions.
* **Pacing Issues Tab:** Spots overly long sentences and consecutive dragging segments.


3. **About Me Slide:** A professional footer section detailing the developer and linking directly to GitHub (`ozturksamira`).

## Extended Vision
- Develop custom stop-word filtering algorithms to isolate overused vocabulary and map occurrence counts directly to in-text context snippets.
- Modify editorial page to look more sleek.
- Extend and develop feature which allows users to modify their scripts' tense (e.g. first to third, past to present).

---
## How the Webpage Works (Architecture Flowchart)

```mermaid
graph TD
    A[User Opens Webpage] --> B[Hero Slide: Welcome Screen]
    B -->|Clicks Down Arrow| C[Editor Slide: Input Interface]
    C -->|Uploads File or Pastes Text| D[Frontend JavaScript: FormData POST Request]
    D --> E[Flask Backend: /analyze Route]
    E -->|If File Uploaded| F[Extract Text via docx / PyPDF2 / UTF-8 Streams]
    E -->|If Text Pasted| G[Read Raw String Payload]
    F & G --> H[ManuscriptProcessor Class Analysis]
    H -->|1. Filter Stop Words & Calculate Dynamic Frequencies| I[Track Word Counts & Context Snippets]
    H -->|2. Regex Scan| J[Detect Passive Voice Sentences]
    H -->|3. Heuristic Scan| K[Detect Long / Consecutive Pacing Bottlenecks]
    I & J & K --> L[Return Structured JSON Payload]
    L --> M[Frontend: Render Interactive Tabs, Tables, Search, & Sort Filters]
    M --> N[User Explores Results & Context Locations]

```

---

## Key Technical Features

* **Multi-Format Document Parsing:** Safely processes raw text strings, Microsoft Word (`.docx`), and Adobe PDF (`.pdf`) documents using server-side binary stream mapping (`io.BytesIO`).
* **Advanced Frequency Analysis:** Automatically strips out extensive stop-words (pronouns, articles, conjunctions) to surface genuine overused vocabulary alongside exact occurrence counts.
* **Contextual Location Tracking:** Maps flagged vocabulary back to the exact sentences they appear in, providing writers with immediate in-text context.
* **Client-Side Data Filtering & Sorting:** Instantaneous DOM manipulation allowing users to search specific words and sort metrics without page reloads.

---

## Local Installation & Setup

To run or inspect this project locally, follow these steps:

1. **Clone the Repository:**
```bash
git clone https://github.com/ozturksamira/manuscript_app.git
cd manuscript_app

```


2. **Create and Activate a Virtual Environment:**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

```


3. **Install Dependencies:**
```bash
pip install -r requirements.txt

```


4. **Run the Flask Development Server:**
```bash
python3 app.py

```


5. **Open in Your Browser:**
Navigate to `[http://127.0.0.1:5000](http://127.0.0.1:5000)` to interact with the dashboard locally.

---

## Tech Stack & Requirements (`requirements.txt`)

* **Backend:** Python, Flask, Gunicorn
* **Document Parsing:** python-docx, PyPDF2, lxml
* **Frontend:** HTML5, CSS3 (Custom CSS Grid / Flexbox Snap Layout), JavaScript (ES6+ Asynchronous Fetch API)

```text
Flask
gunicorn
lxml==6.1.3
PyPDF2==3.0.1
python-docx==1.2.0
typing_extensions==4.16.0

```

---

## About the Developer

Built by **Samira Ozturk**.

* Check out more of my open-source applications on [GitHub (@ozturksamira)](https://www.google.com/search?q=https://github.com/ozturksamira).


## Render production storage

Production storage is defined in `render.yaml`. It provisions a Render Postgres database, wires its private `connectionString` into `DATABASE_URL`, and asks Render to generate a persistent `SECRET_KEY`. Render Blueprints preserve existing environment variables when they are synced.

The Flask app uses PostgreSQL whenever `DATABASE_URL` is present and uses local SQLite only for development. On Render it now refuses to start without `DATABASE_URL` so the application cannot silently fall back to an ephemeral filesystem database and lose accounts or manuscripts after a redeploy. Passwords are stored as secure password hashes, never as plaintext.

### First production deployment

Create or sync the Render Blueprint from this repository so the `magnoliamargin-db` database is created and `DATABASE_URL` is connected to the web service. Keep `SECRET_KEY` managed by Render; do not commit either secret values or database credentials to the repository.

An account that only existed in the old ephemeral SQLite database cannot be recovered by code after the filesystem has already been reset. Once the Render Postgres database is in use, account and manuscript records live outside the web service and survive normal rebuilds and redeployments.

## Project subdomains

The application supports project-specific custom subdomains when `PROJECT_DOMAIN` is configured. For example, with `PROJECT_DOMAIN=magnoliamargin.example`, a project with slug `my-novel` is linked as `https://my-novel.magnoliamargin.example/`.

Render supports wildcard custom domains, so add a wildcard such as `*.magnoliamargin.example` to the web service and configure the corresponding wildcard DNS record. Without a wildcard domain configured, the dashboard automatically falls back to the normal `/project/<slug>/` route.
