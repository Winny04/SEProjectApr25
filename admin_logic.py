import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import pandas as pd
from datetime import datetime 
import os
from firebase_setup import db
import firebase_admin 

class AdminLogic:
    def __init__(self, root, app_instance):
        self.root = root
        self.app = app_instance
        self.users_tree = None
        self.batches_tree = None

    def admin_dashboard(self):
        """Displays the admin dashboard with user and batch management."""
        print("\n--- Initializing Admin Dashboard ---")
        self.app.clear_root()
        self.root.geometry("1200x700")

        # Top frame for Logout button and Welcome message
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(top_frame, text="Logout", command=self.app.logout).pack(side="right")
        ttk.Label(top_frame, text=f"Welcome, Admin {self.app.current_user.get('username')}!",
                  font=("Helvetica", 16)).pack(side="left", expand=True)

        # Users Section
        ttk.Label(self.root, text="User Management", font=("Helvetica", 14, "bold")).pack(pady=(20, 5))
        self.users_tree = ttk.Treeview(self.root, columns=("EmployeeID", "Username", "Email", "Role", "Status"),
                                       show='headings')
        self.users_tree.heading("EmployeeID", text="Employee ID")
        self.users_tree.heading("Username", text="Username")
        self.users_tree.heading("Email", text="Email")
        self.users_tree.heading("Role", text="Role")
        self.users_tree.heading("Status", text="Status")  # New: Status heading

        self.users_tree.column("EmployeeID", width=120, anchor="center")
        self.users_tree.column("Username", width=120, anchor="center")
        self.users_tree.column("Email", width=200, anchor="center")
        self.users_tree.column("Role", width=80, anchor="center")
        self.users_tree.column("Status", width=80, anchor="center")

        self.users_tree.pack(expand=True, fill="both", padx=10, pady=10)

        btn_user_frame = ttk.Frame(self.root)
        btn_user_frame.pack(pady=5)

        ttk.Button(btn_user_frame, text="Add User", command=self.admin_add_user).pack(side="left", padx=5)
        ttk.Button(btn_user_frame, text="Edit User", command=self.admin_edit_user).pack(side="left", padx=5)
        ttk.Button(btn_user_frame, text="Delete User", command=self.admin_delete_user).pack(side="left", padx=5)
        ttk.Button(btn_user_frame, text="Approve User", command=self.admin_approve_user).pack(side="left",
                                                                                                padx=5) 

        self.load_users()

        # Batches Section
        ttk.Label(self.root, text="Batch Approval", font=("Helvetica", 14, "bold")).pack(pady=(20, 5))
        self.batches_tree = ttk.Treeview(self.root,
                                         columns=(
                                             "BatchID", "Product Name", "Description", "Maturation Date", "User",
                                             "Status",
                                             "Sample Count"),
                                         show='headings')
        # Updated heading for the date column to 'Maturation Date'
        self.batches_tree.heading("Maturation Date", text="Maturation Date")
        # Ensure all other columns are also correctly configured
        for col_name in ["BatchID", "Product Name", "Description", "User", "Status", "Sample Count"]:
            self.batches_tree.heading(col_name, text=col_name)
            self.batches_tree.column(col_name, width=100, anchor="center")
        # Adjust column width for Maturation Date if necessary
        self.batches_tree.column("Maturation Date", width=120, anchor="center")

        self.batches_tree.pack(expand=True, fill="both", padx=10, pady=10)

        btn_batch_frame = ttk.Frame(self.root)
        btn_batch_frame.pack(pady=5)

        ttk.Button(btn_batch_frame, text="Approve Batch", command=self.admin_approve_batch).pack(side="left", padx=5)
        ttk.Button(btn_batch_frame, text="Export Approved Batches", command=self.export_user_batches).pack(side="left",
                                                                                                            padx=5)

        self.load_batches()
        print("--- Admin Dashboard Initialized ---")

    def load_users(self):
        """Loads user data from Firestore and populates the users treeview."""
        print("--- AdminLogic: Attempting to load users ---")
        if self.users_tree is None:
            print("AdminLogic: users_tree is None. Admin dashboard not initialized. Skipping user load.")
            return

        self.users_tree.delete(*self.users_tree.get_children())
        users = db.collection("users").stream()
        for user in users:
            data = user.to_dict()
            self.users_tree.insert("", "end", iid=user.id,
                                   values=(data.get("employee_id"), data.get("username", ""),
                                           data.get("email"), data.get("role"),
                                           data.get("status", "active" if data.get("role") == "admin" else "pending")))
        print("--- AdminLogic: Users loaded ---")

    def admin_add_user(self):
        """Opens a form to add a new user by delegating to AuthManager."""
        self.app.auth_manager.user_form_window()

    def admin_edit_user(self):
        """Opens a form to edit an existing user by delegating to AuthManager."""
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a user to edit.")
            return
        user_id = selected[0]
        user_doc = db.collection("users").document(user_id).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            self.app.auth_manager.user_form_window(user_id=user_id, user_data=user_data)

    def admin_delete_user(self):
        """Deletes a selected user from Firestore."""
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a user to delete.")
            return
        user_id = selected[0]
        confirm = messagebox.askyesno("Confirm Delete",
                                     f"Are you sure you want to delete user with Employee ID '{user_id}'?")
        if confirm:
            try:
                db.collection("users").document(user_id).delete()
                messagebox.showinfo("Success", "User deleted successfully.")
                self.load_users()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete user: {e}")

    def admin_approve_user(self):
        """Approves a selected user by changing their status to 'active'."""
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a user to approve.")
            return
        user_id = selected[0]
        user_doc = db.collection("users").document(user_id).get()

        if not user_doc.exists:
            messagebox.showerror("Error", "User not found.")
            return

        user_data = user_doc.to_dict()
        if user_data.get("status") == "active":
            messagebox.showinfo("Info", "User is already active.")
            return

        confirm = messagebox.askyesno("Confirm Approval",
                                     f"Are you sure you want to approve user '{user_data.get('username')}'?")
        if confirm:
            try:
                db.collection("users").document(user_id).update({"status": "active"})
                messagebox.showinfo("Success", f"User '{user_data.get('username')}' approved successfully.")
                self.load_users()  # Refresh the user list
            except Exception as e:
                messagebox.showerror("Error", f"Failed to approve user: {e}")

    def load_batches(self):
        """Loads batch data from Firestore and populates the batches treeview."""
        print("--- AdminLogic: Attempting to load batches ---")
        if self.batches_tree is None:
            print("AdminLogic: batches_tree is None. Admin dashboard not initialized. Skipping batch load.")
            return
            
        self.batches_tree.delete(*self.batches_tree.get_children())
        # Query for batches with status "pending"
        batches = db.collection("batches").where("status", "==", "pending").stream()
        for batch in batches:
            data = batch.to_dict()
            # Firestore automatically converts Timestamps to datetime objects when using .to_dict()
            maturation_date_str = data.get("maturation_date", "")

            # Check if it's already a datetime object (which it should be if from Firestore Timestamp)
            if isinstance(maturation_date_str, datetime):
                maturation_date_str = maturation_date_str.strftime("%Y-%m-%d")
            else:
                # Fallback for anything else (e.g., if it's a string or None initially)
                maturation_date_str = str(maturation_date_str) if maturation_date_str is not None else ''

            self.batches_tree.insert("", "end", iid=batch.id,  # batch.id is the document ID from Firestore
                                     values=(data.get("batch_id", ""),
                                             data.get("product_name", ""),
                                             data.get("description", ""),
                                             maturation_date_str,  # Using the formatted maturation_date_str
                                             data.get("user_email", ""),
                                             data.get("status", "pending"),
                                             data.get("number_of_samples", 0)))
        print("--- AdminLogic: Batches loaded ---")

    def admin_approve_batch(self):
        """Approves a selected batch in Firestore and updates associated samples."""
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

            confirm = messagebox.askyesno("Confirm Approve",
                                         "Approve this batch? This will also update the status of associated samples.")
            if confirm:
                try:
                    batch_write = db.batch()

                    batch_write.update(batch_ref, {"status": "approved"})

                    samples_ref = db.collection("samples")
                    associated_samples = samples_ref.where("batch_id", "==", batch_id).stream()

                    sample_count_updated = 0
                    for sample in associated_samples:
                        sample_ref = db.collection("samples").document(sample.id)
                        batch_write.update(sample_ref, {"status": "approved"})
                        sample_count_updated += 1

                    batch_write.commit()

                    messagebox.showinfo("Success",
                                         f"Batch approved successfully. {sample_count_updated} samples updated.")
                    self.load_batches()
                    # Also refresh user's sample view if they are on their dashboard
                    if self.app.current_user and self.app.current_user.get('role') == 'user':
                        # Ensure user_logic is initialized and has load_samples_from_db method
                        if hasattr(self.app, 'user_logic') and callable(
                                getattr(self.app.user_logic, 'load_all_user_samples_from_db', None)): # Corrected method name
                            self.app.user_logic.load_all_user_samples_from_db()
                        else:
                            print("Warning: user_logic or load_all_user_samples_from_db not found on app instance.")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to approve batch: {e}")

    def export_user_batches(self):
        """Exports approved batches and their associated samples to an Excel file."""
        approved_batches_data = []
        batches_ref = db.collection("batches")
        samples_ref = db.collection("samples")

        # It's better to fetch approved batches directly here if "status" is indexed
        approved_batches = batches_ref.where("status", "==", "approved").get()

        if not approved_batches:
            messagebox.showwarning("Warning", "No approved batches to export.")
            return

        for batch in approved_batches:
            batch_data = batch.to_dict()
            batch_id = batch.id

            # Ensure 'test_date' is handled correctly, as it's used in the export schema
            if isinstance(batch_data.get('test_date'), firebase_admin.firestore.Timestamp):
                batch_data['test_date'] = batch_data['test_date'].to_datetime()
            # If batch_data.get('maturation_date') was used in load_batches, ensure it's also handled here for consistency
            if isinstance(batch_data.get('maturation_date'), firebase_admin.firestore.Timestamp):
                batch_data['maturation_date'] = batch_data['maturation_date'].to_datetime()

            associated_samples = samples_ref.where("batch_id", "==", batch_id).get()

            # It's important to have at least one entry even if no samples, so batch data is exported
            if not associated_samples:
                combined_data = {
                    "BatchID": batch_data.get("batch_id"),
                    "Product_Name": batch_data.get("product_name"),
                    "Batch_Description": batch_data.get("description"),
                    # Use 'test_date' for the batch here, or 'maturation_date' if that's what batch represents
                    "Batch_Test_Date": batch_data.get("test_date").strftime("%Y-%m-%d") if batch_data.get(
                        "test_date") else "",
                    "Batch_Status": batch_data.get("status"),
                    "User_Email": batch_data.get("user_email"),
                    "SampleID": "",  # Empty for no samples
                    "Sample_Owner": "",
                    "Sample_MaturationDate": "",
                    "Sample_Status": ""
                }
                approved_batches_data.append(combined_data)

            for sample in associated_samples:
                sample_data = sample.to_dict()
                if isinstance(sample_data.get('maturation_date'), firebase_admin.firestore.Timestamp):
                    mat_date_str = sample_data['maturation_date'].to_datetime().strftime("%Y-%m-%d")
                elif isinstance(sample_data.get('maturation_date'), datetime):
                    mat_date_str = sample_data['maturation_date'].strftime("%Y-%m-%d")
                else:
                    mat_date_str = str(sample_data.get('maturation_date', ''))

                combined_data = {
                    "BatchID": batch_data.get("batch_id"),
                    "Product_Name": batch_data.get("product_name"),
                    "Batch_Description": batch_data.get("description"),
                    "Batch_Test_Date": batch_data.get("test_date").strftime("%Y-%m-%d") if batch_data.get(
                        "test_date") else "",
                    "Batch_Status": batch_data.get("status"),
                    "User_Email": batch_data.get("user_email"),
                    "SampleID": sample_data.get("sample_id"),
                    "Sample_Owner": sample_data.get("owner"),
                    "Sample_MaturationDate": mat_date_str,
                    "Sample_Status": sample_data.get("status")
                }
                approved_batches_data.append(combined_data)

        if not approved_batches_data:
            messagebox.showwarning("Warning", "No approved batches with samples to export.")
            return

        df_approved_with_samples = pd.DataFrame(approved_batches_data)

        filetypes = (("Excel files", "*.xlsx"),)
        filename = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                                 filetypes=filetypes,
                                                 initialfile="Approved_Batches_and_Samples.xlsx")
        if filename:
            try:
                df_approved_with_samples.to_excel(filename, index=False)
                messagebox.showinfo("Success",
                                     f"Approved batches and their samples exported to {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export Excel file:\n{e}")

