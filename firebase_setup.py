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
except Exception as e:
    messagebox.showerror("Firebase Error", f"Failed to initialize Firebase: {e}\nPlease ensure 'firebase_config.json' is correctly placed and accessible.")
    # In a real application, you might want to log this error and exit more gracefully,
    # or handle it within the main application flow.
    # For now, we exit if Firebase setup is critical.
    exit()
