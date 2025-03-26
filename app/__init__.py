from email.policy import default

from flask import Flask
import click

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///data.db"  # Use SQLite for simplicity
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "RandomKey"

from .bp_main import bp_main
from .bp_auth import bp_auth, login_manager
from .db import db, Doc, Line, import_jsonl_stream, User
from .forms import UploadForm

db.init_app(app)
login_manager.init_app(app)
app.register_blueprint(bp_main)
app.register_blueprint(bp_auth)

@app.cli.group("db")
def db_group():
    return

@db_group.command("create")
@click.option("--admin/--no-admin", is_flag=True, default=True)
@click.option("--admin-name", type=str, default="admin")
@click.option("--admin-password", type=str, default="qwerty")
def db_create(admin, admin_name, admin_password):
    with app.app_context():
        db.create_all()
        click.echo("DB Created")
        if admin:
            admin = User(username=admin_name, is_admin=True, is_approved=True)
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
            click.echo("Admin created")


@db_group.command("reset")
def db_create():
    with app.app_context():
        db.drop_all()
        db.create_all()
    click.echo("DB Recreated")

@db_group.command("drop")
def db_create():
    with app.app_context():
        db.drop_all()
    click.echo("DB Dropped")

@app.cli.command("import")
@click.argument("jsonl")
def import_(jsonl):
    with open(jsonl) as f:
        for x, *_ in import_jsonl_stream(f):
            print(x.strip())