import os
import random
import time
from datetime import datetime

from flask import Flask, request, send_file
from flask_socketio import SocketIO, emit


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "matia-chat-secret")

socketio = SocketIO(app, cors_allowed_origins="*")


# =========================================================
# DATA
# =========================================================

USERS = {}
CONNECTED = {}
MESSAGES = []

GROUP = {
    "name": "MATIA CHAT",
    "locked": False
}

MAX_USERNAME = 20
MAX_MESSAGE = 2000


# =========================================================
# HELPERS
# =========================================================

def now():
    return datetime.now().strftime("%H:%M")


def clean_username(username):
    if not username:
        return ""

    username = str(username).strip()
    username = " ".join(username.split())

    return username[:MAX_USERNAME]


def find_user(username):
    username_lower = username.lower()

    for name, data in USERS.items():
        if name.lower() == username_lower:
            return name, data

    return None, None


def is_online(username):
    return username in CONNECTED


def online_users():
    return list(CONNECTED.values())


def add_message(username, text, msg_type="message"):
    message = {
        "username": username,
        "text": text,
        "time": now(),
        "type": msg_type
    }

    MESSAGES.append(message)

    if len(MESSAGES) > 500:
        del MESSAGES[:-500]

    return message


def broadcast_system(text):
    message = add_message("MATIA CHAT", text, "system")
    socketio.emit("message", message)


def broadcast_users():
    users = []

    for username, role in USERS.items():
        users.append({
            "username": username,
            "role": role.get("role", "member"),
            "online": username in CONNECTED.values()
        })

    socketio.emit("users", users)


def get_role(username):
    user, data = find_user(username)

    if not data:
        return "member"

    return data.get("role", "member")


def is_staff(username):
    return get_role(username) in ("owner", "mod")


def is_owner(username):
    return get_role(username) == "owner"


def command_help(username):
    role = get_role(username)

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
        "/fire",
    ]

    if role in ("owner", "mod"):
        commands += [
            "/ban username",
            "/unban username",
            "/kick username",
            "/mute username",
            "/unmute username",
        ]

    if role == "owner":
        commands += [
            "/promote username",
            "/demote username",
            "/announce text",
            "/clear",
            "/lock",
            "/unlock",
            "/rename name",
            "/event effect",
        ]

    return commands


# =========================================================
# ROUTES
# =========================================================

@app.route("/")
def index():
    # index.html is next to app.py
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

    if not os.path.exists(path):
        return """
        <h1>MATIA CHAT ERROR</h1>
        <p>index.html was not found.</p>
        <p>Make sure index.html is in the same folder as app.py.</p>
        """, 500

    return send_file(path)


@app.route("/health")
def health():
    return {
        "status": "online",
        "service": "MATIA CHAT"
    }


# =========================================================
# CONNECT
# =========================================================

@socketio.on("connect")
def handle_connect():
    emit("connected", {
        "status": "connected",
        "group": GROUP
    })


# =========================================================
# LOGIN
# =========================================================

@socketio.on("login")
def handle_login(data):
    sid = request.sid

    username = clean_username(
        data.get("username", "") if isinstance(data, dict) else ""
    )

    if not username:
        emit("login_error", {
            "error": "Enter a username."
        })
        return

    username_real, existing = find_user(username)

    if existing and existing.get("banned"):
        emit("login_error", {
            "error": "You are banned from MATIA CHAT."
        })
        return

    if username_real and username_real in CONNECTED.values():
        emit("login_error", {
            "error": "That username is already online."
        })
        return

    # First user becomes owner
    if not USERS:
        role = "owner"
    elif existing:
        role = existing.get("role", "member")
    else:
        role = "member"

    if username_real:
        username = username_real
        USERS[username]["online"] = True
    else:
        USERS[username] = {
            "role": role,
            "banned": False,
            "muted": False,
            "online": True,
            "joined": time.time()
        }

    CONNECTED[sid] = username

    emit("login_success", {
        "username": username,
        "role": USERS[username]["role"],
        "group": GROUP,
        "messages": MESSAGES
    })

    broadcast_system(f"{username} joined MATIA CHAT.")
    broadcast_users()


# =========================================================
# DISCONNECT
# =========================================================

@socketio.on("disconnect")
def handle_disconnect():
    username = CONNECTED.pop(request.sid, None)

    if not username:
        return

    if username in USERS:
        USERS[username]["online"] = False

    broadcast_system(f"{username} left MATIA CHAT.")
    broadcast_users()


# =========================================================
# MESSAGE
# =========================================================

@socketio.on("send_message")
def handle_message(data):
    sid = request.sid

    username = CONNECTED.get(sid)

    if not username:
        return

    text = ""

    if isinstance(data, dict):
        text = str(data.get("text", "")).strip()

    if not text:
        return

    text = text[:MAX_MESSAGE]

    user = USERS.get(username, {})

    if user.get("banned"):
        emit("command_result", {
            "text": "You are banned."
        })
        return

    if user.get("muted"):
        emit("command_result", {
            "text": "You are muted."
        })
        return

    if GROUP["locked"] and not is_staff(username):
        emit("command_result", {
            "text": "The group is locked."
        })
        return

    # Commands
    if text.startswith("/"):
        handle_command(username, text)
        return

    message = add_message(username, text)
    socketio.emit("message", message)


# =========================================================
# COMMAND ENGINE
# =========================================================

def handle_command(username, text):
    parts = text.split()
    command = parts[0].lower()
    args = parts[1:]

    # -----------------------------------------------------
    # HELP
    # -----------------------------------------------------

    if command == "/help":
        emit_to_user(username, "commands", {
            "commands": command_help(username)
        })
        return

    # -----------------------------------------------------
    # FUN MENU
    # -----------------------------------------------------

    if command == "/fun":
        emit_to_user(username, "command_result", {
            "text": (
                "🎮 FUN COMMANDS: "
                "/coinflip /dice /roll /8ball /joke /rate /ship "
                "/slap /hug /highfive /dance /spin /rps /trivia "
                "/quiz /party /fireworks /confetti /rainbow /disco "
                "/matrix /neon /fire"
            )
        })
        return

    # -----------------------------------------------------
    # COINFLIP
    # -----------------------------------------------------

    if command == "/coinflip":
        result = random.choice(["Heads 🪙", "Tails 🪙"])

        broadcast_system(f"{username} flipped a coin: {result}")
        return

    # -----------------------------------------------------
    # DICE
    # -----------------------------------------------------

    if command in ("/dice", "/roll"):
        result = random.randint(1, 6)

        broadcast_system(f"🎲 {username} rolled a {result}.")
        return

    # -----------------------------------------------------
    # 8 BALL
    # -----------------------------------------------------

    if command == "/8ball":
        answers = [
            "Yes. 🔮",
            "No. 🔮",
            "Definitely.",
            "Probably.",
            "Ask again later.",
            "Absolutely not.",
            "Looks good!",
            "I wouldn't count on it."
        ]

        broadcast_system(
            f"🔮 {username}: {random.choice(answers)}"
        )
        return

    # -----------------------------------------------------
    # JOKE
    # -----------------------------------------------------

    if command == "/joke":
        jokes = [
            "Why did the computer go to the doctor? It had a virus. 😂",
            "Why was the keyboard tired? It had too many shifts. 😂",
            "I told my PC a joke... it needed a reboot. 💀",
            "Why do programmers prefer dark mode? Because light attracts bugs. 🐛"
        ]

        broadcast_system(random.choice(jokes))
        return

    # -----------------------------------------------------
    # RATE
    # -----------------------------------------------------

    if command == "/rate":
        target = " ".join(args) if args else username
        score = random.randint(1, 100)

        broadcast_system(
            f"⭐ MATIA CHAT rates {target}: {score}/100"
        )
        return

    # -----------------------------------------------------
    # SHIP
    # -----------------------------------------------------

    if command == "/ship":
        if len(args) >= 2:
            a = args[0]
            b = args[1]
        else:
            a = username
            b = "someone"

        score = random.randint(0, 100)

        broadcast_system(
            f"💘 {a} + {b} = {score}% compatibility!"
        )
        return

    # -----------------------------------------------------
    # SLAP
    # -----------------------------------------------------

    if command == "/slap":
        target = " ".join(args) if args else "the chat"

        broadcast_system(
            f"👋 {username} slapped {target}!"
        )
        return

    # -----------------------------------------------------
    # HUG
    # -----------------------------------------------------

    if command == "/hug":
        target = " ".join(args) if args else "everyone"

        broadcast_system(
            f"🤗 {username} hugged {target}!"
        )
        return

    # -----------------------------------------------------
    # HIGH FIVE
    # -----------------------------------------------------

    if command == "/highfive":
        target = " ".join(args) if args else "everyone"

        broadcast_system(
            f"✋ {username} gave {target} a HIGH FIVE!"
        )
        return

    # -----------------------------------------------------
    # DANCE
    # -----------------------------------------------------

    if command == "/dance":
        broadcast_system(
            f"🕺 {username} started dancing! 💃"
        )
        return

    # -----------------------------------------------------
    # SPIN
    # -----------------------------------------------------

    if command == "/spin":
        broadcast_system(
            f"🌀 {username} is spinning!"
        )
        return

    # -----------------------------------------------------
    # RPS
    # -----------------------------------------------------

    if command == "/rps":
        choices = ["rock 🪨", "paper 📄", "scissors ✂️"]
        result = random.choice(choices)

        broadcast_system(
            f"✂️ {username} played RPS: {result}"
        )
        return

    # -----------------------------------------------------
    # TRIVIA
    # -----------------------------------------------------

    if command == "/trivia":
        trivia = [
            "🌍 What is the largest continent? Asia!",
            "⚽ Which country won the 2022 World Cup? Argentina!",
            "🪐 Which planet is known as the Red Planet? Mars!",
            "💻 What does CPU stand for? Central Processing Unit!"
        ]

        broadcast_system(random.choice(trivia))
        return

    # -----------------------------------------------------
    # QUIZ
    # -----------------------------------------------------

    if command == "/quiz":
        quizzes = [
            "🧠 QUIZ: What is 10 × 10? Answer: 100.",
            "🧠 QUIZ: How many sides does a hexagon have? 6.",
            "🧠 QUIZ: What planet do we live on? Earth."
        ]

        broadcast_system(random.choice(quizzes))
        return

    # -----------------------------------------------------
    # ONLINE
    # -----------------------------------------------------

    if command == "/online":
        names = online_users()

        if names:
            text_result = "🟢 Online: " + ", ".join(names)
        else:
            text_result = "No users online."

        emit_to_user(username, "command_result", {
            "text": text_result
        })
        return

    # -----------------------------------------------------
    # USERS
    # -----------------------------------------------------

    if command == "/users":
        names = list(USERS.keys())

        emit_to_user(username, "command_result", {
            "text": "👥 Users: " + ", ".join(names)
        })
        return

    # -----------------------------------------------------
    # WHOIS
    # -----------------------------------------------------

    if command == "/whois":
        if not args:
            emit_to_user(username, "command_result", {
                "text": "Usage: /whois username"
            })
            return

        target, user = find_user(args[0])

        if not user:
            emit_to_user(username, "command_result", {
                "text": "User not found."
            })
            return

        emit_to_user(username, "command_result", {
            "text": (
                f"👤 {target} | "
                f"Role: {user.get('role')} | "
                f"Online: {'Yes' if target in CONNECTED.values() else 'No'}"
            )
        })
        return

    # -----------------------------------------------------
    # RULES
    # -----------------------------------------------------

    if command == "/rules":
        emit_to_user(username, "command_result", {
            "text": (
                "📜 RULES: Be respectful • No spam • "
                "No harassment • Have fun!"
            )
        })
        return

    # -----------------------------------------------------
    # TIME
    # -----------------------------------------------------

    if command == "/time":
        emit_to_user(username, "command_result", {
            "text": f"🕐 Server time: {now()}"
        })
        return

    # -----------------------------------------------------
    # GLOBAL EVENTS
    # -----------------------------------------------------

    event_commands = {
        "/rainbow": "rainbow",
        "/disco": "disco",
        "/matrix": "matrix",
        "/party": "party",
        "/neon": "neon",
        "/fire": "fire",
        "/fireworks": "fireworks",
        "/confetti": "confetti"
    }

    if command in event_commands:
        effect = event_commands[command]

        socketio.emit("event", {
            "effect": effect,
            "by": username
        })

        broadcast_system(
            f"✨ {username} activated {effect.upper()}!"
        )
        return

    # -----------------------------------------------------
    # /event
    # -----------------------------------------------------

    if command == "/event":
        if not args:
            emit_to_user(username, "command_result", {
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
            emit_to_user(username, "command_result", {
                "text": "Unknown event."
            })
            return

        socketio.emit("event", {
            "effect": effect,
            "by": username
        })

        broadcast_system(
            f"✨ {username} activated {effect.upper()}!"
        )
        return

    # =====================================================
    # STAFF COMMANDS
    # =====================================================

    if command in (
        "/ban",
        "/unban",
        "/kick",
        "/mute",
        "/unmute"
    ):
        if not is_staff(username):
            emit_to_user(username, "command_result", {
                "text": "❌ You don't have permission."
            })
            return

        if not args:
            emit_to_user(username, "command_result", {
                "text": f"Usage: {command} username"
            })
            return

        target, user = find_user(args[0])

        if not user:
            emit_to_user(username, "command_result", {
                "text": "❌ User not found."
            })
            return

        if target == username:
            emit_to_user(username, "command_result", {
                "text": "❌ You cannot target yourself."
            })
            return

        # BAN
        if command == "/ban":
            user["banned"] = True

            kick_user(target)

            broadcast_system(
                f"🔨 {target} was banned by {username}."
            )

            broadcast_users()
            return

        # UNBAN
        if command == "/unban":
            user["banned"] = False

            broadcast_system(
                f"🔓 {target} was unbanned by {username}."
            )

            return

        # KICK
        if command == "/kick":
            kick_user(target)

            broadcast_system(
                f"👢 {target} was kicked by {username}."
            )

            broadcast_users()
            return

        # MUTE
        if command == "/mute":
            user["muted"] = True

            broadcast_system(
                f"🔇 {target} was muted by {username}."
            )

            return

        # UNMUTE
        if command == "/unmute":
            user["muted"] = False

            broadcast_system(
                f"🔊 {target} was unmuted by {username}."
            )

            return

    # =====================================================
    # OWNER COMMANDS
    # =====================================================

    if command in (
        "/promote",
        "/demote",
        "/announce",
        "/clear",
        "/lock",
        "/unlock",
        "/rename"
    ):
        if not is_owner(username):
            emit_to_user(username, "command_result", {
                "text": "❌ Owner only."
            })
            return

        # PROMOTE
        if command == "/promote":
            if not args:
                emit_to_user(username, "command_result", {
                    "text": "Usage: /promote username"
                })
                return

            target, user = find_user(args[0])

            if not user:
                emit_to_user(username, "command_result", {
                    "text": "User not found."
                })
                return

            user["role"] = "mod"

            broadcast_system(
                f"🛡️ {target} is now a moderator."
            )

            broadcast_users()
            return

        # DEMOTE
        if command == "/demote":
            if not args:
                emit_to_user(username, "command_result", {
                    "text": "Usage: /demote username"
                })
                return

            target, user = find_user(args[0])

            if not user:
                emit_to_user(username, "command_result", {
                    "text": "User not found."
                })
                return

            if target == username:
                emit_to_user(username, "command_result", {
                    "text": "❌ You cannot demote yourself."
                })
                return

            user["role"] = "member"

            broadcast_system(
                f"⬇️ {target} was demoted to member."
            )

            broadcast_users()
            return

        # ANNOUNCE
        if command == "/announce":
            announcement = " ".join(args).strip()

            if not announcement:
                emit_to_user(username, "command_result", {
                    "text": "Usage: /announce message"
                })
                return

            socketio.emit("announcement", {
                "text": announcement,
                "by": username
            })

            broadcast_system(
                f"📢 {username}: {announcement}"
            )
            return

        # CLEAR
        if command == "/clear":
            MESSAGES.clear()

            socketio.emit("clear_chat")

            broadcast_system(
                f"🧹 Chat cleared by {username}."
            )
            return

        # LOCK
        if command == "/lock":
            GROUP["locked"] = True

            socketio.emit("group_update", {
                "group": GROUP
            })

            broadcast_system(
                f"🔒 Group locked by {username}."
            )
            return

        # UNLOCK
        if command == "/unlock":
            GROUP["locked"] = False

            socketio.emit("group_update", {
                "group": GROUP
            })

            broadcast_system(
                f"🔓 Group unlocked by {username}."
            )
            return

        # RENAME
        if command == "/rename":
            new_name = " ".join(args).strip()

            if not new_name:
                emit_to_user(username, "command_result", {
                    "text": "Usage: /rename new name"
                })
                return

            GROUP["name"] = new_name[:40]

            socketio.emit("group_update", {
                "group": GROUP
            })

            broadcast_system(
                f"✏️ Group renamed to {GROUP['name']}."
            )
            return

    # Unknown command
    emit_to_user(username, "command_result", {
        "text": f"❓ Unknown command: {command}. Use /help."
    })


# =========================================================
# UTILITY FUNCTIONS
# =========================================================

def emit_to_user(username, event, data):
    for sid, connected_username in CONNECTED.items():
        if connected_username == username:
            socketio.emit(event, data, to=sid)
            return


def kick_user(username):
    target_sid = None

    for sid, connected_username in CONNECTED.items():
        if connected_username == username:
            target_sid = sid
            break

    if target_sid:
        socketio.emit("force_disconnect", {
            "reason": "You were removed from MATIA CHAT."
        }, to=target_sid)

        socketio.server.disconnect(target_sid)


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
