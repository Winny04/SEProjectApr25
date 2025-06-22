
import random
from datetime import datetime, timedelta
from typing import List, Dict
import csv
import os

# Simulated Sample Entry
class Sample:
    def __init__(self, sample_id, owner, maturation_date, status="pending", batch_id=None):
        self.sample_id = sample_id
        self.owner = owner
        self.maturation_date = maturation_date
        self.status = status
        self.batch_id = batch_id or f"BATCH{random.randint(100,999)}"

    def to_dict(self):
        return {
            "Sample ID": self.sample_id,
            "Owner": self.owner,
            "Maturation Date": self.maturation_date.strftime("%Y-%m-%d"),
            "Status": self.status,
            "Batch ID": self.batch_id
        }

# SampleShelfSystem main logic
class SampleShelfSystem:
    def __init__(self):
        self.samples: List[Sample] = []

    def generate_samples(self, count=500):
        owners = ["Alice", "Bob", "Charlie", "Diana", "Eve"]
        for i in range(count):
            days_offset = random.randint(-60, 120)
            mat_date = datetime.today() + timedelta(days=days_offset)
            owner = random.choice(owners)
            sample_id = f"SMP{i+1:04d}"
            self.samples.append(Sample(sample_id, owner, mat_date))
        print(f"✅ {count} dummy samples generated.")

    def filter_pending(self):
        return [s for s in self.samples if s.status == "pending"]

    def filter_by_maturation_range(self, days_start: int, days_end: int):
        now = datetime.today()
        return [s for s in self.samples if days_start <= (s.maturation_date - now).days <= days_end]

    def print_sample_table(self, sample_list: List[Sample]):
        print(f"\n{'Sample ID':<10} | {'Owner':<10} | {'Maturation Date':<15} | {'Status':<10} | {'Batch ID'}")
        print("-" * 65)
        for s in sample_list:
            print(f"{s.sample_id:<10} | {s.owner:<10} | {s.maturation_date.strftime('%Y-%m-%d'):<15} | {s.status:<10} | {s.batch_id}")
        print(f"\n📦 Total: {len(sample_list)} samples listed.")

    def simulate_reminders(self, samples: List[Sample], label: str):
        print(f"\n📧 Simulating email reminders for {label}:")
        for s in samples:
            print(f"Sending reminder for Sample ID {s.sample_id} - Matures on {s.maturation_date.strftime('%Y-%m-%d')} - Owner: {s.owner}")

    def export_to_csv(self, filename="exported_samples.csv"):
        with open(filename, mode='w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=self.samples[0].to_dict().keys())
            writer.writeheader()
            for sample in self.samples:
                writer.writerow(sample.to_dict())
        print(f"📁 Data exported to {filename}")

    def update_status(self, sample_id: str, new_status: str):
        found = False
        for s in self.samples:
            if s.sample_id == sample_id:
                s.status = new_status
                found = True
                print(f"✅ Sample {sample_id} status updated to '{new_status}'.")
                break
        if not found:
            print(f"❌ Sample {sample_id} not found.")

    def bulk_update(self, status_from: str, status_to: str):
        count = 0
        for s in self.samples:
            if s.status == status_from:
                s.status = status_to
                count += 1
        print(f"🔁 {count} samples updated from '{status_from}' to '{status_to}'.")

    def find_by_owner(self, owner_name: str):
        return [s for s in self.samples if s.owner.lower() == owner_name.lower()]

    def find_by_batch(self, batch_id: str):
        return [s for s in self.samples if s.batch_id.lower() == batch_id.lower()]

# --- MAIN ---
def main():
    system = SampleShelfSystem()
    system.generate_samples(500)

    pending_samples = system.filter_pending()
    system.print_sample_table(pending_samples)

    # Filter samples maturing in 14 days
    upcoming_samples = system.filter_by_maturation_range(0, 14)
    system.simulate_reminders(upcoming_samples, "Samples due in 2 weeks")

    # Export all to CSV
    system.export_to_csv("sample_data.csv")

    # Update a sample manually
    system.update_status("SMP0005", "approved")

    # Bulk status update
    system.bulk_update("pending", "under review")

    # Find by owner
    alice_samples = system.find_by_owner("Alice")
    print(f"\n🔍 Found {len(alice_samples)} samples owned by Alice")

    # Find by batch ID
    batch = alice_samples[0].batch_id if alice_samples else "BATCH123"
    batch_samples = system.find_by_batch(batch)
    print(f"\n📦 Found {len(batch_samples)} samples in batch {batch}")
    system.print_sample_table(batch_samples)

if __name__ == "__main__":
    main()
