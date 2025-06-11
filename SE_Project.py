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
cred = credentials.Certificate("firebase_config.json")  # TODO: put your path here
firebase_admin.initialize_app(cred)
db = firestore.client()

# ---------------- CONSTANTS ----------------
EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")
MIN_PASSWORD_LENGTH = 6
# Constants
NOTIFICATION_DAYS_BEFORE = 60  # 2 months approx.


# ---------------- HELPERS ----------------
def validate_email(email):
    return EMAIL_REGEX.match(email) is not None


def validate_password(password):
    return len(password) >= MIN_PASSWORD_LENGTH

COLUMNS = ["SampleID", "Owner", "MaturationDate", "Status"]

# --- Main Application ---
class ShelfLifeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Shelf-life Study Management System")
        self.root.geometry("800x600")

        self.data = pd.DataFrame()
        self.file_path = ""

        self.current_user = None
        self.login_screen()

    # -------- LOGIN SCREEN --------
    def login_screen(self):
        self.clear_root()
        frame = ttk.Frame(self.root, padding=20)
        frame.pack()

        ttk.Label(frame, text="Username:").grid(row=0, column=0, sticky="e")
        self.username_entry = ttk.Entry(frame, width=30)
        self.username_entry.grid(row=0, column=1)

        ttk.Label(frame, text="Password:").grid(row=1, column=0, sticky="e")
        self.password_entry = ttk.Entry(frame, width=30, show="*")
        self.password_entry.grid(row=1, column=1)

        ttk.Button(frame, text="Login", command=self.handle_login).grid(row=2, column=0, columnspan=2, pady=10)
        # Add Sign Up button
        ttk.Button(frame, text="Sign Up", command=self.signup_screen).grid(row=3, column=0, columnspan=2)

    def handle_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username:
            messagebox.showerror("Error", "Username is required")
            return
        if not validate_password(password):
            messagebox.showerror("Error", f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
            return

        # Query Firestore users collection
        users_ref = db.collection("users")
        query = users_ref.where("username", "==", username).where("password", "==", password).limit(1).get()

        if not query:
            messagebox.showerror("Error", "Invalid username or password")
            return

        user_doc = query[0]
        user_data = user_doc.to_dict()
        self.current_user = user_data
        self.current_user['id'] = user_doc.id

        # Redirect based on role
        if user_data.get("role") == "admin":
            self.admin_dashboard()
        else:
            self.user_dashboard()

    # -------- SIGN UP SCREEN --------
    def signup_screen(self):
        self.clear_root()
        frame = ttk.Frame(self.root, padding=20)
        frame.pack()

        ttk.Label(frame, text="Username:").grid(row=0, column=0, sticky="e")
        self.signup_username_entry = ttk.Entry(frame, width=30)
        self.signup_username_entry.grid(row=0, column=1)

        ttk.Label(frame, text="Email:").grid(row=1, column=0, sticky="e")
        self.signup_email_entry = ttk.Entry(frame, width=30)
        self.signup_email_entry.grid(row=1, column=1)

        ttk.Label(frame, text="Password:").grid(row=2, column=0, sticky="e")
        self.signup_password_entry = ttk.Entry(frame, width=30, show="*")
        self.signup_password_entry.grid(row=2, column=1)

        ttk.Label(frame, text="Confirm Password:").grid(row=3, column=0, sticky="e")
        self.signup_confirm_password_entry = ttk.Entry(frame, width=30, show="*")
        self.signup_confirm_password_entry.grid(row=3, column=1)

        ttk.Label(frame, text="Role:").grid(row=4, column=0, sticky="e")
        self.signup_role = ttk.Combobox(frame, values=["user", "admin"], state="readonly", width=27)
        self.signup_role.grid(row=4, column=1)
        self.signup_role.current(0)

        ttk.Button(frame, text="Sign Up", command=self.handle_signup).grid(row=5, column=0, columnspan=2, pady=10)
        ttk.Button(frame, text="Back to Login", command=self.login_screen).grid(row=6, column=0, columnspan=2)

    def handle_signup(self):
        username = self.signup_username_entry.get().strip()
        email = self.signup_email_entry.get().strip()
        password = self.signup_password_entry.get().strip()
        confirm_password = self.signup_confirm_password_entry.get().strip()
        role = self.signup_role.get().strip()

        if not username:
            messagebox.showerror("Error", "Username is required")
            return
        if not validate_email(email):
            messagebox.showerror("Error", "Invalid email format")
            return
        if not validate_password(password):
            messagebox.showerror("Error", f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
            return
        if password != confirm_password:
            messagebox.showerror("Error", "Passwords do not match")
            return
        if role not in ["user", "admin"]:
            messagebox.showerror("Error", "Please select a valid role")
            return

        users_ref = db.collection("users")

        # Check if username exists
        existing_user = users_ref.where("username", "==", username).limit(1).get()
        if existing_user:
            messagebox.showerror("Error", "Username already exists")
            return

        # Check if email exists
        existing_email = users_ref.where("email", "==", email).limit(1).get()
        if existing_email:
            messagebox.showerror("Error", "Email already registered")
            return

        # Add new account
        user_data = {
            "username": username,
            "email": email,
            "password": password,
            "role": role
        }
        try:
            users_ref.add(user_data)
            messagebox.showinfo("Success", "Registration successful! You can now log in.")
            self.login_screen()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to register user: {e}")

    # -------- ADMIN DASHBOARD --------
    def admin_dashboard(self):
        self.clear_root()
        self.root.geometry("1000x600")

        # LOGOUT BUTTON (Top-left)
        logout_frame = ttk.Frame(self.root)
        logout_frame.pack(anchor="nw", padx=10, pady=10)
        ttk.Button(logout_frame, text="Logout", command=self.logout).pack()

        ttk.Label(self.root, text="Welcome to the Admin Dashboard!", font=("Helvetica", 16)).pack(pady=20)

        # You can now manually place the user management and batch approval sections
        # directly on the root, or in separate frames instead of tabs.

        # USERS SECTION
        self.users_tree = ttk.Treeview(self.root, columns=("Email", "Name", "Role"), show='headings')
        for col in ("Email", "Name", "Role"):
            self.users_tree.heading(col, text=col)
        self.users_tree.pack(expand=True, fill="both", padx=10, pady=10)

        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=5)

        ttk.Button(btn_frame, text="Add User", command=self.admin_add_user).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Edit User", command=self.admin_edit_user).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Delete User", command=self.admin_delete_user).pack(side="left", padx=5)

        self.load_users()

        # BATCHES SECTION
        self.batches_tree = ttk.Treeview(self.root,
                                         columns=("ProductID", "Name", "Description", "TestDate", "User", "Status"),
                                         show='headings')
        for col in ("ProductID", "Name", "Description", "TestDate", "User", "Status"):
            self.batches_tree.heading(col, text=col)
        self.batches_tree.pack(expand=True, fill="both", padx=10, pady=10)

        btn_batch_frame = ttk.Frame(self.root)
        btn_batch_frame.pack(pady=5)

        ttk.Button(btn_batch_frame, text="Approve Batch", command=self.admin_approve_batch).pack(side="left", padx=5)
        ttk.Button(btn_batch_frame, text="Export Approved Batches", command=self.export_user_batches).pack(side="left",
                                                                                                           padx=5)

        self.load_batches()

        # LOGOUT BUTTON
        logout_frame = ttk.Frame(self.root)
        logout_frame.pack(pady=10)
        ttk.Button(logout_frame, text="Logout", command=self.logout).pack()

    def load_users(self):
        self.users_tree.delete(*self.users_tree.get_children())
        users = db.collection("users").stream()
        for user in users:
            data = user.to_dict()
            self.users_tree.insert("", "end", iid=user.id, values=(data.get("email"), data.get("name", ""), data.get("role")))

    def admin_add_user(self):
        self.user_form_window()

    def admin_edit_user(self):
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a user to edit.")
            return
        user_id = selected[0]
        user_doc = db.collection("users").document(user_id).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            self.user_form_window(user_id=user_id, user_data=user_data)

    def admin_delete_user(self):
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a user to delete.")
            return
        user_id = selected[0]
        confirm = messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this user?")
        if confirm:
            db.collection("users").document(user_id).delete()
            self.load_users()

    def user_form_window(self, user_id=None, user_data=None):
        form = tk.Toplevel(self.root)
        form.title("User Form")
        form.geometry("350x300")

        ttk.Label(form, text="Email:").pack(pady=5)
        email_entry = ttk.Entry(form)
        email_entry.pack()
        if user_data:
            email_entry.insert(0, user_data.get("email"))
            if user_id:
                email_entry.config(state='disabled')

        ttk.Label(form, text="Name:").pack(pady=5)
        name_entry = ttk.Entry(form)
        name_entry.pack()
        if user_data:
            name_entry.insert(0, user_data.get("name", ""))

        ttk.Label(form, text="Password:").pack(pady=5)
        password_entry = ttk.Entry(form, show="*")
        password_entry.pack()
        if user_data:
            password_entry.insert(0, user_data.get("password"))

        ttk.Label(form, text="Role (admin/user):").pack(pady=5)
        role_entry = ttk.Entry(form)
        role_entry.pack()
        if user_data:
            role_entry.insert(0, user_data.get("role", "user"))

        def submit():
            email = email_entry.get().strip()
            name = name_entry.get().strip()
            password = password_entry.get().strip()
            role = role_entry.get().strip().lower()

            if not validate_email(email):
                messagebox.showerror("Error", "Invalid email format")
                return
            if not validate_password(password):
                messagebox.showerror("Error", f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
                return
            if role not in ["admin", "user"]:
                messagebox.showerror("Error", "Role must be 'admin' or 'user'")
                return

            # Check duplicate emails for new user
            if not user_id:
                existing_users = db.collection("users").where("email", "==", email).get()
                if existing_users:
                    messagebox.showerror("Error", "Email already exists")
                    return

            user_obj = {"email": email, "name": name, "password": password, "role": role}

            try:
                if user_id:
                    db.collection("users").document(user_id).set(user_obj)
                else:
                    db.collection("users").add(user_obj)
                self.load_users()
                form.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save user: {e}")

        ttk.Button(form, text="Submit", command=submit).pack(pady=10)

    def load_batches(self):
        self.batches_tree.delete(*self.batches_tree.get_children())
        batches = db.collection("batches").stream()
        for batch in batches:
            data = batch.to_dict()
            test_date_str = data.get("test_date", "")
            if isinstance(test_date_str, datetime):
                test_date_str = test_date_str.strftime("%Y-%m-%d")
            self.batches_tree.insert("", "end", iid=batch.id,
                                     values=(data.get("product_id", ""),
                                             data.get("product_name", ""),
                                             data.get("description", ""),
                                             test_date_str,
                                             data.get("user_email", ""),
                                             data.get("status", "pending")))

    def admin_approve_batch(self):
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
                batch_ref.update({"status": "approved"})
                self.load_batches()

    def logout(self):
        confirm = messagebox.askyesno("Logout", "Are you sure you want to logout?")
        if confirm:
            self.current_user = None
            self.login_screen()

    # -------- USER DASHBOARD --------
    def user_dashboard(self):

        self.clear_root()
        self.root.geometry("1000x600")
        self.excel_imported = False

        ttk.Label(self.root, text="Welcome to the User Dashboard!", font=("Helvetica", 16)).pack(pady=20)

        # === Menu Bar ===
        menubar = tk.Menu(self.root)

        # File Menu
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Import Excel", command=self.import_excel)
        filemenu.add_command(label="Export Excel", command=self.export_excel)
        filemenu.add_separator()
        filemenu.add_command(label="Logout", command=self.logout)
        menubar.add_cascade(label="File", menu=filemenu)

        # Reports Menu
        # reportmenu = tk.Menu(menubar, tearoff=0)
        # reportmenu.add_command(label="Audit Log", command=self.show_audit_log)
        # reportmenu.add_command(label="Summary Report", command=self.show_summary_report)
        # menubar.add_cascade(label="Reports", menu=reportmenu)

        self.root.config(menu=menubar)

        # === Toolbar Frame for Buttons ===
        toolbar = tk.Frame(self.root)
        toolbar.pack(pady=10)

        tk.Button(toolbar, text="Generate Barcode", command=self.generate_barcode).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="Check Notifications", command=self.check_notifications).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="Add Sample", command=self.add_sample).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="Edit Sample", command=self.edit_sample).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="Delete Sample", command=self.delete_sample).pack(side=tk.LEFT, padx=5)

        # === Treeview for Data Display ===
        self.tree = ttk.Treeview(self.root, columns=("SampleID", "Owner", "MaturationDate", "Status"), show='headings')
        self.tree.heading("SampleID", text="Sample ID")
        self.tree.heading("Owner", text="Sample Owner")
        self.tree.heading("MaturationDate", text="Maturation Date")
        self.tree.heading("Status", text="Status")
        self.tree.pack(expand=True, fill=tk.BOTH, pady=10)

        # === Status Bar ===
        self.status_label = tk.Label(self.root, text="Load a file to get started.", anchor='w')
        self.status_label.pack(fill=tk.X, padx=10, pady=5)

    def import_excel(self):
        filetypes = (("Excel files", "*.xlsx *.xls"), ("All files", "*.*"))
        filename = filedialog.askopenfilename(title="Open Excel file", filetypes=filetypes)
        if filename:
            try:
                self.data = pd.read_excel(filename)
                self.file_path = filename
                self.refresh_tree()
                self.status_label.config(text=f"Loaded data from {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load Excel file:\n{e}")

    def export_excel(self):
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
        self.tree.delete(*self.tree.get_children())
        for _, row in self.data.iterrows():
            # Expect columns: SampleID, Owner, MaturationDate
            mat_date = row['MaturationDate']
            if isinstance(mat_date, pd.Timestamp):
                mat_date = mat_date.strftime("%Y-%m-%d")
            self.tree.insert("", tk.END, values=(row['SampleID'], row['Owner'], mat_date, row['Status']))

    def generate_barcode(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a sample from the list.")
            return
        item = self.tree.item(selected[0])
        sample_id = item['values'][0]

        try:
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
        if self.data.empty:
            messagebox.showwarning("Warning", "No data loaded.")
            return

        today = datetime.now()
        notifications = []

        for _, row in self.data.iterrows():
            mat_date = row['MaturationDate']
            if not pd.isnull(mat_date):
                if isinstance(mat_date, pd.Timestamp):
                    mat_date = mat_date.to_pydatetime()
                delta = mat_date - today
                if 0 <= delta.days <= NOTIFICATION_DAYS_BEFORE:
                    notifications.append(f"Sample {row['SampleID']} owned by {row['Owner']} matures on {mat_date.strftime('%Y-%m-%d')}")

        if notifications:
            messagebox.showinfo("Notifications", "\n".join(notifications))
        else:
            messagebox.showinfo("Notifications", "No samples maturing within 2 months.")

    def add_sample(self):
        if self.data.empty:
            messagebox.showwarning("Warning", "Please import data before adding samples.")
            return

        form = tk.Toplevel(self.root)
        form.title("Add New Sample")
        form.geometry("300x200")

        tk.Label(form, text="Sample ID:").pack(pady=5)
        entry_sample_id = tk.Entry(form)
        entry_sample_id.pack()

        tk.Label(form, text="Sample Owner:").pack(pady=5)
        entry_owner = tk.Entry(form)
        entry_owner.pack()

        tk.Label(form, text="Maturation Date (YYYY-MM-DD):").pack(pady=5)
        entry_date = tk.Entry(form)
        entry_date.pack()

        def submit():
            sample_id = entry_sample_id.get().strip()
            owner = entry_owner.get().strip()
            date_str = entry_date.get().strip()

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

            new_row = {'SampleID': sample_id, 'Owner': owner, 'MaturationDate': mat_date}
            self.data = pd.concat([self.data, pd.DataFrame([new_row])], ignore_index=True)
            self.refresh_tree()

            try:
                db.collection("samples").add({
                    "SampleID": sample_id,
                    "Owner": owner,
                    "MaturationDate": mat_date.strftime("%Y-%m-%d"),
                    "CreatedBy": self.current_user["email"]
                })
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save to Firebase:\n{e}")

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

    def delete_sample(self):
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

            try:
                docs = db.collection("samples").where("SampleID", "==", sample_id).stream()
                for doc in docs:
                    db.collection("samples").document(doc.id).delete()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete from Firebase:\n{e}")

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
        form.geometry("300x200")

        tk.Label(form, text="Sample ID:").pack(pady=5)
        entry_sample_id = tk.Entry(form)
        entry_sample_id.insert(0, row['SampleID'])
        entry_sample_id.config(state='disabled')
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

        def submit():
            owner = entry_owner.get().strip()
            date_str = entry_date.get().strip()

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
            self.refresh_tree()

            try:
                docs = db.collection("samples").where("SampleID", "==", sample_id).stream()
                for doc in docs:
                    db.collection("samples").document(doc.id).update({
                        "Owner": owner,
                        "MaturationDate": mat_date.strftime("%Y-%m-%d")
                    })
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update Firebase:\n{e}")

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

    def load_samples(self):
        try:
            self.samples_tree.delete(*self.samples_tree.get_children())

            # If Excel file exists and has data
            if hasattr(self, "data") and not self.data.empty:
                for _, row in self.data.iterrows():
                    self.samples_tree.insert("", "end", values=(
                        row["SampleID"],
                        row["Owner"],
                        row["MaturationDate"],
                        self.current_user["email"]  # or row.get("CreatedBy", "")
                    ))
            else:
                # Load from Firebase filtered by current user
                docs = db.collection("samples").where("CreatedBy", "==", self.current_user["email"]).stream()
                firebase_rows = []

                for doc in docs:
                    d = doc.to_dict()
                    firebase_rows.append({
                        "SampleID": d.get("SampleID", ""),
                        "Owner": d.get("Owner", ""),
                        "MaturationDate": d.get("MaturationDate", ""),
                        "CreatedBy": d.get("CreatedBy", "")
                    })

                # Optionally store in self.data for in-memory reference
                self.data = pd.DataFrame(firebase_rows)

                for row in firebase_rows:
                    self.samples_tree.insert("", "end", values=(
                        row["SampleID"],
                        row["Owner"],
                        row["MaturationDate"],
                        row["CreatedBy"]
                    ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load samples:\n{e}")

    def logout(self):
        confirm = messagebox.askyesno("Logout", "Are you sure you want to logout?")
        if confirm:
            self.current_user = None
            self.login_screen()


    # -------- UTIL --------
    def clear_root(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    # -------- TESTER DASHBOARD ---------

if __name__ == "__main__":
    root = tk.Tk()
    app = ShelfLifeApp(root)
    root.mainloop()
