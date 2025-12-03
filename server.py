import re
import mimetypes
import threading
from datetime import datetime
from pathlib import Path
from functools import wraps

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
from PySide6.QtCore import QThread, Signal, QObject

from config import AppConfig
import utils

class ServerSignals(QObject):
    """Signals for communication between Flask and GUI."""
    upload_request = Signal(dict)

class ServerThread(QThread):
    """Thread to run the Flask server."""
    def __init__(self, config: AppConfig, signals: ServerSignals):
        super().__init__()
        self.config = config
        self.signals = signals
        self.server = None
        self.app = self.create_app()
        self.ctx = self.app.app_context()

    def create_app(self):
        app = Flask(__name__)
        
        # Pass config and signals to app context if needed, 
        # but using closures/methods is easier here.
        
        # ================== Auth ==================
        def check_auth(auth):
            pw = self.config.password
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
                pw = self.config.password
                if not pw:
                    return f(*args, **kwargs)
                auth = request.authorization
                if not check_auth(auth):
                    return authenticate()
                return f(*args, **kwargs)
            return decorated

        def is_admin_request() -> bool:
            return request.remote_addr in ("127.0.0.1", "::1", "0:0:0:0:0:0:1")

        # ================== Routes ==================
        @app.route("/", methods=["GET"])
        @requires_auth
        def index():
            current_rel = request.args.get("p", "").strip()
            q = request.args.get("q", "").strip()
            file_type = request.args.get("type", "all")
            sort_by = request.args.get("sort", "name")
            order = request.args.get("order", "asc")

            try:
                current_dir = utils.get_dir_safe(self.config, current_rel)
            except Exception:
                abort(404)

            folders, files = utils.list_dir(self.config, current_dir)
            files = utils.filter_sort_files(files, q, file_type, sort_by, order)

            total_items = len(folders) + len(files)
            total_size = sum(f["size"] for f in files)
            total_size_human = utils.human_size(total_size)

            # Breadcrumbs
            rel_path = utils.safe_rel_path(current_rel)
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

            pw_enabled = bool(self.config.password)
            is_admin = is_admin_request()
            pending_files = utils.list_pending_files(self.config) if is_admin else []
            pending_count = len(pending_files)

            return render_template(
                "index.html",
                base_dir=str(self.config.base_dir),
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
            try:
                full_path = utils.get_file_safe(self.config, filename)
            except Exception:
                abort(404)
                
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
            try:
                full_path = utils.get_file_safe(self.config, filename)
            except Exception:
                abort(404)
                
            if not full_path.exists():
                abort(404)
            return send_from_directory(
                directory=self.config.base_dir,
                path=filename,
                as_attachment=True
            )

        @app.route("/stream/<path:filename>")
        @requires_auth
        def stream_file(filename):
            try:
                full_path = utils.get_file_safe(self.config, filename)
            except Exception:
                abort(404)
                
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
                    utils.iter_file(full_path, start, end),
                    status=206,
                    headers=headers,
                    mimetype=mimetype,
                )

            headers = {
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
            }
            return Response(
                utils.iter_file(full_path, 0, file_size - 1),
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
            try:
                _ = utils.get_dir_safe(self.config, current_rel)
            except Exception:
                abort(400)

            files = request.files.getlist("files")
            pending_root = self.config.get_pending_dir()
            target_rel = utils.safe_rel_path(current_rel)
            pending_target_dir = (pending_root / target_rel)
            pending_target_dir.mkdir(parents=True, exist_ok=True)

            saved_relpaths_inside_pending = []
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

            if saved_relpaths_inside_pending:
                upload_info = {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "target_folder": current_rel or "/",
                    "pending_relpaths": saved_relpaths_inside_pending,
                    "display_names": original_names,
                    "client_ip": request.remote_addr,
                }
                # Emit signal to GUI
                self.signals.upload_request.emit(upload_info)

            return redirect(url_for("index", p=current_rel))

        @app.route("/approve/<path:filename>", methods=["POST"])
        @requires_auth
        def approve_file(filename):
            if not is_admin_request():
                abort(403)
            
            # Logic to approve file
            pending_root = self.config.get_pending_dir()
            try:
                pending_path = (pending_root / filename).resolve()
            except Exception:
                abort(404)
                
            if not pending_path.exists():
                return redirect(url_for("index"))

            rel_inside = pending_path.relative_to(pending_root)
            dest = self.config.base_dir / rel_inside
            dest.parent.mkdir(parents=True, exist_ok=True)

            if dest.exists():
                stem = dest.stem
                suffix = dest.suffix
                counter = 1
                while dest.exists():
                    dest = dest.parent / f"{stem}_{counter}{suffix}"
                    counter += 1

            pending_path.replace(dest)
            return redirect(url_for("index"))

        @app.route("/reject/<path:filename>", methods=["POST"])
        @requires_auth
        def reject_file(filename):
            if not is_admin_request():
                abort(403)
            
            pending_root = self.config.get_pending_dir()
            try:
                pending_path = (pending_root / filename).resolve()
            except Exception:
                abort(404)
                
            if pending_path.exists() and pending_path.is_file():
                pending_path.unlink()
                
            return redirect(url_for("index"))

        @app.route("/delete/<path:filename>", methods=["POST"])
        @requires_auth
        def delete_file(filename):
            if not is_admin_request():
                abort(403)
            current_rel = request.args.get("p", "").strip()
            try:
                full_path = utils.get_file_safe(self.config, filename)
                if full_path.exists() and full_path.is_file():
                    full_path.unlink()
            except Exception:
                pass
            return redirect(url_for("index", p=current_rel))

        return app

    def run(self):
        self.server = make_server(self.config.host, self.config.port, self.app, threaded=True)
        self.ctx.push()
        self.server.serve_forever()

    def stop(self):
        if self.server:
            self.server.shutdown()
