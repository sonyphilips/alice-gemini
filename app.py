from flask import Flask, request, jsonify
import json
import os
import urllib.request
import urllib.error
import time
import threading

app = Flask(__name__)

# =========================
# 🧠 ДОЛГАЯ ПАМЯТЬ (ФАЙЛ)
# =========================
MEMORY_FILE = "memory.json"
lock = threading.Lock()

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_memory(data):
    with lock:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

CHAT_MEMORY = load_memory()

MAX_HISTORY = 12

# =========================
# ⚡ РЕЖИМЫ АССИСТЕНТА
# =========================
MODES = {
    "friend": "Ты дружелюбный, простой друг. Отвечай легко и по-человечески.",
    "assistant": "Ты умный полезный ассистент. Отвечай чётко и по делу.",
    "expert": "Ты эксперт. Давай точные, глубокие и технические ответы."
}

DEFAULT_MODE = "assistant"

# =========================
# 🧠 ПРЕДСТАВЛЕНИЕ ЛИЧНОСТИ
# =========================
BASE_PERSONALITY = (
    "Ты AI ассистент внутри голосового помощника. "
    "Ты краткий, умный, не болтаешь лишнего."
)

# =========================
# ⚡ АНТИ-СПАМ
# =========================
LAST_REQUEST_TIME = 0
MIN_DELAY = 0.4

# =========================
# 🛡 СТАБИЛЬНЫЕ МОДЕЛИ OPENROUTER
# =========================
MODELS = [
    "mistralai/mistral-7b-instruct",
    "openchat/openchat-7b",
    "gryphe/mythomax-l2-13b"
]


@app.route("/", methods=["GET"])
def home():
    return "OK", 200


@app.route("/", methods=["POST"])
@app.route("/alice", methods=["POST"])
def handler():
    global LAST_REQUEST_TIME, CHAT_MEMORY

    try:
        body = request.get_json(force=True)

        req = body.get("request", {})
        session = body.get("session", {}).get("session_id", "default")

        user_text = req.get("command") or req.get("original_utterance", "")

        if not user_text:
            return send_response("Спроси меня что-нибудь.", [])

        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            return send_response("Нет API ключа.", [])

        # =========================
        # ⚡ ускорение
        # =========================
        now = time.time()
        if now - LAST_REQUEST_TIME < MIN_DELAY:
            time.sleep(MIN_DELAY - (now - LAST_REQUEST_TIME))
        LAST_REQUEST_TIME = time.time()

        # =========================
        # 🧠 режим
        # =========================
        mode = DEFAULT_MODE
        if session in CHAT_MEMORY and isinstance(CHAT_MEMORY[session], dict):
            mode = CHAT_MEMORY[session].get("mode", DEFAULT_MODE)

        system_prompt = BASE_PERSONALITY + " " + MODES.get(mode, MODES["assistant"])

        # =========================
        # 🧠 память
        # =========================
        if session not in CHAT_MEMORY:
            CHAT_MEMORY[session] = {
                "history": [],
                "mode": DEFAULT_MODE
            }

        history = CHAT_MEMORY[session]["history"]

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})

        # =========================
        # 🌐 OpenRouter (fallback)
        # =========================
        answer = None

        for model in MODELS:
            try:
                url = "https://openrouter.ai/api/v1/chat/completions"

                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 250
                }

                req_obj = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}"
                    }
                )

                with urllib.request.urlopen(req_obj, timeout=20) as res:
                    result = json.loads(res.read().decode("utf-8"))

                answer = result["choices"][0]["message"]["content"]
                break

            except Exception as e:
                print(f"Model failed {model}: {str(e)}")
                continue

        if answer is None:
            return send_response("AI временно недоступен.", [])

        # =========================
        # 🧠 сохраняем память
        # =========================
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": answer})

        if len(history) > MAX_HISTORY * 2:
            history = history[-MAX_HISTORY * 2:]

        CHAT_MEMORY[session]["history"] = history
        save_memory(CHAT_MEMORY)

        # очистка текста
        answer = answer.replace("*", "").replace("#", "").replace("`", "")

        if len(answer) > 800:
            answer = answer[:800] + "..."

        return send_response(answer, [])

    except Exception as e:
        print("ERROR:", str(e))
        return send_response("Ошибка сервера.", [])


def send_response(text, history):
    return jsonify({
        "version": "1.0",
        "response": {
            "text": text,
            "tts": text,
            "end_session": False
        },
        "session_state": {"history": history}
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
