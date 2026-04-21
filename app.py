from flask import Flask, request, jsonify
import json
import os
import urllib.request
import urllib.error
import time

app = Flask(__name__)

# анти-спам
LAST_REQUEST_TIME = 0
MIN_DELAY = 1.0  # секунды


@app.route("/", methods=["GET"])
def home():
    return "OK", 200


@app.route("/", methods=["POST"])
@app.route("/alice", methods=["POST"])
def handler():
    global LAST_REQUEST_TIME

    try:
        body = request.get_json(force=True)

        req_data = body.get("request", {})
        user_text = req_data.get("command") or req_data.get("original_utterance", "")

        if not user_text:
            return send_response("Привет! Спроси меня что-нибудь.", [])

        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            return send_response("Ошибка: нет API ключа OpenRouter.", [])

        # 🔹 анти-спам
        now = time.time()
        if now - LAST_REQUEST_TIME < MIN_DELAY:
            wait_time = MIN_DELAY - (now - LAST_REQUEST_TIME)
            print(f"Ждём {wait_time:.2f} сек (анти-спам)")
            time.sleep(wait_time)

        LAST_REQUEST_TIME = time.time()

        # 🔹 OpenRouter API
        url = "https://openrouter.ai/api/v1/chat/completions"

        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [
                {
                    "role": "user",
                    "content": user_text
                }
            ],
            "temperature": 0.7,
            "max_tokens": 300
        }

        data = json.dumps(payload).encode("utf-8")

        req_obj = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
        )

        result = None

        # 🔹 retry логика
        for attempt in range(3):
            try:
                print(f"Запрос к OpenRouter, попытка {attempt + 1}")

                with urllib.request.urlopen(req_obj, timeout=20) as res:
                    result = json.loads(res.read().decode("utf-8"))
                break

            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8", errors="ignore")
                print("=== OPENROUTER HTTP ERROR ===")
                print("Код:", e.code)
                print("Ответ:", error_body)

                if e.code == 429:
                    wait = 2 * (attempt + 1)
                    print(f"Лимит. Ждём {wait} сек...")
                    time.sleep(wait)
                else:
                    return send_response("Ошибка OpenRouter API.", [])

            except urllib.error.URLError as e:
                print("=== OPENROUTER URL ERROR ===")
                print(str(e))
                return send_response("Ошибка соединения с AI.", [])

            except Exception as e:
                print("=== OPENROUTER UNKNOWN ERROR ===")
                print(str(e))
                return send_response("Ошибка обработки AI.", [])

        if result is None:
            return send_response("Сервис перегружен. Попробуй позже.", [])

        # 🔹 извлечение ответа OpenRouter
        try:
            answer = result["choices"][0]["message"]["content"]
        except Exception:
            print("Нестандартный ответ OpenRouter:", result)
            return send_response("Не удалось получить ответ от AI.", [])

        # очистка текста
        answer = answer.replace("*", "").replace("#", "").replace("`", "")

        if len(answer) > 800:
            answer = answer[:800] + "..."

        return send_response(answer, [])

    except Exception as e:
        print("ОБЩАЯ ОШИБКА:", str(e))
        return send_response("Произошла ошибка. Попробуй ещё раз.", [])


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
