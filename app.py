import io
import docx
import PyPDF2
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    text = ""

    # Handle File Upload using io.BytesIO streams
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

    # Handle Text Paste (if no file was uploaded)
    else:
        text = request.form.get("text", "")

    custom_words_raw = request.form.get("custom_words", "")
    custom_words = {w.strip().lower() for w in custom_words_raw.split(",") if w.strip()}

    if not text.strip():
        return jsonify({"words": [], "passive": [], "pacing": [], "flagged_count": 0})

    # Placeholder for your NLP processing logic
    # data = processor.analyze_text(text, custom_words)

    return jsonify({
        "words": [],  # Replace with data.words
        "passive": [],  # Replace with data.passive
        "pacing": []  # Replace with data.pacing
    })


@app.route("/save", methods=["POST"])
def save_progress():
    # Placeholder for database cloud saving
    data = request.get_json()
    return jsonify({"status": "success"})


if __name__ == "__main__":
    app.run(debug=True)