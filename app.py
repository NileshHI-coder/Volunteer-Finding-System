from dotenv import load_dotenv
import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai
import uuid
import json
import re

# ================= LOAD ENV =================
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key')
CORS(app)

# ================= FIREBASE =================
cred = credentials.Certificate({
    "type": "service_account",
    "project_id": os.getenv('FIREBASE_PROJECT_ID'),
    "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
    "private_key": os.getenv('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n'),
    "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
    "client_id": os.getenv('FIREBASE_CLIENT_ID'),
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": os.getenv('FIREBASE_CLIENT_X509_CERT_URL')
})

firebase_admin.initialize_app(cred)
db = firestore.client()

# ================= GEMINI =================
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel("models/gemini-2.5-flash")

# ================= HELPERS =================
def serialize(doc):
    data = doc.to_dict()

    # Fix timestamp issue
    if 'created_at' in data and data['created_at']:
        data['created_at'] = str(data['created_at'])

    if 'matched_at' in data and data.get('matched_at'):
        data['matched_at'] = str(data['matched_at'])

    return data

# ================= ROUTES =================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/request-help')
def request_help():
    return render_template('request-help.html')

@app.route('/volunteer-register')
def volunteer_register_page():
    return render_template('volunteer-register.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# ================= API =================

@app.route('/api/submit-request', methods=['POST'])
def submit_request():
    try:
        data = request.json
        request_id = str(uuid.uuid4())

        request_data = {
            'id': request_id,
            'name': data['name'],
            'location': data['location'],
            'type': data['type'],
            'description': data['description'],
            'urgency': data['urgency'],
            'status': 'pending',
            'created_at': firestore.SERVER_TIMESTAMP,
            'matched': False
        }

        db.collection('requests').document(request_id).set(request_data)

        return jsonify({'success': True, 'request_id': request_id}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/volunteer-register', methods=['POST'])
def volunteer_register():
    try:
        data = request.json
        volunteer_id = str(uuid.uuid4())

        volunteer_data = {
            'id': volunteer_id,
            'name': data['name'],
            'email': data['email'],
            'phone': data['phone'],
            'skills': data['skills'],
            'location': data['location'],
            'availability': data['availability'],
            'created_at': firestore.SERVER_TIMESTAMP
        }

        db.collection('volunteers').document(volunteer_id).set(volunteer_data)

        return jsonify({'success': True, 'volunteer_id': volunteer_id}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/match-volunteer', methods=['POST'])
def match_volunteer():
    try:
        data = request.json
        request_id = data.get('request_id')

        if not request_id:
            return jsonify({'error': 'request_id is required'}), 400

        # ================= GET REQUEST =================
        request_doc = db.collection('requests').document(request_id).get()

        if not request_doc.exists:
            return jsonify({'error': 'Request not found'}), 404

        request_data = request_doc.to_dict()

        # ================= GET VOLUNTEERS =================
        volunteers = db.collection('volunteers').stream()

        volunteer_list = []
        for vol in volunteers:
            vol_data = vol.to_dict()

            volunteer_list.append({
                "doc_id": vol.id,
                "name": vol_data.get("name", "Unknown"),
                "skills": vol_data.get("skills", ""),
                "location": vol_data.get("location", "")
            })

        if not volunteer_list:
            return jsonify({'matches': [], 'message': 'No volunteers available'}), 200

        # ================= AI PROMPT =================
        prompt = f"""
You are an AI volunteer matching system.

STRICT RULE:
Return ONLY valid JSON.
No markdown.
No explanation.
No extra text.

Format:
{{
    "matches": [
        {{
            "volunteer_id": "string",
            "name": "string",
            "reason": "string",
            "score": 0.0
        }}
    ]
}}

Request:
Type: {request_data.get('type', '')}
Description: {request_data.get('description', '')}
Location: {request_data.get('location', '')}
Urgency: {request_data.get('urgency', '')}

Volunteers:
{chr(10).join([f"{v['name']} | Skills:{v['skills']} | Location:{v['location']} | ID:{v['doc_id']}" for v in volunteer_list])}
"""

        # ================= GEMINI CALL =================
        try:
            response = model.generate_content(prompt)

            if not response or not response.text:
                raise Exception("Empty Gemini response")

            ai_text = response.text.strip()

            # Clean possible markdown
            ai_text = ai_text.replace("```json", "").replace("```", "").strip()

            print("🔥 GEMINI RAW OUTPUT:\n", ai_text)

        except Exception as e:
            print("🔥 GEMINI ERROR:", e)
            return jsonify({'error': 'Gemini API failed', 'details': str(e)}), 500

        # ================= SAFE JSON PARSE =================
        try:
            match = re.search(r"\{.*\}", ai_text, re.DOTALL)

            if match:
                parsed = json.loads(match.group())
                matches = parsed.get("matches", [])
            else:
                matches = []

        except Exception as e:
            print("⚠️ JSON PARSE ERROR:", e)
            matches = []

        # ================= SAVE MATCHES =================
        match_data = {
            "request_id": request_id,
            "matches": matches,
            "created_at": firestore.SERVER_TIMESTAMP,
            "status": "matched"
        }

        db.collection("matches").document(str(uuid.uuid4())).set(match_data)

        # ================= UPDATE REQUEST =================
        db.collection("requests").document(request_id).update({
            "status": "matched",
            "matched": True,
            "matched_at": firestore.SERVER_TIMESTAMP
        })

        return jsonify({"matches": matches}), 200

    except Exception as e:
        print("🔥 MATCH VOLUNTEER ERROR:", e)
        return jsonify({"error": str(e)}), 500

@app.route('/api/volunteers')
def get_volunteers():
    try:
        docs = db.collection('volunteers') \
            .order_by('created_at', direction=firestore.Query.DESCENDING) \
            .limit(10).stream()

        return jsonify([serialize(doc) for doc in docs])

    except Exception as e:
        print("ERROR Volunteers:", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/requests')
def get_requests():
    try:
        docs = db.collection('requests') \
            .order_by('created_at', direction=firestore.Query.DESCENDING) \
            .limit(10).stream()

        return jsonify([serialize(doc) for doc in docs])

    except Exception as e:
        print("ERROR Requests:", e)
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/matches')
def get_matches():
    try:
        docs = db.collection('matches') \
            .order_by('created_at', direction=firestore.Query.DESCENDING) \
            .limit(10).stream()

        return jsonify([serialize(doc) for doc in docs])

    except Exception as e:
        print("ERROR Matches:", e)
        return jsonify({'error': str(e)}), 500


# ================= RUN =================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)