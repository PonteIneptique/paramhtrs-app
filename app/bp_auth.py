from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from .db import User, db
from flask_login import LoginManager, login_required


login_manager = LoginManager()

bp_auth = Blueprint('bp_auth', __name__)


@bp_auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("bp_main.home_route"))

    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if user.is_approved:
                login_user(user)
                return redirect(url_for("bp_main.home_route"))
            else:
                flash("Account not approved by admin.", "danger")
        else:
            flash("Invalid username or password.", "danger")

    return render_template("login.html")


@bp_auth.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("bp_auth.login"))


@bp_auth.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user:
            flash("Username already taken.", "danger")
        else:
            new_user = User(username=username)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash("Account created. Waiting for admin approval.", "success")
            return redirect(url_for("bp_auth.login"))

    return render_template("register.html")

# Admin route to approve or reject users
@bp_auth.route("/admin/approve_user/<int:user_id>", methods=["POST"])
@login_required
def approve_user(user_id):
    if not current_user.is_admin:
        flash("You are not authorized to perform this action.", "danger")
        return redirect(url_for("bp_main.home_route"))

    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    flash(f"User {user.username} has been approved.", "success")
    return redirect(url_for("bp_main.home_route"))

# Admin route to reject users
@bp_auth.route("/admin/reject_user/<int:user_id>", methods=["POST"])
@login_required
def reject_user(user_id):
    if not current_user.is_admin:
        flash("You are not authorized to perform this action.", "danger")
        return redirect(url_for("bp_main.home_route"))

    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash(f"User {user.username} has been rejected.", "success")
    return redirect(url_for("bp_main.home_route"))


@bp_auth.route("/admin", methods=["GET"])
@login_required
def admin_panel():
    if not current_user.is_admin:
        flash("You are not authorized to access the admin panel.", "danger")
        return redirect(url_for("bp_auth.home_route"))

    # Query for users who are not approved yet
    unapproved_users = User.query.filter_by(is_approved=False).all()

    return render_template("admin.html", users=unapproved_users)

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
