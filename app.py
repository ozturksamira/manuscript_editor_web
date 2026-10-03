from flask import Flask, render_template, request, jsonify
import re
from collections import Counter
import PyPDF2
import docx
import io

app = Flask(__name__)


class ManuscriptProcessor:
    def __init__(self):
        self.stop_words = {
            "the", "and", "a", "to", "of", "in", "it", "is", "that", "was", "for", "on", "are", "with",
            "as", "i", "you", "he", "she", "they", "at", "be", "this", "have", "from", "or", "had", "by",
            "but", "not", "what", "all", "were", "when", "we", "there", "can", "an", "your", "which",
            "their", "back", "if", "do", "will", "each", "about", "how", "up", "out", "them", "then",
            "against", "through", "would", "his", "her", "him", "hers", "etc", "so", "me", "my", "could", "into"
        }
        self.passive_regex = re.compile(r'\b(is|are|was|were|be|been|being|am)\s+\w+ed\b', re.IGNORECASE)

    @staticmethod
    def get_sentences(text):
        return re.split(r'(?<=[.!?]) +', text.strip())

    def analyze_text(self, text):
        sentences = self.get_sentences(text)

        passive_data = []
        pacing_data = []
        word_tracker = {}

        all_words = re.findall(r'\b\w+\b', text.lower())
        meaningful_words = [w for w in all_words if w not in self.stop_words and len(w) > 2]
        word_counts = Counter(meaningful_words)

        consecutive_long_sentences = 0

        for sentence in sentences:
            clean_sentence = sentence.strip().replace('\n', ' ')
            words = re.findall(r'\b\w+\b', clean_sentence.lower())
            word_count = len(words)

            if word_count == 0:
                continue

            # 1. Passive Voice Check
            if self.passive_regex.search(clean_sentence):
                passive_data.append({"sentence": clean_sentence, "word_count": word_count})

            # 2. Pacing Check
            if word_count > 25:
                consecutive_long_sentences += 1
                if consecutive_long_sentences >= 2:
                    pacing_data.append(
                        {"sentence": clean_sentence, "word_count": word_count, "issue": "Consecutive long sentences"})
                else:
                    pacing_data.append({"sentence": clean_sentence, "word_count": word_count, "issue": "Long sentence"})
            else:
                consecutive_long_sentences = 0

            # 3. Track Word Contexts (Limits to 15 context snippets per word to prevent massive payloads)
            for w in set(words):
                if w in word_counts:
                    if w not in word_tracker:
                        word_tracker[w] = {"word": w, "count": word_counts[w], "contexts": []}
                    if len(word_tracker[w]["contexts"]) < 15:
                        word_tracker[w]["contexts"].append(clean_sentence)

        # Convert word tracker to a list and filter out words only used once to keep the list focused
        word_data = [data for data in word_tracker.values() if data["count"] > 1]

        return {
            "words": word_data,
            "passive": passive_data,
            "pacing": pacing_data
        }


processor = ManuscriptProcessor()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    text = ""

    if 'file' in request.files and request.files['file'].filename:
        file = request.files['file']
        raw_filename = file.filename

        if not raw_filename:
            return jsonify({"error": "No file selected."}), 400

        filename = raw_filename.lower()

        try:
            file_bytes = file.read()
            if filename.endswith('.txt'):
                text = file_bytes.decode('utf-8')
            elif filename.endswith('.docx'):
                doc = docx.Document(io.BytesIO(file_bytes))
                text = "\n".join([para.text for para in doc.paragraphs])
            elif filename.endswith('.pdf'):
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                for page in pdf_reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + " "
            else:
                return jsonify({"error": "Unsupported file type."}), 400
        except Exception as e:
            return jsonify({"error": f"Failed to read file: {str(e)}"}), 500
    else:
        text = request.form.get("text", "")

    if not text.strip():
        return jsonify({"words": [], "passive": [], "pacing": []})

    results = processor.analyze_text(text)
    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True)