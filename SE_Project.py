import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
from datetime import datetime, timedelta
import barcode
from barcode.writer import ImageWriter
import os

# Constants
NOTIFICATION_DAYS_BEFORE = 60  # Notify 2 months before maturation date

class ShelfLifeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Shelf-life Study Management System")
        self.root.geometry("900x600")

        self.data = pd.DataFrame(columns=["SampleID", "Owner", "MaturationDate"])
        self.file_path = None

        self.setup_ui()

    def setup_ui(self):
        # Button frame
        frame_btn = tk.Frame(self.root)
        frame_btn.pack(pady=10)

        tk.Button(frame_btn, text="Import Excel", command=self.import_excel).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_btn, text="Export Excel", command=self.export_excel).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_btn, text="Add Sample", command=self.add_sample).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_btn, text="Edit Sample", command=self.edit_sample).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_btn, text="Delete Sample", command=self.delete_sample).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_btn, text="Generate Barcode", command=self.generate_barcode).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_btn, text="Check Notifications", command=self.check_notifications).pack(side=tk.LEFT, padx=5)

        # Treeview setup
        columns = ("SampleID", "Owner", "MaturationDate")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=250, anchor=tk.CENTER)
        self.tree.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # Status bar
        self.status_label = tk.Label(self.root, text="Load or create data to get started.", anchor='w')
        self.status_label.pack(fill=tk.X, padx=10, pady=5)

    def import_excel(self):
        filetypes = [("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        filename = filedialog.askopenfilename(title="Select Excel file", filetypes=filetypes)
        if filename:
            try:
                df = pd.read_excel(filename)
                # Validate required columns
                if not all(col in df.columns for col in ["SampleID", "Owner", "MaturationDate"]):
                    messagebox.showerror("Error", "Excel file must contain 'SampleID', 'Owner' and 'MaturationDate' columns.")
                    return
                # Ensure date parsing
                df["MaturationDate"] = pd.to_datetime(df["MaturationDate"], errors='coerce')
                if df["MaturationDate"].isnull().any():
                    messagebox.showwarning("Warning", "Some maturation dates could not be parsed and were set to NaT.")
                self.data = df[["SampleID", "Owner", "MaturationDate"]].copy()
                self.file_path = filename
                self.refresh_tree()
                self.status_label.config(text=f"Data loaded from {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file:\n{e}")

    def export_excel(self):
        if self.data.empty:
            messagebox.showwarning("Warning", "No data to export.")
            return
        filetypes = [("Excel files", "*.xlsx")]
        filename = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=filetypes)
        if filename:
            try:
                self.data.to_excel(filename, index=False)
                self.status_label.config(text=f"Data exported to {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export file:\n{e}")

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for _, row in self.data.iterrows():
            mat_date_str = row["MaturationDate"].strftime("%Y-%m-%d") if pd.notnull(row["MaturationDate"]) else ""
            self.tree.insert("", tk.END, values=(row["SampleID"], row["Owner"], mat_date_str))

    def add_sample(self):
        self.sample_form("Add Sample")

    def edit_sample(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a sample to edit.")
            return
        item = self.tree.item(selected[0])
        sample_id = item["values"][0]
        self.sample_form("Edit Sample", sample_id)

    def delete_sample(self):
        if self.data.empty:
            messagebox.showwarning("Warning", "No data loaded.")
            return
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a sample to delete.")
            return
        item = self.tree.item(selected[0])
        sample_id = item["values"][0]

        if messagebox.askyesno("Confirm Delete", f"Delete sample {sample_id}?"):
            self.data = self.data[self.data["SampleID"] != sample_id].reset_index(drop=True)
            self.refresh_tree()
            self.auto_save()
            self.status_label.config(text=f"Deleted sample {sample_id}.")

    def sample_form(self, title, sample_id=None):
        form = tk.Toplevel(self.root)
        form.title(title)
        form.geometry("350x250")
        form.grab_set()

        tk.Label(form, text="Sample ID:").pack(pady=5)
        entry_sample_id = tk.Entry(form)
        entry_sample_id.pack()

        tk.Label(form, text="Sample Owner:").pack(pady=5)
        entry_owner = tk.Entry(form)
        entry_owner.pack()

        tk.Label(form, text="Maturation Date (YYYY-MM-DD):").pack(pady=5)
        entry_date = tk.Entry(form)
        entry_date.pack()

        if sample_id:
            # Editing existing sample: populate fields and disable sample ID editing
            row = self.data.loc[self.data["SampleID"] == sample_id].iloc[0]
            entry_sample_id.insert(0, row["SampleID"])
            entry_sample_id.config(state="disabled")
            entry_owner.insert(0, row["Owner"])
            if pd.notnull(row["MaturationDate"]):
                entry_date.insert(0, row["MaturationDate"].strftime("%Y-%m-%d"))

        def submit():
            sid = entry_sample_id.get().strip()
            owner = entry_owner.get().strip()
            date_str = entry_date.get().strip()

            if not sid or not owner or not date_str:
                messagebox.showerror("Error", "All fields are required.")
                return

            try:
                mat_date = pd.to_datetime(date_str)
            except Exception:
                messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD.")
                return

            if not sample_id and sid in self.data["SampleID"].values:
                messagebox.showerror("Error", "Sample ID already exists.")
                return

            if sample_id:
                # Update existing
                idx = self.data.index[self.data["SampleID"] == sample_id][0]
                self.data.at[idx, "Owner"] = owner
                self.data.at[idx, "MaturationDate"] = mat_date
                self.status_label.config(text=f"Sample {sample_id} updated.")
            else:
                # Add new
                new_row = {"SampleID": sid, "Owner": owner, "MaturationDate": mat_date}
                self.data = pd.concat([self.data, pd.DataFrame([new_row])], ignore_index=True)
                self.status_label.config(text=f"Sample {sid} added.")

            self.refresh_tree()
            self.auto_save()
            form.destroy()

        tk.Button(form, text="Save", command=submit).pack(pady=15)

    def generate_barcode(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a sample to generate barcode.")
            return
        sample_id = self.tree.item(selected[0])["values"][0]

        try:
            EAN = barcode.get_barcode_class("code128")
            ean = EAN(sample_id, writer=ImageWriter())
            save_path = filedialog.asksaveasfilename(defaultextension=".png",
                                                     filetypes=[("PNG files", "*.png")],
                                                     initialfile=f"{sample_id}_barcode.png")
            if save_path:
                ean.save(save_path)
                messagebox.showinfo("Success", f"Barcode saved at:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Barcode generation failed:\n{e}")

    def check_notifications(self):
        if self.data.empty:
            messagebox.showwarning("Warning", "No data loaded.")
            return

        today = datetime.now()
        notify_list = []

        for _, row in self.data.iterrows():
            mat_date = row["MaturationDate"]
            if pd.isnull(mat_date):
                continue
            delta = (mat_date - today).days
            if 0 <= delta <= NOTIFICATION_DAYS_BEFORE:
                notify_list.append(f"Sample {row['SampleID']} (Owner: {row['Owner']}) matures on {mat_date.strftime('%Y-%m-%d')} (in {delta} days)")

        if notify_list:
            # Show notifications in messagebox
            messagebox.showinfo("Upcoming Sample Maturations (within 2 months)", "\n".join(notify_list))
            # Here you could also integrate email notification logic or logs
        else:
            messagebox.showinfo("Notifications", "No samples maturing within the next 2 months.")

    def auto_save(self):
        """Auto-save data to original Excel file, if available."""
        if self.file_path:
            try:
                self.data.to_excel(self.file_path, index=False)
                self.status_label.config(text=f"Data saved to {os.path.basename(self.file_path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to auto-save data:\n{e}")
        else:
            self.status_label.config(text="No original file loaded to auto-save.")

if __name__ == "__main__":
    root = tk.Tk()
    app = ShelfLifeApp(root)
    root.mainloop()
