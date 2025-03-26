from flask import Blueprint, render_template, request, jsonify, Response, stream_with_context
from sqlalchemy import func, or_
import io

from .db import db, Doc, Line, import_jsonl_stream
from .forms import UploadForm
from flask_login import login_required

bp_main = Blueprint("bp_main", __name__)


@bp_main.route("/")
def home_route():
    return render_template("home.html")

@bp_main.route("/document", methods=["GET"])
@login_required
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


@bp_main.route("/document/<int:doc_id>", methods=["POST"])
@login_required
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


@bp_main.route("/document/<int:doc_id>/line/<int:line_id>", methods=["POST"])
@login_required
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


@bp_main.route("/document/<int:doc_id>/line") # Should deal with lines / page
@login_required
def lines_route(doc_id):
    doc = Doc.query.get_or_404(doc_id)
    return render_template(
        "lines.html", lines=doc.lines, document=doc)


@bp_main.route("/import", methods=["GET", "POST"])
@login_required
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

            return Response(stream_with_context(generate()), content_type='text/html')

    return render_template("import.html", form=form)
