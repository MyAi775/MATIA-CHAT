from flask import Flask, render_template, request
from flask_socketio import SocketIO
import uuid
import time
import random

# =========================================================
# MATIA CHAT
# =========================================================

app = Flask(__name__)
app.config["SECRET_KEY"] = "matia-chat-secret"

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="eventlet"
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
# COMMANDS
# =========================================================

OWNER_COMMANDS = {
    "ban", "unban", "kick", "mute", "unmute",
    "promote", "demote", "announce", "event",
    "clear", "lock", "unlock", "rename", "help",

    "fun", "coinflip", "dice", "roll", "8ball",
    "joke", "rate", "ship", "slap", "hug",
    "highfive", "dance", "spin", "rps",
    "trivia", "quiz", "online", "users",
    "whois", "rules", "time", "party",
    "fireworks", "confetti", "rainbow",
    "disco", "matrix", "neon", "fire"
}

MOD_COMMANDS = {
    "ban", "unban", "kick", "mute", "unmute",
    "help",

    "fun", "coinflip", "dice", "roll", "8ball",
    "joke", "rate", "ship", "slap", "hug",
    "highfive", "dance", "spin", "rps",
    "trivia", "quiz", "online", "users",
    "whois", "rules", "time", "party",
    "fireworks", "confetti", "rainbow",
    "disco", "matrix", "neon", "fire"
}

# =========================================================
# HELPERS
# =========================================================

def can_use(username, command):

    if username not in USERS:
        return False

    role = USERS[username]["role"]

    if role == "owner":
        return command in OWNER_COMMANDS

    if role == "mod":
        return command in MOD_COMMANDS

    return False


def system_message(text):

    socketio.emit(
        "system",
        {
            "text": text
        }
    )


def command_result(sid, text):

    socketio.emit(
        "command_result",
        {
            "text": text
        },
        to=sid
    )


def add_message(username, text):

    message = {
        "id": str(uuid.uuid4()),
        "user": username,
        "text": text,
        "time": time.strftime("%H:%M"),
        "system": False
    }

    MESSAGES.append(message)

    if len(MESSAGES) > 200:
        MESSAGES.pop(0)

    return message


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():
    return render_template("index.html")


# =========================================================
# LOGIN
# =========================================================

@socketio.on("login")
def login(data):

    username = str(
        data.get("username", "")
    ).strip()

    if not username:

        socketio.emit(
            "login_result",
            {
                "ok": False,
                "error": "Please enter a username."
            },
            to=request.sid
        )

        return

    if len(username) > 20:

        socketio.emit(
            "login_result",
            {
                "ok": False,
                "error": "Username must be 20 characters or less."
            },
            to=request.sid
        )

        return

    if username in CONNECTED.values():

        socketio.emit(
            "login_result",
            {
                "ok": False,
                "error": "That username is already online."
            },
            to=request.sid
        )

        return

    # =====================================================
    # CREATE USER
    # =====================================================

    if username not in USERS:

        # First user becomes Owner
        role = "owner" if len(USERS) == 0 else "member"

        USERS[username] = {
            "role": role,
            "banned": False,
            "muted": False
        }

    user = USERS[username]

    # =====================================================
    # BAN CHECK
    # =====================================================

    if user["banned"]:

        socketio.emit(
            "login_result",
            {
                "ok": False,
                "error": "You are banned."
            },
            to=request.sid
        )

        return

    # =====================================================
    # CONNECT
    # =====================================================

    CONNECTED[request.sid] = username

    socketio.emit(
        "login_result",
        {
            "ok": True,
            "username": username,
            "role": user["role"],
            "group": GROUP,
            "messages": MESSAGES
        },
        to=request.sid
    )

    system_message(
        f"🟢 {username} joined {GROUP['name']}."
    )


# =========================================================
# MESSAGE
# =========================================================

@socketio.on("message")
def message(data):

    sid = request.sid

    if sid not in CONNECTED:
        return

    username = CONNECTED[sid]

    text = str(
        data.get("text", "")
    ).strip()

    if not text:
        return

    user = USERS.get(username)

    if not user:
        return

    # BANNED
    if user["banned"]:
        return

    # MUTED
    if user["muted"]:

        socketio.emit(
            "system",
            {
                "text": "🔇 You are muted."
            },
            to=sid
        )

        return

    # LOCKED
    if GROUP["locked"]:

        if user["role"] != "owner":

            socketio.emit(
                "system",
                {
                    "text": "🔒 Chat is locked by the Owner."
                },
                to=sid
            )

            return

    # COMMAND
    if text.startswith("/"):

        execute_command(
            username,
            sid,
            text
        )

        return

    # NORMAL MESSAGE
    msg = add_message(
        username,
        text
    )

    socketio.emit(
        "new_message",
        msg
    )


# =========================================================
# COMMAND ENGINE
# =========================================================

def execute_command(username, sid, text):

    parts = text.split()

    if not parts:
        return

    command = parts[0][1:].lower()
    args = parts[1:]

    # =====================================================
    # PERMISSION
    # =====================================================

    if not can_use(username, command):

        command_result(
            sid,
            f"🚫 Permission denied: /{command}"
        )

        return

    # =====================================================
    # HELP
    # =====================================================

    if command == "help":

        role = USERS[username]["role"]

        commands = (
            OWNER_COMMANDS
            if role == "owner"
            else MOD_COMMANDS
        )

        command_result(
            sid,
            "📚 AVAILABLE COMMANDS:\n\n" +
            " ".join(
                "/" + x
                for x in sorted(commands)
            )
        )

        return

    # =====================================================
    # BAN
    # =====================================================

    if command == "ban":

        if not args:

            command_result(
                sid,
                "Usage: /ban username"
            )

            return

        target = args[0]

        if target not in USERS:

            command_result(
                sid,
                "❌ User not found."
            )

            return

        if USERS[target]["role"] == "owner":

            command_result(
                sid,
                "👑 You cannot ban the Owner."
            )

            return

        USERS[target]["banned"] = True

        for target_sid, name in list(
            CONNECTED.items()
        ):

            if name == target:

                socketio.emit(
                    "force_disconnect",
                    {
                        "reason":
                        f"🚫 You were banned by {username}."
                    },
                    to=target_sid
                )

                del CONNECTED[target_sid]

        system_message(
            f"🚫 {target} was banned by {username}."
        )

        return

    # =====================================================
    # UNBAN
    # =====================================================

    if command == "unban":

        if not args:

            command_result(
                sid,
                "Usage: /unban username"
            )

            return

        target = args[0]

        if target not in USERS:

            command_result(
                sid,
                "❌ User not found."
            )

            return

        USERS[target]["banned"] = False

        system_message(
            f"✅ {target} was unbanned by {username}."
        )

        return

    # =====================================================
    # KICK
    # =====================================================

    if command == "kick":

        if not args:

            command_result(
                sid,
                "Usage: /kick username"
            )

            return

        target = args[0]

        if target not in USERS:

            command_result(
                sid,
                "❌ User not found."
            )

            return

        if USERS[target]["role"] == "owner":

            command_result(
                sid,
                "👑 You cannot kick the Owner."
            )

            return

        for target_sid, name in list(
            CONNECTED.items()
        ):

            if name == target:

                socketio.emit(
                    "force_disconnect",
                    {
                        "reason":
                        f"👢 You were kicked by {username}."
                    },
                    to=target_sid
                )

                del CONNECTED[target_sid]

        system_message(
            f"👢 {target} was kicked by {username}."
        )

        return

    # =====================================================
    # MUTE
    # =====================================================

    if command == "mute":

        if not args:

            command_result(
                sid,
                "Usage: /mute username"
            )

            return

        target = args[0]

        if target not in USERS:

            command_result(
                sid,
                "❌ User not found."
            )

            return

        if USERS[target]["role"] == "owner":

            command_result(
                sid,
                "👑 You cannot mute the Owner."
            )

            return

        USERS[target]["muted"] = True

        system_message(
            f"🔇 {target} was muted by {username}."
        )

        return

    # =====================================================
    # UNMUTE
    # =====================================================

    if command == "unmute":

        if not args:

            command_result(
                sid,
                "Usage: /unmute username"
            )

            return

        target = args[0]

        if target not in USERS:

            command_result(
                sid,
                "❌ User not found."
            )

            return

        USERS[target]["muted"] = False

        system_message(
            f"🔊 {target} was unmuted by {username}."
        )

        return

    # =====================================================
    # PROMOTE
    # =====================================================

    if command == "promote":

        if not args:

            command_result(
                sid,
                "Usage: /promote username"
            )

            return

        target = args[0]

        if target not in USERS:

            command_result(
                sid,
                "❌ User not found."
            )

            return

        if USERS[target]["role"] == "owner":

            command_result(
                sid,
                "👑 User is already Owner."
            )

            return

        USERS[target]["role"] = "mod"

        system_message(
            f"🛡️ {target} is now Moderator."
        )

        return

    # =====================================================
    # DEMOTE
    # =====================================================

    if command == "demote":

        if not args:

            command_result(
                sid,
                "Usage: /demote username"
            )

            return

        target = args[0]

        if target not in USERS:

            command_result(
                sid,
                "❌ User not found."
            )

            return

        if USERS[target]["role"] == "owner":

            command_result(
                sid,
                "👑 You cannot demote the Owner."
            )

            return

        USERS[target]["role"] = "member"

        system_message(
            f"👤 {target} is now Member."
        )

        return

    # =====================================================
    # ANNOUNCE
    # =====================================================

    if command == "announce":

        announcement = " ".join(args)

        if not announcement:

            command_result(
                sid,
                "Usage: /announce message"
            )

            return

        socketio.emit(
            "announcement",
            {
                "text": announcement,
                "by": username
            }
        )

        return

    # =====================================================
    # EVENT
    # =====================================================

    if command == "event":

        if not args:

            command_result(
                sid,
                "Usage: /event rainbow"
            )

            return

        event = args[0].lower()

        allowed = {
            "rainbow",
            "disco",
            "matrix",
            "party",
            "neon",
            "fire"
        }

        if event not in allowed:

            command_result(
                sid,
                "❌ Unknown event."
            )

            return

        # GLOBAL EVENT
        socketio.emit(
            "event",
            {
                "name": event,
                "by": username
            }
        )

        system_message(
            f"🎉 {username} started {event.upper()}!"
        )

        return

    # =====================================================
    # CLEAR
    # =====================================================

    if command == "clear":

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

    if command == "lock":

        GROUP["locked"] = True

        socketio.emit(
            "group_update",
            GROUP
        )

        system_message(
            "🔒 Chat locked by Owner."
        )

        return

    # =====================================================
    # UNLOCK
    # =====================================================

    if command == "unlock":

        GROUP["locked"] = False

        socketio.emit(
            "group_update",
            GROUP
        )

        system_message(
            "🔓 Chat unlocked by Owner."
        )

        return

    # =====================================================
    # RENAME
    # =====================================================

    if command == "rename":

        if not args:

            command_result(
                sid,
                "Usage: /rename new name"
            )

            return

        GROUP["name"] = " ".join(args)

        socketio.emit(
            "group_update",
            GROUP
        )

        system_message(
            f"✏️ Group renamed to {GROUP['name']}."
        )

        return

    # =====================================================
    # FUN
    # =====================================================

    if command == "fun":

        command_result(
            sid,
            """
🎮 FUN COMMANDS

/coinflip
/dice
/roll
/8ball question
/joke
/rate username
/ship user1 user2
/slap username
/hug username
/highfive username
/dance
/spin
/rps rock
/rps paper
/rps scissors
/trivia
/quiz
/online
/users
/whois username
/rules
/time

🌈 EVENTS

/party
/fireworks
/confetti
/rainbow
/disco
/matrix
/neon
/fire
"""
        )

        return

    # =====================================================
    # COINFLIP
    # =====================================================

    if command == "coinflip":

        result = random.choice(
            [
                "HEADS",
                "TAILS"
            ]
        )

        system_message(
            f"🪙 {username} flipped → {result}!"
        )

        return

    # =====================================================
    # DICE
    # =====================================================

    if command in {"dice", "roll"}:

        number = random.randint(
            1,
            6
        )

        system_message(
            f"🎲 {username} rolled a {number}!"
        )

        return

    # =====================================================
    # 8 BALL
    # =====================================================

    if command == "8ball":

        if not args:

            command_result(
                sid,
                "Usage: /8ball your question"
            )

            return

        answers = [
            "🎱 Absolutely!",
            "🎱 Definitely!",
            "🎱 Nope.",
            "🎱 Maybe...",
            "🎱 Ask again later.",
            "🎱 100% YES!",
            "🎱 I don't think so.",
            "🎱 The future says YES!"
        ]

        system_message(
            f"🎱 {username}: {random.choice(answers)}"
        )

        return

    # =====================================================
    # JOKE
    # =====================================================

    if command == "joke":

        jokes = [
            "😂 Why did the computer go to the doctor? It had a virus!",
            "🤣 Why was the keyboard cold? It left its Windows open!",
            "💀 I told my PC I needed space... now it deleted my files.",
            "😂 My computer told me it needed a byte."
        ]

        system_message(
            random.choice(jokes)
        )

        return

    # =====================================================
    # RATE
    # =====================================================

    if command == "rate":

        if not args:

            command_result(
                sid,
                "Usage: /rate username"
            )

            return

        score = random.randint(
            1,
            10
        )

        system_message(
            f"⭐ {username} rated {args[0]} "
            f"{score}/10!"
        )

        return

    # =====================================================
    # SHIP
    # =====================================================

    if command == "ship":

        if len(args) < 2:

            command_result(
                sid,
                "Usage: /ship user1 user2"
            )

            return

        score = random.randint(
            0,
            100
        )

        system_message(
            f"💘 {args[0]} + {args[1]} "
            f"= {score}% ❤️"
        )

        return

    # =====================================================
    # SLAP
    # =====================================================

    if command == "slap":

        target = (
            args[0]
            if args
            else "everyone"
        )

        system_message(
            f"👋 {username} slapped {target}!"
        )

        return

    # =====================================================
    # HUG
    # =====================================================

    if command == "hug":

        target = (
            args[0]
            if args
            else "everyone"
        )

        system_message(
            f"🫂 {username} hugged {target}!"
        )

        return

    # =====================================================
    # HIGH FIVE
    # =====================================================

    if command == "highfive":

        target = (
            args[0]
            if args
            else "everyone"
        )

        system_message(
            f"✋ {username} high-fived {target}!"
        )

        return

    # =====================================================
    # DANCE
    # =====================================================

    if command == "dance":

        system_message(
            f"🕺 {username} started dancing! 💃"
        )

        socketio.emit(
            "event",
            {
                "name": "disco",
                "by": username
            }
        )

        return

    # =====================================================
    # SPIN
    # =====================================================

    if command == "spin":

        degrees = random.randint(
            1,
            360
        )

        system_message(
            f"🌀 {username} spun {degrees}°!"
        )

        return

    # =====================================================
    # RPS
    # =====================================================

    if command == "rps":

        if not args:

            command_result(
                sid,
                "Usage: /rps rock"
            )

            return

        player = args[0].lower()

        choices = [
            "rock",
            "paper",
            "scissors"
        ]

        if player not in choices:

            command_result(
                sid,
                "Choose rock, paper or scissors."
            )

            return

        bot = random.choice(
            choices
        )

        if player == bot:

            result = "DRAW 🤝"

        elif (
            (player == "rock" and bot == "scissors")
            or
            (player == "paper" and bot == "rock")
            or
            (player == "scissors" and bot == "paper")
        ):

            result = "YOU WIN 🏆"

        else:

            result = "BOT WINS 🤖"

        system_message(
            f"🎮 {username}: "
            f"{player} vs {bot} → {result}"
        )

        return

    # =====================================================
    # TRIVIA / QUIZ
    # =====================================================

    if command in {"trivia", "quiz"}:

        questions = [
            "🌍 Capital of France? → Paris 🇫🇷",
            "🪐 Red Planet? → Mars",
            "⚽ Sport with a goalkeeper? → Football",
            "💻 CPU stands for? → Central Processing Unit",
            "🌊 Largest ocean? → Pacific Ocean"
        ]

        system_message(
            random.choice(questions)
        )

        return

    # =====================================================
    # ONLINE
    # =====================================================

    if command in {"online", "users"}:

        online = list(
            CONNECTED.values()
        )

        if not online:

            command_result(
                sid,
                "Nobody is online."
            )

            return

        command_result(
            sid,
            "🟢 ONLINE USERS:\n" +
            "\n".join(
                "• " + name
                for name in online
            )
        )

        return

    # =====================================================
    # WHOIS
    # =====================================================

    if command == "whois":

        if not args:

            command_result(
                sid,
                "Usage: /whois username"
            )

            return

        target = args[0]

        if target not in USERS:

            command_result(
                sid,
                "❌ User not found."
            )

            return

        online = (
            target in CONNECTED.values()
        )

        command_result(
            sid,
            f"""
👤 USER INFO

Username: {target}
Role: {USERS[target]["role"].upper()}
Online: {"YES 🟢" if online else "NO 🔴"}
Muted: {"YES 🔇" if USERS[target]["muted"] else "NO"}
Banned: {"YES 🚫" if USERS[target]["banned"] else "NO"}
"""
        )

        return

    # =====================================================
    # RULES
    # =====================================================

    if command == "rules":

        command_result(
            sid,
            """
📜 MATIA CHAT RULES

1. Be respectful.
2. No spam.
3. No abuse.
4. Follow Owner/Mods.
5. Have fun! 😎
"""
        )

        return

    # =====================================================
    # TIME
    # =====================================================

    if command == "time":

        command_result(
            sid,
            "🕐 Server time: " +
            time.strftime("%H:%M:%S")
        )

        return

    # =====================================================
    # VISUAL EVENTS
    # =====================================================

    if command in {
        "party",
        "fireworks",
        "confetti",
        "rainbow",
        "disco",
        "matrix",
        "neon",
        "fire"
    }:

        event_map = {

            "party": "party",

            "fireworks": "party",

            "confetti": "party",

            "rainbow": "rainbow",

            "disco": "disco",

            "matrix": "matrix",

            "neon": "neon",

            "fire": "fire"
        }

        socketio.emit(
            "event",
            {
                "name": event_map[command],
                "by": username
            }
        )

        return

    # =====================================================
    # UNKNOWN
    # =====================================================

    command_result(
        sid,
        f"❓ Unknown command: /{command}"
    )


# =========================================================
# DISCONNECT
# =========================================================

@socketio.on("disconnect")
def disconnect():

    username = CONNECTED.pop(
        request.sid,
        None
    )

    if username:

        system_message(
            f"🔴 {username} left {GROUP['name']}."
        )


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    print()
    print("========================================")
    print("          MATIA CHAT SERVER")
    print("========================================")
    print()
    print(" Login: USERNAME ONLY")
    print(" First user: OWNER 👑")
    print(" Other users: MEMBER")
    print()
    print(" Local:")
    print(" http://127.0.0.1:5000")
    print()
    print(" Render:")
    print(" Use gunicorn + eventlet")
    print()
    print("========================================")

    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=False
    )
