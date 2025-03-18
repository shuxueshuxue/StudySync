# core/sync.py
import os
import shutil
import datetime
import time
import threading
import hashlib

class SyncManager:
    """Manages bidirectional syncing of letters between local and shared folders"""
    
    def __init__(self, config):
        self.config = config
        self.username = config.get('username', 'User')
        self.shared_folder = config.get('shared_folder', '')
        self.local_folder = config.get('local_folder', 'nova_letters')
        self.sync_frequency = config.get('sync_frequency_minutes', 15) * 60  # Convert to seconds
        self.stop_event = threading.Event()
        
        # Ensure local folder exists
        os.makedirs(self.local_folder, exist_ok=True)
        
        # Track last sync time for each file
        self.last_sync_times = {}
    
    def start_sync_loop(self):
        """Start a background thread that periodically checks for changes"""
        if not self.shared_folder or not os.path.exists(self.shared_folder):
            print("Shared folder not configured or not accessible - sync loop not started")
            return False
            
        # Create background thread
        self.sync_thread = threading.Thread(target=self._sync_loop)
        self.sync_thread.daemon = True
        self.sync_thread.start()
        
        print(f"Sync loop started (checking every {self.sync_frequency//60} minutes)")
        return True
    
    def stop_sync_loop(self):
        """Stop the sync loop"""
        self.stop_event.set()
        if hasattr(self, 'sync_thread') and self.sync_thread.is_alive():
            self.sync_thread.join(timeout=1)
    
    def _sync_loop(self):
        """Background thread to check for changes periodically"""
        while not self.stop_event.is_set():
            try:
                # Check for configuration changes
                sync_frequency_new = self.config.get('sync_frequency_minutes', 15) * 60
                if sync_frequency_new != self.sync_frequency:
                    self.sync_frequency = sync_frequency_new
                    print(f"Sync frequency updated to {self.sync_frequency//60} minutes")
                
                # Perform bidirectional sync
                self.bidirectional_sync()
                
            except Exception as e:
                print(f"Error in sync loop: {e}")
            
            # Sleep until next check, with periodic checks for stop event
            start_time = time.time()
            while time.time() - start_time < self.sync_frequency:
                if self.stop_event.is_set():
                    break
                time.sleep(1)
    
    def bidirectional_sync(self):
        """Perform bidirectional sync between local and shared folders"""
        if not self.shared_folder or not os.path.exists(self.shared_folder):
            print("Shared folder not configured or not accessible")
            return False
        
        try:
            # Ensure user folder exists in shared space
            user_folder = os.path.join(self.shared_folder, self.username)
            os.makedirs(user_folder, exist_ok=True)
            
            # 1. Local to shared sync (outgoing changes)
            local_to_shared_count = self._sync_local_to_shared()
            
            # 2. Shared to local sync (incoming changes from others)
            shared_to_local_count = self._sync_shared_to_local()
            
            # 3. Detect and resolve conflicts
            conflicts_count = self._detect_and_resolve_conflicts()
            
            if local_to_shared_count > 0 or shared_to_local_count > 0 or conflicts_count > 0:
                print(f"Sync completed: {local_to_shared_count} outgoing, {shared_to_local_count} incoming, {conflicts_count} conflicts resolved")
                return True
            return False
            
        except Exception as e:
            print(f"Error during bidirectional sync: {e}")
            return False
    
    def _sync_local_to_shared(self):
        """Sync local letters to shared folder"""
        sync_count = 0
        user_folder = os.path.join(self.shared_folder, self.username)
        
        # Go through all local letters
        for filename in os.listdir(self.local_folder):
            if not self._is_letter_file(filename):
                continue
                
            local_path = os.path.join(self.local_folder, filename)
            shared_path = os.path.join(user_folder, filename)
            
            # Check if the letter needs to be synced
            if self._needs_sync(local_path, shared_path):
                shutil.copy2(local_path, shared_path)
                self.last_sync_times[filename] = time.time()
                sync_count += 1
                print(f"Synced local → shared: {filename}")
        
        return sync_count
    
    def bidirectional_sync(self):
        """Perform bidirectional sync between local and shared folders"""
        if not self.shared_folder or not os.path.exists(self.shared_folder):
            print("Shared folder not configured or not accessible")
            return False
        
        try:
            # Ensure user folder exists in shared space
            user_folder = os.path.join(self.shared_folder, self.username)
            os.makedirs(user_folder, exist_ok=True)
            
            # 1. Local to shared sync (outgoing changes)
            local_to_shared_count = self._sync_local_to_shared()
            
            # 2. Shared to local sync (incoming changes from others AND the user's own files that were edited externally)
            shared_to_local_count = self._sync_shared_to_local()
            
            # 3. Detect and resolve conflicts
            conflicts_count = self._detect_and_resolve_conflicts()
            
            if local_to_shared_count > 0 or shared_to_local_count > 0 or conflicts_count > 0:
                print(f"Sync completed: {local_to_shared_count} outgoing, {shared_to_local_count} incoming, {conflicts_count} conflicts resolved")
                return True
            else:
                print("Sync completed: No changes detected")
            return False
            
        except Exception as e:
            print(f"Error during bidirectional sync: {e}")
            return False

    def _sync_shared_to_local(self):
        """Sync letters from shared folder to local folder (including own files edited by others)"""
        sync_count = 0
        
        # Exit if no shared folder
        if not self.shared_folder or not os.path.exists(self.shared_folder):
            return 0
            
        # Go through all user folders in shared space
        for username in os.listdir(self.shared_folder):
            user_folder = os.path.join(self.shared_folder, username)
            if not os.path.isdir(user_folder):
                continue
                
            # Check for letters in this user's folder
            for filename in os.listdir(user_folder):
                if not self._is_letter_file(filename):
                    continue
                    
                shared_path = os.path.join(user_folder, filename)
                
                # Different handling based on if it's the user's own files or others' files
                if username == self.username:
                    # For user's own letters, sync back if shared is newer than local
                    local_path = os.path.join(self.local_folder, filename)
                    
                    if os.path.exists(local_path):
                        # If both exist, get timestamps and hashes
                        shared_mod_time = os.path.getmtime(shared_path)
                        local_mod_time = os.path.getmtime(local_path)
                        
                        shared_hash = self._get_file_hash(shared_path)
                        local_hash = self._get_file_hash(local_path)
                        
                        # Only sync if content different and shared is newer
                        if shared_hash != local_hash and shared_mod_time > local_mod_time:
                            # Create backup
                            backup_path = os.path.join(self.local_folder, f"{filename}.local_backup")
                            shutil.copy2(local_path, backup_path)
                            # Copy from shared to local
                            shutil.copy2(shared_path, local_path)
                            self.last_sync_times[filename] = time.time()
                            sync_count += 1
                            print(f"Synced shared → local (own file updated remotely): {filename}")
                    else:
                        # If local doesn't exist but shared does, copy it
                        shutil.copy2(shared_path, local_path)
                        self.last_sync_times[filename] = time.time()
                        sync_count += 1
                        print(f"Synced shared → local (own file missing locally): {filename}")
                else:
                    # For other users' letters, store in community subfolder
                    local_user_folder = os.path.join(self.local_folder, "_community", username)
                    os.makedirs(local_user_folder, exist_ok=True)
                    
                    local_path = os.path.join(local_user_folder, filename)
                    
                    # Check if the letter needs to be synced
                    if self._needs_sync(shared_path, local_path):
                        shutil.copy2(shared_path, local_path)
                        self.last_sync_times[f"{username}/{filename}"] = time.time()
                        sync_count += 1
                        print(f"Synced shared → local: {username}/{filename}")
        
        return sync_count
    
    def _detect_and_resolve_conflicts(self):
        """Detect and resolve conflicts between local and shared letters"""
        conflict_count = 0
        user_folder = os.path.join(self.shared_folder, self.username)
        
        # Check for conflicts in user's own letters
        for filename in os.listdir(self.local_folder):
            if not self._is_letter_file(filename):
                continue
                
            local_path = os.path.join(self.local_folder, filename)
            shared_path = os.path.join(user_folder, filename)
            
            # Only check files that exist in both locations
            if not os.path.exists(shared_path):
                continue
                
            local_hash = self._get_file_hash(local_path)
            shared_hash = self._get_file_hash(shared_path)
            
            # If content differs but modification times are close, we have a conflict
            if local_hash != shared_hash:
                local_mod_time = os.path.getmtime(local_path)
                shared_mod_time = os.path.getmtime(shared_path)
                
                # Resolve based on which is newer
                if shared_mod_time > local_mod_time:
                    # Shared is newer - keep a backup of local and use shared
                    backup_path = os.path.join(self.local_folder, f"{filename}.local_backup")
                    shutil.copy2(local_path, backup_path)
                    shutil.copy2(shared_path, local_path)
                    print(f"Conflict: {filename} - shared version is newer, local backed up")
                else:
                    # Local is newer - update shared
                    backup_path = os.path.join(user_folder, f"{filename}.shared_backup")
                    shutil.copy2(shared_path, backup_path)
                    shutil.copy2(local_path, shared_path)
                    print(f"Conflict: {filename} - local version is newer, shared backed up")
                
                conflict_count += 1
                self.last_sync_times[filename] = time.time()
        
        return conflict_count
    
    def _needs_sync(self, source_path, dest_path):
        """Check if a file needs to be synced based on modification times"""
        # If destination doesn't exist, definitely sync
        if not os.path.exists(dest_path):
            return True
            
        # Compare modification times
        source_mod_time = os.path.getmtime(source_path)
        dest_mod_time = os.path.getmtime(dest_path)
        
        # Get filename for tracking last sync time
        filename = os.path.basename(source_path)
        
        # If we've synced this file before, check if it's been modified since
        if filename in self.last_sync_times:
            last_sync = self.last_sync_times[filename]
            return source_mod_time > last_sync and source_mod_time > dest_mod_time
        
        # Otherwise, sync if source is newer
        return source_mod_time > dest_mod_time
    
    def _get_file_hash(self, file_path):
        """Get a hash of the file contents for comparison"""
        if not os.path.exists(file_path):
            return None
            
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            return file_hash
        except Exception as e:
            print(f"Error getting file hash for {file_path}: {e}")
            return None
    
    def _is_letter_file(self, filename):
        """Check if a filename is a valid letter file"""
        return (filename.startswith("nova_letter_") and 
                (filename.endswith(".html") or filename.endswith(".md")))
    
    def sync_all_letters(self):
        """Sync all letters to the shared folder"""
        if not self.shared_folder or not os.path.exists(self.shared_folder):
            print("Shared folder not configured or not accessible")
            return False
        
        # Ensure user folder exists in shared space
        user_folder = os.path.join(self.shared_folder, self.username)
        os.makedirs(user_folder, exist_ok=True)
        
        synced_count = 0
        for filename in os.listdir(self.local_folder):
            if self._is_letter_file(filename):
                # Extract YYYYMMDD part from filename
                if filename.endswith(".html"):
                    date_str = filename[len("nova_letter_"):-5]
                else:  # .md file
                    date_str = filename[len("nova_letter_"):-3]
                
                # Check if the letter needs to be synced
                local_letter_path = os.path.join(self.local_folder, filename)
                shared_letter_path = os.path.join(user_folder, filename)
                
                if self._needs_sync(local_letter_path, shared_letter_path):
                    shutil.copy2(local_letter_path, shared_letter_path)
                    self.last_sync_times[filename] = time.time()
                    synced_count += 1
                    print(f"Synced letter: {date_str} ({filename})")
        
        print(f"Synced {synced_count} letters")
        return synced_count > 0
    
    def sync_letter(self, date_str):
        """Sync a specific letter to the shared folder"""
        if not self.shared_folder or not os.path.exists(self.shared_folder):
            print("Shared folder not configured or not accessible")
            return False
        
        # Check both HTML and MD formats
        letter_path_html = os.path.join(self.local_folder, f"nova_letter_{date_str}.html")
        letter_path_md = os.path.join(self.local_folder, f"nova_letter_{date_str}.md")
        
        letter_path = None
        if os.path.exists(letter_path_html):
            letter_path = letter_path_html
        elif os.path.exists(letter_path_md):
            letter_path = letter_path_md
        
        if not letter_path:
            print(f"Letter not found for date: {date_str}")
            return False
        
        try:
            # Ensure user folder exists
            user_folder = os.path.join(self.shared_folder, self.username)
            os.makedirs(user_folder, exist_ok=True)
            
            # Copy letter to shared folder
            shared_letter_path = os.path.join(user_folder, os.path.basename(letter_path))
            shutil.copy2(letter_path, shared_letter_path)
            self.last_sync_times[os.path.basename(letter_path)] = time.time()
            print(f"Synced letter: {date_str} ({os.path.basename(letter_path)})")
            return True
            
        except Exception as e:
            print(f"Error syncing letter {date_str}: {e}")
            return False
    
    def unsync_letter(self, date_str):
        """Remove a letter from the shared folder"""
        if not self.shared_folder or not os.path.exists(self.shared_folder):
            print("Shared folder not configured or not accessible")
            return False
        
        try:
            # Check both HTML and MD formats
            user_folder = os.path.join(self.shared_folder, self.username)
            shared_letter_path_html = os.path.join(user_folder, f"nova_letter_{date_str}.html")
            shared_letter_path_md = os.path.join(user_folder, f"nova_letter_{date_str}.md")
            
            removed = False
            # Remove HTML version if it exists
            if os.path.exists(shared_letter_path_html):
                os.remove(shared_letter_path_html)
                if f"nova_letter_{date_str}.html" in self.last_sync_times:
                    del self.last_sync_times[f"nova_letter_{date_str}.html"]
                removed = True
            
            # Remove MD version if it exists
            if os.path.exists(shared_letter_path_md):
                os.remove(shared_letter_path_md)
                if f"nova_letter_{date_str}.md" in self.last_sync_times:
                    del self.last_sync_times[f"nova_letter_{date_str}.md"]
                removed = True
            
            if removed:
                print(f"Unsynced letter: {date_str}")
                return True
            
            print(f"No shared letter found for {date_str}")
            return False
            
        except Exception as e:
            print(f"Error unsyncing letter {date_str}: {e}")
            return False
    
    def get_community_letters(self):
        """Get all letters shared by the community"""
        community = {}
        
        if self.shared_folder and os.path.exists(self.shared_folder):
            # Get all user folders
            for username in os.listdir(self.shared_folder):
                user_path = os.path.join(self.shared_folder, username)
                if os.path.isdir(user_path):
                    user_letters = []
                    
                    # Get all letters for this user
                    for filename in os.listdir(user_path):
                        if self._is_letter_file(filename):
                            # Extract date part depending on file extension
                            if filename.endswith(".html"):
                                date_str = filename[len("nova_letter_"):-5]
                                format = "html"
                            else:  # .md file
                                date_str = filename[len("nova_letter_"):-3]
                                format = "markdown"
                            
                            try:
                                date = datetime.datetime.strptime(date_str, "%Y%m%d")
                                letter_date = date.strftime("%Y-%m-%d")
                                user_letters.append({
                                    'date': letter_date,
                                    'date_str': date_str,
                                    'format': format
                                })
                            except ValueError:
                                pass
                    
                    if user_letters:
                        community[username] = sorted(user_letters, key=lambda x: x['date'], reverse=True)
        
        return community
    
    def get_user_letters(self):
        """Get all letters for the current user"""
        letters = []
        
        if os.path.exists(self.local_folder):
            for filename in os.listdir(self.local_folder):
                if self._is_letter_file(filename):
                    # Extract date part depending on file extension
                    if filename.endswith(".html"):
                        date_str = filename[len("nova_letter_"):-5]
                        format = "html"
                    else:  # .md file
                        date_str = filename[len("nova_letter_"):-3]
                        format = "markdown"
                    
                    try:
                        date = datetime.datetime.strptime(date_str, "%Y%m%d")
                        letter_date = date.strftime("%Y-%m-%d")
                        
                        # Check if synced
                        synced = False
                        if self.shared_folder and os.path.exists(self.shared_folder):
                            user_folder = os.path.join(self.shared_folder, self.username)
                            if os.path.exists(os.path.join(user_folder, filename)):
                                synced = True
                                    
                        letters.append({
                            'date': letter_date,
                            'date_str': date_str,
                            'synced': synced,
                            'format': format
                        })
                    except ValueError:
                        pass
        
        return sorted(letters, key=lambda x: x['date'], reverse=True)