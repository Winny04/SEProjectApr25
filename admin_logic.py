# admin_logic.py
import tkinter as tk
from tkinter import messagebox, ttk
import pandas as pd
from datetime import datetime
import os
from firebase_setup import db
import firebase_admin # Needed for firestore.Timestamp

class AdminLogic:
    def __init__(self, root, app_instance):
        self.root = root
        self.app = app_instance
        self.users_tree = None
        self.batches_tree = None

    def admin_dashboard(self):
        """Displays the admin dashboard with user and batch management."""
        self.app.clear_root()
        self.root.geometry("1200x700") 

        # Top frame for Logout button and Welcome message
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(top_frame, text="Logout", command=self.app.logout).pack(side="right")
        ttk.Label(top_frame, text=f"Welcome, Admin {self.app.current_user.get('username')}!", font=("Helvetica", 16)).pack(side="left", expand=True)

        # Users Section
        ttk.Label(self.root, text="User Management", font=("Helvetica", 14, "bold")).pack(pady=(20, 5))
        self.users_tree = ttk.Treeview(self.root, columns=("EmployeeID", "Username", "Email", "Role"), show='headings')
        self.users_tree.heading("EmployeeID", text="Employee ID")
        self.users_tree.heading("Username", text="Username")
        self.users_tree.heading("Email", text="Email")
        self.users_tree.heading("Role", text="Role")
        
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
                                         columns=("BatchID", "Product Name", "Description", "Test Date", "User", "Status", "Sample Count"),
                                         show='headings')
        for col in ("BatchID", "Product Name", "Description", "Test Date", "User", "Status", "Sample Count"):
            self.batches_tree.heading(col, text=col)
            self.batches_tree.column(col, width=100, anchor="center") 
        self.batches_tree.pack(expand=True, fill="both", padx=10, pady=10)

        btn_batch_frame = ttk.Frame(self.root)
        btn_batch_frame.pack(pady=5)

        ttk.Button(btn_batch_frame, text="Approve Batch", command=self.admin_approve_batch).pack(side="left", padx=5)
        ttk.Button(btn_batch_frame, text="Export Approved Batches", command=self.export_user_batches).pack(side="left", padx=5)

        self.load_batches()
        
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
        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete user with Employee ID '{user_id}'?")
        if confirm:
            try:
                db.collection("users").document(user_id).delete()
                messagebox.showinfo("Success", "User deleted successfully.")
                self.load_users()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete user: {e}")

    def load_batches(self):
        """Loads batch data from Firestore and populates the batches treeview."""
        self.batches_tree.delete(*self.batches_tree.get_children())
        batches = db.collection("batches").stream()
        for batch in batches:
            data = batch.to_dict()
            test_date_str = data.get("test_date", "")
            if isinstance(test_date_str, firebase_admin.firestore.Timestamp): # Use full path for Timestamp
                test_date_str = test_date_str.to_datetime().strftime("%Y-%m-%d")
            elif isinstance(test_date_str, datetime): 
                test_date_str = test_date_str.strftime("%Y-%m-%d")
            
            self.batches_tree.insert("", "end", iid=batch.id,
                                     values=(data.get("batch_id", ""), 
                                             data.get("product_name", ""),
                                             data.get("description", ""),
                                             test_date_str,
                                             data.get("user_email", ""), 
                                             data.get("status", "pending"),
                                             data.get("number_of_samples", 0)))

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

            confirm = messagebox.askyesno("Confirm Approve", "Approve this batch? This will also update the status of associated samples.")
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

                    messagebox.showinfo("Success", f"Batch approved successfully. {sample_count_updated} samples updated.")
                    self.load_batches() 
                    # Also refresh user's sample view if they are on their dashboard
                    if self.app.current_user and self.app.current_user.get('role') == 'user':
                        self.app.user_logic.load_samples_from_db() 
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to approve batch: {e}")

    def export_user_batches(self):
        """Exports approved batches and their associated samples to an Excel file."""
        approved_batches_data = []
        batches_ref = db.collection("batches")
        samples_ref = db.collection("samples")

        approved_batches = batches_ref.where("status", "==", "approved").get()

        if not approved_batches:
            messagebox.showwarning("Warning", "No approved batches to export.")
            return

        for batch in approved_batches:
            batch_data = batch.to_dict()
            batch_id = batch.id

            if isinstance(batch_data.get('test_date'), firebase_admin.firestore.Timestamp):
                batch_data['test_date'] = batch_data['test_date'].to_datetime()
            
            associated_samples = samples_ref.where("batch_id", "==", batch_id).get()
            
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
                    "Batch_Test_Date": batch_data.get("test_date").strftime("%Y-%m-%d") if batch_data.get("test_date") else "",
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
                messagebox.showinfo("Success", f"Approved batches and their samples exported to {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export Excel file:\n{e}")
