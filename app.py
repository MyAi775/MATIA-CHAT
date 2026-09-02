import os
import random
from datetime import datetime

from flask import Flask, send_file, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "matia-chat-secret")

socketio = SocketIO(app, cors_allowed_origins="*")

USERS = {}
CONNECTED = {}
MESSAGES = []

GROUP = {
    "name": "MATIA CHAT",
    "locked": False
}


# =========================================================
# HELPERS
# =========================================================

def get_time():
    return datetime.now().strftime("%H:%M")


def find_user(username):
    for name, data in USERS.items():
        if name.lower() == username.lower():
            return name, data
    return None, None


def get_role(username):
    _, user = find_user(username)

    if user:
        return user.get("role", "member")

    return "member"


def is_owner(username):
    return get_role(username) == "owner"


def is_staff(username):
    return get_role(username) in ("owner", "mod")


def add_message(username, text, msg_type="message"):
    message = {
        "username": username,
        "text": text,
        "time": get_time(),
        "type": msg_type
    }

    MESSAGES.append(message)

    if len(MESSAGES) > 500:
        del MESSAGES[:-500]

    return message


def system_message(text):
    msg = add_message("MATIA CHAT", text, "system")
    socketio.emit("message", msg)


def send_to_user(username, event, data):
    for sid, name in CONNECTED.items():
        if name == username:
            socketio.emit(event, data, to=sid)
            break


def broadcast_users():
    users = []

    for username, data in USERS.items():
        users.append({
            "username": username,
            "role": data.get("role", "member"),
            "online": username in CONNECTED.values()
        })

    socketio.emit("users", users)


def disconnect_user(username):
    target_sid = None

    for sid, name in CONNECTED.items():
        if name == username:
            target_sid = sid
            break

    if target_sid:
        socketio.emit(
            "force_disconnect",
            {"reason": "You were removed from MATIA CHAT."},
            to=target_sid
        )

        try:
            socketio.server.disconnect(target_sid)
        except Exception:
            pass


# =========================================================
# PAGE
# =========================================================

@app.route("/")
def index():
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "index.html"
    )

    if not os.path.exists(path):
        return "index.html not found", 500

    return send_file(path)


@app.route("/health")
def health():
    return {"status": "online", "app": "MATIA CHAT"}


# =========================================================
# CONNECT
# =========================================================

@socketio.on("connect")
def connect():
    emit("connected", {
        "status": "ok",
        "group": GROUP
    })


# =========================================================
# LOGIN
# =========================================================

@socketio.on("login")
def login(data):
    username = str(data.get("username", "")).strip()

    if not username:
        emit("login_error", {
            "error": "Please enter a username."
        })
        return

    username = " ".join(username.split())[:20]

    real_name, existing = find_user(username)

    if existing and existing.get("banned"):
        emit("login_error", {
            "error": "You are banned from MATIA CHAT."
        })
        return

    if real_name and real_name in CONNECTED.values():
        emit("login_error", {
            "error": "This username is already online."
        })
        return

    if real_name:
        username = real_name
        USERS[username]["online"] = True
    else:
        role = "owner" if len(USERS) == 0 else "member"

        USERS[username] = {
            "role": role,
            "banned": False,
            "muted": False,
            "online": True
        }

    CONNECTED[request.sid] = username

    emit("login_success", {
        "username": username,
        "role": USERS[username]["role"],
        "group": GROUP,
        "messages": MESSAGES
    })

    system_message(f"{username} joined MATIA CHAT.")
    broadcast_users()


# =========================================================
# DISCONNECT
# =========================================================

@socketio.on("disconnect")
def disconnect():
    username = CONNECTED.pop(request.sid, None)

    if not username:
        return

    if username in USERS:
        USERS[username]["online"] = False

    system_message(f"{username} left MATIA CHAT.")
    broadcast_users()


# =========================================================
# MESSAGES
# =========================================================

@socketio.on("send_message")
def send_message(data):
    username = CONNECTED.get(request.sid)

    if not username:
        return

    text = str(data.get("text", "")).strip()

    if not text:
        return

    text = text[:2000]

    user = USERS.get(username)

    if not user:
        return

    if user.get("banned"):
        return

    if user.get("muted"):
        emit("command_result", {
            "text": "🔇 You are muted."
        })
        return

    if GROUP["locked"] and not is_staff(username):
        emit("command_result", {
            "text": "🔒 The group is locked."
        })
        return

    if text.startswith("/"):
        command(username, text)
        return

    msg = add_message(username, text)
    socketio.emit("message", msg)


# =========================================================
# COMMANDS
# =========================================================

def command(username, text):
    parts = text.split()
    cmd = parts[0].lower()
    args = parts[1:]

    # -------------------------
    # HELP
    # -------------------------

    if cmd == "/help":
        commands = [
            "/help",
            "/fun",
            "/coinflip",
            "/dice",
            "/roll",
            "/8ball",
            "/joke",
            "/rate",
            "/ship",
            "/slap",
            "/hug",
            "/highfive",
            "/dance",
            "/spin",
            "/rps",
            "/trivia",
            "/quiz",
            "/online",
            "/users",
            "/whois",
            "/rules",
            "/time",
            "/party",
            "/fireworks",
            "/confetti",
            "/rainbow",
            "/disco",
            "/matrix",
            "/neon",
            "/fire"
        ]

        if is_staff(username):
            commands += [
                "/ban username",
                "/unban username",
                "/kick username",
                "/mute username",
                "/unmute username"
            ]

        if is_owner(username):
            commands += [
                "/promote username",
                "/demote username",
                "/announce text",
                "/clear",
                "/lock",
                "/unlock",
                "/rename name",
                "/event effect"
            ]

        send_to_user(username, "command_list", {
            "commands": commands
        })
        return

    # -------------------------
    # FUN
    # -------------------------

    if cmd == "/fun":
        send_to_user(username, "command_result", {
            "text": "🎮 FUN: /coinflip /dice /roll /8ball /joke /rate /ship /slap /hug /highfive /dance /spin /rps /trivia /quiz /party /fireworks /confetti /rainbow /disco /matrix /neon /fire"
        })
        return

    if cmd == "/coinflip":
        system_message(
            f"🪙 {username} flipped: {random.choice(['HEADS', 'TAILS'])}"
        )
        return

    if cmd in ("/dice", "/roll"):
        system_message(
            f"🎲 {username} rolled: {random.randint(1, 6)}"
        )
        return

    if cmd == "/8ball":
        answers = [
            "Yes 🔮",
            "No 🔮",
            "Definitely!",
            "Probably.",
            "Ask again later.",
            "Absolutely not.",
            "Looks good!",
            "Maybe..."
        ]

        system_message(
            f"🔮 {username}: {random.choice(answers)}"
        )
        return

    if cmd == "/joke":
        jokes = [
            "😂 Why did the computer go to the doctor? It had a virus.",
            "🐛 Why do programmers like dark mode? Because light attracts bugs.",
            "💻 My PC told me it needed space... so I deleted a game.",
            "⌨️ Why was the keyboard tired? Too many shifts."
        ]

        system_message(random.choice(jokes))
        return

    if cmd == "/rate":
        target = " ".join(args) if args else username
        score = random.randint(1, 100)

        system_message(
            f"⭐ {target} gets {score}/100!"
        )
        return

    if cmd == "/ship":
        if len(args) >= 2:
            a, b = args[0], args[1]
        else:
            a, b = username, "someone"

        score = random.randint(0, 100)

        system_message(
            f"💘 {a} + {b} = {score}%"
        )
        return

    if cmd == "/slap":
        target = " ".join(args) if args else "the chat"
        system_message(f"👋 {username} slapped {target}!")
        return

    if cmd == "/hug":
        target = " ".join(args) if args else "everyone"
        system_message(f"🤗 {username} hugged {target}!")
        return

    if cmd == "/highfive":
        target = " ".join(args) if args else "everyone"
        system_message(f"✋ {username} high-fived {target}!")
        return

    if cmd == "/dance":
        system_message(f"🕺 {username} is dancing! 💃")
        return

    if cmd == "/spin":
        system_message(f"🌀 {username} is spinning!")
        return

    if cmd == "/rps":
        system_message(
            f"✂️ {username} chose {random.choice(['ROCK 🪨', 'PAPER 📄', 'SCISSORS ✂️'])}"
        )
        return

    if cmd == "/trivia":
        questions = [
            "🌍 Largest continent? Asia.",
            "⚽ 2022 World Cup winner? Argentina.",
            "🪐 Red Planet? Mars.",
            "💻 CPU means Central Processing Unit."
        ]

        system_message(random.choice(questions))
        return

    if cmd == "/quiz":
        questions = [
            "🧠 10 × 10 = 100",
            "🧠 A hexagon has 6 sides.",
            "🧠 We live on Earth."
        ]

        system_message(random.choice(questions))
        return

    if cmd == "/online":
        names = list(CONNECTED.values())

        send_to_user(username, "command_result", {
            "text": "🟢 Online: " + ", ".join(names)
        })
        return

    if cmd == "/users":
        send_to_user(username, "command_result", {
            "text": "👥 Users: " + ", ".join(USERS.keys())
        })
        return

    if cmd == "/whois":
        if not args:
            send_to_user(username, "command_result", {
                "text": "Usage: /whois username"
            })
            return

        target, user = find_user(args[0])

        if not user:
            send_to_user(username, "command_result", {
                "text": "❌ User not found."
            })
            return

        online = target in CONNECTED.values()

        send_to_user(username, "command_result", {
            "text": f"👤 {target} | Role: {user['role']} | Online: {online}"
        })
        return

    if cmd == "/rules":
        send_to_user(username, "command_result", {
            "text": "📜 Be respectful • No spam • No harassment • Have fun!"
        })
        return

    if cmd == "/time":
        send_to_user(username, "command_result", {
            "text": f"🕐 Server time: {get_time()}"
        })
        return

    # =====================================================
    # EVENTS
    # =====================================================

    event_map = {
        "/rainbow": "rainbow",
        "/disco": "disco",
        "/matrix": "matrix",
        "/party": "party",
        "/neon": "neon",
        "/fire": "fire",
        "/fireworks": "fireworks",
        "/confetti": "confetti"
    }

    if cmd in event_map:
        effect = event_map[cmd]

        socketio.emit("event", {
            "effect": effect,
            "by": username
        })

        system_message(
            f"✨ {username} activated {effect.upper()}!"
        )
        return

    if cmd == "/event":
        if not args:
            send_to_user(username, "command_result", {
                "text": "Usage: /event rainbow"
            })
            return

        effect = args[0].lower()

        allowed = [
            "rainbow",
            "disco",
            "matrix",
            "party",
            "neon",
            "fire",
            "fireworks",
            "confetti"
        ]

        if effect not in allowed:
            send_to_user(username, "command_result", {
                "text": "❌ Unknown event."
            })
            return

        socketio.emit("event", {
            "effect": effect,
            "by": username
        })

        system_message(
            f"✨ {username} activated {effect.upper()}!"
        )
        return

    # =====================================================
    # STAFF
    # =====================================================

    if cmd in (
        "/ban",
        "/unban",
        "/kick",
        "/mute",
        "/unmute"
    ):
        if not is_staff(username):
            send_to_user(username, "command_result", {
                "text": "❌ Permission denied."
            })
            return

        if not args:
            send_to_user(username, "command_result", {
                "text": f"Usage: {cmd} username"
            })
            return

        target, user = find_user(args[0])

        if not user:
            send_to_user(username, "command_result", {
                "text": "❌ User not found."
            })
            return

        if target == username:
            send_to_user(username, "command_result", {
                "text": "❌ You cannot target yourself."
            })
            return

        if cmd == "/ban":
            user["banned"] = True
            disconnect_user(target)
            system_message(f"🔨 {target} was banned by {username}.")

        elif cmd == "/unban":
            user["banned"] = False
            system_message(f"🔓 {target} was unbanned by {username}.")

        elif cmd == "/kick":
            disconnect_user(target)
            system_message(f"👢 {target} was kicked by {username}.")

        elif cmd == "/mute":
            user["muted"] = True
            system_message(f"🔇 {target} was muted by {username}.")

        elif cmd == "/unmute":
            user["muted"] = False
            system_message(f"🔊 {target} was unmuted by {username}.")

        broadcast_users()
        return

    # =====================================================
    # OWNER
    # =====================================================

    if cmd in (
        "/promote",
        "/demote",
        "/announce",
        "/clear",
        "/lock",
        "/unlock",
        "/rename"
    ):
        if not is_owner(username):
            send_to_user(username, "command_result", {
                "text": "👑 Owner only."
            })
            return

        if cmd == "/promote":
            if not args:
                return

            target, user = find_user(args[0])

            if user:
                user["role"] = "mod"
                system_message(f"🛡️ {target} is now a moderator.")
                broadcast_users()

            return

        if cmd == "/demote":
            if not args:
                return

            target, user = find_user(args[0])

            if user and target != username:
                user["role"] = "member"
                system_message(f"⬇️ {target} was demoted.")
                broadcast_users()

            return

        if cmd == "/announce":
            message = " ".join(args).strip()

            if message:
                socketio.emit("announcement", {
                    "text": message,
                    "by": username
                })

                system_message(
                    f"📢 {username}: {message}"
                )

            return

        if cmd == "/clear":
            MESSAGES.clear()
            socketio.emit("clear_chat")
            system_message(f"🧹 Chat cleared by {username}.")
            return

        if cmd == "/lock":
            GROUP["locked"] = True

            socketio.emit("group_update", {
                "group": GROUP
            })

            system_message(f"🔒 Group locked by {username}.")
            return

        if cmd == "/unlock":
            GROUP["locked"] = False

            socketio.emit("group_update", {
                "group": GROUP
            })

            system_message(f"🔓 Group unlocked by {username}.")
            return

        if cmd == "/rename":
            name = " ".join(args).strip()

            if name:
                GROUP["name"] = name[:40]

                socketio.emit("group_update", {
                    "group": GROUP
                })

                system_message(
                    f"✏️ Group renamed to {GROUP['name']}."
                )

            return

    send_to_user(username, "command_result", {
        "text": f"❓ Unknown command: {cmd}. Use /help."
    })


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    socketio.run(
        app,
        host="0.0.0.0",
        port=port
    )
