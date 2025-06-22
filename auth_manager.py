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

        # Initialize ttk Style for modern look
        self.style = ttk.Style()
        self.style.theme_use('clam')  # Or 'alt', 'vista', 'xpnative'

        # Configure general styles for a cleaner look
        self.style.configure('TFrame', background='#e0e0e0', relief='flat')
        self.style.configure('TLabel', font=('Helvetica Neue', 11), background='#e0e0e0', foreground='#333333')
        self.style.configure('TEntry', font=('Helvetica Neue', 11), padding=5)
        self.style.map('TEntry', fieldbackground=[('focus', '#ffffff'), ('!focus', '#f0f0f0')]) # Lighter background

        # Accent button style
        self.style.configure('Accent.TButton',
                             font=('Helvetica Neue', 11, 'bold'),
                             background='#4CAF50',  # Green
                             foreground='white',
                             relief='flat',
                             padding=(10, 5))
        self.style.map('Accent.TButton',
                       background=[('active', '#45a049')],
                       foreground=[('active', 'white')])

        # Secondary button style
        self.style.configure('TButton',
                             font=('Helvetica Neue', 11),
                             background='#007bff',  # Blue
                             foreground='white',
                             relief='flat',
                             padding=(10, 5))
        self.style.map('TButton',
                       background=[('active', '#0056b3')],
                       foreground=[('active', 'white')])


    def login_screen(self):
        """Displays the login screen for users with a modernized design and app title."""
        self.app.clear_root()

        # Main frame with padding and background
        main_frame = ttk.Frame(self.root, padding="40 20 40 40", style='TFrame')
        main_frame.pack(expand=True, fill='both')

        # Center the content
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_rowconfigure(4, weight=1) # To push content to center vertically
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(2, weight=1) # To push content to center horizontally

        # Inner frame for form elements
        form_frame = ttk.Frame(main_frame, padding=30, relief='solid', borderwidth=1, style='TFrame')
        form_frame.grid(row=1, column=1, sticky='nsew', padx=20, pady=20)
        form_frame.columnconfigure(0, weight=1)
        form_frame.columnconfigure(1, weight=2)

        # App Title
        ttk.Label(form_frame, text="Shelf-Life Study Management System ", font=("Helvetica Neue", 18, "bold"),
                  background="#ffffff", foreground='#2c3e50').grid(row=0, column=0, columnspan=2, pady=(0, 25))

        # Login form fields
        ttk.Label(form_frame, text="Username:", font=("Helvetica Neue", 11)).grid(row=1, column=0, sticky="w", pady=5, padx=5)
        self.username_entry = ttk.Entry(form_frame, width=40, font=("Helvetica Neue", 11))
        self.username_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(form_frame, text="Password:", font=("Helvetica Neue", 11)).grid(row=2, column=0, sticky="w", pady=5, padx=5)
        self.password_entry = ttk.Entry(form_frame, width=40, show="*", font=("Helvetica Neue", 11))
        self.password_entry.grid(row=2, column=1, sticky="ew", pady=5, padx=5)

        # Buttons
        ttk.Button(form_frame, text="Login", command=self.handle_login, style="Accent.TButton").grid(row=3, column=0, columnspan=2, pady=15, sticky='ew', padx=5)
        ttk.Button(form_frame, text="Sign Up", command=self.signup_screen).grid(row=4, column=0, columnspan=2, sticky='ew', padx=5)


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

        # New: Check user status
        if user_data.get("role") != "admin" and user_data.get("status") == "pending":
            messagebox.showerror("Login Error",
                                 "Your account is pending admin approval. Please contact an administrator.")
            self.app.current_user = None  # Clear current user
            return

        # If not pending (or if admin), proceed with login
        self.app.current_user = user_data

        if user_data.get("role") == "admin":
            self.app.admin_dashboard()
        elif user_data.get("role") == "user":  # Assuming "user" is the role for general users
            self.app.user_dashboard()
        elif user_data.get("role") == "tester":  # Correctly routing for tester role
            self.app.test_dashboard()
        else:
            # Handle unknown or unapproved roles
            messagebox.showwarning("Access Denied", "Your role is not recognized or approved for access.")
            self.app.logout()

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
        self.signup_role = ttk.Combobox(frame, values=["user", "admin", "tester"], state="readonly", width=27)
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
        if role not in ["user", "admin", "tester"]:
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
            "role": role,
            "status": "active" if role == "admin" else "pending"
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
        role_combobox = ttk.Combobox(frame, values=["user", "admin", "tester"], state="readonly", width=27)
        role_combobox.grid(row=4, column=1, sticky="ew", pady=5)
        if user_data:
            role_combobox.set(user_data.get("role", "user"))
        else:
            role_combobox.current(0)

            # New: Status field
            ttk.Label(frame, text="Status:").grid(row=5, column=0, sticky="e", pady=5)
            status_combobox = ttk.Combobox(frame, values=["pending", "active"], state="readonly", width=27)
            status_combobox.grid(row=5, column=1, sticky="ew", pady=5)
            if user_data:
                status_combobox.set(user_data.get("status", "pending"))
            else:
                status_combobox.current(0)  # Default to pending for new users
            # End New

        def submit():
            current_employee_id = employee_id_entry.get().strip()
            username = username_entry.get().strip()
            email = email_entry.get().strip()
            password = password_entry.get().strip()
            role = role_combobox.get().strip().lower()
            status = status_combobox.get().strip().lower()  # New: Retrieve status

            # --- Validation ---
            if not user_id:
                if not current_employee_id:
                    messagebox.showerror("Error", "Employee ID is required.")
                    return
                if not validate_employee_id(current_employee_id):
                    messagebox.showerror("Error", "Invalid Employee ID format. Must start with 'E' followed by digits (e.g., E12345).")
                    return

            # New: Validate status
            if status not in ["pending", "active"]:
                messagebox.showerror("Error", "Status must be 'pending' or 'active'.")
                return
            # End New

            if not username:
                messagebox.showerror("Error", "Username is required.")
                return
            if not validate_email(email):
                messagebox.showerror("Error", "Invalid email format.")
                return
            if not validate_password(password):
                messagebox.showerror("Error", f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
                return
            if role not in ["admin", "user", "tester"]:
                messagebox.showerror("Error", "Role must be 'admin', 'user' or 'tester'.")
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
                "role": role,
                "status": "active" if role == "admin" else "pending"# New: Include status in user_obj
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

        ttk.Button(frame, text="Submit", command=submit, style="Accent.TButton").grid(row=6, column=0, columnspan=2, pady=15)
        form.protocol("WM_DELETE_WINDOW", form.destroy)

