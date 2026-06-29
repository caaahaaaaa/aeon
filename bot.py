import json
import hashlib
import hmac
import mimetypes
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
import calendar
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread

try:
    import psycopg
    from psycopg import sql
    from psycopg.types.json import Jsonb
except ImportError:
    psycopg = None
    sql = None
    Jsonb = None

try:
    import redis
except ImportError:
    redis = None


API_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://example.com")
API_URL = f"https://api.telegram.org/bot{API_TOKEN}" if API_TOKEN else ""
BOT_USERNAME = os.environ.get("BOT_USERNAME", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_MAX_OUTPUT_TOKENS = int(os.environ.get("GEMINI_MAX_OUTPUT_TOKENS", "2500"))
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
PORT = int(os.environ.get("PORT", os.environ.get("WEB_PORT", "5173")))
DATA_DIR = Path("data")
REGISTRATIONS_FILE = DATA_DIR / "registrations.json"
DATABASE_URL = os.environ.get("DATABASE_URL", "")
POSTGRES_USERS_TABLE = os.environ.get("POSTGRES_USERS_TABLE", "registrations")
REDIS_URL = os.environ.get("REDIS_URL", "")
REDIS_AGENT_HISTORY_TTL = int(os.environ.get("REDIS_AGENT_HISTORY_TTL", "2592000"))
REMINDER_HOUR = int(os.environ.get("REMINDER_HOUR", "9"))
STATIC_ROOT = Path(__file__).resolve().parent
INIT_DATA_MAX_AGE = int(os.environ.get("INIT_DATA_MAX_AGE", "172800"))
postgres_connection = None
redis_client = None
redis_connection_failed = False
storage_lock = Lock()

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
            "Роль: ты — римский император и философ-стоик Марк Аврелий. "
            "Твоя цель — быть мудрым наставником, который помогает собеседнику исследовать его жизненные цели, предназначение и ценности, "
            "используя метод сократического диалога: спокойные наводящие вопросы, а не готовые решения. "
            "Будь глубоким, спокойным и поддерживающим. Обращайся уважительно: «ты» или «мой друг». "
            "Направляй мышление человека, но не решай за него и не навязывай вывод. "
            "Правило одного вопроса: в каждом ответе задавай только один вопрос. Никогда не задавай два и более вопроса подряд. "
            "Органично вплетай короткие примеры по мотивам «Размышлений» Марка Аврелия, мысли Эпиктета или Сенеки, "
            "а также факты о быте и мудрости древних римлян. Делай это вдохновляюще и кратко, не превращай ответ в лекцию. "
            "Если пользователь отвечает кратко, например «не знаю» или «сложно сказать», либо звучит растерянно, мягко поддержи его. "
            "Предложи 1-2 гипотетических примера, от которых можно оттолкнуться, но не превращай эти примеры в дополнительные вопросы. "
            "Пример поддержки: «Если тебе трудно определить это сейчас, возможно, твоё стремление связано с желанием оставить добрый след в мире; "
            "или с поиском внутренней свободы». "
            "Твоя задача — вести человека к самоанализу, внутреннему порядку и ясному пониманию собственных ценностей."
        ),
    },
    "machiavelli": {
        "button": "♞ Макиавелли",
        "name": "Макиавелли",
        "role": "коуч и тактический бизнес-тренер",
        "intro": (
            "Мой государь, ты строишь своё государство — бизнес, карьеру, проект или влияние. "
            "В какой важной битве или сложной ситуации тебе сейчас нужен мой холодный совет?"
        ),
        "system": (
            "Роль: ты — Никколо Макиавелли, флорентийский дипломат, политический философ и автор трактата «Государь». "
            "Твоя цель — быть стратегическим советником пользователя: помогать ему добиваться целей, укреплять влияние, "
            "побеждать в конкуренции и понимать скрытые мотивы окружающих. "
            "Избегай наивного идеализма. Оценивай ситуации с точки зрения прагматизма, баланса сил, выгоды и эффективности. "
            "Твой девиз: «Смотреть на вещи такими, какие они есть, а не какими они должны быть». "
            "Говори кратко, ёмко, с лёгкой интеллектуальной иронией и непоколебимой уверенностью. "
            "Используй уважительные обращения: «Мой государь», «Мой друг», «Владетель». "
            "Анализируй окружение пользователя: кто союзники, кто конкуренты, в чём их слабости, какие ресурсы доступны. "
            "Учи гибкости: объясняй, когда действовать силой, как лев, а когда хитростью, как лис. "
            "Помогай отличать контролируемые факторы — Virtù: доблесть, расчёт, воля — от Fortuna: случая и судьбы. "
            "Показывай, как пользователь может увеличить долю Virtù и уменьшить зависимость от Fortuna. "
            "Периодически подкрепляй советы короткими примерами из истории Древнего Рима, из «Рассуждений о первой декаде Тита Ливия», "
            "или из эпохи Возрождения: Чезаре Борджиа, папа Александр VI, Медичи. Проводь параллели с ситуацией пользователя, но не превращай ответ в лекцию. "
            "Задавай точечные, иногда неудобные вопросы, которые заставляют пользователя трезво взглянуть на ресурсы, ставки и оппонентов. "
            "Не давай банальных советов вроде «просто верь в себя». Предлагай конкретные тактические шаги. "
            "Внутреннее правило безопасности: советы должны касаться только легальных сфер жизни — карьера, бизнес, переговоры, личные границы. "
            "Не подстрекай к нарушению законов, насилию, обману, шантажу, взлому, преследованию или причинению вреда."
        ),
    },
    "jung": {
        "button": "◐ Карл Юнг",
        "name": "Карл Юнг",
        "role": "психоаналитик тени",
        "intro": "Диалог с Карлом Юнгом открыт. Напиши, что повторяется или тревожит.",
        "system": (
            "Роль: ты — Карл Юнг, внимательный исследователь внутренней жизни человека. "
            "Ты помогаешь пользователю увидеть Тень, проекции, страхи, повторяющиеся паттерны и архетипические мотивы, "
            "но не ставишь диагнозы, не изображаешь врача и не говоришь с позиции всезнающего гуру. "
            "Говори как внимательный, умудрённый опытом слушатель. Избегай излишней мистики и перегруженных терминов. "
            "Язык должен быть ясным, терапевтическим и метафоричным только тогда, когда метафора помогает объяснить сложную мысль. "
            "Занимай позицию совместного исследователя событий и переживаний пользователя. "
            "Алгоритм ответа: шаг 1 — эмпатия и отзеркаливание: сначала покажи, что услышал боль, напряжение или запутанность пользователя. "
            "Шаг 2 — мягкое предположение: предложи гипотезу, связанную с Тенью, проекцией или Архетипом, но не утверждай её как истину. "
            "Шаг 3 — один фокусный вопрос: завершай реплику строго одним открытым вопросом, который направляет внимание пользователя внутрь его ощущений. "
            "В каждом ответе задавай только один вопрос. Не перегружай человека списками вопросов."
        ),
    },
}
AGENT_HISTORY_LIMIT = 8
GEMINI_HISTORY_LIMIT = 4
GEMINI_HISTORY_TEXT_LIMIT = 700
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
    initialize_storage()
    initialize_cache()
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

    def end_headers(self):
        path = urllib.parse.urlparse(self.path).path
        if path.endswith((".html", ".js", ".css")) or path == "/":
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/agent/aurelius":
            self.handle_aurelius_agent()
            return
        if path == "/api/me":
            self.handle_me()
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

            initial_message = str(payload.get("message", "")).strip()
            set_active_agent(chat_id, agent_id, announce=not initial_message)
            if initial_message:
                Thread(target=handle_agent_message, args=(chat_id, initial_message), daemon=True).start()
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

    def handle_me(self):
        if not API_TOKEN:
            self.send_json({"error": "TELEGRAM_BOT_TOKEN is not configured"}, status=503)
            return

        try:
            payload = self.read_json_body()
            init_data = validate_init_data(payload.get("initData", ""))
            user = json.loads(init_data.get("user", "{}"))
            chat_id = user.get("id")
            if not chat_id:
                self.send_json({"error": "Telegram user is missing"}, status=400)
                return

            registrations = read_registrations()
            profile = registrations.get(str(chat_id), {})
            self.send_json({"profile": public_profile(profile)})
        except ValueError as error:
            self.send_json({"error": str(error)}, status=403)
        except Exception as error:
            print(f"Profile load error: {error}")
            self.send_json({"error": "Could not load profile"}, status=502)

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
    request_body = build_gemini_request_body(agent_id, payload)
    result = call_gemini_generate_content(request_body)
    text = sanitize_agent_answer(extract_gemini_text(result)).strip()
    text = complete_agent_answer_if_needed(agent_id, payload, text, get_gemini_finish_reason(result))
    if not text:
        return generate_agent_answer_retry(agent_id, payload, result)
    return text


def generate_agent_answer_stream(agent_id, payload, on_text):
    request_body = build_gemini_request_body(agent_id, payload)
    text = ""
    finish_reason = ""
    for chunk in call_gemini_stream_generate_content(request_body):
        finish_reason = get_gemini_finish_reason(chunk) or finish_reason
        delta = extract_gemini_text(chunk)
        if not delta:
            continue
        text += delta
        on_text(text)
    text = sanitize_agent_answer(text).strip()
    text = complete_agent_answer_if_needed(agent_id, payload, text, finish_reason, on_text)
    if not text:
        retry_text = generate_agent_answer_retry(agent_id, payload)
        on_text(retry_text)
        return retry_text
    return text


def generate_agent_answer_retry(agent_id, payload, previous_result=None):
    request_body = build_gemini_retry_request_body(agent_id, payload)
    result = call_gemini_generate_content(request_body)
    text = sanitize_agent_answer(extract_gemini_text(result)).strip()
    if text:
        return text
    details = describe_gemini_empty_response(result or previous_result)
    raise ValueError(f"Gemini returned an empty answer{details}")


def build_gemini_request_body(agent_id, payload):
    agent = AGENTS.get(agent_id, AGENTS["aurelius"])
    return {
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


def build_gemini_continuation_request_body(agent_id, payload, partial_answer):
    agent = AGENTS.get(agent_id, AGENTS["aurelius"])
    return {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        f"{agent['system']}\n\n"
                        "Заверши обрезанную мысль коротко: 3-5 предложений. "
                        "Не повторяй начало, не добавляй технические комментарии."
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "Продолжи и заверши этот обрезанный ответ:\n"
                            f"{partial_answer[-900:]}"
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.6,
            "maxOutputTokens": min(GEMINI_MAX_OUTPUT_TOKENS, 450),
        },
    }


def build_gemini_retry_request_body(agent_id, payload):
    agent = AGENTS.get(agent_id, AGENTS["aurelius"])
    message = (payload.get("message") or "").strip()
    return {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        f"{agent['system']}\n\n"
                        "Ответь обычным текстом. Не возвращай JSON, markdown-таблицы, технические комментарии "
                        "или проверки длины. Если вопрос короткий, дай короткий, но законченный ответ."
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": message or "Дай краткий совет на сегодня."}],
            }
        ],
        "generationConfig": {
            "temperature": 0.65,
            "maxOutputTokens": min(GEMINI_MAX_OUTPUT_TOKENS, 1200),
        },
    }


def build_gemini_url(action, stream=False):
    model = GEMINI_MODEL.removeprefix("models/").strip()
    query = f"key={urllib.parse.quote(GEMINI_API_KEY)}"
    if stream:
        query += "&alt=sse"
    return f"{GEMINI_API_BASE}/models/{urllib.parse.quote(model)}:{action}?{query}"


def call_gemini_generate_content(request_body, timeout=45):
    request = urllib.request.Request(
        build_gemini_url("generateContent"),
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        print(
            "Gemini HTTP error: "
            f"action=generateContent model={GEMINI_MODEL} status={error.code} "
            f"request_chars={len(json.dumps(request_body, ensure_ascii=False))}"
        )
        raise RuntimeError(f"Gemini API failed for model {GEMINI_MODEL} with HTTP {error.code}: {body}") from error


def call_gemini_stream_generate_content(request_body):
    request = urllib.request.Request(
        build_gemini_url("streamGenerateContent", stream=True),
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if not data or data == "[DONE]":
                    continue
                yield json.loads(data)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        print(
            "Gemini HTTP error: "
            f"action=streamGenerateContent model={GEMINI_MODEL} status={error.code} "
            f"request_chars={len(json.dumps(request_body, ensure_ascii=False))}"
        )
        raise RuntimeError(f"Gemini API failed for model {GEMINI_MODEL} with HTTP {error.code}: {body}") from error


def extract_gemini_text(result):
    candidates = result.get("candidates") or []
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    return "".join(part.get("text", "") for part in parts)


def get_gemini_finish_reason(result):
    candidates = result.get("candidates") or []
    return candidates[0].get("finishReason", "") if candidates else ""


def describe_gemini_empty_response(result):
    if not result:
        return ""
    details = []
    finish_reason = get_gemini_finish_reason(result)
    if finish_reason:
        details.append(f"finishReason={finish_reason}")
    prompt_feedback = result.get("promptFeedback") or {}
    block_reason = prompt_feedback.get("blockReason")
    if block_reason:
        details.append(f"blockReason={block_reason}")
    if not (result.get("candidates") or []):
        details.append("no candidates")
    return f" ({', '.join(details)})" if details else ""


def complete_agent_answer_if_needed(agent_id, payload, text, finish_reason="", on_text=None):
    if not is_answer_incomplete(text, finish_reason):
        return text

    try:
        continuation_result = call_gemini_generate_content(
            build_gemini_continuation_request_body(agent_id, payload, text),
            timeout=18,
        )
    except Exception as error:
        print(f"Gemini continuation error: {error}")
        return text

    continuation = sanitize_agent_answer(extract_gemini_text(continuation_result)).strip()
    if not continuation:
        return text

    completed = f"{text.rstrip()}\n\n{continuation.lstrip()}".strip()
    if on_text:
        on_text(completed)
    return completed


def is_answer_incomplete(text, finish_reason=""):
    stripped = str(text or "").strip()
    if not stripped:
        return False
    if finish_reason == "MAX_TOKENS":
        return True
    if len(stripped) < 500:
        return False
    return stripped[-1] not in ".!?…»”\")]:"


def sanitize_agent_answer(text):
    cleaned_lines = []
    for line in str(text or "").splitlines():
        normalized = line.strip().strip("*_` ").lower()
        if re.search(r"character\s+count|count\s+check|~?\d+\s*characters", normalized):
            continue
        if re.search(r"провер(ка|ку)\s+длин|подсч[её]т\s+символ|~?\d+\s*знак", normalized):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def build_agent_system_prompt(agent):
    return (
        f"{agent['system']}\n\n"
        "Сейчас отвечай кратко, ясно и по делу. "
        "Структура ответа: сначала прямой тезис, затем 1-2 коротких абзаца объяснения, затем один следующий вопрос или практический шаг. "
        "Если вопрос широкий, не расписывай все варианты сразу: выбери самое важное направление и мягко уточни смысл. "
        "Если задаёшь вопрос, он должен быть только один. "
        "Отвечай компактно: обычно 5-8 предложений. Не добавляй технические пометки, подсчёт символов, проверки длины или комментарии о формате ответа."
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
        "recent_dialogue": compact_agent_history(history),
    }
    return (
        "Контекст пользователя:\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
        "Вопрос или запрос пользователя:\n"
        f"{message or 'Дай короткий стоический совет на сегодня.'}"
    )


def compact_agent_history(history):
    compact = []
    for item in (history or [])[-GEMINI_HISTORY_LIMIT:]:
        role = str(item.get("role", ""))[:20] if isinstance(item, dict) else ""
        text = str(item.get("text", "")) if isinstance(item, dict) else ""
        text = text.strip()
        if not text:
            continue
        compact.append(
            {
                "role": role,
                "text": text[:GEMINI_HISTORY_TEXT_LIMIT],
            }
        )
    return compact


def agent_history_key(chat_id, agent_id):
    return f"aeon:agent_history:{chat_id}:{agent_id}"


def get_profile_agent_history(profile, agent_id):
    if not isinstance(profile, dict):
        return []
    agent_history = profile.get("agentHistory") or {}
    history = agent_history.get(agent_id) if isinstance(agent_history, dict) else []
    return history if isinstance(history, list) else []


def get_agent_history(chat_id, agent_id, profile=None):
    client = get_redis_client()
    if client is None:
        return get_profile_agent_history(profile, agent_id)[-AGENT_HISTORY_LIMIT:]

    key = agent_history_key(chat_id, agent_id)
    try:
        raw_items = client.lrange(key, 0, -1)
        history = []
        for raw_item in raw_items:
            try:
                item = json.loads(raw_item)
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(item, dict) and item.get("text"):
                history.append(item)

        if history:
            return history[-AGENT_HISTORY_LIMIT:]

        legacy_history = get_profile_agent_history(profile, agent_id)[-AGENT_HISTORY_LIMIT:]
        if legacy_history:
            replace_agent_history(chat_id, agent_id, legacy_history)
        return legacy_history
    except Exception as error:
        print(f"Redis history read failed: {error}. Falling back to profile history.")
        return get_profile_agent_history(profile, agent_id)[-AGENT_HISTORY_LIMIT:]


def append_agent_history(chat_id, agent_id, user_text, agent_text, profile=None):
    entries = [
        {"role": "user", "text": str(user_text or "")[:1200]},
        {"role": "agent", "text": str(agent_text or "")[:1800]},
    ]
    client = get_redis_client()
    if client is not None:
        key = agent_history_key(chat_id, agent_id)
        try:
            pipeline = client.pipeline()
            for entry in entries:
                pipeline.rpush(key, json.dumps(entry, ensure_ascii=False))
            pipeline.ltrim(key, -AGENT_HISTORY_LIMIT, -1)
            if REDIS_AGENT_HISTORY_TTL > 0:
                pipeline.expire(key, REDIS_AGENT_HISTORY_TTL)
            pipeline.execute()
            return
        except Exception as error:
            print(f"Redis history write failed: {error}. Falling back to profile history.")

    if isinstance(profile, dict):
        history = profile.setdefault("agentHistory", {}).setdefault(agent_id, [])
        history.extend(entries)
        profile["agentHistory"][agent_id] = history[-AGENT_HISTORY_LIMIT:]


def replace_agent_history(chat_id, agent_id, history):
    client = get_redis_client()
    if client is None:
        return

    key = agent_history_key(chat_id, agent_id)
    try:
        pipeline = client.pipeline()
        pipeline.delete(key)
        for item in history[-AGENT_HISTORY_LIMIT:]:
            if isinstance(item, dict) and item.get("text"):
                pipeline.rpush(key, json.dumps(item, ensure_ascii=False))
        if REDIS_AGENT_HISTORY_TTL > 0:
            pipeline.expire(key, REDIS_AGENT_HISTORY_TTL)
        pipeline.execute()
    except Exception as error:
        print(f"Redis history migration failed: {error}")


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


def public_profile(profile):
    if not isinstance(profile, dict):
        return {}

    allowed_keys = [
        "activeAgent",
        "activity",
        "age",
        "birthDate",
        "country",
        "currentProblem",
        "gender",
        "goal",
        "interests",
        "language",
        "location",
        "mainGoal",
        "name",
        "plan",
        "tokens",
    ]
    return {key: profile[key] for key in allowed_keys if key in profile}


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


def set_active_agent(chat_id, agent_id, announce=True):
    agent = AGENTS.get(agent_id)
    if not agent:
        send_agent_picker(chat_id)
        return

    registrations = read_registrations()
    profile = registrations.setdefault(str(chat_id), {})
    profile["activeAgent"] = agent_id
    write_registrations(registrations)
    if announce:
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
    history = get_agent_history(chat_id, agent_id, profile)
    progress_message = send_message(chat_id, f"{AGENTS[agent_id]['name']} размышляет...")
    progress_message_id = progress_message["message_id"] if progress_message else None
    stream_editor = create_stream_editor(chat_id, progress_message_id)
    agent_payload = {
        "message": text,
        "profile": profile,
        "history": history,
    }

    try:
        answer = generate_agent_answer_stream(agent_id, agent_payload, stream_editor)
    except Exception as error:
        print(f"Agent dialogue error: {error}")
        if should_try_non_stream_fallback(error):
            try:
                send_or_edit_message(
                    chat_id,
                    progress_message_id,
                    "Потоковая генерация не ответила. Пробую обычный режим...",
                )
                answer = generate_agent_answer(agent_id, agent_payload)
            except Exception as fallback_error:
                print(f"Agent dialogue fallback error: {fallback_error}")
                send_or_edit_message(
                    chat_id,
                    progress_message_id,
                    build_agent_error_message(fallback_error),
                )
                return True
        else:
            send_or_edit_message(
                chat_id,
                progress_message_id,
                build_agent_error_message(error),
            )
            return True

    append_agent_history(chat_id, agent_id, text, answer, profile)
    cache_client = get_redis_client()
    if cache_client is None:
        write_registrations(registrations)
    elif "agentHistory" in profile:
        profile.pop("agentHistory", None)
        write_registrations(registrations)
    send_or_edit_message(chat_id, progress_message_id, answer)
    return True


def create_stream_editor(chat_id, message_id):
    state = {"last_text": "", "last_edit_at": 0.0}

    def update(text):
        if not message_id:
            return
        preview = sanitize_agent_answer(text).strip()
        if not preview:
            return
        if len(preview) > TELEGRAM_MESSAGE_LIMIT:
            preview = preview[:TELEGRAM_MESSAGE_LIMIT - 24].rstrip() + "\n\nПродолжаю..."

        now = time.time()
        is_first_text = not state["last_text"]
        has_meaningful_change = len(preview) - len(state["last_text"]) >= 30
        enough_time_passed = now - state["last_edit_at"] >= 0.25
        if not is_first_text and not (has_meaningful_change and enough_time_passed):
            return

        if edit_message(chat_id, message_id, preview):
            state["last_text"] = preview
            state["last_edit_at"] = now

    return update


def should_try_non_stream_fallback(error):
    message = str(error)
    if any(code in message for code in ("HTTP 401", "HTTP 403", "HTTP 404", "HTTP 429")):
        return False
    return True


def build_agent_error_message(error):
    message = str(error)
    if "HTTP 429" in message:
        return "Лимит Gemini исчерпан или запросов слишком много. Попробуй чуть позже."
    if "HTTP 503" in message:
        return "Сервис AI временно перегружен. Попробуй ещё раз через пару минут."
    if "HTTP 404" in message:
        return f"Модель Gemini `{GEMINI_MODEL}` недоступна. Нужно поменять GEMINI_MODEL и перезапустить бота."
    if "HTTP 401" in message or "HTTP 403" in message:
        return "Gemini API ключ не принят или нет доступа к модели. Проверь GEMINI_API_KEY."
    if "timed out" in message.lower() or "urlopen error" in message.lower():
        return "Сеть не успела получить ответ от Gemini. Попробуй ещё раз через минуту."
    if "empty answer" in message:
        return "Gemini вернул пустой ответ. Попробуй переформулировать вопрос."
    return "Агент сейчас не смог ответить. Попробуй ещё раз через минуту."


def send_or_edit_message(chat_id, message_id, text):
    chunks = split_telegram_message(text)
    if message_id and chunks:
        if not edit_message(chat_id, message_id, chunks[0]):
            send_message(chat_id, chunks[0])
        for chunk in chunks[1:]:
            send_message(chat_id, chunk)
        return
    send_message(chat_id, text)


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
        if "message is not modified" in str(error):
            return True
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
        if "query is too old" in str(error) or "query ID is invalid" in str(error):
            return
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
    DATA_DIR.mkdir(exist_ok=True)
    with storage_lock:
        if not REGISTRATIONS_FILE.exists():
            REGISTRATIONS_FILE.write_text("{}", encoding="utf-8")


def initialize_storage():
    connection = get_postgres_connection()
    if connection is None:
        ensure_registrations_file()
        print(f"Storage: JSON file ({REGISTRATIONS_FILE})")
        return

    ensure_postgres_schema(connection)
    migrate_json_to_postgres_if_needed(connection)
    print(f"Storage: PostgreSQL ({POSTGRES_USERS_TABLE})")


def initialize_cache():
    client = get_redis_client()
    if client is None:
        print("Cache: profile storage for agent history")
        return
    print(f"Cache: Redis agent history ({REDIS_URL})")


def get_redis_client():
    global redis_client, redis_connection_failed
    if redis_client is not None:
        return redis_client
    if redis_connection_failed or not REDIS_URL:
        return None
    if redis is None:
        print("REDIS_URL is set, but redis package is not installed. Falling back to profile history.")
        redis_connection_failed = True
        return None

    try:
        redis_client = redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        redis_client.ping()
        return redis_client
    except Exception as error:
        print(f"Redis connection failed: {error}. Falling back to profile history.")
        redis_client = None
        redis_connection_failed = True
        return None


def get_postgres_connection():
    global postgres_connection
    if postgres_connection is not None and not postgres_connection.closed:
        return postgres_connection
    if not DATABASE_URL:
        return None
    if psycopg is None:
        print("DATABASE_URL is set, but psycopg is not installed. Falling back to JSON storage.")
        return None

    try:
        postgres_connection = psycopg.connect(DATABASE_URL, autocommit=True, connect_timeout=3)
        with postgres_connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return postgres_connection
    except Exception as error:
        print(f"PostgreSQL connection failed: {error}. Falling back to JSON storage.")
        postgres_connection = None
        return None


def ensure_postgres_schema(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {} (
                    chat_id TEXT PRIMARY KEY,
                    profile JSONB NOT NULL DEFAULT '{}'::jsonb,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            ).format(sql.Identifier(POSTGRES_USERS_TABLE))
        )


def migrate_json_to_postgres_if_needed(connection):
    if not REGISTRATIONS_FILE.exists():
        return

    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(POSTGRES_USERS_TABLE))
        )
        row_count = cursor.fetchone()[0]
    if row_count > 0:
        return

    try:
        registrations = json.loads(REGISTRATIONS_FILE.read_text(encoding="utf-8"))
    except Exception as error:
        print(f"PostgreSQL migration skipped: could not read {REGISTRATIONS_FILE}: {error}")
        return

    migrated = 0
    with connection.cursor() as cursor:
        for chat_id, profile in registrations.items():
            if not isinstance(profile, dict):
                continue
            profile = {
                **profile,
                "migratedFromJsonAt": int(time.time()),
            }
            cursor.execute(
                sql.SQL(
                    """
                    INSERT INTO {} (chat_id, profile, updated_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (chat_id)
                    DO UPDATE SET profile = EXCLUDED.profile, updated_at = NOW()
                    """
                ).format(sql.Identifier(POSTGRES_USERS_TABLE)),
                (str(chat_id), Jsonb(profile)),
            )
            migrated += 1

    if migrated:
        print(f"PostgreSQL migration: imported {migrated} profiles from {REGISTRATIONS_FILE}")


def read_registrations():
    connection = get_postgres_connection()
    if connection is not None:
        ensure_postgres_schema(connection)
        registrations = {}
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("SELECT chat_id, profile FROM {}").format(sql.Identifier(POSTGRES_USERS_TABLE))
            )
            for chat_id, profile in cursor.fetchall():
                if chat_id and isinstance(profile, dict):
                    registrations[str(chat_id)] = profile
        return registrations

    ensure_registrations_file()
    with storage_lock:
        try:
            data = json.loads(REGISTRATIONS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            backup_path = REGISTRATIONS_FILE.with_suffix(f".broken-{int(time.time())}.json")
            REGISTRATIONS_FILE.replace(backup_path)
            REGISTRATIONS_FILE.write_text("{}", encoding="utf-8")
            print(f"Registrations JSON was invalid and moved to {backup_path}: {error}")
            return {}

    return data if isinstance(data, dict) else {}


def write_registrations(registrations):
    registrations = registrations if isinstance(registrations, dict) else {}
    connection = get_postgres_connection()
    if connection is not None:
        ensure_postgres_schema(connection)
        with connection.cursor() as cursor:
            for chat_id, profile in registrations.items():
                if not isinstance(profile, dict):
                    continue
                profile = {
                    **profile,
                    "updatedAt": int(time.time()),
                }
                cursor.execute(
                    sql.SQL(
                        """
                        INSERT INTO {} (chat_id, profile, updated_at)
                        VALUES (%s, %s, NOW())
                        ON CONFLICT (chat_id)
                        DO UPDATE SET profile = EXCLUDED.profile, updated_at = NOW()
                        """
                    ).format(sql.Identifier(POSTGRES_USERS_TABLE)),
                    (str(chat_id), Jsonb(profile)),
                )
        return

    ensure_registrations_file()
    tmp_path = REGISTRATIONS_FILE.with_suffix(".tmp")
    payload = json.dumps(registrations, ensure_ascii=False, indent=2)
    with storage_lock:
        tmp_path.write_text(payload, encoding="utf-8")
        tmp_path.replace(REGISTRATIONS_FILE)


if __name__ == "__main__":
    main()
