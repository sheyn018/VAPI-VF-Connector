from typing import Dict, List, Optional
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import logging
import requests
import os
import functools

app = Flask(__name__)
load_dotenv()

VOICEFLOW_URL = "https://general-runtime.voiceflow.com/state/user/userID/interact?logs=off"
VOICEFLOW_API_KEY = os.getenv("VOICEFLOW_API_KEY")

HEADERS = {
    "accept": "application/json",
    "content-type": "application/json",
    "Authorization": VOICEFLOW_API_KEY
}

CONFIG = {
    "tts": False,
    "stripSSML": True,
    "stopAll": True,
    "excludeTypes": ["block", "debug", "flow"]
}

# Setup logging
logging.basicConfig(level=logging.INFO)

# Use lru_cache to memoize the function
@functools.lru_cache(maxsize=None)
def get_nested_data(data: any, keys: List[any], default: Optional[any] = None) -> any:
    for key in keys:
        try:
            data = data[key]
        except (KeyError, IndexError, TypeError):
            return default
    return data

def interact_with_voiceflow(action_type: str, payload: Optional[any] = None) -> Dict:
    request_payload = {
        "action": {"type": action_type, "payload": payload},
        "config": CONFIG
    }
    response = requests.post(VOICEFLOW_URL, json=request_payload, headers=HEADERS)
    response.raise_for_status()
    try:
        return response.json()
    except ValueError:
        raise Exception("Invalid JSON response from Voiceflow")

def process_response(response_data: List[Dict]) -> List[str]:
    messages = set()
    for item in response_data:
        if item.get('type') == 'text':
            payload = item.get('payload', {})
            message = payload.get('message', '').replace('\n', ' ').replace('**', '')
            if message:
                messages.add(message)
            for content_item in payload.get('slate', {}).get('content', []):
                messages.update(child.get('text', '') for child in content_item.get('children', []) if child.get('text'))
    return list(messages)

def handle_voiceflow_interaction(action_type: str, requires_question: bool = True):
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    tool_call_id = get_nested_data(data, ["message", "toolWithToolCallList", 0, "toolCall", "id"])
    user_question = get_nested_data(data, ["message", "toolWithToolCallList", 0, "toolCall", "function", "arguments", "query"])

    if requires_question and user_question is None:
        return jsonify({"error": "Question not found in request"}), 400

    logging.info('%s TO VF: %s', action_type.upper(), user_question if requires_question else '')
    response_data = interact_with_voiceflow(action_type, user_question if requires_question else None)

    messages = process_response(response_data)
    logging.info('%s VF RESPONSE: %s', action_type.upper(), messages)

    return jsonify({"results": [{"toolCallId": tool_call_id, "result": messages}]})

@app.route('/')
def index():
    return '/start for initiating booking process <br> /query for asking questions'

@app.route('/start', methods=['POST'])
def launch():
    return handle_voiceflow_interaction('launch', requires_question=False)

@app.route('/query', methods=['POST'])
def api_call():
    return handle_voiceflow_interaction('text')

@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
