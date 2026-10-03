import PyPDF2
import docx
import io
from flask import Flask, render_template, request, jsonify
import re
from collections import Counter

app = Flask(__name__)


class ManuscriptProcessor:
    def __init__(self):
        self.stop_words = {"the", "and", "a", "to", "of", "in", "it", "is", "that", "was", "for", "on", "are", "with",
                           "as", "i", "you", "he", "she", "they", "at", "be", "this", "have", "from", "or", "had", "by",
                           "but", "not", "what", "all", "were", "when", "we", "there", "can", "an", "your", "which",
                           "their", "said", "if", "do", "will", "each", "about", "how", "up", "out", "them", "then"}
        self.passive_regex = re.compile(r'\b(is|are|was|were|be|been|being|am)\s+\w+ed\b', re.IGNORECASE)

    def get_sentences(self, text):
        return re.split(r'(?<=[.!?]) +', text.strip())

    def analyze_text(self, text, custom_words):
        sentences = self.get_sentences(text)
        flagged_data = []

        # Calculate overall word frequency for the whole text
        all_words = re.findall(r'\b\w+\b', text.lower())
        meaningful_words = [w for w in all_words if w not in self.stop_words and len(w) > 2]
        word_counts = Counter(meaningful_words)
        # Find words used more than 5 times (adjust as needed)
        frequent_words = {word for word, count in word_counts.items() if count > 5}

        consecutive_long_sentences = 0

        for sentence in sentences:
            words = re.findall(r'\b\w+\b', sentence.lower())
            word_count = len(words)
            if word_count == 0:
                continue

            issues = []
            issue_types = []  # Used for frontend filtering

            # 1. Custom User Words
            found_custom = [w for w in words if w in custom_words]
            if found_custom:
                issues.append(f"Custom flag: {', '.join(set(found_custom))}")
                issue_types.append("custom")

            # 2. Dynamic Frequency Checking
            found_frequent = [w for w in words if w in frequent_words]
            if found_frequent:
                issues.append(f"High frequency words: {', '.join(set(found_frequent))}")
                issue_types.append("frequency")

            # 3. Passive Voice
            if self.passive_regex.search(sentence):
                issues.append("Passive voice")
                issue_types.append("passive")

            # 4. Better Pacing (Flags if >25 words OR if multiple long sentences appear in a row)
            if word_count > 25:
                consecutive_long_sentences += 1
                if consecutive_long_sentences >= 2:
                    issues.append("Pacing: Consecutive long sentences dragging momentum")
                    issue_types.append("pacing")
                else:
                    issues.append("Pacing: Long sentence")
                    issue_types.append("pacing")
            else:
                consecutive_long_sentences = 0

            if issues:
                flagged_data.append({
                    "sentence": sentence.strip().replace('\n', ' '),
                    "word_count": word_count,
                    "issues": " | ".join(issues),
                    "types": issue_types
                })

        return flagged_data, word_counts.most_common(10)


processor = ManuscriptProcessor()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    text = ""

    # Handle File Upload
    if 'file' in request.files and request.files['file'].filename != '':
        file = request.files['file']
        filename = file.filename.lower()

        try:
            if filename.endswith('.txt'):
                text = file.read().decode('utf-8')

            elif filename.endswith('.docx'):
                doc = docx.Document(file)
                text = "\n".join([para.text for para in doc.paragraphs])

            elif filename.endswith('.pdf'):
                pdf_reader = PyPDF2.PdfReader(file)
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
        return jsonify({"results": [], "flagged_count": 0, "top_words": []})

    results, top_words = processor.analyze_text(text, custom_words)

    return jsonify({
        "results": results,
        "flagged_count": len(results),
        "top_words": top_words
    })

if __name__ == "__main__":
    app.run(debug=True)