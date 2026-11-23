# ClarityForge — Classical AI Document Question Answering System

## Overview
A document-grounded question-answering application using deterministic, explainable classical techniques. It does **not** use NLP libraries, large language models, embeddings, vector databases, or Retrieval-Augmented Generation (RAG).

## Features
- Upload multiple TXT, text-based PDF, and DOCX files.
- Extract and segment document text into statements.
- Build a persistent SQLite knowledge base.
- Ask questions and rank statements using lexical overlap, query-term coverage, and statement-term density.
- View source evidence, matched terms, relevance scores, and a transparent reasoning trace.
- Search extracted statements, remove documents, clear the knowledge base, and export statements as TSV.
- Run a small expected-term coverage evaluation.

## Setup
Python 3.10+ is recommended.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## Deployment
This is a Flask application, not a static-only site. Deploy it to a Python web-service host with:
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`

For persistent production use, configure a persistent disk for the `data/` directory or use managed database/object storage. The included local SQLite and uploads directory are suitable for coursework/local demonstration, not multi-instance production.

## Assignment compliance
The system uses explicit knowledge representation (document statements), deterministic lexical search, scoring rules, and evidence selection. It does not claim human-like semantic understanding. Evaluation reports expected-term coverage only; this is not semantic accuracy.

## Limitations
- Scanned/image-only PDFs need OCR, which is intentionally not included.
- Lexical matching can miss paraphrases and may return weak matches for vague questions.
- Upload size is limited to 20 MB per request.
- Uploaded files should be treated as untrusted; production deployment needs authentication, malware scanning, stronger validation, and persistent storage configuration.
