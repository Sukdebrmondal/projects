"""
app.py
Flask web application for the Question Paper Leak Detection System.

Run locally (from the project root):
    python app.py
Then open http://127.0.0.1:5000 in the browser.
"""
import base64
import io
import os
import secrets
import zipfile
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from PIL import Image, UnidentifiedImageError
from werkzeug.security import check_password_hash

import database as db
from core import STATUS_NO_DATA, STATUS_TAMPERED, STATUS_VALID, create_copy, verify_copy
from crypto_utils import KEY_SIZE, load_private_key, load_public_key
from stego import capacity_bytes, load_image, save_image

# ---------------- Configuration ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATED_DIR = os.path.join(BASE_DIR, "generated")    # ZIP files of copies

MAX_UPLOAD_MB = 10
MAX_CENTRES = 50
MAX_NAME_LENGTH = 100
MIN_CAPACITY_BYTES = 2048                              # image must hold the payload easily

GENERATE_EXTENSIONS = {".png"}
VERIFY_EXTENSIONS = {".png", ".jpg", ".jpeg"}

# How each verification status looks on the page (Bootstrap colour, icon, title)
STATUS_UI = {
    STATUS_VALID: {
        "color": "success",
        "icon": "bi-check-circle-fill",
        "title": "Genuine copy - source identified",
    },
    STATUS_TAMPERED: {
        "color": "warning",
        "icon": "bi-exclamation-triangle-fill",
        "title": "Tampered copy - this data cannot be trusted",
    },
    STATUS_NO_DATA: {
        "color": "danger",
        "icon": "bi-x-circle-fill",
        "title": "No hidden data found",
    },
}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

# ---------------- Startup ----------------
db.init_db()
os.makedirs(GENERATED_DIR, exist_ok=True)

try:
    PRIVATE_KEY = load_private_key()
    PUBLIC_KEY = load_public_key()
except (FileNotFoundError, ValueError) as exc:
    raise SystemExit("RSA keys missing or broken. Run 'python setup_keys.py' first.") from exc


# ---------------- Security helpers ----------------
def login_required(view):
    """Send visitors to the login page if they are not logged in as admin."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            flash("Please log in as admin first.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


def get_csrf_token() -> str:
    """A random secret per session, placed in every delete form."""
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_hex(16)
        session["csrf_token"] = token
    return token


def csrf_ok() -> bool:
    """True only if the form sent back the same secret that is in the session."""
    sent = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    return bool(sent) and bool(expected) and secrets.compare_digest(sent, expected)


@app.context_processor
def inject_csrf_token():
    """Lets templates call {{ csrf_token() }}."""
    return {"csrf_token": get_csrf_token}


# ---------------- Helpers ----------------
def get_extension(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower()


def read_uploaded_image(field: str, allowed: set):
    """Read an uploaded image. Returns (pixels, filename, error_message)."""
    file = request.files.get(field)
    if file is None or file.filename == "":
        return None, None, "Please choose an image file."

    if get_extension(file.filename) not in allowed:
        return None, file.filename, (
            "Unsupported file type. Allowed: " + ", ".join(sorted(allowed))
        )

    try:
        pixels = load_image(file.stream)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return None, file.filename, "This file is not a valid image."

    return pixels, file.filename, None


def clean_text(text: str) -> str:
    """Remove extra spaces."""
    return " ".join((text or "").split())


def parse_centres(text: str) -> list:
    """One centre per line; skip blank lines and duplicates, keep the order."""
    seen, centres = set(), []
    for line in (text or "").splitlines():
        name = clean_text(line)
        if name and name.lower() not in seen:
            seen.add(name.lower())
            centres.append(name)
    return centres


def build_copy_id(paper_id: int, centre_id: int) -> str:
    """Example: year 2026, paper 1, centre 3 -> 'QP-26-P001-C03'."""
    return f"QP-{datetime.now():%y}-P{paper_id:03d}-C{centre_id:02d}"


def zip_path(paper_id: int) -> str:
    return os.path.join(GENERATED_DIR, f"paper_{paper_id:03d}.zip")


def delete_zip(paper_id: int):
    """Remove a paper's ZIP file if it exists."""
    path = zip_path(paper_id)
    if os.path.exists(path):
        os.remove(path)


def remove_from_zip(paper_id: int, copy_id: str):
    """
    Remove one copy from a paper's ZIP.
    ZIP files cannot delete an entry in place, so the ZIP is rewritten
    without that file and then swapped in.
    """
    path = zip_path(paper_id)
    if not os.path.exists(path):
        return

    target = f"{copy_id}.png"
    temp_path = path + ".tmp"
    with zipfile.ZipFile(path) as src, \
            zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            if item.filename != target:
                dst.writestr(item, src.read(item.filename))
    os.replace(temp_path, path)


def make_thumbnail(pixels, max_size: int = 480) -> str:
    """Small JPEG preview of the image as a data URL, for showing on the page."""
    img = Image.fromarray(pixels)
    img.thumbnail((max_size, max_size))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


# ---------------- Public pages ----------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/verify", methods=["GET", "POST"])
def verify():
    if request.method == "GET":
        return render_template("verify.html")

    pixels, filename, error = read_uploaded_image("image", VERIFY_EXTENSIONS)
    if error:
        flash(error, "danger")
        return render_template("verify.html")

    result = verify_copy(pixels, PUBLIC_KEY)

    # For genuine copies, also check whether this copy exists in our records
    record = None
    if result["status"] == STATUS_VALID:
        record = db.get_copy(str(result["payload"].get("copy_id", "")))

    return render_template(
        "verify.html",
        result=result,
        ui=STATUS_UI[result["status"]],
        filename=filename,
        is_jpeg=get_extension(filename) in {".jpg", ".jpeg"},
        record=record,
        key_size=KEY_SIZE,
        preview=make_thumbnail(pixels),
    )


# ---------------- Login / logout ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = db.get_admin(username)

        if admin and check_password_hash(admin["password_hash"], password):
            session.clear()
            session["admin"] = admin["username"]
            flash(f"Welcome, {admin['username']}.", "success")

            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)          # only local pages, for safety
            return redirect(url_for("generate"))

        flash("Wrong username or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------- Admin pages ----------------
@app.route("/generate", methods=["GET", "POST"])
@login_required
def generate():
    if request.method == "GET":
        return render_template("generate.html", form=request.form)

    def form_error(message):
        flash(message, "danger")
        return render_template("generate.html", form=request.form)

    # ---- Validate the form ----
    paper_name = clean_text(request.form.get("paper_name"))
    centres = parse_centres(request.form.get("centres"))

    if not paper_name:
        return form_error("Enter the paper name.")
    if len(paper_name) > MAX_NAME_LENGTH:
        return form_error(f"Paper name must be at most {MAX_NAME_LENGTH} characters.")
    if not centres:
        return form_error("Enter at least one exam centre (one per line).")
    if len(centres) > MAX_CENTRES:
        return form_error(f"At most {MAX_CENTRES} centres are allowed at once.")
    if any(len(name) > MAX_NAME_LENGTH for name in centres):
        return form_error(f"Each centre name must be at most {MAX_NAME_LENGTH} characters.")

    pixels, filename, error = read_uploaded_image("paper", GENERATE_EXTENSIONS)
    if error:
        return form_error(error)
    if capacity_bytes(pixels) < MIN_CAPACITY_BYTES:
        return form_error("The image is too small to hide the data. Use a larger PNG.")

    # ---- Create one signed copy per centre and pack them into a ZIP ----
    paper_id = db.add_paper(paper_name, filename)
    results = []

    with zipfile.ZipFile(zip_path(paper_id), "w", zipfile.ZIP_DEFLATED) as zf:
        for centre_name in centres:
            centre_id = db.get_or_create_centre(centre_name)
            copy_id = build_copy_id(paper_id, centre_id)

            stego_pixels, payload = create_copy(
                pixels, centre_id, centre_name, copy_id, paper_name, PRIVATE_KEY
            )

            buffer = io.BytesIO()
            save_image(stego_pixels, buffer)
            zf.writestr(f"{copy_id}.png", buffer.getvalue())

            db.add_copy(copy_id, paper_id, centre_id,
                        payload["image_hash"], payload["created_at"])
            results.append({
                "copy_id": copy_id,
                "centre_id": centre_id,
                "centre_name": centre_name,
            })

    flash(f"{len(results)} signed copies created.", "success")
    return render_template(
        "generate.html",
        form=request.form,
        results=results,
        paper_id=paper_id,
        paper_name=paper_name,
        preview=make_thumbnail(pixels),
    )


@app.route("/download/<int:paper_id>")
@login_required
def download(paper_id):
    path = zip_path(paper_id)
    if not os.path.exists(path):
        flash("That ZIP file was not found. Please create the copies again.", "danger")
        return redirect(url_for("generate"))
    return send_file(path, mimetype="application/zip", as_attachment=True,
                     download_name=f"QP-P{paper_id:03d}-copies.zip")


@app.route("/records")
@login_required
def records():
    return render_template("records.html", copies=db.list_copies())


@app.route("/records/copy/<copy_id>/delete", methods=["POST"])
@login_required
def delete_copy_record(copy_id):
    """Delete one copy from the database and from its paper's ZIP."""
    if not csrf_ok():
        flash("The request expired. Please refresh the page and try again.", "danger")
        return redirect(url_for("records"))

    paper_id, paper_removed = db.delete_copy(copy_id)
    if paper_id is None:
        flash("That record was not found. It may already be deleted.", "warning")
    else:
        if paper_removed:
            delete_zip(paper_id)                   # last copy gone: remove the whole ZIP
        else:
            remove_from_zip(paper_id, copy_id)
        flash(f"Record {copy_id} was deleted.", "success")

    return redirect(url_for("records"))


@app.route("/records/paper/<int:paper_id>/delete", methods=["POST"])
@login_required
def delete_paper_record(paper_id):
    """Delete a paper, all of its copies and its ZIP file."""
    if not csrf_ok():
        flash("The request expired. Please refresh the page and try again.", "danger")
        return redirect(url_for("records"))

    deleted = db.delete_paper(paper_id)
    delete_zip(paper_id)

    if deleted:
        flash(f"Paper P{paper_id:03d} and its {deleted} copies were deleted.", "success")
    else:
        flash("That paper was not found. It may already be deleted.", "warning")

    return redirect(url_for("records"))


# ---------------- Error pages ----------------
@app.errorhandler(413)
def file_too_large(_error):
    flash(f"File is too large. Maximum size is {MAX_UPLOAD_MB} MB.", "danger")
    return redirect(request.url)


@app.errorhandler(404)
def page_not_found(_error):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True)