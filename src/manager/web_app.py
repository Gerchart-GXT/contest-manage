import os

from flask import Flask, jsonify, request, send_from_directory

from manager_service import ManagerService
from runtime import resolve_runtime_path


WEB_DIR = resolve_runtime_path("web")

app = Flask(__name__, static_folder=WEB_DIR, static_url_path="/static")
service = ManagerService()


def success(payload=None):
    return jsonify({
        "status": "success",
        "data": payload
    })


def error_response(message, status_code=400):
    return jsonify({
        "status": "error",
        "mesg": message
    }), status_code


@app.route("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/api/state", methods=["GET"])
def get_state():
    try:
        return success(service.get_state())
    except Exception as exc:
        return error_response(str(exc), 500)


@app.route("/api/settings", methods=["POST"])
def update_settings():
    try:
        payload = request.get_json() or {}
        return success(service.update_settings(payload))
    except Exception as exc:
        return error_response(str(exc), 400)


@app.route("/api/upload-xlsx", methods=["POST"])
def upload_xlsx():
    try:
        uploaded_file = request.files.get("file")
        return success(service.save_uploaded_excel(uploaded_file))
    except Exception as exc:
        return error_response(str(exc), 400)


@app.route("/api/reload-clients", methods=["POST"])
def reload_clients():
    try:
        return success(service.reload_clients())
    except Exception as exc:
        return error_response(str(exc), 400)


@app.route("/api/readme", methods=["GET"])
def get_readme():
    try:
        return success(service.get_usage_readme())
    except Exception as exc:
        return error_response(str(exc), 400)


@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    try:
        return success(service.get_task_summaries())
    except Exception as exc:
        return error_response(str(exc), 400)


@app.route("/api/tasks/clear-history", methods=["POST"])
def clear_task_history():
    try:
        return success(service.clear_task_history())
    except Exception as exc:
        return error_response(str(exc), 400)


@app.route("/api/tasks/<task_id>", methods=["GET"])
def get_task_detail(task_id):
    try:
        return success(service.get_task_detail(task_id))
    except Exception as exc:
        return error_response(str(exc), 404)


@app.route("/api/actions/ping", methods=["POST"])
def run_ping():
    try:
        payload = request.get_json() or {}
        return success(service.submit_task(
            action="ping",
            title="Ping",
            meta={"note": payload.get("note", "")},
            runner=lambda task_id: service._run_ping_internal(task_id=task_id)
        ))
    except Exception as exc:
        return error_response(str(exc), 400)


@app.route("/api/actions/update-client-list", methods=["POST"])
def update_client_list():
    try:
        payload = request.get_json() or {}
        return success(service.submit_task(
            action="update-client-list",
            title="更新绑定",
            meta={"note": payload.get("note", "")},
            runner=lambda task_id: service._update_client_list_internal(task_id=task_id)
        ))
    except Exception as exc:
        return error_response(str(exc), 400)


def request_ids():
    payload = request.get_json() or {}
    return payload.get("selected_ids") or []


@app.route("/api/actions/connect-check", methods=["POST"])
def connect_check():
    try:
        payload = request.get_json() or {}
        selected_ids = payload.get("selected_ids") or []
        return success(service.submit_task(
            action="connect-check",
            title="Connect Check",
            meta={"note": payload.get("note", "")},
            runner=lambda task_id: service._connect_check_internal(selected_ids=selected_ids, task_id=task_id)
        ))
    except Exception as exc:
        return error_response(str(exc), 400)


@app.route("/api/actions/set-client-info", methods=["POST"])
def set_client_info():
    try:
        payload = request.get_json() or {}
        selected_ids = payload.get("selected_ids") or []
        return success(service.submit_task(
            action="set-client-info",
            title="下发考生信息",
            meta={"note": payload.get("note", "")},
            runner=lambda task_id: service._set_client_info_internal(selected_ids=selected_ids, task_id=task_id)
        ))
    except Exception as exc:
        return error_response(str(exc), 400)


@app.route("/api/actions/get-client-status", methods=["POST"])
def get_client_status():
    try:
        payload = request.get_json() or {}
        selected_ids = payload.get("selected_ids") or []
        return success(service.submit_task(
            action="get-client-status",
            title="获取客户端状态",
            meta={"note": payload.get("note", "")},
            runner=lambda task_id: service._get_client_status_internal(selected_ids=selected_ids, task_id=task_id)
        ))
    except Exception as exc:
        return error_response(str(exc), 400)


@app.route("/api/actions/get-client-log", methods=["POST"])
def get_client_log():
    try:
        payload = request.get_json() or {}
        selected_ids = payload.get("selected_ids") or []
        return success(service.submit_task(
            action="get-client-log",
            title="获取客户端日志",
            meta={"note": payload.get("note", "")},
            runner=lambda task_id: service._get_client_log_internal(selected_ids=selected_ids, task_id=task_id)
        ))
    except Exception as exc:
        return error_response(str(exc), 400)


@app.route("/api/actions/run-command", methods=["POST"])
def run_command():
    try:
        payload = request.get_json() or {}
        selected_ids = payload.get("selected_ids")
        command_id = payload.get("command_id", "default")
        command_template = payload.get("command", "")
        return success(service.submit_task(
            action="run-command",
            title=f"批量命令 {command_id}",
            meta={
                "note": payload.get("note", ""),
                "command_id": str(command_id),
                "command": command_template
            },
            runner=lambda task_id: service._run_command_internal(
                selected_ids=selected_ids,
                command_id=command_id,
                command_template=command_template,
                task_id=task_id
            )
        ))
    except Exception as exc:
        return error_response(str(exc), 400)


@app.route("/api/actions/kill-command", methods=["POST"])
def kill_command():
    try:
        payload = request.get_json() or {}
        selected_ids = payload.get("selected_ids")
        command_id = payload.get("command_id", "default")
        return success(service.submit_task(
            action="kill-command",
            title=f"停止命令 {command_id}",
            meta={
                "note": payload.get("note", ""),
                "command_id": str(command_id)
            },
            runner=lambda task_id: service._kill_command_internal(
                selected_ids=selected_ids,
                command_id=command_id,
                task_id=task_id
            )
        ))
    except Exception as exc:
        return error_response(str(exc), 400)


@app.route("/api/actions/open-window", methods=["POST"])
def open_window():
    try:
        payload = request.get_json() or {}
        selected_ids = payload.get("selected_ids")
        window_id = payload.get("window_id", 1)
        title = payload.get("title", "")
        content = payload.get("content", "")
        front_size = payload.get("front_size", 16)
        return success(service.submit_task(
            action="open-window",
            title=f"打开窗口 {window_id}",
            meta={
                "note": payload.get("note", ""),
                "window_id": int(window_id),
                "window_title": title,
                "window_content": content,
                "front_size": int(front_size)
            },
            runner=lambda task_id: service._open_info_window_internal(
                selected_ids=selected_ids,
                window_id=window_id,
                title=title,
                content=content,
                front_size=front_size,
                task_id=task_id
            )
        ))
    except Exception as exc:
        return error_response(str(exc), 400)


@app.route("/api/actions/close-window", methods=["POST"])
def close_window():
    try:
        payload = request.get_json() or {}
        selected_ids = payload.get("selected_ids")
        window_id = payload.get("window_id", 1)
        return success(service.submit_task(
            action="close-window",
            title=f"关闭窗口 {window_id}",
            meta={
                "note": payload.get("note", ""),
                "window_id": int(window_id)
            },
            runner=lambda task_id: service._close_info_window_internal(
                selected_ids=selected_ids,
                window_id=window_id,
                task_id=task_id
            )
        ))
    except Exception as exc:
        return error_response(str(exc), 400)


def run_server():
    app.run(host="0.0.0.0", port=8090, threaded=True, use_reloader=False)


if __name__ == "__main__":
    run_server()
