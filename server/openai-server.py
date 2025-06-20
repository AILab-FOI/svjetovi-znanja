#!/usr/bin/env python3
import os
import openai
import hashlib
import hmac
import numpy as np
import faiss
import fitz
import logging
from rethinkdb import RethinkDB
from collections import defaultdict
from flask import Flask, jsonify, request, send_from_directory
from docx import Document
from io import BytesIO
import tempfile
import textract

app = Flask(__name__)

logging.basicConfig(filename="errors.log", level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")

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

# Data to connect to the local RethinkDB
r = RethinkDB()
db_host = "localhost"
db_port = 28015
db_embedding_table = "embeddings"
db_name = "mmorpg"

# Document store 
dimension = 1536
agent_document_indexes = defaultdict(lambda: faiss.IndexHNSWFlat(dimension, 32))
agent_doc_map = defaultdict(list)

# RethinkDB connection
conn = r.connect(host=db_host, port=db_port, db=db_name)

# Folder to save uploaded files
UPLOAD_FOLDER = 'lecture_materials'

def find_embedding_for_scientist(teacher, scientist):
    record = list(r.table(db_embedding_table).filter({
        "teacher": teacher,
        "scientist": scientist
    }).run(conn))
    
    if record:
        return np.array(record[0]['embedding'], dtype=np.float32)
    return None

def load_embeddings_from_database():
    documents = list(r.table(db_embedding_table).run(conn))
    total_embeddings = 0

    for doc in documents:
        teacher = doc.get("teacher")
        agent_name = doc.get("agent_name")
        embedding = doc.get("embedding")
        doc_id = doc.get("id")

        if not all([teacher, agent_name, embedding, doc_id]):
            continue

        index_key = (teacher, agent_name)

        if index_key not in agent_document_indexes:
            agent_document_indexes[index_key] = faiss.IndexHNSWFlat(dimension, 32)

        agent_document_indexes[index_key].add(np.array([embedding], dtype=np.float32))
        agent_doc_map[index_key].append(doc_id)
        total_embeddings += 1

    print(f"Loaded {total_embeddings} document embeddings into FAISS.")


def get_embedding(text: str):
    try:
        response = openai.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )

        return response.data[0].embedding 
    except Exception as e:
        print(f"Error while retrieving embeddings: {e}")

    return None

def store_document(text, teacher, agent_name):
    embedding = get_embedding(text)
    
    if embedding:
        insert_result = r.table(db_embedding_table).insert({
            "teacher": teacher,
            "agent_name": agent_name,
            "text": text,
            "embedding": embedding
        }).run(conn)

        doc_id = insert_result.get("generated_keys", [None])[0]

        if doc_id:
            index_key = (teacher, agent_name)
            agent_document_indexes[index_key].add(np.array([embedding], dtype=np.float32))
            agent_doc_map[index_key].append(doc_id)
            load_embeddings_from_database()
            return True

    return False


def setup_database():
    try:
        if db_name not in r.db_list().run(conn):
            r.db_create(db_name).run(conn)
            print(f"Created database: {db_name}")

        conn.use(db_name)
        if db_embedding_table not in r.table_list().run(conn):
            r.table_create(db_embedding_table).run(conn)
            print(f"Created table: {db_embedding_table}")

    except Exception as e:
        print(f"Error setting up RethinkDB: {e}")

def handle_pdf(file):
    file_stream = BytesIO(file.read())
    doc = fitz.open(stream=file_stream, filetype="pdf")
    full_text = "\n".join([page.get_text("text") for page in doc])
    return full_text

def handle_doc(file_path):
    try:
        extracted_text = textract.process(file_path).decode("utf-8")
    except Exception as e:
        extracted_text = f"Error extracting text: {str(e)}"
    return extracted_text

    
def handle_docx(file_path):
    doc = Document(file_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    return text

def handle_text(file):
    return file.read()
    
# ----------------------------------------------------------------
# Create a new agent (POST)
#    Endpoint: /new/<username>/<agent_name>
#    JSON Body: { "content": <systemPrompt> }
# ----------------------------------------------------------------
@app.route("/new/<path:teacher>/<path:username>/<path:agent_name>", methods=["POST"])
def create_agent(teacher, username, agent_name):
    try:
        # Extract the system prompt from JSON
        data = request.get_json(force=True)
        system_prompt = data.get("content", "")

        # TODO: added teacher here in key bellow, now integrate with the rest
        # Initialize conversation with a system message
        conversations[(teacher, username, agent_name)] = [
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
    try:
        # 1. Look up the student's teacher
        user_record = list(r.table("users").filter({"username": username}).run(conn))
        if not user_record:
            return jsonify({"status": "error", "response": "Student user not found."}), 404

        teacher = user_record[0].get("teacher")
        if not teacher:
            return jsonify({"status": "error", "response": "Teacher not assigned to student."}), 400

        # 2. Retrieve the student's question
        data = request.get_json(force=True)
        user_prompt = data.get("prompt", "").strip()
        if not user_prompt:
            return jsonify({"status": "error", "response": "Prompt is required."}), 400

        # 3. Get the embedding of the user prompt
        query_embedding = get_embedding(user_prompt)
        if query_embedding is None:
            return jsonify({"status": "error", "response": "Failed to get embedding."}), 500

        # 4. Retrieve relevant document chunks for this (teacher, agent)
        index_key = (teacher, agent_name)
        if index_key not in agent_document_indexes:
            return jsonify({"status": "error", "response": "No documents found for this agent."}), 404
            
        

        faiss_index = agent_document_indexes[index_key]
        doc_ids = agent_doc_map[index_key]

        k = 5  # top-k chunks to use
        D, I = faiss_index.search(np.array([query_embedding], dtype=np.float32), k)
        
        
        # Retrieve corresponding document texts from DB
        context_chunks = []
        for idx in I[0]:
            if 0 <= idx < len(doc_ids):
                doc_id = doc_ids[idx]
                record = r.table(db_embedding_table).get(doc_id).run(conn)
                if record:
                    context_chunks.append(record["text"])

        if not context_chunks:
            return jsonify({"status": "error", "response": "No relevant document chunks found."}), 404

        context = "\n\n".join(context_chunks)

        # 5. Build or retrieve conversation state
        conv_key = (teacher, username, agent_name)
        if conv_key not in conversations:
            conversations[conv_key] = []

        messages = conversations[conv_key]

        # Append current user question
        messages.append({"role": "user", "content": user_prompt})

        # 6. Call OpenAI with context and question
        system_instruction = (
            "Odgovori na pitanje koristeći sljedeći kontekst iz dokumenata "
            f"koje je učitelj '{teacher}' priložio za agenta '{agent_name}'. "
            "Ako pitanje nije vezan uz kontekst, reci da ne znaš, a ako je "
            "pitanje vezano uz kontekst, možeš ponuditi i odgovor temeljem drugih znanja."
            "Ako te učenik pita što znaš ili o čemu znaš najviše daj kratki "
            "sažetak konteksta na način da kažeš da je zadnji svitak koji si"
            "proučio je [tema koja je opisana u kontekstu] jer ti si lik znanstvenika "
            "u fantasy RPG igri. Nemoj spominjati riječ kontekst, nego samo govori "
            "o svitku kao da je on opisao sve što je u kontekstu."
        )

        prompt_with_context = (
            f"{system_instruction}\n\n"
            f"Kontekst:\n{context}\n\n"
            f"Pitanje: {user_prompt}\n\nOdgovor:"
        )
        
        print( prompt_with_context )

        response = openai.chat.completions.create(
            model="gpt-4o-mini",  # You can adjust the model
            messages=[{"role": "user", "content": prompt_with_context}]
        )

        assistant_reply = response.choices[0].message.content
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

    files = {}
    for root, dirs, filenames in os.walk(user_folder):
        for filename in filenames:
            if 'Naesala' in root:
                scientist = 'Naesala'
            elif 'Haryk' in root:
                scientist = 'Haryk'
            elif 'Ayred' in root:
                scientist = 'Ayred'
            elif 'Hagmar' in root:
                scientist = 'Hagmar'
                
            if scientist not in files:
                files[ scientist ] = []
            
            files[ scientist ].append( filename )

    return jsonify(success=True, files=files), 200

@app.route('/upload', methods=['POST'])
def upload_file():
    def combine_scientist_documents(username, scientist):
        folder_path = os.path.join(UPLOAD_FOLDER, username, scientist)
        full_text = ""
        
        for filename in os.listdir(folder_path):
            filepath = os.path.join(folder_path, filename)
            if filename.endswith(".pdf"):
                with open(filepath, 'rb') as f:
                    full_text += handle_pdf(f) + "\n"
            elif filename.endswith(".doc") or filename.endswith(".docx"):
                if filename.endswith(".docx"):
                    full_text += handle_docx(filepath) + "\n"
                else:
                    with open(filepath, 'rb') as f:
                        full_text += handle_doc(f) + "\n"
            elif filename.endswith(".txt"):
                with open(filepath, 'r', encoding='utf-8') as f:
                    full_text += f.read() + "\n"
            else:
                continue
        
        return full_text.strip()

    if 'file' not in request.files:
        return jsonify(success=False, message='No file part'), 400

    file = request.files['file']
    username = request.form.get('username')
    scientist = request.form.get('scientist')

    if file.filename == '':
        return jsonify(success=False, message='No selected file'), 400

    if file and username and scientist:
        # Create user folder if it doesn't exist
        user_folder = os.path.join(UPLOAD_FOLDER, username)
        os.makedirs(user_folder, exist_ok=True)

        # Create subfolder based on dropdown selection
        subfolder = os.path.join(user_folder, scientist)
        os.makedirs(subfolder, exist_ok=True)

        # Save the file
        file.save(os.path.join(subfolder, file.filename))

        full_text = combine_scientist_documents(username, scientist)
        
        #print( "FULL TEXT:", full_text )

        result = store_document(full_text, username, scientist)

        if result:
            
        

            embedding = get_embedding(full_text)

            if embedding:
                # Delete old embedding
                r.table(db_embedding_table).filter({
                    "teacher": username,
                    "scientist": scientist
                }).delete().run(conn)

                # Insert new one
                r.table(db_embedding_table).insert({
                    "teacher": username,
                    "scientist": scientist,
                    "embedding": embedding
                }).run(conn)
            else:
                return jsonify(success=False, message='Error while fetching embedding'), 400

            return jsonify(success=True, message='File uploaded successfully'), 200
        else:
            os.remove(os.path.join(subfolder, file.filename))
            return jsonify(success=False, message='Error while uploading document. Probably the document is to big. Try a smaller one.'), 400
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

@app.route('/regucenik', methods=['POST'])
def regucenik():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    teacher = data.get('teacher')
    
    if not username or not password:
        return jsonify(success=False, message='Obavezno unesi korisničko ime i lozinku!'), 400

    # Check if the username already exists
    existing_user = r.table('users').filter({'username': username}).run(conn)
    if list(existing_user):
        return jsonify(success=False, message='Korisničko ime već postoji!'), 400

    # Insert the new user into the database
    r.table('users').insert({
        'username': username,
        'password': password,  # Password is already hashed on the frontend
        'teacher': teacher,
        'permission': 0,
        'mapId': 1,
        'skin': {
            'battlerName': 'Actor1_1',
            'characterIndex': 0,
            'characterName': 'Actor1',
            'faceIndex': 0,
            'faceName': 'Actor1',
        },
        'x': 7,
        'y': 6,
        'isBusy': False,
        'stats': {
            'armors' : { },
            'classId': 1,
            'equips': [0, 0, 0, 0, 0],
            'exp': {"1": 0},
            'gold': 0,
            'hp': 1,
            'items': { },
            'level': 1,
            'mp': 1,
            'skills': [],
            'weapons': { }
        },
    }).run(conn)

    return jsonify(success=True, message='Registration successful'), 200

# ----------------------------------------------------------------
# Run the server
# ----------------------------------------------------------------
if __name__ == "__main__":
    setup_database()
    load_embeddings_from_database()
    app.run(debug=True, host="0.0.0.0", port=5000)

