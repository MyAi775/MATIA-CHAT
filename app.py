import os
import random
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "matia-chat-secret")

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading"
)

USERS = {}
MESSAGES = []
GROUPS = {
    "main": {
        "name": "MATIA CHAT",
        "owner": None
    }
}

BANNED = set()
MUTED = set()
LOCKED_GROUPS = set()

MAX_MESSAGES = 500


# =========================================================
# HELPERS
# =========================================================

def current_time():
    return datetime.now().strftime("%H:%M")


def clean_username(value):
    value = str(value or "").strip()
    value = value[:24]

    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_- "
    value = "".join(char for char in value if char in allowed)

    return value.strip()


def clean_text(value):
    return str(value or "").strip()[:2000]


def username_exists(username):
    username_lower = username.lower()

    return any(
        existing.lower() == username_lower
        for existing in USERS
    )


def get_existing_username(username):
    username_lower = username.lower()

    for existing in USERS:
        if existing.lower() == username_lower:
            return existing

    return None


def get_role(username):
    existing = get_existing_username(username)

    if existing is None:
        return "user"

    return USERS[existing]["role"]


def is_owner(username):
    return get_role(username) == "owner"


def is_mod(username):
    return get_role(username) in ("owner", "mod")


def add_message(username, text, group="main", kind="user"):
    message = {
        "id": len(MESSAGES) + 1,
        "username": username,
        "text": text,
        "group": group,
        "time": current_time(),
        "kind": kind,
        "role": get_role(username)
    }

    MESSAGES.append(message)

    if len(MESSAGES) > MAX_MESSAGES:
        del MESSAGES[:-MAX_MESSAGES]

    return message


def broadcast_users():
    payload = []

    for username, info in USERS.items():
        payload.append({
            "username": username,
            "role": info["role"],
            "online": True
        })

    socketio.emit("users", payload)


def broadcast_groups():
    payload = []

    for group_id, group in GROUPS.items():
        payload.append({
            "id": group_id,
            "name": group["name"]
        })

    socketio.emit("groups", payload)


def send_system_message(text, group="main"):
    message = add_message(
        "MATIA BOT",
        text,
        group,
        "system"
    )

    socketio.emit("new_message", message)


def command_result(username, text, group):
    message = add_message(
        username,
        text,
        group,
        "command"
    )

    socketio.emit("new_message", message)


# =========================================================
# ROUTES
# =========================================================

@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/index.html")
def index_page():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "MATIA CHAT"
    })


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    username = clean_username(data.get("username"))

    if not username:
        return jsonify({
            "ok": False,
            "error": "Enter a username."
        }), 400

    if len(username) < 2:
        return jsonify({
            "ok": False,
            "error": "Username must be at least 2 characters."
        }), 400

    if username.lower() in {
        item.lower() for item in BANNED
    }:
        return jsonify({
            "ok": False,
            "error": "This username is banned."
        }), 403

    # IMPORTANT:
    # Same username is rejected, even if capitalization differs.
    if username_exists(username):
        return jsonify({
            "ok": False,
            "error": "Username already taken."
        }), 409

    new_role = "owner" if len(USERS) == 0 else "user"

    USERS[username] = {
        "role": new_role,
        "joined": datetime.now().isoformat()
    }

    if new_role == "owner":
        GROUPS["main"]["owner"] = username

    broadcast_users()
    broadcast_groups()

    return jsonify({
        "ok": True,
        "username": username,
        "role": new_role
    })


@app.route("/api/messages")
def get_messages():
    group = request.args.get("group", "main")

    result = [
        message
        for message in MESSAGES
        if message["group"] == group
    ]

    return jsonify(result)


@app.route("/api/groups")
def get_groups():
    return jsonify([
        {
            "id": group_id,
            "name": group["name"]
        }
        for group_id, group in GROUPS.items()
    ])


@app.route("/api/users")
def get_users():
    return jsonify([
        {
            "username": username,
            "role": info["role"],
            "online": True
        }
        for username, info in USERS.items()
    ])


@app.route("/api/messages", methods=["POST"])
def post_message():
    data = request.get_json(silent=True) or {}

    username = clean_username(data.get("username"))
    text = clean_text(data.get("text"))
    group = clean_text(data.get("group") or "main")

    actual_username = get_existing_username(username)

    if actual_username is None:
        return jsonify({
            "ok": False,
            "error": "Login first."
        }), 403

    if actual_username in MUTED:
        return jsonify({
            "ok": False,
            "error": "You are muted."
        }), 403

    if group in LOCKED_GROUPS and not is_mod(actual_username):
        return jsonify({
            "ok": False,
            "error": "This group is locked."
        }), 403

    if not text:
        return jsonify({
            "ok": False,
            "error": "Message is empty."
        }), 400

    if text.startswith("/"):
        return jsonify({
            "ok": False,
            "error": "Use the command endpoint for commands."
        }), 400

    message = add_message(
        actual_username,
        text,
        group,
        "user"
    )

    socketio.emit("new_message", message)

    return jsonify({
        "ok": True,
        "message": message
    })


@app.route("/api/group", methods=["POST"])
def create_group():
    data = request.get_json(silent=True) or {}

    username = clean_username(data.get("username"))
    name = clean_text(data.get("name"))

    actual_username = get_existing_username(username)

    if actual_username is None:
        return jsonify({
            "ok": False,
            "error": "Login first."
        }), 403

    if not is_mod(actual_username):
        return jsonify({
            "ok": False,
            "error": "Only Owner or Mod can create groups."
        }), 403

    if not name:
        return jsonify({
            "ok": False,
            "error": "Enter a group name."
        }), 400

    group_id = f"group_{len(GROUPS)}"

    GROUPS[group_id] = {
        "name": name,
        "owner": actual_username
    }

    broadcast_groups()

    return jsonify({
        "ok": True,
        "id": group_id,
        "name": name
    })


# =========================================================
# COMMANDS
# =========================================================

@app.route("/api/command", methods=["POST"])
def command_api():
    data = request.get_json(silent=True) or {}

    username = clean_username(data.get("username"))
    command_text = clean_text(data.get("command"))
    group = clean_text(data.get("group") or "main")

    actual_username = get_existing_username(username)

    if actual_username is None:
        return jsonify({
            "ok": False,
            "error": "Login first."
        }), 403

    if not command_text.startswith("/"):
        return jsonify({
            "ok": False,
            "error": "Commands start with /"
        }), 400

    parts = command_text.split()
    command = parts[0].lower()
    args = parts[1:]

    # ---------------- FUN ----------------

    if command == "/help" or command == "/commands":

        text = (
            "📚 Commands: "
            "/time /flip /dice /roll /8ball /rate "
            "/online /users /clear /announce /kick "
            "/ban /unban /mute /unmute /promote /demote "
            "/lock /unlock /rename /hug /slap /dance"
        )

    elif command == "/time":

        text = f"🕐 Server time: {datetime.now().strftime('%H:%M:%S')}"

    elif command == "/flip":

        text = random.choice([
            "🪙 Heads!",
            "🪙 Tails!"
        ])

    elif command == "/dice":

        text = f"🎲 You rolled {random.randint(1, 6)}"

    elif command == "/roll":

        max_value = 100

        if args:
            try:
                max_value = max(
                    1,
                    min(int(args[0]), 100000)
                )
            except ValueError:
                pass

        text = f"🎲 Roll: {random.randint(1, max_value)}"

    elif command == "/8ball":

        text = random.choice([
            "🎱 Definitely.",
            "🎱 Yes.",
            "🎱 Probably.",
            "🎱 Maybe.",
            "🎱 Ask again later.",
            "🎱 Nope.",
            "🎱 Absolutely not."
        ])

    elif command == "/rate":

        target = " ".join(args) or actual_username

        text = (
            f"⭐ {target} gets "
            f"{random.randint(1,100)}/100"
        )

    elif command == "/online" or command == "/users":

        text = f"🟢 Online users: {len(USERS)}"

    elif command == "/hug":

        target = " ".join(args) or "everyone"

        text = f"🤗 {actual_username} hugged {target}"

    elif command == "/slap":

        target = " ".join(args) or "the air"

        text = f"👋 {actual_username} slapped {target}"

    elif command == "/dance":

        text = f"💃 {actual_username} is dancing!"

    # ---------------- MODERATION ----------------

    elif command == "/clear":

        if not is_mod(actual_username):
            return jsonify({
                "ok": False,
                "error": "Only Owner/Mod can use /clear."
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

        if not is_mod(actual_username):
            return jsonify({
                "ok": False,
                "error": "Only Owner/Mod can announce."
            }), 403

        announcement = " ".join(args).strip()

        if not announcement:
            return jsonify({
                "ok": False,
                "error": "Usage: /announce your message"
            }), 400

        socketio.emit("announcement", {
            "text": announcement,
            "username": actual_username
        })

        text = f"📢 {announcement}"

    elif command == "/kick":

        if not is_mod(actual_username):
            return jsonify({
                "ok": False,
                "error": "Only Owner/Mod can kick."
            }), 403

        target = clean_username(args[0] if args else "")
        existing_target = get_existing_username(target)

        if existing_target is None:

            text = "❌ User not found."

        elif is_owner(existing_target):

            text = "❌ The Owner cannot be kicked."

        elif existing_target == actual_username:

            text = "❌ You cannot kick yourself."

        else:

            USERS.pop(existing_target)

            socketio.emit("force_logout", {
                "username": existing_target
            })

            broadcast_users()

            text = f"👢 {existing_target} was kicked."

    elif command == "/ban":

        if not is_mod(actual_username):
            return jsonify({
                "ok": False,
                "error": "Only Owner/Mod can ban."
            }), 403

        target = clean_username(args[0] if args else "")
        existing_target = get_existing_username(target)

        if existing_target is None:

            text = "❌ User not found."

        elif is_owner(existing_target):

            text = "❌ The Owner cannot be banned."

        elif existing_target == actual_username:

            text = "❌ You cannot ban yourself."

        else:

            BANNED.add(existing_target)
            USERS.pop(existing_target)

            socketio.emit("force_logout", {
                "username": existing_target
            })

            broadcast_users()

            text = f"🔨 {existing_target} was banned."

    elif command == "/unban":

        if not is_owner(actual_username):
            return jsonify({
                "ok": False,
                "error": "Only Owner can unban."
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

        if not is_mod(actual_username):
            return jsonify({
                "ok": False,
                "error": "Only Owner/Mod can mute."
            }), 403

        target = clean_username(args[0] if args else "")
        existing_target = get_existing_username(target)

        if existing_target is None:

            text = "❌ User not found."

        elif is_owner(existing_target):

            text = "❌ The Owner cannot be muted."

        else:

            MUTED.add(existing_target)

            text = f"🔇 {existing_target} was muted."

    elif command == "/unmute":

        if not is_mod(actual_username):
            return jsonify({
                "ok": False,
                "error": "Only Owner/Mod can unmute."
            }), 403

        target = clean_username(args[0] if args else "")

        MUTED.discard(target)

        text = f"🔊 {target} was unmuted."

    elif command == "/promote":

        if not is_owner(actual_username):
            return jsonify({
                "ok": False,
                "error": "Only Owner can promote."
            }), 403

        target = clean_username(args[0] if args else "")
        existing_target = get_existing_username(target)

        if existing_target is None:

            text = "❌ User not found."

        elif is_owner(existing_target):

            text = "👑 User is already Owner."

        else:

            USERS[existing_target]["role"] = "mod"
            broadcast_users()

            text = (
                f"🛡️ {existing_target} "
                f"is now a Mod."
            )

    elif command == "/demote":

        if not is_owner(actual_username):
            return jsonify({
                "ok": False,
                "error": "Only Owner can demote."
            }), 403

        target = clean_username(args[0] if args else "")
        existing_target = get_existing_username(target)

        if existing_target is None:

            text = "❌ User not found."

        elif is_owner(existing_target):

            text = "❌ Owner cannot be demoted."

        else:

            USERS[existing_target]["role"] = "user"
            broadcast_users()

            text = (
                f"⬇️ {existing_target} "
                f"is now a User."
            )

    elif command == "/lock":

        if not is_mod(actual_username):
            return jsonify({
                "ok": False,
                "error": "Only Owner/Mod can lock."
            }), 403

        LOCKED_GROUPS.add(group)

        text = "🔒 This group is now locked."

    elif command == "/unlock":

        if not is_mod(actual_username):
            return jsonify({
                "ok": False,
                "error": "Only Owner/Mod can unlock."
            }), 403

        LOCKED_GROUPS.discard(group)

        text = "🔓 This group is now unlocked."

    elif command == "/rename":

        if not is_mod(actual_username):
            return jsonify({
                "ok": False,
                "error": "Only Owner/Mod can rename."
            }), 403

        new_name = " ".join(args).strip()

        if not new_name:
            return jsonify({
                "ok": False,
                "error": "Usage: /rename New Name"
            }), 400

        if group not in GROUPS:
            return jsonify({
                "ok": False,
                "error": "Group not found."
            }), 404

        GROUPS[group]["name"] = new_name

        broadcast_groups()

        text = f"✏️ Group renamed to {new_name}"

    else:

        return jsonify({
            "ok": False,
            "error": f"Unknown command: {command}"
        }), 400

    command_result(
        actual_username,
        text,
        group
    )

    return jsonify({
        "ok": True,
        "message": text
    })


# =========================================================
# SOCKET.IO
# =========================================================

@socketio.on("connect")
def on_connect():
    emit("server_status", {
        "status": "connected"
    })

    broadcast_users()
    broadcast_groups()


@socketio.on("login")
def socket_login(data):
    data = data or {}

    username = clean_username(
        data.get("username")
    )

    if not username:
        emit("login_error", {
            "error": "Enter a username."
        })
        return

    if username.lower() in {
        item.lower() for item in BANNED
    }:
        emit("login_error", {
            "error": "This username is banned."
        })
        return

    # NEVER replace an existing user.
    if username_exists(username):
        emit("login_error", {
            "error": "Username already taken."
        })
        return

    new_role = "owner" if len(USERS) == 0 else "user"

    USERS[username] = {
        "role": new_role,
        "joined": datetime.now().isoformat()
    }

    if new_role == "owner":
        GROUPS["main"]["owner"] = username

    emit("login_success", {
        "username": username,
        "role": new_role
    })

    broadcast_users()
    broadcast_groups()


@socketio.on("send_message")
def socket_send_message(data):
    data = data or {}

    username = clean_username(
        data.get("username")
    )

    text = clean_text(
        data.get("text")
    )

    group = clean_text(
        data.get("group") or "main"
    )

    actual_username = get_existing_username(username)

    if actual_username is None:
        emit("error_message", {
            "error": "Login first."
        })
        return

    if actual_username in MUTED:
        emit("error_message", {
            "error": "You are muted."
        })
        return

    if group in LOCKED_GROUPS and not is_mod(actual_username):
        emit("error_message", {
            "error": "This group is locked."
        })
        return

    if not text:
        return

    if text.startswith("/"):
        emit("error_message", {
            "error": "Use commands through the command box."
        })
        return

    message = add_message(
        actual_username,
        text,
        group,
        "user"
    )

    socketio.emit(
        "new_message",
        message
    )


@socketio.on("disconnect")
def on_disconnect():
    pass


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 5000)
    )

    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        allow_unsafe_werkzeug=True
    )
