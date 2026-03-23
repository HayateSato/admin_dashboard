from datetime import datetime

def get_current_timestamp() -> str:
    """Get current timestamp in ISO format"""
    return datetime.now().isoformat()