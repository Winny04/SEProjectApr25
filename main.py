import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import re
import pandas as pd
from datetime import datetime
import barcode
from barcode.writer import ImageWriter
import firebase_admin
from firebase_admin import credentials, firestore
import os
from pathlib import Path

# ---------------- FIREBASE SETUP ----------------
cred = credentials.Certificate("firebase_config.json")  # TODO: put your path here
firebase_admin.initialize_app(cred)
db = firestore.client()

# ---------------- CONSTANTS ----------------
EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")
MIN_PASSWORD_LENGTH = 6


# ---------------- HELPERS ----------------
def validate_email(email):
    return EMAIL_REGEX.match(email) is not None


def validate_password(password):
    return len(password) >= MIN_PASSWORD_LENGTH


def generate_barcode(sample_id, save_dir):
    EAN = barcode.get_barcode_class('code128')
    ean = EAN(sample_id, writer=ImageWriter())
    file_path = os.path.join(save_dir, f"{sample_id}_barcode.png")
    ean.save(file_path)
    return file_path


# ---------------- MAIN APP ----------------
class ShelfLifeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Shelf-life Study Management System")

        self.current_user = None  # dictionary with user info from Firestore

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

        ttk.Label(self.root, text="Welcome to the Admin Dashboard!", font=("Helvetica", 16)).pack(pady=20)

        tab_control = ttk.Notebook(self.root)
        tab_users = ttk.Frame(tab_control)
        tab_batches = ttk.Frame(tab_control)

        tab_control.add(tab_users, text="Manage Users")
        tab_control.add(tab_batches, text="Approve Batches")
        tab_control.pack(expand=1, fill="both")

        # USERS TAB
        self.users_tree = ttk.Treeview(tab_users, columns=("Email", "Name", "Role"), show='headings')
        for col in ("Email", "Name", "Role"):
            self.users_tree.heading(col, text=col)
        self.users_tree.pack(expand=True, fill="both", padx=10, pady=10)

        btn_frame = ttk.Frame(tab_users)
        btn_frame.pack(pady=5)

        ttk.Button(btn_frame, text="Add User", command=self.admin_add_user).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Edit User", command=self.admin_edit_user).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Delete User", command=self.admin_delete_user).pack(side="left", padx=5)

        self.load_users()

        # BATCHES TAB
        self.batches_tree = ttk.Treeview(tab_batches, columns=("ProductID", "Name", "Description", "TestDate", "User", "Status"), show='headings')
        for col in ("ProductID", "Name", "Description", "TestDate", "User", "Status"):
            self.batches_tree.heading(col, text=col)
        self.batches_tree.pack(expand=True, fill="both", padx=10, pady=10)

        btn_batch_frame = ttk.Frame(tab_batches)
        btn_batch_frame.pack(pady=5)

        ttk.Button(btn_batch_frame, text="Approve Batch", command=self.admin_approve_batch).pack(side="left", padx=5)
        ttk.Button(btn_batch_frame, text="Export Approved Batches", command=self.export_user_batches).pack(side="left", padx=5)

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

        # Import Excel and other buttons
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=5)

        ttk.Button(btn_frame, text="Import Excel", command=self.import_excel).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="Export Approved Batches", command=self.export_user_batches).pack(side="left",
                                                                                                     padx=10)
        ttk.Button(btn_frame, text="Export Selected Barcode", command=self.export_selected_barcode).pack(side="left",
                                                                                                         padx=10)
        ttk.Button(btn_frame, text="Logout", command=self.logout).pack(side="right", padx=10)

        # Frame to show imported Excel data
        self.excel_data_frame = ttk.Frame(self.root)
        self.excel_data_frame.pack(pady=10, fill="both", expand=True)

        if not self.excel_imported:
            ttk.Label(self.excel_data_frame, text="Please import an Excel file before adding batches.").pack()
        else:
            self.show_excel_data()  # show Excel data in treeview if imported

        # Batch form
        form_frame = ttk.Frame(self.root)
        form_frame.pack(pady=10, fill="x", padx=20)

        ttk.Label(form_frame, text="Product ID:").grid(row=0, column=0, sticky="e")
        self.product_id_entry = ttk.Entry(form_frame, width=30)
        self.product_id_entry.grid(row=0, column=1)

        ttk.Label(form_frame, text="Product Name:").grid(row=1, column=0, sticky="e")
        self.product_name_entry = ttk.Entry(form_frame, width=30)
        self.product_name_entry.grid(row=1, column=1)

        ttk.Label(form_frame, text="Description:").grid(row=2, column=0, sticky="e")
        self.description_entry = ttk.Entry(form_frame, width=30)
        self.description_entry.grid(row=2, column=1)

        ttk.Label(form_frame, text="Test Date (YYYY-MM-DD):").grid(row=3, column=0, sticky="e")
        self.test_date_entry = ttk.Entry(form_frame, width=30)
        self.test_date_entry.grid(row=3, column=1)

        ttk.Button(form_frame, text="Add Batch", command=self.add_batch).grid(row=4, column=0, columnspan=2, pady=10)

        # User batches treeview (keep but do NOT load batches now)
        ttk.Label(self.root, text="Your Batches:").pack()
        self.user_batches_tree = ttk.Treeview(self.root,
                                              columns=("ProductID", "Name", "Description", "TestDate", "Status"),
                                              show='headings')
        for col in ("ProductID", "Name", "Description", "TestDate", "Status"):
            self.user_batches_tree.heading(col, text=col)
        self.user_batches_tree.pack(expand=True, fill="both", padx=10, pady=10)

    def import_excel(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Excel files", "*.xlsx *.xls")],
            title="Select Excel File"
        )
        if not filepath:
            return

        try:
            df = pd.read_excel(filepath)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read Excel file:\n{e}")
            return

        required_cols = ["ProductID", "ProductName", "Description", "TestDate"]
        for col in required_cols:
            if col not in df.columns:
                messagebox.showerror("Error", f"Missing required column: {col}")
                return

        if hasattr(self, 'import_tree'):
            self.import_tree.destroy()

        self.import_tree = ttk.Treeview(self.excel_data_frame, columns=required_cols, show='headings')
        for col in required_cols:
            self.import_tree.heading(col, text=col)
            self.import_tree.column(col, width=150)
        self.import_tree.pack(expand=True, fill="both", padx=10, pady=10)

        for _, row in df.iterrows():
            test_date_val = row["TestDate"]
            if pd.notna(test_date_val) and hasattr(test_date_val, 'strftime'):
                test_date_val = test_date_val.strftime("%Y-%m-%d")
            else:
                test_date_val = ""

            self.import_tree.insert("", "end", values=(
                row["ProductID"],
                row["ProductName"],
                row.get("Description", ""),
                test_date_val
            ))

        self.excel_data = df  # save the dataframe if needed
        self.excel_imported = True  # mark Excel imported
        messagebox.showinfo("Success", "Excel data imported and displayed successfully!")
        self.load_user_batches()
        self.auto_export_approved_batches()

    def add_batch(self):

        if not getattr(self, "excel_imported", False):
            messagebox.showwarning("Warning", "Please import an Excel file first.")
            return

        pid = self.product_id_entry.get().strip()
        pname = self.product_name_entry.get().strip()
        desc = self.description_entry.get().strip()
        test_date_str = self.test_date_entry.get().strip()

        if not pid or not pname or not test_date_str:
            messagebox.showerror("Error", "Product ID, Name and Test Date are required.")
            return

        try:
            test_date = datetime.strptime(test_date_str, "%Y-%m-%d")
        except:
            messagebox.showerror("Error", "Test Date must be in YYYY-MM-DD format")
            return

        batch_obj = {
            "product_id": pid,
            "product_name": pname,
            "description": desc,
            "test_date": test_date,
            "user_email": self.current_user["email"],
            "status": "pending"
        }
        try:
            db.collection("batches").add(batch_obj)
            messagebox.showinfo("Success", "Batch added successfully!")
            self.product_id_entry.delete(0, tk.END)
            self.product_name_entry.delete(0, tk.END)
            self.description_entry.delete(0, tk.END)
            self.test_date_entry.delete(0, tk.END)
            self.load_user_batches()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add batch: {e}")

    def export_user_batches(self):
        approved_batches = db.collection("batches") \
            .where("user_email", "==", self.current_user["email"]) \
            .where("status", "==", "approved") \
            .stream()

        export_data = []
        downloads_path = str(Path.home() / "Downloads")
        export_dir = os.path.join(downloads_path, "exported_batches")
        os.makedirs(export_dir, exist_ok=True)

        for batch in approved_batches:
            data = batch.to_dict()
            test_date_str = data.get("test_date", "")
            if isinstance(test_date_str, datetime):
                test_date_str = test_date_str.strftime("%Y-%m-%d")

            # Generate barcode
            barcode_value = f"{data.get('product_id', '')}-{test_date_str}"
            filename = os.path.join(export_dir, f"{barcode_value}.png")
            barcode_obj = barcode.get_barcode_class("code128")
            barcode_obj(barcode_value, writer=ImageWriter()).save(filename)

            export_data.append({
                "ProductID": data.get("product_id", ""),
                "ProductName": data.get("product_name", ""),
                "Description": data.get("description", ""),
                "TestDate": test_date_str,
                "BarcodeImage": filename
            })

        if export_data:
            df = pd.DataFrame(export_data)
            export_filename = os.path.join(export_dir, f"approved_batches_{self.current_user['email'].replace('@', '_')}.xlsx")
            df.to_excel(export_filename, index=False)
            messagebox.showinfo("Exported", f"Approved batches exported to: {export_filename}")
        else:
            messagebox.showinfo("Info", "No approved batches to export.")

    def export_selected_barcode(self):
        selected = self.user_batches_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a batch.")
            return

        batch_id = selected[0]
        batch_ref = db.collection("batches").document(batch_id).get()

        if not batch_ref.exists:
            messagebox.showerror("Error", "Selected batch not found.")
            return

        data = batch_ref.to_dict()
        if data.get("status") != "approved":
            messagebox.showwarning("Warning", "Only approved batches can be exported.")
            return

        test_date_str = data.get("test_date", "")
        if isinstance(test_date_str, datetime):
            test_date_str = test_date_str.strftime("%Y-%m-%d")

        barcode_value = f"{data.get('product_id', '')}-{test_date_str}"
        downloads_path = str(Path.home() / "Downloads")
        export_dir = os.path.join(downloads_path, "exported_batches")
        os.makedirs(export_dir, exist_ok=True)

        filename = os.path.join(export_dir, f"{barcode_value}.png")
        barcode_obj = barcode.get_barcode_class("code128")
        barcode_obj(barcode_value, writer=ImageWriter()).save(filename)

        messagebox.showinfo("Success", f"Barcode saved to: {filename}")

    def logout(self):
        self.current_user = None
        self.clear_root()
        self.login_screen()

    def load_user_batches(self):
        self.user_batches_tree.delete(*self.user_batches_tree.get_children())
        batches = db.collection("batches").where("user_email", "==", self.current_user["email"]).stream()
        for batch in batches:
            data = batch.to_dict()
            test_date_str = data.get("test_date", "")
            if isinstance(test_date_str, datetime):
                test_date_str = test_date_str.strftime("%Y-%m-%d")
            self.user_batches_tree.insert("", "end", iid=batch.id,
                                         values=(data.get("product_id", ""),
                                                 data.get("product_name", ""),
                                                 data.get("description", ""),
                                                 test_date_str,
                                                 data.get("status", "pending")))

    def auto_export_approved_batches(self):
        approved_batches = db.collection("batches") \
            .where("user_email", "==", self.current_user["email"]) \
            .where("status", "==", "approved") \
            .stream()

        export_data = []
        export_dir = os.path.join(os.path.expanduser("~"), "Downloads", "ApprovedBatches")
        os.makedirs(export_dir, exist_ok=True)

        for batch in approved_batches:
            data = batch.to_dict()
            test_date_str = data.get("test_date", "")
            if isinstance(test_date_str, datetime):
                test_date_str = test_date_str.strftime("%Y-%m-%d")

            barcode_value = f"{data.get('product_id', '')}-{test_date_str}"
            barcode_filename = os.path.join(export_dir, f"{barcode_value}.png")
            barcode_class = barcode.get_barcode_class("code128")
            barcode_class(barcode_value, writer=ImageWriter()).save(barcode_filename)

            export_data.append({
                "ProductID": data.get("product_id", ""),
                "ProductName": data.get("product_name", ""),
                "Description": data.get("description", ""),
                "TestDate": test_date_str,
                "BarcodeImage": barcode_filename
            })

        if export_data:
            date_str = datetime.now().strftime("%Y%m%d")
            filename = f"approved_batches_{self.current_user['email'].replace('@', '_')}_{date_str}.xlsx"
            filepath = os.path.join(export_dir, filename)

            df = pd.DataFrame(export_data)
            df.to_excel(filepath, index=False)
            messagebox.showinfo("Exported", f"Approved batches auto-exported to:\n{filepath}")

    # -------- UTIL --------
    def clear_root(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    # -------- TESTER DASHBOARD ---------

if __name__ == "__main__":
    root = tk.Tk()
    app = ShelfLifeApp(root)
    root.mainloop()
