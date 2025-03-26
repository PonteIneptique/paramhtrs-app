from flask import Flask, render_template, request, jsonify, url_for, redirect, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, or_
import click
import io
import json
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import SubmitField


class UploadForm(FlaskForm):
    file = FileField("JSONL File", validators=[FileRequired()])
    submit = SubmitField('Submit')

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///data.db"  # Use SQLite for simplicity
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "RandomKey"
db = SQLAlchemy(app)


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


@app.route("/")
def home_route():
    return render_template("home.html")

@app.route("/document", methods=["GET"])
def documents_route():
    # Get the filter query from the request, if provided
    search_query = request.args.get('search', '')

    # Apply the search filter if there's a query, and order by title
    query = Doc.query.filter(or_(
        Doc.title.ilike(f'%{search_query}%'),
        Doc.human_readable.ilike(f"%{search_query}%")
    )).order_by(func.lower(Doc.human_readable), func.lower(Doc.title))

    # Set up pagination (e.g., 10 documents per page)
    page = request.args.get('page', 1, type=int)
    per_page = 20
    documents_paginated = query.paginate(page=page, per_page=per_page)

    # Pass the documents to the template
    return render_template(
        "docs.html",
        documents=documents_paginated.items,
        pagination=documents_paginated,
        search_query=search_query
    )


@app.route("/document/<int:doc_id>", methods=["POST"])
def document_route(doc_id):
    document = Doc.query.get_or_404(doc_id)
    # Try to capture and debug the incoming data
    data = request.get_json()  # This will parse the incoming JSON body
    if not data:
        return jsonify({"status": "error", "message": "No JSON data received"}), 400

    # Get the new name from the JSON data
    new_name = data.get("human_readable")

    if new_name:
        # Update the document's human_readable field
        document.human_readable = new_name
        db.session.commit()
        return jsonify({"status": "success"}), 200
    else:
        return jsonify({"status": "error", "message": "No 'human_readable' field provided"}), 400


@app.route("/document/<int:doc_id>/line/<int:line_id>", methods=["POST"])
def line_route(doc_id, line_id):
    try:
        data = request.get_json()

        line = Line.query.get(line_id)
        if not line:
            return jsonify({"status": "error", "message": "Line not found"}), 404

        # Update the line with new data
        line.update_from_dict(data)
        db.session.commit()

        return jsonify({"status": "success", "message": "Line updated successfully"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/document/<int:doc_id>/line") # Should deal with lines / page
def lines_route(doc_id):
    doc = Doc.query.get_or_404(doc_id)
    return render_template(
        "lines.html", lines=doc.lines, document=doc)


@app.route("/import", methods=["GET", "POST"])
def import_jsonl_route():
    form = UploadForm()

    if request.method == "POST" and form.validate_on_submit():
        file = form.file.data
        if file:
            # Convert the uploaded file into a BytesIO object
            file_stream = io.BytesIO(file.read())  # Read the file content into memory

            def generate():
                # Pass the file stream directly to the import function (no need for readlines)
                for message, cls, details in import_jsonl_stream(file_stream):
                    if details == "bold":
                        yield f"<div class='bg-{cls} text-dark bg-opacity-10' style='font-weight:bold;'>{message}</div><br>"
                    else:
                        yield f"<div class='bg-{cls} text-dark bg-opacity-10' style='font-size:smaller;'>{message}</div><br>"

            g = generate()
            return Response(g, content_type='text/html')

    return render_template("import.html", form=form)

@app.cli.group("db")
def db_group():
    return

@db_group.command("create")
def db_create():
    with app.app_context():
        db.create_all()
    click.echo("DB Created")

@db_group.command("reset")
def db_create():
    with app.app_context():
        db.drop_all()
        db.create_all()
    click.echo("DB Recreated")

@app.cli.command("import")
@click.argument("jsonl")
def import_(jsonl):
    with open(jsonl) as f:
        for x, *_ in import_jsonl_stream(f):
            print(x.strip())