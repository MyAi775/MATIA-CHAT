import os
import random
import secrets
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit


# =========================================================
# CONFIG
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

OWNER_USERNAME = "Matia"

# Në Render krijo:
# OWNER_PIN = PIN-i yt sekret
#
# Ky default përdoret vetëm për test lokal.
OWNER_PIN = os.environ.get("OWNER_PIN", "847291")

MAX_MESSAGES = 500
MAX_USERNAME_LENGTH = 24
MAX_MESSAGE_LENGTH = 2000


# =========================================================
# FLASK
# =========================================================

app = Flask(
    __name__,
    static_folder=BASE_DIR,
    static_url_path=""
)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "matia-chat-secret"
)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading"
)


# =========================================================
# DATA
# =========================================================

USERS = {}
TOKENS = {}
SOCKET_USERS = {}

MESSAGES = []

GROUPS = {
    "main": {
        "name": "MATIA CHAT",
        "owner": OWNER_USERNAME
    }
}

BANNED = set()
MUTED = set()
LOCKED_GROUPS = set()


# =========================================================
# TIME
# =========================================================

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def current_time():
    return datetime.now().strftime("%H:%M")


# =========================================================
# USERNAME
# =========================================================

def clean_username(value):
    value = str(value or "").strip()

    value = value[:MAX_USERNAME_LENGTH]

    allowed = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789_- "
    )

    value = "".join(
        char for char in value
        if char in allowed
    )

    return value.strip()


def username_exists(username):
    username = clean_username(username).lower()

    for existing in USERS:
        if existing.lower() == username:
            return True

    return False


def existing_username(username):
    username = clean_username(username).lower()

    for existing in USERS:
        if existing.lower() == username:
            return existing

    return None


# =========================================================
# ROLES
# =========================================================

def get_role(username):
    user = existing_username(username)

    if user is None:
        return "user"

    return USERS[user].get("role", "user")


def is_owner(username):
    return (
        clean_username(username).lower()
        == OWNER_USERNAME.lower()
    )


def is_mod(username):
    return get_role(username) in (
        "owner",
        "mod"
    )


# =========================================================
# TOKENS
# =========================================================

def make_token(username):
    token = secrets.token_urlsafe(32)

    TOKENS[token] = username

    return token


def verify_token(token, username):
    if not token:
        return None

    token_user = TOKENS.get(token)

    if not token_user:
        return None

    if token_user.lower() != username.lower():
        return None

    user = existing_username(token_user)

    if user is None:
        return None

    return user


# =========================================================
# MESSAGE SYSTEM
# =========================================================

def add_message(
    username,
    text,
    group="main",
    kind="user"
):
    message = {
        "id": secrets.token_hex(8),
        "username": username,
        "text": text,
        "group": group,
        "time": current_time(),
        "timestamp": now_iso(),
        "kind": kind,
        "role": get_role(username)
    }

    MESSAGES.append(message)

    if len(MESSAGES) > MAX_MESSAGES:
        del MESSAGES[:-MAX_MESSAGES]

    return message


def broadcast_message(message):
    socketio.emit(
        "new_message",
        message
    )


# =========================================================
# BROADCAST USERS
# =========================================================

def send_users():
    payload = []

    for username, data in USERS.items():
        payload.append({
            "username": username,
            "role": data.get(
                "role",
                "user"
            ),
            "online": True
        })

    socketio.emit(
        "users",
        payload
    )


# =========================================================
# BROADCAST GROUPS
# =========================================================

def send_groups():
    payload = []

    for group_id, group in GROUPS.items():
        payload.append({
            "id": group_id,
            "name": group["name"]
        })

    socketio.emit(
        "groups",
        payload
    )


# =========================================================
# REMOVE USER
# =========================================================

def remove_user(username):
    user = existing_username(username)

    if user is None:
        return

    socket_id = USERS[user].get(
        "socket_id"
    )

    USERS.pop(
        user,
        None
    )

    # Remove token(s)
    for token, token_user in list(
        TOKENS.items()
    ):
        if token_user.lower() == user.lower():
            TOKENS.pop(
                token,
                None
            )

    # Remove socket mapping
    if socket_id:
        SOCKET_USERS.pop(
            socket_id,
            None
        )


# =========================================================
# FRONTEND
# =========================================================

@app.route("/")
def home():
    return send_from_directory(
        BASE_DIR,
        "index.html"
    )


@app.route("/index.html")
def index_page():
    return send_from_directory(
        BASE_DIR,
        "index.html"
    )


@app.route("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "MATIA CHAT"
    })


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/api/login",
    methods=["POST"]
)
def login():
    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    username = clean_username(
        data.get("username")
    )

    pin = str(
        data.get("pin") or ""
    ).strip()

    # -------------------------
    # VALIDATION
    # -------------------------

    if not username:
        return jsonify({
            "ok": False,
            "error": "Enter a username."
        }), 400

    if len(username) < 2:
        return jsonify({
            "ok": False,
            "error":
                "Username must be at least 2 characters."
        }), 400

    # -------------------------
    # BANNED
    # -------------------------

    if username.lower() in {
        item.lower()
        for item in BANNED
    }:
        return jsonify({
            "ok": False,
            "error": "This username is banned."
        }), 403

    # =====================================================
    # OWNER LOGIN
    # =====================================================

    if username.lower() == OWNER_USERNAME.lower():

        # Owner is already online
        if username_exists(
            OWNER_USERNAME
        ):
            return jsonify({
                "ok": False,
                "error":
                    "Owner is already online."
            }), 409

        # Wrong PIN
        if pin != OWNER_PIN:
            return jsonify({
                "ok": False,
                "error":
                    "That username is reserved for the Owner."
            }), 403

        # Canonical owner name
        username = OWNER_USERNAME

        role = "owner"

    # =====================================================
    # NORMAL USER
    # =====================================================

    else:

        if username_exists(username):
            return jsonify({
                "ok": False,
                "error":
                    "Username already taken."
            }), 409

        role = "user"

    # =====================================================
    # CREATE SESSION
    # =====================================================

    USERS[username] = {
        "role": role,
        "joined": now_iso(),
        "socket_id": None
    }

    if role == "owner":
        GROUPS["main"]["owner"] = (
            OWNER_USERNAME
        )

    token = make_token(
        username
    )

    send_users()
    send_groups()

    return jsonify({
        "ok": True,
        "username": username,
        "role": role,
        "token": token
    })


# =========================================================
# USERS API
# =========================================================

@app.route("/api/users")
def users_api():
    return jsonify([
        {
            "username": username,
            "role": data.get(
                "role",
                "user"
            ),
            "online": True
        }
        for username, data in USERS.items()
    ])


# =========================================================
# GROUPS API
# =========================================================

@app.route("/api/groups")
def groups_api():
    return jsonify([
        {
            "id": group_id,
            "name": group["name"]
        }
        for group_id, group
        in GROUPS.items()
    ])


# =========================================================
# CREATE GROUP
# =========================================================

@app.route(
    "/api/group",
    methods=["POST"]
)
def create_group_api():
    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    username = clean_username(
        data.get("username")
    )

    token = str(
        data.get("token") or ""
    )

    name = str(
        data.get("name") or ""
    ).strip()[:40]

    user = verify_token(
        token,
        username
    )

    if user is None:
        return jsonify({
            "ok": False,
            "error":
                "Invalid session."
        }), 403

    if not is_mod(user):
        return jsonify({
            "ok": False,
            "error":
                "Only Owner or Mod can create groups."
        }), 403

    if not name:
        return jsonify({
            "ok": False,
            "error":
                "Enter a group name."
        }), 400

    group_id = (
        "group_"
        + secrets.token_hex(4)
    )

    GROUPS[group_id] = {
        "name": name,
        "owner": user
    }

    send_groups()

    return jsonify({
        "ok": True,
        "id": group_id,
        "name": name
    })


# =========================================================
# GET MESSAGES
# =========================================================

@app.route("/api/messages")
def messages_get():
    group = request.args.get(
        "group",
        "main"
    )

    return jsonify([
        message
        for message in MESSAGES
        if message["group"] == group
    ])


# =========================================================
# POST MESSAGE
# =========================================================

@app.route(
    "/api/messages",
    methods=["POST"]
)
def messages_post():
    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    username = clean_username(
        data.get("username")
    )

    token = str(
        data.get("token") or ""
    )

    text = str(
        data.get("text") or ""
    ).strip()

    text = text[:MAX_MESSAGE_LENGTH]

    group = str(
        data.get("group") or "main"
    ).strip()

    user = verify_token(
        token,
        username
    )

    if user is None:
        return jsonify({
            "ok": False,
            "error":
                "Invalid session."
        }), 403

    if not text:
        return jsonify({
            "ok": False,
            "error":
                "Message is empty."
        }), 400

    if user in MUTED:
        return jsonify({
            "ok": False,
            "error":
                "You are muted."
        }), 403

    if (
        group in LOCKED_GROUPS
        and not is_mod(user)
    ):
        return jsonify({
            "ok": False,
            "error":
                "This group is locked."
        }), 403

    if text.startswith("/"):
        return jsonify({
            "ok": False,
            "error":
                "Use the command system."
        }), 400

    message = add_message(
        user,
        text,
        group,
        "user"
    )

    broadcast_message(
        message
    )

    return jsonify({
        "ok": True,
        "message": message
    })


# =========================================================
# COMMAND SYSTEM
# =========================================================

@app.route(
    "/api/command",
    methods=["POST"]
)
def command_api():
    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    username = clean_username(
        data.get("username")
    )

    token = str(
        data.get("token") or ""
    )

    command_text = str(
        data.get("command") or ""
    ).strip()

    group = str(
        data.get("group") or "main"
    ).strip()

    user = verify_token(
        token,
        username
    )

    if user is None:
        return jsonify({
            "ok": False,
            "error":
                "Invalid session."
        }), 403

    if not command_text.startswith("/"):
        return jsonify({
            "ok": False,
            "error":
                "Commands start with /"
        }), 400

    parts = command_text.split()

    command = parts[0].lower()

    args = parts[1:]


    # =====================================================
    # USER COMMANDS
    # =====================================================

    if command in (
        "/help",
        "/commands"
    ):

        text = (
            "📚 USER COMMANDS\n"
            "/time\n"
            "/flip\n"
            "/dice\n"
            "/roll 100\n"
            "/8ball\n"
            "/rate username\n"
            "/online\n"
            "/users\n"
            "/hug username\n"
            "/slap username\n"
            "/dance"
        )


    elif command == "/time":

        text = (
            "🕐 Server time: "
            + datetime.now().strftime(
                "%H:%M:%S"
            )
        )


    elif command == "/flip":

        text = random.choice([
            "🪙 Heads!",
            "🪙 Tails!"
        ])


    elif command == "/dice":

        text = (
            f"🎲 You rolled "
            f"{random.randint(1, 6)}"
        )


    elif command == "/roll":

        maximum = 100

        if args:
            try:
                maximum = max(
                    1,
                    min(
                        int(args[0]),
                        100000
                    )
                )
            except ValueError:
                pass

        text = (
            f"🎲 Roll: "
            f"{random.randint(1, maximum)}"
        )


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

        target = (
            " ".join(args)
            or user
        )

        text = (
            f"⭐ {target}: "
            f"{random.randint(1,100)}/100"
        )


    elif command in (
        "/online",
        "/users"
    ):

        text = (
            f"🟢 Online users: "
            f"{len(USERS)}"
        )


    elif command == "/hug":

        target = (
            " ".join(args)
            or "everyone"
        )

        text = (
            f"🤗 {user} hugged "
            f"{target}"
        )


    elif command == "/slap":

        target = (
            " ".join(args)
            or "the air"
        )

        text = (
            f"👋 {user} slapped "
            f"{target}"
        )


    elif command == "/dance":

        text = (
            f"💃 {user} is dancing!"
        )


    # =====================================================
    # CLEAR
    # =====================================================

    elif command == "/clear":

        if not is_mod(user):
            return jsonify({
                "ok": False,
                "error":
                    "Only Owner/Mod can use /clear."
            }), 403

        MESSAGES[:] = [
            message
            for message in MESSAGES
            if message["group"] != group
        ]

        socketio.emit(
            "clear_group",
            {
                "group": group
            }
        )

        text = "🧹 Chat cleared."


    # =====================================================
    # ANNOUNCE
    # =====================================================

    elif command == "/announce":

        if not is_mod(user):
            return jsonify({
                "ok": False,
                "error":
                    "Only Owner/Mod can announce."
            }), 403

        announcement = (
            " ".join(args)
            .strip()
        )

        if not announcement:
            return jsonify({
                "ok": False,
                "error":
                    "Usage: /announce message"
            }), 400

        socketio.emit(
            "announcement",
            {
                "text": announcement,
                "username": user
            }
        )

        text = (
            f"📢 {announcement}"
        )


    # =====================================================
    # KICK
    # =====================================================

    elif command == "/kick":

        if not is_mod(user):
            return jsonify({
                "ok": False,
                "error":
                    "Only Owner/Mod can kick."
            }), 403

        target = clean_username(
            args[0]
            if args
            else ""
        )

        target_user = existing_username(
            target
        )

        if target_user is None:

            text = "❌ User not found."

        elif is_owner(target_user):

            text = (
                "❌ The Owner cannot be kicked."
            )

        elif (
            target_user.lower()
            == user.lower()
        ):

            text = (
                "❌ You cannot kick yourself."
            )

        elif (
            get_role(user) == "mod"
            and get_role(target_user) == "mod"
        ):

            text = (
                "❌ A Mod cannot kick another Mod."
            )

        else:

            sid = USERS[
                target_user
            ].get("socket_id")

            if sid:
                socketio.emit(
                    "force_logout",
                    {
                        "username":
                            target_user
                    },
                    to=sid
                )

            remove_user(
                target_user
            )

            send_users()

            text = (
                f"👢 {target_user} "
                f"was kicked."
            )


    # =====================================================
    # BAN
    # =====================================================

    elif command == "/ban":

        if not is_mod(user):
            return jsonify({
                "ok": False,
                "error":
                    "Only Owner/Mod can ban."
            }), 403

        target = clean_username(
            args[0]
            if args
            else ""
        )

        target_user = existing_username(
            target
        )

        if target_user is None:

            text = "❌ User not found."

        elif is_owner(target_user):

            text = (
                "❌ The Owner cannot be banned."
            )

        elif (
            target_user.lower()
            == user.lower()
        ):

            text = (
                "❌ You cannot ban yourself."
            )

        elif (
            get_role(user) == "mod"
            and get_role(target_user) == "mod"
        ):

            text = (
                "❌ A Mod cannot ban another Mod."
            )

        else:

            sid = USERS[
                target_user
            ].get("socket_id")

            BANNED.add(
                target_user
            )

            if sid:
                socketio.emit(
                    "force_logout",
                    {
                        "username":
                            target_user
                    },
                    to=sid
                )

            remove_user(
                target_user
            )

            send_users()

            text = (
                f"🔨 {target_user} "
                f"was banned."
            )


    # =====================================================
    # UNBAN
    # =====================================================

    elif command == "/unban":

        if not is_owner(user):
            return jsonify({
                "ok": False,
                "error":
                    "Only Owner can unban."
            }), 403

        target = clean_username(
            args[0]
            if args
            else ""
        )

        if not target:
            return jsonify({
                "ok": False,
                "error":
                    "Usage: /unban username"
            }), 400

        BANNED.discard(
            target
        )

        text = (
            f"✅ {target} "
            f"was unbanned."
        )


    # =====================================================
    # MUTE
    # =====================================================

    elif command == "/mute":

        if not is_mod(user):
            return jsonify({
                "ok": False,
                "error":
                    "Only Owner/Mod can mute."
            }), 403

        target = clean_username(
            args[0]
            if args
            else ""
        )

        target_user = existing_username(
            target
        )

        if target_user is None:

            text = "❌ User not found."

        elif is_owner(target_user):

            text = (
                "❌ The Owner cannot be muted."
            )

        elif (
            get_role(user) == "mod"
            and get_role(target_user) == "mod"
        ):

            text = (
                "❌ A Mod cannot mute another Mod."
            )

        else:

            MUTED.add(
                target_user
            )

            text = (
                f"🔇 {target_user} "
                f"was muted."
            )


    # =====================================================
    # UNMUTE
    # =====================================================

    elif command == "/unmute":

        if not is_mod(user):
            return jsonify({
                "ok": False,
                "error":
                    "Only Owner/Mod can unmute."
            }), 403

        target = clean_username(
            args[0]
            if args
            else ""
        )

        MUTED.discard(
            target
        )

        text = (
            f"🔊 {target} "
            f"was unmuted."
        )


    # =====================================================
    # PROMOTE
    # =====================================================

    elif command == "/promote":

        if not is_owner(user):
            return jsonify({
                "ok": False,
                "error":
                    "Only Owner can promote."
            }), 403

        target = clean_username(
            args[0]
            if args
            else ""
        )

        target_user = existing_username(
            target
        )

        if target_user is None:

            text = "❌ User not found."

        elif is_owner(target_user):

            text = (
                "👑 That user is already Owner."
            )

        else:

            USERS[
                target_user
            ]["role"] = "mod"

            send_users()

            text = (
                f"🛡️ {target_user} "
                f"is now a Mod."
            )


    # =====================================================
    # DEMOTE
    # =====================================================

    elif command == "/demote":

        if not is_owner(user):
            return jsonify({
                "ok": False,
                "error":
                    "Only Owner can demote."
            }), 403

        target = clean_username(
            args[0]
            if args
            else ""
        )

        target_user = existing_username(
            target
        )

        if target_user is None:

            text = "❌ User not found."

        elif is_owner(target_user):

            text = (
                "❌ Owner cannot be demoted."
            )

        else:

            USERS[
                target_user
            ]["role"] = "user"

            send_users()

            text = (
                f"⬇️ {target_user} "
                f"is now a User."
            )


    # =====================================================
    # LOCK
    # =====================================================

    elif command == "/lock":

        if not is_mod(user):
            return jsonify({
                "ok": False,
                "error":
                    "Only Owner/Mod can lock."
            }), 403

        LOCKED_GROUPS.add(
            group
        )

        text = (
            "🔒 This group is locked."
        )


    # =====================================================
    # UNLOCK
    # =====================================================

    elif command == "/unlock":

        if not is_mod(user):
            return jsonify({
                "ok": False,
                "error":
                    "Only Owner/Mod can unlock."
            }), 403

        LOCKED_GROUPS.discard(
            group
        )

        text = (
            "🔓 This group is unlocked."
        )


    # =====================================================
    # RENAME
    # =====================================================

    elif command == "/rename":

        if not is_mod(user):
            return jsonify({
                "ok": False,
                "error":
                    "Only Owner/Mod can rename."
            }), 403

        new_name = (
            " ".join(args)
            .strip()
        )[:40]

        if not new_name:
            return jsonify({
                "ok": False,
                "error":
                    "Usage: /rename New Name"
            }), 400

        if group not in GROUPS:
            return jsonify({
                "ok": False,
                "error":
                    "Group not found."
            }), 404

        GROUPS[group]["name"] = new_name

        send_groups()

        text = (
            f"✏️ Group renamed to "
            f"{new_name}"
        )


    # =====================================================
    # UNKNOWN
    # =====================================================

    else:

        return jsonify({
            "ok": False,
            "error":
                f"Unknown command: {command}"
        }), 400


    # =====================================================
    # COMMAND MESSAGE
    # =====================================================

    message = add_message(
        user,
        text,
        group,
        "command"
    )

    broadcast_message(
        message
    )

    return jsonify({
        "ok": True,
        "message": text
    })


# =========================================================
# SOCKET.IO
# =========================================================

@socketio.on("connect")
def socket_connect():

    emit(
        "server_status",
        {
            "status": "connected"
        }
    )

    send_users()
    send_groups()


@socketio.on("login")
def socket_login(data):

    data = data or {}

    username = clean_username(
        data.get("username")
    )

    token = str(
        data.get("token") or ""
    )

    user = verify_token(
        token,
        username
    )

    if user is None:

        emit(
            "login_error",
            {
                "error":
                    "Invalid login session."
            }
        )

        return


    sid = request.sid


    old_sid = USERS[
        user
    ].get("socket_id")


    # Reconnect
    if old_sid and old_sid != sid:

        SOCKET_USERS.pop(
            old_sid,
            None
        )


    USERS[
        user
    ]["socket_id"] = sid


    SOCKET_USERS[
        sid
    ] = user


    emit(
        "login_success",
        {
            "username":
                user,

            "role":
                get_role(user)
        }
    )


    send_users()


@socketio.on("send_message")
def socket_send_message(data):

    data = data or {}

    username = clean_username(
        data.get("username")
    )

    token = str(
        data.get("token") or ""
    )

    text = str(
        data.get("text") or ""
    ).strip()

    text = text[:MAX_MESSAGE_LENGTH]

    group = str(
        data.get("group") or "main"
    ).strip()


    user = verify_token(
        token,
        username
    )


    if user is None:

        emit(
            "error_message",
            {
                "error":
                    "Invalid session."
            }
        )

        return


    if not text:

        return


    if user in MUTED:

        emit(
            "error_message",
            {
                "error":
                    "You are muted."
            }
        )

        return


    if (
        group in LOCKED_GROUPS
        and not is_mod(user)
    ):

        emit(
            "error_message",
            {
                "error":
                    "This group is locked."
            }
        )

        return


    if text.startswith("/"):

        emit(
            "error_message",
            {
                "error":
                    "Use the command system."
            }
        )

        return


    message = add_message(
        user,
        text,
        group,
        "user"
    )


    broadcast_message(
        message
    )


@socketio.on("disconnect")
def socket_disconnect():

    sid = request.sid


    user = SOCKET_USERS.pop(
        sid,
        None
    )


    if not user:
        return


    current_user = existing_username(
        user
    )


    if current_user is None:
        return


    current_sid = USERS[
        current_user
    ].get("socket_id")


    # Only remove if this socket
    # is still the active socket.
    if current_sid == sid:

        remove_user(
            current_user
        )

        send_users()


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        allow_unsafe_werkzeug=True
    )
