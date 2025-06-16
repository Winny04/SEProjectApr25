import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
from firebase_setup import db  # Assuming db is initialized from firebase_setup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class TesterLogic:
    def __init__(self, root, app_instance):
        self.root = root
        self.app = app_instance
        self.tester_mat_date_start_entry = None
        self.tester_mat_date_end_entry = None
        self.tester_tree = None  # Treeview for displaying samples in Tester dashboard

    def tester_dashboard(self):
        """Displays the Tester dashboard with features for date range filtering and email reminders."""
        self.app.clear_root()
        self.root.geometry("1200x700")

        # Top frame for Logout button and Welcome message
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(top_frame, text="Logout", command=self.app.logout).pack(side="right")
        ttk.Label(top_frame, text=f"Welcome, Tester {self.app.current_user.get('username')}!",
                  font=("Helvetica", 16)).pack(side="left", expand=True)

        # === Tester Features Section ===
        tester_frame = ttk.LabelFrame(self.root, text="Tester Features")
        tester_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(tester_frame, text="Maturation Date Start (YYYY-MM-DD):").grid(row=0, column=0, sticky="e", padx=5,
                                                                                 pady=2)
        self.tester_mat_date_start_entry = ttk.Entry(tester_frame, width=15)
        self.tester_mat_date_start_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(tester_frame, text="Maturation Date End (YYYY-MM-DD):").grid(row=0, column=2, sticky="e", padx=5,
                                                                               pady=2)
        self.tester_mat_date_end_entry = ttk.Entry(tester_frame, width=15)
        self.tester_mat_date_end_entry.grid(row=0, column=3, sticky="ew", padx=5, pady=2)

        ttk.Button(tester_frame, text="Filter Samples", command=self.filter_samples_by_maturation_date).grid(row=0,
                                                                                                             column=4,
                                                                                                             padx=10,
                                                                                                             pady=2)
        ttk.Button(tester_frame, text="Send Reminder Email", command=self.send_reminder_email).grid(row=0, column=5,
                                                                                                    padx=10, pady=2)

        # === Treeview for Data Display ===
        ttk.Label(self.root, text="Samples within Date Range", font=("Helvetica", 14, "bold")).pack(pady=(10, 5))
        self.tester_tree = ttk.Treeview(self.root, columns=(
        "SampleID", "Owner", "MaturationDate", "Status", "BatchID", "ProductOwnerEmail", "TestTeamEmail"),
                                        show='headings')
        self.tester_tree.heading("SampleID", text="Sample ID")
        self.tester_tree.heading("Owner", text="Sample Owner")
        self.tester_tree.heading("MaturationDate", text="Maturation Date")
        self.tester_tree.heading("Status", text="Status")
        self.tester_tree.heading("BatchID", text="Batch ID")
        self.tester_tree.heading("ProductOwnerEmail", text="Product Owner Email")  # New column for email
        self.tester_tree.heading("TestTeamEmail", text="Test Team Email")  # New column for email

        self.tester_tree.column("SampleID", width=100, anchor="center")
        self.tester_tree.column("Owner", width=100, anchor="center")
        self.tester_tree.column("MaturationDate", width=120, anchor="center")
        self.tester_tree.column("Status", width=80, anchor="center")
        self.tester_tree.column("BatchID", width=120, anchor="center")
        self.tester_tree.column("ProductOwnerEmail", width=150, anchor="center")
        self.tester_tree.column("TestTeamEmail", width=150, anchor="center")

        self.tester_tree.pack(expand=True, fill="both", padx=10, pady=10)

        # Initial load of all samples or based on default range if desired
        self.filter_samples_by_maturation_date()  # Load samples on dashboard start

    def filter_samples_by_maturation_date(self):
        """Filters and displays samples based on the provided maturation date range."""
        self.tester_tree.delete(*self.tester_tree.get_children())
        start_date_str = self.tester_mat_date_start_entry.get().strip()
        end_date_str = self.tester_mat_date_end_entry.get().strip()

        start_date = None
        end_date = None

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Invalid Date", "Maturation Date Start: Use YYYY-MM-DD format.")
                return

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
                end_date = end_date.replace(hour=23, minute=59, second=59)  # Include full end day
            except ValueError:
                messagebox.showerror("Invalid Date", "Maturation Date End: Use YYYY-MM-DD format.")
                return

        samples_ref = db.collection("samples")
        query = samples_ref

        # Apply date filters
        if start_date:
            query = query.where("maturation_date", ">=", start_date)
        if end_date:
            query = query.where("maturation_date", "<=", end_date)

        try:
            samples = query.stream()
            for sample in samples:
                data = sample.to_dict()
                maturation_date_str = data.get("maturation_date", "")
                if isinstance(maturation_date_str, datetime):
                    maturation_date_str = maturation_date_str.strftime("%Y-%m-%d")
                else:
                    maturation_date_str = str(maturation_date_str) if maturation_date_str is not None else ''

                # Fetch product owner email from the sample's submitted_by_employee_id
                submitted_by_employee_id = data.get("submitted_by_employee_id")
                product_owner_email = "N/A"
                if submitted_by_employee_id:
                    user_doc = db.collection("users").document(submitted_by_employee_id).get()
                    if user_doc.exists:
                        user_data = user_doc.to_dict()
                        product_owner_email = user_data.get("email", "N/A")

                # Fetch test team emails (example: assuming roles 'tester' or specific test team users)
                test_team_email = "N/A"  # Initialize to N/A
                test_team_users = db.collection("users").where("role", "==",
                                                               "tester").stream()  # Or a specific group/role
                test_team_emails = [u.to_dict().get("email") for u in test_team_users if
                                    u.to_dict().get("email")]
                test_team_email = ", ".join(test_team_emails) if test_team_emails else "N/A"

                self.tester_tree.insert("", "end", iid=sample.id,
                                        values=(data.get("sample_id", ""),
                                                data.get("owner", ""),
                                                maturation_date_str,
                                                data.get("status", "pending"),
                                                data.get("batch_id", ""),
                                                product_owner_email,
                                                test_team_email))
            messagebox.showinfo("Filter Complete", "Samples filtered successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to filter samples: {e}")

    def send_reminder_email(self):
        """Sends reminder emails for samples expiring soon based on the filtered data."""
        samples_to_remind = []
        recipients_map = {}  # To store unique recipients and their samples

        # Iterate through currently displayed samples in the treeview
        for item_id in self.tester_tree.get_children():
            values = self.tester_tree.item(item_id, "values")
            # Unpack values based on the column definition in tester_dashboard
            sample_id = values[0]
            owner = values[1]
            maturation_date_str = values[2]
            status = values[3]
            batch_id = values[4]
            product_owner_email = values[5]
            test_team_email_str = values[6]  # This is a comma-separated string

            # Convert maturation date string back to datetime for comparison
            try:
                maturation_date = datetime.strptime(maturation_date_str, "%Y-%m-%d")
            except ValueError:
                continue  # Skip if date format is invalid

            # Define "expire soon" logic (e.g., within next 7 days, or within the filtered range)
            # For this context, let's assume "expire soon" means samples whose maturation_date
            # falls within the range currently displayed/filtered, and are not yet approved/rejected.
            if status == "pending":  # Only remind for pending samples
                samples_to_remind.append({
                    "sample_id": sample_id,
                    "owner": owner,
                    "maturation_date": maturation_date_str,
                    "batch_id": batch_id,
                    "product_owner_email": product_owner_email,
                    "test_team_emails": [email.strip() for email in test_team_email_str.split(',') if
                                         email.strip() and email.strip() != "N/A"]
                })

        if not samples_to_remind:
            messagebox.showinfo("No Reminders",
                                "No pending samples found within the specified range to send reminders.")
            return

        # Prepare emails for product owners and test team
        for sample in samples_to_remind:
            po_email = sample["product_owner_email"]
            tt_emails = sample["test_team_emails"]

            # Add product owner to recipients
            if po_email and po_email != "N/A":
                if po_email not in recipients_map:
                    recipients_map[po_email] = []
                recipients_map[po_email].append(sample)

            # Add test team to recipients
            for email in tt_emails:
                if email not in recipients_map:
                    recipients_map[email] = []
                recipients_map[email].append(sample)

        if not recipients_map:
            messagebox.showinfo("No Recipients", "No valid email recipients found for reminders.")
            return

        # --- Email Sending Logic (Placeholder) ---
        # NOTE: For actual email sending, you would need to configure an SMTP server.
        # This is a placeholder and will not send actual emails without proper setup.
        # Example: Using a dummy SMTP configuration.
        smtp_server = "smtp.example.com"  # Replace with your SMTP server
        smtp_port = 587  # Replace with your SMTP port (e.g., 587 for TLS, 465 for SSL)
        sender_email = "your_email@example.com"  # Replace with your sender email
        sender_password = "your_password"  # Replace with your email password or app-specific password

        email_send_success = []
        email_send_fail = []

        for recipient_email, samples_for_recipient in recipients_map.items():
            subject = "Reminder: Expiring Samples Requiring Attention"
            body = f"Dear User,\n\nThe following samples are pending and require your attention as their maturation date is approaching or within the filtered range:\n\n"
            for s in samples_for_recipient:
                body += f"- Sample ID: {s['sample_id']}, Owner: {s['owner']}, Maturation Date: {s['maturation_date']}, Batch ID: {s['batch_id']}\n"
            body += "\nPlease take necessary action.\n\nBest regards,\nSample Management System"

            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = recipient_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            try:
                # This part requires a live SMTP server and correct credentials
                # with smtplib.SMTP(smtp_server, smtp_port) as server:
                #     server.starttls()  # Start TLS encryption
                #     server.login(sender_email, sender_password)
                #     server.send_message(msg)
                # For now, we simulate success
                print(f"Simulating email sent to {recipient_email} for {len(samples_for_recipient)} samples.")
                email_send_success.append(recipient_email)
            except Exception as e:
                email_send_fail.append(f"{recipient_email} ({e})")
                messagebox.showerror("Email Error", f"Failed to send email to {recipient_email}: {e}")

        if email_send_success:
            messagebox.showinfo("Reminder Sent",
                                f"Reminder emails simulated/sent successfully to: {', '.join(email_send_success)}")
        if email_send_fail:
            messagebox.showwarning("Email Send Failure",
                                   f"Failed to send emails to some recipients:\n{'\n'.join(email_send_fail)}")

        messagebox.showinfo("Reminder Process Complete",
                            "Reminder email process finished. Check console for simulated sends.")

    def toggle_batch_fields(self, parent_frame, is_existing_batch_selected):
        """Toggles the visibility/state of new/existing batch fields. (Placeholder for other modules)"""
        pass  # This method is not directly used in TesterLogic, but kept as a stub if called


    def load_existing_batches_into_combobox(self):
        """Loads batch IDs from Firestore into the combobox. (Placeholder for other modules)"""
        pass  # This method is not directly used in TesterLogic, but kept as a stub if called
