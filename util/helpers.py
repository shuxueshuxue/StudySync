# util/helpers.py
import datetime

def parse_date(date_str):
    """Parse date from user input in different formats."""
    try:
        # Try YYYY-MM-DD format
        if '-' in date_str:
            parts = date_str.split('-')
            if len(parts) == 3:
                year, month, day = parts
                return f"{year}{month.zfill(2)}{day.zfill(2)}"
        
        # Try YYYYMMDD format
        if len(date_str) == 8 and date_str.isdigit():
            return date_str
        
        # Try "today", "yesterday", etc.
        if date_str.lower() == 'today':
            return datetime.datetime.now().strftime("%Y%m%d")
        elif date_str.lower() == 'yesterday':
            return (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
        
        # If all else fails, try to parse with datetime
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%Y%m%d")
    except:
        print(f"Error: Could not parse date '{date_str}'. Please use YYYY-MM-DD format.")
        return None

def format_date_for_display(date_str):
    """Format date string for display (YYYYMMDD to Month Day, Year)."""
    try:
        dt = datetime.datetime.strptime(date_str, "%Y%m%d")
        return dt.strftime("%B %d, %Y")
    except:
        return date_str

def format_date_for_api(date):
    """Format datetime object for API (YYYYMMDD)."""
    return date.strftime("%Y%m%d")

def format_time_ago(timestamp):
    """Format a timestamp as a human-readable time ago string."""
    now = datetime.datetime.now()
    if isinstance(timestamp, str):
        dt = datetime.datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
    else:
        dt = timestamp
    
    diff = now - dt
    
    if diff.days > 365:
        years = diff.days // 365
        return f"{years} year{'s' if years != 1 else ''} ago"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "just now"

def ensure_directory(path):
    """Ensure directory exists, create if it doesn't."""
    import os
    if not os.path.exists(path):
        os.makedirs(path)
    return os.path.exists(path)
