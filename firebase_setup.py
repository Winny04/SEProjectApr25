# firebase_setup.py
import firebase_admin
from firebase_admin import credentials, firestore
from tkinter import messagebox

# Path to your Firebase service account key file
# Replace "firebase_config.json" with the actual path if it's not in the same directory
try:
    cred = credentials.Certificate("firebase_config.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase initialized successfully.")
except Exception as e:
    print(f"Error initializing Firebase: {e}")
    # You might want to add more robust error handling or exit the application
    db = None  # Ensure db is None if initialization fails
