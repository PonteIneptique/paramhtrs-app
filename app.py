from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
import click
import json
from typing import List
from dataclasses import dataclass, field


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///data.db"  # Use SQLite for simplicity
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class Doc(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # Auto-increment ID
    title = db.Column(db.String(255), unique=True, nullable=False)  # Ensure unique title
    text = db.Column(db.Text, nullable=False)
    lines = db.relationship("Line", backref="doc", cascade="all, delete-orphan", lazy=True)

class Line(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # Auto-increment ID
    start = db.Column(db.Integer, nullable=False)
    canonical = db.Column(db.Text, nullable=False)
    normalized = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default="Pending")
    merge = db.Column(db.Boolean, default=False)
    doc_id = db.Column(db.Integer, db.ForeignKey("doc.id"), nullable=False)  # Relationship to Doc

    @property
    def length(self):
        return len(self.canonical)

    @property
    def end(self):
        return len(self.canonical) + self.start


@app.route("/")
def index():
    # Pass the documents to the template
    return render_template("index.html", documents=Doc.query.all())


@app.route("/document/<int:doc_id>/lines") # Should deal with lines / page
def lines(doc_id):
    doc = Doc.query.get_or_404(doc_id)
    return render_template(
        "lines.html", lines=doc.lines, document=doc)


@app.cli.group("db")
def db_group():
    return

@db_group.command("create")
def db_create():
    with app.app_context():
        db.create_all()
    print("DB Created")

@db_group.command("reset")
def db_create():
    with app.app_context():
        db.drop_all()
        db.create_all()
    print("DB Created")

@app.cli.command("import")
@click.argument("jsonl")
def import_(jsonl):
    with app.app_context():
        with open(jsonl) as f:
            for line in f:
                j = json.loads(line)

                # Check if document already exists
                existing_doc = Doc.query.filter_by(title=j["id"]).first()
                if existing_doc:
                    continue  # Skip if it exists

                # Create and insert new document
                new_doc = Doc(title=j["id"], text=j["text"])
                db.session.add(new_doc)
                db.session.commit()  # Save to get an ID

                # Prepare for preprocessing
                last_end = 0
                line_id = 1  # Start ID from 1

                sorted_lines = sorted(j["lines"], key=lambda l: l["begin"])  # Sort by start index

                for line_data in sorted_lines:
                    if not line_data.get("wits"):
                        continue

                    start = line_data["begin"]
                    canonical = line_data["text"]
                    normalized = line_data["wits"][0]["text"]

                    # Handle uncovered text before this line
                    if start > last_end:
                        uncovered_text = j["text"][last_end:start].strip()
                        if uncovered_text:
                            uncovered_line = Line(
                                start=last_end, canonical=uncovered_text, normalized="", doc_id=new_doc.id
                            )
                            db.session.add(uncovered_line)
                            line_id += 1

                    # Add actual mapped line
                    new_line = Line(start=start, canonical=canonical, normalized=normalized, doc_id=new_doc.id)
                    db.session.add(new_line)
                    last_end = start + len(canonical)  # Update last_end

                # Handle remaining text at the end
                if last_end < len(j["text"]) and j["text"][last_end:].strip():
                    trailing_line = Line(
                        start=last_end, canonical=j["text"][last_end:], normalized="", doc_id=new_doc.id
                    )
                    db.session.add(trailing_line)

                db.session.commit()  # Save all lines