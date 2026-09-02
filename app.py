import os
import random
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=BASE_DIR,
    static_url_path=""
)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading"
)

USERS = {}
MESSAGES = []
GROUPS = {}
BANNED = set()
MUTED = set()

MAX_MESSAGES = 500


# =========================================================
# HELPERS
# =========================================================

def now_time():
    return datetime.now().strftime("%H:%M")


def clean_username(username):
    username = str(username or "").strip()

    if not username:
        return ""

    username = username[:24]

    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_- "
    username = "".join(c for c in username if c in allowed)

    return username.strip()


def clean_text(text):
    text = str(text or "").strip()
    return text[:2000]


def role(username):
    username = clean_username(username)

    if not USERS:
        return "owner"

    user = USERS.get(username)

    if user:
        return user.get("role", "user")

    return "user"


def is_owner(username):
    return role(username) == "owner"


def is_mod(username):
    return role(username) in ("owner", "mod")


def add_message(username, text, group="main", kind="user"):
    message = {
        "id": len(MESSAGES) + 1,
        "username": username,
        "text": text,
        "group": group,
        "time": now_time(),
        "kind": kind,
        "role": role(username)
    }

    MESSAGES.append(message)

    if len(MESSAGES) > MAX_MESSAGES:
        del MESSAGES[:-MAX_MESSAGES]

    return message


def send_users():
    socketio.emit("users", [
        {
            "username": username,
            "role": info.get("role", "user"),
            "online": True
        }
        for username, info in USERS.items()
    ])


def system_message(text, group="main"):
    message = add_message("MATIA BOT", text, group, "system")
    socketio.emit("new_message", message)


def fun_response(command, username):
    options = {
        "/flip": [
            "🪙 Heads!",
            "🪙 Tails!"
        ],
        "/dice": [
            f"🎲 {random.randint(1, 6)}"
        ],
        "/roll": [
            f"🎲 {random.randint(1, 100)}"
        ],
        "/8ball": [
            "🎱 Definitely.",
            "🎱 Probably.",
            "🎱 Ask again later.",
            "🎱 Nope.",
            "🎱 Absolutely not.",
            "🎱 The future is unclear."
        ],
        "/rate": [
            f"⭐ {random.randint(1, 100)}/100"
        ]
    }

    values = options.get(command)

    if values:
        return random.choice(values)

    return None


# =========================================================
# ROUTES
# =========================================================

@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/index.html")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "MATIA CHAT"
    })


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}

    username = clean_username(data.get("username"))

    if not username:
        return jsonify({
            "ok": False,
            "error": "Username required"
        }), 400

    if username.lower() in {x.lower() for x in BANNED}:
        return jsonify({
            "ok": False,
            "error": "You are banned."
        }), 403

    if username not in USERS:
        role_value = "owner" if len(USERS) == 0 else "user"

        USERS[username] = {
            "role": role_value,
            "joined": datetime.now().isoformat()
        }

    send_users()

    return jsonify({
        "ok": True,
        "username": username,
        "role": USERS[username]["role"]
    })


@app.route("/api/messages")
def api_messages():
    group = request.args.get("group", "main")

    result = [
        message
        for message in MESSAGES
        if message["group"] == group
    ]

    return jsonify(result)


@app.route("/api/groups")
def api_groups():
    groups = [
        {
            "id": "main",
            "name": "MATIA CHAT"
        }
    ]

    for group_id, group in GROUPS.items():
        groups.append({
            "id": group_id,
            "name": group["name"]
        })

    return jsonify(groups)


@app.route("/api/group", methods=["POST"])
def create_group():
    data = request.get_json(silent=True) or {}

    username = clean_username(data.get("username"))
    name = clean_text(data.get("name"))

    if not username or not name:
        return jsonify({
            "ok": False,
            "error": "Missing username or group name"
        }), 400

    if not is_mod(username):
        return jsonify({
            "ok": False,
            "error": "Only owner/mod can create groups."
        }), 403

    group_id = f"group_{len(GROUPS) + 1}"

    GROUPS[group_id] = {
        "name": name,
        "owner": username
    }

    socketio.emit("groups", [
        {
            "id": "main",
            "name": "MATIA CHAT"
        }
    ] + [
        {
            "id": gid,
            "name": group["name"]
        }
        for gid, group in GROUPS.items()
    ])

    return jsonify({
        "ok": True,
        "id": group_id,
        "name": name
    })


@app.route("/api/command", methods=["POST"])
def api_command():
    data = request.get_json(silent=True) or {}

    username = clean_username(data.get("username"))
    command_text = clean_text(data.get("command"))
    group = clean_text(data.get("group") or "main")

    if not username or not command_text:
        return jsonify({
            "ok": False,
            "error": "Missing data"
        }), 400

    if username not in USERS:
        return jsonify({
            "ok": False,
            "error": "Login first"
        }), 403

    parts = command_text.split()
    command = parts[0].lower()
    args = parts[1:]

    # ---------------- FUN COMMANDS ----------------

    fun = fun_response(command, username)

    if fun:
        message = add_message(
            username,
            fun,
            group,
            "command"
        )

        socketio.emit("new_message", message)

        return jsonify({
            "ok": True,
            "message": fun
        })

    if command == "/time":
        text = f"🕐 Current time: {datetime.now().strftime('%H:%M:%S')}"

    elif command in ("/help", "/commands"):
        text = (
            "📚 Commands: /time /flip /dice /roll /8ball /rate "
            "/online /users /clear /announce /kick /ban /unban "
            "/mute /unmute /promote /demote /lock /unlock /rename"
        )

    elif command in ("/online", "/users"):
        text = f"🟢 Online users: {len(USERS)}"

    elif command == "/clear":
        if not is_mod(username):
            return jsonify({
                "ok": False,
                "error": "Only owner/mod can use /clear."
            }), 403

        MESSAGES[:] = [
            m for m in MESSAGES
            if m["group"] != group
        ]

        socketio.emit("clear_group", {
            "group": group
        })

        text = "🧹 Chat cleared."

    elif command == "/announce":
        if not is_mod(username):
            return jsonify({
                "ok": False,
                "error": "Only owner/mod can announce."
            }), 403

        announcement = " ".join(args).strip()

        if not announcement:
            return jsonify({
                "ok": False,
                "error": "Usage: /announce message"
            }), 400

        socketio.emit("announcement", {
            "text": announcement,
            "username": username
        })

        text = f"📢 {announcement}"

    elif command == "/kick":
        if not is_mod(username):
            return jsonify({
                "ok": False,
                "error": "Only owner/mod can kick."
            }), 403

        target = clean_username(args[0] if args else "")

        if target not in USERS:
            text = "❌ User not found."
        elif target == username:
            text = "❌ You cannot kick yourself."
        elif is_owner(target):
            text = "❌ You cannot kick the owner."
        else:
            USERS.pop(target, None)
            socketio.emit("force_logout", {
                "username": target
            })
            send_users()
            text = f"👢 {target} was kicked."

    elif command == "/ban":
        if not is_mod(username):
            return jsonify({
                "ok": False,
                "error": "Only owner/mod can ban."
            }), 403

        target = clean_username(args[0] if args else "")

        if not target:
            return jsonify({
                "ok": False,
                "error": "Usage: /ban username"
            }), 400

        if target == username or is_owner(target):
            text = "❌ You cannot ban that user."
        else:
            BANNED.add(target)
            USERS.pop(target, None)

            socketio.emit("force_logout", {
                "username": target
            })

            send_users()

            text = f"🔨 {target} was banned."

    elif command == "/unban":
        if not is_owner(username):
            return jsonify({
                "ok": False,
                "error": "Only owner can unban."
            }), 403

        target = clean_username(args[0] if args else "")

        if not target:
            return jsonify({
                "ok": False,
                "error": "Usage: /unban username"
            }), 400

        BANNED.discard(target)
        text = f"✅ {target} was unbanned."

    elif command == "/mute":
        if not is_mod(username):
            return jsonify({
                "ok": False,
                "error": "Only owner/mod can mute."
            }), 403

        target = clean_username(args[0] if args else "")

        if not target:
            return jsonify({
                "ok": False,
                "error": "Usage: /mute username"
            }), 400

        if target in USERS and not is_owner(target):
            MUTED.add(target)
            text = f"🔇 {target} was muted."
        else:
            text = "❌ Cannot mute that user."

    elif command == "/unmute":
        if not is_mod(username):
            return jsonify({
                "ok": False,
                "error": "Only owner/mod can unmute."
            }), 403

        target = clean_username(args[0] if args else "")

        MUTED.discard(target)
        text = f"🔊 {target} was unmuted."

    elif command == "/promote":
        if not is_owner(username):
            return jsonify({
                "ok": False,
                "error": "Only owner can promote."
            }), 403

        target = clean_username(args[0] if args else "")

        if target in USERS:
            USERS[target]["role"] = "mod"
            send_users()
            text = f"🛡️ {target} is now a moderator."
        else:
            text = "❌ User not found."

    elif command == "/demote":
        if not is_owner(username):
            return jsonify({
                "ok": False,
                "error": "Only owner can demote."
            }), 403

        target = clean_username(args[0] if args else "")

        if target in USERS and target != username:
            USERS[target]["role"] = "user"
            send_users()
            text = f"⬇️ {target} is now a user."
        else:
            text = "❌ Cannot demote that user."

    elif command == "/lock":
        if not is_mod(username):
            return jsonify({
                "ok": False,
                "error": "Only owner/mod can lock."
            }), 403

        text = "🔒 Group locked."

    elif command == "/unlock":
        if not is_mod(username):
            return jsonify({
                "ok": False,
                "error": "Only owner/mod can unlock."
            }), 403

        text = "🔓 Group unlocked."

    elif command == "/rename":
        if not is_mod(username):
            return jsonify({
                "ok": False,
                "error": "Only owner/mod can rename."
            }), 403

        new_name = " ".join(args).strip()

        if not new_name:
            return jsonify({
                "ok": False,
                "error": "Usage: /rename new name"
            }), 400

        if group == "main":
            text = "✏️ Main group renamed to " + new_name
        elif group in GROUPS:
            GROUPS[group]["name"] = new_name
            text = "✏️ Group renamed to " + new_name
        else:
            text = "❌ Group not found."

    else:
        text = f"❓ Unknown command: {command}"

    message = add_message(
        username,
        text,
        group,
        "command"
    )

    socketio.emit("new_message", message)

    return jsonify({
        "ok": True,
        "message": text
    })


# =========================================================
# SOCKET.IO
# =========================================================

@socketio.on("connect")
def socket_connect():
    emit("server_status", {
        "status": "connected"
    })

    send_users()


@socketio.on("login")
def socket_login(data):
    username = clean_username((data or {}).get("username"))

    if not username:
        return

    if username.lower() in {x.lower() for x in BANNED}:
        emit("login_error", {
            "error": "You are banned."
        })
        return

    if username not in USERS:
        USERS[username] = {
            "role": "owner" if len(USERS) == 0 else "user",
            "joined": datetime.now().isoformat()
        }

    emit("login_success", {
        "username": username,
        "role": USERS[username]["role"]
    })

    send_users()


@socketio.on("send_message")
def socket_message(data):
    data = data or {}

    username = clean_username(data.get("username"))
    text = clean_text(data.get("text"))
    group = clean_text(data.get("group") or "main")

    if not username or not text:
        return

    if username not in USERS:
        return

    if username in MUTED:
        emit("error_message", {
            "error": "You are muted."
        })
        return

    if text.startswith("/"):
        return

    message = add_message(
        username,
        text,
        group,
        "user"
    )

    socketio.emit("new_message", message)


@socketio.on("disconnect")
def socket_disconnect():
    send_users()


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        allow_unsafe_werkzeug=True
    )
