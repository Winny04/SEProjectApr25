# auth_manager.py
import tkinter as tk
from tkinter import ttk, messagebox
from firebase_setup import db
from helpers import validate_email, validate_password, validate_employee_id
from constants import MIN_PASSWORD_LENGTH

class AuthManager:
    def __init__(self, root, app_instance):
        self.root = root
        self.app = app_instance
        self.username_entry = None
        self.password_entry = None
        self.signup_employee_id_entry = None
        self.signup_username_entry = None
        self.signup_email_entry = None
        self.signup_password_entry = None
        self.signup_confirm_password_entry = None
        self.signup_role = None

    def login_screen(self):
        """Displays the login screen for users."""
        self.app.clear_root()
        frame = ttk.Frame(self.root, padding=40) 
        frame.pack(expand=True) 

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Username:", font=("Helvetica", 12)).grid(row=0, column=0, sticky="e", pady=5, padx=5)
        self.username_entry = ttk.Entry(frame, width=40, font=("Helvetica", 12))
        self.username_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(frame, text="Password:", font=("Helvetica", 12)).grid(row=1, column=0, sticky="e", pady=5, padx=5)
        self.password_entry = ttk.Entry(frame, width=40, show="*", font=("Helvetica", 12))
        self.password_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=5)

        ttk.Button(frame, text="Login", command=self.handle_login, style="Accent.TButton").grid(row=2, column=0, columnspan=2, pady=15)
        ttk.Button(frame, text="Sign Up", command=self.signup_screen).grid(row=3, column=0, columnspan=2)

    def handle_login(self):
        """Handles user login authentication against Firestore."""
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username:
            messagebox.showerror("Error", "Username is required.")
            return
        if not validate_password(password):
            messagebox.showerror("Error", f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
            return

        users_ref = db.collection("users")
        query = users_ref.where("username", "==", username).where("password", "==", password).limit(1).get()

        if not query:
            messagebox.showerror("Error", "Invalid username or password.")
            return

        user_doc = query[0]
        user_data = user_doc.to_dict()
        self.app.current_user = user_data
        self.app.current_user['id'] = user_doc.id 
        self.app.current_user['employee_id'] = user_doc.id 

        if user_data.get("role") == "admin":
            self.app.admin_dashboard()
        else:
            self.app.user_dashboard()

    def signup_screen(self):
        """Displays the sign-up screen for new users."""
        self.app.clear_root()
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(expand=True)

        ttk.Label(frame, text="Employee ID (E...):").grid(row=0, column=0, sticky="e", pady=5, padx=5)
        self.signup_employee_id_entry = ttk.Entry(frame, width=30)
        self.signup_employee_id_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(frame, text="Username:").grid(row=1, column=0, sticky="e", pady=5, padx=5)
        self.signup_username_entry = ttk.Entry(frame, width=30)
        self.signup_username_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(frame, text="Email:").grid(row=2, column=0, sticky="e", pady=5, padx=5)
        self.signup_email_entry = ttk.Entry(frame, width=30)
        self.signup_email_entry.grid(row=2, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(frame, text="Password:").grid(row=3, column=0, sticky="e", pady=5, padx=5)
        self.signup_password_entry = ttk.Entry(frame, width=30, show="*")
        self.signup_password_entry.grid(row=3, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(frame, text="Confirm Password:").grid(row=4, column=0, sticky="e", pady=5, padx=5)
        self.signup_confirm_password_entry = ttk.Entry(frame, width=30, show="*")
        self.signup_confirm_password_entry.grid(row=4, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(frame, text="Role:").grid(row=5, column=0, sticky="e", pady=5, padx=5)
        self.signup_role = ttk.Combobox(frame, values=["user", "admin"], state="readonly", width=27)
        self.signup_role.grid(row=5, column=1, sticky="ew", pady=5, padx=5)
        self.signup_role.current(0) 

        ttk.Button(frame, text="Sign Up", command=self.handle_signup, style="Accent.TButton").grid(row=6, column=0, columnspan=2, pady=15)
        ttk.Button(frame, text="Back to Login", command=self.login_screen).grid(row=7, column=0, columnspan=2)

    def handle_signup(self):
        """Handles new user registration and saves data to Firestore."""
        employee_id = self.signup_employee_id_entry.get().strip()
        username = self.signup_username_entry.get().strip()
        email = self.signup_email_entry.get().strip()
        password = self.signup_password_entry.get().strip()
        confirm_password = self.signup_confirm_password_entry.get().strip()
        role = self.signup_role.get().strip()

        # --- Validation ---
        if not employee_id:
            messagebox.showerror("Error", "Employee ID is required.")
            return
        if not validate_employee_id(employee_id):
            messagebox.showerror("Error", "Invalid Employee ID format. Must start with 'E' followed by digits (e.g., E12345).")
            return
        if not username:
            messagebox.showerror("Error", "Username is required.")
            return
        if not validate_email(email):
            messagebox.showerror("Error", "Invalid email format.")
            return
        if not validate_password(password):
            messagebox.showerror("Error", f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
            return
        if password != confirm_password:
            messagebox.showerror("Error", "Passwords do not match.")
            return
        if role not in ["user", "admin"]:
            messagebox.showerror("Error", "Please select a valid role.")
            return

        users_ref = db.collection("users")

        existing_emp_id_doc = users_ref.document(employee_id).get()
        if existing_emp_id_doc.exists:
            messagebox.showerror("Error", "Employee ID already registered.")
            return

        existing_username_query = users_ref.where("username", "==", username).limit(1).get()
        if existing_username_query:
            for doc in existing_username_query:
                if doc.id != employee_id: 
                    messagebox.showerror("Error", "Username already exists.")
                    return

        existing_email_query = users_ref.where("email", "==", email).limit(1).get()
        if existing_email_query:
            for doc in existing_email_query:
                if doc.id != employee_id: 
                    messagebox.showerror("Error", "Email already registered.")
                    return

        user_data = {
            "employee_id": employee_id, 
            "username": username,
            "email": email,
            "password": password, 
            "role": role
        }
        try:
            users_ref.document(employee_id).set(user_data) 
            messagebox.showinfo("Success", "Registration successful! You can now log in.")
            self.app.login_screen()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to register user: {e}")

    def user_form_window(self, user_id=None, user_data=None):
        """Creates a Toplevel window for adding or editing user details (for admin)."""
        form = tk.Toplevel(self.root)
        form.title("User Form")
        form.geometry("400x400") 
        form.grab_set() 
        form.transient(self.root) 

        frame = ttk.Frame(form, padding=15)
        frame.pack(expand=True, fill="both")

        ttk.Label(frame, text="Employee ID (E...):").grid(row=0, column=0, sticky="e", pady=5)
        employee_id_entry = ttk.Entry(frame, width=30)
        employee_id_entry.grid(row=0, column=1, sticky="ew", pady=5)
        if user_data: 
            employee_id_entry.insert(0, user_data.get("employee_id", ""))
            employee_id_entry.config(state='disabled')
        
        ttk.Label(frame, text="Username:").grid(row=1, column=0, sticky="e", pady=5)
        username_entry = ttk.Entry(frame, width=30)
        username_entry.grid(row=1, column=1, sticky="ew", pady=5)
        if user_data:
            username_entry.insert(0, user_data.get("username", ""))

        ttk.Label(frame, text="Email:").grid(row=2, column=0, sticky="e", pady=5)
        email_entry = ttk.Entry(frame, width=30)
        email_entry.grid(row=2, column=1, sticky="ew", pady=5)
        if user_data:
            email_entry.insert(0, user_data.get("email", ""))

        ttk.Label(frame, text="Password:").grid(row=3, column=0, sticky="e", pady=5)
        password_entry = ttk.Entry(frame, width=30, show="*")
        password_entry.grid(row=3, column=1, sticky="ew", pady=5)
        if user_data:
            password_entry.insert(0, user_data.get("password", "")) 

        ttk.Label(frame, text="Role (admin/user):").grid(row=4, column=0, sticky="e", pady=5)
        role_combobox = ttk.Combobox(frame, values=["user", "admin"], state="readonly", width=27)
        role_combobox.grid(row=4, column=1, sticky="ew", pady=5)
        if user_data:
            role_combobox.set(user_data.get("role", "user"))
        else:
            role_combobox.current(0)

        def submit():
            current_employee_id = employee_id_entry.get().strip() 
            username = username_entry.get().strip()
            email = email_entry.get().strip()
            password = password_entry.get().strip()
            role = role_combobox.get().strip().lower()

            # --- Validation ---
            if not user_id: 
                if not current_employee_id:
                    messagebox.showerror("Error", "Employee ID is required.")
                    return
                if not validate_employee_id(current_employee_id):
                    messagebox.showerror("Error", "Invalid Employee ID format. Must start with 'E' followed by digits (e.g., E12345).")
                    return

            if not username:
                messagebox.showerror("Error", "Username is required.")
                return
            if not validate_email(email):
                messagebox.showerror("Error", "Invalid email format.")
                return
            if not validate_password(password):
                messagebox.showerror("Error", f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
                return
            if role not in ["admin", "user"]:
                messagebox.showerror("Error", "Role must be 'admin' or 'user'.")
                return

            users_ref = db.collection("users")

            if not user_id: 
                if users_ref.document(current_employee_id).get().exists:
                    messagebox.showerror("Error", "Employee ID already exists.")
                    return
                existing_username_query = users_ref.where("username", "==", username).limit(1).get()
                if existing_username_query:
                    messagebox.showerror("Error", "Username already exists.")
                    return
                existing_email_query = users_ref.where("email", "==", email).limit(1).get()
                if existing_email_query:
                    messagebox.showerror("Error", "Email already exists.")
                    return
            else: 
                existing_username_query = users_ref.where("username", "==", username).limit(1).get()
                for doc in existing_username_query:
                    if doc.id != user_id:
                        messagebox.showerror("Error", "Username already exists for another user.")
                        return
                existing_email_query = users_ref.where("email", "==", email).limit(1).get()
                for doc in existing_email_query:
                    if doc.id != user_id:
                        messagebox.showerror("Error", "Email already exists for another user.")
                        return

            user_obj = {
                "employee_id": current_employee_id if not user_id else user_id, 
                "username": username,
                "email": email,
                "password": password, 
                "role": role
            }

            try:
                if user_id: 
                    db.collection("users").document(user_id).set(user_obj)
                    messagebox.showinfo("Success", "User updated successfully.")
                else: 
                    db.collection("users").document(current_employee_id).set(user_obj)
                    messagebox.showinfo("Success", "User added successfully.")
                
                # This needs to call back to AdminLogic to refresh users_tree
                self.app.admin_logic.load_users() 
                form.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save user: {e}")

        ttk.Button(frame, text="Submit", command=submit, style="Accent.TButton").grid(row=5, column=0, columnspan=2, pady=15) 
        form.protocol("WM_DELETE_WINDOW", form.destroy) 
