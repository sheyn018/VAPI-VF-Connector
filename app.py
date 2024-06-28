from flask import Flask, request, jsonify
import requests
import json

app = Flask(__name__)


@app.route('/')
def hello_world():
    return 'Hello, World!'


@app.route('/start', methods=['POST'])
def launch():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()

    # Navigate through the nested structure to get the question
    user_question = data.get("message", {}).get("functionCall",
                                                {}).get("parameters",
                                                        {}).get("name")

    if user_question is None:
        # Handle the case where "question" is not in the data dictionary
        print("The question key is not present in the data dictionary.")

    print(user_question)

    url = "https://general-runtime.voiceflow.com/state/user/userID/interact?logs=off"

    payload = {
        "action": {
            "type": "launch"
        },
        "config": {
            "tts": False,
            "stripSSML": True,
            "stopAll": True,
            "excludeTypes": ["block", "debug", "flow"]
        }
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": "VF.DM.667ebf23df7622f70a587cce.jWhy2PQfM3l7htto"
    }

    response = requests.post(url, json=payload, headers=headers)

    response_data = response.json()

    # Extracting messages from the response
    messages = []
    for item in response_data:
        if item['type'] == 'text':
            message = item['payload'].get('message')
            if message:
                messages.append(message)
            content = item['payload'].get('slate', {}).get('content', [])
            for content_item in content:
                for child in content_item.get('children', []):
                    text = child.get('text')
                    if text:
                        messages.append(text)

    print(messages)
    return jsonify({"result": messages})

@app.route('/query', methods=['POST'])
def api_call():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()

    # Navigate through the nested structure to get the question
    user_question = data.get("message", {}).get("functionCall", {}).get("parameters", {}).get("question")

    if user_question is None:
        # Handle the case where "question" is not in the data dictionary
        print("The question key is not present in the data dictionary.")
        return jsonify({"error": "Question not found in request"}), 400

    print('THIS IS SENT TO VF: ', user_question)

    url = "https://general-runtime.voiceflow.com/state/user/userID/interact?logs=off"

    payload = {
        "action": {
            "type": "text",
            "payload": user_question
        },
        "config": {
            "tts": False,
            "stripSSML": True,
            "stopAll": True,
            "excludeTypes": ["block", "debug", "flow"]
        }
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": "VF.DM.667ebf23df7622f70a587cce.jWhy2PQfM3l7htto"
    }

    response = requests.post(url, json=payload, headers=headers)

    response_json = json.loads(response.text)

    messages = []
    for item in response_json:
        if item['type'] == 'text':
            # Clean the message by removing '\n' and '**'
            cleaned_message = item['payload']['message'].replace('\n', ' ').replace('**', '')
            messages.append(cleaned_message)

    print('VF RETURNS THIS:', messages)

    return jsonify({"result": messages})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
