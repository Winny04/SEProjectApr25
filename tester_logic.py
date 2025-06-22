import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime

from firebase_setup import db  # Assuming db is initialized from firebase_setup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from tkcalendar import DateEntry
from tkinter import simpledialog

# --- Logging Setup ---
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# --- End Logging Setup ---


class TesterLogic:
    def __init__(self, root, app_instance):
        """
        Initializes the TesterLogic class.

        Args:
            root: The main Tkinter root window.
            app_instance: The main application instance (ShelfLifeApp) to access shared attributes.
        """
        self.root = root
        self.app = app_instance
        self.tester_tree = None # Initialize tester_tree attribute
        self.tester_mat_date_start_entry = None # Initialize entry widgets
        self.tester_mat_date_end_entry = None
        logging.info("TesterLogic initialized.")


    def tester_dashboard(self):
        """Displays the Tester dashboard with features for date range filtering and email reminders."""
        logging.info("Entering tester_dashboard method.")
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
        self.tester_mat_date_start_entry = DateEntry(tester_frame, width=12, background='darkblue',
                                                     foreground='white', date_pattern='yyyy-mm-dd')
        self.tester_mat_date_start_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(tester_frame, text="Maturation Date End (YYYY-MM-DD):").grid(row=0, column=2, sticky="e", padx=5,
                                                                                pady=2)
        self.tester_mat_date_end_entry = DateEntry(tester_frame, width=12, background='darkblue',
                                                     foreground='white', date_pattern='yyyy-mm-dd')
        self.tester_mat_date_end_entry.grid(row=0, column=3, sticky="ew", padx=5, pady=2)

        ttk.Button(tester_frame, text="Filter Samples", command=self.filter_samples_by_maturation_date).grid(row=0,
                                                                                                                column=4,
                                                                                                                padx=10,
                                                                                                                pady=2)
        ttk.Button(tester_frame, text="Send Reminder Email", command=self.send_reminder_email).grid(row=0, column=5,
                                                                                                     padx=10, pady=2)

        # === Treeview for Data Display ===
        ttk.Label(self.root, text="Samples within Date Range", font=("Helvetica", 14, "bold")).pack(pady=(10, 5))
        
        # Frame to hold Treeview and Scrollbar
        tree_frame = ttk.Frame(self.root)
        tree_frame.pack(expand=True, fill="both", padx=10, pady=10)

        self.tester_tree = ttk.Treeview(self.root, columns=(
            "SampleID", "Owner", "MaturationDate", "Status", "BatchID", "ProductOwnerEmail", "TestTeamEmail"
        ), show='headings')
        self.tester_tree.tag_configure("today", background="salmon")
        self.tester_tree.tag_configure("urgent", background="khaki")

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

        # Add a scrollbar to the Treeview
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tester_tree.yview)
        self.tester_tree.configure(yscrollcommand=tree_scrollbar.set)

        self.tester_tree.pack(side="left", expand=True, fill="both")
        tree_scrollbar.pack(side="right", fill="y")

        # Initial load of all samples or based on default range if desired
        self.filter_samples_by_maturation_date()  # Load samples on dashboard start
        logging.info("Tester dashboard loaded.")

    def filter_samples_by_maturation_date(self):
        """Filters and displays samples based on the provided maturation date range."""
        logging.info("Starting filter_samples_by_maturation_date.")
        self.tester_tree.delete(*self.tester_tree.get_children())
        self.tester_tree.tag_configure('urgent', background='khaki')
        self.tester_tree.tag_configure('today', background='salmon')
        start_date_str = self.tester_mat_date_start_entry.get().strip()
        end_date_str = self.tester_mat_date_end_entry.get().strip()

        start_date = None
        end_date = None

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                logging.info(f"Parsed start date: {start_date}")
            except ValueError:
                messagebox.showerror("Invalid Date", "Maturation Date Start: Use YYYY-MM-DD format.")
                logging.error(f"Invalid start date format: {start_date_str}")
                return

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
                end_date = end_date.replace(hour=23, minute=59, second=59)  # Include full end day
                logging.info(f"Parsed end date: {end_date}")
            except ValueError:
                messagebox.showerror("Invalid Date", "Maturation Date End: Use YYYY-MM-DD format.")
                logging.error(f"Invalid end date format: {end_date_str}")
                return

        samples_ref = db.collection("samples")
        query = samples_ref

        # Apply date filters
        if start_date:
            query = query.where("maturation_date", ">=", start_date)
            logging.info(f"Applied Firestore filter: maturation_date >= {start_date}")
        if end_date:
            query = query.where("maturation_date", "<=", end_date)
            logging.info(f"Applied Firestore filter: maturation_date <= {end_date}")

        try:
            # Pre-fetch all user emails to avoid N+1 queries
            logging.info("Pre-fetching all user emails.")
            users_docs = db.collection("users").stream()
            user_emails_map = {}
            test_team_emails = [] # This will still be populated for the Treeview display
            for user_doc in users_docs:
                user_data = user_doc.to_dict()
                if user_data.get("employee_id"):
                    user_emails_map[user_data["employee_id"]] = user_data.get("email", "N/A")
                if user_data.get("role") == "tester" and user_data.get("email"):
                    test_team_emails.append(user_data["email"])
            test_team_email_str = ", ".join(test_team_emails) if test_team_emails else "N/A"
            logging.info(f"Pre-fetched {len(user_emails_map)} user emails and {len(test_team_emails)} tester emails.")


            samples = query.stream()
            sample_count = 0
            for sample in samples:
                sample_count += 1
                data = sample.to_dict()
                maturation_date_str = data.get("maturation_date", "")
                if isinstance(maturation_date_str, datetime):
                    maturation_date_str = maturation_date_str.strftime("%Y-%m-%d")
                else:
                    maturation_date_str = str(maturation_date_str) if maturation_date_str is not None else ''

                # Get product owner email from pre-fetched map
                submitted_by_employee_id = data.get("submitted_by_employee_id")
                product_owner_email = user_emails_map.get(submitted_by_employee_id, "N/A")
                logging.debug(f"Resolved product owner email: {product_owner_email} for user {submitted_by_employee_id}")

                days_left = -1
                try:
                    maturation_date = datetime.strptime(maturation_date_str, "%Y-%m-%d")
                    days_left = (maturation_date.date() - datetime.today().date()).days
                except ValueError as ve:
                    logging.warning(f"Could not parse maturation date '{maturation_date_str}' for sample {data.get('sample_id', 'N/A')}: {ve}")
                    pass # Continue processing even if date parsing fails for coloring

                tags = ()
                if days_left == 0:
                    tags = ('today',)
                    logging.debug(f"Sample {data.get('sample_id', '')} tagged as 'today'.")
                elif 0 < days_left <= 7:
                    tags = ('urgent',)
                    logging.debug(f"Sample {data.get('sample_id', '')} tagged as 'urgent'.")

                self.tester_tree.insert("", "end", iid=sample.id,
                                         values=(data.get("sample_id", ""),
                                                 data.get("owner", ""),
                                                 maturation_date_str,
                                                 data.get("status", "pending"),
                                                 data.get("batch_id", ""),
                                                 product_owner_email,
                                                 test_team_email_str), tags=tags)
            logging.info(f"Filtered {sample_count} samples and populated Treeview.")
            messagebox.showinfo("Filter Complete", "Samples filtered successfully.")
        except Exception as e:
            logging.exception("Failed to filter samples.") # Use logging.exception for full traceback
            messagebox.showerror("Error", f"Failed to filter samples: {e}")

    def prompt_reminder_period(self):
        """Show a pop-up window with radio buttons to choose reminder period."""
        logging.info("Prompting for reminder period.")
        reminder_window = tk.Toplevel(self.root)
        reminder_window.title("Choose Reminder Period")
        reminder_window.geometry("300x250")
        reminder_window.grab_set()  # Make this pop-up modal

        reminder_var = tk.StringVar(value="7d")  # default selection changed to 1 week (7 days)

        options = [
            ("Due Today", "0d"),
            ("Within 3 Days", "3d"),
            ("Within 1 Week", "7d"),    # Changed from '1w' to '7d' for consistency
            ("Within 2 Weeks", "14d"),   # Changed from '2w' to '14d'
            ("Within 30 Days", "30d"),   # Changed from '1m' to '30d' and label updated
            ("Within 60 Days", "60d")    # Changed from '2m' to '60d' and label updated
        ]

        tk.Label(reminder_window, text="Select Reminder Period:", font=("Helvetica", 12)).pack(pady=10)

        for label, value in options:
            tk.Radiobutton(reminder_window, text=label, variable=reminder_var, value=value).pack(anchor="w", padx=20)

        def submit_choice():
            logging.info(f"Reminder period selected: {reminder_var.get()}")
            period_code = reminder_var.get()
            reminder_window.destroy()
            self.prompt_test_team_selection(period_code) # Call new function to select test team

        tk.Button(reminder_window, text="Next", command=submit_choice).pack(pady=15) # Changed button text
        logging.info("Reminder period prompt displayed.")

    def prompt_test_team_selection(self, period_code):
        """
        Opens a Toplevel window for the user to select specific test team members
        to receive reminder emails.
        """
        logging.info(f"Prompting for test team selection for period code: {period_code}")
        test_team_window = tk.Toplevel(self.root)
        test_team_window.title("Select Test Team Members")
        test_team_window.geometry("600x400")
        test_team_window.grab_set()
        test_team_window.transient(self.root)

        frame = ttk.Frame(test_team_window, padding=10)
        frame.pack(expand=True, fill="both")

        ttk.Label(frame, text="Select Test Team Members:", font=("Helvetica", 12)).pack(pady=10)

        # Container for checkboxes with a scrollbar
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tester_vars = [] # To hold (BooleanVar, email) tuples
        testers_fetched = []

        try:
            users_docs = db.collection("users").where("role", "==", "tester").stream()
            for user_doc in users_docs:
                user_data = user_doc.to_dict()
                email = user_data.get("email")
                username = user_data.get("username")
                if email and email != "N/A":
                    var = tk.BooleanVar(value=True) # Default to selected
                    cb = ttk.Checkbutton(scrollable_frame, text=f"{username} ({email})", variable=var)
                    cb.pack(anchor="w", padx=5, pady=2)
                    self.tester_vars.append((var, email))
                    testers_fetched.append(f"{username} ({email})")
            logging.info(f"Fetched {len(testers_fetched)} tester users for selection: {', '.join(testers_fetched)}")

        except Exception as e:
            logging.error(f"Failed to load tester users for selection: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load tester users: {e}")
            test_team_window.destroy()
            return

        if not self.tester_vars:
            messagebox.showinfo("No Testers", "No tester users found in the database.")
            test_team_window.destroy()
            return


        def send_selected_reminders():
            selected_emails = [email for var, email in self.tester_vars if var.get()]
            logging.info(f"Selected test team emails: {selected_emails}")
            if not selected_emails:
                messagebox.showwarning("No Selection", "Please select at least one test team member.")
                return

            test_team_window.destroy()
            self.process_reminder_email(period_code, selected_emails)

        ttk.Button(frame, text="Send Reminders", command=send_selected_reminders).pack(pady=10)
        ttk.Button(frame, text="Cancel", command=test_team_window.destroy).pack(pady=5)
        logging.info("Test team selection window displayed.")


    def send_reminder_email(self):
        logging.info("Initiating send_reminder_email.")
        self.prompt_reminder_period()
        logging.info("send_reminder_email process initiated.")

    def process_reminder_email(self, period_code, selected_test_team_emails):
        """Processes and sends emails based on selected period and selected test team members."""
        logging.info(f"Processing reminder email for period code: {period_code}")
        logging.info(f"Selected test team emails for this reminder: {selected_test_team_emails}")

        days_map = {"0d": 0, "3d": 3, "7d": 7, "14d": 14, "30d": 30, "60d": 60}
        days_threshold = days_map.get(period_code, 7)
        logging.info(f"Calculated days threshold: {days_threshold}")

        samples_to_remind = []
        recipients_map = {}

        today = datetime.today()
        logging.info(f"Current date for comparison: {today.date()}")

        if not self.tester_tree.get_children():
            messagebox.showinfo("No Reminders", f"No samples currently displayed to check for reminders.")
            logging.info("No samples in Treeview to process for reminders.")
            return
        
        # We no longer need to pre-fetch all tester emails here, as they are passed directly
        # all_test_team_emails = selected_test_team_emails # This is now the actual list to use.


        for item_id in self.tester_tree.get_children():
            values = self.tester_tree.item(item_id, "values")
            sample_id = values[0]
            owner = values[1]
            maturation_date_str = values[2]
            status = values[3]
            batch_id = values[4]
            product_owner_email = values[5]

            logging.debug(f"Processing sample: {sample_id}, Maturation Date: {maturation_date_str}, Status: {status}")

            try:
                maturation_date = datetime.strptime(maturation_date_str, "%Y-%m-%d")
                days_until = (maturation_date.date() - today.date()).days
                logging.debug(f"Days until maturation for {sample_id}: {days_until}")
            except ValueError:
                logging.warning(f"Could not parse maturation date '{maturation_date_str}' for sample {sample_id}. Skipping.")
                continue

            if (period_code == "0d" and days_until == 0) or \
               (period_code == "3d" and 0 < days_until <= 3) or \
               (period_code == "7d" and 0 < days_until <= 7) or \
               (period_code == "14d" and 0 < days_until <= 14) or \
               (period_code == "30d" and 0 < days_until <= 30) or \
               (period_code == "60d" and 0 < days_until <= 60):
                samples_to_remind.append({
                    "sample_id": sample_id,
                    "owner": owner,
                    "maturation_date": maturation_date_str,
                    "batch_id": batch_id,
                    "product_owner_email": product_owner_email,
                    "test_team_emails": selected_test_team_emails # Use the selected list
                })
                logging.info(f"Sample {sample_id} added to reminders list (within threshold).")
            else:
                logging.debug(f"Sample {sample_id} (status: {status}, days_until: {days_until}) does not meet reminder criteria for period '{period_code}'.")


        if not samples_to_remind:
            messagebox.showinfo("No Reminders", f"No samples found for the selected period.")
            logging.info("No samples found meeting reminder criteria.")
            return

        # Map recipients
        for sample in samples_to_remind:
            po_email = sample["product_owner_email"]
            tt_emails = sample["test_team_emails"]
            if po_email and po_email != "N/A":
                recipients_map.setdefault(po_email, []).append(sample)
                logging.debug(f"Adding product owner {po_email} to recipients map.")
            for email in tt_emails: # Iterate through the pre-fetched list
                if email and email != "N/A":
                    recipients_map.setdefault(email, []).append(sample)
                    logging.debug(f"Adding test team member {email} to recipients map.")


        if not recipients_map:
            messagebox.showinfo("No Recipients", "No valid email recipients found.")
            logging.warning("No valid email recipients found after mapping.")
            return

        # Email config
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        sender_email = "test.dept7@gmail.com"
        app_password = "gicklxfdonaszuzh" 

        email_send_success = []
        email_send_fail = []
        logging.info(f"Attempting to send emails to {len(recipients_map)} unique recipients.")

        for recipient_email, samples in recipients_map.items():
            subject = f"Reminder: Samples maturing soon"
            body = "Dear User,\n\nThese samples require your attention:\n\n"
            for s in samples:
                body += f"- Sample ID: {s['sample_id']}, Owner: {s['owner']}, Maturation: {s['maturation_date']}, Batch: {s['batch_id']}\n"
            body += "\nPlease take necessary action.\n\nBest regards,\nSample Management System"
            logging.debug(f"Preparing email for {recipient_email}. Subject: {subject}")

            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = recipient_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            try:
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.starttls()
                    server.login(sender_email, app_password)
                    server.send_message(msg)
                    email_send_success.append(recipient_email)
                    logging.info(f"Successfully sent email to: {recipient_email}")
            except Exception as e:
                email_send_fail.append(f"{recipient_email} ({e})")
                logging.error(f"Failed to send email to {recipient_email}: {e}", exc_info=True)

        if email_send_success:
            messagebox.showinfo("Reminder Sent", f"Emails sent to: {', '.join(email_send_success)}")
            logging.info(f"Emails successfully sent to: {', '.join(email_send_success)}")
        if email_send_fail:
            messagebox.showwarning("Some Failed", f"Some emails failed:\n{chr(10).join(email_send_fail)}")
            logging.warning(f"Emails failed for: {', '.join(email_send_fail)}")

        messagebox.showinfo("Done", "Reminder email process completed.")
        logging.info("Reminder email process completed.")

    def toggle_batch_fields(self, parent_frame, is_existing_batch_selected):
        """Toggles the visibility/state of new/existing batch fields. (Placeholder for other modules)"""
        pass  # This method is not directly used in TesterLogic, but kept as a stub if called


    def load_existing_batches_into_combobox(self):
        """Loads batch IDs from Firestore into the combobox. (Placeholder for other modules)"""
        pass  # This method is not directly used in TesterLogic, but kept as a stub if called
