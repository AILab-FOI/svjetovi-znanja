import os
import openai

from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)

# ----------------------------------------------------------------
# Configure OpenAI (for openai>=1.0.0)
# ----------------------------------------------------------------
openai.api_key = os.environ.get("OPENAI_API_KEY")
# If you prefer to hardcode your key (not recommended):
# openai.api_key = "sk-xxxx..."

# ----------------------------------------------------------------
# In-memory store of conversations
#    Key: (username, agentName)
#    Value: [ {"role":"system","content": ...}, {"role":"user","content": ...}, ... ]
# ----------------------------------------------------------------
conversations = {}

# ----------------------------------------------------------------
# Create a new agent (POST)
#    Endpoint: /new/<username>/<agent_name>
#    JSON Body: { "content": <systemPrompt> }
# ----------------------------------------------------------------
@app.route("/new/<path:username>/<path:agent_name>", methods=["POST"])
def create_agent(username, agent_name):
    try:
        # Extract the system prompt from JSON
        data = request.get_json(force=True)
        system_prompt = data.get("content", "")

        # Initialize conversation with a system message
        conversations[(username, agent_name)] = [
            {"role": "system", "content": system_prompt}
        ]

        return jsonify({
            "status": "success",
            "message": f"Agent '{agent_name}' created for user '{username}'."
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ----------------------------------------------------------------
# Query (ask) an existing agent (POST)
#    Endpoint: /query/<username>/<agent_name>
#    JSON Body: { "prompt": <userPrompt> }
# ----------------------------------------------------------------
@app.route("/query/<path:username>/<path:agent_name>", methods=["POST"])
def query_agent(username, agent_name):
    key = (username, agent_name)
    if key not in conversations:
        return jsonify({
            "status": "error",
            "response": f"No such agent '{agent_name}' for user '{username}'."
        }), 404

    try:
        data = request.get_json(force=True)
        user_prompt = data.get("prompt", "")

        messages = conversations[key]
        # Append user message
        messages.append({"role": "user", "content": user_prompt})

        # Call OpenAI ChatCompletion
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        assistant_reply = response.choices[0].message.content

        # Append the assistant’s reply
        messages.append({"role": "assistant", "content": assistant_reply})

        return jsonify({
            "status": "success",
            "response": assistant_reply
        })
    except Exception as e:
        return jsonify({"status": "error", "response": str(e)}), 500

# ----------------------------------------------------------------
# Delete an agent (POST)
#    Endpoint: /delete/<username>/<agent_name>
#    JSON Body: (not strictly required)
# ----------------------------------------------------------------
@app.route("/delete/<path:username>/<path:agent_name>", methods=["POST"])
def delete_agent(username, agent_name):
    key = (username, agent_name)
    if key not in conversations:
        return jsonify({
            "status": "error",
            "message": f"No such agent '{agent_name}' for user '{username}'."
        }), 404

    del conversations[key]
    return jsonify({
        "status": "success",
        "message": f"Deleted agent '{agent_name}' for user '{username}'."
    })

# ----------------------------------------------------------------
# Serve static files
#    
# ----------------------------------------------------------------
@app.route('/<path:filename>', methods=['GET'])
def serve_static(filename):
    # Prevent access to the server directory
    if filename.startswith('server/'):
        return jsonify({"status": "error", "message": "Access denied."}), 403

    # Serve the file if it exists
    file_path = os.path.join('..', filename)
    if os.path.isfile(file_path):
        directory = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        return send_from_directory(directory, file_name)
    else:
        return jsonify({"status": "error", "message": "File not found."}), 404


@app.route('/', methods=['GET'])
def serve_index():
    return serve_static( 'index.html' )

# ----------------------------------------------------------------
# Run the server
# ----------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

