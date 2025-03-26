import json

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

db = SQLAlchemy()


class Doc(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # Auto-increment ID
    title = db.Column(db.String(255), unique=True, nullable=False)  # Ensure unique title
    text = db.Column(db.Text, nullable=False)
    human_readable = db.Column(db.String(255), nullable=True)  # Add human-readable name
    lines = db.relationship("Line", backref="doc", cascade="all, delete-orphan", lazy=True)

    @property
    def displayable_title(self):
        return self.human_readable if self.human_readable else self.title

    @property
    def validation_percentage(self):
        # Total number of lines in the document
        total_lines = db.session.query(func.count(Line.id)).filter(Line.doc_id == self.id).scalar()
        # Number of validated lines
        validated_lines = db.session.query(func.count(Line.id)).filter(Line.doc_id == self.id,
                                                                       Line.status == "Validated").scalar()

        # Calculate the validation percentage
        return round((validated_lines / total_lines * 100) if total_lines > 0 else 0.0, 1)


class Line(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # Auto-increment ID
    start = db.Column(db.Integer, nullable=False)
    canonical = db.Column(db.Text, nullable=False)
    normalized = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default="Pending")
    merge = db.Column(db.Boolean, default=False)
    doc_id = db.Column(db.Integer, db.ForeignKey("doc.id"), nullable=False)  # Relationship to Doc

    @property
    def status_css(self):
        if self.status.lower() == "validated":
            return "table-success"
        else:
            return "table-pending"

    @property
    def length(self):
        return len(self.canonical)

    @property
    def end(self):
        return len(self.canonical) + self.start

    def update_from_dict(self, data):
        """Update the Line object from a dictionary."""
        self.normalized = data.get("normalized", self.normalized)
        self.merge = data.get("merge", self.merge)
        self.status = data.get("status", self.status)


def import_jsonl_stream(file_stream):
    with app.app_context():
        for line in file_stream:
            j = json.loads(line)

            # Check if document already exists
            existing_doc = Doc.query.filter_by(title=j["id"]).first()
            if existing_doc:
                yield f"Document with ID {j['id']} already exists. Skipping...", "warning", "bold"
                continue  # Skip if it exists

            # Create and insert new document
            new_doc = Doc(title=j["id"], text=j["text"])
            db.session.add(new_doc)
            db.session.commit()  # Save to get an ID
            yield f"Document {j['id']} created successfully.", "success", "bold"

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
                        yield f"Uncovered line added at position {last_end} for `{uncovered_text}`", "warning", ""

                # Add actual mapped line
                new_line = Line(start=start, canonical=canonical, normalized=normalized, doc_id=new_doc.id)
                db.session.add(new_line)
                last_end = start + len(canonical)  # Update last_end
                yield f"Line added: {canonical}", "info", ""

            # Handle remaining text at the end
            if last_end < len(j["text"]) and j["text"][last_end:].strip():
                trailing_line = Line(
                    start=last_end, canonical=j["text"][last_end:], normalized="", doc_id=new_doc.id
                )
                db.session.add(trailing_line)
                yield f"Uncovered line added at position {last_end} for `{uncovered_text}`", "warning", ""

            db.session.commit()  # Save all lines
            yield f"Document {j['id']} import completed.", "success", ""
