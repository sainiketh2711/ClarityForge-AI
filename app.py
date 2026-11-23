
import os, re, sqlite3, uuid
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename
from pypdf import PdfReader
from docx import Document as DocxDocument
from io import BytesIO
from datetime import datetime

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
UPLOADS = DATA / "uploads"
DATA.mkdir(exist_ok=True)
UPLOADS.mkdir(exist_ok=True)
DB = DATA / "knowledge.db"
ALLOWED = {".txt", ".pdf", ".docx"}
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS documents(
            id TEXT PRIMARY KEY, filename TEXT NOT NULL, stored TEXT NOT NULL,
            uploaded_at TEXT NOT NULL, char_count INTEGER NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS facts(
            id INTEGER PRIMARY KEY AUTOINCREMENT, document_id TEXT NOT NULL,
            filename TEXT NOT NULL, content TEXT NOT NULL)""")

def extract_text(path):
    ext = path.suffix.lower()
    if ext == ".txt":
        return path.read_text(encoding="utf-8", errors="replace")
    if ext == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if ext == ".docx":
        doc = DocxDocument(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    raise ValueError("Unsupported file type")

def split_facts(text):
    # Simple deterministic sentence/line segmentation; deliberately not NLP.
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [re.sub(r"\s+", " ", p).strip() for p in parts if len(p.strip()) >= 12]

STOP = {"the","and","for","with","that","this","from","are","was","were","what","when","where","who","why","how","does","did","can","could","into","about","have","has","had","not","but","you","your","their","they","its","our","use","using"}
def terms(text):
    return [w for w in re.findall(r"[a-zA-Z0-9]+", text.lower()) if len(w) > 1 and w not in STOP]

def score(query, fact):
    q = set(terms(query)); f = set(terms(fact))
    if not q or not f: return 0.0, []
    overlap = sorted(q & f)
    coverage = len(overlap) / len(q)
    density = len(overlap) / len(f)
    phrase = 0.12 if query.lower().strip() in fact.lower() else 0
    return round(coverage * 0.72 + density * 0.28 + phrase, 4), overlap

@app.get("/")
def home():
    return render_template("index.html", brand='ClarityForge', tagline='Turn source documents into clear, traceable answers.', accent='#FF684A')

@app.post("/api/upload")
def upload():
    files = request.files.getlist("files")
    if not files or all(not f.filename for f in files):
        return jsonify(error="Choose at least one document."), 400
    added, errors = [], []
    for f in files:
        name = secure_filename(f.filename or "")
        ext = Path(name).suffix.lower()
        if not name or ext not in ALLOWED:
            errors.append(f"{name or 'Unnamed file'}: only TXT, PDF and DOCX are supported.")
            continue
        doc_id = uuid.uuid4().hex
        dest = UPLOADS / f"{doc_id}{ext}"
        try:
            f.save(dest)
            content = extract_text(dest)
            if not content.strip():
                raise ValueError("No extractable text found. Scanned PDFs are not supported.")
            facts = split_facts(content)
            with db() as c:
                c.execute("INSERT INTO documents VALUES(?,?,?,?,?)",
                          (doc_id, name, str(dest.relative_to(ROOT)), datetime.utcnow().isoformat(), len(content)))
                c.executemany("INSERT INTO facts(document_id,filename,content) VALUES(?,?,?)",
                              [(doc_id, name, fact) for fact in facts])
            added.append({"id": doc_id, "filename": name, "facts": len(facts), "characters": len(content)})
        except Exception as e:
            dest.unlink(missing_ok=True)
            errors.append(f"{name}: {e}")
    return jsonify(added=added, errors=errors), (200 if added else 400)

@app.post("/api/ask")
def ask():
    question = (request.json or {}).get("question", "").strip()
    if not question: return jsonify(error="Enter a question."), 400
    with db() as c:
        rows = c.execute("SELECT filename,content FROM facts").fetchall()
    ranked = []
    for row in rows:
        s, matched = score(question, row["content"])
        if s > 0: ranked.append((s, row["filename"], row["content"], matched))
    ranked.sort(key=lambda x: x[0], reverse=True)
    selected = ranked[:4]
    if not selected or selected[0][0] < 0.12:
        answer = "I could not find a sufficiently relevant statement in the uploaded documents. Try rephrasing the question or adding a relevant document."
    else:
        answer = " ".join(item[2] for item in selected[:3])
    evidence = [{"source": n, "statement": t, "score": s, "matched_terms": m} for s,n,t,m in selected]
    trace = [
        "Tokenized the question using a fixed alphanumeric rule.",
        "Removed a small, fixed list of common words.",
        "Compared remaining terms with each stored statement.",
        "Ranked statements by query-term coverage and statement-term density.",
        f"Selected {len(selected)} evidence statement(s); no generative model or external knowledge was used."
    ]
    return jsonify(answer=answer, evidence=evidence, reasoning=trace)

@app.get("/api/documents")
def documents():
    with db() as c:
        rows = c.execute("""SELECT d.id,d.filename,d.uploaded_at,d.char_count,
            COUNT(f.id) AS fact_count FROM documents d LEFT JOIN facts f
            ON d.id=f.document_id GROUP BY d.id ORDER BY d.uploaded_at DESC""").fetchall()
    return jsonify(documents=[dict(r) for r in rows])

@app.get("/api/facts")
def facts():
    q = request.args.get("q","").lower().strip()
    with db() as c:
        rows = c.execute("SELECT filename,content FROM facts ORDER BY id DESC").fetchall()
    result = [dict(source=r["filename"], statement=r["content"]) for r in rows
              if not q or q in r["filename"].lower() or q in r["content"].lower()]
    return jsonify(facts=result)

@app.delete("/api/documents/<doc_id>")
def delete_document(doc_id):
    with db() as c:
        row = c.execute("SELECT stored FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not row: return jsonify(error="Document not found."), 404
        (ROOT / row["stored"]).unlink(missing_ok=True)
        c.execute("DELETE FROM facts WHERE document_id=?", (doc_id,))
        c.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    return jsonify(success=True)

@app.post("/api/evaluate")
def evaluate():
    payload = request.json or {}
    questions = payload.get("questions", [])
    results = []
    for item in questions:
        q = str(item.get("question","")).strip()
        expected = terms(str(item.get("expected","")))
        with app.test_client() as client:
            response = client.post("/api/ask", json={"question": q})
        answer = response.get_json().get("answer","")
        actual = set(terms(answer))
        coverage = round(len(set(expected) & actual) / len(set(expected)), 3) if expected else 0
        results.append({"question": q, "answer": answer, "expected_term_coverage": coverage})
    avg = round(sum(r["expected_term_coverage"] for r in results)/len(results), 3) if results else 0
    return jsonify(results=results, average_expected_term_coverage=avg,
                   note="Lexical coverage is a simple diagnostic, not a semantic or human accuracy score.")

@app.get("/api/stats")
def stats():
    with db() as c:
        docs = c.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        facts_count = c.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        chars = c.execute("SELECT COALESCE(SUM(char_count),0) FROM documents").fetchone()[0]
    return jsonify(documents=docs, facts=facts_count, characters=chars)

@app.get("/api/export")
def export():
    with db() as c:
        rows = c.execute("SELECT filename,content FROM facts ORDER BY filename,id").fetchall()
    out = "SOURCE\tSTATEMENT\n" + "\n".join(f"{r['filename']}\t{r['content']}" for r in rows)
    return send_file(BytesIO(out.encode("utf-8")), mimetype="text/tab-separated-values",
                     as_attachment=True, download_name="knowledge_base.tsv")

@app.post("/api/clear")
def clear():
    with db() as c:
        c.execute("DELETE FROM facts"); c.execute("DELETE FROM documents")
    for p in UPLOADS.iterdir():
        if p.is_file(): p.unlink()
    return jsonify(success=True)

init_db()
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=True)
