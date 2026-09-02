import os
import random
from datetime import datetime

from flask import Flask, jsonify, request, send_file
from flask_socketio import SocketIO

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
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
CONNECTED = {}
MESSAGES = []

GROUP = {
    "name": "MATIA CHAT",
    "locked": False
}


# =========================================================
# HELPERS
# =========================================================

def now():
    return datetime.now().strftime("%H:%M")


def find_user(username):
    username = username.lower().strip()

    for name in USERS:
        if name.lower() == username:
            return name

    return None


def get_role(username):
    user = USERS.get(username)

    if not user:
        return "member"

    return user.get("role", "member")


def is_owner(username):
    return get_role(username) == "owner"


def is_staff(username):
    return get_role(username) in ("owner", "admin", "mod")


def add_message(
    username,
    text,
    message_type="message"
):
    message = {
        "username": username,
        "text": text,
        "time": now(),
        "type": message_type
    }

    MESSAGES.append(message)

    if len(MESSAGES) > 300:
        del MESSAGES[:-300]

    return message


def system_message(text):

    message = add_message(
        "MATIA",
        text,
        "system"
    )

    socketio.emit(
        "message",
        message
    )

    return message


def users_data():

    result = []

    for username, data in USERS.items():

        result.append({
            "username": username,
            "role": data.get(
                "role",
                "member"
            )
        })

    return result


def send_users():

    socketio.emit(
        "users_update",
        users_data()
    )


# =========================================================
# 1000 FUN COMMANDS
# =========================================================

FUN_COMMANDS = {}

fun_templates = [
    "🔥 {user} activated FUN MODE #{n}!",
    "😂 {user} just broke the fun meter #{n}!",
    "⚡ {user} launched FUN COMMAND #{n}!",
    "🚀 {user} reached chaos level #{n}!",
    "🎮 {user} unlocked secret mode #{n}!",
    "💀 {user} accidentally pressed #{n}!",
    "👑 {user} is now the king of FUN #{n}!",
    "🧠 {user} used 200% brain power #{n}!",
    "🌌 {user} opened a mysterious portal #{n}!",
    "🛸 {user} has been abducted by aliens #{n}!",
    "💎 {user} found a legendary item #{n}!",
    "⚔️ {user} entered battle mode #{n}!",
    "🏆 {user} earned +9999 cool points #{n}!",
    "🌪️ {user} created a mini tornado #{n}!",
    "🔮 {user} activated the forbidden spell #{n}!",
    "🎉 {user} started an invisible party #{n}!",
    "🤖 {user} became a robot for 3 seconds #{n}!",
    "🕶️ {user} activated hacker sunglasses #{n}!",
    "🌈 {user} unlocked rainbow mode #{n}!",
    "👻 {user} summoned a friendly ghost #{n}!"
]

for i in range(1, 1001):

    template = random.choice(fun_templates)

    FUN_COMMANDS[f"/fun{i}"] = (
        lambda user, n=i, t=template:
        t.format(
            user=user,
            n=n
        )
    )


# =========================================================
# INDEX
# =========================================================

@app.route("/")
def home():

    return send_file(
        os.path.join(
            BASE_DIR,
            "index.html"
        )
    )


@app.route("/health")
def health():

    return jsonify({
        "status": "online",
        "service": "MATIA CHAT",
        "users": len(USERS),
        "messages": len(MESSAGES)
    })


# =========================================================
# HTTP LOGIN FALLBACK
# =========================================================

@app.route(
    "/api/login",
    methods=["POST"]
)
def http_login():

    data = request.get_json(
        silent=True
    ) or {}

    username = str(
        data.get("username", "")
    ).strip()

    if not username:

        return jsonify({
            "ok": False,
            "error": "Enter a username."
        }), 400

    if len(username) < 2:

        return jsonify({
            "ok": False,
            "error": "Username must contain at least 2 characters."
        }), 400

    if len(username) > 20:

        return jsonify({
            "ok": False,
            "error": "Username is too long."
        }), 400

    existing = find_user(username)

    if existing:

        username = existing

    else:

        role = (
            "owner"
            if len(USERS) == 0
            else "member"
        )

        USERS[username] = {
            "role": role
        }

    return jsonify({
        "ok": True,
        "username": username,
        "role": get_role(username),
        "group": GROUP["name"],
        "messages": MESSAGES,
        "users": users_data()
    })


# =========================================================
# HTTP MESSAGES FALLBACK
# =========================================================

@app.route(
    "/api/messages",
    methods=["GET"]
)
def http_messages():

    return jsonify({
        "ok": True,
        "group": GROUP,
        "messages": MESSAGES,
        "users": users_data()
    })


# =========================================================
# SOCKET CONNECT
# =========================================================

@socketio.on("connect")
def socket_connect():

    print(
        "[SOCKET] Connected:",
        request.sid
    )


# =========================================================
# SOCKET LOGIN
# =========================================================

@socketio.on("login")
def socket_login(data):

    data = data or {}

    username = str(
        data.get("username", "")
    ).strip()

    if not username:

        socketio.emit(
            "login_error",
            {
                "error":
                "Enter a username."
            },
            to=request.sid
        )

        return

    if len(username) < 2:

        socketio.emit(
            "login_error",
            {
                "error":
                "Username must contain at least 2 characters."
            },
            to=request.sid
        )

        return

    if len(username) > 20:

        socketio.emit(
            "login_error",
            {
                "error":
                "Username is too long."
            },
            to=request.sid
        )

        return

    existing = find_user(username)

    if existing:
        username = existing

    else:

        role = (
            "owner"
            if len(USERS) == 0
            else "member"
        )

        USERS[username] = {
            "role": role
        }

    CONNECTED[request.sid] = username

    print(
        f"[LOGIN] {username} "
        f"({get_role(username)})"
    )

    socketio.emit(
        "login_success",
        {
            "username": username,
            "role": get_role(username),
            "group": GROUP["name"],
            "messages": MESSAGES
        },
        to=request.sid
    )

    socketio.emit(
        "group_update",
        {
            "name": GROUP["name"],
            "locked": GROUP["locked"]
        },
        to=request.sid
    )

    system_message(
        f"🟢 {username} joined MATIA CHAT"
    )

    send_users()


# =========================================================
# DISCONNECT
# =========================================================

@socketio.on("disconnect")
def socket_disconnect():

    username = CONNECTED.pop(
        request.sid,
        None
    )

    if username:

        print(
            f"[DISCONNECT] {username}"
        )

        system_message(
            f"🔴 {username} left MATIA CHAT"
        )

        send_users()


# =========================================================
# SEND MESSAGE
# =========================================================

@socketio.on("send_message")
def socket_send_message(data):

    username = CONNECTED.get(
        request.sid
    )

    if not username:
        return

    data = data or {}

    text = str(
        data.get("text", "")
    ).strip()

    if not text:
        return

    if len(text) > 5000:

        socketio.emit(
            "command_result",
            {
                "text":
                "❌ Message is too long."
            },
            to=request.sid
        )

        return

    # COMMAND
    if text.startswith("/"):
        execute_command(
            username,
            text
        )
        return

    # GROUP LOCK
    if GROUP["locked"] and not is_staff(username):

        socketio.emit(
            "command_result",
            {
                "text":
                "🔒 Chat is currently locked."
            },
            to=request.sid
        )

        return

    message = add_message(
        username,
        text
    )

    socketio.emit(
        "message",
        message
    )


# =========================================================
# COMMAND ENGINE
# =========================================================

def execute_command(
    username,
    text
):

    parts = text.split()

    command = parts[0].lower()

    args = parts[1:]


    # -----------------------------------------------------
    # 1000 FUN COMMANDS
    # -----------------------------------------------------

    if command in FUN_COMMANDS:

        result = FUN_COMMANDS[
            command
        ](username)

        socketio.emit(
            "command_result",
            {
                "text": result
            },
            to=request.sid
        )

        return


    # -----------------------------------------------------
    # FUN
    # -----------------------------------------------------

    if command == "/fun":

        number = random.randint(
            1,
            1000
        )

        result = FUN_COMMANDS[
            f"/fun{number}"
        ](username)

        socketio.emit(
            "command_result",
            {
                "text": result
            },
            to=request.sid
        )

        return


    # -----------------------------------------------------
    # HELP
    # -----------------------------------------------------

    if command == "/help":

        socketio.emit(
            "command_result",
            {
                "text":
                "📚 Commands: /fun1-/fun1000 /coinflip /dice /8ball /joke /rate /ship /slap /hug /highfive /dance /spin /rps /trivia /quiz /online /users /whois /rules /time /rainbow /matrix /disco /party /neon /fire /fireworks /confetti"
            },
            to=request.sid
        )

        return


    # -----------------------------------------------------
    # COINFLIP
    # -----------------------------------------------------

    if command == "/coinflip":

        result = random.choice([
            "🪙 HEADS!",
            "🪙 TAILS!"
        ])

        socketio.emit(
            "command_result",
            {"text": result},
            to=request.sid
        )

        return


    # -----------------------------------------------------
    # DICE
    # -----------------------------------------------------

    if command in (
        "/dice",
        "/roll"
    ):

        result = random.randint(
            1,
            6
        )

        socketio.emit(
            "command_result",
            {
                "text":
                f"🎲 {username} rolled {result}/6"
            },
            to=request.sid
        )

        return


    # -----------------------------------------------------
    # 8 BALL
    # -----------------------------------------------------

    if command == "/8ball":

        answers = [
            "🎱 Absolutely!",
            "🎱 Definitely!",
            "🎱 Probably.",
            "🎱 Maybe...",
            "🎱 Ask again.",
            "🎱 Not today.",
            "🎱 No chance 😂",
            "🎱 The future is unclear."
        ]

        socketio.emit(
            "command_result",
            {
                "text":
                random.choice(answers)
            },
            to=request.sid
        )

        return


    # -----------------------------------------------------
    # JOKE
    # -----------------------------------------------------

    if command == "/joke":

        jokes = [
            "😂 Why did the computer go to the doctor? It had a virus.",
            "🤣 Why was the keyboard tired? It had too many shifts.",
            "💀 My PC told me it needed space... so I deleted Minecraft.",
            "😂 Programmer's favorite place? The cache."
        ]

        socketio.emit(
            "command_result",
            {
                "text":
                random.choice(jokes)
            },
            to=request.sid
        )

        return


    # -----------------------------------------------------
    # RATE
    # -----------------------------------------------------

    if command == "/rate":

        target = (
            " ".join(args)
            if args
            else username
        )

        score = random.randint(
            1,
            100
        )

        socketio.emit(
            "command_result",
            {
                "text":
                f"⭐ {target} is {score}/100!"
            },
            to=request.sid
        )

        return


    # -----------------------------------------------------
    # SHIP
    # -----------------------------------------------------

    if command == "/ship":

        target = (
            " ".join(args)
            if args
            else "someone"
        )

        score = random.randint(
            0,
            100
        )

        socketio.emit(
            "command_result",
            {
                "text":
                f"❤️ {username} + {target} = {score}% compatibility!"
            },
            to=request.sid
        )

        return


    # -----------------------------------------------------
    # ACTION COMMANDS
    # -----------------------------------------------------

    actions = {
        "/slap": "👋 slapped",
        "/hug": "🤗 hugged",
        "/highfive": "✋ high-fived",
        "/dance": "💃 started dancing",
        "/spin": "🌀 started spinning"
    }

    if command in actions:

        target = (
            " ".join(args)
            if args
            else "everyone"
        )

        socketio.emit(
            "command_result",
            {
                "text":
                f"{actions[command]} {target}!"
            },
            to=request.sid
        )

        return


    # -----------------------------------------------------
    # RPS
    # -----------------------------------------------------

    if command == "/rps":

        choices = [
            "rock",
            "paper",
            "scissors"
        ]

        computer = random.choice(
            choices
        )

        player = (
            args[0].lower()
            if args and
            args[0].lower() in choices
            else random.choice(choices)
        )

        if player == computer:

            result = "DRAW 🤝"

        elif (
            player == "rock"
            and computer == "scissors"
        ) or (
            player == "paper"
            and computer == "rock"
        ) or (
            player == "scissors"
            and computer == "paper"
        ):

            result = "YOU WIN 🏆"

        else:

            result = "BOT WINS 🤖"

        socketio.emit(
            "command_result",
            {
                "text":
                f"✊ You: {player} | Bot: {computer} → {result}"
            },
            to=request.sid
        )

        return


    # -----------------------------------------------------
    # TRIVIA
    # -----------------------------------------------------

    if command == "/trivia":

        trivia = [
            "🌍 What is the largest planet? Jupiter.",
            "⚽ Which country won the 2022 World Cup? Argentina.",
            "💻 What does CPU stand for? Central Processing Unit.",
            "🌙 What is Earth's natural satellite? The Moon.",
            "🧠 How many sides does a hexagon have? Six."
        ]

        socketio.emit(
            "command_result",
            {
                "text":
                random.choice(trivia)
            },
            to=request.sid
        )

        return


    # -----------------------------------------------------
    # QUIZ
    # -----------------------------------------------------

    if command == "/quiz":

        questions = [
            "🧠 QUIZ: What is 12 × 12? Answer: 144.",
            "🧠 QUIZ: How many continents are there? Answer: 7.",
            "🧠 QUIZ: What planet is known as the Red Planet? Mars.",
            "🧠 QUIZ: How many days are in a leap year? 366."
        ]

        socketio.emit(
            "command_result",
            {
                "text":
                random.choice(questions)
            },
            to=request.sid
        )

        return


    # -----------------------------------------------------
    # ONLINE
    # -----------------------------------------------------

    if command in (
        "/online",
        "/users"
    ):

        names = list(
            USERS.keys()
        )

        if names:

            result = (
                "🟢 Online: "
                + ", ".join(names)
            )

        else:

            result = "Nobody online."

        socketio.emit(
            "command_result",
            {
                "text": result
            },
            to=request.sid
        )

        return


    # -----------------------------------------------------
    # WHOIS
    # -----------------------------------------------------

    if command == "/whois":

        target = (
            " ".join(args)
            if args
            else username
        )

        found = find_user(
            target
        )

        if found:

            result = (
                f"👤 {found} — "
                f"{get_role(found)}"
            )

        else:

            result = (
                f"❓ {target} is not online."
            )

        socketio.emit(
            "command_result",
            {
                "text": result
            },
            to=request.sid
        )

        return


    # -----------------------------------------------------
    # RULES
    # -----------------------------------------------------

    if command == "/rules":

        result = (
            "📜 MATIA CHAT RULES\n"
            "1. Be respectful.\n"
            "2. No spam.\n"
            "3. Have fun.\n"
            "4. Follow the Owner/Admin commands."
        )

        socketio.emit(
            "command_result",
            {
                "text": result
            },
            to=request.sid
        )

        return


    # -----------------------------------------------------
    # TIME
    # -----------------------------------------------------

    if command == "/time":

        socketio.emit(
            "command_result",
            {
                "text":
                f"🕐 Server time: {now()}"
            },
            to=request.sid
        )

        return


    # =====================================================
    # VISUAL EVENTS
    # =====================================================

    effects = [
        "/rainbow",
        "/disco",
        "/matrix",
        "/party",
        "/neon",
        "/fire",
        "/fireworks",
        "/confetti"
    ]

    if command in effects:

        effect = command[1:]

        socketio.emit(
            "event_effect",
            {
                "effect": effect
            }
        )

        socketio.emit(
            "command_result",
            {
                "text":
                f"✨ {username} activated /{effect}!"
            },
            to=request.sid
        )

        return


    # =====================================================
    # /EVENT
    # =====================================================

    if command == "/event":

        effect = (
            args[0].lower()
            if args
            else "rainbow"
        )

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

            effect = "rainbow"

        if not is_staff(username):

            socketio.emit(
                "command_result",
                {
                    "text":
                    "❌ Staff only."
                },
                to=request.sid
            )

            return

        socketio.emit(
            "event_effect",
            {
                "effect": effect
            }
        )

        system_message(
            f"✨ {username} activated global {effect} event!"
        )

        return


    # =====================================================
    # STAFF
    # =====================================================

    if command == "/kick":

        if not is_staff(username):

            socketio.emit(
                "command_result",
                {
                    "text":
                    "❌ Staff only."
                },
                to=request.sid
            )

            return

        target = (
            " ".join(args)
            if args
            else ""
        )

        target = find_user(target)

        if not target:

            socketio.emit(
                "command_result",
                {
                    "text":
                    "❌ User not found."
                },
                to=request.sid
            )

            return

        target_sid = None

        for sid, name in CONNECTED.items():

            if name == target:

                target_sid = sid
                break

        if target_sid:

            socketio.emit(
                "command_result",
                {
                    "text":
                    "👢 You have been kicked."
                },
                to=target_sid
            )

            socketio.disconnect(
                target_sid
            )

            system_message(
                f"👢 {target} was kicked by {username}."
            )

        return


    # =====================================================
    # BAN
    # =====================================================

    if command == "/ban":

        if not is_staff(username):

            socketio.emit(
                "command_result",
                {
                    "text":
                    "❌ Staff only."
                },
                to=request.sid
            )

            return

        target = (
            " ".join(args)
            if args
            else ""
        )

        target = find_user(target)

        if not target:

            socketio.emit(
                "command_result",
                {
                    "text":
                    "❌ User not found."
                },
                to=request.sid
            )

            return

        USERS[target]["banned"] = True

        target_sid = None

        for sid, name in CONNECTED.items():

            if name == target:

                target_sid = sid
                break

        if target_sid:

            socketio.emit(
                "command_result",
                {
                    "text":
                    "🚫 You were banned."
                },
                to=target_sid
            )

            socketio.disconnect(
                target_sid
            )

        system_message(
            f"🚫 {target} was banned by {username}."
        )

        return


    # =====================================================
    # UNBAN
    # =====================================================

    if command == "/unban":

        if not is_staff(username):

            socketio.emit(
                "command_result",
                {
                    "text":
                    "❌ Staff only."
                },
                to=request.sid
            )

            return

        target = (
            " ".join(args)
            if args
            else ""
        )

        target = find_user(target)

        if target:

            USERS[target]["banned"] = False

            socketio.emit(
                "command_result",
                {
                    "text":
                    f"✅ {target} unbanned."
                },
                to=request.sid
            )

        return


    # =====================================================
    # MUTE
    # =====================================================

    if command == "/mute":

        if not is_staff(username):

            socketio.emit(
                "command_result",
                {
                    "text":
                    "❌ Staff only."
                },
                to=request.sid
            )

            return

        target = (
            " ".join(args)
            if args
            else ""
        )

        target = find_user(target)

        if target:

            USERS[target]["muted"] = True

            system_message(
                f"🔇 {target} was muted by {username}."
            )

        return


    # =====================================================
    # UNMUTE
    # =====================================================

    if command == "/unmute":

        if not is_staff(username):

            socketio.emit(
                "command_result",
                {
                    "text":
                    "❌ Staff only."
                },
                to=request.sid
            )

            return

        target = (
            " ".join(args)
            if args
            else ""
        )

        target = find_user(target)

        if target:

            USERS[target]["muted"] = False

            system_message(
                f"🔊 {target} was unmuted by {username}."
            )

        return


    # =====================================================
    # PROMOTE
    # =====================================================

    if command == "/promote":

        if not is_owner(username):

            socketio.emit(
                "command_result",
                {
                    "text":
                    "❌ Owner only."
                },
                to=request.sid
            )

            return

        target = (
            " ".join(args)
            if args
            else ""
        )

        target = find_user(target)

        if target:

            USERS[target]["role"] = "admin"

            system_message(
                f"👑 {target} is now Admin."
            )

            send_users()

        return


    # =====================================================
    # DEMOTE
    # =====================================================

    if command == "/demote":

        if not is_owner(username):

            socketio.emit(
                "command_result",
                {
                    "text":
                    "❌ Owner only."
                },
                to=request.sid
            )

            return

        target = (
            " ".join(args)
            if args
            else ""
        )

        target = find_user(target)

        if target:

            USERS[target]["role"] = "member"

            system_message(
                f"⬇️ {target} is now Member."
            )

            send_users()

        return


    # =====================================================
    # ANNOUNCE
    # =====================================================

    if command == "/announce":

        if not is_owner(username):

            socketio.emit(
                "command_result",
                {
                    "text":
                    "❌ Owner only."
                },
                to=request.sid
            )

            return

        text_to_send = (
            " ".join(args)
            if args
            else "MATIA CHAT ANNOUNCEMENT"
        )

        socketio.emit(
            "announcement",
            {
                "text":
                text_to_send
            }
        )

        return


    # =====================================================
    # CLEAR
    # =====================================================

    if command == "/clear":

        if not is_staff(username):

            socketio.emit(
                "command_result",
                {
                    "text":
                    "❌ Staff only."
                },
                to=request.sid
            )

            return

        MESSAGES.clear()

        socketio.emit(
            "clear_chat"
        )

        system_message(
            f"🧹 Chat cleared by {username}."
        )

        return


    # =====================================================
    # LOCK
    # =====================================================

    if command == "/lock":

        if not is_staff(username):

            socketio.emit(
                "command_result",
                {
                    "text":
                    "❌ Staff only."
                },
                to=request.sid
            )

            return

        GROUP["locked"] = True

        socketio.emit(
            "group_update",
            {
                "name": GROUP["name"],
                "locked": True
            }
        )

        system_message(
            f"🔒 Chat locked by {username}."
        )

        return


    # =====================================================
    # UNLOCK
    # =====================================================

    if command == "/unlock":

        if not is_staff(username):

            socketio.emit(
                "command_result",
                {
                    "text":
                    "❌ Staff only."
                },
                to=request.sid
            )

            return

        GROUP["locked"] = False

        socketio.emit(
            "group_update",
            {
                "name": GROUP["name"],
                "locked": False
            }
        )

        system_message(
            f"🔓 Chat unlocked by {username}."
        )

        return


    # =====================================================
    # RENAME
    # =====================================================

    if command == "/rename":

        if not is_owner(username):

            socketio.emit(
                "command_result",
                {
                    "text":
                    "❌ Owner only."
                },
                to=request.sid
            )

            return

        new_name = (
            " ".join(args)
            if args
            else ""
        ).strip()

        if not new_name:

            socketio.emit(
                "command_result",
                {
                    "text":
                    "Usage: /rename New Name"
                },
                to=request.sid
            )

            return

        GROUP["name"] = new_name[:40]

        socketio.emit(
            "group_update",
            {
                "name":
                GROUP["name"],
                "locked":
                GROUP["locked"]
            }
        )

        system_message(
            f"✏️ Group renamed to {GROUP['name']}."
        )

        return


    # =====================================================
    # UNKNOWN
    # =====================================================

    socketio.emit(
        "command_result",
        {
            "text":
            f"❓ Unknown command: {command}. Type /help."
        },
        to=request.sid
    )


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

    print()
    print("=" * 55)
    print("        MATIA CHAT")
    print("=" * 55)
    print(f"Server: http://127.0.0.1:{port}")
    print("1000 FUN COMMANDS: READY")
    print("Socket.IO: READY")
    print("=" * 55)
    print()

    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        allow_unsafe_werkzeug=True
    )
