import io
import docx
import PyPDF2
from flask import Flask, request, jsonify, render_template, session, redirect

app = Flask(__name__)
app.secret_key = "super_secret_secure_key_for_sessions"  # Replace with a secure environment variable in production

# Mock database for demonstration purposes
users_db = {}
user_documents = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/auth", methods=["POST"])
def auth():
    """Handles both login and account creation with email and password."""
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    action = data.get("action")  # 'login' or 'register'

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    if action == "register":
        if email in users_db:
            return jsonify({"error": "Account already exists. Please log in."}), 400
        # In a real app, hash the password using werkzeug.security.generate_password_hash
        users_db[email] = password
        session['user'] = email
        return jsonify({"status": "success", "message": "Account created successfully."})

    elif action == "login":
        if users_db.get(email) == password:
            session['user'] = email
            return jsonify({"status": "success", "message": "Logged in successfully."})
        return jsonify({"error": "Invalid email or password."}), 401


@app.route("/logout", methods=["POST"])
def logout():
    session.pop('user', None)
    return jsonify({"status": "success"})


@app.route("/analyze", methods=["POST"])
def analyze():
    text = ""

    if 'file' in request.files and request.files['file'].filename != '':
        file = request.files['file']
        filename = file.filename.lower()

        try:
            if filename.endswith('.txt'):
                text = file.read().decode('utf-8')
            elif filename.endswith('.docx'):
                file_stream = io.BytesIO(file.read())
                doc = docx.Document(file_stream)
                text = "\n".join([para.text for para in doc.paragraphs])
            elif filename.endswith('.pdf'):
                file_stream = io.BytesIO(file.read())
                pdf_reader = PyPDF2.PdfReader(file_stream)
                for page in pdf_reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + " "
            else:
                return jsonify({"error": "Unsupported file type. Please use .txt, .docx, or .pdf"}), 400

        except Exception as e:
            return jsonify({"error": f"Failed to read file: {str(e)}"}), 500
    else:
        text = request.form.get("text", "")

    if not text.strip():
        return jsonify({"words": [], "passive": [], "pacing": [], "flagged_count": 0})

    # Placeholder for NLP processing logic
    return jsonify({
        "words": [],
        "passive": [],
        "pacing": []
    })


@app.route("/save", methods=["POST"])
def save_progress():
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    user_documents[session['user']] = data.get('content', '')
    return jsonify({"status": "success"})


@app.route("/load", methods=["GET"])
def load_progress():
    if 'user' in session and session['user'] in user_documents:
        return jsonify({"content": user_documents[session['user']]})
    return jsonify({"content": ""})


if __name__ == "__main__":
    app.run(debug=True)