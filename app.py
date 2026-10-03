from flask import Flask, render_template, request, jsonify
import re

app = Flask(__name__)


class ManuscriptProcessor:
    """Analyzes manuscript text for common writing pitfalls."""

    def __init__(self):
        # Target words commonly overused in creative writing[cite: 1]
        self.overused_words = {"just", "really", "very", "suddenly", "literally", "actually", "that", "almost"}

        # Regex for passive voice detection[cite: 1]
        self.passive_regex = re.compile(r'\b(is|are|was|were|be|been|being|am)\s+\w+ed\b', re.IGNORECASE)

        # Sentence word count threshold for pacing issues[cite: 1]
        self.long_sentence_threshold = 30

    def get_sentences(self, text):
        """Splits raw text into a list of sentences[cite: 1]."""
        return re.split(r'(?<=[.!?]) +', text.strip())

    def analyze_text(self, text):
        """Parses sentences directly from string input and identifies issues[cite: 1]."""
        sentences = self.get_sentences(text)
        flagged_data = []

        for sentence in sentences:
            words = re.findall(r'\b\w+\b', sentence.lower())
            word_count = len(words)

            if word_count == 0:
                continue

            issues = []

            # 1. Overused words check[cite: 1]
            found_overused = [w for w in words if w in self.overused_words]
            if found_overused:
                unique_overused = list(set(found_overused))
                issues.append(f"Overused words: {', '.join(unique_overused)}")

            # 2. Passive voice check[cite: 1]
            if self.passive_regex.search(sentence):
                issues.append("Passive voice detected")

            # 3. Pacing check[cite: 1]
            if word_count > self.long_sentence_threshold:
                issues.append("Pacing issue: Long sentence")

            if issues:
                flagged_data.append({
                    "sentence": sentence.strip().replace('\n', ' '),
                    "word_count": word_count,
                    "issues": " | ".join(issues)
                })

        return flagged_data


processor = ManuscriptProcessor()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json() or {}
    text = data.get("text", "")

    if not text.strip():
        return jsonify({"results": [], "flagged_count": 0})

    results = processor.analyze_text(text)
    return jsonify({"results": results, "flagged_count": len(results)})


if __name__ == "__main__":
    # 0.0.0.0 tells Flask to listen on all public IPs on your local network
    app.run(host="0.0.0.0", port=5000, debug=True)