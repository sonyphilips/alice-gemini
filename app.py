from flask import Flask, request, jsonify
import json
import os
import urllib.request
import urllib.error
import time
import threading

app = Flask(__name__)

# =========================
# 💾 ПАМЯТЬ
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

memory = load_memory()

MAX_HISTORY = 10

# =========================
# 🧠 РЕЖИМЫ
# =========================
MODES = {
    "friend": "Ты дружелюбный собеседник.",
    "assistant": "Ты умный ассистент, отвечай чётко.",
    "expert": "Ты эксперт, давай точные технические ответы."
}

DEFAULT_MODE = "assistant"

SYSTEM = "Ты AI ассистент внутри голосового помощника. Будь кратким."

# =========================
# ⚡ АНТИ-СПАМ
# =========================
LAST_TIME = 0
MIN_DELAY = 0.3

# =========================
# 🧠 СТАБИЛЬНЫЕ МОДЕЛИ
# =========================
MODELS = [
    "openai/gpt-3.5-turbo",
    "anthropic/claude-3-haiku",
    "mistralai/mistral-small"
]


@app.route("/", methods=["GET"])
def home():
    return "OK", 200


@app.route("/", methods=["POST"])
@app.route("/alice", methods=["POST"])
def handler():
    global LAST_TIME, memory

    try:
        body = request.get_json(force=True)

        req = body.get("request", {})
        session = body.get("session", {}).get("session_id", "default")

        user_text = req.get("command") or req.get("original_utterance", "")

        if not user_text:
            return send("Спроси меня что-нибудь.", [])

        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            return send("Нет API ключа.", [])

        # =========================
        # ⚡ задержка
        # =========================
        now = time.time()
        if now - LAST_TIME < MIN_DELAY:
            time.sleep(MIN_DELAY - (now - LAST_TIME))
        LAST_TIME = time.time()

        # =========================
        # 🧠 память
        # =========================
        if session not in memory:
            memory[session] = {
                "history": [],
                "mode": DEFAULT_MODE
            }

        mode = memory[session]["mode"]
        history = memory[session]["history"]

        system_prompt = SYSTEM + " " + MODES.get(mode, MODES["assistant"])

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})

        # =========================
        # 🌐 AI запрос
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
                print("MODEL FAIL:", model, str(e))
                continue

        if not answer:
            return send("AI временно недоступен.", [])

        # =========================
        # 💾 память сохраняем
        # =========================
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": answer})

        if len(history) > MAX_HISTORY * 2:
            history = history[-MAX_HISTORY * 2:]

        memory[session]["history"] = history
        save_memory(memory)

        # очистка
        answer = answer.replace("*", "").replace("#", "").replace("`", "")

        if len(answer) > 800:
            answer = answer[:800] + "..."

        return send(answer, [])

    except Exception as e:
        print("ERROR:", str(e))
        return send("Ошибка сервера.", [])


def send(text, history):
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
