# admin_logic.py
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import pandas as pd
from datetime import datetime
import os
from firebase_setup import db
import firebase_admin

# --- Logging Setup ---
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- End Logging Setup ---

class AdminLogic:
    def __init__(self, root, app_instance):
        logging.info("Initializing AdminLogic class.")
        self.root = root
        self.app = app_instance
        self.users_tree = None
        self.batches_tree = None
        self.batch_filter_var = None  # Variable to hold the selected batch filter (All, Pending, Approved)

        style = ttk.Style()
        style.theme_use('clam')  # Better default look

        # Button styles
        style.configure("Green.TButton", background="#2ecc71", foreground="white", font=("Segoe UI", 10, "bold"))
        style.map("Green.TButton", background=[("active", "#27ae60")])

        style.configure("Yellow.TButton", background="#f1c40f", foreground="black", font=("Segoe UI", 10, "bold"))
        style.map("Yellow.TButton", background=[("active", "#f39c12")])

        style.configure("Orange.TButton", background="#e67e22", foreground="white", font=("Segoe UI", 10, "bold"))
        style.map("Orange.TButton", background=[("active", "#d35400")])

        style.configure("View.TButton", background="#3498db", foreground="white", font=("Segoe UI", 10, "bold"))
        style.map("View.TButton", background=[("active", "#2980b9")])
        logging.info("AdminLogic initialized.")

    def admin_dashboard(self):
        """Displays the admin dashboard with user and batch management."""
        logging.info("Entering admin_dashboard method.")
        self.app.clear_root()
        self.root.geometry("1200x700")

        # Top frame for Logout button and Welcome message
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(top_frame, text="Logout", command=self.app.logout).pack(side="right")
        ttk.Label(top_frame, text=f"Welcome, Admin {self.app.current_user.get('username')}!",
                  font=("Helvetica", 16)).pack(side="left", expand=True) # Added welcome message

        # Main content frame to hold sidebar and central content
        main_content_frame = ttk.Frame(self.root)
        main_content_frame.pack(expand=True, fill="both", padx=10, pady=10)

        # Sidebar Frame
        sidebar_frame = ttk.Frame(main_content_frame, width=200, relief="raised", borderwidth=1)
        sidebar_frame.pack(side="left", fill="y", padx=(0, 20))
        sidebar_frame.pack_propagate(False)  # Prevent sidebar from resizing based on content

        ttk.Label(sidebar_frame, text="Navigation", font=("Helvetica", 12, "bold")).pack(pady=10)

        # Sidebar buttons
        ttk.Button(sidebar_frame, text="User Management", command=self.show_user_management).pack(fill="x", pady=5,
                                                                                                  padx=10)
        ttk.Button(sidebar_frame, text="Batch Management", command=self.show_batch_management).pack(fill="x", pady=5,
                                                                                                    padx=10)
        ttk.Button(sidebar_frame, text="Export Approved Data", command=self.export_user_batches).pack(fill="x", pady=5,
                                                                                                      padx=10)

        # Central content area
        self.central_content_frame = ttk.Frame(main_content_frame)
        self.central_content_frame.pack(side="right", expand=True, fill="both")

        # Initially show user management
        self.show_user_management()
        logging.info("Admin dashboard loaded.")

    def clear_central_content(self):
        """Clears all widgets from the central content frame."""
        logging.info("Clearing central content frame.")
        for widget in self.central_content_frame.winfo_children():
            widget.destroy()
        logging.info("Central content frame cleared.")

    def show_user_management(self):
        """Displays the user management section in the central content frame."""
        logging.info("Displaying user management section.")
        self.clear_central_content()
        # Users Section
        ttk.Label(self.central_content_frame, text="User Management", font=("Helvetica", 14, "bold")).pack(pady=(20, 5))
        self.users_tree = ttk.Treeview(self.central_content_frame,
                                       columns=("EmployeeID", "Username", "Email", "Role", "Status"),
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

        btn_user_frame = ttk.Frame(self.central_content_frame)
        btn_user_frame.pack(pady=5)

        ttk.Button(btn_user_frame, text="Add User", command=self.admin_add_user, style="Green.TButton").pack(
            side="left", padx=5)
        ttk.Button(btn_user_frame, text="Edit User", command=self.admin_edit_user, style="View.TButton").pack(
            side="left", padx=5)
        ttk.Button(btn_user_frame, text="Delete User", command=self.admin_delete_user, style="Yellow.TButton").pack(
            side="left", padx=5)
        ttk.Button(btn_user_frame, text="Approve User", command=self.admin_approve_user, style="Green.TButton").pack(
            side="left", padx=5)

        self.load_users()
        logging.info("User management section displayed.")

    def show_batch_management(self):
        """Displays the batch management section in the central content frame, with a filter for status."""
        logging.info("Displaying batch management section.")
        self.clear_central_content()
        ttk.Label(self.central_content_frame, text="Batch Management", font=("Helvetica", 14, "bold")).pack(
            pady=(20, 5))

        # Filter controls
        filter_frame = ttk.Frame(self.central_content_frame)
        filter_frame.pack(pady=5)

        ttk.Label(filter_frame, text="Filter by Status:").pack(side="left", padx=5)
        self.batch_filter_var = tk.StringVar(value="pending approval")  # Default to pending approval
        filter_combobox = ttk.Combobox(filter_frame, textvariable=self.batch_filter_var,
                                       values=["pending approval", "approved", "all"],
                                       state="readonly")
        filter_combobox.pack(side="left", padx=5)
        filter_combobox.bind("<<ComboboxSelected>>", lambda event: self.load_batches(self.batch_filter_var.get()))

        self.batches_tree = ttk.Treeview(self.central_content_frame,
                                         columns=(
                                             "BatchID", "Product Name", "Description", "Submission Date", "User",
                                             "Status",
                                             "Sample Count"),
                                         show='headings')
        # Updated heading for the date column to 'Submission Date'
        self.batches_tree.heading("Submission Date", text="Submission Date")  # Changed heading text
        # Ensure all other columns are also correctly configured
        for col_name in ["BatchID", "Product Name", "Description", "User", "Status", "Sample Count"]:
            self.batches_tree.heading(col_name, text=col_name)
            self.batches_tree.column(col_name, width=100, anchor="center")
        # Adjust column width for Submission Date if necessary
        self.batches_tree.column("Submission Date", width=120, anchor="center")

        self.batches_tree.pack(expand=True, fill="both", padx=10, pady=10)

        btn_batch_frame = ttk.Frame(self.central_content_frame)
        btn_batch_frame.pack(pady=5)

        ttk.Button(btn_batch_frame, text="Approve Selected Batch", command=self.admin_approve_selected_batch,
                   style="Green.TButton").pack(side="left", padx=5)
        ttk.Button(btn_batch_frame, text="Reject Selected Batch", command=self.admin_reject_selected_batch,
                   style="Orange.TButton").pack(side="left", padx=5)
        ttk.Button(btn_batch_frame, text="View Samples", command=self.admin_view_samples_for_batch,
                   style="View.TButton").pack(side="left", padx=5)
        ttk.Button(btn_batch_frame, text="Delete Batch", command=self.delete_batch, style="Yellow.TButton").pack(
            side="left", padx=5)
        # add edit batch
        ttk.Button(btn_batch_frame, text="Edit Batch", command=self.edit_batch_info, style="Yellow.TButton").pack(
            side="left", padx=5)

        # Removed the "View Approved Batches" button here as well
        self.load_batches(self.batch_filter_var.get())  # Load batches based on initial filter value
        logging.info("Batch management section displayed.")

    def load_users(self):
        """Loads user data from Firestore and populates the users treeview."""
        logging.info("Attempting to load users.")
        if self.users_tree is None:
            logging.warning("users_tree is None. Admin dashboard not initialized. Skipping user load.")
            return

        self.users_tree.delete(*self.users_tree.get_children())
        try:
            users = db.collection("users").stream()
            for user in users:
                data = user.to_dict()
                self.users_tree.insert("", "end", iid=user.id,
                                       values=(data.get("employee_id"), data.get("username", ""),
                                               data.get("email"), data.get("role"),
                                               data.get("status", "active" if data.get("role") == "admin" else "pending")))
            logging.info("Users loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load users: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load users: {e}")

    def admin_add_user(self):
        """Opens a form to add a new user by delegating to AuthManager."""
        logging.info("Opening add user form.")
        self.app.auth_manager.user_form_window()
        logging.info("Add user form opened.")

    def admin_edit_user(self):
        """Opens a form to edit an existing user by delegating to AuthManager."""
        logging.info("Attempting to open edit user form.")
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a user to edit.")
            logging.warning("Edit user aborted: No user selected.")
            return
        user_id = selected[0]
        try:
            user_doc = db.collection("users").document(user_id).get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                self.app.auth_manager.user_form_window(user_id=user_id, user_data=user_data)
                logging.info(f"Edit user form opened for user ID: {user_id}.")
            else:
                messagebox.showerror("Error", "User not found.")
                logging.error(f"User with ID {user_id} not found for editing.")
        except Exception as e:
            logging.error(f"Failed to retrieve user data for editing: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to retrieve user data: {e}")

    def admin_delete_user(self):
        """Deletes a selected user from Firestore."""
        logging.info("Attempting to delete user.")
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a user to delete.")
            logging.warning("Delete user aborted: No user selected.")
            return
        user_id = selected[0]
        confirm = messagebox.askyesno("Confirm Delete",
                                      f"Are you sure you want to delete user with Employee ID '{user_id}'?")
        if confirm:
            try:
                db.collection("users").document(user_id).delete()
                messagebox.showinfo("Success", "User deleted successfully.")
                logging.info(f"User with ID {user_id} deleted successfully.")
                self.load_users()
            except Exception as e:
                logging.error(f"Failed to delete user {user_id}: {e}", exc_info=True)
                messagebox.showerror("Error", f"Failed to delete user: {e}")
        else:
            logging.info("Delete user cancelled by user.")

    def admin_approve_user(self):
        """Approves a selected user by changing their status to 'active'."""
        logging.info("Attempting to approve user.")
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a user to approve.")
            logging.warning("Approve user aborted: No user selected.")
            return
        user_id = selected[0]
        try:
            user_doc = db.collection("users").document(user_id).get()

            if not user_doc.exists:
                messagebox.showerror("Error", "User not found.")
                logging.error(f"User with ID {user_id} not found for approval.")
                return

            user_data = user_doc.to_dict()
            if user_data.get("status") == "active":
                messagebox.showinfo("Info", "User is already active.")
                logging.info(f"User {user_id} is already active, no action needed.")
                return

            confirm = messagebox.askyesno("Confirm Approval",
                                          f"Are you sure you want to approve user '{user_data.get('username')}'?")
            if confirm:
                db.collection("users").document(user_id).update({"status": "active"})
                messagebox.showinfo("Success", f"User '{user_data.get('username')}' approved successfully.")
                logging.info(f"User {user_id} approved successfully and status set to 'active'.")
                self.load_users()  # Refresh the user list
            else:
                logging.info("Approve user cancelled by user.")
        except Exception as e:
            logging.error(f"Failed to approve user {user_id}: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to approve user: {e}")

    def load_batches(self, status_filter="pending approval"):
        """Loads batch data from Firestore and populates the batches treeview.
           Can filter by status: "pending approval", "approved", or "all"."""
        logging.info(f"Attempting to load batches with filter: {status_filter}.")
        if self.batches_tree is None:
            logging.warning("batches_tree is None. Admin dashboard not initialized. Skipping batch load.")
            return

        self.batches_tree.delete(*self.batches_tree.get_children())

        batches_query = db.collection("batches")
        if status_filter and status_filter != "all":
            batches_query = batches_query.where("status", "==", status_filter)

        try:
            batches = batches_query.stream()

            for batch in batches:
                data = batch.to_dict()
                submission_date_str = data.get("submission_date", "")

                if isinstance(submission_date_str, datetime):
                    submission_date_str = submission_date_str.strftime("%Y-%m-%d")
                elif isinstance(submission_date_str, firebase_admin.firestore.Timestamp):
                    submission_date_str = submission_date_str.to_datetime().strftime("%Y-%m-%d")
                else:
                    submission_date_str = str(submission_date_str) if submission_date_str is not None else ''

                row_id = self.batches_tree.insert("", "end", iid=batch.id,
                                                  values=(data.get("batch_id", ""),
                                                          data.get("product_name", ""),
                                                          data.get("description", ""),
                                                          submission_date_str,
                                                          data.get("user_email", ""),
                                                          data.get("status", "pending approval"),
                                                          data.get("number_of_samples", 0)))

                # Apply row tag based on status
                status = data.get("status", "pending approval")
                if status == "approved":
                    self.batches_tree.item(row_id, tags=("approved",))
                elif status == "pending approval":
                    self.batches_tree.item(row_id, tags=("pending",))
                elif status == "rejected":
                    self.batches_tree.item(row_id, tags=("rejected",))

                # Define tag styles
                self.batches_tree.tag_configure("approved", background="#d4edda")  # light green
                self.batches_tree.tag_configure("pending", background="#fff3cd")  # light yellow
                self.batches_tree.tag_configure("rejected", background="#f8d7da")  # light red/orange

            logging.info(f"Batches loaded successfully with filter: {status_filter}.")
        except Exception as e:
            logging.error(f"Failed to load batches with filter {status_filter}: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load batches: {e}")

    def admin_approve_selected_batch(self):
        """Approves the selected batch and all its associated samples."""
        logging.info("Attempting to approve selected batch.")
        selected = self.batches_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a batch to approve.")
            logging.warning("Approve batch aborted: No batch selected.")
            return

        batch_doc_id = selected[0]
        try:
            batch_doc = db.collection("batches").document(batch_doc_id).get()

            if not batch_doc.exists:
                messagebox.showerror("Error", "Selected batch not found.")
                logging.error(f"Batch with document ID {batch_doc_id} not found for approval.")
                return

            batch_data = batch_doc.to_dict()
            if batch_data.get("status") == "approved":
                messagebox.showinfo("Info", "Batch is already approved.")
                logging.info(f"Batch {batch_doc_id} is already approved.")
                return

            confirm = messagebox.askyesno("Confirm Batch Approval",
                                          f"Are you sure you want to approve batch '{batch_data.get('product_name')}' (ID: {batch_data.get('batch_id')}) and all its samples?")
            if confirm:
                batch_write = db.batch()
                # Update batch status to approved
                batch_write.update(db.collection("batches").document(batch_doc_id), {"status": "approved"})
                logging.info(f"Prepared to set batch {batch_doc_id} status to 'approved'.")

                # Also approve all samples associated with this batch
                associated_samples = db.collection("samples").where("batch_id", "==", batch_data.get('batch_id')).stream() # Use batch_id field
                samples_updated_count = 0
                for sample in associated_samples:
                    batch_write.update(sample.reference, {"status": "approved"})
                    samples_updated_count += 1
                logging.info(f"Prepared to approve {samples_updated_count} samples for batch {batch_doc_id}.")

                batch_write.commit()
                messagebox.showinfo("Success",
                                    f"Batch '{batch_data.get('product_name')}' and all its samples approved successfully.")
                logging.info(f"Batch {batch_doc_id} and {samples_updated_count} samples approved successfully.")
                self.load_batches(self.batch_filter_var.get())  # Refresh the batches tree with current filter
            else:
                logging.info("Approve batch cancelled by user.")
        except Exception as e:
            logging.error(f"Failed to approve batch {batch_doc_id} and samples: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to approve batch and samples: {e}")

    def admin_reject_selected_batch(self):
        """Rejects the selected batch and all its associated samples."""
        logging.info("Attempting to reject selected batch.")
        selected = self.batches_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a batch to reject.")
            logging.warning("Reject batch aborted: No batch selected.")
            return

        batch_doc_id = selected[0]
        try:
            batch_doc = db.collection("batches").document(batch_doc_id).get()

            if not batch_doc.exists:
                messagebox.showerror("Error", "Selected batch not found.")
                logging.error(f"Batch with document ID {batch_doc_id} not found for rejection.")
                return

            batch_data = batch_doc.to_dict()
            if batch_data.get("status") == "rejected":
                messagebox.showinfo("Info", "Batch is already rejected.")
                logging.info(f"Batch {batch_doc_id} is already rejected.")
                return

            confirm = messagebox.askyesno("Confirm Batch Rejection",
                                          f"Are you sure you want to reject batch '{batch_data.get('product_name')}' (ID: {batch_data.get('batch_id')}) and all its samples?")
            if confirm:
                batch_write = db.batch()
                # Update batch status to rejected
                batch_write.update(db.collection("batches").document(batch_doc_id), {"status": "rejected"})
                logging.info(f"Prepared to set batch {batch_doc_id} status to 'rejected'.")

                # Also reject all samples associated with this batch
                associated_samples = db.collection("samples").where("batch_id", "==", batch_data.get('batch_id')).stream() # Use batch_id field
                samples_updated_count = 0
                for sample in associated_samples:
                    batch_write.update(sample.reference, {"status": "rejected"})
                    samples_updated_count += 1
                logging.info(f"Prepared to reject {samples_updated_count} samples for batch {batch_doc_id}.")

                batch_write.commit()
                messagebox.showinfo("Success",
                                    f"Batch '{batch_data.get('product_name')}' and all its samples rejected successfully.")
                logging.info(f"Batch {batch_doc_id} and {samples_updated_count} samples rejected successfully.")
                self.load_batches(self.batch_filter_var.get())  # Refresh the batches tree with current filter
            else:
                logging.info("Reject batch cancelled by user.")
        except Exception as e:
            logging.error(f"Failed to reject batch {batch_doc_id} and samples: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to reject batch and samples: {e}")

    def admin_view_samples_for_batch(self):
        """Opens a new window to display samples associated with the selected batch with pagination."""
        logging.info("Attempting to view samples for selected batch.")
        selected = self.batches_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a batch to view its samples.")
            logging.warning("View samples aborted: No batch selected.")
            return

        batch_doc_id = selected[0]
        try:
            batch_doc = db.collection("batches").document(batch_doc_id).get()

            if not batch_doc.exists:
                messagebox.showerror("Error", "Selected batch not found.")
                logging.error(f"Batch with document ID {batch_doc_id} not found for viewing samples.")
                return

            batch_data = batch_doc.to_dict()
            batch_id_from_doc = batch_data.get("batch_id")  # Get the 'batch_id' field from the batch document
            product_name = batch_data.get("product_name")
            # user_employee_id = batch_data.get("user_employee_id", "")  # Get user_employee_id from batch - not used here, so commented out

            if not batch_id_from_doc:
                messagebox.showerror("Error", "Batch ID not found for the selected batch.")
                logging.error(f"Batch ID field missing for batch document ID {batch_doc_id}.")
                return

            samples_window = tk.Toplevel(self.root)
            samples_window.title(f"Samples for Batch: {product_name} ({batch_id_from_doc})")  # Use the actual batch_id
            samples_window.geometry("800x550")
            samples_window.current_page = 1  # Initialize current page for this window
            samples_window.items_per_page = 20  # Samples per page
            logging.info(f"Opened samples window for batch {batch_id_from_doc}.")

            ttk.Label(samples_window, text=f"Samples for Batch: {product_name} (ID: {batch_id_from_doc})",
                      font=("Helvetica", 14, "bold")).pack(pady=10)

            samples_tree = ttk.Treeview(samples_window,
                                        columns=(
                                            "SampleID", "Owner", "Maturation Date", "Status", "Creation Date"),
                                        show='headings')

            samples_tree.heading("SampleID", text="Sample ID")
            samples_tree.heading("Owner", text="Owner")
            samples_tree.heading("Maturation Date", text="Maturation Date")
            samples_tree.heading("Status", text="Status")
            samples_tree.heading("Creation Date", text="Creation Date")

            samples_tree.column("SampleID", width=100, anchor="center")
            samples_tree.column("Owner", width=100, anchor="center")
            samples_tree.column("Maturation Date", width=120, anchor="center")
            samples_tree.column("Status", width=100, anchor="center")
            samples_tree.column("Creation Date", width=120, anchor="center")

            samples_tree.pack(expand=True, fill="both", padx=10, pady=10)

            # Pagination controls frame
            pagination_frame = ttk.Frame(samples_window)
            pagination_frame.pack(pady=5)

            prev_button = ttk.Button(pagination_frame, text="Previous Page")
            prev_button.pack(side="left", padx=5)

            page_label = ttk.Label(pagination_frame, text="Page X of Y")
            page_label.pack(side="left", padx=10)

            next_button = ttk.Button(pagination_frame, text="Next Page")
            next_button.pack(side="left", padx=5)

            # Frame for buttons below the samples tree
            btn_sample_frame = ttk.Frame(samples_window)
            btn_sample_frame.pack(pady=5)

            # New "Approve Sample" button
            ttk.Button(btn_sample_frame, text="Approve Sample",
                       command=lambda: self.admin_approve_sample(samples_tree, batch_doc_id)).pack(side="left", padx=5)
            ttk.Button(btn_sample_frame, text="Reject Sample",  # New button
                       command=lambda: self.admin_reject_sample(samples_tree, batch_doc_id)).pack(side="left", padx=5)

            def go_to_page(page_num):
                samples_window.current_page = page_num
                self._load_samples_into_tree(batch_id_from_doc, samples_tree, page_label,
                                             samples_window.current_page, samples_window.items_per_page)
                # Enable/disable buttons based on current page
                prev_button.config(state="normal" if samples_window.current_page > 1 else "disabled")
                next_button.config(
                    state="normal" if samples_window.current_page < samples_window.total_pages else "disabled")

            prev_button.config(command=lambda: go_to_page(samples_window.current_page - 1))
            next_button.config(command=lambda: go_to_page(samples_window.current_page + 1))

            # Initial load of samples for the first page
            go_to_page(1)  # Load first page
            logging.info(f"Samples window for batch {batch_id_from_doc} initialized with pagination.")

        except Exception as e:
            logging.error(f"Error opening samples view for batch {batch_doc_id}: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to view samples for batch: {e}")

    def admin_approve_sample(self, samples_tree_ref, batch_doc_id):
        """Approves a selected sample and checks/updates the parent batch status."""
        logging.info(f"Attempting to approve sample for batch document ID: {batch_doc_id}.")
        selected_sample_iid = samples_tree_ref.selection()
        if not selected_sample_iid:
            messagebox.showinfo("Info", "Please select a sample to approve.")
            logging.warning("Approve sample aborted: No sample selected.")
            return

        sample_tree_data = samples_tree_ref.item(selected_sample_iid[0], 'values')
        sample_id_from_tree = sample_tree_data[0]  # Assuming Sample ID is the first column

        try:
            # Find the Firestore document ID for the selected sample using its sample_id and batch_id
            sample_query = db.collection("samples").where("sample_id", "==", sample_id_from_tree).where("batch_id", "==",
                                                                                                        self._get_batch_id_from_doc_id(batch_doc_id)).limit( # Use the actual batch_id string from the batch document
                1).get()

            if not sample_query:
                messagebox.showerror("Error", "Selected sample not found in database.")
                logging.error(f"Sample with display ID {sample_id_from_tree} not found in database for batch document ID {batch_doc_id}.")
                return

            sample_doc_ref = sample_query[0].reference
            sample_doc = sample_query[0].to_dict()

            if sample_doc.get("status") == "approved":
                messagebox.showinfo("Info", "Sample is already approved.")
                logging.info(f"Sample {sample_id_from_tree} is already approved.")
                return

            confirm = messagebox.askyesno("Confirm Approve Sample",
                                          f"Approve sample '{sample_doc.get('sample_id')}'?")
            if confirm:
                # Update sample status
                sample_doc_ref.update({"status": "approved"})
                messagebox.showinfo("Success", f"Sample '{sample_doc.get('sample_id')}' approved successfully.")
                logging.info(f"Sample {sample_id_from_tree} approved successfully.")

                self.load_batches(self.batch_filter_var.get()) # Reload main batches tree

                # Now, check if all samples in the batch are approved
                all_samples_approved = True
                # Use the actual batch_id field for querying samples
                associated_samples_in_batch = db.collection("samples").where("batch_id", "==", self._get_batch_id_from_doc_id(batch_doc_id)).stream()

                # Check for samples in the generator before iterating
                samples_exist = False
                temp_samples_list = []
                for s in associated_samples_in_batch:
                    samples_exist = True
                    temp_samples_list.append(s)  # Store to iterate again if needed

                if samples_exist:
                    logging.debug(f"Checking {len(temp_samples_list)} samples for batch {self._get_batch_id_from_doc_id(batch_doc_id)}.")
                    for s in temp_samples_list:
                        s_data = s.to_dict()
                        if s_data.get("status") != "approved":
                            all_samples_approved = False
                            logging.debug(f"Sample {s_data.get('sample_id')} is not approved. Batch cannot be fully approved.")
                            break  # Found a pending or rejected sample, no need to check further
                else:  # If no samples exist, it cannot be 'all approved'
                    all_samples_approved = False
                    logging.info(f"No samples found for batch {self._get_batch_id_from_doc_id(batch_doc_id)}. Batch status will not be set to 'approved'.")

                batch_ref = db.collection("batches").document(batch_doc_id)
                current_batch_status = batch_ref.get().to_dict().get("status")

                if all_samples_approved and samples_exist:  # Only set batch to approved if there are samples and all are approved
                    if current_batch_status != "approved":
                        batch_ref.update({"status": "approved"})
                        messagebox.showinfo("Batch Status Update",
                                            f"Batch '{self._get_batch_id_from_doc_id(batch_doc_id)}' status updated to 'approved' as all samples are approved.")
                        logging.info(f"Batch {self._get_batch_id_from_doc_id(batch_doc_id)} status updated to 'approved'.")
                        self.load_batches(self.batch_filter_var.get())  # Refresh the main batches tree
                elif not all_samples_approved and current_batch_status == "approved": # If it was approved, but now a sample is not, revert
                    batch_ref.update({"status": "pending approval"})
                    messagebox.showinfo("Batch Status Update",
                                        f"Batch '{self._get_batch_id_from_doc_id(batch_doc_id)}' status updated to 'pending approval' as some samples are not yet approved.")
                    logging.info(f"Batch {self._get_batch_id_from_doc_id(batch_doc_id)} status reverted to 'pending approval'.")
                    self.load_batches(self.batch_filter_var.get())  # Refresh the main batches tree
                else:
                    logging.info(f"Batch {self._get_batch_id_from_doc_id(batch_doc_id)} status remains '{current_batch_status}' as not all samples are approved or no samples exist.")

            else:
                logging.info("Approve sample cancelled by user.")
        except Exception as e:
            logging.error(f"Failed to approve sample or update batch status for sample {sample_id_from_tree}: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to approve sample or update batch status: {e}")

    def admin_reject_sample(self, samples_tree_ref, batch_doc_id):
        """Rejects a selected sample and updates the parent batch status if necessary."""
        logging.info(f"Attempting to reject sample for batch document ID: {batch_doc_id}.")
        selected_sample_iid = samples_tree_ref.selection()
        if not selected_sample_iid:
            messagebox.showinfo("Info", "Please select a sample to reject.")
            logging.warning("Reject sample aborted: No sample selected.")
            return

        sample_tree_data = samples_tree_ref.item(selected_sample_iid[0], 'values')
        sample_id_from_tree = sample_tree_data[0]

        try:
            sample_query = db.collection("samples").where("sample_id", "==", sample_id_from_tree).where("batch_id", "==",
                                                                                                        self._get_batch_id_from_doc_id(batch_doc_id)).limit( # Use the actual batch_id string
                1).get()

            if not sample_query:
                messagebox.showerror("Error", "Selected sample not found in database.")
                logging.error(f"Sample {sample_id_from_tree} not found in database for rejection.")
                return

            sample_doc_ref = sample_query[0].reference
            sample_doc = sample_query[0].to_dict()

            if sample_doc.get("status") == "rejected":
                messagebox.showinfo("Info", "Sample is already rejected.")
                logging.info(f"Sample {sample_id_from_tree} is already rejected.")
                return

            confirm = messagebox.askyesno("Confirm Reject Sample",
                                          f"Reject sample '{sample_doc.get('sample_id')}'?")
            if confirm:
                sample_doc_ref.update({"status": "rejected"})
                messagebox.showinfo("Success", f"Sample '{sample_doc.get('sample_id')}' rejected successfully.")
                logging.info(f"Sample {sample_id_from_tree} rejected successfully.")
                self.load_batches(self.batch_filter_var.get())  # Reload the main batches tree

                # If a sample is rejected, the batch status should definitely revert to "pending approval"
                batch_ref = db.collection("batches").document(batch_doc_id)
                current_batch_status = batch_ref.get().to_dict().get("status")
                if current_batch_status != "pending approval":
                    batch_ref.update({"status": "pending approval"})
                    messagebox.showinfo("Batch Status Update",
                                        f"Batch '{self._get_batch_id_from_doc_id(batch_doc_id)}' status updated to 'pending approval' as a sample was rejected.")
                    logging.info(f"Batch {self._get_batch_id_from_doc_id(batch_doc_id)} status updated to 'pending approval' due to sample rejection.")
                    self.load_batches(self.batch_filter_var.get())
            else:
                logging.info("Reject sample cancelled by user.")
        except Exception as e:
            logging.error(f"Failed to reject sample or update batch status for sample {sample_id_from_tree}: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to reject sample or update batch status: {e}")

    def _load_samples_into_tree(self, batch_id, samples_tree, page_label_ref, page_number, items_per_page):
        """Helper method to load samples into the provided treeview with pagination."""
        logging.info(f"Loading samples into tree for batch_id: {batch_id}, page: {page_number}.")
        samples_tree.delete(*samples_tree.get_children())

        try:
            # First, get the total count of samples for this batch
            all_samples_query = db.collection("samples").where("batch_id", "==", batch_id).stream()
            all_samples = list(all_samples_query)  # Convert stream to list to count
            total_samples = len(all_samples)
            total_pages = (total_samples + items_per_page - 1) // items_per_page
            if total_pages == 0:
                total_pages = 1  # At least one page even if no samples

            # Update the page label in the UI
            page_label_ref.master.master.total_pages = total_pages  # Store total_pages on the samples_window
            page_label_ref.config(text=f"Page {page_number} of {total_pages}")
            logging.debug(f"Total samples for batch {batch_id}: {total_samples}, Total pages: {total_pages}.")

            # Calculate offset for Firestore query - Firestore's .offset() is for documents, not arbitrary lists
            # To implement true pagination, you'd generally use start_at or start_after with an order_by.
            # For simplicity here, if using .offset() for illustration, keep in mind its limitations with large datasets.
            # A more robust solution would involve fetching the 'items_per_page' starting after the last document of the previous page.
            # For this example, assuming simpler offset might be intended if data size is small.
            # However, for correct Firestore pagination:
            # You would need a query that orders by a field (e.g., creation_date or sample_id)
            # and then use start_after() based on the last document of the previous page.
            # This implementation will retrieve all samples and then slice them, which is inefficient for large datasets.
            # Let's adjust to perform slicing on the fetched list as it was likely intended by 'offset'.

            start_index = (page_number - 1) * items_per_page
            end_index = start_index + items_per_page
            paginated_samples = all_samples[start_index:end_index]
            logging.debug(f"Slicing samples from index {start_index} to {end_index}. Fetched {len(paginated_samples)} for current page.")


            samples_found_on_page = 0
            for sample in paginated_samples:
                samples_found_on_page += 1
                sample_data = sample.to_dict()
                logging.debug(f"  Found sample: {sample_data.get('sample_id')}, batch_id: {sample_data.get('batch_id')}")

                maturation_date_str = ""
                if isinstance(sample_data.get('maturation_date'), datetime):
                    maturation_date_str = sample_data['maturation_date'].strftime("%Y-%m-%d")
                elif isinstance(sample_data.get('maturation_date'), firebase_admin.firestore.Timestamp):
                    maturation_date_str = sample_data['maturation_date'].to_datetime().strftime("%Y-%m-%d")
                else:
                    maturation_date_str = str(sample_data.get('maturation_date', ''))

                creation_date_str = ""
                if isinstance(sample_data.get('creation_date'), datetime):
                    creation_date_str = sample_data['creation_date'].strftime("%Y-%m-%d %H:%M:%S")
                elif isinstance(sample_data.get('creation_date'), firebase_admin.firestore.Timestamp):
                    creation_date_str = sample_data['creation_date'].to_datetime().strftime("%Y-%m-%d %H:%M:%S")
                else:
                    creation_date_str = str(sample_data.get('creation_date', ''))

                samples_tree.insert("", "end", iid=sample.id,  # Store document ID for easy reference
                                    values=(sample_data.get("sample_id", ""),
                                            sample_data.get("owner", ""),
                                            maturation_date_str,
                                            sample_data.get("status", ""),
                                            creation_date_str))
            
            if samples_found_on_page == 0 and total_samples > 0 and page_number > 1:
                logging.info("No samples on current page, navigating to previous valid page recursively.")
                page_label_ref.master.master.current_page = max(1, page_number - 1)
                self._load_samples_into_tree(batch_id, samples_tree, page_label_ref,
                                             page_label_ref.master.master.current_page, items_per_page)
            elif samples_found_on_page == 0 and total_samples == 0:
                logging.info(f"No samples found at all for batch_id: {batch_id}.")
            else:
                logging.info(f"Loaded {samples_found_on_page} samples for page {page_number} of batch {batch_id}.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load samples for batch: {e}")
            logging.error(f"Error loading samples into tree for batch {batch_id}: {e}", exc_info=True)

    def _get_batch_id_from_doc_id(self, doc_id):
        """Helper to get the 'batch_id' field (the human-readable ID) from a Firestore batch document ID."""
        try:
            batch_doc = db.collection("batches").document(doc_id).get()
            if batch_doc.exists:
                return batch_doc.to_dict().get("batch_id")
            return None
        except Exception as e:
            logging.error(f"Failed to retrieve batch_id for document ID {doc_id}: {e}", exc_info=True)
            return None

    def delete_batch(self):
        """Deletes a selected batch and all its associated samples from Firestore."""
        logging.info("Starting delete_batch process.")
        selected = self.batches_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a batch to delete.")
            logging.warning("Delete batch aborted: No batch selected.")
            return

        firestore_batch_doc_id = selected[0]
        # Get the displayed batch ID for the confirmation message
        item_values = self.batches_tree.item(firestore_batch_doc_id)['values']
        batch_id_display = item_values[0] if item_values else firestore_batch_doc_id

        logging.info(f"Attempting to delete batch: DocID='{firestore_batch_doc_id}', DisplayID='{batch_id_display}'")

        confirm = messagebox.askyesno("Confirm Delete Batch",
                                      f"Are you sure you want to delete Batch '{batch_id_display}'?\n\n"
                                      "This will PERMANENTLY DELETE ALL SAMPLES associated with this batch as well. This action cannot be undone.")
        if not confirm:
            logging.info("Delete batch aborted: User cancelled.")
            return

        try:
            batch_write = db.batch()

            # 1. Delete all samples associated with this batch
            # Use 'batch_id' field in samples collection, which stores the human-readable batch_id_display
            samples_to_delete = db.collection("samples").where("batch_id", "==", batch_id_display).stream()
            deleted_samples_count = 0
            for sample_doc in samples_to_delete:
                batch_write.delete(sample_doc.reference)
                deleted_samples_count += 1
            logging.info(f"Prepared to delete {deleted_samples_count} samples for batch '{batch_id_display}'.")

            # 2. Delete the batch document itself
            batch_doc_ref = db.collection("batches").document(firestore_batch_doc_id)
            batch_write.delete(batch_doc_ref)
            logging.info(f"Prepared to delete batch document: {firestore_batch_doc_id}.")

            # Commit the batch operation
            batch_write.commit()
            logging.info("Firestore batch committed successfully (batch and samples deleted).")

            messagebox.showinfo("Success",
                                f"Batch '{batch_id_display}' and its {deleted_samples_count} associated samples deleted successfully.")
            logging.info(f"Batch '{batch_id_display}' and its samples deleted.")

            # Refresh the Treeview to reflect the deletion
            self.load_batches(self.batch_filter_var.get())
            logging.info("Batch data reloaded and tree refreshed after deletion.")

        except Exception as e:
            logging.error(f"Failed to delete batch '{batch_id_display}': {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to delete batch and its samples:\n{e}")

    #Add edit_batch
    def edit_batch_info(self):
        """Opens a form to edit the product name and description of a selected batch."""
        logging.info("Attempting to open edit batch form.")
        selected = self.batches_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a batch to edit.")
            logging.warning("Edit batch aborted: No batch selected.")
            return

        batch_doc_id = selected[0]
        try:
            batch_doc = db.collection("batches").document(batch_doc_id).get()

            if not batch_doc.exists:
                messagebox.showerror("Error", "Selected batch not found.")
                logging.error(f"Batch with document ID {batch_doc_id} not found for editing.")
                return

            batch_data = batch_doc.to_dict()
            logging.info(f"Opened edit form for batch: {batch_data.get('batch_id')}.")

            edit_window = tk.Toplevel(self.root)
            edit_window.title(f"Edit Batch: {batch_data.get('batch_id')}")
            edit_window.geometry("400x250")
            edit_window.transient(self.root)  # Make it appear on top of the main window
            edit_window.grab_set()  # Make it modal

            # Product Name
            ttk.Label(edit_window, text="Product Name:").pack(pady=5)
            product_name_entry = ttk.Entry(edit_window, width=40)
            product_name_entry.pack(pady=5)
            product_name_entry.insert(0, batch_data.get("product_name", ""))

            # Description
            ttk.Label(edit_window, text="Description:").pack(pady=5)
            description_text = tk.Text(edit_window, width=30, height=5)
            description_text.pack(pady=5)
            description_text.insert("1.0", batch_data.get("description", ""))

            def save_changes():
                logging.info(f"Attempting to save changes for batch {batch_data.get('batch_id')}.")
                new_product_name = product_name_entry.get().strip()
                new_description = description_text.get("1.0", tk.END).strip()

                if not new_product_name:
                    messagebox.showwarning("Input Error", "Product Name cannot be empty.")
                    logging.warning("Product Name is empty during batch edit save.")
                    return

                try:
                    db.collection("batches").document(batch_doc_id).update({
                        "product_name": new_product_name,
                        "description": new_description
                    })
                    messagebox.showinfo("Success", "Batch information updated successfully.")
                    logging.info(f"Batch {batch_doc_id} information updated successfully.")
                    edit_window.destroy()
                    self.load_batches(self.batch_filter_var.get())  # Refresh batches tree
                except Exception as e:
                    logging.error(f"Failed to update batch information for {batch_doc_id}: {e}", exc_info=True)
                    messagebox.showerror("Error", f"Failed to update batch information: {e}")

            ttk.Button(edit_window, text="Save Changes", command=save_changes, style="Green.TButton").pack(pady=10)
            edit_window.protocol("WM_DELETE_WINDOW", edit_window.destroy) # Ensure window closes properly
            logging.info(f"Edit batch form for {batch_doc_id} displayed.")

        except Exception as e:
            logging.error(f"Failed to open edit batch form for {batch_doc_id}: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to open edit batch form: {e}")


    def export_user_batches(self):
        """Exports approved batches and their associated samples to an Excel file."""
        logging.info("Initiating export of approved batches and samples to Excel.")
        # Add confirmation dialog here
        confirm = messagebox.askyesno("Confirm Export",
                                      "Are you sure you want to export all approved batch data to Excel?")
        if not confirm:
            logging.info("Export cancelled by user.")
            return  # User cancelled the export

        logging.info("Attempting to export approved batches and samples to Excel.")
        approved_batches_data = []
        batches_ref = db.collection("batches")
        samples_ref = db.collection("samples")

        try:
            approved_batches = batches_ref.where("status", "==", "approved").get()

            if not approved_batches:
                messagebox.showwarning("Warning", "No approved batches to export.")
                logging.warning("No approved batches found to export.")
                return

            for batch in approved_batches:
                batch_data = batch.to_dict()
                actual_batch_id_field = batch_data.get("batch_id")
                logging.debug(f"Processing batch {actual_batch_id_field} for export.")

                # Query samples using the 'batch_id' field from the batch document
                associated_samples = samples_ref.where("batch_id", "==", actual_batch_id_field).get()

                # Ensure batch data is always included, even if no samples
                if not associated_samples:
                    logging.info(f"Batch {actual_batch_id_field} has no samples. Exporting batch data only.")
                    combined_data = {
                        "batch_id": batch_data.get("batch_id", ""),
                        "product_name": batch_data.get("product_name", ""),
                        "batch_description": batch_data.get("description", ""),
                        "batch_status": batch_data.get("status", ""),
                        "user_employee_id": batch_data.get("user_employee_id", ""), # Added employee ID to export
                        "user_email": batch_data.get("user_email", ""),
                        "sample_id": "",
                        "sample_owner": "",
                        "sample_maturation_date": "",
                        "sample_status": "",
                        "sample_creation_date": "" # Added sample creation date
                    }
                    approved_batches_data.append(combined_data)

                for sample in associated_samples:
                    sample_data = sample.to_dict()
                    mat_date_str = ""
                    sample_mat_date_obj = sample_data.get('maturation_date')
                    if isinstance(sample_mat_date_obj, datetime):
                        mat_date_str = sample_mat_date_obj.strftime("%Y-%m-%d")
                    elif isinstance(sample_mat_date_obj, firebase_admin.firestore.Timestamp):
                        mat_date_str = sample_mat_date_obj.to_datetime().strftime("%Y-%m-%d")
                    else:
                        mat_date_str = str(sample_mat_date_obj) if sample_mat_date_obj is not None else ''

                    creation_date_str = ""
                    sample_creation_date_obj = sample_data.get('creation_date')
                    if isinstance(sample_creation_date_obj, datetime):
                        creation_date_str = sample_creation_date_obj.strftime("%Y-%m-%d %H:%M:%S")
                    elif isinstance(sample_creation_date_obj, firebase_admin.firestore.Timestamp):
                        creation_date_str = sample_creation_date_obj.to_datetime().strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        creation_date_str = str(sample_creation_date_obj) if sample_creation_date_obj is not None else ''


                    combined_data = {
                        "batch_id": batch_data.get("batch_id", ""),
                        "product_name": batch_data.get("product_name", ""),
                        "batch_description": batch_data.get("description", ""),
                        "batch_status": batch_data.get("status", ""),
                        "user_employee_id": batch_data.get("user_employee_id", ""), # Added employee ID to export
                        "user_email": batch_data.get("user_email", ""),
                        "sample_id": sample_data.get("sample_id", ""),
                        "sample_owner": sample_data.get("owner", ""),
                        "sample_maturation_date": mat_date_str,
                        "sample_status": sample_data.get("status", ""),
                        "sample_creation_date": creation_date_str # Added sample creation date
                    }
                    approved_batches_data.append(combined_data)

            if not approved_batches_data:
                messagebox.showwarning("Warning", "No approved batches with data to export.")
                logging.warning("No data collected for approved batches, nothing to export.")
                return

            df_approved_with_samples = pd.DataFrame(approved_batches_data)

            filetypes = (("Excel files", "*.xlsx"),)
            filename = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                                    filetypes=filetypes,
                                                    initialfile="Approved_Batches_and_Samples.xlsx")
            if filename:
                try:
                    for col in df_approved_with_samples.columns:
                        if pd.api.types.is_datetime64_any_dtype(df_approved_with_samples[col]):
                            if df_approved_with_samples[col].dt.tz is not None:
                                df_approved_with_samples[col] = df_approved_with_samples[col].dt.tz_localize(None)

                    df_approved_with_samples.to_excel(filename, index=False)
                    messagebox.showinfo("Success",
                                        f"Approved batches and their samples exported to {os.path.basename(filename)}")
                    logging.info(f"Successfully exported approved batches and samples to {filename}.")
                except Exception as e:
                    logging.error(f"Failed to export Excel file for approved batches: {e}", exc_info=True)
                    messagebox.showerror("Error", f"Failed to export Excel file:\n{e}")
            else:
                logging.info("Export to Excel cancelled by user.")
        except Exception as e:
            logging.error(f"Error fetching data for Excel export: {e}", exc_info=True)
            messagebox.showerror("Error", f"Error during data collection for export:\n{e}")
