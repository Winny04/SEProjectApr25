import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
from datetime import datetime, timedelta
import barcode
from barcode.writer import ImageWriter
import os

# Constants
NOTIFICATION_DAYS_BEFORE = 60  # 2 months approx.

class ShelfLifeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Shelf-life Study Management System")
        self.root.geometry("800x600")

        self.data = pd.DataFrame()
        self.file_path = ""

        # Setup UI
        self.setup_ui()

    def setup_ui(self):
        # Frame for buttons
        frame_btn = tk.Frame(self.root)
        frame_btn.pack(pady=10)

        tk.Button(frame_btn, text="Import Excel", command=self.import_excel).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_btn, text="Export Excel", command=self.export_excel).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_btn, text="Generate Barcode", command=self.generate_barcode).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_btn, text="Check Notifications", command=self.check_notifications).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_btn, text="Add Sample", command=self.add_sample).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_btn, text="Edit Sample", command=self.edit_sample).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_btn, text="Delete Sample", command=self.delete_sample).pack(side=tk.LEFT, padx=5)

        # Treeview for data display
        self.tree = ttk.Treeview(self.root, columns=("SampleID", "Owner", "MaturationDate"), show='headings')
        self.tree.heading("SampleID", text="Sample ID")
        self.tree.heading("Owner", text="Sample Owner")
        self.tree.heading("MaturationDate", text="Maturation Date")
        self.tree.pack(expand=True, fill=tk.BOTH, pady=10)

        # Status Label
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
            self.tree.insert("", tk.END, values=(row['SampleID'], row['Owner'], mat_date))

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


if __name__ == "__main__":
    root = tk.Tk()
    app = ShelfLifeApp(root)
    root.mainloop()
