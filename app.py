from flask import Flask, request, jsonify 
import json
import os
import urllib.request
import urllib.error
import time

app = Flask(__name__)

# защита от спама (минимальный интервал между запросами)
LAST_REQUEST_TIME = 0
MIN_DELAY = 1.0  # секунды

@app.route("/", methods=["GET"])
def home():
    return "OK", 200


@app.route('/', methods=['POST'])
@app.route('/alice', methods=['POST'])
def handler():
    global LAST_REQUEST_TIME

    try:
        body = request.get_json(force=True)

        req = body.get('request', {})
        user_text = req.get('command') or req.get('original_utterance', '')

        if not user_text:
            return send_response("Привет! Спроси меня что-нибудь.", [])

        api_key = os.environ.get('GEMINI_API_KEY', '')
        if not api_key:
            return send_response("Ошибка: нет API ключа.", [])

        # 🔹 анти-спам (чтобы не ловить 429)
        now = time.time()
        if now - LAST_REQUEST_TIME < MIN_DELAY:
            wait_time = MIN_DELAY - (now - LAST_REQUEST_TIME)
            print(f"Ждём {wait_time:.2f} сек (анти-спам)")
            time.sleep(wait_time)

        LAST_REQUEST_TIME = time.time()

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

        payload = {
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "generationConfig": {
                "maxOutputTokens": 300,
                "temperature": 0.7
            }
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

        # 🔹 retry логика
        for attempt in range(3):
            try:
                print(f"Запрос к Gemini, попытка {attempt+1}")
                with urllib.request.urlopen(req, timeout=15) as res:
                    result = json.loads(res.read().decode("utf-8"))
                break

            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8", errors="ignore")
                print("=== GEMINI HTTP ERROR ===")
                print("Код:", e.code)
                print("Ответ:", error_body)

                if e.code == 429:
                    wait = 2 * (attempt + 1)
                    print(f"Лимит. Ждём {wait} сек...")
                    time.sleep(wait)
                else:
                    return send_response("Ошибка Gemini API.", [])

            except Exception as e:
                print("=== GEMINI UNKNOWN ERROR ===")
                print(str(e))
                return send_response("Ошибка соединения с AI.", [])

        else:
            return send_response("Сервис перегружен. Попробуй чуть позже.", [])

        # 🔹 обработка ответа
        try:
            answer = result["candidates"][0]["content"]["parts"][0]["text"]
        except:
            print("Нестандартный ответ Gemini:", result)
            return send_response("Не удалось получить ответ от AI.", [])

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
