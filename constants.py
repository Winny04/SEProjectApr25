# constants.py
import re

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
MIN_PASSWORD_LENGTH = 6
EMPLOYEE_ID_REGEX = re.compile(r"^E\d+$") 

NOTIFICATION_DAYS_BEFORE = 60 # 2 months approx.

# Default columns for displaying samples in Treeview
# Note: 'DocID' is for internal Firestore document ID, 'DisplaySampleID' is the user-facing ID
COLUMNS = ["SampleID", "Owner", "MaturationDate", "Status", "BatchID", "ProductName", "Description", "TestDate", "UserEmployeeID", "UserUsername", "UserEmail", "SubmissionDate", "NumberOfSamples"]

# Status options for samples
SAMPLE_STATUS_OPTIONS = ["pending approval", "approved", "rejected", "pending test", "tested"]
