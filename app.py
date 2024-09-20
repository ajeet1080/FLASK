from flask import Flask, request, jsonify, send_from_directory
# from flask_marshmallow import Marshmallow
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
import openai
from cryptography.hazmat.primitives.serialization import pkcs12
import json
from azure.cosmos import CosmosClient, PartitionKey
import uuid
import os
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
#from promptflow.core import AzureOpenAIModelConfiguration
#from promptflow.client import load_flow
#from promptflow.evals.evaluators import RelevanceEvaluator, GroundednessEvaluator, CoherenceEvaluator
import pymongo
import pytz
import time
from datetime import datetime, timedelta
import base64
import os

# test
app = Flask(__name__)

# Initialize the database with the app instance


CORS(app)
app.app_context().push()

# Azure Text Analytics setup
key = "603cdb17c06845adbebf09158a7ef2ab"
endpoint = "https://text-analytics-demo1.cognitiveservices.azure.com/"
text_analytics_client = TextAnalyticsClient(endpoint=endpoint, credential=AzureKeyCredential(key))

openai.api_type = "azure"
openai.api_version = "2023-05-15"
# Your Azure OpenAI resource's endpoint value.
openai.api_base = "https://shplayground2.openai.azure.com/"
openai.api_key = "fefc20d1c3ee4046b446c239f96e4fc4"

COSMOS_CONNECTION_STRING = "mongodb://notebuddy-02:wQvnE4bXrOsplHFVryyeN6MRDwhNhISn7lG5R6jmaKBIYaxEebzgO5AT0FOvch4HlOp6cXYl9MBWACDbJPcHlA==@notebuddy-02.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000&appName=@notebuddy-02@"
client = pymongo.MongoClient(COSMOS_CONNECTION_STRING)

TEXT_ANALYTICS_ENDPOINT = "https://text-analytics-demo1.cognitiveservices.azure.com/"
TEXT_ANALYTICS_API_KEY = "603cdb17c06845adbebf09158a7ef2ab"

azure_credential = AzureKeyCredential(TEXT_ANALYTICS_API_KEY)
text_analytics_client = TextAnalyticsClient(endpoint=TEXT_ANALYTICS_ENDPOINT, credential=azure_credential)


@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)


# Create route to upload file
UPLOAD_FOLDER = 'uploads'


@app.route('/uploads/<path:filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


# Add code snippet to include Swagger docs route for API
SWAGGER_URL = '/api/docs'  # URL for exposing Swagger UI (without trailing '/')
# Our API url (can of course be a local resource)
API_URL = '/static/swagger.json'

# Call factory function to create our blueprint
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "SingHealth Medical Report Generator"
    }
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)


API_KEYS = {
    "client1": "api_key_1",
    "client2": "sgsgenaiapikey123098",
    # Add more clients and API keys as needed
}


# SaveRoute

@app.route('/getMaxCode', methods=['GET'])
def retrieve_highest_code():
    pipeline = [
        {
            '$project': {
                'code': {'$toInt': '$code'}  # Cast code to integer
            }
        },
        {
            '$group': {
                '_id': None,
                'code': {'$max': '$code'}
            }
        }
    ]

    try:
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy"]
        result = list(collection.aggregate(pipeline))
        if result:
            return jsonify({"code": result[0]['code']})
        else:
            return jsonify({"code":0})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/save', methods=['POST'])
# @validate_hmac
# @validate_client_cert
def save_to_mongodb(*args, **kwargs):
    data = request.json
    # summary = data.get('summary')
    # transcript = data.get('transcript')
    # user_id = request.headers['userId']
    item = data['item']

    try:
        new_id = str(uuid.uuid4())

        # Decode
        decoded_transcript = base64.b64decode(item['transcript']).decode('utf-8')
        decoded_summary = base64.b64decode(item['summary']).decode('utf-8')
        decoded_formattedtranscript = base64.b64decode(item['formattedtranscript']).decode('utf-8')
        decoded_prompt = base64.b64decode(item['prompt']).decode('utf-8')
        decoded_prompt_title = base64.b64decode(item['promptTitle']).decode('utf-8')

        # Save the data
        # 29072024 - Updated below to include more fields.
        document = {
            "id": new_id,
            "user": item['user'],
            "patientID": item['patientID'],
            "dataCategory": item['dataCategory'],
            "summary": decoded_summary,
            "transcript": decoded_transcript,
            "formattedtranscript": decoded_formattedtranscript,
            "updatedSummary": "",
            "promptTitle": decoded_prompt_title,
            "prompt": decoded_prompt,
            "code": item['id_cd'],
            "accuracy": "",
            "completeness": "",
            "coherence": "",
            "lexiconPrecision": "",
            "feedback": "",
            "_ts": int(time.time())  # Current Unix timestamp
        }

        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy"]
        collection.insert_one(document)

        # Return the new id
        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/saveNotebuddyPrompt', methods=['POST'])
# @validate_hmac
# @validate_client_cert
def save_notebuddy_prompt(*args, **kwargs):
    data = request.json
    # summary = data.get('summary')
    # transcript = data.get('transcript')
    # user_id = request.headers['userId']
    item = data['item']

    # Decode
    decoded_prompttitle = base64.b64decode(item['promptTitle']).decode('utf-8')
    decoded_prompt = base64.b64decode(item['prompt']).decode('utf-8')
    decoded_promptCategory = base64.b64decode(item['promptCategory']).decode('utf-8') # Added 28082024
    decoded_promptVisibility = base64.b64decode(item['promptVisibility']).decode('utf-8') # Added 28082024
        
    #check if there is a prompt in db with same title
    try:
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy_prompts"]
        document = collection.find_one({"promptTitle": decoded_prompttitle})
        if document:
            return jsonify({"error": "Prompt with same title already exists"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
    pipeline = [
            {
                '$project': {
                    'id': {'$toInt': '$id'}  # Cast code to integer
                }
            },
            {
                '$group': {
                    '_id': None,
                    'id': {'$max': '$id'}
                }
            }
        ]

    try:
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy_prompts"]
        result = list(collection.aggregate(pipeline))

        if len(result) == 0:
            highest = 0
        else:
            highest = result[0]['id']
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    try:
        # Save the data
        document = {
            "id": highest+1,
            "user": item['user'],
            "prompt": decoded_prompt,
            "promptTitle": decoded_prompttitle,
            "promptCategory": decoded_promptCategory, # Added 28082024
            "promptVisibility": decoded_promptVisibility, # Added 28082024
          
            "_ts": int(time.time())
        }
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy_prompts"]
        collection.insert_one(document)

        # Return the new id
        return jsonify({"success": True, "id": highest+1})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

#Retrieve Route

@app.route('/getAllPromptsNotebuddy', methods=['GET'])
# @validate_hmac
# @validate_client_cert
def get_all_prompts_notebuddy(*args, **kwargs):
    try:
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy_prompts"]
        documents = list(collection.find())

        if documents:
            for doc in documents:
                doc['_id'] = str(doc['_id'])

            return jsonify(documents)
        else:
            return jsonify([]), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/getAllInstNotebuddy', methods=['GET'])
# @validate_hmac
# @validate_client_cert
def get_all_institutions_notebuddy(*args, **kwargs):
    try:
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy_institutions"]
        documents = list(collection.find())

        if documents:
            for doc in documents:
                doc['_id'] = str(doc['_id'])

            return jsonify(documents)
        else:
            return jsonify([]), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500  

@app.route('/getAllDeptNotebuddy', methods=['GET'])
# @validate_hmac
# @validate_client_cert
def get_all_dept_notebuddy(*args, **kwargs):
    try:
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy_departments"]
        documents = list(collection.find())

        if documents:
            for doc in documents:
                doc['_id'] = str(doc['_id'])

            return jsonify(documents)
        else:
            return jsonify([]), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500      

@app.route('/getUserSession', methods=['POST'])
def get_user_session():
    data = request.json
    #unique_code = data['item']['id']
    #aad_user = data['item']['user']
    unique_code = data['id']
    aad_user = data['user']

    # Calculate the timestamp for 30 days ago
    #thirty_days_ago_timestamp = int(time.time()) - 30 * 24 * 60 * 60


    try:
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy"]
 
        # Construct the query
        query = {
            "id": unique_code,
            "user": aad_user,
        }
 
        # Execute the query
        items = list(collection.find(query))        

        for item in items:
            item['_id'] = str(item['_id'])
 
        if items:
            return jsonify(items), 200
        else:
            return jsonify({"error": "Data not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/retrieve', methods=['POST'])
# @validate_hmac
# @validate_client_cert
def retrieve_from_mongodb(*args, **kwargs):
    data = request.json
    #unique_code = data['item']['id']
    #aad_user = data['item']['user']
    unique_code = data['id']
    aad_user = data['user']
    
    if not unique_code:
        return jsonify({"error": "Unique code is required"}), 400
    if not aad_user:
        return jsonify({"error": "User is required"}), 400
    
 # Calculate the timestamp for 30 days ago
    #thirty_days_ago_timestamp = int(time.time()) - 30 * 24 * 60 * 60    
    
    try:
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy"]
 
        # Construct the query
        query = {
            "patientID": unique_code,
            "user": aad_user,
        }
 
        # Execute the query
        items = list(collection.find(query))        

        for item in items:
            item['_id'] = str(item['_id'])
 
        if items:
            return jsonify(items), 200
        else:
            return jsonify({"error": "Data not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/getPatientList', methods=['POST'])
# @validate_hmac
# @validate_client_cert
def get_patient_list_from_mongodb(*args, **kwargs):
    data = request.json
    #aad_user = data['item']['user']
    aad_user = data['user']
 
    if not aad_user:
        return jsonify({"error": "User is required"}), 400
 
    # Calculate the timestamp for 30 days ago
    #thirty_days_ago_timestamp = int(time.time()) - 30 * 24 * 60 * 60
 
    try:
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy"]
 
        # Construct the query
        query = {
            "user": aad_user,
            # "_ts": {"$gte": thirty_days_ago_timestamp}
        }
 
        # Execute the query
        items = list(collection.find(query))
 
        # Convert ObjectId to string for JSON serialization
        for item in items:
            item['_id'] = str(item['_id'])
 
        if items:
            return jsonify(items), 200
        else:
            # return jsonify({"error": "Data not found"}), 404
            # JH
            return jsonify([]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/retrieveAll', methods=['GET'])
# @validate_hmac
# @validate_client_cert
def retrieve_all_from_mongodb(*args, **kwargs):
    
   
    try:
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy"]
 

 
        # Execute the query
        # Execute the query to get all documents, but only return the user and transcript fields
        items = list(collection.find())

        for item in items:
            item['_id'] = str(item['_id'])

        if items:
            return jsonify(items), 200
        else:
            return jsonify({"error": "Data not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
#Insert Route
@app.route('/insertInstitutions', methods=['POST'])
# @validate_hmac
# @validate_client_cert
def insert_institutions(*args, **kwargs):
    institutions = [ 'SGH','CGH', 'KKH','SKH',  'NCCS',  'NDCS',  'NHCS',  'NNI', 'POLY',   'SCH',  'SERI', 'SHP', 'SNEC','ADMIN','ALLIED HEALTH' ,'SHHQ', 'ALL', 'OTHERS']

    try:
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy_institutions"]

        # Delete
        collection.delete_many({})

        # Insert institutions
        for institution in institutions:
            collection.insert_one({
                "id": str(uuid.uuid4()),  # Generate a unique ID
                "inst": institution
            })

        return jsonify({
            "title": "Institutions inserted",
            "description": "Static institutions inserted successfully",
            "status": "success"
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/insertDepts', methods=['POST'])
# @validate_hmac
# @validate_client_cert
def insert_Depts(*args, **kwargs):
    institutions = ['Admin','Allied Health','Nursing','Anaesthesiology',	'Breast Surgery',	'Colorectal Surgery',	'Dermatology',	'Radiology',	'Emergency Med',	'Endocrinology',	'Family Med',	'Gastroenterology',	'General Surgery',	'Geriatric Med',	'Gynaecology',	'Haematology',	'Hand Surgery',	'Head & Neck',	'Health Screening',	'HPB',	'Infectious Diseases',	'Internal Med',	'Lung Centre',	'Neonatology',	'Neurology',	'Neurosurgery',	'Nuclear Med',	'Occupational Med',	'Orthopaedic Surgery',	'Otorhinolaryngology',	'Pain Management Ctr','Pediatrics',	'Plastic Surgery',	'Psychiatry',	'Rehab Med',	'Renal Med',	'Respiratory Med',	'Rheumatology',	'Sleep Disorders',	'SPRinT',	'Staff Clinic',	'Upper GI Surgery',	'Urology',	'Vascular Surgery',	'MICU',	'NEMICU',	'BICU',	'Obstetrics',	'Burns',	'Ophthalmology',	'Otolaryngology',	'Oncology',	'Newborn Nursery',	'Occupational Therapy',	'General','Others']

    try:
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy_departments"]

        # Delete
        collection.delete_many({})

        # Insert institutions
        for institution in institutions:
            collection.insert_one({
                "id": str(uuid.uuid4()),  # Generate a unique ID
                "dept": institution
            })

        return jsonify({
            "title": "Departments inserted",
            "description": "Static departments inserted successfully",
            "status": "success"
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500 

#Feedback Route
@app.route('/updateFeedback', methods=['POST'])
# @validate_hmac
# @validate_client_cert
#01082024 -Updated to include feedback fields
def update_feedback_in_mongodb(*args, **kwargs):
    data = request.json['item']
    document_id = data['id']
    accuracy = data['accuracy']
    completeness = data['completeness']
    coherence = data['coherence']
    lexiconPrecision = data['lexiconPrecision']
    feedback = data['feedback']
    
    if not document_id or (not accuracy and not completeness and not coherence and not lexiconPrecision):
        return jsonify({"error": "No data or updated Feedback to save."}), 400

    try:
        # Update the summary field in the document
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy"]
        result = collection.update_one({"id": document_id}, {"$set": {**data,"accuracy": accuracy , "completeness": completeness, "coherence": coherence, "lexiconPrecision": lexiconPrecision, "feedback": feedback}})
        
        #return updated document if modified
        if result.modified_count > 0:
            document = collection.find_one({"id": document_id})
            response = {
                "accuracy": document["accuracy"],
                "completeness": document["completeness"],
                "coherence": document["coherence"],
                "lexiconPrecision": document["lexiconPrecision"],
                "feedback": document["feedback"],
                "id": document["id"],
                "code": document["code"],
            }
            return jsonify(response)
            # return jsonify({"success": True, "message": "Feedback updated successfully in MongoDB."})
        else:
            return jsonify({"error": "Document not found or Feedback not updated."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
#Delete Route 
@app.route('/deleteNotebuddyPrompt', methods=['POST'])
# @validate_hmac
# @validate_client_cert
def delete_notebuddy_prompt(*args, **kwargs):
    prompt_id = request.json['promptId']
    #data = request['item']
    #prompt_id = data['promptId']
 
    if not prompt_id:
        return jsonify({"error": "Prompt ID is required"}), 400
 
    try:
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy_prompts"]
 
        # Search collection for documents with the same prompt ID
        item_to_delete = collection.find_one({"id": prompt_id})
 
        if not item_to_delete:
            return jsonify({"error": "Item not found"}), 404
 
        # Delete the item from the database
        result = collection.delete_one({"id": prompt_id})
 
        if result.deleted_count == 1:
            return jsonify({
                "title": "Prompt deleted",
                "description": f"Prompt with id {prompt_id} deleted successfully",
                "status": "success"
            }), 200
        else:
            return jsonify({"error": "Prompt not deleted."}), 500
 
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/deleteAllNotes', methods=['POST'])
# @validate_hmac
# @validate_client_cert
def delete_all_notes(*args, **kwargs):
    try:
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy_prompts"]
 
        # Delete all documents from the collection
        result = collection.delete_many({})
 
        if result.deleted_count > 0:
            return jsonify({
                "title": "All Prompts Deleted",
                "description": f"{result.deleted_count} prompts deleted successfully",
                "status": "success"
            }), 200
        else:
            return jsonify({
                "title": "No Prompts Found",
                "description": "No prompts were found to delete.",
                "status": "success"
            }), 200
 
    except Exception as e:
        return jsonify({"error": str(e)}), 500

#UpdateSummary Route 
@app.route('/updateSummary', methods=['POST'])
# @validate_hmac
# @validate_client_cert
def update_summary_in_mongodb(*args, **kwargs):
    data = request.json['item']
    document_code = data['code']
    document_id = data['id']
    summary = data['updatedSummary']

    
    if not document_id or not summary:
        return jsonify({"error": "No data or updated summary to save."}), 400
    
    # Decode
    decoded_updatedsummary = base64.b64decode(data['updatedSummary']).decode('utf-8')

    try:
        # Update the summary field in the document
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy"]
        result = collection.update_one({"id": document_id}, {"$set": {**data,"code": document_code,"updatedSummary": decoded_updatedsummary , "_ts": int(time.time())}})

        
        #return updated document if modified
        if result.modified_count > 0:
            document = collection.find_one({"id": document_id})
            response = {
                "UpdatedSummary": decoded_updatedsummary,  #29072024 - Updated to return updated summary
                "transcript": document["transcript"],
                "id": document["code"]
            }
            return jsonify(response)
            # return jsonify({"success": True, "message": "Summary updated successfully in MongoDB."})
        else:
            return jsonify({"error": "Document not found or summary not updated."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/regenerateSummary', methods=['POST'])
# @validate_hmac
# @validate_client_cert
def regenerate_summary_in_mongodb(*args, **kwargs):
    data = request.json
    document_id = data['item']['id']
    document_code = data['item']['code']
    updated_summary = data['item']['updatedSummary']
    summary = data['item']['summary']
    
    if not document_id or not summary:
        return jsonify({"error": "No data or updated summary to save."}), 400

    # Decode
    decoded_updatedsummary = base64.b64decode(data['item']['updatedSummary']).decode('utf-8')
    decoded_summary = base64.b64decode(data['item']['summary']).decode('utf-8')

    try:
        # Update the summary field in the document
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy"]
        result = collection.update_one({"id": document_id}, {"$set": {**data,"code":document_code, "updatedSummary": decoded_updatedsummary, "summary": decoded_summary}})
        
        #return updated document if modified
        if result.modified_count > 0:
            document = collection.find_one({"id": document_id})
            response = {
                "summary": document["summary"],
                "updatedSummary": document["updatedSummary"],
                "transcript": document["transcript"],
                "id": document["code"]
            }
            return jsonify(response)
            # return jsonify({"success": True, "message": "Summary updated successfully in MongoDB."})
        else:
            return jsonify({"error": "Document not found or summary not updated."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/updateNotebuddyPrompt', methods=['POST'])
# @validate_hmac
# @validate_client_cert
def update_notebuddy_prompt(*args, **kwargs):
    data = request.json["item"]
   

    # Decode
    decoded_prompttitle = base64.b64decode(data['promptTitle']).decode('utf-8')
    decoded_prompt = base64.b64decode(data['prompt']).decode('utf-8')
    decoded_promptVisibility = data['promptVisibility']

    # Update the decoded prompt into data
    data['promptTitle'] = decoded_prompttitle
    data['prompt'] = decoded_prompt
    data['promptVisibility'] = decoded_promptVisibility

    try:
        filter = {'id': data['id']}
        update = {
            '$set': {
                **data,
                'prompt': decoded_prompt,
                'promptVisibility': decoded_promptVisibility,
                '_ts': int(time.time())  # Add current timestamp
            }
        }
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy_prompts"]

        #search collection for documents with same prompt title
        documents = list(collection.find({"promptTitle": decoded_prompttitle}))

        #if no docs found
        if documents and len(documents) == 0:
            return jsonify({"error": "Prompt not found."}), 404

        #if more than 1 doc, immediately fail
        if documents and len(documents) != 1:
            return jsonify({"error": "Prompt with same title already exists."}), 400

        doc = documents[0]
        print(doc)
        print(data)
        #if only 1 doc, check if id matches
        if doc and doc['id'] != data['id']:
            return jsonify({"error": "Prompt with same title already exists."}), 400

        #only allow update if aad user id "owns" the prompt
        result = collection.update_one(filter, update, upsert = True)

        if result.modified_count == 1:
            return jsonify({"success": True, "message": "Prompt updated successfully."})
        else:
            return jsonify({"error": "Prompt not updated."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500  

#Encrypt Route
@app.route('/encrypt', methods=['POST'])
# @validate_hmac
# @validate_client_cert
def encrypt_tns_text(*args, **kwargs):
    data = request.json['item']
    transcript = data['transcript']

    if not transcript:
        return jsonify({"error": "Transcript is required"}), 400

    try:
        chunks = [transcript[i:i+5000] for i in range(0, len(transcript), 5000)]

        # Process each chunk
        identified_pii = set()
        for i in range(len(chunks)):
            chunk = chunks[i]

            # Use Azure Text Analytics to identify names and email addresses
            response = text_analytics_client.recognize_pii_entities(documents=[chunk], categories_filter=["Email", "PhoneNumber", "SGNationalRegistrationIdentityCardNumber", "Address"])

            # Go through the recognized entities
            for entity in response[0].entities:
                if entity.category in ["Email", "PhoneNumber", "SGNationalRegistrationIdentityCardNumber", "Address"]:
                    # Add the identified PII to the set
                    identified_pii.add(entity.text)

        # Replace all unique PII values with their masked counterparts
        for pii in identified_pii:
            transcript = transcript.replace(pii, "XXXX")

        return jsonify({"encrypted_transcript": transcript, "identified_pii": list(identified_pii)}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/manageData', methods=['POST'])
# @validate_hmac
# @validate_client_cert
def manage_data():
    try:
        db_name = "notebuddy-db"
        db = client[db_name]
        collection = db["notebuddy"]
        archive_collection = db["notebuddy_archive"]

        # Move data to another collection before it expires
        expiration_threshold = datetime.utcnow() - timedelta(days=30)
        documents_to_archive = list(collection.find({"_ts": {"$lt": int(expiration_threshold.timestamp())}}))

        archived_count = 0  # Counter for archived documents

        if documents_to_archive:  # Check if the list is not empty
            for doc in documents_to_archive:
                try:
                    archive_collection.insert_one(doc)
                    collection.delete_one({"id": doc["id"]})
                    archived_count += 1  # Increment the counter
                except pymongo.errors.DuplicateKeyError:
                    # Skip the document if it causes a duplicate key error
                    continue

        return jsonify({"message": f"{archived_count} documents archived successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500  

@app.route('/manageArchive', methods=['POST'])
def manage_archive():
    try:
        db_name = "notebuddy-db"
        db = client[db_name]
        archive_collection = db["notebuddy_archive"]

        # Get expiration threshold from request body
        data = request.get_json()
        expiration_days = data.get('expiration_days', 60)  # Default to 30 days if not provided

        # Delete documents older than the specified expiration threshold
        expiration_threshold = datetime.utcnow() - timedelta(days=expiration_days)
        result = archive_collection.delete_many({"_ts": {"$lt": int(expiration_threshold.timestamp())}})

        return jsonify({"message": f"{result.deleted_count} documents deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Run Server
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000)
