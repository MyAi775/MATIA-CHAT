import os
import random
from datetime import datetime

from flask import Flask, send_file, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "matia-chat")

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading"
)

USERS = {}
CONNECTED = {}
MESSAGES = []

GROUP = {
    "name": "MATIA CHAT",
    "locked": False
}


# =========================================================
# BASIC
# =========================================================

def clock():
    return datetime.now().strftime("%H:%M")


def find_user(name):
    for username, data in USERS.items():
        if username.lower() == name.lower():
            return username, data
    return None, None


def role(username):
    _, user = find_user(username)
    return user.get("role", "member") if user else "member"


def owner(username):
    return role(username) == "owner"


def staff(username):
    return role(username) in ("owner", "mod")


def add_message(username, text, msg_type="message"):
    msg = {
        "username": username,
        "text": text,
        "time": clock(),
        "type": msg_type
    }

    MESSAGES.append(msg)

    if len(MESSAGES) > 1000:
        del MESSAGES[:-1000]

    return msg


def system(text):
    socketio.emit(
        "message",
        add_message("MATIA CHAT", text, "system")
    )


def to_user(username, event, data):
    for sid, name in CONNECTED.items():
        if name == username:
            socketio.emit(event, data, to=sid)


def users_update():
    result = []

    for username, data in USERS.items():
        result.append({
            "username": username,
            "role": data["role"],
            "online": username in CONNECTED.values()
        })

    socketio.emit("users", result)


# =========================================================
# 1000 FUN COMMANDS
# =========================================================

FUN_COMMANDS = {}

fun_templates = [
    "😂 {u} just activated FUN MODE!",
    "🔥 {u} is absolutely cracked!",
    "⚡ {u} activated turbo mode!",
    "🎮 {u} unlocked a secret level!",
    "👑 {u} has entered boss mode!",
    "🚀 {u} launched into space!",
    "💀 {u} caused maximum chaos!",
    "🗿 {u} became an absolute legend!",
    "✨ {u} summoned pure randomness!",
    "🎉 {u} started the party!",
    "🌀 {u} activated CHAOS!",
    "😎 {u} is too cool for this server!",
    "🐐 {u} has entered GOAT mode!",
    "🏆 {u} just won absolutely nothing!",
    "💫 {u} broke the simulation!",
    "🤯 {u} confused the entire chat!",
    "🧠 {u} used 999 IQ!",
    "🎲 {u} rolled the universe!",
    "👽 {u} contacted aliens!",
    "🌌 {u} opened a portal!",
]

for i in range(1, 1001):
    FUN_COMMANDS[f"/fun{i}"] = fun_templates[(i - 1) % len(fun_templates)]


# =========================================================
# ROUTES
# =========================================================

@app.route("/")
def home():
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "index.html"
    )

    if not os.path.exists(path):
        return "ERROR: index.html missing", 500

    return send_file(path)


@app.route("/health")
def health():
    return {
        "status": "online",
        "service": "MATIA CHAT"
    }


# =========================================================
# SOCKET
# =========================================================

@socketio.on("connect")
def connected():
    emit("connected", {
        "ok": True,
        "group": GROUP
    })


# =========================================================
# LOGIN
# =========================================================

@socketio.on("login")
def login(data):

    username = str(
        data.get("username", "")
    ).strip()

    username = " ".join(username.split())[:20]

    if not username:
        emit("login_error", {
            "error": "Enter a username."
        })
        return

    real_name, existing = find_user(username)

    if existing and existing.get("banned"):
        emit("login_error", {
            "error": "You are banned."
        })
        return

    if real_name and real_name in CONNECTED.values():
        emit("login_error", {
            "error": "Username already online."
        })
        return

    if real_name:
        username = real_name
    else:
        new_role = "owner" if not USERS else "member"

        USERS[username] = {
            "role": new_role,
            "banned": False,
            "muted": False
        }

    CONNECTED[request.sid] = username

    emit("login_success", {
        "username": username,
        "role": USERS[username]["role"],
        "group": GROUP,
        "messages": MESSAGES
    })

    system(f"🟢 {username} connected to MATIA CHAT.")

    users_update()


# =========================================================
# DISCONNECT
# =========================================================

@socketio.on("disconnect")
def disconnected():

    username = CONNECTED.pop(request.sid, None)

    if username:
        system(f"🔴 {username} disconnected.")
        users_update()


# =========================================================
# SEND
# =========================================================

@socketio.on("send_message")
def message(data):

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
        to_user(username, "command_result", {
            "text": "🔇 You are muted."
        })
        return

    if GROUP["locked"] and not staff(username):
        to_user(username, "command_result", {
            "text": "🔒 Chat is locked."
        })
        return

    if text.startswith("/"):
        execute_command(username, text)
        return

    socketio.emit(
        "message",
        add_message(username, text)
    )


# =========================================================
# COMMAND ENGINE
# =========================================================

def execute_command(username, text):

    parts = text.split()
    cmd = parts[0].lower()
    args = parts[1:]

    # -----------------------------------------------------
    # 1000 FUN
    # -----------------------------------------------------

    if cmd in FUN_COMMANDS:

        template = FUN_COMMANDS[cmd]

        system(
            template.format(u=username)
            + f"  [{cmd}]"
        )

        return

    # -----------------------------------------------------
    # HELP
    # -----------------------------------------------------

    if cmd == "/help":

        commands = [
            "/help",
            "/fun",
            "/fun1 ... /fun1000",
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

        if staff(username):
            commands += [
                "/ban username",
                "/unban username",
                "/kick username",
                "/mute username",
                "/unmute username"
            ]

        if owner(username):
            commands += [
                "/promote username",
                "/demote username",
                "/announce text",
                "/clear",
                "/lock",
                "/unlock",
                "/rename name"
            ]

        to_user(username, "command_list", {
            "commands": commands
        })

        return

    # -----------------------------------------------------
    # FUN LIST
    # -----------------------------------------------------

    if cmd == "/fun":

        to_user(username, "command_result", {
            "text": (
                "🎮 1000 FUN COMMANDS AVAILABLE!\n"
                "Try /fun1, /fun2, /fun100, /fun500 or /fun1000"
            )
        })

        return

    # -----------------------------------------------------
    # COIN
    # -----------------------------------------------------

    if cmd == "/coinflip":

        system(
            f"🪙 {username}: "
            f"{random.choice(['HEADS', 'TAILS'])}"
        )

        return

    # -----------------------------------------------------
    # DICE
    # -----------------------------------------------------

    if cmd in ("/dice", "/roll"):

        system(
            f"🎲 {username} rolled "
            f"{random.randint(1, 6)}"
        )

        return

    # -----------------------------------------------------
    # 8 BALL
    # -----------------------------------------------------

    if cmd == "/8ball":

        answers = [
            "🔮 Yes!",
            "🔮 No!",
            "🔮 Definitely!",
            "🔮 Probably!",
            "🔮 Ask again later.",
            "🔮 Absolutely not!",
            "🔮 100%!",
            "🔮 Maybe..."
        ]

        system(
            f"🔮 {username}: "
            f"{random.choice(answers)}"
        )

        return

    # -----------------------------------------------------
    # JOKE
    # -----------------------------------------------------

    if cmd == "/joke":

        jokes = [
            "😂 Why did the computer go to the doctor? It had a virus.",
            "🐛 Programmers prefer dark mode because light attracts bugs.",
            "💻 My PC needed space, so I deleted a game.",
            "⌨️ The keyboard was tired because it had too many shifts."
        ]

        system(random.choice(jokes))

        return

    # -----------------------------------------------------
    # RATE
    # -----------------------------------------------------

    if cmd == "/rate":

        target = " ".join(args) or username

        system(
            f"⭐ {target}: "
            f"{random.randint(1,100)}/100"
        )

        return

    # -----------------------------------------------------
    # SHIP
    # -----------------------------------------------------

    if cmd == "/ship":

        a = args[0] if len(args) > 0 else username
        b = args[1] if len(args) > 1 else "someone"

        system(
            f"💘 {a} + {b}: "
            f"{random.randint(0,100)}%"
        )

        return

    # -----------------------------------------------------
    # SOCIAL FUN
    # -----------------------------------------------------

    social = {
        "/slap": "👋 {u} slapped {t}!",
        "/hug": "🤗 {u} hugged {t}!",
        "/highfive": "✋ {u} high-fived {t}!",
        "/dance": "🕺 {u} started dancing!",
        "/spin": "🌀 {u} started spinning!"
    }

    if cmd in social:

        target = " ".join(args) or "everyone"

        system(
            social[cmd]
            .format(u=username, t=target)
        )

        return

    # -----------------------------------------------------
    # RPS
    # -----------------------------------------------------

    if cmd == "/rps":

        system(
            f"✂️ {username} chose "
            f"{random.choice(['ROCK 🪨','PAPER 📄','SCISSORS ✂️'])}"
        )

        return

    # -----------------------------------------------------
    # TRIVIA
    # -----------------------------------------------------

    if cmd == "/trivia":

        questions = [
            "🌍 Largest continent? Asia.",
            "⚽ 2022 World Cup winner? Argentina.",
            "🪐 Red Planet? Mars.",
            "💻 CPU = Central Processing Unit.",
            "🌊 Largest ocean? Pacific Ocean."
        ]

        system(random.choice(questions))

        return

    # -----------------------------------------------------
    # QUIZ
    # -----------------------------------------------------

    if cmd == "/quiz":

        system(
            random.choice([
                "🧠 10 × 10 = 100",
                "🧠 A hexagon has 6 sides.",
                "🧠 Earth is our planet.",
                "🧠 Water freezes at 0°C."
            ])
        )

        return

    # -----------------------------------------------------
    # ONLINE
    # -----------------------------------------------------

    if cmd == "/online":

        names = list(CONNECTED.values())

        to_user(username, "command_result", {
            "text": "🟢 Online: " + ", ".join(names)
        })

        return

    # -----------------------------------------------------
    # USERS
    # -----------------------------------------------------

    if cmd == "/users":

        to_user(username, "command_result", {
            "text": "👥 Users: " + ", ".join(USERS.keys())
        })

        return

    # -----------------------------------------------------
    # WHOIS
    # -----------------------------------------------------

    if cmd == "/whois":

        if not args:
            to_user(username, "command_result", {
                "text": "Usage: /whois username"
            })
            return

        target, user = find_user(args[0])

        if not user:
            to_user(username, "command_result", {
                "text": "User not found."
            })
            return

        to_user(username, "command_result", {
            "text": (
                f"👤 {target} | "
                f"Role: {user['role']} | "
                f"Online: {target in CONNECTED.values()}"
            )
        })

        return

    # -----------------------------------------------------
    # RULES
    # -----------------------------------------------------

    if cmd == "/rules":

        to_user(username, "command_result", {
            "text": "📜 Respect others • No spam • Have fun!"
        })

        return

    # -----------------------------------------------------
    # TIME
    # -----------------------------------------------------

    if cmd == "/time":

        to_user(username, "command_result", {
            "text": f"🕐 Server time: {clock()}"
        })

        return

    # -----------------------------------------------------
    # EFFECTS
    # -----------------------------------------------------

    effects = {
        "/rainbow": "rainbow",
        "/disco": "disco",
        "/matrix": "matrix",
        "/party": "party",
        "/neon": "neon",
        "/fire": "fire",
        "/fireworks": "fireworks",
        "/confetti": "confetti"
    }

    if cmd in effects:

        socketio.emit("event", {
            "effect": effects[cmd],
            "by": username
        })

        system(
            f"✨ {username} activated "
            f"{effects[cmd].upper()}!"
        )

        return

    # -----------------------------------------------------
    # /event
    # -----------------------------------------------------

    if cmd == "/event":

        if not args:
            to_user(username, "command_result", {
                "text": "Usage: /event disco"
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
            to_user(username, "command_result", {
                "text": "Unknown effect."
            })
            return

        socketio.emit("event", {
            "effect": effect,
            "by": username
        })

        system(
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

        if not staff(username):
            to_user(username, "command_result", {
                "text": "❌ Permission denied."
            })
            return

        if not args:
            to_user(username, "command_result", {
                "text": f"Usage: {cmd} username"
            })
            return

        target, user = find_user(args[0])

        if not user:
            to_user(username, "command_result", {
                "text": "User not found."
            })
            return

        if target == username:
            return

        if cmd == "/ban":

            user["banned"] = True

            system(
                f"🔨 {target} was banned by {username}."
            )

            kick(target)

        elif cmd == "/unban":

            user["banned"] = False

            system(
                f"🔓 {target} was unbanned."
            )

        elif cmd == "/kick":

            system(
                f"👢 {target} was kicked by {username}."
            )

            kick(target)

        elif cmd == "/mute":

            user["muted"] = True

            system(
                f"🔇 {target} was muted."
            )

        elif cmd == "/unmute":

            user["muted"] = False

            system(
                f"🔊 {target} was unmuted."
            )

        users_update()

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

        if not owner(username):

            to_user(username, "command_result", {
                "text": "👑 Owner only."
            })

            return

        if cmd == "/promote":

            if not args:
                return

            target, user = find_user(args[0])

            if user:

                user["role"] = "mod"

                system(
                    f"🛡️ {target} is now MOD."
                )

                users_update()

            return

        if cmd == "/demote":

            if not args:
                return

            target, user = find_user(args[0])

            if user and target != username:

                user["role"] = "member"

                system(
                    f"⬇️ {target} is now MEMBER."
                )

                users_update()

            return

        if cmd == "/announce":

            text2 = " ".join(args)

            if text2:

                socketio.emit("announcement", {
                    "text": text2,
                    "by": username
                })

                system(
                    f"📢 {username}: {text2}"
                )

            return

        if cmd == "/clear":

            MESSAGES.clear()

            socketio.emit("clear_chat")

            system(
                f"🧹 Chat cleared by {username}."
            )

            return

        if cmd == "/lock":

            GROUP["locked"] = True

            socketio.emit(
                "group_update",
                {"group": GROUP}
            )

            system(
                f"🔒 Chat locked by {username}."
            )

            return

        if cmd == "/unlock":

            GROUP["locked"] = False

            socketio.emit(
                "group_update",
                {"group": GROUP}
            )

            system(
                f"🔓 Chat unlocked by {username}."
            )

            return

        if cmd == "/rename":

            name = " ".join(args).strip()

            if name:

                GROUP["name"] = name[:40]

                socketio.emit(
                    "group_update",
                    {"group": GROUP}
                )

                system(
                    f"✏️ Group renamed to {GROUP['name']}."
                )

            return

    # -----------------------------------------------------
    # UNKNOWN
    # -----------------------------------------------------

    to_user(username, "command_result", {
        "text": f"❓ Unknown command: {cmd}. Try /help."
    })


# =========================================================
# KICK
# =========================================================

def kick(username):

    sid_to_remove = None

    for sid, name in CONNECTED.items():

        if name == username:
            sid_to_remove = sid
            break

    if sid_to_remove:

        socketio.emit(
            "force_disconnect",
            {
                "reason": "You were removed from MATIA CHAT."
            },
            to=sid_to_remove
        )

        CONNECTED.pop(sid_to_remove, None)


# =========================================================
# START
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
