import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
from datetime import datetime, timedelta
import barcode
from barcode.writer import ImageWriter
import os, re
import firebase_admin
from firebase_admin import credentials, firestore

# ---------------- FIREBASE SETUP ----------------
# TODO: Ensure 'firebase_config.json' is in the same directory as this script,
# or provide the full path to it (e.g., r"C:\Users\srist\Documents\Firebase_Keys\firebase_config.json")
try:
    cred = credentials.Certificate("firebase_config.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    messagebox.showerror("Firebase Error", f"Failed to initialize Firebase: {e}\nPlease ensure 'firebase_config.json' is correctly placed and accessible.")
    # Exit the application if Firebase initialization fails critically
    exit()


# ---------------- CONSTANTS ----------------
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
MIN_PASSWORD_LENGTH = 6
# Employee ID must start with 'E' followed by one or more digits
EMPLOYEE_ID_REGEX = re.compile(r"^E\d+$") 

NOTIFICATION_DAYS_BEFORE = 60 # 2 months approx.

# Expected columns for Excel data, 'Status' will be added if not present
COLUMNS = ["SampleID", "Owner", "MaturationDate", "Status"] 

# ---------------- HELPERS ----------------
def validate_email(email):
    """Validates if the provided string is a valid email format."""
    return EMAIL_REGEX.match(email) is not None

def validate_password(password):
    """Validates if the password meets the minimum length requirement."""
    return len(password) >= MIN_PASSWORD_LENGTH

def validate_employee_id(emp_id):
    """Validates if the employee ID matches the required pattern (e.g., E12345)."""
    return EMPLOYEE_ID_REGEX.match(emp_id) is not None

# --- Main Application ---
class ShelfLifeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Shelf-life Study Management System")
        self.root.geometry("800x600") # Default size, will adjust for admin view

        self.data = pd.DataFrame()
        self.file_path = "" # Path to the imported Excel file for user dashboard

        self.current_user = None # Stores authenticated user's data
        self.login_screen()

    # -------- UI UTILITIES --------
    def clear_root(self):
        """Clears all widgets from the main window."""
        for widget in self.root.winfo_children():
            widget.destroy()

    # -------- LOGIN SCREEN --------
    def login_screen(self):
        """Displays the login screen for users."""
        self.clear_root()
        frame = ttk.Frame(self.root, padding=40) # Increased padding
        frame.pack(expand=True) # Center frame in window

        # Configure columns for better layout
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

        # Query Firestore users collection for the given username and password
        users_ref = db.collection("users")
        # Note: We are still querying by username and password, as employee_id is the document ID,
        # but the user logs in with their chosen username.
        query = users_ref.where("username", "==", username).where("password", "==", password).limit(1).get()

        if not query:
            messagebox.showerror("Error", "Invalid username or password.")
            return

        user_doc = query[0]
        user_data = user_doc.to_dict()
        self.current_user = user_data
        # Store the actual Firestore document ID (which is now the employee_id)
        self.current_user['id'] = user_doc.id 
        # Add employee_id to current_user if not already there (it should be from user_data)
        self.current_user['employee_id'] = user_doc.id 

        # Redirect based on role
        if user_data.get("role") == "admin":
            self.admin_dashboard()
        else:
            self.user_dashboard()

    # -------- SIGN UP SCREEN --------
    def signup_screen(self):
        """Displays the sign-up screen for new users."""
        self.clear_root()
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
        self.signup_role.current(0) # Default to 'user' role

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

        # Check if Employee ID already exists as a document ID
        existing_emp_id_doc = users_ref.document(employee_id).get()
        if existing_emp_id_doc.exists:
            messagebox.showerror("Error", "Employee ID already registered.")
            return

        # Check if Username already exists for another user
        existing_username_query = users_ref.where("username", "==", username).limit(1).get()
        if existing_username_query:
            # Check if the existing username belongs to a different document ID
            for doc in existing_username_query:
                if doc.id != employee_id: # Ensure it's not the same employee_id attempting to sign up again
                    messagebox.showerror("Error", "Username already exists.")
                    return

        # Check if Email already exists for another user
        existing_email_query = users_ref.where("email", "==", email).limit(1).get()
        if existing_email_query:
            for doc in existing_email_query:
                if doc.id != employee_id: # Ensure it's not the same employee_id attempting to sign up again
                    messagebox.showerror("Error", "Email already registered.")
                    return

        # Add new account using employee_id as the document ID
        user_data = {
            "employee_id": employee_id, # Store employee_id as a field as well
            "username": username,
            "email": email,
            "password": password, # In a real app, hash this password!
            "role": role
        }
        try:
            users_ref.document(employee_id).set(user_data) # Set document with custom ID
            messagebox.showinfo("Success", "Registration successful! You can now log in.")
            self.login_screen()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to register user: {e}")

    # -------- ADMIN DASHBOARD --------
    def admin_dashboard(self):
        """Displays the admin dashboard with user and batch management."""
        self.clear_root()
        self.root.geometry("1200x700") # Increased size for admin view

        # Top frame for Logout button and Welcome message
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(top_frame, text="Logout", command=self.logout).pack(side="right")
        ttk.Label(top_frame, text=f"Welcome, Admin {self.current_user.get('username')}!", font=("Helvetica", 16)).pack(side="left", expand=True)

        # Users Section
        ttk.Label(self.root, text="User Management", font=("Helvetica", 14, "bold")).pack(pady=(20, 5))
        self.users_tree = ttk.Treeview(self.root, columns=("EmployeeID", "Username", "Email", "Role"), show='headings')
        self.users_tree.heading("EmployeeID", text="Employee ID")
        self.users_tree.heading("Username", text="Username")
        self.users_tree.heading("Email", text="Email")
        self.users_tree.heading("Role", text="Role")
        
        # Adjust column widths
        self.users_tree.column("EmployeeID", width=120, anchor="center")
        self.users_tree.column("Username", width=120, anchor="center")
        self.users_tree.column("Email", width=200, anchor="center")
        self.users_tree.column("Role", width=80, anchor="center")

        self.users_tree.pack(expand=True, fill="both", padx=10, pady=10)

        btn_user_frame = ttk.Frame(self.root)
        btn_user_frame.pack(pady=5)

        ttk.Button(btn_user_frame, text="Add User", command=self.admin_add_user).pack(side="left", padx=5)
        ttk.Button(btn_user_frame, text="Edit User", command=self.admin_edit_user).pack(side="left", padx=5)
        ttk.Button(btn_user_frame, text="Delete User", command=self.admin_delete_user).pack(side="left", padx=5)

        self.load_users()

        # Batches Section
        ttk.Label(self.root, text="Batch Approval", font=("Helvetica", 14, "bold")).pack(pady=(20, 5))
        self.batches_tree = ttk.Treeview(self.root,
                                         columns=("ProductID", "Name", "Description", "TestDate", "User", "Status"),
                                         show='headings')
        for col in ("ProductID", "Name", "Description", "TestDate", "User", "Status"):
            self.batches_tree.heading(col, text=col)
            self.batches_tree.column(col, width=100, anchor="center") # Default width for batch columns
        self.batches_tree.pack(expand=True, fill="both", padx=10, pady=10)

        btn_batch_frame = ttk.Frame(self.root)
        btn_batch_frame.pack(pady=5)

        ttk.Button(btn_batch_frame, text="Approve Batch", command=self.admin_approve_batch).pack(side="left", padx=5)
        ttk.Button(btn_batch_frame, text="Export Approved Batches", command=self.export_user_batches).pack(side="left", padx=5)

        self.load_batches()
        
        # Removed redundant logout button at the bottom

    def load_users(self):
        """Loads user data from Firestore and populates the users treeview."""
        self.users_tree.delete(*self.users_tree.get_children())
        users = db.collection("users").stream()
        for user in users:
            data = user.to_dict()
            self.users_tree.insert("", "end", iid=user.id, 
                                   values=(data.get("employee_id"), data.get("username", ""), 
                                           data.get("email"), data.get("role")))

    def admin_add_user(self):
        """Opens a form to add a new user."""
        self.user_form_window()

    def admin_edit_user(self):
        """Opens a form to edit an existing user."""
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a user to edit.")
            return
        user_id = selected[0] # This will be the employee_id
        user_doc = db.collection("users").document(user_id).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            self.user_form_window(user_id=user_id, user_data=user_data)

    def admin_delete_user(self):
        """Deletes a selected user from Firestore."""
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a user to delete.")
            return
        user_id = selected[0] # This is the employee_id
        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete user with Employee ID '{user_id}'?")
        if confirm:
            try:
                db.collection("users").document(user_id).delete()
                messagebox.showinfo("Success", "User deleted successfully.")
                self.load_users()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete user: {e}")

    def user_form_window(self, user_id=None, user_data=None):
        """Creates a Toplevel window for adding or editing user details."""
        form = tk.Toplevel(self.root)
        form.title("User Form")
        form.geometry("400x400") # Adjusted size
        form.grab_set() # Make this window modal
        form.transient(self.root) # Set to be on top of the root window

        frame = ttk.Frame(form, padding=15)
        frame.pack(expand=True, fill="both")

        # Employee ID
        ttk.Label(frame, text="Employee ID (E...):").grid(row=0, column=0, sticky="e", pady=5)
        employee_id_entry = ttk.Entry(frame, width=30)
        employee_id_entry.grid(row=0, column=1, sticky="ew", pady=5)
        if user_data: # If editing, populate and disable Employee ID
            employee_id_entry.insert(0, user_data.get("employee_id", ""))
            employee_id_entry.config(state='disabled')
        
        # Username
        ttk.Label(frame, text="Username:").grid(row=1, column=0, sticky="e", pady=5)
        username_entry = ttk.Entry(frame, width=30)
        username_entry.grid(row=1, column=1, sticky="ew", pady=5)
        if user_data:
            username_entry.insert(0, user_data.get("username", ""))

        # Email
        ttk.Label(frame, text="Email:").grid(row=2, column=0, sticky="e", pady=5)
        email_entry = ttk.Entry(frame, width=30)
        email_entry.grid(row=2, column=1, sticky="ew", pady=5)
        if user_data:
            email_entry.insert(0, user_data.get("email", ""))

        # Password
        ttk.Label(frame, text="Password:").grid(row=3, column=0, sticky="e", pady=5)
        password_entry = ttk.Entry(frame, width=30, show="*")
        password_entry.grid(row=3, column=1, sticky="ew", pady=5)
        if user_data:
            password_entry.insert(0, user_data.get("password", "")) # Be careful with actual passwords

        # Role
        ttk.Label(frame, text="Role (admin/user):").grid(row=4, column=0, sticky="e", pady=5)
        role_combobox = ttk.Combobox(frame, values=["user", "admin"], state="readonly", width=27)
        role_combobox.grid(row=4, column=1, sticky="ew", pady=5)
        if user_data:
            role_combobox.set(user_data.get("role", "user"))
        else:
            role_combobox.current(0)

        def submit():
            current_employee_id = employee_id_entry.get().strip() # This is the entered ID for new, or disabled ID for edit
            username = username_entry.get().strip()
            email = email_entry.get().strip()
            password = password_entry.get().strip()
            role = role_combobox.get().strip().lower()

            # --- Validation ---
            # If adding a new user, validate employee ID format
            if not user_id: # Only validate format if it's a new entry (not disabled)
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

            # Uniqueness checks
            if not user_id: # If adding a new user
                # Check if Employee ID already exists as a document ID
                if users_ref.document(current_employee_id).get().exists:
                    messagebox.showerror("Error", "Employee ID already exists.")
                    return
                # Check if Username already exists (for other users)
                existing_username_query = users_ref.where("username", "==", username).limit(1).get()
                if existing_username_query:
                    messagebox.showerror("Error", "Username already exists.")
                    return
                # Check if Email already exists (for other users)
                existing_email_query = users_ref.where("email", "==", email).limit(1).get()
                if existing_email_query:
                    messagebox.showerror("Error", "Email already exists.")
                    return
            else: # If editing an existing user
                # Check if Username exists for a *different* employee ID
                existing_username_query = users_ref.where("username", "==", username).limit(1).get()
                for doc in existing_username_query:
                    if doc.id != user_id:
                        messagebox.showerror("Error", "Username already exists for another user.")
                        return
                # Check if Email exists for a *different* employee ID
                existing_email_query = users_ref.where("email", "==", email).limit(1).get()
                for doc in existing_email_query:
                    if doc.id != user_id:
                        messagebox.showerror("Error", "Email already exists for another user.")
                        return

            user_obj = {
                "employee_id": current_employee_id if not user_id else user_id, # Use current_employee_id for new, or existing user_id for edit
                "username": username,
                "email": email,
                "password": password, # Again, hash this in a real app
                "role": role
            }

            try:
                if user_id: # Editing existing user
                    users_ref.document(user_id).set(user_obj)
                    messagebox.showinfo("Success", "User updated successfully.")
                else: # Adding new user
                    users_ref.document(current_employee_id).set(user_obj)
                    messagebox.showinfo("Success", "User added successfully.")
                
                self.load_users() # Refresh user list
                form.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save user: {e}")

        ttk.Button(frame, text="Submit", command=submit, style="Accent.TButton").grid(row=5, column=0, columnspan=2, pady=15) # Adjusted row
        form.protocol("WM_DELETE_WINDOW", form.destroy) # Allow closing with X button


    def load_batches(self):
        """Loads batch data from Firestore and populates the batches treeview."""
        self.batches_tree.delete(*self.batches_tree.get_children())
        batches = db.collection("batches").stream()
        for batch in batches:
            data = batch.to_dict()
            test_date_str = data.get("test_date", "")
            # Handle Firestore Timestamp objects or string dates
            if isinstance(test_date_str, firestore.Timestamp):
                test_date_str = test_date_str.to_datetime().strftime("%Y-%m-%d")
            elif isinstance(test_date_str, datetime): # Already a datetime object
                test_date_str = test_date_str.strftime("%Y-%m-%d")
            
            self.batches_tree.insert("", "end", iid=batch.id,
                                     values=(data.get("product_id", ""),
                                             data.get("product_name", ""),
                                             data.get("description", ""),
                                             test_date_str,
                                             data.get("user_email", ""), # Assuming this is email of the user who submitted
                                             data.get("status", "pending")))

    def admin_approve_batch(self):
        """Approves a selected batch in Firestore."""
        selected = self.batches_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a batch to approve.")
            return
        batch_id = selected[0]
        batch_ref = db.collection("batches").document(batch_id)
        batch_doc = batch_ref.get()
        if batch_doc.exists:
            batch_data = batch_doc.to_dict()
            if batch_data.get("status") == "approved":
                messagebox.showinfo("Info", "Batch already approved.")
                return

            confirm = messagebox.askyesno("Confirm Approve", "Approve this batch?")
            if confirm:
                try:
                    batch_ref.update({"status": "approved"})
                    messagebox.showinfo("Success", "Batch approved successfully.")
                    self.load_batches() # Refresh batch list
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to approve batch: {e}")

    def export_user_batches(self):
        """Exports approved batches to an Excel file."""
        approved_batches = []
        batches = db.collection("batches").where("status", "==", "approved").get()
        for batch in batches:
            data = batch.to_dict()
            # Convert Firestore Timestamp to datetime object for consistency
            if isinstance(data.get('test_date'), firestore.Timestamp):
                data['test_date'] = data['test_date'].to_datetime()
            approved_batches.append(data)

        if not approved_batches:
            messagebox.showwarning("Warning", "No approved batches to export.")
            return

        df_approved = pd.DataFrame(approved_batches)

        # Reorder columns for better readability
        export_columns = ["product_id", "product_name", "description", "test_date", "user_email", "status"]
        # Ensure all columns exist, fill missing with None
        df_approved = df_approved.reindex(columns=export_columns)

        filetypes = (("Excel files", "*.xlsx"),)
        filename = filedialog.asksaveasfilename(defaultextension=".xlsx", 
                                                 filetypes=filetypes,
                                                 initialfile="Approved_Batches.xlsx")
        if filename:
            try:
                df_approved.to_excel(filename, index=False)
                messagebox.showinfo("Success", f"Approved batches exported to {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export Excel file:\n{e}")

    def logout(self):
        """Logs out the current user and returns to the login screen."""
        confirm = messagebox.askyesno("Logout", "Are you sure you want to logout?")
        if confirm:
            self.current_user = None
            self.login_screen()

    # -------- USER DASHBOARD --------
    def user_dashboard(self):
        """Displays the user dashboard with sample management features."""
        self.clear_root()
        self.root.geometry("1000x600")
        self.excel_imported = False

        # === Menu Bar ===
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Import Excel", command=self.import_excel)
        filemenu.add_command(label="Export Excel", command=self.export_excel)
        filemenu.add_separator()
        filemenu.add_command(label="Logout", command=self.logout)
        menubar.add_cascade(label="File", menu=filemenu)
        self.root.config(menu=menubar)

        # === Toolbar Frame for Buttons ===
        toolbar = tk.Frame(self.root, pady=10)
        toolbar.pack(fill="x", padx=10) # Added fill="x" and padx for better layout

        ttk.Button(toolbar, text="Generate Barcode", command=self.generate_barcode).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Check Notifications", command=self.check_notifications).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Add Sample", command=self.add_sample).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Edit Sample", command=self.edit_sample).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Delete Sample", command=self.delete_sample).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Submit Batch for Approval", command=self.submit_batch_for_approval).pack(side=tk.LEFT, padx=5)


        # === Treeview for Data Display ===
        self.tree = ttk.Treeview(self.root, columns=("SampleID", "Owner", "MaturationDate", "Status"), show='headings')
        self.tree.heading("SampleID", text="Sample ID")
        self.tree.heading("Owner", text="Sample Owner")
        self.tree.heading("MaturationDate", text="Maturation Date")
        self.tree.heading("Status", text="Status")
        
        # Adjust column widths for user treeview
        self.tree.column("SampleID", width=120, anchor="center")
        self.tree.column("Owner", width=120, anchor="center")
        self.tree.column("MaturationDate", width=150, anchor="center")
        self.tree.column("Status", width=80, anchor="center")

        self.tree.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # === Status Bar ===
        self.status_label = tk.Label(self.root, text="Load a file to get started.", anchor='w', bd=1, relief=tk.SUNKEN)
        self.status_label.pack(fill=tk.X, padx=10, pady=5)

    def import_excel(self):
        """Imports data from an Excel file into the application."""
        filetypes = (("Excel files", "*.xlsx *.xls"), ("All files", "*.*"))
        filename = filedialog.askopenfilename(title="Open Excel file", filetypes=filetypes)
        if filename:
            try:
                self.data = pd.read_excel(filename)
                # Ensure 'Status' column exists, defaulting to 'pending' if not
                if 'Status' not in self.data.columns:
                    self.data['Status'] = 'pending'
                self.file_path = filename
                self.refresh_tree()
                self.status_label.config(text=f"Loaded data from {os.path.basename(filename)}")
                self.excel_imported = True
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load Excel file:\n{e}")

    def export_excel(self):
        """Exports current data to an Excel file."""
        if self.data.empty:
            messagebox.showwarning("Warning", "No data to export.")
            return
        filetypes = (("Excel files", "*.xlsx"),)
        filename = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=filetypes)
        if filename:
            try:
                self.data.to_excel(filename, index=False)
                self.status_label.config(text=f"Data exported to {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export Excel file:\n{e}")

    def refresh_tree(self):
        """Refreshes the Treeview widget with the current DataFrame data."""
        self.tree.delete(*self.tree.get_children())
        for _, row in self.data.iterrows():
            mat_date = row['MaturationDate']
            # Format datetime objects for display
            if isinstance(mat_date, pd.Timestamp):
                mat_date_str = mat_date.strftime("%Y-%m-%d")
            else: # Handle cases where it might be a string or other type already
                mat_date_str = str(mat_date) 
            self.tree.insert("", tk.END, values=(row['SampleID'], row['Owner'], mat_date_str, row['Status']))

    def generate_barcode(self):
        """Generates a barcode for the selected sample ID."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a sample from the list.")
            return
        item = self.tree.item(selected[0])
        sample_id = str(item['values'][0]) # Ensure sample_id is a string

        try:
            # Use Code128 which supports alphanumeric data
            EAN = barcode.get_barcode_class('code128') 
            ean = EAN(sample_id, writer=ImageWriter())
            save_path = filedialog.asksaveasfilename(defaultextension=".png",
                                                     filetypes=[("PNG files", "*.png")],
                                                     initialfile=f"{sample_id}_barcode.png")
            if save_path:
                ean.save(save_path)
                messagebox.showinfo("Success", f"Barcode saved at {save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Barcode generation failed:\n{e}")

    def check_notifications(self):
        """Checks for samples maturing within the defined notification period."""
        if self.data.empty:
            messagebox.showwarning("Warning", "No data loaded.")
            return

        today = datetime.now()
        notifications = []

        for _, row in self.data.iterrows():
            mat_date = row['MaturationDate']
            if pd.isna(mat_date): # Check for NaN/NaT dates
                continue

            if isinstance(mat_date, pd.Timestamp):
                mat_date_dt = mat_date.to_pydatetime()
            elif isinstance(mat_date, datetime):
                mat_date_dt = mat_date
            else:
                try: # Attempt to parse if it's a string
                    mat_date_dt = datetime.strptime(str(mat_date), "%Y-%m-%d")
                except ValueError:
                    continue # Skip if date format is invalid

            delta = mat_date_dt - today
            if 0 <= delta.days <= NOTIFICATION_DAYS_BEFORE:
                notifications.append(f"Sample {row['SampleID']} owned by {row['Owner']} matures on {mat_date_dt.strftime('%Y-%m-%d')}.")

        if notifications:
            messagebox.showinfo("Notifications", "\n".join(notifications))
        else:
            messagebox.showinfo("Notifications", f"No samples maturing within {NOTIFICATION_DAYS_BEFORE} days.")

    def add_sample(self):
        """Opens a form to add a new sample to the DataFrame."""
        if not self.excel_imported:
            messagebox.showwarning("Warning", "Please import data before adding samples.")
            return

        form = tk.Toplevel(self.root)
        form.title("Add New Sample")
        form.geometry("300x250") # Adjusted size
        form.grab_set()
        form.transient(self.root)

        tk.Label(form, text="Sample ID:").pack(pady=5)
        entry_sample_id = tk.Entry(form)
        entry_sample_id.pack()

        tk.Label(form, text="Sample Owner:").pack(pady=5)
        entry_owner = tk.Entry(form)
        entry_owner.pack()

        tk.Label(form, text="Maturation Date (YYYY-MM-DD):").pack(pady=5)
        entry_date = tk.Entry(form)
        entry_date.pack()
        
        # Add a status dropdown for adding samples (default to pending)
        tk.Label(form, text="Status:").pack(pady=5)
        status_combobox = ttk.Combobox(form, values=["pending", "approved", "rejected"], state="readonly", width=27)
        status_combobox.pack()
        status_combobox.current(0) # Default to pending

        def submit():
            sample_id = entry_sample_id.get().strip()
            owner = entry_owner.get().strip()
            date_str = entry_date.get().strip()
            status = status_combobox.get().strip()

            if not sample_id or not owner or not date_str:
                messagebox.showerror("Error", "All fields are required.")
                return
            try:
                mat_date = pd.to_datetime(date_str)
            except Exception:
                messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD.")
                return

            if sample_id in self.data['SampleID'].values:
                messagebox.showerror("Error", "Sample ID already exists.")
                return

            new_row = {'SampleID': sample_id, 'Owner': owner, 'MaturationDate': mat_date, 'Status': status}
            # Use concat for adding a new row to DataFrame
            self.data = pd.concat([self.data, pd.DataFrame([new_row])], ignore_index=True)
            self.refresh_tree()

            # Auto-save to original Excel file
            if self.file_path:
                try:
                    self.data.to_excel(self.file_path, index=False)
                    self.status_label.config(text=f"Added sample {sample_id} and saved to {os.path.basename(self.file_path)}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save Excel file:\n{e}")
            else:
                self.status_label.config(text=f"Added sample {sample_id}. No original file to save.")

            form.destroy()

        tk.Button(form, text="Add", command=submit).pack(pady=10)
        form.protocol("WM_DELETE_WINDOW", form.destroy)

    def delete_sample(self):
        """Deletes a selected sample from the DataFrame."""
        if self.data.empty:
            messagebox.showwarning("Warning", "Please import data before deleting samples.")
            return

        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a sample to delete.")
            return

        item = self.tree.item(selected[0])
        sample_id = item['values'][0]

        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete sample {sample_id}?")
        if confirm:
            self.data = self.data[self.data['SampleID'] != sample_id].reset_index(drop=True)
            self.refresh_tree()

            # Auto-save to original Excel file
            if self.file_path:
                try:
                    self.data.to_excel(self.file_path, index=False)
                    self.status_label.config(text=f"Deleted sample {sample_id} and saved to {os.path.basename(self.file_path)}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save Excel file:\n{e}")
            else:
                self.status_label.config(text=f"Deleted sample {sample_id}. No original file to save.")

    def edit_sample(self):
        """Opens a form to edit details of a selected sample."""
        if self.data.empty:
            messagebox.showwarning("Warning", "Please import data before editing samples.")
            return

        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a sample to edit.")
            return

        item = self.tree.item(selected[0])
        sample_id = item['values'][0]

        idx = self.data.index[self.data['SampleID'] == sample_id][0]
        row = self.data.loc[idx]

        form = tk.Toplevel(self.root)
        form.title(f"Edit Sample {sample_id}")
        form.geometry("300x250") # Adjusted size
        form.grab_set()
        form.transient(self.root)

        tk.Label(form, text="Sample ID:").pack(pady=5)
        entry_sample_id = tk.Entry(form)
        entry_sample_id.insert(0, row['SampleID'])
        entry_sample_id.config(state='disabled') # Sample ID cannot be changed
        entry_sample_id.pack()

        tk.Label(form, text="Sample Owner:").pack(pady=5)
        entry_owner = tk.Entry(form)
        entry_owner.insert(0, row['Owner'])
        entry_owner.pack()

        tk.Label(form, text="Maturation Date (YYYY-MM-DD):").pack(pady=5)
        entry_date = tk.Entry(form)
        if isinstance(row['MaturationDate'], pd.Timestamp):
            entry_date.insert(0, row['MaturationDate'].strftime('%Y-%m-%d'))
        else:
            entry_date.insert(0, str(row['MaturationDate']))
        entry_date.pack()

        tk.Label(form, text="Status:").pack(pady=5)
        status_combobox = ttk.Combobox(form, values=["pending", "approved", "rejected"], state="readonly", width=27)
        status_combobox.pack()
        status_combobox.set(row.get('Status', 'pending')) # Set current status

        def submit():
            owner = entry_owner.get().strip()
            date_str = entry_date.get().strip()
            status = status_combobox.get().strip()

            if not owner or not date_str:
                messagebox.showerror("Error", "All fields are required.")
                return
            try:
                mat_date = pd.to_datetime(date_str)
            except Exception:
                messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD.")
                return

            confirm = messagebox.askyesno("Confirm Edit", f"Are you sure you want to save changes to sample '{sample_id}'?")
            if not confirm:
                return

            self.data.at[idx, 'Owner'] = owner
            self.data.at[idx, 'MaturationDate'] = mat_date
            self.data.at[idx, 'Status'] = status # Update status
            self.refresh_tree()

            # Auto-save to original Excel file
            if self.file_path:
                try:
                    self.data.to_excel(self.file_path, index=False)
                    self.status_label.config(text=f"Updated sample {sample_id} and saved to {os.path.basename(self.file_path)}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save Excel file:\n{e}")
            else:
                self.status_label.config(text=f"Updated sample {sample_id}. No original file to save.")

            form.destroy()

        tk.Button(form, text="Save", command=submit).pack(pady=10)
        form.protocol("WM_DELETE_WINDOW", form.destroy)

    def submit_batch_for_approval(self):
        """Submits the current Excel data as a 'batch' to Firestore for admin approval."""
        if self.data.empty:
            messagebox.showwarning("Warning", "No data to submit for approval.")
            return
        
        # You need a unique identifier for the batch. Let's use a combination of user ID and timestamp.
        # For simplicity, let's create a batch entry for all currently loaded Excel data.
        # You might want to allow users to select specific rows for a batch submission.

        # Generate a unique batch ID
        batch_id = f"{self.current_user['employee_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        batch_data = {
            "batch_id": batch_id, # Store as a field as well
            "user_employee_id": self.current_user['employee_id'],
            "user_username": self.current_user['username'],
            "user_email": self.current_user['email'],
            "submission_date": firestore.SERVER_TIMESTAMP, # Firestore timestamp for when it was submitted
            "status": "pending", # Initial status
            # Convert DataFrame to a list of dictionaries for storage in a single document
            "samples": self.data.to_dict(orient='records') 
        }

        # For a more structured batch, you might want product_id, product_name, description, test_date from the samples
        # For this example, I'll add basic info from the first sample, or you can make the user input it.
        if not self.data.empty:
            first_sample = self.data.iloc[0]
            batch_data["product_id"] = first_sample.get("SampleID", "N/A")
            batch_data["product_name"] = "Batch of Samples" # Generic name
            batch_data["description"] = f"Submitted by {self.current_user['username']} ({self.current_user['employee_id']})"
            # Use a representative date, e.g., earliest maturation date or just submission date
            if 'MaturationDate' in first_sample and pd.notna(first_sample['MaturationDate']):
                if isinstance(first_sample['MaturationDate'], pd.Timestamp):
                    batch_data["test_date"] = first_sample['MaturationDate'].to_pydatetime()
                else: # Try to parse if it's a string
                    try:
                        batch_data["test_date"] = datetime.strptime(str(first_sample['MaturationDate']), "%Y-%m-%d")
                    except ValueError:
                        batch_data["test_date"] = None # Or provide a default

        confirm = messagebox.askyesno("Confirm Submission", "Submit current loaded Excel data for approval?")
        if confirm:
            try:
                db.collection("batches").document(batch_id).set(batch_data)
                messagebox.showinfo("Success", "Batch submitted for approval.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to submit batch: {e}")

# If you were to use `db.collection("users").document("your_id").set(...)` in the `ShelfLifeApp` class,
# ensure that `db` is properly initialized and accessible within the class methods.
# The current setup (`db = firestore.client()`) makes it globally available, which is fine.

if __name__ == "__main__":
    root = tk.Tk()
    # Apply a modern theme
    style = ttk.Style(root)
    style.theme_use('clam') # 'clam', 'alt', 'default', 'classic'
    # Define an accent button style
    style.configure('Accent.TButton', background='#4CAF50', foreground='white', font=('Helvetica', 10, 'bold'))
    style.map('Accent.TButton', 
              background=[('active', '#45a049'), ('pressed', '#367c39')],
              foreground=[('active', 'white'), ('pressed', 'white')])

    app = ShelfLifeApp(root)
    root.mainloop()
