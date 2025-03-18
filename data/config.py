# data/config.py
import os
import json
import socket

def get_app_data_dir():
    """Get the application data directory (creates it if it doesn't exist)"""
    # Use standard Windows AppData location
    app_data = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'NovaProject')
    os.makedirs(app_data, exist_ok=True)
    return app_data

def get_default_config():
    """Get default configuration values"""
    app_data = get_app_data_dir()
    nova_data_dir = os.path.join(app_data, 'NovaData')
    screenshots_dir = os.path.join(nova_data_dir, 'screenshots')
    key_points_dir = os.path.join(nova_data_dir, 'key_points')
    letters_dir = os.path.join(nova_data_dir, 'nova_letters')
    
    return {
        "username": os.environ.get('USERNAME', socket.gethostname()),
        "auto_sync": True,
        "auto_launch": False,
        "morning_webui_launch": True,  # Auto-launch web UI in the morning
        "morning_cutoff_hour": 11,     # Don't auto-launch after this hour
        "shared_folder": "",
        "local_folder": nova_data_dir,
        "screenshots_folder": screenshots_dir,
        "key_points_folder": key_points_dir,
        "letter_style": "",
        "letter_language": "English",
        "app_icon": "lightbulb",
        "screenshot_interval": 180,
        "keypoints_threshold": 15,
        "letter_generation_time": "21:00",
        "screenshot_retention_days": 7,
        "sync_frequency_minutes": 15,
        "screenshot_model": "google/gemma-3-27b-it",
        "keypoints_model": "deepseek/deepseek-r1",
        "letter_model": "deepseek/deepseek-r1",
        "openrouter_api_key": ""
    }

def init_config():
    """Initialize configuration system"""
    # Define the standard application paths
    app_data = get_app_data_dir()
    config_path = os.path.join(app_data, 'nova_config.json')
    
    # Get default config
    default_config = get_default_config()
    
    # Create default folders if they don't exist
    nova_data_dir = default_config["local_folder"]
    screenshots_dir = default_config["screenshots_folder"]
    key_points_dir = default_config["key_points_folder"]
    letters_dir = os.path.join(nova_data_dir, 'nova_letters')
    
    os.makedirs(nova_data_dir, exist_ok=True)
    os.makedirs(screenshots_dir, exist_ok=True)
    os.makedirs(key_points_dir, exist_ok=True)
    os.makedirs(letters_dir, exist_ok=True)
    
    # If config doesn't exist, create it with default values
    if not os.path.exists(config_path):
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=4)
    
    return config_path

class ConfigManager:
    """Manages application configuration"""
    
    def __init__(self, config_file=None):
        self.config_file = init_config()
        
    def load_config(self):
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                return config
            except Exception as e:
                print(f"Error loading config from {self.config_file}: {e}")
                return get_default_config()
        else:
            print(f"Config file {self.config_file} not found, using defaults")
            return get_default_config()
    
    def save_config(self, config):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def update_config(self, key, value):
        """Update a specific configuration value"""
        config = self.load_config()
        config[key] = value
        return self.save_config(config)
    
    def update_multiple(self, updates):
        """Update multiple configuration values"""
        config = self.load_config()
        for key, value in updates.items():
            config[key] = value
            
            # If updating the local_folder, also update the subfolders
            if key == 'local_folder' and value:
                try:
                    # Make sure path exists
                    os.makedirs(value, exist_ok=True)
                    
                    # Update subfolder paths
                    config['screenshots_folder'] = os.path.join(value, 'screenshots')
                    config['key_points_folder'] = os.path.join(value, 'key_points')
                    
                    # Create the subfolders
                    os.makedirs(config['screenshots_folder'], exist_ok=True)
                    os.makedirs(config['key_points_folder'], exist_ok=True)
                except Exception as e:
                    print(f"Error updating folder paths: {e}")
        
        return self.save_config(config)
    
    def get(self, key, default=None):
        """Get a configuration value"""
        config = self.load_config()
        return config.get(key, default)
    
    def validate_api_key(self):
        """Validate that the API key is configured"""
        api_key = self.get('openrouter_api_key')
        return bool(api_key and api_key.startswith('sk-or-'))
    
    def validate_folders(self):
        """Validate that required folders exist and are accessible"""
        folders = {
            'local_folder': self.get('local_folder'),
            'screenshots_folder': self.get('screenshots_folder'),
            'key_points_folder': self.get('key_points_folder')
        }
        
        results = {}
        for name, folder in folders.items():
            if not folder:
                results[name] = False
                continue
                
            # Create folder if it doesn't exist
            try:
                os.makedirs(folder, exist_ok=True)
                results[name] = os.path.exists(folder) and os.access(folder, os.W_OK)
            except Exception:
                results[name] = False
        
        # Check shared folder separately (it's optional but needs to be valid if specified)
        shared_folder = self.get('shared_folder')
        if shared_folder:
            results['shared_folder'] = os.path.exists(shared_folder) and os.access(shared_folder, os.W_OK)
        else:
            results['shared_folder'] = None  # None means not specified
            
        return results
