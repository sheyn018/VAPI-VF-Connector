from flask import Flask, request, jsonify
from dotenv import load_dotenv
import logging
import requests
import os

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

def get_nested_data(data: Any, keys: List[Any], default: Optional[Any] = None) -> Any:
    for key in keys:
        try:
            data = data[key]
        except (KeyError, IndexError, TypeError):
            return default
    return data

def interact_with_voiceflow(action_type: str, payload: Optional[Any] = None) -> Dict:
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
            slate_content = payload.get('slate', {}).get('content', [])
            for content_item in slate_content:
                for child in content_item.get('children', []):
                    text = child.get('text', '')
                    if text:
                        messages.add(text)
    return list(messages)

def handle_voiceflow_interaction(action_type: str, requires_question: bool = True):
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    tool_call_id = get_nested_data(data, ["message", "toolWithToolCallList", 0, "toolCall", "id"])
    user_question = get_nested_data(data, ["message", "toolWithToolCallList", 0, "toolCall", "function", "arguments", "query"])

    if requires_question and user_question is None:
        return jsonify({"error": "Question not found in request"}), 400

    if requires_question:
        logging.info('%s TO VF: %s', action_type.upper(), user_question)
        response_data = interact_with_voiceflow(action_type, user_question)
    else:
        logging.info('%s TO VF', action_type.upper())
        response_data = interact_with_voiceflow(action_type)

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
    app.run(host='0.0.0.0', port=8080, threaded=True)
