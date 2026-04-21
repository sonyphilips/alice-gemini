from flask import Flask, request, jsonify
import json
import os
import urllib.request

app = Flask(__name__)

@app.route('/alice', methods=['POST'])
@app.route('/', methods=['POST'])   # Добавили обработку корневого пути
def handler():
    try:
        body = request.get_json(force=True)

        user_text = body.get('request', {}).get('command', '') or \
                    body.get('request', {}).get('original_utterance', '')

        session_state = body.get('state', {}).get('session', {})
        history = session_state.get('history', [])

        if not user_text:
            return send_response('Привет! Я слушаю тебя. Спроси меня что-нибудь.', history)

        history.append({"role": "user", "parts": [{"text": user_text}]})

        api_key = os.environ.get('GEMINI_API_KEY', '')
        if not api_key:
            return send_response('Ошибка: ключ Gemini не найден.', history)

        url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}'

        payload = {
            "contents": history,
            "generationConfig": {"maxOutputTokens": 400, "temperature": 0.7}
        }

        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

        with urllib.request.urlopen(req, timeout=12) as res:
            result = json.loads(res.read().decode('utf-8'))

        answer = result['candidates'][0]['content']['parts'][0]['text']

        answer = answer.replace('**', '').replace('*', '').replace('#', '').replace('`', '')

        if len(answer) > 800:
            answer = answer[:800] + '...'

        history.append({"role": "model", "parts": [{"text": answer}]})

        if len(history) > 10:
            history = history[-10:]

        return send_response(answer, history)

    except Exception as e:
        print("Ошибка:", str(e))
        return send_response('Произошла ошибка. Попробуй ещё раз.', [])

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
