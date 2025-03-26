from flask import Flask
import click

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///data.db"  # Use SQLite for simplicity
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "RandomKey"

from app.bp_app import bp_main
from .db import db, Doc, Line, import_jsonl_stream
from .forms import UploadForm

db.init_app(app)
app.register_blueprint(bp_main)

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