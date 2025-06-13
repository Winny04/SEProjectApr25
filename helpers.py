# helpers.py
from constants import EMAIL_REGEX, MIN_PASSWORD_LENGTH, EMPLOYEE_ID_REGEX

def validate_email(email):
    """Validates if the provided string is a valid email format."""
    return EMAIL_REGEX.match(email) is not None

def validate_password(password):
    """Validates if the password meets the minimum length requirement."""
    return len(password) >= MIN_PASSWORD_LENGTH

def validate_employee_id(emp_id):
    """Validates if the employee ID matches the required pattern (e.g., E12345)."""
    return EMPLOYEE_ID_REGEX.match(emp_id) is not None
