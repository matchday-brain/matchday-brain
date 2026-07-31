from flask import Flask, render_template, request, jsonify
import json
from pathlib import Path

app = Flask(__name__)
DATA = Path(__file__).resolve().parent / "data"

def products():
    return json.loads((DATA / "products.json").read_text(encoding="utf-8"))

@app.route("/")
def home():
    return render_template("home.html", products=products())

@app.route("/range")
def range_page():
    return render_template("range.html", products=products())

@app.route("/bespoke")
def bespoke():
    return render_template("bespoke.html")

@app.route("/gallery")
def gallery():
    return render_template("gallery.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/api/bespoke-quote", methods=["POST"])
def bespoke_quote():
    data = request.get_json(force=True)
    base = 3500
    additions = {
        "prep": 850, "storage": 750, "sink": 1100, "fridge": 950,
        "pizza": 1650, "bar": 1450, "pergola": 2600, "lighting": 425
    }
    total = base + sum(additions.get(x,0) for x in data.get("features", []))
    if data.get("finish") == "stainless":
        total += 850
    if data.get("finish") == "corten":
        total += 600
    return jsonify({"estimate": total, "reference":"INV-BSP-001"})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
