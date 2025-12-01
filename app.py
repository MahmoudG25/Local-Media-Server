import os
import re
import mimetypes
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from functools import wraps
import urllib.request
import urllib.error
from datetime import datetime
import queue

from flask import (
    Flask,
    request,
    Response,
    abort,
    render_template,
    send_from_directory,
    redirect,
    url_for,
)
from werkzeug.utils import secure_filename
from werkzeug.serving import make_server

# ================== إعدادات عامة ==================

app = Flask(__name__)

APP_CONFIG = {
    "base_dir": Path.cwd() / "files",
    "host": "0.0.0.0",
    "port": 4142,
    "password": "",  # فاضي = بدون باسورد
    "pending_dir_name": "_pending_uploads",
}

# Queue للتواصل بين Flask (thread) و Tkinter (main thread)
UPLOAD_REQUESTS = queue.Queue()

server_thread = None
server_running = False
srv = None

# ================== Helpers ==================

def get_base_dir() -> Path:
    return Path(APP_CONFIG["base_dir"]).resolve()

def get_pending_dir() -> Path:
    base = get_base_dir()
    pending = base / APP_CONFIG["pending_dir_name"]
    pending.mkdir(exist_ok=True)
    return pending.resolve()

def human_size(num_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"

def detect_type(mimetype: str) -> str:
    if not mimetype:
        return "other"
    if mimetype.startswith("video"):
        return "video"
    if mimetype.startswith("image"):
        return "image"
    if mimetype.startswith("audio"):
        return "audio"
    return "other"

def safe_rel_path(rel: str) -> Path:
    rel = rel.strip().replace("\\", "/")
    if rel in ("", ".", "/"):
        return Path(".")
    p = Path(rel)
    if ".." in p.parts:
        abort(400)
    return p

def get_dir_safe(rel: str) -> Path:
    base = get_base_dir()
    rel_path = safe_rel_path(rel)
    full = (base / rel_path).resolve()
    if not str(full).startswith(str(base)):
        abort(400)
    if not full.exists():
        abort(404)
    if not full.is_dir():
        abort(400)
    return full

def get_file_safe(rel: str) -> Path:
    base = get_base_dir()
    rel_path = Path(rel)
    if ".." in rel_path.parts:
        abort(400)
    full = (base / rel_path).resolve()
    if not str(full).startswith(str(base)):
        abort(400)
    # لا نسمح بالوصول لملفات pending كملفات نهائية
    pending_dir = get_pending_dir()
    if str(full).startswith(str(pending_dir)):
        abort(404)
    return full

def get_pending_file_safe(rel: str) -> Path:
    base = get_pending_dir()
    rel_path = Path(rel)
    if ".." in rel_path.parts:
        abort(400)
    full = (base / rel_path).resolve()
    if not str(full).startswith(str(base)):
        abort(400)
    return full

def list_dir(current_dir: Path):
    folders = []
    files = []
    for entry in sorted(current_dir.iterdir(), key=lambda p: p.name.lower()):
        if entry.is_dir():
            if entry.name == APP_CONFIG["pending_dir_name"]:
                continue
            items = sum(1 for _ in entry.iterdir())
            rel = entry.relative_to(get_base_dir())
            folders.append({
                "name": entry.name,
                "relpath": str(rel).replace("\\", "/"),
                "items_count": items,
            })
        else:
            stat = entry.stat()
            size = stat.st_size
            mtime = stat.st_mtime
            mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            rel = entry.relative_to(get_base_dir())
            mimetype, _ = mimetypes.guess_type(str(entry))
            ext = entry.suffix.lower().lstrip(".")
            ftype = detect_type(mimetype or "application/octet-stream")
            files.append({
                "name": entry.name,
                "relpath": str(rel).replace("\\", "/"),
                "size": size,
                "size_human": human_size(size),
                "mimetype": mimetype or "application/octet-stream",
                "ext": ext,
                "is_video": ftype == "video",
                "is_image": ftype == "image",
                "type": ftype,
                "mtime": mtime,
                "mtime_str": mtime_str,
            })
    return folders, files

def filter_sort_files(files, q, file_type, sort_by, order):
    if q:
        q_lower = q.lower()
        files = [f for f in files if q_lower in f["name"].lower()]
    if file_type != "all":
        files = [f for f in files if f["type"] == file_type]

    reverse = order == "desc"
    if sort_by == "size":
        key = lambda f: f["size"]
    elif sort_by == "mtime":
        key = lambda f: f["mtime"]
    else:
        key = lambda f: f["name"].lower()
    files.sort(key=key, reverse=reverse)
    return files

def list_pending_files():
    pending_dir = get_pending_dir()
    files = []
    for root, dirs, filenames in os.walk(pending_dir):
        for name in filenames:
            full = Path(root) / name
            rel = full.relative_to(pending_dir)
            stat = full.stat()
            size = stat.st_size
            mtime = stat.st_mtime
            mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            mimetype, _ = mimetypes.guess_type(str(full))
            ftype = detect_type(mimetype or "application/octet-stream")
            files.append({
                "relpath": str(rel).replace("\\", "/"),
                "size_human": human_size(size),
                "mtime": mtime,
                "mtime_str": mtime_str,
                "type": ftype,
            })
    files.sort(key=lambda f: f["mtime"], reverse=True)
    return files

def approve_pending_file(rel_inside_pending: str):
    """
    rel_inside_pending: المسار النسبي للملف داخل فولدر pending فقط
    مثال: subfolder/video.mp4
    """
    pending_root = get_pending_dir()
    pending_path = pending_root / rel_inside_pending
    pending_path = pending_path.resolve()
    if not pending_path.exists():
        return

    rel_inside = pending_path.relative_to(pending_root)
    dest = get_base_dir() / rel_inside
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix
        counter = 1
        while dest.exists():
            dest = dest.parent / f"{stem}_{counter}{suffix}"
            counter += 1

    pending_path.replace(dest)

def reject_pending_file(rel_inside_pending: str):
    pending_root = get_pending_dir()
    pending_path = (pending_root / rel_inside_pending).resolve()
    if pending_path.exists() and pending_path.is_file():
        pending_path.unlink()

def iter_file(path, start, end, chunk_size=1024 * 1024):
    with open(path, "rb") as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = f.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk

def is_admin_request() -> bool:
    # مدير السيرفر = متصفح شغال من نفس الجهاز (localhost)
    return request.remote_addr in ("127.0.0.1", "::1", "0:0:0:0:0:0:0:1")

# ================== Auth ==================

def check_auth(auth):
    pw = APP_CONFIG.get("password") or ""
    if not pw:
        return True
    if not auth:
        return False
    return auth.username == "user" and auth.password == pw

def authenticate():
    return Response(
        "Authentication required", 401,
        {"WWW-Authenticate": 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        pw = APP_CONFIG.get("password") or ""
        if not pw:
            return f(*args, **kwargs)
        auth = request.authorization
        if not check_auth(auth):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# ================== Routes ==================

@app.route("/", methods=["GET"])
@requires_auth
def index():
    current_rel = request.args.get("p", "").strip()
    q = request.args.get("q", "").strip()
    file_type = request.args.get("type", "all")
    sort_by = request.args.get("sort", "name")
    order = request.args.get("order", "asc")

    current_dir = get_dir_safe(current_rel)
    folders, files = list_dir(current_dir)
    files = filter_sort_files(files, q, file_type, sort_by, order)

    total_items = len(folders) + len(files)
    total_size = sum(f["size"] for f in files)
    total_size_human = human_size(total_size)

    # breadcrumbs
    rel_path = safe_rel_path(current_rel)
    breadcrumbs = []
    if str(rel_path) not in ("", "."):
        parts = list(rel_path.parts)
        acc = []
        for part in parts:
            acc.append(part)
            breadcrumbs.append({
                "name": part,
                "path": "/".join(acc),
            })

    pw_enabled = bool(APP_CONFIG.get("password"))
    is_admin = is_admin_request()
    pending_files = list_pending_files() if is_admin else []
    pending_count = len(pending_files)

    return render_template(
        "index.html",
        base_dir=str(get_base_dir()),
        current_rel=str(rel_path) if str(rel_path) != "." else "",
        breadcrumbs=breadcrumbs,
        folders=folders,
        files=files,
        q=q,
        file_type=file_type,
        sort_by=sort_by,
        order=order,
        total_items=total_items,
        total_size_human=total_size_human,
        pw_enabled=pw_enabled,
        is_admin=is_admin,
        pending_files=pending_files,
        pending_count=pending_count,
    )

@app.route("/player/<path:filename>")
@requires_auth
def stream_page(filename):
    full_path = get_file_safe(filename)
    if not full_path.exists():
        abort(404)
    mimetype, _ = mimetypes.guess_type(str(full_path))
    return render_template(
        "player.html",
        name=full_path.name,
        relpath=filename,
        mimetype=mimetype or "video/mp4"
    )

@app.route("/download/<path:filename>")
@requires_auth
def download_file(filename):
    full_path = get_file_safe(filename)
    if not full_path.exists():
        abort(404)
    return send_from_directory(
        directory=get_base_dir(),
        path=filename,
        as_attachment=True
    )

@app.route("/stream/<path:filename>")
@requires_auth
def stream_file(filename):
    full_path = get_file_safe(filename)
    if not full_path.exists():
        abort(404)

    file_size = full_path.stat().st_size
    range_header = request.headers.get("Range", None)
    mimetype, _ = mimetypes.guess_type(str(full_path))
    mimetype = mimetype or "application/octet-stream"

    if range_header:
        match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if not match:
            return Response(status=416)
        start = int(match.group(1))
        end_str = match.group(2)
        end = int(end_str) if end_str else file_size - 1
        if start >= file_size:
            return Response(status=416)
        end = min(end, file_size - 1)
        content_length = end - start + 1
        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
        }
        return Response(
            iter_file(full_path, start, end),
            status=206,
            headers=headers,
            mimetype=mimetype,
        )

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
    }
    return Response(
        iter_file(full_path, 0, file_size - 1),
        status=200,
        headers=headers,
        mimetype=mimetype,
    )

@app.route("/upload", methods=["POST"])
@requires_auth
def upload():
    if "files" not in request.files:
        return redirect(url_for("index"))

    current_rel = request.form.get("p", "").strip()
    _ = get_dir_safe(current_rel)  # للتأكد إنه فولدر صالح

    files = request.files.getlist("files")
    pending_root = get_pending_dir()
    target_rel = safe_rel_path(current_rel)  # Path(".") لو الروت
    pending_target_dir = (pending_root / target_rel)
    pending_target_dir.mkdir(parents=True, exist_ok=True)

    saved_relpaths_inside_pending = []  # مسارات الملفات داخل pending_root
    original_names = []

    for file in files:
        if not file or not file.filename:
            continue
        filename = secure_filename(file.filename)
        if not filename:
            continue
        save_path = pending_target_dir / filename
        if save_path.exists():
            stem = save_path.stem
            suffix = save_path.suffix
            counter = 1
            while save_path.exists():
                save_path = pending_target_dir / f"{stem}_{counter}{suffix}"
                counter += 1
        file.save(save_path)

        rel_inside_pending = save_path.relative_to(pending_root)
        saved_relpaths_inside_pending.append(str(rel_inside_pending).replace("\\", "/"))
        original_names.append(filename)

    # لو فيه فعلاً ملفات اترفعت، نبعت Notification للـ GUI
    if saved_relpaths_inside_pending:
        upload_info = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "target_folder": current_rel or "/",
            "pending_relpaths": saved_relpaths_inside_pending,
            "display_names": original_names,
            "client_ip": request.remote_addr,
        }
        try:
            UPLOAD_REQUESTS.put_nowait(upload_info)
        except queue.Full:
            pass

    return redirect(url_for("index", p=current_rel))

@app.route("/approve/<path:filename>", methods=["POST"])
@requires_auth
def approve_file(filename):
    if not is_admin_request():
        abort(403)
    approve_pending_file(filename)  # filename هنا المسار داخل pending_root
    return redirect(url_for("index"))

@app.route("/reject/<path:filename>", methods=["POST"])
@requires_auth
def reject_file(filename):
    if not is_admin_request():
        abort(403)
    reject_pending_file(filename)
    return redirect(url_for("index"))

@app.route("/delete/<path:filename>", methods=["POST"])
@requires_auth
def delete_file(filename):
    if not is_admin_request():
        abort(403)
    current_rel = request.args.get("p", "").strip()
    full_path = get_file_safe(filename)
    if full_path.exists() and full_path.is_file():
        full_path.unlink()
    return redirect(url_for("index", p=current_rel))

# ================== تشغيل Flask في Thread ==================

def run_flask():
    global server_running, srv
    server_running = True
    srv = make_server(APP_CONFIG["host"], APP_CONFIG["port"], app, threaded=True)
    ctx = app.app_context()
    ctx.push()
    try:
        srv.serve_forever()
    except Exception:
        pass
    finally:
        server_running = False

# ================== GUI بـ Tkinter ==================

class MediaServerGUI:
    def __init__(self, root):
        self.root = root
        root.title("Local Media Server")
        root.geometry("520x300")
        root.resizable(False, False)

        tk.Label(root, text="Folder path:", anchor="w").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.folder_var = tk.StringVar(value=str(APP_CONFIG["base_dir"]))
        self.folder_entry = tk.Entry(root, textvariable=self.folder_var, width=40)
        self.folder_entry.grid(row=0, column=1, padx=5, pady=10, sticky="w")
        tk.Button(root, text="Browse", command=self.browse_folder).grid(row=0, column=2, padx=5, pady=10)

        tk.Label(root, text="Host / IP:", anchor="w").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.host_var = tk.StringVar(value=APP_CONFIG["host"])
        tk.Entry(root, textvariable=self.host_var, width=20).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        tk.Label(root, text="Port:", anchor="w").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.port_var = tk.StringVar(value=str(APP_CONFIG["port"]))
        tk.Entry(root, textvariable=self.port_var, width=10).grid(row=2, column=1, padx=5, pady=5, sticky="w")

        tk.Label(root, text="Password (Basic Auth):", anchor="w").grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.pw_var = tk.StringVar(value=APP_CONFIG["password"])
        tk.Entry(root, textvariable=self.pw_var, width=20, show="*").grid(row=3, column=1, padx=5, pady=5, sticky="w")

        hint = "لو حطيت باسورد: username = user\nلو سبتها فاضية: الدخول بدون باسورد."
        tk.Label(root, text=hint, fg="gray").grid(row=4, column=0, columnspan=3, padx=10, pady=5, sticky="w")

        self.start_btn = tk.Button(root, text="Start Server", command=self.start_server, bg="#22c55e", fg="white")
        self.start_btn.grid(row=5, column=0, padx=10, pady=15, sticky="we")

        self.stop_btn = tk.Button(root, text="Stop Server", command=self.stop_server, bg="#ef4444", fg="white")
        self.stop_btn.grid(row=5, column=1, padx=10, pady=15, sticky="we")

        self.status_var = tk.StringVar(value="Server status: stopped")
        tk.Label(root, textvariable=self.status_var, fg="blue").grid(row=6, column=0, columnspan=3, padx=10, sticky="w")

        self.url_var = tk.StringVar(value="")
        tk.Label(root, textvariable=self.url_var, fg="green").grid(row=7, column=0, columnspan=3, padx=10, sticky="w")

        # لوب حالة السيرفر
        self.update_status_loop()
        # مراقبة طلبات الرفع القادمة من Flask
        self.check_upload_requests()

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_var.set(folder)

    def start_server(self):
        global server_thread, server_running

        if server_running:
            messagebox.showinfo("Info", "السيرفر شغّال بالفعل.")
            return

        folder = self.folder_var.get().strip()
        host = self.host_var.get().strip()
        port_str = self.port_var.get().strip()
        pw = self.pw_var.get()

        if not folder:
            messagebox.showerror("Error", "اختار فولدر الملفات أولاً.")
            return

        try:
            port = int(port_str)
        except ValueError:
            messagebox.showerror("Error", "البورت لازم يكون رقم صحيح.")
            return

        base_dir = Path(folder)
        if not base_dir.exists() or not base_dir.is_dir():
            messagebox.showerror("Error", "مسار الفولدر غير صحيح.")
            return

        APP_CONFIG["base_dir"] = base_dir
        APP_CONFIG["host"] = host or "0.0.0.0"
        APP_CONFIG["port"] = port
        APP_CONFIG["password"] = pw or ""

        base_dir.mkdir(exist_ok=True)
        get_pending_dir()

        server_thread = threading.Thread(target=run_flask, daemon=True)
        server_thread.start()

        self.status_var.set("Server status: starting...")
        url_display = f"http://{host or '127.0.0.1'}:{port}"
        self.url_var.set(f"Open in browser: {url_display}")

    def stop_server(self):
        global server_running, srv

        if not server_running:
            messagebox.showinfo("Info", "السيرفر بالفعل متوقف.")
            return

        if srv:
            srv.shutdown()

        self.status_var.set("Server status: stopping...")

    def update_status_loop(self):
        global server_running
        if server_running:
            self.status_var.set("Server status: running")
        else:
            self.status_var.set("Server status: stopped")
        self.root.after(500, self.update_status_loop)

    def check_upload_requests(self):
        """
        تراقب UPLOAD_REQUESTS Queue من ثريد Flask
        وكل طلب جديد يطلع له popup
        """
        try:
            while True:
                info = UPLOAD_REQUESTS.get_nowait()
                self.show_upload_dialog(info)
        except queue.Empty:
            pass

        self.root.after(500, self.check_upload_requests)

    def show_upload_dialog(self, info: dict):
        """
        info:
          - time
          - target_folder
          - pending_relpaths
          - display_names
          - client_ip
        """
        win = tk.Toplevel(self.root)
        win.title("New upload request")
        win.resizable(False, False)
        win.attributes("-topmost", True)

        container = tk.Frame(win)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        tk.Label(
            container,
            text="New upload request",
            font=("Segoe UI", 11, "bold")
        ).pack(pady=(0, 4), anchor="w")

        folder_text = info.get("target_folder") or "/"
        client_ip = info.get("client_ip") or "Unknown"
        time_str = info.get("time") or ""

        tk.Label(
            container,
            text=f"From: {client_ip}",
            anchor="w"
        ).pack(pady=1, anchor="w")

        tk.Label(
            container,
            text=f"Folder: {folder_text}",
            anchor="w"
        ).pack(pady=1, anchor="w")

        if time_str:
            tk.Label(
                container,
                text=f"Time: {time_str}",
                anchor="w",
                fg="gray"
            ).pack(pady=(0, 6), anchor="w")

        tk.Label(container, text="Files:", anchor="w").pack(pady=(4, 2), anchor="w")

        # قللنا الارتفاع عشان يفضل في مساحة للأزرار
        listbox = tk.Listbox(container, height=4, width=50)
        listbox.pack(pady=2, fill="both", expand=True)

        for name in info.get("display_names", []):
            listbox.insert(tk.END, name)

        btn_frame = tk.Frame(container)
        btn_frame.pack(pady=8, anchor="e")

        def do_approve():
            for rel in info.get("pending_relpaths", []):
                approve_pending_file(rel)
            win.destroy()
            messagebox.showinfo("Approved", "Files approved and moved to main folder.")

        def do_reject():
            if not messagebox.askyesno("Confirm", "Reject and delete these files?"):
                return
            for rel in info.get("pending_relpaths", []):
                reject_pending_file(rel)
            win.destroy()
            messagebox.showinfo("Rejected", "Files were rejected and deleted.")

        tk.Button(
            btn_frame,
            text="Approve",
            command=do_approve,
            bg="#22c55e",
            fg="white",
            width=10
        ).pack(side="left", padx=5)

        tk.Button(
            btn_frame,
            text="Reject",
            command=do_reject,
            bg="#ef4444",
            fg="white",
            width=10
        ).pack(side="left", padx=5)

        # خليه يظبط الحجم بعد ما كل الـ widgets تتعمل
        win.update_idletasks()
        win.minsize(win.winfo_width(), win.winfo_height())

# ================== Main ==================

if __name__ == "__main__":
    root = tk.Tk()
    app_gui = MediaServerGUI(root)
    root.mainloop()
