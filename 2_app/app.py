import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, make_response, g, session
from flask_bcrypt import Bcrypt
from flask_session import Session
from functools import wraps

# Setup logging
logging.basicConfig(level=logging.DEBUG)

# Initialize Flask app
app = Flask(__name__, template_folder="templates")

# Configure session
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Initialize Bcrypt for password hashing
bcrypt = Bcrypt(app)

# Admin-required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        
        # Check if the user is an admin
        with get_users_db() as db:
            cur = db.cursor()
            cur.execute("SELECT is_admin FROM users WHERE id = ?", (session["user_id"],))
            user = cur.fetchone()
            if user["is_admin"] != 1:
                return redirect(url_for("index"))  # Redirect if not admin
        return f(*args, **kwargs)
    return decorated_function

# Database connection functions
def get_users_db():
    db = getattr(g, '_users_database', None)
    if db is None:
        db = g._users_database = sqlite3.connect('users.db')
        db.row_factory = sqlite3.Row
    return db

def get_polls_db():
    db = getattr(g, '_polls_database', None)
    if db is None:
        db = g._polls_database = sqlite3.connect('polls.db')
        db.row_factory = sqlite3.Row
    return db

def get_votes_db():
    db = getattr(g, '_votes_database', None)
    if db is None:
        db = g._votes_database = sqlite3.connect('votes.db')
        db.row_factory = sqlite3.Row
    return db

# Close all database connections after each request
@app.teardown_appcontext
def close_connections(exception):
    for db_name in ['_users_database', '_polls_database', '_votes_database']:
        conn = getattr(g, db_name, None)
        if conn is not None:
            conn.close()

# Ensure the tables are initialized
initialized = False

@app.before_request
def initialize_tables():
    global initialized
    if not initialized:
        # Initialize users table in users.db
        with get_users_db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT NOT NULL UNIQUE,
                            password TEXT NOT NULL,
                            is_admin INTEGER DEFAULT 0)''')
            db.commit()

        # Initialize polls and related tables in polls.db
        with get_polls_db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS polls (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            poll TEXT NOT NULL,
                            creator_username TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS options (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            poll_id INTEGER NOT NULL,
                            option_text TEXT NOT NULL,
                            votes INTEGER DEFAULT 0,
                            FOREIGN KEY (poll_id) REFERENCES polls(id))''')

            # Create the comments table
            db.execute('''CREATE TABLE IF NOT EXISTS comments (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            poll_id INTEGER NOT NULL,
                            username TEXT NOT NULL,
                            comment TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            parent_comment_id INTEGER,
                            FOREIGN KEY (poll_id) REFERENCES polls(id))''')
            db.commit()

        initialized = True

# Routes

# Home route (index)
@app.route("/")
def index():
    cur = get_polls_db().cursor()
    cur.execute("SELECT * FROM polls")
    polls = cur.fetchall()

    my_polls = []
    if "user_id" in session:
        cur.execute("SELECT * FROM polls WHERE creator_username = ?", (session["username"],))
        my_polls = cur.fetchall()

    return render_template("index.html", polls=polls, my_polls=my_polls)

# Registration route
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        with get_users_db() as db:
            cur = db.cursor()
            try:
                cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
                db.commit()
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                return "Username already exists. Please choose another."
    return render_template("register.html")

# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        with get_users_db() as db:
            cur = db.cursor()
            cur.execute("SELECT * FROM users WHERE username = ?", (username,))
            user = cur.fetchone()

            if user and bcrypt.check_password_hash(user["password"], password):
                session["user_id"] = user["id"]
                session["username"] = user["username"]

                # Redirect based on admin status
                if user["is_admin"] == 1:
                    return redirect(url_for("admin_dashboard"))
                else:
                    return redirect(url_for("index"))
            else:
                return "Invalid username or password."

    return render_template("login.html")

# Logout route
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# Poll details route
@app.route("/polls/<id>")
def polls(id):
    cur = get_polls_db().cursor()

    # Fetch the poll details
    cur.execute("SELECT * FROM polls WHERE id = ?", (id,))
    poll = cur.fetchone()

    # Fetch the options for the poll
    cur.execute("SELECT * FROM options WHERE poll_id = ?", (id,))
    options = cur.fetchall()

    # Fetch all comments and replies for the poll
    cur.execute("SELECT * FROM comments WHERE poll_id = ? ORDER BY created_at ASC", (id,))
    comments = cur.fetchall()

    if poll:
        return render_template("show_poll.html", poll=poll, options=options, comments=comments)
    else:
        return "Poll not found", 404



# Voting route
@app.route("/vote/<id>/<option_id>")
def vote(id, option_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.cookies.get(f"vote_{id}_cookie") is None:
        with get_polls_db() as db:
            cur = db.cursor()
            cur.execute("SELECT * FROM options WHERE id = ? AND poll_id = ?", (option_id, id))
            option = cur.fetchone()

            if option:
                cur.execute("UPDATE options SET votes = votes + 1 WHERE id = ?", (option_id,))
                db.commit()

                response = make_response(redirect(url_for("polls", id=id)))
                response.set_cookie(f"vote_{id}_cookie", str(option_id))
                return response
            return "Invalid option", 400
    return f"Cannot vote more than once! Go back <a href='{url_for('polls', id=id)}'>here</a>"

# Create poll route
@app.route("/polls", methods=["GET", "POST"])
def create_poll():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        poll = request.form["poll"]
        options = request.form.getlist("options[]")
        creator_username = session["username"]

        with get_polls_db() as db:
            cur = db.cursor()
            cur.execute("INSERT INTO polls (poll, creator_username) VALUES (?, ?)", (poll, creator_username))
            poll_id = cur.lastrowid

            for option in options:
                cur.execute("INSERT INTO options (poll_id, option_text) VALUES (?, ?)", (poll_id, option))

            db.commit()

        return redirect(url_for("index"))

    return render_template("new_poll.html")

# Route for viewing a user's polls
@app.route("/my_polls")
def my_polls():
    if "user_id" not in session:
        return redirect(url_for("login"))

    creator_username = session["username"]
    cur = get_polls_db().cursor()
    cur.execute("SELECT * FROM polls WHERE creator_username = ?", (creator_username,))
    polls = cur.fetchall()

    return render_template("my_polls.html", polls=polls)

# Add comment to poll route
@app.route("/add_comment/<int:poll_id>", methods=["POST"])
def add_comment(poll_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    comment_text = request.form["comment"]
    username = session["username"]

    with get_polls_db() as db:
        cur = db.cursor()
        cur.execute("INSERT INTO comments (poll_id, username, comment) VALUES (?, ?, ?)", (poll_id, username, comment_text))
        db.commit()

    return redirect(url_for("polls", id=poll_id))


# Add reply to comment route
@app.route("/add_reply/<int:poll_id>/<int:parent_comment_id>", methods=["POST"])
def add_reply(poll_id, parent_comment_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    reply_text = request.form["reply"]
    username = session["username"]

    with get_polls_db() as db:
        cur = db.cursor()
        cur.execute("INSERT INTO comments (poll_id, username, comment, parent_comment_id) VALUES (?, ?, ?, ?)",
                    (poll_id, username, reply_text, parent_comment_id))
        db.commit()

    return redirect(url_for("polls", id=poll_id))



# Admin dashboard
@app.route("/admin")
@admin_required
def admin_dashboard():
    # Fetch all polls
    cur = get_polls_db().cursor()
    cur.execute("SELECT * FROM polls")
    polls = cur.fetchall()

    # Fetch all users
    cur = get_users_db().cursor()
    cur.execute("SELECT * FROM users")
    users = cur.fetchall()

    return render_template("admin_dashboard.html", polls=polls, users=users)

# Admin delete user route
@app.route("/admin/delete_user/<int:user_id>", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    if user_id == session["user_id"]:
        return redirect(url_for("admin_dashboard"))

    with get_users_db() as db:
        cur = db.cursor()
        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.commit()

    return redirect(url_for("admin_dashboard"))

# Admin delete poll route
@app.route("/admin/delete_poll/<int:poll_id>", methods=["POST"])
@admin_required
def delete_poll(poll_id):
    with get_polls_db() as db:
        cur = db.cursor()
        cur.execute("DELETE FROM polls WHERE id = ?", (poll_id,))
        cur.execute("DELETE FROM options WHERE poll_id = ?", (poll_id,))
        db.commit()
    return redirect(url_for("admin_dashboard"))

# 404 error handler
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

if __name__ == "__main__":
    app.run(host="localhost", debug=True)
