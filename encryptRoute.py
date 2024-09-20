from flask import Flask, request, jsonify
import uuid
import os
import pymongo
from blueprints.notebuddyAPI import bp
from decorators.ValidateClientCert import validate_client_cert
from decorators.validateHMACDecorator import validate_hmac
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential

# COSMOS_CONNECTION_STRING = os.environ.get("COSMOS_CONNECTION_STRING")
# client = pymongo.MongoClient(COSMOS_CONNECTION_STRING)

# key = "f0c9555dd72f452192efd53cdf422996"
# endpoint = "https://text-analytics-demo1.cognitiveservices.azure.com/"

# text_analytics_client = TextAnalyticsClient(endpoint=endpoint, credential=AzureKeyCredential(key))

# TEXT_ANALYTICS_ENDPOINT = os.environ["TEXT_ANALYTICS_SERVICE_ENDPOINT"]
# azure_credential = DefaultAzureCredential()
# text_analytics_client = TextAnalyticsClient(endpoint=TEXT_ANALYTICS_ENDPOINT, credential=azure_credential)

key = "603cdb17c06845adbebf09158a7ef2ab"
endpoint = "https://text-analytics-demo1.cognitiveservices.azure.com/"
text_analytics_client = TextAnalyticsClient(endpoint=endpoint, credential=AzureKeyCredential(key))
  
@bp.route('/encrypt', methods=['POST'])
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
