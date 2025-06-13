# constants.py
import re

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
MIN_PASSWORD_LENGTH = 6
EMPLOYEE_ID_REGEX = re.compile(r"^E\d+$") 

NOTIFICATION_DAYS_BEFORE = 60 # 2 months approx.

# Expected columns for Excel data, 'Status' will be added if not present
# Note: These columns are primarily for local Excel import/export and Treeview display.
# Firestore documents will have their own fields.
COLUMNS = ["SampleID", "Owner", "MaturationDate", "Status"] 
