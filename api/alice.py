import json
import os
import urllib.request

def handler(request, response):
    try:
        body = json.loads(request.body)
        user_text = body.get('request', {}).get('command', '')

        if not user_text:
            user_text = body.get('request', {}).get('original_utterance', '')

        # Достаём историю разговора из session_state (память беседы)
        session_state = body.get('state', {}).get('session', {})
        history = session_state.get('history', [])

        if not user_text:
            return send_response(response, 'Привет! Я слушаю тебя. Спроси меня что-нибудь.', history)

        # Добавляем новый вопрос пользователя в историю
        history.append({
            "role": "user",
            "parts": [{"text": user_text}]
        })

        api_key = os.environ.get('GEMINI_API_KEY', '')
        url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}'

        payload = {
            "contents": history,
            "generationConfig": {
                "maxOutputTokens": 300,
                "temperature": 0.7
            }
        }

        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url, data=data,
            headers={'Content-Type': 'application/json'}
        )

        with urllib.request.urlopen(req, timeout=8) as res:
            result = json.loads(res.read().decode('utf-8'))

        answer = result['candidates'][0]['content']['parts'][0]['text']

        # Убираем markdown-символы чтобы Алиса читала чисто
        answer = answer.replace('**', '').replace('*', '').replace('#', '').replace('`', '')

        # Ограничиваем длину ответа для голосовой колонки
        if len(answer) > 800:
            answer = answer[:800] + '...'

        # Добавляем ответ Gemini в историю
        history.append({
            "role": "model",
            "parts": [{"text": answer}]
        })

        # Храним только последние 10 сообщений чтобы не переполнить память
        if len(history) > 10:
            history = history[-10:]

        return send_response(response, answer, history)

    except Exception as e:
        return send_response(response, 'Произошла ошибка. Попробуй ещё раз.', [])


def send_response(response, text, history):
    response.status_code = 200
    response.headers['Content-Type'] = 'application/json'
    response.body = json.dumps({
        "version": "1.0",
        "response": {
            "text": text,
            "tts": text,
            "end_session": False
        },
        "session_state": {
            "history": history
        }
    }, ensure_ascii=False)
    return response
