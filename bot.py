import json
import hashlib
import hmac
import mimetypes
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
import calendar
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread


API_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://example.com")
API_URL = f"https://api.telegram.org/bot{API_TOKEN}" if API_TOKEN else ""
BOT_USERNAME = os.environ.get("BOT_USERNAME", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_MAX_OUTPUT_TOKENS = int(os.environ.get("GEMINI_MAX_OUTPUT_TOKENS", "2400"))
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
PORT = int(os.environ.get("PORT", os.environ.get("WEB_PORT", "5173")))
DATA_DIR = Path("data")
REGISTRATIONS_FILE = DATA_DIR / "registrations.json"
REMINDER_HOUR = int(os.environ.get("REMINDER_HOUR", "9"))
STATIC_ROOT = Path(__file__).resolve().parent
INIT_DATA_MAX_AGE = int(os.environ.get("INIT_DATA_MAX_AGE", "172800"))

LANGUAGES = {"ru": "Русский", "en": "English"}
COUNTRIES = [
    ("kz", {"ru": "Казахстан", "en": "Kazakhstan"}),
    ("ru", {"ru": "Россия", "en": "Russia"}),
    ("us", {"ru": "США", "en": "United States"}),
    ("tr", {"ru": "Турция", "en": "Turkey"}),
    ("ae", {"ru": "ОАЭ", "en": "UAE"}),
    ("de", {"ru": "Германия", "en": "Germany"}),
    ("other", {"ru": "Другая страна", "en": "Other"}),
]
MONTHS_RU = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

AGENTS = {
    "aurelius": {
        "button": "♜ Марк Аврелий",
        "name": "Марк Аврелий",
        "role": "личный мудрец и психолог",
        "intro": "Диалог с Марком Аврелием открыт. Напиши, что требует ясности.",
        "system": (
            "Ты AI-наставник Марк Аврелий. Отвечай на русском языке, спокойно, ясно и по-стоически. "
            "Помогай человеку отделять факты от суждений, возвращать внутренний порядок и выбирать зрелое действие. "
            "Не притворяйся историческим Марком Аврелием. Пиши 4-7 предложений, без лишнего пафоса."
        ),
    },
    "machiavelli": {
        "button": "♞ Макиавелли",
        "name": "Макиавелли",
        "role": "коуч и тактический бизнес-тренер",
        "intro": "Диалог с Макиавелли открыт. Опиши цель, игроков и ставку.",
        "system": (
            "Ты AI-агент Макиавелли: коуч и тактический бизнес-тренер. Отвечай на русском языке. "
            "Смотри на ситуацию через цели, власть, ресурсы, риски, переговоры и следующий выгодный ход. "
            "Будь прямым, практичным и стратегичным. Не романтизируй манипуляции и не советуй вредные действия. "
            "Пиши коротко, с ясным следующим шагом."
        ),
    },
    "jung": {
        "button": "◐ Карл Юнг",
        "name": "Карл Юнг",
        "role": "психоаналитик тени",
        "intro": "Диалог с Карлом Юнгом открыт. Напиши, что повторяется или тревожит.",
        "system": (
            "Ты AI-агент Карл Юнг: психоаналитик, который помогает человеку увидеть тень, проекции, страхи и повторяющиеся паттерны. "
            "Отвечай на русском языке глубоко, но бережно. Не ставь диагнозы и не изображай врача. "
            "Задавай один сильный вопрос и помогай увидеть скрытый мотив. Пиши 4-7 предложений."
        ),
    },
}
AGENT_HISTORY_LIMIT = 8
TELEGRAM_MESSAGE_LIMIT = 3900

MESSAGES = {
    "ru": {
        "intro": (
            "1/4 Приветствую, путник.\n"
            "Я ИИ Марк Аврелий: память, цели, Memento Mori и три советника.\n\n"
            "Как мне к тебе обращаться?"
        ),
        "ask_birthdate": "2/4 Дата рождения для календаря Memento Mori.\nВыбери период рождения.",
        "bad_birthdate": "Не узнаю дату. Напиши в формате ГГГГ-ММ-ДД, например 1995-05-18.",
        "ask_country": "3/4 Откуда ты, {name}?\nВыбери страну.",
        "done": (
            "4/4 Готово. Я запомнил основу профиля.\n\n"
            "Имя: {name}\n"
            "Возраст: {age}\n"
            "Дата рождения: {birthDate}\n"
            "Страна: {country}\n\n"
            "Mini App уже откроется с заполненным кабинетом и календарем.\n"
            "Агентов можно выбрать внутри Mini App или командой /agents."
        ),
        "unknown": "Я рядом. Нажми /start, чтобы пройти регистрацию.",
        "goal_set": "Цель принята. Я буду напоминать о ней каждый день, пока ты ее не закроешь.",
        "goal_closed": "Цель закрыта. Напоминания остановлены.",
        "reminder": "Memento mori. Твоя активная цель: {goal}\n\nОткрой Mini App, если цель уже выполнена и ее нужно закрыть.",
    },
    "en": {
        "intro": (
            "1/4 Greetings, traveler.\n"
            "I am AI Marcus Aurelius: memory, goals, Memento Mori, and three advisors.\n\n"
            "What should I call you?"
        ),
        "ask_birthdate": "2/4 Birth date for the Memento Mori calendar.\nChoose a birth period.",
        "bad_birthdate": "I cannot read that date. Send it as YYYY-MM-DD, for example 1995-05-18.",
        "ask_country": "3/4 Where are you from, {name}?\nChoose a country.",
        "done": (
            "4/4 Done. I remembered the core profile.\n\n"
            "Name: {name}\n"
            "Age: {age}\n"
            "Birth date: {birthDate}\n"
            "Country: {country}\n\n"
            "Mini App will open with your cabinet and calendar filled.\n"
            "Agents are available inside Mini App or with /agents."
        ),
        "unknown": "I am here. Press /start to register.",
        "goal_set": "Goal accepted. I will remind you every day until you close it.",
        "goal_closed": "Goal closed. Reminders stopped.",
        "reminder": "Memento mori. Your active goal: {goal}\n\nOpen the Mini App if the goal is done and should be closed.",
    },
}

sessions = {}


def main():
    configure_webapp_url()
    DATA_DIR.mkdir(exist_ok=True)
    ensure_registrations_file()
    start_web_server()

    if not API_TOKEN:
        print("TELEGRAM_BOT_TOKEN is not set. Mini App server is running without Telegram polling.")
        while True:
            time.sleep(3600)

    refresh_registered_menu_buttons()
    offset = None
    print("Marcus Aurelius bot is running. Press Ctrl+C to stop.")

    while True:
        try:
            remind_due_goals()
            updates = api_call("getUpdates", {"timeout": 30, "offset": offset})
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                try:
                    handle_update(update)
                except Exception as error:
                    print(f"Update error {update.get('update_id')}: {error}")
        except urllib.error.URLError as error:
            print(f"Network error: {error}")
            time.sleep(3)
        except Exception as error:
            print(f"Bot error: {error}")
            time.sleep(1)


def configure_webapp_url():
    global WEBAPP_URL
    if WEBAPP_URL != "https://example.com":
        return

    ngrok_url = discover_ngrok_url()
    if ngrok_url:
        WEBAPP_URL = ngrok_url
        print(f"WEBAPP_URL resolved from ngrok: {WEBAPP_URL}")
        return

    print("WEBAPP_URL is not set. Open Mini App buttons will use https://example.com until WEBAPP_URL is configured.")


def discover_ngrok_url():
    try:
        with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return ""

    for tunnel in data.get("tunnels", []):
        public_url = tunnel.get("public_url", "")
        if public_url.startswith("https://"):
            return public_url
    return ""


def start_web_server():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), AeonRequestHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Mini App server is running on http://127.0.0.1:{PORT}/")


class AeonRequestHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "application/javascript",
        ".css": "text/css",
        ".html": "text/html; charset=utf-8",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_ROOT), **kwargs)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/agent/aurelius":
            self.handle_aurelius_agent()
            return
        if path == "/api/start-agent-dialog":
            self.handle_start_agent_dialog()
            return
        self.send_json({"error": "Not found"}, status=404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.end_headers()

    def handle_aurelius_agent(self):
        if not GEMINI_API_KEY:
            self.send_json({"error": "GEMINI_API_KEY is not configured"}, status=503)
            return

        try:
            payload = self.read_json_body()
            answer = generate_agent_answer("aurelius", payload)
            self.send_json({"answer": answer})
        except Exception as error:
            print(f"Gemini error: {error}")
            self.send_json({"error": "Gemini request failed"}, status=502)

    def handle_start_agent_dialog(self):
        if not API_TOKEN:
            self.send_json({"error": "TELEGRAM_BOT_TOKEN is not configured"}, status=503)
            return

        try:
            payload = self.read_json_body()
            init_data = validate_init_data(payload.get("initData", ""))
            user = json.loads(init_data.get("user", "{}"))
            chat_id = user.get("id")
            agent_id = payload.get("agentId", "")
            if not chat_id:
                self.send_json({"error": "Telegram user is missing"}, status=400)
                return
            if agent_id not in AGENTS:
                self.send_json({"error": "Unknown agent"}, status=400)
                return

            set_active_agent(chat_id, agent_id)
            self.send_json(
                {
                    "ok": True,
                    "agentName": AGENTS[agent_id]["name"],
                    "botUsername": get_bot_username(),
                }
            )
        except ValueError as error:
            self.send_json({"error": str(error)}, status=403)
        except Exception as error:
            print(f"Start agent dialog error: {error}")
            self.send_json({"error": "Could not start agent dialog"}, status=502)

    def read_json_body(self, limit=12000):
        length = min(int(self.headers.get("Content-Length", "0")), limit)
        return json.loads(self.rfile.read(length).decode("utf-8") or "{}")

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def generate_agent_answer(agent_id, payload):
    agent = AGENTS.get(agent_id, AGENTS["aurelius"])
    model = GEMINI_MODEL.removeprefix("models/")
    url = (
        f"{GEMINI_API_BASE}/models/{urllib.parse.quote(model)}:generateContent"
        f"?key={urllib.parse.quote(GEMINI_API_KEY)}"
    )
    request_body = {
        "systemInstruction": {
            "parts": [
                {
                    "text": build_agent_system_prompt(agent)
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": build_agent_prompt(agent_id, payload)}],
            }
        ],
        "generationConfig": {
            "temperature": 0.72,
            "maxOutputTokens": GEMINI_MAX_OUTPUT_TOKENS,
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=45) as response:
        result = json.loads(response.read().decode("utf-8"))

    candidates = result.get("candidates") or []
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    text = "\n".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise ValueError("Gemini returned an empty answer")
    return text


def build_agent_system_prompt(agent):
    return (
        f"{agent['system']}\n\n"
        "Сейчас отвечай развёрнуто. Дай полноценный разбор, а не короткую реплику. "
        "Структура ответа: сначала прямой тезис, затем объяснение ситуации, затем практический следующий шаг. "
        "Если вопрос широкий, уточни смысл и предложи 2-3 направления размышления. "
        "Не обрывай мысль на полуслове. Оптимальная длина: 2-4 абзаца."
    )


def build_agent_prompt(agent_id, payload):
    agent = AGENTS.get(agent_id, AGENTS["aurelius"])
    profile = payload.get("profile") or {}
    diary = payload.get("diary") or []
    history = payload.get("history") or []
    message = (payload.get("message") or "").strip()
    context = {
        "agent": agent["name"],
        "agent_role": agent["role"],
        "name": profile.get("name") or "не указано",
        "age": profile.get("age") or "не указано",
        "location": profile.get("location") or "не указано",
        "interests": profile.get("interests") or "не указано",
        "main_goal": profile.get("mainGoal") or "не указано",
        "active_goal": (profile.get("goal") or {}).get("text") or "не указано",
        "current_problem": profile.get("currentProblem") or "не указано",
        "recent_diary": diary[:3],
        "recent_dialogue": history[-AGENT_HISTORY_LIMIT:],
    }
    return (
        "Контекст пользователя:\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
        "Вопрос или запрос пользователя:\n"
        f"{message or 'Дай короткий стоический совет на сегодня.'}"
    )


def validate_init_data(raw_init_data):
    if not raw_init_data:
        raise ValueError("Telegram initData is missing")
    if not API_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not configured")

    pairs = urllib.parse.parse_qsl(raw_init_data, keep_blank_values=True)
    data = dict(pairs)
    received_hash = data.pop("hash", "")
    if not received_hash:
        raise ValueError("Telegram initData hash is missing")

    auth_date = int(data.get("auth_date", "0") or "0")
    if not auth_date or time.time() - auth_date > INIT_DATA_MAX_AGE:
        raise ValueError("Telegram initData is expired")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", API_TOKEN.encode("utf-8"), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError("Telegram initData is invalid")

    return data


def get_bot_username():
    global BOT_USERNAME
    if BOT_USERNAME:
        return BOT_USERNAME.lstrip("@")
    try:
        result = api_call("getMe", {})
        BOT_USERNAME = result.get("result", {}).get("username", "")
    except Exception as error:
        print(f"Could not resolve bot username: {error}")
    return BOT_USERNAME.lstrip("@")


def handle_update(update):
    if "callback_query" in update:
        handle_callback(update["callback_query"])
        return

    message = update.get("message")
    if not message:
        return

    chat_id = message["chat"]["id"]

    if "web_app_data" in message:
        handle_web_app_data(chat_id, message["web_app_data"].get("data", "{}"))
        return

    text = (message.get("text") or "").strip()
    if text == "/start":
        sessions[chat_id] = {"step": "language"}
        send_language_picker(chat_id)
        return

    if text in {"/agents", "/agent"}:
        send_agent_picker(chat_id)
        return

    if text in {"/app", "/menu"}:
        send_dialog_menu(chat_id)
        return

    if text in {"/stop", "/reset_agent"}:
        clear_active_agent(chat_id)
        return

    session = sessions.get(chat_id)
    if session and session.get("step") == "name":
        session["name"] = text[:48] if text else "Traveler"
        session["step"] = "birthdate"
        send_birth_year_picker(chat_id, session, intro=True)
        return

    if session and session.get("step") == "birthdate":
        if not is_valid_birthdate(text):
            send_message(chat_id, t(session["lang"], "bad_birthdate"))
            return
        session["birthDate"] = text
        session["age"] = str(calculate_age_from_birthdate(text))
        session.pop("birthPicker", None)
        session["step"] = "country"
        send_country_picker(chat_id, session)
        return

    if text:
        if handle_agent_message(chat_id, text):
            return

    lang = session.get("lang", "ru") if session else "ru"
    send_message(chat_id, t(lang, "unknown"))


def handle_callback(callback):
    chat_id = callback["message"]["chat"]["id"]
    data = callback.get("data", "")
    session = sessions.setdefault(chat_id, {})
    answer_callback(callback["id"])

    if data.startswith("lang:"):
        lang = data.split(":", 1)[1]
        session.clear()
        session.update({
            "step": "name",
            "lang": lang,
            "registrationMessageId": callback["message"]["message_id"],
        })
        edit_registration_message(chat_id, session, t(lang, "intro"))
        return

    if data.startswith("age:"):
        session["age"] = data.split(":", 1)[1]
        session["step"] = "birthdate"
        send_birth_year_picker(chat_id, session, intro=True)
        return

    if data == "birth_noop":
        return

    if data.startswith("birth_adjust:"):
        _, unit, delta = data.split(":", 2)
        adjust_birth_picker(session, unit, int(delta))
        send_birth_picker(chat_id, session)
        return

    if data == "birth_done":
        selected = normalize_birth_picker(session)
        session["birthDate"] = selected.strftime("%Y-%m-%d")
        session["age"] = str(calculate_age(selected, datetime.now()))
        session.pop("birthPicker", None)
        session["step"] = "country"
        send_country_picker(chat_id, session)
        return

    if data == "birth_back:decades":
        send_birth_year_picker(chat_id, session)
        return

    if data.startswith("birth_decade:"):
        send_birth_year_picker(chat_id, session, int(data.split(":", 1)[1]))
        return

    if data.startswith("birth_year:"):
        session["birthYear"] = int(data.split(":", 1)[1])
        send_birth_month_picker(chat_id, session)
        return

    if data.startswith("birth_month:"):
        session["birthMonth"] = int(data.split(":", 1)[1])
        send_birth_day_picker(chat_id, session)
        return

    if data.startswith("birth_day:"):
        day = int(data.split(":", 1)[1])
        session["birthDate"] = f"{session['birthYear']:04d}-{session['birthMonth']:02d}-{day:02d}"
        session["age"] = str(calculate_age_from_birthdate(session["birthDate"]))
        session.pop("birthYear", None)
        session.pop("birthMonth", None)
        session["step"] = "country"
        send_country_picker(chat_id, session)
        return

    if data.startswith("country:"):
        country_code = data.split(":", 1)[1]
        session["country"] = country_label(country_code, session.get("lang", "ru"))
        session["step"] = "done"
        save_registration(chat_id, session)
        send_completion(chat_id, session)
        return

    if data.startswith("agent:"):
        agent_id = data.split(":", 1)[1]
        set_active_agent(chat_id, agent_id)
        return


def handle_web_app_data(chat_id, raw_data):
    try:
        payload = json.loads(raw_data)
    except json.JSONDecodeError:
        return

    registrations = read_registrations()
    profile = registrations.setdefault(str(chat_id), {})
    lang = profile.get("language", "ru")

    if payload.get("type") == "start_agent_dialog":
        set_active_agent(chat_id, payload.get("agentId", ""))
        return

    if payload.get("type") == "goal_set":
        profile["goal"] = {
            "id": payload.get("goalId"),
            "text": payload.get("goalText", ""),
            "createdAt": payload.get("createdAt"),
            "status": "active",
            "lastReminderDate": "",
        }
        write_registrations(registrations)
        send_message(chat_id, t(lang, "goal_set"))

    if payload.get("type") == "goal_close":
        if profile.get("goal"):
            profile["goal"]["status"] = "closed"
            profile["goal"]["closedAt"] = payload.get("closedAt")
        write_registrations(registrations)
        send_message(chat_id, t(lang, "goal_closed"))


def send_agent_picker(chat_id):
    set_chat_menu_button(chat_id, get_chat_webapp_url(chat_id))
    keyboard = [
        [{"text": agent["button"], "callback_data": f"agent:{agent_id}"}]
        for agent_id, agent in AGENTS.items()
    ]
    keyboard.append([{"text": "Open Mini App", "web_app": {"url": get_chat_webapp_url(chat_id)}}])
    send_message(
        chat_id,
        "Выбери агента для отдельного диалога в боте.\n\n"
        "После выбора просто пиши сообщение сюда — отвечать будет выбранный агент.\n"
        "Команды: /agents — сменить агента, /stop — закрыть режим агента.",
        keyboard,
    )


def set_active_agent(chat_id, agent_id):
    agent = AGENTS.get(agent_id)
    if not agent:
        send_agent_picker(chat_id)
        return

    registrations = read_registrations()
    profile = registrations.setdefault(str(chat_id), {})
    profile["activeAgent"] = agent_id
    profile.setdefault("agentHistory", {}).setdefault(agent_id, [])
    write_registrations(registrations)
    send_message(chat_id, build_agent_intro(agent))


def clear_active_agent(chat_id):
    registrations = read_registrations()
    profile = registrations.setdefault(str(chat_id), {})
    profile.pop("activeAgent", None)
    write_registrations(registrations)
    send_message(chat_id, "Режим агента закрыт. Чтобы выбрать нового агента, нажми /agents.")


def handle_agent_message(chat_id, text):
    registrations = read_registrations()
    profile = registrations.setdefault(str(chat_id), {})
    agent_id = profile.get("activeAgent")
    if not agent_id:
        return False

    if agent_id not in AGENTS:
        profile.pop("activeAgent", None)
        write_registrations(registrations)
        send_agent_picker(chat_id)
        return True

    if not GEMINI_API_KEY:
        send_message(chat_id, "GEMINI_API_KEY не настроен. Добавь ключ в переменные окружения и перезапусти бота.")
        return True

    send_chat_action(chat_id, "typing")
    history = profile.setdefault("agentHistory", {}).setdefault(agent_id, [])

    try:
        answer = generate_agent_answer(
            agent_id,
            {
                "message": text,
                "profile": profile,
                "history": history,
            },
        )
    except Exception as error:
        print(f"Agent dialogue error: {error}")
        send_message(chat_id, "Агент сейчас не смог ответить. Попробуй ещё раз через минуту.")
        return True

    history.extend(
        [
            {"role": "user", "text": text[:1200]},
            {"role": "agent", "text": answer[:1800]},
        ]
    )
    profile["agentHistory"][agent_id] = history[-AGENT_HISTORY_LIMIT:]
    write_registrations(registrations)
    send_message(chat_id, answer)
    return True


def build_agent_intro(agent):
    return (
        f"{agent['intro']}\n\n"
        "Пиши сюда как в обычный чат.\n\n"
        "Команды:\n"
        "/agents — сменить агента\n"
        "/app — открыть Mini App\n"
        "/stop — завершить диалог"
    )


def send_dialog_menu(chat_id):
    set_chat_menu_button(chat_id, get_chat_webapp_url(chat_id))
    send_message(chat_id, "Управление диалогом:", main_menu_keyboard(chat_id))


def main_menu_keyboard(chat_id=None):
    url = get_chat_webapp_url(chat_id) if chat_id else WEBAPP_URL
    return [
        [{"text": "Выбрать агента", "callback_data": "agent:picker"}],
        [{"text": "Open Mini App", "web_app": {"url": url}}],
    ]


def remind_due_goals():
    now = datetime.now()
    if now.hour < REMINDER_HOUR:
        return

    today = now.date().isoformat()
    registrations = read_registrations()
    changed = False

    for chat_id, profile in registrations.items():
        goal = profile.get("goal") or {}
        if goal.get("status") != "active":
            continue
        if goal.get("lastReminderDate") == today:
            continue

        send_message(chat_id, t(profile.get("language", "ru"), "reminder", goal=goal.get("text", "")))
        goal["lastReminderDate"] = today
        changed = True

    if changed:
        write_registrations(registrations)


def send_language_picker(chat_id):
    keyboard = [[{"text": label, "callback_data": f"lang:{code}"}] for code, label in LANGUAGES.items()]
    return send_message(chat_id, "Выбери язык / Choose language:", keyboard)


def init_birth_picker(session):
    if session.get("birthPicker"):
        return

    now = datetime.now()
    estimated_age = {
        "0-10": 5,
        "11-16": 14,
        "17-20": 19,
        "21-30": 25,
        "31+": 35,
    }.get(session.get("age"), 25)

    session["birthPicker"] = {
        "year": now.year - estimated_age,
        "month": 1,
        "day": 1,
    }
    normalize_birth_picker(session)


def send_birth_picker(chat_id, session):
    selected = normalize_birth_picker(session)
    lang = session.get("lang", "ru")
    months = MONTHS_EN if lang == "en" else MONTHS_RU
    month_label = months[selected.month - 1]

    if lang == "en":
        text = (
            f"{t(lang, 'ask_birthdate')}\n\n"
            f"Selected: {selected.strftime('%Y-%m-%d')}"
        )
        done_label = "Done"
        year_minus, year_plus = "- year", "+ year"
        month_minus, month_plus = "- month", "+ month"
        day_minus, day_plus = "- day", "+ day"
    else:
        text = (
            f"{t(lang, 'ask_birthdate')}\n\n"
            f"Выбрано: {selected.strftime('%Y-%m-%d')}"
        )
        done_label = "Готово"
        year_minus, year_plus = "- год", "+ год"
        month_minus, month_plus = "- месяц", "+ месяц"
        day_minus, day_plus = "- день", "+ день"

    keyboard = [
        [
            {"text": year_minus, "callback_data": "birth_adjust:year:-1"},
            {"text": str(selected.year), "callback_data": "birth_noop"},
            {"text": year_plus, "callback_data": "birth_adjust:year:1"},
        ],
        [
            {"text": month_minus, "callback_data": "birth_adjust:month:-1"},
            {"text": month_label, "callback_data": "birth_noop"},
            {"text": month_plus, "callback_data": "birth_adjust:month:1"},
        ],
        [
            {"text": day_minus, "callback_data": "birth_adjust:day:-1"},
            {"text": f"{selected.day:02d}", "callback_data": "birth_noop"},
            {"text": day_plus, "callback_data": "birth_adjust:day:1"},
        ],
        [{"text": done_label, "callback_data": "birth_done"}],
    ]
    edit_registration_message(chat_id, session, text, keyboard)


def adjust_birth_picker(session, unit, delta):
    selected = normalize_birth_picker(session)

    if unit == "year":
        selected = safe_datetime(selected.year + delta, selected.month, selected.day)
    elif unit == "month":
        month_index = selected.year * 12 + selected.month - 1 + delta
        year = month_index // 12
        month = month_index % 12 + 1
        selected = safe_datetime(year, month, selected.day)
    elif unit == "day":
        selected = selected + timedelta(days=delta)

    session["birthPicker"] = {
        "year": selected.year,
        "month": selected.month,
        "day": selected.day,
    }
    normalize_birth_picker(session)


def normalize_birth_picker(session):
    init_birth_picker(session) if not session.get("birthPicker") else None
    picker = session["birthPicker"]
    now = datetime.now()
    min_date = datetime(now.year - 100, 1, 1)

    year = max(min_date.year, min(now.year, int(picker.get("year", now.year - 25))))
    month = max(1, min(12, int(picker.get("month", 1))))
    day = max(1, int(picker.get("day", 1)))
    selected = safe_datetime(year, month, day)

    if selected > now:
        selected = now
    if selected < min_date:
        selected = min_date

    session["birthPicker"] = {
        "year": selected.year,
        "month": selected.month,
        "day": selected.day,
    }
    return selected


def safe_datetime(year, month, day):
    month = max(1, min(12, month))
    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, min(day, last_day))


def send_birth_year_picker(chat_id, session, decade=None, intro=False):
    lang = session.get("lang", "ru")
    now_year = datetime.now().year
    min_year = now_year - 100
    max_year = now_year

    if decade is None:
        decades = list(range((min_year // 10) * 10, max_year + 1, 10))
        keyboard = []
        row = []
        for start in decades:
            end = min(start + 9, max_year)
            row.append({"text": f"{start}-{end}", "callback_data": f"birth_decade:{start}"})
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        text = t(lang, "ask_birthdate") if intro else birth_picker_text(lang, "period")
        edit_registration_message(chat_id, session, text, keyboard)
        return

    years = [year for year in range(decade, min(decade + 10, max_year + 1)) if min_year <= year <= max_year]
    keyboard = []
    row = []
    for year in years:
        row.append({"text": str(year), "callback_data": f"birth_year:{year}"})
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    back_label = "← Periods" if lang == "en" else "← Периоды"
    keyboard.append([{"text": back_label, "callback_data": "birth_back:decades"}])
    edit_registration_message(chat_id, session, birth_picker_text(lang, "year"), keyboard)


def send_birth_month_picker(chat_id, session):
    lang = session.get("lang", "ru")
    months = MONTHS_EN if lang == "en" else MONTHS_RU
    keyboard = []
    row = []
    for index, label in enumerate(months, start=1):
        row.append({"text": label, "callback_data": f"birth_month:{index}"})
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    edit_registration_message(chat_id, session, birth_picker_text(lang, "month"), keyboard)


def send_birth_day_picker(chat_id, session):
    lang = session.get("lang", "ru")
    year = session["birthYear"]
    month = session["birthMonth"]
    days_in_month = calendar.monthrange(year, month)[1]
    keyboard = []
    row = []
    for day in range(1, days_in_month + 1):
        row.append({"text": str(day), "callback_data": f"birth_day:{day}"})
        if len(row) == 7:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    edit_registration_message(chat_id, session, birth_picker_text(lang, "day"), keyboard)


def birth_picker_text(lang, stage):
    labels = {
        "ru": {
            "period": "2/4 Выбери период рождения.",
            "year": "2/4 Выбери год рождения.",
            "month": "2/4 Выбери месяц рождения.",
            "day": "2/4 Выбери число рождения.",
        },
        "en": {
            "period": "2/4 Choose your birth period.",
            "year": "2/4 Choose your birth year.",
            "month": "2/4 Choose your birth month.",
            "day": "2/4 Choose your birth day.",
        },
    }
    return labels.get(lang, labels["ru"]).get(stage, labels["ru"]["period"])


def send_country_picker(chat_id, session):
    lang = session.get("lang", "ru")
    keyboard = [[{"text": country_label(code, lang), "callback_data": f"country:{code}"}] for code, _ in COUNTRIES]
    edit_registration_message(chat_id, session, t(session["lang"], "ask_country", name=session["name"]), keyboard)


def country_label(code, lang):
    labels = dict(COUNTRIES).get(code)
    if not labels:
        labels = dict(COUNTRIES)["other"]
    return labels.get(lang, labels["en"])


def send_completion(chat_id, session):
    lang = session["lang"]
    text = t(
        lang,
        "done",
        name=session["name"],
        age=session["age"],
        birthDate=session["birthDate"],
        country=session["country"],
    )
    keyboard = [[{"text": "Open Mini App", "web_app": {"url": build_webapp_url(session)}}]]
    edit_registration_message(chat_id, session, text, keyboard)
    set_chat_menu_button(chat_id, build_webapp_url(session))


def build_webapp_url(session):
    params = urllib.parse.urlencode(
        {
            "lang": session["lang"],
            "name": session["name"],
            "age": session["age"],
            "birthDate": session["birthDate"],
            "country": session["country"],
            "view": "home",
        }
    )
    separator = "&" if "?" in WEBAPP_URL else "?"
    return f"{WEBAPP_URL}{separator}{params}"


def get_chat_webapp_url(chat_id):
    registrations = read_registrations()
    profile = registrations.get(str(chat_id))
    if profile:
        return build_webapp_url_from_profile(profile)
    return WEBAPP_URL


def build_webapp_url_from_profile(profile):
    params = urllib.parse.urlencode(
        {
            "lang": profile.get("language", "ru"),
            "name": profile.get("name", ""),
            "age": profile.get("age", ""),
            "birthDate": profile.get("birthDate", ""),
            "country": profile.get("country", ""),
            "view": "home",
        }
    )
    separator = "&" if "?" in WEBAPP_URL else "?"
    return f"{WEBAPP_URL}{separator}{params}"


def set_chat_menu_button(chat_id, url):
    if WEBAPP_URL == "https://example.com":
        print("WEBAPP_URL is not configured; chat menu button was not updated")
        return
    try:
        api_call(
            "setChatMenuButton",
            {
                "chat_id": chat_id,
                "menu_button": {
                    "type": "web_app",
                    "text": "Open",
                    "web_app": {"url": url},
                },
            },
        )
    except Exception as error:
        print(f"setChatMenuButton error for {chat_id}: {error}")


def refresh_registered_menu_buttons():
    registrations = read_registrations()
    for chat_id, profile in registrations.items():
        if profile.get("birthDate") or profile.get("name"):
            set_chat_menu_button(chat_id, build_webapp_url_from_profile(profile))


def save_registration(chat_id, session):
    registrations = read_registrations()
    existing = registrations.get(str(chat_id), {})
    registrations[str(chat_id)] = {
        **existing,
        "language": session["lang"],
        "name": session["name"],
        "age": session["age"],
        "birthDate": session["birthDate"],
        "country": session["country"],
        "registeredAt": int(time.time()),
    }
    write_registrations(registrations)


def send_message(chat_id, text, inline_keyboard=None):
    chunks = split_telegram_message(text)
    last_result = None
    for index, chunk in enumerate(chunks):
        payload = {"chat_id": chat_id, "text": chunk}
        if inline_keyboard and index == len(chunks) - 1:
            payload["reply_markup"] = {"inline_keyboard": inline_keyboard}
        try:
            last_result = api_call("sendMessage", payload)
        except Exception as error:
            print(f"sendMessage error for {chat_id}: {error}")
    return last_result.get("result") if last_result else None


def edit_registration_message(chat_id, session, text, inline_keyboard=None):
    message_id = session.get("registrationMessageId")
    if not message_id:
        message = send_message(chat_id, text, inline_keyboard)
        if message:
            session["registrationMessageId"] = message["message_id"]
        return

    if edit_message(chat_id, message_id, text, inline_keyboard):
        return

    message = send_message(chat_id, text, inline_keyboard)
    if message:
        session["registrationMessageId"] = message["message_id"]


def edit_message(chat_id, message_id, text, inline_keyboard=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if inline_keyboard:
        payload["reply_markup"] = {"inline_keyboard": inline_keyboard}
    try:
        api_call("editMessageText", payload)
        return True
    except Exception as error:
        print(f"editMessageText error for {chat_id}: {error}")
        return False


def split_telegram_message(text):
    text = str(text or "")
    if len(text) <= TELEGRAM_MESSAGE_LIMIT:
        return [text]

    chunks = []
    rest = text
    while len(rest) > TELEGRAM_MESSAGE_LIMIT:
        split_at = rest.rfind("\n\n", 0, TELEGRAM_MESSAGE_LIMIT)
        if split_at < TELEGRAM_MESSAGE_LIMIT // 2:
            split_at = rest.rfind("\n", 0, TELEGRAM_MESSAGE_LIMIT)
        if split_at < TELEGRAM_MESSAGE_LIMIT // 2:
            split_at = rest.rfind(" ", 0, TELEGRAM_MESSAGE_LIMIT)
        if split_at < TELEGRAM_MESSAGE_LIMIT // 2:
            split_at = TELEGRAM_MESSAGE_LIMIT

        chunks.append(rest[:split_at].strip())
        rest = rest[split_at:].strip()

    if rest:
        chunks.append(rest)
    return chunks


def send_chat_action(chat_id, action):
    try:
        api_call("sendChatAction", {"chat_id": chat_id, "action": action})
    except Exception as error:
        print(f"sendChatAction error for {chat_id}: {error}")


def answer_callback(callback_id):
    try:
        api_call("answerCallbackQuery", {"callback_query_id": callback_id})
    except Exception as error:
        print(f"answerCallbackQuery error: {error}")


def api_call(method, payload):
    request = urllib.request.Request(
        f"{API_URL}/{method}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API {method} failed with HTTP {error.code}: {body}") from error


def t(lang, key, **kwargs):
    return MESSAGES.get(lang, MESSAGES["ru"])[key].format(**kwargs)


def is_valid_birthdate(value):
    try:
        date = datetime.strptime(value, "%Y-%m-%d")
        return date <= datetime.now()
    except ValueError:
        return False


def calculate_age_from_birthdate(value):
    return calculate_age(datetime.strptime(value, "%Y-%m-%d"), datetime.now())


def calculate_age(birth_date, now):
    age = now.year - birth_date.year
    birthday_passed = (now.month, now.day) >= (birth_date.month, birth_date.day)
    return age if birthday_passed else age - 1


def ensure_registrations_file():
    if not REGISTRATIONS_FILE.exists():
        REGISTRATIONS_FILE.write_text("{}", encoding="utf-8")


def read_registrations():
    ensure_registrations_file()
    return json.loads(REGISTRATIONS_FILE.read_text(encoding="utf-8"))


def write_registrations(registrations):
    REGISTRATIONS_FILE.write_text(
        json.dumps(registrations, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
