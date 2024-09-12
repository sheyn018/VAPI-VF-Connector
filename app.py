from flask import Flask, request, jsonify
from dotenv import load_dotenv
import requests
import os

app = Flask(__name__)
load_dotenv()

VOICEFLOW_URL = "https://general-runtime.voiceflow.com/state/user/userID/interact?logs=off"
VOICEFLOW_API_KEY = os.getenv("VOICEFLOW_API_KEY")

HEADERS = {
    "accept": "application/json",
    "content-type": "application/json",
    "Authorization": "{VOICEFLOW_API_KEY}"
}
CONFIG = {
    "tts": False,
    "stripSSML": True,
    "stopAll": True,
    "excludeTypes": ["block", "debug", "flow"]
}

def get_nested_data(data, keys, default=None):
    for key in keys:
        try:
            if isinstance(data, list):
                data = data[key] if key < len(data) else default
            else:
                data = data.get(key, default)
        except (AttributeError, IndexError, TypeError):
            return default
        if data is default:
            break
    return data

def interact_with_voiceflow(action_type, payload=None):
    payload = {
        "action": {"type": action_type, "payload": payload},
        "config": CONFIG
    }
    response = requests.post(VOICEFLOW_URL, json=payload, headers=HEADERS)
    response.raise_for_status()  # Will raise an error for bad status codes
    return response.json()

def process_response(response_data):
    messages = set()  # Use a set to avoid duplicate messages
    for item in response_data:
        if item['type'] == 'text':
            messages.add(item['payload'].get('message', '').replace('\n', ' ').replace('**', ''))
            for content_item in item['payload'].get('slate', {}).get('content', []):
                for child in content_item.get('children', []):
                    text = child.get('text', '')
                    if text:
                        messages.add(text)
    return list(messages)  # Convert the set back to a list

@app.route('/')
def hello_world():
    return 'Hello, World!'

@app.route('/start', methods=['POST'])
def launch():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    tool_call_id = get_nested_data(data, ["message", "toolWithToolCallList", 0, "toolCall", "id"])
    user_question = get_nested_data(data, ["message", "toolWithToolCallList", 0, "toolCall", "function", "arguments", "query"])

    if user_question is None:
        return jsonify({"error": "Question not found in request"}), 400

    print('STARTING VF...')
    print('START QUESTION:', user_question)

    response_data = interact_with_voiceflow("launch")
    messages = process_response(response_data)

    print('START VF RESPONSE:', messages)

    return jsonify({"results": [{"toolCallId": tool_call_id, "result": messages}]})

@app.route('/query', methods=['POST'])
def api_call():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    tool_call_id = get_nested_data(data, ["message", "toolWithToolCallList", 0, "toolCall", "id"])
    user_question = get_nested_data(data, ["message", "toolWithToolCallList", 0, "toolCall", "function", "arguments", "query"])

    if user_question is None:
        return jsonify({"error": "Question not found in request"}), 400

    print('QUERY TO VF: ', user_question)

    response_data = interact_with_voiceflow("text", user_question)
    messages = process_response(response_data)

    print('QUERY VF RESPONSE:', messages)

    return jsonify({"results": [{"toolCallId": tool_call_id, "result": messages}]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, threaded=True)
