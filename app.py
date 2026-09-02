import os
import random
import time
from datetime import datetime

from flask import Flask, jsonify, request, send_file
from flask_socketio import SocketIO, emit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = "matia-chat-secret"

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading"
)

# =========================================================
# DATA
# =========================================================

USERS = {}
MESSAGES = []
BANNED = set()
MUTED = set()

GROUP = {
    "name": "MATIA CHAT",
    "locked": False
}

MAX_MESSAGES = 500


# =========================================================
# HELPERS
# =========================================================

def now():
    return datetime.now().strftime("%H:%M")


def clean_username(name):
    name = str(name or "").strip()
    name = name[:24]

    if not name:
        return None

    allowed = []
    for c in name:
        if c.isalnum() or c in "_- ":
            allowed.append(c)

    name = "".join(allowed).strip()

    return name if name else None


def clean_text(text):
    return str(text or "").strip()[:2000]


def add_message(username, text, kind="message"):
    msg = {
        "id": int(time.time() * 1000) + random.randint(0, 999),
        "username": username,
        "text": text,
        "time": now(),
        "kind": kind
    }

    MESSAGES.append(msg)

    if len(MESSAGES) > MAX_MESSAGES:
        del MESSAGES[:-MAX_MESSAGES]

    return msg


def broadcast_message(msg):
    socketio.emit("new_message", msg)


def system_message(text):
    msg = add_message("MATIA BOT", text, "system")
    broadcast_message(msg)
    return msg


def users_payload():
    result = []

    for username, info in USERS.items():
        result.append({
            "username": username,
            "role": info.get("role", "member"),
            "online": info.get("online", False),
            "banned": username in BANNED,
            "muted": username in MUTED
        })

    return result


def send_users():
    socketio.emit("users_update", {
        "users": users_payload()
    })


def role(username):
    if username not in USERS:
        return "member"

    return USERS[username].get("role", "member")


def is_staff(username):
    return role(username) in ("owner", "admin", "mod")


def is_owner(username):
    return role(username) == "owner"


# =========================================================
# FUN COMMANDS
# =========================================================

FUN_TEMPLATES = [
    "😂 {user} just activated FUN MODE!",
    "🔥 {user} has entered the danger zone!",
    "🚀 {user} launched into orbit!",
    "🗿 {user} has achieved maximum sigma.",
    "💀 {user} disconnected from reality.",
    "👽 {user} has been abducted by aliens.",
    "⚡ {user} charged up to 100%.",
    "🎮 {user} unlocked a secret achievement!",
    "🐐 {user} is officially the GOAT.",
    "🧠 {user} used 200% of their brain.",
    "🌪️ {user} created a random tornado.",
    "💎 {user} found a legendary diamond.",
    "👑 {user} is now the king of MATIA CHAT.",
    "🍕 {user} ordered 999 pizzas.",
    "🐔 {user} has challenged a chicken to a duel.",
    "🦈 {user} is swimming with sharks.",
    "🌋 {user} accidentally activated a volcano.",
    "🛸 {user} stole an alien spaceship.",
    "🎉 {user} started a party!",
    "💫 {user} just broke the laws of physics."
]

FUN_COMMANDS = {}

for i in range(1, 1001):
    FUN_COMMANDS[f"/fun{i}"] = random.choice(FUN_TEMPLATES)


# =========================================================
# HTTP ROUTES
# =========================================================

@app.route("/")
def home():
    return send_file(os.path.join(BASE_DIR, "index.html"))


@app.route("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "MATIA CHAT",
        "users": len(USERS),
        "messages": len(MESSAGES)
    })


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}

    username = clean_username(data.get("username"))

    if not username:
        return jsonify({
            "ok": False,
            "error": "Invalid username"
        }), 400

    if username in BANNED:
        return jsonify({
            "ok": False,
            "error": "You are banned."
        }), 403

    if username not in USERS:
        first_user = len(USERS) == 0

        USERS[username] = {
            "role": "owner" if first_user else "member",
            "online": True
        }
    else:
        USERS[username]["online"] = True

    return jsonify({
        "ok": True,
        "username": username,
        "role": role(username),
        "users": users_payload()
    })


@app.route("/api/messages")
def api_messages():
    return jsonify({
        "ok": True,
        "messages": MESSAGES[-200:],
        "users": users_payload(),
        "group": GROUP
    })


@app.route("/api/messages", methods=["POST"])
def api_send_message():
    data = request.get_json(silent=True) or {}

    username = clean_username(data.get("username"))
    text = clean_text(data.get("text"))

    if not username or not text:
        return jsonify({"ok": False}), 400

    if username in BANNED:
        return jsonify({
            "ok": False,
            "error": "Banned"
        }), 403

    if username in MUTED:
        return jsonify({
            "ok": False,
            "error": "Muted"
        }), 403

    if GROUP["locked"] and not is_staff(username):
        return jsonify({
            "ok": False,
            "error": "Chat is locked"
        }), 403

    msg = add_message(username, text)

    broadcast_message(msg)

    return jsonify({
        "ok": True,
        "message": msg
    })


@app.route("/api/command", methods=["POST"])
def api_command():
    data = request.get_json(silent=True) or {}

    username = clean_username(data.get("username"))
    command = clean_text(data.get("command"))

    if not username or not command:
        return jsonify({"ok": False}), 400

    result = execute_command(username, command)

    return jsonify(result)


# =========================================================
# COMMAND ENGINE
# =========================================================

def execute_command(username, command):
    raw = command.strip()

    if not raw.startswith("/"):
        return {
            "ok": False,
            "error": "Not a command"
        }

    parts = raw.split()
    cmd = parts[0].lower()
    args = parts[1:]

    # ---------------------------------------------
    # 1000 FUN COMMANDS
    # ---------------------------------------------

    if cmd in FUN_COMMANDS:
        text = FUN_COMMANDS[cmd].format(user=username)

        msg = add_message("MATIA BOT", text, "bot")
        broadcast_message(msg)

        return {
            "ok": True,
            "message": msg
        }

    # ---------------------------------------------
    # FUN RANDOM
    # ---------------------------------------------

    if cmd == "/fun":
        text = random.choice(FUN_TEMPLATES).format(user=username)

        msg = add_message("MATIA BOT", text, "bot")
        broadcast_message(msg)

        return {"ok": True, "message": msg}

    # ---------------------------------------------
    # HELP
    # ---------------------------------------------

    if cmd in ("/help", "/commands"):
        text = (
            "🧠 MATIA CHAT COMMANDS\n\n"
            "🎉 /fun\n"
            "🎲 /dice\n"
            "🪙 /coinflip\n"
            "🎱 /8ball\n"
            "😂 /joke\n"
            "⭐ /rate name\n"
            "❤️ /ship name1 name2\n"
            "✋ /slap name\n"
            "🤗 /hug name\n"
            "🖐️ /highfive name\n"
            "💃 /dance\n"
            "🎮 /rps rock/paper/scissors\n"
            "🧠 /trivia\n"
            "👥 /online\n"
            "📜 /rules\n"
            "🕐 /time\n\n"
            "🌈 /rainbow\n"
            "🟩 /matrix\n"
            "🎉 /party\n"
            "💡 /neon\n"
            "🔥 /fire\n"
            "🎆 /fireworks\n"
            "🎊 /confetti\n\n"
            "👑 STAFF COMMANDS\n"
            "/announce message\n"
            "/kick name\n"
            "/ban name\n"
            "/unban name\n"
            "/mute name\n"
            "/unmute name\n"
            "/promote name\n"
            "/demote name\n"
            "/lock\n"
            "/unlock\n"
            "/rename new name\n"
            "/clear"
        )

        msg = add_message("MATIA BOT", text, "help")
        broadcast_message(msg)

        return {"ok": True, "message": msg}

    # ---------------------------------------------
    # COIN
    # ---------------------------------------------

    if cmd == "/coinflip":
        result = random.choice(["HEADS 🪙", "TAILS 🪙"])

        msg = add_message(
            "MATIA BOT",
            f"{username} flipped the coin → {result}",
            "bot"
        )

        broadcast_message(msg)

        return {"ok": True, "message": msg}

    # ---------------------------------------------
    # DICE
    # ---------------------------------------------

    if cmd in ("/dice", "/roll"):
        number = random.randint(1, 6)

        msg = add_message(
            "MATIA BOT",
            f"🎲 {username} rolled a {number}!",
            "bot"
        )

        broadcast_message(msg)

        return {"ok": True, "message": msg}

    # ---------------------------------------------
    # 8 BALL
    # ---------------------------------------------

    if cmd == "/8ball":
        answers = [
            "Yes. Absolutely. 🔮",
            "Nope. ❌",
            "Maybe... 👀",
            "Definitely! 🔥",
            "Ask again later. 🧠",
            "100% yes. 💯",
            "The matrix says yes. 🟩",
            "I wouldn't risk it. 💀"
        ]

        msg = add_message(
            "MATIA BOT",
            f"🎱 {username}: {random.choice(answers)}",
            "bot"
        )

        broadcast_message(msg)

        return {"ok": True, "message": msg}

    # ---------------------------------------------
    # JOKE
    # ---------------------------------------------

    if cmd == "/joke":
        jokes = [
            "Why did the computer go to the doctor? It had a virus. 💻😂",
            "Why was the keyboard tired? Too many shifts. ⌨️😂",
            "I told my PC a joke... it needed more RAM to understand it. 🧠",
            "What does a hacker's coffee say? Access granted. ☕",
            "Why did the Wi-Fi break up? There was no connection. 💔📶"
        ]

        msg = add_message(
            "MATIA BOT",
            random.choice(jokes),
            "bot"
        )

        broadcast_message(msg)

        return {"ok": True, "message": msg}

    # ---------------------------------------------
    # RATE
    # ---------------------------------------------

    if cmd == "/rate":
        target = " ".join(args) if args else username
        score = random.randint(1, 100)

        msg = add_message(
            "MATIA BOT",
            f"⭐ MATIA rates {target}: {score}/100",
            "bot"
        )

        broadcast_message(msg)

        return {"ok": True, "message": msg}

    # ---------------------------------------------
    # SHIP
    # ---------------------------------------------

    if cmd == "/ship":
        if len(args) >= 2:
            a = args[0]
            b = args[1]
        else:
            a = username
            b = "MATIA"

        score = random.randint(0, 100)

        msg = add_message(
            "MATIA BOT",
            f"❤️ {a} + {b} = {score}% compatibility!",
            "bot"
        )

        broadcast_message(msg)

        return {"ok": True, "message": msg}

    # ---------------------------------------------
    # ACTIONS
    # ---------------------------------------------

    actions = {
        "/slap": "👋 {user} slapped {target}!",
        "/hug": "🤗 {user} hugged {target}!",
        "/highfive": "🖐️ {user} high-fived {target}!",
        "/dance": "💃 {user} is DANCING!",
        "/spin": "🌀 {user} started spinning!",
    }

    if cmd in actions:
        target = "everyone"

        if args:
            target = " ".join(args)

        text = actions[cmd].format(
            user=username,
            target=target
        )

        msg = add_message("MATIA BOT", text, "action")
        broadcast_message(msg)

        return {"ok": True, "message": msg}

    # ---------------------------------------------
    # RPS
    # ---------------------------------------------

    if cmd == "/rps":
        choices = ["rock", "paper", "scissors"]

        player = args[0].lower() if args else random.choice(choices)

        if player not in choices:
            player = random.choice(choices)

        bot = random.choice(choices)

        if player == bot:
            result = "DRAW 🤝"
        elif (
            (player == "rock" and bot == "scissors") or
            (player == "paper" and bot == "rock") or
            (player == "scissors" and bot == "paper")
        ):
            result = "YOU WIN 🏆"
        else:
            result = "BOT WINS 🤖"

        msg = add_message(
            "MATIA BOT",
            f"🎮 {username}: {player} vs {bot} → {result}",
            "bot"
        )

        broadcast_message(msg)

        return {"ok": True, "message": msg}

    # ---------------------------------------------
    # TRIVIA
    # ---------------------------------------------

    if cmd in ("/trivia", "/quiz"):
        questions = [
            "🌍 What is the capital of France? → Paris 🇫🇷",
            "🪐 Which planet is known as the Red Planet? → Mars 🔴",
            "⚽ How many players are on a football team on the pitch? → 11",
            "💻 What does CPU stand for? → Central Processing Unit",
            "🌊 Which is the largest ocean? → Pacific Ocean"
        ]

        msg = add_message(
            "MATIA BOT",
            random.choice(questions),
            "quiz"
        )

        broadcast_message(msg)

        return {"ok": True, "message": msg}

    # ---------------------------------------------
    # ONLINE
    # ---------------------------------------------

    if cmd in ("/online", "/users"):
        online = [
            u for u, info in USERS.items()
            if info.get("online")
        ]

        text = (
            "🟢 ONLINE USERS\n\n" +
            ("\n".join(f"• {u}" for u in online)
             if online else "Nobody online.")
        )

        msg = add_message(
            "MATIA BOT",
            text,
            "system"
        )

        broadcast_message(msg)

        return {"ok": True, "message": msg}

    # ---------------------------------------------
    # RULES
    # ---------------------------------------------

    if cmd == "/rules":
        text = (
            "📜 MATIA CHAT RULES\n\n"
            "1. Be respectful 🤝\n"
            "2. No spam 🚫\n"
            "3. No harassment ❌\n"
            "4. Have fun 🎉\n"
            "5. Don't share passwords or private information 🔐"
        )

        msg = add_message(
            "MATIA BOT",
            text,
            "help"
        )

        broadcast_message(msg)

        return {"ok": True, "message": msg}

    # ---------------------------------------------
    # TIME
    # ---------------------------------------------

    if cmd == "/time":
        msg = add_message(
            "MATIA BOT",
            f"🕐 Server time: {datetime.now().strftime('%H:%M:%S')}",
            "bot"
        )

        broadcast_message(msg)

        return {"ok": True, "message": msg}

    # ---------------------------------------------
    # VISUAL EFFECTS
    # ---------------------------------------------

    visual_commands = {
        "/rainbow": "rainbow",
        "/matrix": "matrix",
        "/party": "party",
        "/neon": "neon",
        "/fire": "fire",
        "/fireworks": "fireworks",
        "/confetti": "confetti",
        "/disco": "disco"
    }

    if cmd in visual_commands:
        effect = visual_commands[cmd]

        socketio.emit("visual_effect", {
            "effect": effect,
            "by": username
        })

        msg = add_message(
            "MATIA BOT",
            f"✨ {username} activated {effect.upper()} MODE!",
            "effect"
        )

        broadcast_message(msg)

        return {
            "ok": True,
            "message": msg,
            "effect": effect
        }

    # =====================================================
    # STAFF
    # =====================================================

    if cmd == "/announce":
        if not is_staff(username):
            return {
                "ok": False,
                "error": "Staff only."
            }

        text = " ".join(args).strip()

        if not text:
            return {
                "ok": False,
                "error": "Usage: /announce message"
            }

        socketio.emit("announcement", {
            "text": text,
            "by": username
        })

        msg = add_message(
            "MATIA BOT",
            f"📢 {text}",
            "announcement"
        )

        broadcast_message(msg)

        return {"ok": True, "message": msg}

    if cmd == "/lock":
        if not is_staff(username):
            return {"ok": False, "error": "Staff only."}

        GROUP["locked"] = True

        socketio.emit("group_update", GROUP)

        msg = system_message(
            f"🔒 {username} locked the chat."
        )

        return {"ok": True, "message": msg}

    if cmd == "/unlock":
        if not is_staff(username):
            return {"ok": False, "error": "Staff only."}

        GROUP["locked"] = False

        socketio.emit("group_update", GROUP)

        msg = system_message(
            f"🔓 {username} unlocked the chat."
        )

        return {"ok": True, "message": msg}

    if cmd == "/clear":
        if not is_staff(username):
            return {"ok": False, "error": "Staff only."}

        MESSAGES.clear()

        socketio.emit("clear_messages")

        return {
            "ok": True,
            "cleared": True
        }

    if cmd in ("/kick", "/ban", "/mute"):
        if not is_staff(username):
            return {"ok": False, "error": "Staff only."}

        target = clean_username(" ".join(args))

        if not target:
            return {
                "ok": False,
                "error": f"Usage: {cmd} username"
            }

        if target not in USERS:
            return {
                "ok": False,
                "error": "User not found."
            }

        if cmd == "/kick":
            USERS[target]["online"] = False

            msg = system_message(
                f"👢 {target} was kicked by {username}."
            )

        elif cmd == "/ban":
            BANNED.add(target)
            USERS[target]["online"] = False

            msg = system_message(
                f"🚫 {target} was banned by {username}."
            )

        else:
            MUTED.add(target)

            msg = system_message(
                f"🔇 {target} was muted by {username}."
            )

        send_users()

        return {"ok": True, "message": msg}

    if cmd in ("/unban", "/unmute"):
        if not is_staff(username):
            return {"ok": False, "error": "Staff only."}

        target = clean_username(" ".join(args))

        if not target:
            return {"ok": False, "error": "Username required."}

        if cmd == "/unban":
            BANNED.discard(target)
            text = f"✅ {target} was unbanned by {username}."
        else:
            MUTED.discard(target)
            text = f"🔊 {target} was unmuted by {username}."

        msg = system_message(text)
        send_users()

        return {"ok": True, "message": msg}

    if cmd == "/promote":
        if not is_owner(username):
            return {"ok": False, "error": "Owner only."}

        target = clean_username(" ".join(args))

        if target not in USERS:
            return {"ok": False, "error": "User not found."}

        USERS[target]["role"] = "admin"

        msg = system_message(
            f"👑 {target} was promoted to ADMIN."
        )

        send_users()

        return {"ok": True, "message": msg}

    if cmd == "/demote":
        if not is_owner(username):
            return {"ok": False, "error": "Owner only."}

        target = clean_username(" ".join(args))

        if target not in USERS:
            return {"ok": False, "error": "User not found."}

        USERS[target]["role"] = "member"

        msg = system_message(
            f"⬇️ {target} was demoted to MEMBER."
        )

        send_users()

        return {"ok": True, "message": msg}

    if cmd == "/rename":
        if not is_staff(username):
            return {"ok": False, "error": "Staff only."}

        new_name = " ".join(args).strip()

        if not new_name:
            return {"ok": False, "error": "New name required."}

        GROUP["name"] = new_name[:40]

        socketio.emit("group_update", GROUP)

        msg = system_message(
            f"✏️ Group renamed to {GROUP['name']}."
        )

        return {"ok": True, "message": msg}

    # ---------------------------------------------
    # UNKNOWN
    # ---------------------------------------------

    msg = add_message(
        "MATIA BOT",
        f"❓ Unknown command: {cmd}\nTry /help",
        "error"
    )

    broadcast_message(msg)

    return {
        "ok": False,
        "message": msg
    }


# =========================================================
# SOCKET.IO
# =========================================================

@socketio.on("connect")
def on_connect():
    emit("server_ready", {
        "ok": True
    })


@socketio.on("login")
def on_login(data):
    data = data or {}

    username = clean_username(
        data.get("username")
    )

    if not username:
        emit("login_error", {
            "error": "Invalid username"
        })
        return

    if username in BANNED:
        emit("login_error", {
            "error": "You are banned."
        })
        return

    if username not in USERS:
        USERS[username] = {
            "role": "owner" if len(USERS) == 0 else "member",
            "online": True
        }
    else:
        USERS[username]["online"] = True

    emit("login_success", {
        "username": username,
        "role": role(username),
        "messages": MESSAGES[-200:],
        "users": users_payload(),
        "group": GROUP
    })

    socketio.emit("group_update", GROUP)

    system_message(
        f"🟢 {username} joined MATIA CHAT."
    )

    send_users()


@socketio.on("send_message")
def on_send_message(data):
    data = data or {}

    username = clean_username(
        data.get("username")
    )

    text = clean_text(
        data.get("text")
    )

    if not username or not text:
        return

    if username in BANNED:
        return

    if username in MUTED:
        emit("action_error", {
            "error": "You are muted."
        })
        return

    if GROUP["locked"] and not is_staff(username):
        emit("action_error", {
            "error": "Chat is locked."
        })
        return

    if text.startswith("/"):
        execute_command(username, text)
        return

    msg = add_message(
        username,
        text
    )

    broadcast_message(msg)


@socketio.on("disconnect")
def on_disconnect():
    # Don't aggressively delete users because polling/browser
    # reconnects can happen.
    send_users()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    print("=" * 55)
    print("        MATIA CHAT")
    print("        SERVER ONLINE")
    print("=" * 55)
    print(f"PORT: {port}")

    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        allow_unsafe_werkzeug=True
    )
