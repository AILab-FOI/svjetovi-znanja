#!/usr/bin/env python3
import os
import openai
import hashlib
import hmac
from rethinkdb import RethinkDB; r = RethinkDB()

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
    return serve_static( 'teacher_login.html' )

# ----------------------------------------------------------------
# File upload
#    
# ----------------------------------------------------------------

# Folder to save uploaded files
UPLOAD_FOLDER = 'lecture_materials'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/folder-structure', methods=['GET'])
def get_folder_structure():
    username = request.args.get('username')
    if not username:
        return jsonify(success=False, message='Username is required'), 400

    user_folder = os.path.join(UPLOAD_FOLDER, username)
    if not os.path.exists(user_folder):
        return jsonify(success=False, message='User folder does not exist'), 404

    files = []
    for root, dirs, filenames in os.walk(user_folder):
        for filename in filenames:
            files.append(os.path.relpath(os.path.join(root, filename), user_folder))

    return jsonify(success=True, files=files), 200

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify(success=False, message='No file part'), 400

    file = request.files['file']
    username = request.form.get('username')
    folder = request.form.get('folder')

    if file.filename == '':
        return jsonify(success=False, message='No selected file'), 400

    if file and username and folder:
        # Create user folder if it doesn't exist
        user_folder = os.path.join(UPLOAD_FOLDER, username)
        os.makedirs(user_folder, exist_ok=True)

        # Create subfolder based on dropdown selection
        subfolder = os.path.join(user_folder, folder)
        os.makedirs(subfolder, exist_ok=True)

        # Save the file
        file.save(os.path.join(subfolder, file.filename))
        return jsonify(success=True, message='File uploaded successfully'), 200
    else:
        return jsonify(success=False, message='Invalid request'), 400

@app.route('/delete-file', methods=['POST'])
def delete_file():
    data = request.json
    username = data.get('username')
    filename = data.get('filename')

    if not username or not filename:
        return jsonify(success=False, message='Username and filename are required'), 400

    file_path = os.path.join(UPLOAD_FOLDER, username, filename)
    if not os.path.exists(file_path):
        return jsonify(success=False, message='File does not exist'), 404

    os.remove(file_path)
    return jsonify(success=True, message='File deleted successfully'), 200
    
# ----------------------------------------------------------------
# Insert teacher
#    
# ----------------------------------------------------------------

# RethinkDB connection
conn = r.connect(host='localhost', port=28015, db='mmorpg')

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    permission = data.get('permission')

    if not username or not password:
        return jsonify(success=False, message='Username and password are required'), 400

    # Check if the username already exists
    existing_user = r.table('users').filter({'username': username}).run(conn)
    if list(existing_user):
        return jsonify(success=False, message='Username already exists'), 400

    # Insert the new user into the database
    r.table('users').insert({
        'username': username,
        'password': password,  # Password is already hashed on the frontend
        'permission': permission,
    }).run(conn)

    # Create folder structure for the user
    base_folder = os.path.join('lecture_materials')
    os.makedirs(base_folder, exist_ok=True)  # Create base folder if it doesn't exist
    user_folder = os.path.join(base_folder, username)
    os.makedirs(user_folder, exist_ok=True)  # Create user folder

    # Create subfolders
    subfolders = ['Naesala', 'Haryk', 'Ayred', 'Hagmar']
    for subfolder in subfolders:
        os.makedirs(os.path.join(user_folder, subfolder), exist_ok=True)

    return jsonify(success=True, message='Registration successful'), 200


# ----------------------------------------------------------------
# Login check
#    
# ----------------------------------------------------------------

# RethinkDB connection
conn = r.connect(host='localhost', port=28015, db='mmorpg')

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify(success=False, message='Username and password are required'), 400

    # Check if the username and password match
    user = r.table('users').filter({'username': username, 'password': password}).run(conn)
    user = list(user)

    if not user:
        return jsonify(success=False, message='Invalid credentials'), 400

    # Return the user's permission level
    return jsonify(success=True, permission=user[0]['permission']), 200


# ----------------------------------------------------------------
# Insert student
#    
# ----------------------------------------------------------------

# RethinkDB connection
conn = r.connect(host='localhost', port=28015, db='mmorpg')

@app.route('/regucenik', methods=['POST'])
def regucenik():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify(success=False, message='Username and password are required'), 400

    # Check if the username already exists
    existing_user = r.table('users').filter({'username': username}).run(conn)
    if list(existing_user):
        return jsonify(success=False, message='Username already exists'), 400

    # Insert the new user into the database
    r.table('users').insert({
        'username': username,
        'password': password,  # Password is already hashed on the frontend
        'permission': 0,
        'mapId': 1,
        'skin': {
            'battlerName': 'Actor1_1',
            'characterIndex': 0,
            'characterName': 'Actor1',
            'faceIndex': 0,
            'faceName': 'Actor1',
        },
        'x': 5,
        'y': 5,
        'isBusy': False,
        'stats': {
            'armors' : { },
            'classId': 1,
            'equips': [1, 1, 2, 3, 0],
            'exp': {"1": 0},
            'gold': 0,
            'hp': 450,
            'items': { },
            'level': 1,
            'mp': 90,
            'skills': [8, 10],
            'weapons': { }
        },
    }).run(conn)

    return jsonify(success=True, message='Registration successful'), 200

# ----------------------------------------------------------------
# Run the server
# ----------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

