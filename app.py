from __future__ import annotations

import json
from pathlib import Path
from flask import Flask, render_template, jsonify, request, redirect, url_for

app = Flask(__name__)
DATA_PATH = Path(__file__).resolve().parent / "data" / "modules.json"

def load_modules():
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))

def save_modules(modules):
    DATA_PATH.write_text(json.dumps(modules, indent=2), encoding="utf-8")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/modules")
def api_modules():
    return jsonify(load_modules())

@app.route("/api/checkout", methods=["POST"])
def api_checkout():
    payload = request.get_json(force=True)
    selected = payload.get("selected", [])
    module_map = {m["id"]: m for m in load_modules()}
    items = [module_map[i] for i in selected if i in module_map]
    subtotal = sum(float(i["price"]) for i in items)
    delivery = 450 if items else 0
    vat = round((subtotal + delivery) * 0.2, 2)
    bom = {}
    for item in items:
        for part, qty in item.get("bom", []):
            if qty:
                bom[part] = bom.get(part, 0) + qty
    return jsonify({
        "order_ref": "INV-OL-MOCK-001",
        "subtotal": subtotal,
        "delivery": delivery,
        "vat": vat,
        "total": subtotal + delivery + vat,
        "width": sum(int(i.get("width", 0)) for i in items),
        "bom": [{"part": k, "qty": v} for k, v in sorted(bom.items())],
    })

@app.route("/admin", methods=["GET", "POST"])
def admin():
    modules = load_modules()
    if request.method == "POST":
        updated = []
        for m in modules:
            item = dict(m)
            item["name"] = request.form.get(f"{m['id']}_name", m["name"])
            item["category"] = request.form.get(f"{m['id']}_category", m["category"])
            item["price"] = float(request.form.get(f"{m['id']}_price", m["price"]) or 0)
            item["width"] = int(float(request.form.get(f"{m['id']}_width", m["width"]) or 0))
            item["description"] = request.form.get(f"{m['id']}_description", m["description"])
            updated.append(item)
        save_modules(updated)
        return redirect(url_for("admin", saved=1))
    return render_template("admin.html", modules=modules, saved=request.args.get("saved"))

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
