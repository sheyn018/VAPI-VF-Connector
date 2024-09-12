import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import requests

app = Flask(__name__)

# Load environment variables
load_dotenv()

# Constants
VOICEFLOW_API_KEY = os.getenv("VOICEFLOW_API_KEY")
VOICEFLOW_URL = "https://general-runtime.voiceflow.com/state/user/{user_id}/interact?logs=off"

# API request headers
HEADERS = {
    "accept": "application/json",
    "content-type": "application/json",
    "Authorization": f"Bearer {VOICEFLOW_API_KEY}"  # API Key correctly included as a Bearer token
}

# Voiceflow request configuration
CONFIG = {
    "tts": False,
    "stripSSML": True,
    "stopAll": True,
    "excludeTypes": ["block", "debug", "flow"]
}

# Helper function to extract nested data from a dictionary
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

# Interact with the Voiceflow API
def interact_with_voiceflow(action_type, payload=None, user_id='default_user'):
    # Construct the request URL
    url = VOICEFLOW_URL.format(user_id=user_id)
    
    payload_data = {
        "action": {"type": action_type, "payload": payload},
        "config": CONFIG
    }

    response = requests.post(url, json=payload_data, headers=HEADERS)

    # Log errors if status code is >= 400
    if response.status_code >= 400:
        print(f"Error from Voiceflow API: {response.status_code} - {response.text}")

    response.raise_for_status()  # Raises an error for bad status codes
    return response.json()

# Process response data and extract text messages
def process_response(response_data):
    messages = set()
    for item in response_data:
        if item['type'] == 'text':
            messages.add(item['payload'].get('message', '').replace('\n', ' ').replace('**', ''))
            for content_item in item['payload'].get('slate', {}).get('content', []):
                for child in content_item.get('children', []):
                    text = child.get('text', '')
                    if text:
                        messages.add(text)
    return list(messages)

# Root endpoint with basic instructions
@app.route('/')
def index():
    return '/start for initiating booking process <br> /query for asking questions'

# Endpoint to initiate the booking process
@app.route('/start', methods=['POST'])
def launch():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()

    # Extract necessary data from the request
    tool_call_id = get_nested_data(data, ["message", "toolWithToolCallList", 0, "toolCall", "id"])
    user_question = get_nested_data(data, ["message", "toolWithToolCallList", 0, "toolCall", "function", "arguments", "query"])

    if user_question is None:
        return jsonify({"error": "Question not found in request"}), 400

    print('Starting Voiceflow interaction...')
    print('Start question:', user_question)

    # Make the API call to Voiceflow
    response_data = interact_with_voiceflow("launch")
    messages = process_response(response_data)

    print('Voiceflow response:', messages)

    return jsonify({"results": [{"toolCallId": tool_call_id, "result": messages}]})

# Endpoint for handling user queries
@app.route('/query', methods=['POST'])
def api_call():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()

    # Extract necessary data from the request
    tool_call_id = get_nested_data(data, ["message", "toolWithToolCallList", 0, "toolCall", "id"])
    user_question = get_nested_data(data, ["message", "toolWithToolCallList", 0, "toolCall", "function", "arguments", "query"])

    if user_question is None:
        return jsonify({"error": "Question not found in request"}), 400

    print('Query to Voiceflow:', user_question)

    # Make the API call to Voiceflow with the user query
    response_data = interact_with_voiceflow("text", user_question)
    messages = process_response(response_data)

    print('Voiceflow response:', messages)

    return jsonify({"results": [{"toolCallId": tool_call_id, "result": messages}]})

# Run the app in threaded mode to handle multiple requests concurrently
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, threaded=True)
