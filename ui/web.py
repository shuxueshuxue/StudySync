# ui/web.py
import os
import threading
import re
import markdown
import jinja2
import hashlib
from flask import Flask, render_template, jsonify, request, send_from_directory
from werkzeug.serving import make_server

class WebUI:
    """Web UI for Nova Project"""
    
    def __init__(self, config, port=11000):
        self.config = config
        self.port = port
        self.flask_thread = None
        self.flask_server = None
        self.selected_folder = None
        
        # Create Flask app
        self.app = Flask(
            __name__,
            static_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web/static'),
            template_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web/templates')
        )
        
        # Configure routes
        self._configure_routes()
    
    def _configure_routes(self):
        """Configure Flask routes"""
        # Main routes
        @self.app.route('/')
        def index():
            return render_template('index.html', 
                                port=self.port, 
                                username=self.config.get('username', 'User'),
                                app_icon=self.config.get('app_icon', 'lightbulb'))
        
        @self.app.route('/settings')
        def settings():
            return render_template('settings.html', 
                                config=self.config, 
                                port=self.port)
        
        # API routes
        @self.app.route('/api/settings', methods=['GET', 'POST'])
        def api_settings():
            from data.config import ConfigManager
            config_manager = ConfigManager()
            
            if request.method == 'POST':
                data = request.json
                
                # Normalize folder paths to ensure proper separators
                if 'local_folder' in data and data['local_folder']:
                    data['local_folder'] = os.path.normpath(data['local_folder'])
                    
                if 'shared_folder' in data and data['shared_folder']:
                    data['shared_folder'] = os.path.normpath(data['shared_folder'])
                
                # Update config
                updates = {
                    'username': data.get('username', self.config.get('username')),
                    'auto_sync': data.get('auto_sync', self.config.get('auto_sync')),
                    'auto_launch': data.get('auto_launch', self.config.get('auto_launch')),
                    'shared_folder': data.get('shared_folder', self.config.get('shared_folder')),
                    'local_folder': data.get('local_folder', self.config.get('local_folder')),
                    'letter_style': data.get('letter_style', self.config.get('letter_style')),
                    'letter_language': data.get('letter_language', self.config.get('letter_language')),
                    'openrouter_api_key': data.get('openrouter_api_key', self.config.get('openrouter_api_key')),
                    'app_icon': data.get('app_icon', self.config.get('app_icon')),
                    'screenshot_interval': int(data.get('screenshot_interval', self.config.get('screenshot_interval'))),
                    'keypoints_threshold': int(data.get('keypoints_threshold', self.config.get('keypoints_threshold'))),
                    'screenshot_retention_days': int(data.get('screenshot_retention_days', self.config.get('screenshot_retention_days'))),
                    'letter_generation_time': data.get('letter_generation_time', self.config.get('letter_generation_time')),
                    'sync_frequency_minutes': int(data.get('sync_frequency_minutes', self.config.get('sync_frequency_minutes'))),
                    'screenshot_model': data.get('screenshot_model', self.config.get('screenshot_model')),
                    'keypoints_model': data.get('keypoints_model', self.config.get('keypoints_model')),
                    'letter_model': data.get('letter_model', self.config.get('letter_model'))
                }
                
                # Save to config file
                if config_manager.update_multiple(updates):
                    # Update current config
                    for key, value in updates.items():
                        self.config[key] = value
                    
                    # Create user folder in shared space if it doesn't exist
                    if self.config.get('shared_folder') and os.path.exists(self.config.get('shared_folder')):
                        user_folder = os.path.join(self.config.get('shared_folder'), self.config.get('username'))
                        os.makedirs(user_folder, exist_ok=True)
                    
                    # Setup auto-launch if enabled
                    if data.get('auto_launch', False):
                        self._setup_auto_launch()
                    else:
                        self._remove_auto_launch()
                    
                    return jsonify({'status': 'success'})
                
                return jsonify({'error': 'Failed to save settings'})
            else:
                return jsonify(self.config)
        
        @self.app.route('/api/letters')
        def api_letters():
            """Get all letters for the current user (both .html and .md)"""
            letters_folder = self.config.get('local_folder', 'nova_letters')
            letters = []
            
            try:
                if os.path.exists(letters_folder):
                    for filename in os.listdir(letters_folder):
                        if filename.startswith("nova_letter_"):
                            # Check if it's an html or md file
                            if filename.endswith(".html") or filename.endswith(".md"):
                                # Extract date part depending on the extension
                                if filename.endswith(".html"):
                                    date_str = filename[len("nova_letter_"):-5]
                                    format = "html"
                                else:  # .md file
                                    date_str = filename[len("nova_letter_"):-3]
                                    format = "markdown"
                                
                                try:
                                    import datetime
                                    date = datetime.datetime.strptime(date_str, "%Y%m%d")
                                    letter_date = date.strftime("%Y-%m-%d")
                                    
                                    # Check if synced
                                    synced = False
                                    if self.config.get('shared_folder') and os.path.exists(self.config.get('shared_folder')):
                                        user_folder = os.path.join(self.config.get('shared_folder'), self.config.get('username', 'User'))
                                        shared_letter_path = os.path.join(user_folder, filename)
                                        if os.path.exists(shared_letter_path):
                                            synced = True
                                        
                                    letters.append({
                                        'date': letter_date,
                                        'date_str': date_str,
                                        'synced': synced,
                                        'format': format
                                    })
                                except ValueError:
                                    # Skip if date can't be parsed
                                    pass
            except Exception as e:
                print(f"Error loading letters: {e}")
            
            return jsonify(sorted(letters, key=lambda x: x['date'], reverse=True))
        
        @self.app.route('/api/community_letters')
        def api_community_letters():
            """Get community letters (both .html and .md)"""
            community = {}
            
            try:
                shared_folder = self.config.get('shared_folder')
                if shared_folder and os.path.exists(shared_folder):
                    # Get all user folders
                    for username in os.listdir(shared_folder):
                        user_path = os.path.join(shared_folder, username)
                        if os.path.isdir(user_path):
                            user_letters = []
                            
                            # Get all letters for this user
                            for filename in os.listdir(user_path):
                                if filename.startswith("nova_letter_"):
                                    # Check if it's an html or md file
                                    if filename.endswith(".html") or filename.endswith(".md"):
                                        # Extract date part depending on the extension
                                        if filename.endswith(".html"):
                                            date_str = filename[len("nova_letter_"):-5]
                                            format = "html"
                                        else:  # .md file
                                            date_str = filename[len("nova_letter_"):-3]
                                            format = "markdown"
                                        
                                        try:
                                            import datetime
                                            date = datetime.datetime.strptime(date_str, "%Y%m%d")
                                            letter_date = date.strftime("%Y-%m-%d")
                                            user_letters.append({
                                                'date': letter_date,
                                                'date_str': date_str,
                                                'format': format
                                            })
                                        except ValueError:
                                            # Skip if date can't be parsed
                                            pass
                            
                            if user_letters:
                                community[username] = sorted(user_letters, key=lambda x: x['date'], reverse=True)
            except Exception as e:
                print(f"Error loading community letters: {e}")
            
            return jsonify(community)
        
        @self.app.route('/api/letter/<date_str>')
        def api_letter(date_str):
            """Get a specific letter (either .html or .md)"""
            letters_folder = self.config.get('local_folder', 'nova_letters')
            
            # Try both formats
            letter_path_html = os.path.join(letters_folder, f"nova_letter_{date_str}.html")
            letter_path_md = os.path.join(letters_folder, f"nova_letter_{date_str}.md")
            
            letter_path = None
            letter_format = None
            
            if os.path.exists(letter_path_html):
                letter_path = letter_path_html
                letter_format = 'html'
            elif os.path.exists(letter_path_md):
                letter_path = letter_path_md
                letter_format = 'markdown'
                
            if not letter_path:
                return jsonify({'error': f'Letter for {date_str} not found'}), 404
            
            try:
                with open(letter_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Force specific format detection based on content
                if letter_format == 'html':
                    # Double-check it actually looks like HTML
                    if not content.strip().startswith('<'):
                        letter_format = 'markdown'
                else:  # markdown format
                    # Double-check it's not actually HTML
                    if content.strip().startswith('<!DOCTYPE html>') or content.strip().startswith('<html'):
                        letter_format = 'html'
                
                return jsonify({
                    'content': content,
                    'format': letter_format
                })
            except Exception as e:
                return jsonify({'error': f'Error reading letter: {str(e)}'}), 500
        
        @self.app.route('/api/community_letter/<username>/<date_str>')
        def api_community_letter(username, date_str):
            """Get a community letter (either .html or .md)"""
            shared_folder = self.config.get('shared_folder')
            
            if not shared_folder or not os.path.exists(shared_folder):
                return jsonify({'error': 'Shared folder not configured'}), 404
            
            # Try both formats
            letter_path_html = os.path.join(shared_folder, username, f"nova_letter_{date_str}.html")
            letter_path_md = os.path.join(shared_folder, username, f"nova_letter_{date_str}.md")
            
            letter_path = None
            letter_format = None
            
            if os.path.exists(letter_path_html):
                letter_path = letter_path_html
                letter_format = 'html'
            elif os.path.exists(letter_path_md):
                letter_path = letter_path_md
                letter_format = 'markdown'
                
            if not letter_path:
                return jsonify({'error': f'Letter for {date_str} not found'}), 404
            
            try:
                with open(letter_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Force specific format detection based on content
                if letter_format == 'html':
                    # Double-check it actually looks like HTML
                    if not content.strip().startswith('<'):
                        letter_format = 'markdown'
                else:  # markdown format
                    # Double-check it's not actually HTML
                    if content.strip().startswith('<!DOCTYPE html>') or content.strip().startswith('<html'):
                        letter_format = 'html'
                
                return jsonify({
                    'content': content,
                    'format': letter_format
                })
            except Exception as e:
                return jsonify({'error': f'Error reading letter: {str(e)}'}), 500
        
        @self.app.route('/api/sync_letter/<date_str>', methods=['POST'])
        def api_sync_letter(date_str):
            """Sync or unsync a letter"""
            data = request.json
            sync_action = data.get('action', 'sync')  # sync or unsync
            
            from core.sync import SyncManager
            sync_manager = SyncManager(self.config)
            
            try:
                if sync_action == 'sync':
                    result = sync_manager.sync_letter(date_str)
                    if result:
                        return jsonify({'status': 'synced'})
                    else:
                        return jsonify({'error': 'Failed to sync letter'}), 500
                else:
                    result = sync_manager.unsync_letter(date_str)
                    if result:
                        return jsonify({'status': 'unsynced'})
                    else:
                        return jsonify({'error': 'Failed to unsync letter'}), 500
            except Exception as e:
                return jsonify({'error': f'Error syncing letter: {str(e)}'}), 500
        
        @self.app.route('/api/sync_letters_now', methods=['POST'])
        def api_sync_letters_now():
            """Sync all letters bidirectionally"""
            try:
                from core.sync import SyncManager
                sync_manager = SyncManager(self.config)
                
                # Use bidirectional_sync for complete two-way sync
                result = sync_manager.bidirectional_sync()
                
                if result:
                    return jsonify({'status': 'success', 'message': 'Letters synced successfully'})
                else:
                    return jsonify({'status': 'success', 'message': 'Sync completed (no changes detected)'})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/generate_letter', methods=['POST'])
        def api_generate_letter():
            """Generate a new letter"""
            try:
                from core.letter import LetterGenerator
                letter_generator = LetterGenerator(self.config)
                threading.Thread(target=letter_generator.generate_letter, daemon=True).start()
                return jsonify({'status': 'generating'})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/edit_letter', methods=['POST'])
        def api_edit_letter():
            """Edit a letter (either .html or .md)"""
            try:
                data = request.json
                date_str = data.get('date_str')
                username = data.get('username')
                content = data.get('content')
                format = data.get('format', 'markdown')  # Default to markdown
                
                # Validate input
                if not date_str or not username or not content:
                    return jsonify({'error': 'Missing required fields'}), 400
                
                # Determine the letter path
                if username == self.config.get('username'):
                    # Edit local letter
                    letters_folder = self.config.get('local_folder', 'nova_letters')
                    
                    # First try to find existing letter in either format
                    letter_path_html = os.path.join(letters_folder, f"nova_letter_{date_str}.html")
                    letter_path_md = os.path.join(letters_folder, f"nova_letter_{date_str}.md")
                    
                    if os.path.exists(letter_path_html):
                        letter_path = letter_path_html
                        existing_format = 'html'
                    elif os.path.exists(letter_path_md):
                        letter_path = letter_path_md
                        existing_format = 'markdown'
                    else:
                        # Create a new file based on the format
                        extension = '.html' if format == 'html' else '.md'
                        letter_path = os.path.join(letters_folder, f"nova_letter_{date_str}{extension}")
                        existing_format = format
                else:
                    # Edit shared letter
                    shared_folder = self.config.get('shared_folder')
                    if not shared_folder or not os.path.exists(shared_folder):
                        return jsonify({'error': 'Shared folder not configured'}), 404
                    
                    # First try to find existing letter in either format
                    letter_path_html = os.path.join(shared_folder, username, f"nova_letter_{date_str}.html")
                    letter_path_md = os.path.join(shared_folder, username, f"nova_letter_{date_str}.md")
                    
                    if os.path.exists(letter_path_html):
                        letter_path = letter_path_html
                        existing_format = 'html'
                    elif os.path.exists(letter_path_md):
                        letter_path = letter_path_md
                        existing_format = 'markdown'
                    else:
                        return jsonify({'error': 'Letter not found'}), 404
                
                # Check if we need to convert formats
                if format != existing_format and os.path.exists(letter_path):
                    # We're changing formats, so delete the old file after saving the new one
                    old_path = letter_path
                    extension = '.html' if format == 'html' else '.md'
                    new_path = os.path.join(os.path.dirname(letter_path), f"nova_letter_{date_str}{extension}")
                    letter_path = new_path
                    
                    # If new file already exists, remove it for clean overwrite
                    if os.path.exists(new_path):
                        os.remove(new_path)
                
                # Save the content
                if format == 'markdown' or letter_path.endswith('.md'):
                    # No need to convert markdown content
                    with open(letter_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                else:
                    # For HTML, check if we need to convert from markdown
                    if content.strip().startswith('#') and not content.strip().startswith('<!DOCTYPE'):
                        # Content is markdown, convert to HTML
                        from core.letter import LetterGenerator
                        letter_generator = LetterGenerator(self.config)
                        
                        # Format date for the template
                        import datetime
                        date_obj = datetime.datetime.strptime(date_str, "%Y%m%d")
                        date_formatted = date_obj.strftime("%B %d, %Y")
                        
                        # Convert markdown to HTML
                        letter_html = letter_generator._process_markdown_to_html(content, date_formatted)
                        with open(letter_path, 'w', encoding='utf-8') as f:
                            f.write(letter_html)
                    else:
                        # Content is already HTML, save directly
                        with open(letter_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                
                # If we changed formats, remove the old file
                if format != existing_format and os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except Exception as e:
                        print(f"Warning: Could not remove old file {old_path}: {e}")
                
                return jsonify({'status': 'success'})
            except Exception as e:
                return jsonify({'error': f'Error saving letter: {str(e)}'}), 500
        
        @self.app.route('/api/browse_folder', methods=['GET'])
        def api_browse_folder():
            if self.selected_folder:
                folder_path = self.selected_folder
                self.selected_folder = None  # Clear after use
                return jsonify({'folder_path': folder_path})
            else:
                return jsonify({'error': 'No folder selected - use desktop UI to select folders'}), 400
    
    def _setup_auto_launch(self):
        """Set up auto-launch at system startup"""
        try:
            import platform
            import subprocess
            import os
            
            if platform.system() == 'Windows':
                # Get the path to the startup folder
                startup_folder = os.path.join(os.environ.get('APPDATA', ''), 
                                        'Microsoft\\Windows\\Start Menu\\Programs\\Startup')
                
                # Ensure the startup folder exists
                os.makedirs(startup_folder, exist_ok=True)
                
                # Get the path to Nova.cmd in the root folder
                app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                root_dir = os.path.dirname(app_dir)  # Go up to the root where Nova.cmd is
                cmd_path = os.path.join(root_dir, 'Nova.cmd')
                
                # Check if Nova.cmd exists
                if not os.path.exists(cmd_path):
                    print(f"Warning: Nova.cmd not found at: {cmd_path}")
                    return
                
                # Create a shortcut using PowerShell (more reliable than VBS)
                ps_command = f'''
                $WshShell = New-Object -ComObject WScript.Shell
                $Shortcut = $WshShell.CreateShortcut("{os.path.join(startup_folder, 'Nova Project.lnk')}")
                $Shortcut.TargetPath = "{cmd_path}"
                $Shortcut.WorkingDirectory = "{root_dir}"
                $Shortcut.Save()
                '''
                
                # Run PowerShell command with hidden window
                subprocess.run(['powershell', '-Command', ps_command], 
                            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                
                print("Auto-launch enabled on Windows")
                
            elif platform.system() == 'Darwin':  # macOS
                plist_path = os.path.expanduser('~/Library/LaunchAgents/com.novaproject.launcher.plist')
                app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                root_dir = os.path.dirname(app_dir)
                
                # For macOS, we need a shell script launcher
                launcher_path = os.path.join(root_dir, 'Nova.sh')
                
                # Create shell script if it doesn't exist
                if not os.path.exists(launcher_path):
                    with open(launcher_path, 'w') as f:
                        f.write(f'''#!/bin/bash
    cd "{root_dir}"
    ./python_env/bin/pythonw ./app/nova_app.py
    ''')
                    
                    # Make it executable
                    os.chmod(launcher_path, 0o755)
                
                plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
        <key>Label</key>
        <string>com.novaproject.launcher</string>
        <key>ProgramArguments</key>
        <array>
            <string>{launcher_path}</string>
        </array>
        <key>RunAtLoad</key>
        <true/>
    </dict>
    </plist>
    '''
                try:
                    with open(plist_path, 'w') as f:
                        f.write(plist_content)
                    os.system(f'launchctl load {plist_path}')
                    print("Auto-launch enabled on macOS")
                except Exception as e:
                    print(f"Error setting up auto-launch on macOS: {e}")
            
            elif platform.system() == 'Linux':
                autostart_dir = os.path.expanduser('~/.config/autostart')
                if not os.path.exists(autostart_dir):
                    os.makedirs(autostart_dir)
                
                app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                root_dir = os.path.dirname(app_dir)
                
                # For Linux, create a shell script launcher if it doesn't exist
                launcher_path = os.path.join(root_dir, 'Nova.sh')
                
                if not os.path.exists(launcher_path):
                    with open(launcher_path, 'w') as f:
                        f.write(f'''#!/bin/bash
    cd "{root_dir}"
    ./python_env/bin/pythonw ./app/nova_app.py
    ''')
                    
                    # Make it executable
                    os.chmod(launcher_path, 0o755)
                
                desktop_file = os.path.join(autostart_dir, 'novaproject.desktop')
                desktop_content = f'''[Desktop Entry]
    Type=Application
    Name=Nova Project
    Exec={launcher_path}
    Terminal=false
    X-GNOME-Autostart-enabled=true
    '''
                try:
                    with open(desktop_file, 'w') as f:
                        f.write(desktop_content)
                    os.chmod(desktop_file, 0o755)
                    print("Auto-launch enabled on Linux")
                except Exception as e:
                    print(f"Error setting up auto-launch on Linux: {e}")
            
        except Exception as e:
            print(f"Error setting up auto-launch: {e}")

    def _remove_auto_launch(self):
        """Remove auto-launch from system startup"""
        try:
            import platform
            import os
            
            if platform.system() == 'Windows':
                # Remove the shortcut from startup folder
                startup_folder = os.path.join(os.environ.get('APPDATA', ''), 
                                        'Microsoft\\Windows\\Start Menu\\Programs\\Startup')
                shortcut_path = os.path.join(startup_folder, 'Nova Project.lnk')
                
                if os.path.exists(shortcut_path):
                    os.remove(shortcut_path)
                    print("Auto-launch disabled on Windows")
            
            elif platform.system() == 'Darwin':  # macOS
                plist_path = os.path.expanduser('~/Library/LaunchAgents/com.novaproject.launcher.plist')
                if os.path.exists(plist_path):
                    try:
                        os.system(f'launchctl unload {plist_path}')
                        os.remove(plist_path)
                        print("Auto-launch disabled on macOS")
                    except Exception as e:
                        print(f"Error removing auto-launch on macOS: {e}")
            
            elif platform.system() == 'Linux':
                desktop_file = os.path.expanduser('~/.config/autostart/novaproject.desktop')
                if os.path.exists(desktop_file):
                    try:
                        os.remove(desktop_file)
                        print("Auto-launch disabled on Linux")
                    except Exception as e:
                        print(f"Error removing auto-launch on Linux: {e}")
            
        except Exception as e:
            print(f"Error removing auto-launch: {e}")
    
    def start(self):
        """Start the web server in a separate thread"""
        # Don't start if already running
        if self.flask_thread and self.flask_thread.is_alive():
            return
            
        def run_flask():
            try:
                self.flask_server = make_server('0.0.0.0', self.port, self.app)
                self.flask_server.serve_forever()
            except Exception as e:
                print(f"Error starting web server: {e}")
        
        self.flask_thread = threading.Thread(target=run_flask)
        self.flask_thread.daemon = True
        self.flask_thread.start()
        print(f"Web server started on http://localhost:{self.port}")
    
    def start_in_main_thread(self):
        """Start the web server in the main thread (blocks)"""
        print(f"Starting web server on http://localhost:{self.port}")
        try:
            self.app.run(host='0.0.0.0', port=self.port, debug=False)
        except KeyboardInterrupt:
            print("Web server stopped")
        except Exception as e:
            print(f"Error starting web server: {e}")
    
    def stop(self):
        """Stop the web server"""
        if self.flask_server:
            try:
                self.flask_server.shutdown()
                print("Web server stopped")
            except Exception as e:
                print(f"Error stopping web server: {e}")
    
    def set_selected_folder(self, folder_path):
        """Set the selected folder from desktop UI file dialog"""
        self.selected_folder = folder_path
