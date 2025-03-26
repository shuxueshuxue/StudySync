import socket
import subprocess
import re
import os
import tempfile
import platform

def get_excluded_port_ranges():
    """Get the current TCP excluded port ranges dynamically"""
    if platform.system() != 'Windows':
        return []  # Currently only implemented for Windows
    
    try:
        # Run the netsh command to get current exclusions
        result = subprocess.run(
            ["netsh", "interface", "ipv4", "show", "excludedportrange", "protocol=tcp"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        
        # Parse the output to extract port ranges
        ranges = []
        lines = result.stdout.split('\n')
        for line in lines:
            # Look for lines with port ranges
            match = re.search(r'^\s*(\d+)\s+(\d+)', line)
            if match:
                start = int(match.group(1))
                end = int(match.group(2))
                ranges.append((start, end))
        
        return ranges
    except Exception as e:
        print(f"Warning: Could not get excluded port ranges: {e}")
        return []  # Return empty list if command fails

def is_port_excluded(port):
    """Check if a port is in the excluded ranges"""
    for start, end in get_excluded_port_ranges():
        if start <= port <= end:
            return True
    return False

def is_port_available(port):
    """Check if a specific port is available"""
    if is_port_excluded(port):
        return False
        
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', port))
            return True
    except OSError:
        return False

def find_available_port(start_range=11000, end_range=12000):
    """Find a port that's available and not in excluded ranges"""
    for port in range(start_range, end_range):
        if is_port_excluded(port):
            continue
            
        # Also check if port is actually bindable
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return port
        except OSError:
            continue
            
    raise RuntimeError(f"No available ports found in range {start_range}-{end_range}")

def save_port_to_file(port, filename=None):
    """Save the port number to a file in a standard location"""
    if filename is None:
        # Use a standard filename in the temp directory
        filename = os.path.join(tempfile.gettempdir(), "nova_app_port.txt")
    
    try:
        with open(filename, 'w') as f:
            f.write(str(port))
        return filename
    except Exception as e:
        print(f"Warning: Could not save port to file: {e}")
        return None

def read_port_from_file(filename=None):
    """Read the port number from a file"""
    if filename is None:
        filename = os.path.join(tempfile.gettempdir(), "nova_app_port.txt")
    
    try:
        with open(filename, 'r') as f:
            return int(f.read().strip())
    except Exception:
        return None

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
