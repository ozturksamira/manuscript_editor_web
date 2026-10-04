from flask import Flask, render_template, request, jsonify
import PyPDF2
import docx
from io import BytesIO

# Initialize your Flask app and your ManuscriptProcessor
app = Flask(__name__)


# processor = ManuscriptProcessor()

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    text = ""

    # Handle File Upload safely using io.BytesIO streams
    if 'file' in request.files and request.files['file'].filename != '':
        file = request.files['file']
        filename = file.filename.lower()

        try:
            if filename.endswith('.txt'):
                text = file.read().decode('utf-8')

            elif filename.endswith('.docx'):
                file_stream = BytesIO(file.read())
                doc = docx.Document(file_stream)
                text = "\n".join([para.text for para in doc.paragraphs])

            elif filename.endswith('.pdf'):
                file_stream = BytesIO(file.read())
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

    # Execute your processor logic here
    # data = processor.analyze_text(text, custom_words)

    # The frontend expects 'words', 'passive', and 'pacing' arrays in the JSON response
    return jsonify({
        # "words": data.words,
        # "passive": data.passive,
        # "pacing": data.pacing
    })


if __name__ == "__main__":
    app.run(debug=True)