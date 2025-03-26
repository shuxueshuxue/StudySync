# Nova Project - Combined Source Code

# Generated on: 2025-03-21 11:19:56

# This file contains the combined source code of the Nova Project


## File: core\key_points.py

```python
# core/key_points.py
import os
import datetime
import requests
import threading
import json

class KeyPointsExtractor:
    """Extracts key points from screenshots"""
    
    def __init__(self, config, screenshots_queue):
        self.config = config
        self.screenshots_queue = screenshots_queue
        self.interval = config.get('keypoints_threshold', 30)  # Number of screenshots before extraction
        self.key_points_folder = config.get('key_points_folder', 'key_points')
        self.api_base = "https://openrouter.ai/api/v1"
        self.last_extraction_time = None
        
        # Ensure key points directory exists
        os.makedirs(self.key_points_folder, exist_ok=True)
    
    def extract_now(self):
        """Force extraction of key points from current queue"""
        if not self.screenshots_queue:
            print("No screenshots in queue to extract points from.")
            return None
        
        return self.extract_key_points()
    
    def check_queue(self):
        """Check if we should extract key points based on queue size"""
        # Update threshold from config in case it was changed
        self.interval = self.config.get('keypoints_threshold', 30)
        
        if len(self.screenshots_queue) >= self.interval:
            return self.extract_key_points()
        return None
    
    def extract_key_points(self):
        """Extract key points from the queued screenshots"""
        if not self.screenshots_queue:
            return None
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Prepare the text content from all screenshots in the queue
        all_texts = []
        for item in self.screenshots_queue:
            all_texts.append(f"[{item['timestamp']}]\n{item['text_content']}")
        
        combined_text = "\n\n====================\n\n".join(all_texts)
        
        try:
            # Get API key from config
            api_key = self.config.get('openrouter_api_key', '')
            if not api_key:
                raise Exception("OpenRouter API key not configured")
            
            # Get model from config
            model = self.config.get('keypoints_model', 'openai/o3-mini')
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            prompt = f"""
            You are the user's personal secretary. I'm going to provide you with text extracted from several screenshots taken over time.
            Please extract the key points of knowledge from this content. Focus on specific facts, technical details and meaningful information.
            Ignore irrelevant information, navigation elements, ads, etc.

            Format your response as bullet points grouped by topic if possible.
            Include timestamps where appropriate to show when information was captured.
            
            Here are the extracted texts:
            
            {combined_text}
            """
            
            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            
            return self._make_key_points_request(payload, headers, timestamp)
                
        except Exception as e:
            print(f"Error during key points extraction: {e}")
            return None
    
    def _make_key_points_request(self, payload, headers, timestamp):
        """Make the API request with fallback to alternative models"""
        try:
            response = requests.post(f"{self.api_base}/chat/completions", headers=headers, json=payload)
            
            if response.status_code == 200:
                response_data = response.json()
                key_points = response_data["choices"][0]["message"]["content"]
                return self._save_key_points(key_points, timestamp)
            else:
                # Try fallback models
                return self._try_fallback_models(payload, headers, timestamp)
                
        except Exception as e:
            print(f"Error in key points API request: {e}")
            return self._try_fallback_models(payload, headers, timestamp)
    
    def _try_fallback_models(self, payload, headers, timestamp):
        """Try alternative models if the primary model fails"""
        current_model = payload["model"]
        alternative_models = self.config.get('alternative_models', {}).get('keypoints', [])
        
        for model in alternative_models:
            # Skip the model that already failed
            if model == current_model:
                continue
                
            try:
                print(f"Trying fallback model for key points: {model}")
                payload["model"] = model
                
                response = requests.post(f"{self.api_base}/chat/completions", headers=headers, json=payload)
                
                if response.status_code == 200:
                    response_data = response.json()
                    key_points = response_data["choices"][0]["message"]["content"]
                    return self._save_key_points(key_points, timestamp)
            except Exception as e:
                print(f"Error with fallback model {model}: {e}")
        
        # If all models fail, return None
        print("All models failed for key points extraction")
        return None
    
    def _save_key_points(self, key_points, timestamp):
        """Save extracted key points to file"""
        try:
            # Save the key points
            key_points_file = os.path.join(self.key_points_folder, f"key_points_{timestamp}.txt")
            with open(key_points_file, "w", encoding="utf-8") as f:
                first_ts = self.screenshots_queue[0]["timestamp"] if self.screenshots_queue else timestamp
                last_ts = self.screenshots_queue[-1]["timestamp"] if self.screenshots_queue else timestamp
                f.write(f"Key Points Report ({first_ts} to {last_ts})\n")
                f.write("=" * 50 + "\n\n")
                f.write(key_points)
            
            print(f"Key points extracted and saved to {key_points_file}")
            self.last_extraction_time = datetime.datetime.now()
            
            # Clear the queue after processing
            self.screenshots_queue.clear()
            
            return key_points_file
        except Exception as e:
            print(f"Error saving key points: {e}")
            return None
    
    def get_recent_key_points(self, days=1):
        """Get key points from the last N days"""
        key_points = []
        today = datetime.datetime.now()
        
        for i in range(days):
            date = today - datetime.timedelta(days=i)
            date_str = date.strftime("%Y%m%d")
            
            # Find all key points files for the specified date
            for filename in os.listdir(self.key_points_folder):
                if filename.startswith("key_points_") and filename.endswith(".txt") and date_str in filename:
                    file_path = os.path.join(self.key_points_folder, filename)
                    with open(file_path, "r", encoding="utf-8") as f:
                        key_points.append({
                            "date": date.strftime("%Y-%m-%d"),
                            "content": f.read()
                        })
        
        return key_points

```

## File: core\letter.py

```python
# core/letter.py
import os
import time
import datetime
import requests
import threading
import hashlib
import re
import webbrowser

class LetterGenerator:
    """Generates Nova letters based on key points"""
    
    # Class-level flag to track if a letter is currently being generated
    _is_generating = False
    _generation_start_time = None
    _generation_timeout = 600  # 10 minutes timeout
    
    def __init__(self, config):
        self.config = config
        self.letters_folder = config.get('local_folder', 'nova_letters')
        self.api_base = "https://openrouter.ai/api/v1"
        
        # Ensure letters directory exists
        os.makedirs(self.letters_folder, exist_ok=True)
    
    def schedule_daily_letter(self):
        """Schedule a daily letter at configurable time"""
        import schedule
        
        # Get generation time from config (default 9:00 PM)
        generation_time = self.config.get('letter_generation_time', '21:00')
        
        # Schedule the letter generation
        schedule.every().day.at(generation_time).do(self.generate_letter_if_needed)
        print(f"Daily letter scheduled for {generation_time}")
        
        while True:
            schedule.run_pending()
            
            # Check for configuration changes every 10 minutes
            generation_time_new = self.config.get('letter_generation_time', '21:00')
            if generation_time_new != generation_time:
                schedule.clear()
                schedule.every().day.at(generation_time_new).do(self.generate_letter_if_needed)
                generation_time = generation_time_new
                print(f"Letter generation time updated to {generation_time}")
            
            time.sleep(60)  # Check every minute
    
    def is_generation_in_progress(self):
        """Check if letter generation is currently in progress with timeout protection"""
        if not LetterGenerator._is_generating:
            return False
            
        # Check if generation has been going on for too long (timeout)
        if LetterGenerator._generation_start_time:
            elapsed_time = time.time() - LetterGenerator._generation_start_time
            if elapsed_time > LetterGenerator._generation_timeout:
                # Reset the flag if generation has timed out
                print(f"Letter generation timed out after {elapsed_time:.1f} seconds")
                LetterGenerator._is_generating = False
                LetterGenerator._generation_start_time = None
                return False
                
        return True
    
    def generate_letter_if_needed(self):
        """Generate letter only if there isn't already a manually generated one for today"""
        today = datetime.datetime.now().strftime("%Y%m%d")
        letter_path = os.path.join(self.letters_folder, f"nova_letter_{today}.md")
        
        # First check if letter generation is already in progress
        if self.is_generation_in_progress():
            print(f"Letter generation for {today} is already in progress. Skipping duplicate request.")
            return None
        
        # Check if letter already exists locally
        if os.path.exists(letter_path):
            print(f"Letter for {today} already exists locally. Skipping auto-generation.")
            return None
        
        # Check if letter exists in shared folder
        shared_folder = self.config.get('shared_folder')
        username = self.config.get('username', 'User')
        
        if shared_folder and os.path.exists(shared_folder):
            shared_letter_path = os.path.join(shared_folder, username, f"nova_letter_{today}.md")
            if os.path.exists(shared_letter_path):
                print(f"Letter for {today} already exists in shared folder. Skipping auto-generation.")
                return None
        
        # Generate letter if it doesn't exist
        return self.generate_letter()
    
    def check_todays_letter_exists(self):
        """Check if today's letter has been generated or is currently being generated"""
        # If a letter generation is in progress, consider it as existing
        if self.is_generation_in_progress():
            return True
            
        today = datetime.datetime.now().strftime("%Y%m%d")
        letter_path = os.path.join(self.letters_folder, f"nova_letter_{today}.md")
        
        # Also check shared folder
        shared_folder = self.config.get('shared_folder')
        username = self.config.get('username', 'User')
        
        if shared_folder and os.path.exists(shared_folder):
            shared_letter_path = os.path.join(shared_folder, username, f"nova_letter_{today}.md")
            if os.path.exists(shared_letter_path):
                return True
                
        return os.path.exists(letter_path)
    
    def is_after_generation_time(self):
        """Check if current time is after the configured letter generation time"""
        now = datetime.datetime.now()
        
        # Get generation time from config (default 9:00 PM)
        generation_time_str = self.config.get('letter_generation_time', '21:00')
        
        try:
            # Parse the time string (expecting format HH:MM)
            hour, minute = map(int, generation_time_str.split(':'))
            generation_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            return now >= generation_time
        except (ValueError, TypeError):
            # Fall back to 9:00 PM if there's an error parsing the time
            fallback_time = now.replace(hour=21, minute=0, second=0, microsecond=0)
            return now >= fallback_time
    
    def generate_letter(self, date_str=None):
        """Generate a letter for the specified date or today"""
        if not date_str:
            # Default to today
            date_str = datetime.datetime.now().strftime("%Y%m%d")
        
        # Set generation in progress flag
        if LetterGenerator._is_generating:
            print(f"Letter generation already in progress. Started at {LetterGenerator._generation_start_time}")
            return None
            
        LetterGenerator._is_generating = True
        LetterGenerator._generation_start_time = time.time()
        
        print(f"Generating Nova's letter for date: {date_str}")
        
        try:
            # Get key points and previous letters
            key_points = self._get_recent_key_points(1)
            previous_letters = self._get_recent_letters(3)
            
            if not key_points:
                print("No recent activity found. Cannot generate a meaningful letter.")
                LetterGenerator._is_generating = False
                LetterGenerator._generation_start_time = None
                return None
            
            # Prepare previous letter content to avoid repetition
            previous_letters_summary = ""
            if previous_letters:
                previous_letters_summary = "Previous letters summary:\n\n"
                for letter in previous_letters:
                    previous_letters_summary += f"Letter from {letter['date']}:\n"
                    # Extract exercise sections to avoid repetition
                    if "## Practical Exercises" in letter["content"]:
                        exercise_section = letter["content"].split("## Practical Exercises")[1].split("##", 1)[0]
                        previous_letters_summary += exercise_section + "\n\n"
            
            # Format date for the letter
            today_formatted = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%B %d, %Y")
            
            # Get custom style and language
            letter_style = self.config.get('letter_style', '')
            letter_language = self.config.get('letter_language', 'English')
            
            try:
                # Get API key from config
                api_key = self.config.get('openrouter_api_key', '')
                if not api_key:
                    raise Exception("OpenRouter API key not configured")
                
                # Get selected model from config
                model = self.config.get('letter_model', 'anthropic/claude-3-7-sonnet')
                
                # Customize the system prompt based on language and style
                system_prompt = "You are Nova, a learning assistant who monitors a user's learning activities. "
                
                # Add language instruction if specified
                if letter_language and letter_language.lower() != "english":
                    system_prompt += f"You write educational recaps in {letter_language}. "
                else:
                    system_prompt += "You write educational recaps in English. "
                
                # Add style instruction if specified
                if letter_style:
                    system_prompt += f"Your writing style should be {letter_style}. "
                else:
                    system_prompt += "Focus on knowledge and insights rather than emotional encouragement. "
                
                # Create letter template once to avoid duplication
                letter_template = f"""
                As the user's personal secretary, create an educational letter for the user.

                Today is {today_formatted}.

                Your letter should:
                1. Begin with a brief, emotional inspiring greeting
                2. Based what the user's learning and doing today, review important knowledge concepts, specific facts
                3. Provide an analysis and deeper insights on them
                4. Include 2-3 thoughtful, interesting exercises related to the content (but not too heavy)
                5. For each exercise, provide a detailed solution immediately after the exercise
                6. Close with a brief, emotional inspiring sign-off
                
                Important: Focus on substantive content rather than motivational fluff. Prioritize knowledge, insights, and useful exercises over compliments.                       
                Recent learning activity:
                {' '.join([kp["content"] for kp in key_points])}

                {previous_letters_summary}

                THE MOST IMPORTANT: Please return the letter in MARKDOWN format!

                First line: Add tags as "tags: tag1, tag2, tag3" (extract 3-5 relevant tags from the content)
                Second line: Add a title as "# Title of Letter"
                Then proceed with the letter content in markdown. But don't wrap the content in a markdown code block.

                Make sure exercises do not repeat content from previous letters.
                
                Use standard markdown features:
                - Headings with #, ##, ###
                - Lists with *, -, or numbers
                - Code blocks with ```
                - Math expressions with $ and $$ for inline and display math
                """
                
                # Try generating with the main model
                markdown_content = self._call_api_for_letter(model, api_key, system_prompt, letter_template)
                
                if markdown_content:
                    return self._save_letter(markdown_content, date_str)
                
                # If main model failed, try alternate models
                alternate_models = self.config.get('alternative_models', {}).get('letter', [])
                
                for alt_model in alternate_models:
                    # Skip the model that already failed
                    if alt_model == model:
                        continue
                    
                    print(f"Trying alternate model for letter generation: {alt_model}")
                    markdown_content = self._call_api_for_letter(alt_model, api_key, system_prompt, letter_template)
                    
                    if markdown_content:
                        return self._save_letter(markdown_content, date_str)
                
                # If all models failed
                print("All models failed for letter generation")
                LetterGenerator._is_generating = False
                LetterGenerator._generation_start_time = None
                return None
                
            except Exception as e:
                print(f"Error generating Nova's letter: {e}")
                LetterGenerator._is_generating = False
                LetterGenerator._generation_start_time = None
                return None
                
        except Exception as e:
            print(f"Unexpected error during letter generation: {e}")
            LetterGenerator._is_generating = False
            LetterGenerator._generation_start_time = None
            return None
    
    def _call_api_for_letter(self, model, api_key, system_prompt, letter_template):
        """Call the API with the given model and return the generated content if successful"""
        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": letter_template}
                    ]
                }
            ).json()
            
            if "choices" in response and len(response["choices"]) > 0:
                return response["choices"][0]["message"]["content"]
            else:
                print(f"Error with API using model {model}: {response}")
                return None
                
        except Exception as e:
            print(f"Error with model {model}: {e}")
            return None
    
    def _save_letter(self, markdown_content: str, date_str):
        """Save the markdown content as a letter"""
        letter_file = os.path.join(self.letters_folder, f"nova_letter_{date_str}.md")
        
        try:
            with open(letter_file, "w", encoding="utf-8") as f:
                f.write(markdown_content.strip())
            
            print(f"Nova's letter generated and saved to {letter_file}")
            
            # Auto-sync the letter if configured
            if self.config.get('auto_sync', True):
                from core.sync import SyncManager
                sync_manager = SyncManager(self.config)
                sync_manager.sync_letter(date_str)
            
            # Automatically open the letter in the web browser
            auto_open = self.config.get('auto_open_letter', True)
            if auto_open:
                web_url = f'http://localhost:5678/#letter/{date_str}'
                try:
                    print(f"Opening letter in web browser: {web_url}")
                    webbrowser.open(web_url)
                except Exception as e:
                    print(f"Error opening letter in browser: {e}")
            else:
                # Just display the URL without opening
                print(f"Letter can be viewed through the web UI at http://localhost:5678/#letter/{date_str}")
            
            # Reset the generation flag now that we've finished
            LetterGenerator._is_generating = False
            LetterGenerator._generation_start_time = None
            
            return letter_file
        except Exception as e:
            print(f"Error saving letter: {e}")
            LetterGenerator._is_generating = False
            LetterGenerator._generation_start_time = None
            return None
    
    def _get_recent_key_points(self, days=1):
        """Get key points from the last N days"""
        key_points = []
        today = datetime.datetime.now()
        key_points_folder = self.config.get('key_points_folder', 'key_points')
        
        for i in range(days):
            date = today - datetime.timedelta(days=i)
            date_str = date.strftime("%Y%m%d")
            
            # Find all key points files for the specified date
            for filename in os.listdir(key_points_folder):
                if filename.startswith("key_points_") and filename.endswith(".txt") and date_str in filename:
                    file_path = os.path.join(key_points_folder, filename)
                    with open(file_path, "r", encoding="utf-8") as f:
                        key_points.append({
                            "date": date.strftime("%Y-%m-%d"),
                            "content": f.read()
                        })
        
        return key_points
    
    def _get_recent_letters(self, days=3):
        """Get Nova's letters from the last N days to avoid repetition"""
        letters = []
        today = datetime.datetime.now()
        
        for i in range(days):
            date = today - datetime.timedelta(days=i)
            date_str = date.strftime("%Y%m%d")
            letter_path = os.path.join(self.letters_folder, f"nova_letter_{date_str}.md")
            
            if os.path.exists(letter_path):
                with open(letter_path, "r", encoding="utf-8") as f:
                    letters.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "content": f.read()
                    })
        
        return letters


```

## File: core\screenshot.py

```python
# core/screenshot.py
import os
import time
import base64
import datetime
import threading
import pyautogui
import requests
from PIL import Image

class ScreenshotManager:
    """Manages taking screenshots and extracting text"""
    
    def __init__(self, config):
        self.config = config
        self.interval = config.get('screenshot_interval', 120)  # Default: 2 minutes in seconds
        self.retention_days = config.get('screenshot_retention_days', 7)  # Default: 7 days
        self.queue = []
        self.stop_event = threading.Event()
        self.screenshots_folder = config.get('screenshots_folder', 'screenshots')
        self.api_base = "https://openrouter.ai/api/v1"
        
        # Ensure screenshots directory exists
        # os.makedirs(self.screenshots_folder, exist_ok=True)
    
    def start(self):
        """Start the screenshot worker thread and cleanup thread"""
        # Start screenshot worker thread
        self.thread = threading.Thread(target=self._screenshot_worker)
        self.thread.daemon = True
        self.thread.start()
        
        # Start cleanup thread for old screenshots
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker)
        self.cleanup_thread.daemon = True
        self.cleanup_thread.start()
        
        print(f"Screenshot manager started (interval: {self.interval}s, retention: {self.retention_days} days)")
        
    def stop(self):
        """Stop the screenshot worker thread"""
        self.stop_event.set()
        if hasattr(self, 'thread') and self.thread.is_alive():
            self.thread.join(timeout=1)
        if hasattr(self, 'cleanup_thread') and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=1)
    
    def _screenshot_worker(self):
        """Worker thread to take screenshots at regular intervals"""
        next_time = time.time() + self.interval
        
        while not self.stop_event.is_set():
            current_time = time.time()
            if current_time >= next_time:
                self.take_screenshot()
                # Use the potentially updated interval from config
                self.interval = self.config.get('screenshot_interval', 120)
                next_time = current_time + self.interval
            
            # Sleep a bit to avoid using too much CPU
            time.sleep(1)
    
    def _cleanup_worker(self):
        """Worker thread to clean up old screenshots"""
        # Run once a day
        while not self.stop_event.is_set():
            try:
                self.cleanup_old_screenshots()
            except Exception as e:
                print(f"Error during screenshot cleanup: {e}")
            
            # Sleep for 24 hours (with periodic checks for stop event)
            for _ in range(24 * 60):  # Check every minute for 24 hours
                if self.stop_event.is_set():
                    break
                time.sleep(60)
    
    def cleanup_old_screenshots(self):
        """Delete screenshots older than retention_days"""
        self.retention_days = self.config.get('screenshot_retention_days', 7)
        if self.retention_days <= 0:  # Keep indefinitely if set to 0 or negative
            return
            
        try:
            now = datetime.datetime.now()
            cutoff_date = now - datetime.timedelta(days=self.retention_days)
            
            count_removed = 0
            for filename in os.listdir(self.screenshots_folder):
                if filename.startswith("screenshot_") and filename.endswith(".png"):
                    # Extract date from filename (format: screenshot_YYYYMMDD_HHMMSS.png)
                    date_str = filename[len("screenshot_"):len("screenshot_") + 15]  # YYYYMMDD_HHMMSS
                    try:
                        file_date = datetime.datetime.strptime(date_str, "%Y%m%d_%H%M%S")
                        
                        if file_date < cutoff_date:
                            # Delete the file
                            file_path = os.path.join(self.screenshots_folder, filename)
                            os.remove(file_path)
                            count_removed += 1
                    except ValueError:
                        # Skip files with invalid date format
                        continue
            
            if count_removed > 0:
                print(f"Cleaned up {count_removed} screenshots older than {self.retention_days} days")
        except Exception as e:
            print(f"Error cleaning up old screenshots: {e}")
    
    def take_screenshot(self):
        """Take a screenshot and extract text"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.screenshots_folder, f"screenshot_{timestamp}.png")
        
        try:
            # Take the screenshot
            screenshot = pyautogui.screenshot()
            screenshot.save(filename)
            
            # Process the screenshot to extract text
            text_content = self.extract_text_from_image(filename)
            
            if text_content:
                screenshot_data = {
                    "timestamp": timestamp,
                    "text_content": text_content,
                    "image_path": filename
                }
                
                self.queue.append(screenshot_data)
                return screenshot_data
            
            return None
        except Exception as e:
            print(f"Error taking screenshot: {e}")
            return None
    
    def image_to_base64(self, image_path):
        """Convert image to base64 string"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def extract_text_from_image(self, image_path):
        """Extract text from image using selected LLM model"""
        try:
            base64_image = self.image_to_base64(image_path)
            
            # Get API key from config
            api_key = self.config.get('openrouter_api_key', '')
            if not api_key:
                raise Exception("OpenRouter API key not configured")
            
            # Get selected model from config
            model = self.config.get('screenshot_model', 'google/gemma-3-27b-it')
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extract all visible text content from this screenshot. Focus on capturing meaningful information, especially knowledge related content. Ignore UI elements, ads, and irrelevant text."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ]
            }
            
            response = requests.post(f"{self.api_base}/chat/completions", headers=headers, json=payload)
            response_data = response.json()
            
            if response.status_code == 200:
                return response_data["choices"][0]["message"]["content"]
            else:
                print(f"Error extracting text (status {response.status_code}): {response_data}")
                
                # Try with fallback models if primary model fails
                return self._try_fallback_models(base64_image, model, api_key, headers)
                
        except Exception as e:
            print(f"Error extracting text: {e}")
            return ""
    
    def _try_fallback_models(self, base64_image, failed_model, api_key, headers):
        """Try fallback models if the primary model fails"""
        alternative_models = self.config.get('alternative_models', {}).get('screenshot', [])
        
        for model in alternative_models:
            # Skip the model that already failed
            if model == failed_model:
                continue
                
            try:
                print(f"Trying fallback model for screenshot: {model}")
                
                payload = {
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Extract all visible text content from this screenshot. Focus on capturing meaningful information, especially knowledge/working related content. Ignore UI elements, ads, and irrelevant text."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    }
                                }
                            ]
                        }
                    ]
                }
                
                response = requests.post(f"{self.api_base}/chat/completions", headers=headers, json=payload)
                response_data = response.json()
                
                if response.status_code == 200:
                    return response_data["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"Error with fallback model {model}: {e}")
        
        # If all models fail, return empty string
        return ""
    
    def get_queue(self):
        """Get the current screenshot queue"""
        return self.queue
    
    def clear_queue(self):
        """Clear the screenshot queue"""
        self.queue = []

```

## File: core\sync.py

```python
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
```

## File: data\config.py

```python
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

```

## File: nova_app.py

```python
#!/usr/bin/env python3
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')  # Set standard output encoding to UTF-8
sys.path.append(os.path.abspath(os.path.dirname(__file__)))  # for embedded python distribution

import argparse
import threading
import time
from core.screenshot import ScreenshotManager
from data.config import ConfigManager
from ui.desktop import DesktopUI
from ui.web import WebUI
from util.helpers import parse_date, ensure_directory, find_available_port, save_port_to_file, read_port_from_file, is_port_available
from core.letter import LetterGenerator
from core.key_points import KeyPointsExtractor
from core.sync import SyncManager

def check_api_key():
    """Check if API key is configured or try to load from myapikeys.py"""
    config_manager = ConfigManager()
    api_key = config_manager.get('openrouter_api_key')
    
    if not api_key:
        # Try to get from myapikeys.py if it exists
        try:
            if os.path.exists('myapikeys.py'):
                from myapikeys import openrouter
                if openrouter and openrouter.startswith('sk-or-'):
                    # Save to config
                    config_manager.update_config('openrouter_api_key', openrouter)
                    print("✓ API key loaded from myapikeys.py")
                    return True
        except ImportError:
            pass
        
        print("⚠ WARNING: OpenRouter API key not configured. Some features may not work.")
        return False
    
    return True

def validate_configuration():
    """Validate critical configuration settings"""
    config_manager = ConfigManager()
    
    # Check API key
    api_key_valid = config_manager.validate_api_key()
    
    # Check folders
    folder_validation = config_manager.validate_folders()
    
    all_valid = api_key_valid and all(result for name, result in folder_validation.items() if name != 'shared_folder')
    
    if not all_valid:
        print("\n⚠ WARNING: Configuration issues detected:")
        if not api_key_valid:
            print("  - OpenRouter API key missing or invalid")
        
        for name, valid in folder_validation.items():
            if valid is False:  # Not None (which means optional)
                print(f"  - {name} configuration is invalid")
    
    return all_valid

def start_letter_scheduler(letter_generator):
    """Start the thread that schedules daily letters"""
    thread = threading.Thread(target=letter_generator.schedule_daily_letter)
    thread.daemon = True
    thread.start()
    return thread

def start_sync_loop(sync_manager):
    """Start the background sync loop"""
    return sync_manager.start_sync_loop()

def check_morning_web_ui_launch(config, web_ui_port):
    """Check if we should auto-launch the web UI this morning"""
    import datetime
    import webbrowser
    
    # Check if feature is enabled
    if not config.get('morning_webui_launch', True):
        return False
        
    # Check if it's morning (before configured cutoff hour)
    current_hour = datetime.datetime.now().hour
    cutoff_hour = config.get('morning_cutoff_hour', 11)
    
    if current_hour >= cutoff_hour:
        print(f"Current hour {current_hour} is after morning cutoff ({cutoff_hour}), skipping auto-launch")
        return False
    
    # It's morning and the feature is enabled - open the web UI
    try:
        web_url = f'http://localhost:{web_ui_port}'
        print(f"Auto-launching web UI for morning review: {web_url}")
        webbrowser.open(web_url)
        return True
    except Exception as e:
        print(f"Error auto-launching web UI: {e}")
        return False

def main():
    """Main entry point for the Nova Project application"""
    parser = argparse.ArgumentParser(description="Nova Project: Your Personal Learning Companion")
    parser.add_argument('--letter', type=str, help='Generate Nova letter for a specific date (YYYY-MM-DD, or "today"/"yesterday")')
    parser.add_argument('--extract-now', action='store_true', help='Force extraction of key points from current queue')
    parser.add_argument('--show', action='store_true', help='Show the UI at startup (default: hidden in system tray)')
    parser.add_argument('--port', type=int, default=None, help='Web server port (default: auto-select in range 11000-12000)')
    parser.add_argument('--web-only', action='store_true', help='Run only the web server without the desktop UI')
    parser.add_argument('--check-config', action='store_true', help='Check configuration and exit')
    parser.add_argument('--no-morning-launch', action='store_true', help='Disable auto-launching web UI in the morning')
    
    args = parser.parse_args()
    
    # Port selection logic
    if args.port is None:
        # Try to read previously used port
        port = read_port_from_file()
        
        if port is None or not is_port_available(port):
            # Find and save a new port
            try:
                port = find_available_port(start_range=11000, end_range=12000)
                save_port_to_file(port)
                print(f"✓ Found available port: {port}")
            except RuntimeError as e:
                print(f"Warning: {e}")
                # Fall back to a default port if no available port found
                port = 5678
                print(f"Falling back to default port: {port}")
    else:
        port = args.port
    
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    # Override morning launch if specified in command line
    if args.no_morning_launch:
        config['morning_webui_launch'] = False
    
    # Check API key
    check_api_key()
    
    # Validate configuration if requested
    if args.check_config:
        valid = validate_configuration()
        sys.exit(0 if valid else 1)
    
    # Ensure common parent folder exists
    local_folder = config.get('local_folder', 'NovaData')
    ensure_directory(local_folder)
    
    # Set up paths for subfolders based on the common parent
    if not config.get('screenshots_folder'):
        config['screenshots_folder'] = os.path.join(local_folder, 'screenshots')
    if not config.get('key_points_folder'):
        config['key_points_folder'] = os.path.join(local_folder, 'key_points')
    if not config.get('letters_folder'):
        config['letters_folder'] = os.path.join(local_folder, 'nova_letters')
    
    # Create necessary directories
    ensure_directory(config.get('screenshots_folder'))
    ensure_directory(config.get('key_points_folder')) 
    ensure_directory(config.get('letters_folder', os.path.join(local_folder, 'nova_letters')))
    
    # Print welcome message
    print(f"""
╔═══════════════════════════════════════════════╗
║                 NOVA PROJECT                  ║
║       Your Personal Learning Companion        ║
╚═══════════════════════════════════════════════╝

✓ Starting Nova Project...
✓ Web UI available at: http://localhost:{port}
✓ Desktop UI {'disabled' if args.web_only else 'running in system tray'}
""")
    
    # Handle web-only mode
    if args.web_only:
        web_ui = WebUI(config, port=port)
        
        # Check if we should auto-launch the web UI for morning review
        check_morning_web_ui_launch(config, port)
        
        web_ui.start_in_main_thread()
        return
    
    # Initialize components
    screenshot_manager = ScreenshotManager(config)
    key_points_extractor = KeyPointsExtractor(config, screenshot_manager.get_queue())
    letter_generator = LetterGenerator(config)
    sync_manager = SyncManager(config)
    
    # Handle specific command line options
    if args.letter:
        date_str = parse_date(args.letter)
        if date_str:
            print(f"Generating letter for {date_str}...")
            letter_generator.generate_letter(date_str)
        return
    
    if args.extract_now:
        if screenshot_manager.get_queue():
            print(f"Extracting key points from {len(screenshot_manager.get_queue())} queued screenshots...")
            key_points_extractor.extract_now()
        else:
            print("No screenshots in queue to extract points from.")
            
            # Take a screenshot now and extract text
            print("Taking a screenshot now...")
            screenshot_data = screenshot_manager.take_screenshot()
            if screenshot_data:
                print("Screenshot taken and text extracted successfully.")
                print("Try running with --extract-now again.")
        return
    
    # Regular mode with desktop and web UI
    web_ui = WebUI(config, port=port)
    desktop_ui = DesktopUI(config, web_ui, screenshot_manager, key_points_extractor, letter_generator, sync_manager)
    
    # Start components
    try:
        # Start screenshot manager
        screenshot_manager.start()
        print("✓ Screenshot manager started")
        
        # Start letter scheduler
        letter_thread = start_letter_scheduler(letter_generator)
        print(f"✓ Letter scheduler started (daily at {config.get('letter_generation_time', '21:00')})")
        
        # Start sync manager and perform initial sync
        sync_started = start_sync_loop(sync_manager)
        if sync_started:
            print(f"✓ Sync manager started (every {config.get('sync_frequency_minutes', 15)} minutes)")
            
            # Perform immediate sync at startup
            print("Performing initial sync...")
            sync_result = sync_manager.bidirectional_sync()
            if sync_result:
                print("✓ Initial sync completed")
            else:
                print("✓ Initial sync completed (no changes detected)")
        else:
            print("⚠ Sync manager not started (no shared folder configured)")
        
        # Start web UI
        web_ui.start()
        print("✓ Web UI started")
        
        # Check if we should auto-launch the web UI for morning review
        web_ui_launched = check_morning_web_ui_launch(config, port)
        
        # Set UI visibility (only show if explicitly requested or not auto-launched in morning)
        if args.show:
            desktop_ui.show()
            print("✓ Desktop UI is now visible")
        else:
            desktop_ui.hide()
            print("✓ Desktop UI is running in the system tray")
        
        # Don't open web UI automatically to minimize disturbance
        print(f"✓ Web UI available at: http://localhost:{port}")
        print(f"✓ Access Nova via the system tray icon")
        
        # Set up signal handlers for proper cleanup
        try:
            import signal
            def signal_handler(sig, frame):
                print(f"\nSignal {sig} received, shutting down...")
                screenshot_manager.stop()
                sync_manager.stop_sync_loop()
                desktop_ui.stop()
                web_ui.stop()
                sys.exit(0)
                
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except (ImportError, AttributeError):
            # Gracefully handle platforms without signal support
            pass
        
        # Start the application
        print("\nNova is now running. Press Ctrl+C to quit.")
        sys.exit(desktop_ui.start())
        
    except Exception as e:
        print(f"Error starting Nova: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

```

## File: ui\desktop.py

```python
# ui/desktop.py
import os
import time
import sys
import threading
import webbrowser
from PyQt5.QtCore import Qt, QTimer, QPoint, pyqtSignal
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QLabel, QSystemTrayIcon, QMenu, QAction,
                           QPushButton, QMessageBox, QFileDialog)

class ActionType:
    """Types of actions that can be performed"""
    SCREENSHOT = "Screenshot"
    KEY_POINTS = "KeyPoints" 
    LETTER = "Letter"
    SYNC = "Sync"

class ActionStatus:
    """Status of actions"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class NovaAction:
    """Represents an action performed by Nova"""
    def __init__(self, action_type, details=None):
        import uuid
        self.id = str(uuid.uuid4())[:8]
        self.action_type = action_type
        self.status = ActionStatus.PENDING
        self.creation_time = time.time()
        self.details = details
        self.error = None
        self.result = None

class NovaWindow(QMainWindow):
    """Main desktop UI window"""
    
    # Signals
    statusFlashed = pyqtSignal(str, str, int)
    generateLetterSignal = pyqtSignal()
    openLetterSignal = pyqtSignal(str)
    openWebUISignal = pyqtSignal()
    syncNowSignal = pyqtSignal()
    browseFolderSignal = pyqtSignal(str)
    
    def __init__(self, config):
        super(NovaWindow, self).__init__()
        self.config = config
        
        # Initialize UI components
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("Nova")
        
        # Create letter buttons list
        self.letter_buttons = []
        self.letter_buttons_layout = None
        
        # Set up the system tray icon
        self.tray_icon = QSystemTrayIcon(self)
        
        # Use app_icon from config if available
        app_icon = self.config.get('app_icon', 'lightbulb')
        icon_path = "nova_icon.png"
        
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            # Use a system icon if Nova icon not available
            self.tray_icon.setIcon(QApplication.style().standardIcon(QApplication.style().SP_ComputerIcon))
        
        # Create tray menu
        self._create_tray_menu()
        
        # Set up main window layout
        self._create_ui_layout()
        
        # Connect signals
        self.statusFlashed.connect(self.flash_status_slot)
        
        # Initialize status properties
        self._original_status_style = self.status_label.styleSheet()
        self._original_status_text = self.status_label.text()
        
        # Track window dragging
        self.pressing = False
        self.start_point = None
    
    def _create_tray_menu(self):
        """Create the system tray menu"""
        tray_menu = QMenu()
        
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        generate_action = QAction("Generate Letter Now", self)
        generate_action.triggered.connect(lambda: self.generateLetterSignal.emit())
        tray_menu.addAction(generate_action)
        
        web_ui_action = QAction("Open Web UI", self)
        web_ui_action.triggered.connect(lambda: self.openWebUISignal.emit())
        tray_menu.addAction(web_ui_action)
        
        sync_action = QAction("Sync Letters Now", self)
        sync_action.triggered.connect(lambda: self.syncNowSignal.emit())
        tray_menu.addAction(sync_action)
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(QApplication.quit)
        tray_menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()
    
    def _create_ui_layout(self):
        """Create the main window layout"""
        # Main layout
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Content area with styling
        self.content_area = QWidget()
        self.content_area.setObjectName("contentArea")
        self.content_area.setStyleSheet("""
            QWidget#contentArea {
                background-color: rgba(45, 45, 48, 200);
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
            }
        """)
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.setSpacing(8)
        
        # Header with controls
        self._create_header()
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("""
            background-color: #2AAA8A;
            color: white;
            padding: 8px;
            border-radius: 5px;
            font-weight: bold;
        """)
        self.status_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.content_layout.addWidget(self.status_label)
        
        # Web UI Button
        web_ui_button = QPushButton("Open Web UI")
        web_ui_button.setStyleSheet("""
            QPushButton {
                background-color: #6A0DAD;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #8A2BE2;
            }
            QPushButton:pressed {
                background-color: #4B0082;
            }
        """)
        web_ui_button.clicked.connect(lambda: self.openWebUISignal.emit())
        self.content_layout.addWidget(web_ui_button)
        
        # Previous Letters section
        self._create_letters_section()
        
        # Action buttons
        self._create_action_buttons()
        
        # Latest activity display
        self._create_activity_display()
        
        # Add content to main layout and set window size
        self.main_layout.addWidget(self.content_area)
        self.setFixedSize(350, 450)
        self.position_window_bottom_right()
    
    def _create_header(self):
        """Create the window header with title and control buttons"""
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        self.title_label = QLabel("Nova Project")
        self.title_label.setStyleSheet("""
            color: #FFFFFF;
            font-weight: bold;
        """)
        self.title_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        
        # Control buttons
        hide_button = QPushButton("Hide")
        hide_button.setStyleSheet("""
            QPushButton {
                background-color: #444444;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
            QPushButton:pressed {
                background-color: #333333;
            }
        """)
        hide_button.clicked.connect(self.hide)
        
        quit_button = QPushButton("Quit")
        quit_button.setStyleSheet("""
            QPushButton {
                background-color: #8B0000;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #A00000;
            }
            QPushButton:pressed {
                background-color: #700000;
            }
        """)
        quit_button.clicked.connect(QApplication.quit)
        
        # Assemble header
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(hide_button)
        header_layout.addWidget(quit_button)
        
        self.content_layout.addWidget(header_widget)
    
    def _create_letters_section(self):
        """Create the previous letters section"""
        letters_section = QWidget()
        letters_layout = QVBoxLayout(letters_section)
        letters_layout.setContentsMargins(0, 0, 0, 0)
        letters_layout.setSpacing(5)
        
        # Section header
        letters_header = QLabel("Previous Letters")
        letters_header.setStyleSheet("color: white; font-weight: bold;")
        letters_layout.addWidget(letters_header)
        
        # Letter buttons container
        self.letter_buttons_layout = QVBoxLayout()
        self.letter_buttons_layout.setSpacing(5)
        letters_layout.addLayout(self.letter_buttons_layout)
        
        self.content_layout.addWidget(letters_section)
    
    def _create_action_buttons(self):
        """Create action buttons (generate letter, sync)"""
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(8)
        
        # Generate Letter Button
        generate_button = QPushButton("Generate Today's Letter")
        generate_button.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1084DE;
            }
            QPushButton:pressed {
                background-color: #0068C0;
            }
        """)
        generate_button.clicked.connect(lambda: self.generateLetterSignal.emit())
        
        # Sync Button
        sync_button = QPushButton("Sync Letters")
        sync_button.setStyleSheet("""
            QPushButton {
                background-color: #FF4500;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FF6347;
            }
            QPushButton:pressed {
                background-color: #DC143C;
            }
        """)
        sync_button.clicked.connect(lambda: self.syncNowSignal.emit())
        
        buttons_layout.addWidget(generate_button)
        buttons_layout.addWidget(sync_button)
        self.content_layout.addWidget(buttons_widget)
    
    def _create_activity_display(self):
        """Create the latest activity display"""
        activity_header = QLabel("Latest Activity")
        activity_header.setStyleSheet("color: white; font-weight: bold;")
        self.content_layout.addWidget(activity_header)
        
        self.latest_activity_label = QLabel("No recent activity")
        self.latest_activity_label.setStyleSheet("""
            background-color: rgba(37, 37, 38, 120);
            border: none;
            border-radius: 5px;
            color: #FFFFFF;
            padding: 10px;
        """)
        self.latest_activity_label.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.latest_activity_label.setWordWrap(True)
        self.latest_activity_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.latest_activity_label.setFixedHeight(50)
        self.content_layout.addWidget(self.latest_activity_label)
    
    def mousePressEvent(self, event):
        """Handle mouse press for window dragging"""
        if event.button() == Qt.LeftButton:
            self.pressing = True
            self.start_point = event.globalPos()
            
    def mouseReleaseEvent(self, event):
        """Handle mouse release for window dragging"""
        self.pressing = False
        
    def mouseMoveEvent(self, event):
        """Handle mouse move for window dragging"""
        if self.pressing and self.start_point:
            movement = event.globalPos() - self.start_point
            self.window().move(self.window().pos() + movement)
            self.start_point = event.globalPos()
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Minimize to tray instead of closing
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Nova Project",
            "Nova is still running in the background.",
            QSystemTrayIcon.Information,
            2000
        )
    
    def tray_icon_activated(self, reason):
        """Handle system tray icon activation"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
        
    def position_window_bottom_right(self):
        """Position the window in the bottom right corner of the screen"""
        screen_geo = QApplication.primaryScreen().geometry()
        window_width = 350
        window_height = 450
        x_position = screen_geo.width() - window_width - 20
        y_position = screen_geo.height() - window_height - 60
        self.setGeometry(x_position, y_position, window_width, window_height)
    
    def update_latest_activity(self, actions):
        """Update the latest activity display"""
        if not actions:
            self.latest_activity_label.setText("No recent activity")
            return
            
        # Get the most recent action
        recent_action = actions[0] if actions else None
        
        if recent_action:
            if recent_action.status == ActionStatus.PENDING:
                status_symbol = "🔄"
                color = "#DDB100"
            elif recent_action.status == ActionStatus.PROCESSING:
                status_symbol = "⚙️"
                color = "#3794FF" 
            elif recent_action.status == ActionStatus.COMPLETED:
                status_symbol = "✓"
                color = "#73C991"
            else:
                status_symbol = "✗"
                color = "#F14C4C"
            
            if recent_action.action_type == ActionType.SCREENSHOT:
                type_icon = "📷"
            elif recent_action.action_type == ActionType.KEY_POINTS:
                type_icon = "📝" 
            elif recent_action.action_type == ActionType.LETTER:
                type_icon = "📨"
            elif recent_action.action_type == ActionType.SYNC:
                type_icon = "🔄"
                
            action_text = f"{status_symbol} {type_icon} {recent_action.action_type}"
            if recent_action.details:
                action_text += f": {recent_action.details}"
            if recent_action.status == ActionStatus.FAILED and recent_action.error:
                error_msg = recent_action.error
                if len(error_msg) > 40:
                    error_msg = error_msg[:37] + "..."
                action_text += f" - {error_msg}"
                
            self.latest_activity_label.setText(action_text)
            
            # Set background color based on status
            if recent_action.status == ActionStatus.FAILED:
                bg_color = "rgba(150, 20, 20, 120)"
            elif recent_action.status == ActionStatus.COMPLETED:
                bg_color = "rgba(20, 120, 20, 120)"
            elif recent_action.status == ActionStatus.PROCESSING:
                bg_color = "rgba(20, 20, 150, 120)"
            else:
                bg_color = "rgba(150, 150, 20, 120)"
                
            self.latest_activity_label.setStyleSheet(f"""
                background-color: {bg_color};
                border: none;
                border-radius: 5px;
                color: #FFFFFF;
                padding: 10px;
            """)
    
    def update_status(self, status_text):
        """Update the status label"""
        self.status_label.setText(status_text)
    
    def update_letter_buttons(self):
        """Update letter buttons based on available letters"""
        # Clear existing buttons
        for button in self.letter_buttons:
            button.setParent(None)
            button.deleteLater()
        self.letter_buttons.clear()
        
        # Get letter files
        letters_folder = self.config.get('local_folder', 'nova_letters')
        letter_files = []
        
        try:
            if os.path.exists(letters_folder):
                for filename in os.listdir(letters_folder):
                    if filename.startswith("nova_letter_"):
                        # Check if it's a letter file
                        if filename.endswith(".html") or filename.endswith(".md"):
                            # Extract date part
                            if filename.endswith(".html"):
                                date_str = filename[len("nova_letter_"):-5]
                            else:  # .md file
                                date_str = filename[len("nova_letter_"):-3]
                            
                            try:
                                import datetime
                                date = datetime.datetime.strptime(date_str, "%Y%m%d")
                                letter_date = date.strftime("%b %d, %Y")  # Format as "Jan 01, 2023"
                                letter_files.append((filename, letter_date, date_str))
                            except ValueError:
                                pass  # Skip if date can't be parsed
                
                # Sort by date (newest first) and limit to 3 most recent
                letter_files.sort(key=lambda x: x[2], reverse=True)
                letter_files = letter_files[:3]
                
                # Create new buttons
                for filename, letter_date, date_str in letter_files:
                    format_icon = "📄" if filename.endswith(".html") else "📝"
                    button = QPushButton(f"{format_icon} Letter: {letter_date}")
                    button.setStyleSheet("""
                        QPushButton {
                            background-color: #2C3E50;
                            color: white;
                            border: none;
                            padding: 6px;
                            border-radius: 4px;
                            text-align: left;
                        }
                        QPushButton:hover {
                            background-color: #34495E;
                        }
                        QPushButton:pressed {
                            background-color: #1A252F;
                        }
                    """)
                    # Use a lambda with a default argument to avoid closure issues
                    button.clicked.connect(lambda checked=False, d=date_str: self.openLetterSignal.emit(d))
                    self.letter_buttons_layout.addWidget(button)
                    self.letter_buttons.append(button)
            
            # Add a placeholder if no letters found
            if not letter_files:
                label = QLabel("No previous letters found")
                label.setStyleSheet("color: #AAAAAA; padding: 6px;")
                self.letter_buttons_layout.addWidget(label)
                self.letter_buttons.append(label)
                
        except Exception as e:
            print(f"Error updating letter buttons: {e}")
            label = QLabel(f"Error: {str(e)[:40]}")
            label.setStyleSheet("color: #FF6666; padding: 6px;")
            self.letter_buttons_layout.addWidget(label)
            self.letter_buttons.append(label)
    
    def flash_status(self, message, color, duration=2000):
        """Flash a status message temporarily"""
        self.statusFlashed.emit(message, color, duration)
        
    def flash_status_slot(self, message, color, duration):
        """Slot to handle status flash signal"""
        self.status_label.setStyleSheet(f"""
            background-color: {color};
            color: white;
            padding: 8px;
            border-radius: 5px;
            font-weight: bold;
        """)
        self.status_label.setText(message)
        QTimer.singleShot(duration, lambda: (
            self.status_label.setStyleSheet(self._original_status_style),
            self.status_label.setText(self._original_status_text)
        ))
    
    def browse_folder(self):
        """Show a folder selection dialog"""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.browseFolderSignal.emit(folder_path)
            return folder_path
        return None

class DesktopUI:
    """Desktop UI manager"""
    
    def __init__(self, config, web_ui, screenshot_manager=None, key_points_extractor=None, letter_generator=None, sync_manager=None):
        self.config = config
        self.web_ui = web_ui
        self.action_history = []
        self.stop_event = threading.Event()
        
        # Initialize PyQt application
        self.app = QApplication.instance() or QApplication(sys.argv)
        
        # Create main window
        self.window = NovaWindow(config)
        
        # Connect signals to handlers
        self._connect_signals()
        
        # Set up timers
        self._setup_timers()
        
        # Use provided components or create new ones if not provided
        from core.screenshot import ScreenshotManager
        from core.key_points import KeyPointsExtractor
        from core.letter import LetterGenerator
        from core.sync import SyncManager
        
        self.screenshot_manager = screenshot_manager or ScreenshotManager(config)
        self.key_points_extractor = key_points_extractor or KeyPointsExtractor(config, self.screenshot_manager.get_queue())
        self.letter_generator = letter_generator or LetterGenerator(config)
        self.sync_manager = sync_manager or SyncManager(config)
    
    def _connect_signals(self):
        """Connect UI signals to handlers"""
        self.window.generateLetterSignal.connect(self.generate_today_letter)
        self.window.openLetterSignal.connect(self.open_letter)
        self.window.openWebUISignal.connect(self.open_web_ui)
        self.window.syncNowSignal.connect(self.sync_letters_now)
        self.window.browseFolderSignal.connect(self.handle_browse_folder)
    
    def _setup_timers(self):
        """Set up UI update timers"""
        # Key points timer
        self.key_points_timer = QTimer()
        self.key_points_timer.timeout.connect(self.check_key_points)
        self.key_points_timer.setInterval(60 * 1000)  # Check every minute

        # UI update timer
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.update_ui)
        
        # Action cleanup timer
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self.cleanup_old_actions)
        
        # Letter buttons update timer
        self.letter_buttons_timer = QTimer()
        self.letter_buttons_timer.timeout.connect(self.update_letter_buttons)
        self.letter_buttons_timer.setInterval(15 * 60 * 1000)  # 15 minutes
        
        # Sync timer
        self.sync_timer = QTimer()
        self.sync_timer.timeout.connect(self.sync_letters)
        self.sync_timer.setInterval(30 * 60 * 1000)  # 30 minutes
    
    def check_key_points(self):
        """Check if key points should be extracted based on queue size"""
        if self.stop_event.is_set():
            return
                
        # Get the current queue
        queue = self.screenshot_manager.get_queue()
        
        # Update the key_points_extractor's queue reference
        self.key_points_extractor.screenshots_queue = queue
        
        # Check if we have enough screenshots to extract key points
        if len(queue) >= self.key_points_extractor.interval:
            action = NovaAction(ActionType.KEY_POINTS)
            action.details = f"Extracting from {len(queue)} screenshots"
            self.action_history.insert(0, action)
            action.status = ActionStatus.PROCESSING
            
            # Run extraction in a separate thread to prevent UI freezing
            def extract_thread():
                try:
                    key_points_file = self.key_points_extractor.extract_key_points()
                    if key_points_file:
                        action.status = ActionStatus.COMPLETED
                        action.result = f"Key points extracted to {os.path.basename(key_points_file)}"
                        self.window.flash_status("Key points extracted", "#73C991")
                    else:
                        action.status = ActionStatus.FAILED
                        action.error = "Failed to extract key points"
                        self.window.flash_status("Failed to extract key points", "#F14C4C")
                except Exception as e:
                    action.status = ActionStatus.FAILED
                    action.error = str(e)
                    self.window.flash_status(f"Error extracting key points: {str(e)[:30]}", "#F14C4C")
            
            # Create and start thread inside the same scope as the function definition
            thread = threading.Thread(target=extract_thread)
            thread.daemon = True
            thread.start()

    def show(self):
        """Show the main window"""
        self.window.show()
    
    def hide(self):
        """Hide the main window"""
        self.window.hide()
    
    def start(self):
        """Start the desktop UI and associated functionality"""
        # Start timers
        self.ui_timer.start(100)  # Update UI every 100ms
        self.cleanup_timer.start(60000)  # Clean up old actions every minute
        self.letter_buttons_timer.start()  # Update letter buttons periodically
        self.sync_timer.start()  # Start sync timer
        self.key_points_timer.start()
        
        # Initialize letter buttons
        try:
            self.update_letter_buttons()
        except Exception as e:
            print(f"Warning: Could not initialize letter buttons: {e}")
        
        # Only start the screenshot manager if we created it (not if it was passed in)
        # if not hasattr(self, '_screenshot_manager_provided') or not self._screenshot_manager_provided:
        #    self.screenshot_manager.start()
        
        # Start daily letter scheduler
        self._start_letter_scheduler()
        
        # Start letter checker
        self._start_letter_checker()
        
        # Start web server if not already started
        self.web_ui.start()
        
        # Log startup
        print("Desktop UI started")
        self.window.flash_status("Nova Project started", "#73C991", 3000)
        
        # Run the app
        return self.app.exec_()
    
    def stop(self):
        """Stop the desktop UI and associated functionality"""
        self.stop_event.set()
        
        # Stop timers
        self.ui_timer.stop()
        self.cleanup_timer.stop()
        self.letter_buttons_timer.stop()
        self.sync_timer.stop()
        self.key_points_timer.stop()
        
        # Stop screenshot manager
        self.screenshot_manager.stop()
        
        # Stop web UI
        self.web_ui.stop()
        
        print("Desktop UI stopped")
    
    def _start_letter_scheduler(self):
        """Start the thread that schedules daily letters"""
        thread = threading.Thread(target=self.letter_generator.schedule_daily_letter)
        thread.daemon = True
        thread.start()
    
    def _start_letter_checker(self):
        """Start the thread that checks for missed letters"""
        def check_and_generate_letter():
            while not self.stop_event.is_set():
                if self.letter_generator.is_after_generation_time() and not self.letter_generator.check_todays_letter_exists():
                    print("It's after generation time and today's letter hasn't been generated. Generating now...")
                    self.window.flash_status("Generating today's letter...", "#3794FF")
                    self.letter_generator.generate_letter()
                time.sleep(60)  # Check every minute
        
        thread = threading.Thread(target=check_and_generate_letter)
        thread.daemon = True
        thread.start()
    
    def update_ui(self):
        """Update the UI with current status"""
        # Update the latest activity
        self.window.update_latest_activity(self.action_history)
        
        # Update status with constant color (no color changes)
        screenshot_count = len(self.screenshot_manager.get_queue())
        next_letter_time = self._get_next_letter_time()
        status_text = f"Screenshots: {screenshot_count} | Letter: {next_letter_time}"
        self.window.update_status(status_text)
    
    def _get_next_letter_time(self):
        """Get the time of the next scheduled letter"""
        import datetime
        import schedule
        
        now = datetime.datetime.now()
        next_run = schedule.next_run()
        
        if next_run:
            return next_run.strftime('%H:%M:%S')
        else:
            # If today's letter exists, show tomorrow's time
            if self.letter_generator.check_todays_letter_exists():
                tomorrow = now + datetime.timedelta(days=1)
                return tomorrow.replace(hour=21, minute=0, second=0).strftime('%H:%M:%S')
            else:
                # If today's letter doesn't exist and it's after the generation time, show "Due Now"
                if self.letter_generator.is_after_generation_time():
                    return "Due Now"
                # Otherwise show today's generation time
                generation_time = self.config.get('letter_generation_time', '21:00')
                hour, minute = map(int, generation_time.split(':'))
                return now.replace(hour=hour, minute=minute, second=0).strftime('%H:%M:%S')
    
    def cleanup_old_actions(self):
        """Remove old actions from history"""
        if self.stop_event.is_set():
            return
            
        current_time = time.time()
        to_remove = []
        
        for action in self.action_history:
            # Keep letter actions forever, clean up others after 1 hour
            if action.action_type != ActionType.LETTER and (current_time - action.creation_time > 3600):
                to_remove.append(action)
        
        for action in to_remove:
            if action in self.action_history:
                self.action_history.remove(action)
    
    def update_letter_buttons(self):
        """Update letter buttons in the UI"""
        self.window.update_letter_buttons()
    
    def open_web_ui(self):
        """Open the Web UI in the default browser"""
        try:
            webbrowser.open(f'http://localhost:{self.web_ui.port}')
        except Exception as e:
            self.window.flash_status(f"Error opening web UI: {str(e)[:30]}", "#F14C4C")
    
    def open_letter(self, date_str):
        """Open a specific letter in the web UI"""
        try:
            # Open the letter in the web UI with a hash to indicate which letter to show
            web_url = f'http://localhost:{self.web_ui.port}/#letter/{date_str}'
            self.window.flash_status(f"Opening letter from {date_str} in web UI", "#3794FF")
            webbrowser.open(web_url)
        except Exception as e:
            self.window.flash_status(f"Error opening letter: {str(e)[:30]}", "#F14C4C")
    
    def generate_today_letter(self):
        """Generate today's letter"""
        # Create a letter action
        action = NovaAction(ActionType.LETTER)
        action.details = "Generating letter for today"
        self.action_history.insert(0, action)
        action.status = ActionStatus.PROCESSING
        
        self.window.flash_status("Generating today's letter...", "#3794FF")
        
        # Generate letter in a separate thread
        def generate_thread():
            try:
                letter_file = self.letter_generator.generate_letter()
                if letter_file:
                    action.status = ActionStatus.COMPLETED
                    action.result = f"Letter generated: {os.path.basename(letter_file)}"
                    self.window.flash_status("Letter generated successfully", "#73C991")
                else:
                    action.status = ActionStatus.FAILED
                    action.error = "Failed to generate letter"
                    self.window.flash_status("Failed to generate letter", "#F14C4C")
            except Exception as e:
                action.status = ActionStatus.FAILED
                action.error = str(e)
                self.window.flash_status(f"Error: {str(e)[:30]}", "#F14C4C")
        
        thread = threading.Thread(target=generate_thread)
        thread.daemon = True
        thread.start()
    
    def sync_letters(self):
        """Sync letters based on configuration"""
        # Create a sync action
        action = NovaAction(ActionType.SYNC)
        action.details = "Manual sync"
        self.action_history.insert(0, action)
        action.status = ActionStatus.PROCESSING
        
        try:
            self.window.flash_status("Syncing letters...", "#3794FF")
            # Use bidirectional_sync instead of sync_all_letters for true bidirectional sync
            result = self.sync_manager.bidirectional_sync()
            
            if result:
                action.status = ActionStatus.COMPLETED
                action.result = "Letters synced successfully"
                self.window.flash_status("Letters synced successfully", "#73C991")
            else:
                action.status = ActionStatus.COMPLETED
                action.result = "Sync completed (no changes)"
                self.window.flash_status("Sync completed (no changes)", "#73C991")
            
        except Exception as e:
            action.status = ActionStatus.FAILED
            action.error = str(e)
            self.window.flash_status(f"Sync error: {str(e)[:30]}", "#F14C4C")
    
    def sync_letters_now(self):
        """Manually trigger letter sync"""
        thread = threading.Thread(target=self.sync_letters)
        thread.daemon = True
        thread.start()
    
    def handle_browse_folder(self, folder_path):
        """Handle folder selection from UI"""
        # Forward to web UI for API response
        self.web_ui.set_selected_folder(folder_path)

```

## File: ui\web.py

```python
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
    
    def __init__(self, config, port=5678):
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
```

## File: util\helpers.py

```python
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

```

## File: web\templates\index.html

```html
<!-- web/templates/index.html -->
<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nova Project</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css" rel="stylesheet">
    <!-- Add highlight.js CSS for syntax highlighting -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.7.0/styles/github.min.css" id="light-theme-code">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.7.0/styles/github-dark.min.css" id="dark-theme-code" disabled>
    <style>
        :root {
            /* Theme variables will be set in CSS */
            /* Light theme (default) */
            --primary-color: #4361ee;
            --secondary-color: #3ECF8E;
            --accent-color: #7B2CBF;
            --bg-color: #F8F9FA;
            --card-color: #FFFFFF;
            --text-color: #333333;
            --border-color: #E0E0E0;
            --hover-color: #F1F3F9;
            --success-color: #4CAF50;
            --warning-color: #FF9800;
            --danger-color: #F44336;
            --muted-color: #6c757d;
            --shadow-sm: 0 2px 4px rgba(0,0,0,0.05);
            --shadow-md: 0 4px 8px rgba(0,0,0,0.1);
            --shadow-lg: 0 8px 16px rgba(0,0,0,0.1);
            --radius-sm: 4px;
            --radius-md: 8px;
            --radius-lg: 16px;
            --font-sans: 'Segoe UI', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
            --font-mono: 'Consolas', 'Monaco', 'Andale Mono', 'Ubuntu Mono', monospace;
            --transition-fast: 0.15s ease;
            --transition-normal: 0.25s ease;
        }
        
        /* Dark theme */
        html[data-theme='dark'] {
            --primary-color: #6366F1;
            --secondary-color: #10B981;
            --accent-color: #8B5CF6;
            --bg-color: #111827;
            --card-color: #1F2937;
            --text-color: #F9FAFB;
            --border-color: #374151;
            --hover-color: #2D3748;
            --success-color: #059669;
            --warning-color: #D97706;
            --danger-color: #DC2626;
            --muted-color: #9CA3AF;
            --shadow-sm: 0 2px 4px rgba(0,0,0,0.3);
            --shadow-md: 0 4px 8px rgba(0,0,0,0.4);
            --shadow-lg: 0 8px 16px rgba(0,0,0,0.5);
        }
        
        /* Light theme */
        html[data-theme='light'] {
            --primary-color: #4361ee;
            --secondary-color: #3ECF8E;
            --accent-color: #7B2CBF;
            --bg-color: #F8F9FA;
            --card-color: #FFFFFF;
            --text-color: #333333;
            --border-color: #E0E0E0;
            --hover-color: #F1F3F9;
            --success-color: #4CAF50;
            --warning-color: #FF9800;
            --danger-color: #F44336;
            --muted-color: #6c757d;
        }
        
        /* Custom theme */
        html[data-theme='custom'] {
            --primary-color: #FF5722;
            --secondary-color: #03A9F4;
            --accent-color: #9C27B0;
            --bg-color: #FFF8E1;
            --card-color: #FFFFFF;
            --text-color: #212121;
            --border-color: #BDBDBD;
            --hover-color: #F5F5F5;
            --success-color: #8BC34A;
            --warning-color: #FFEB3B;
            --danger-color: #FF5252;
            --muted-color: #9E9E9E;
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: var(--font-sans);
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 0;
            line-height: 1.6;
            font-size: 16px;
            transition: background-color var(--transition-normal), color var(--transition-normal);
        }
        
        .container {
            max-width: 1280px;
            margin: 0 auto;
            padding: 20px;
        }
        
        header {
            background-color: var(--card-color);
            padding: 1rem;
            box-shadow: var(--shadow-sm);
            position: sticky;
            top: 0;
            z-index: 100;
            margin-bottom: 30px;
            border-bottom: 1px solid var(--border-color);
            transition: background-color var(--transition-normal);
        }
        
        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
            max-width: 1280px;
            margin: 0 auto;
        }
        
        .brand {
            display: flex;
            align-items: center;
        }
        
        .brand h1 {
            margin: 0;
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--primary-color);
            transition: color var(--transition-normal);
        }
        
        .brand-icon {
            margin-right: 15px;
            color: var(--primary-color);
            font-size: 1.8rem;
            transition: color var(--transition-normal);
        }
        
        .nav-links {
            display: flex;
            gap: 0.75rem;
        }
        
        .nav-links a {
            color: var(--text-color);
            text-decoration: none;
            padding: 0.5rem 0.75rem;
            border-radius: var(--radius-sm);
            transition: all var(--transition-fast);
            font-weight: 500;
        }
        
        .nav-links a:hover {
            background-color: var(--hover-color);
        }
        
        .nav-links a.active {
            background-color: var(--primary-color);
            color: white;
        }
        
        /* Copy button styling */
        .copy-button {
            position: absolute;
            top: 5px;
            right: 5px;
            background-color: var(--primary-color);
            color: white;
            border: none;
            border-radius: var(--radius-sm);
            padding: 4px 8px;
            font-size: 12px;
            cursor: pointer;
            opacity: 0;
            transition: opacity var(--transition-fast), background-color var(--transition-fast);
        }
        
        .markdown-body pre {
            position: relative;
            border-radius: var(--radius-sm);
            overflow: hidden;
        }
        
        .markdown-body pre:hover .copy-button {
            opacity: 1;
        }
        
        .copy-button:hover {
            background-color: var(--accent-color);
        }
        
        .copy-button.copied {
            background-color: var(--success-color);
        }
        
        .main-content {
            display: grid;
            grid-template-columns: 1fr 3fr;
            gap: 24px;
        }
        
        .sidebar {
            background-color: var(--card-color);
            border-radius: var(--radius-md);
            padding: 1.5rem;
            height: fit-content;
            box-shadow: var(--shadow-sm);
            transition: background-color var(--transition-normal), box-shadow var(--transition-normal);
        }
        
        .sidebar h2 {
            margin-top: 0;
            color: var(--primary-color);
            font-size: 1.2rem;
            margin-bottom: 1.25rem;
            font-weight: 600;
            transition: color var(--transition-normal);
        }
        
        .sidebar-actions {
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin-bottom: 1.5rem;
        }
        
        .btn {
            background-color: var(--primary-color);
            color: white;
            border: none;
            padding: 10px 16px;
            border-radius: var(--radius-sm);
            cursor: pointer;
            font-weight: 600;
            transition: background-color var(--transition-fast), transform var(--transition-fast);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            box-shadow: var(--shadow-sm);
            font-size: 0.9rem;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-md);
        }
        
        .btn:active {
            transform: translateY(0);
        }
        
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .btn-success {
            background-color: var(--secondary-color);
        }
        
        .btn-accent {
            background-color: var(--accent-color);
        }
        
        .btn-warning {
            background-color: var(--warning-color);
        }
        
        .btn-danger {
            background-color: var(--danger-color);
        }
        
        .calendar-view {
            background-color: var(--card-color);
            border-radius: var(--radius-md);
            padding: 1.5rem;
            box-shadow: var(--shadow-sm);
            transition: background-color var(--transition-normal), box-shadow var(--transition-normal);
        }
        
        .calendar-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
        }
        
        .calendar-header h2 {
            margin: 0;
            color: var(--primary-color);
            font-size: 1.4rem;
            font-weight: 600;
            transition: color var(--transition-normal);
        }
        
        .calendar-controls {
            display: flex;
            gap: 8px;
        }
        
        .calendar-grid {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 8px;
            margin-bottom: 12px;
        }
        
        .calendar-days-container {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 8px;
        }
        
        .calendar-day-header {
            text-align: center;
            font-weight: 600;
            padding: 8px;
            color: var(--text-color);
            font-size: 0.85rem;
        }
        
        .calendar-day {
            background-color: var(--card-color);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-sm);
            min-height: 100px;
            padding: 8px;
            position: relative;
            transition: all var(--transition-fast);
            box-shadow: var(--shadow-sm);
        }
        
        .calendar-day:hover {
            box-shadow: var(--shadow-md);
            transform: translateY(-2px);
            border-color: var(--primary-color);
        }
        
        .calendar-day-number {
            font-size: 0.85rem;
            font-weight: 500;
            color: var(--muted-color);
            margin-bottom: 6px;
        }
        
        .day-content {
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin-top: 10px;
        }
        
        .letter-card {
            padding: 8px;
            border-radius: var(--radius-sm);
            cursor: pointer;
            position: relative;
            display: flex;
            flex-direction: column;
            transition: all var(--transition-fast);
            border: 1px solid transparent;
        }
        
        .letter-card:hover {
            transform: translateY(-2px);
        }
        
        .letter-card.mine {
            background-color: rgba(67, 97, 238, 0.1);
            border-color: rgba(67, 97, 238, 0.3);
        }
        
        .letter-card.mine:hover {
            background-color: rgba(67, 97, 238, 0.15);
        }
        
        .letter-card.shared {
            background-color: rgba(62, 207, 142, 0.1);
            border-color: rgba(62, 207, 142, 0.3);
        }
        
        .letter-card.shared:hover {
            background-color: rgba(62, 207, 142, 0.15);
        }
        
        .letter-card.not-shared {
            background-color: rgba(200, 200, 200, 0.1);
            border-color: rgba(200, 200, 200, 0.3);
        }
        
        .letter-card.not-shared:hover {
            background-color: rgba(200, 200, 200, 0.15);
        }
        
        .letter-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }
        
        .letter-card-title {
            font-weight: 500;
            font-size: 0.9rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .letter-card-author {
            font-size: 0.75rem;
            color: var(--muted-color);
        }
        
        .letter-preview {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(0, 0, 0, 0.7);
            z-index: 1000;
            padding: 20px;
            overflow-y: auto;
            backdrop-filter: blur(5px);
        }
        
        .letter-preview-content {
            background-color: var(--card-color);
            max-width: 900px;
            margin: 40px auto;
            padding: 30px;
            border-radius: var(--radius-lg);
            position: relative;
            color: var(--text-color);
            box-shadow: var(--shadow-lg);
            transition: background-color var(--transition-normal);
        }
        
        .letter-preview-content h1,
        .letter-preview-content h2,
        .letter-preview-content h3 {
            color: var(--primary-color);
        }
        
        .close-preview {
            position: fixed;
            top: 20px;
            right: 30px;
            font-size: 2rem;
            color: white;
            cursor: pointer;
            z-index: 1001;
            transition: transform var(--transition-fast);
        }
        
        .close-preview:hover {
            transform: rotate(90deg);
        }
        
        .letter-actions {
            position: absolute;
            top: 20px;
            right: 20px;
            display: flex;
            gap: 10px;
        }
        
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: var(--radius-sm);
            font-size: 0.75rem;
            background-color: var(--primary-color);
            color: white;
            font-weight: 500;
        }
        
        .badge-success {
            background-color: var(--success-color);
        }
        
        .badge-accent {
            background-color: var(--accent-color);
        }
        
        .badge-warning {
            background-color: var(--warning-color);
        }
        
        .user-list {
            margin-top: 1.5rem;
        }
        
        .user-list h3 {
            margin-top: 0;
            font-size: 1rem;
            color: var(--primary-color);
            margin-bottom: 1rem;
            font-weight: 600;
            transition: color var(--transition-normal);
        }
        
        .user-item {
            display: flex;
            align-items: center;
            padding: 8px 10px;
            border-radius: var(--radius-sm);
            margin-bottom: 6px;
            transition: background-color var(--transition-fast);
        }
        
        .user-item:hover {
            background-color: var(--hover-color);
        }
        
        .user-avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background-color: var(--primary-color);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 12px;
            font-weight: 600;
            color: white;
            font-size: 0.85rem;
            transition: background-color var(--transition-normal);
        }
        
        .user-name {
            flex-grow: 1;
        }
        
        .user-letter-count {
            background-color: var(--accent-color);
            color: white;
            border-radius: 50%;
            width: 24px;
            height: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75rem;
            font-weight: 600;
            transition: background-color var(--transition-normal);
        }

        .tooltip {
            position: relative;
        }

        .tooltip .tooltiptext {
            visibility: hidden;
            width: 150px;
            background-color: rgba(0, 0, 0, 0.8);
            color: #fff;
            text-align: center;
            border-radius: var(--radius-sm);
            padding: 6px 8px;
            position: absolute;
            z-index: 1;
            bottom: 125%;
            left: 50%;
            margin-left: -75px;
            opacity: 0;
            transition: opacity 0.3s;
            font-size: 0.8rem;
            pointer-events: none;
        }

        .tooltip:hover .tooltiptext {
            visibility: visible;
            opacity: 1;
        }

        .loading {
            text-align: center;
            padding: 30px;
            color: var(--text-color);
        }

        .spinner {
            border: 4px solid rgba(255, 255, 255, 0.1);
            border-radius: 50%;
            border-top: 4px solid var(--primary-color);
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .today {
            border: 2px solid var(--primary-color);
            background-color: var(--card-color);
            box-shadow: var(--shadow-md);
        }

        .empty-day {
            opacity: 0.4;
            background-color: transparent;
            border: 1px dashed var(--border-color);
            box-shadow: none;
        }
        
        .empty-day:hover {
            transform: none;
            box-shadow: none;
        }

        .notification {
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: var(--radius-md);
            background-color: var(--success-color);
            color: white;
            box-shadow: var(--shadow-md);
            z-index: 1000;
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s ease;
            max-width: 350px;
        }

        .notification.show {
            transform: translateY(0);
            opacity: 1;
        }

        .notification.error {
            background-color: var(--danger-color);
        }
        
        /* Styles for the letter iframe */
        .letter-iframe {
            width: 100%;
            height: calc(100vh - 150px);
            border: none;
            background-color: var(--card-color);
            border-radius: var(--radius-md);
        }

        /* Theme switcher */
        .theme-switcher {
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 12px;
            margin-top: 20px;
            background-color: var(--bg-color);
            border-radius: var(--radius-sm);
            border: 1px solid var(--border-color);
        }
        
        .theme-option {
            width: 28px;
            height: 28px;
            border-radius: 50%;
            cursor: pointer;
            border: 2px solid transparent;
            position: relative;
            transition: all var(--transition-fast);
        }
        
        .theme-option.active {
            border-color: var(--primary-color);
            transform: scale(1.1);
        }
        
        .theme-light {
            background: linear-gradient(135deg, #f5f5f5 50%, #e0e0e0 50%);
        }
        
        .theme-dark {
            background: linear-gradient(135deg, #333333 50%, #121212 50%);
        }
        
        .theme-custom {
            background: linear-gradient(135deg, #FF5722 50%, #FFF8E1 50%);
        }
        
        .edit-mode-toggle {
            margin-top: 12px;
            padding: 12px;
            display: flex;
            align-items: center;
            background-color: var(--bg-color);
            border-radius: var(--radius-sm);
            border: 1px solid var(--border-color);
        }
        
        .edit-toggle {
            margin-left: 10px;
        }
        
        /* Switch toggle styling */
        .switch {
            position: relative;
            display: inline-block;
            width: 50px;
            height: 24px;
        }
        
        .switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #ccc;
            transition: .4s;
            border-radius: 24px;
        }
        
        .slider:before {
            position: absolute;
            content: "";
            height: 18px;
            width: 18px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        }
        
        input:checked + .slider {
            background-color: var(--secondary-color);
        }
        
        input:checked + .slider:before {
            transform: translateX(26px);
        }

        /* Editor styles */
        .letter-editor {
            display: none;
            background-color: var(--card-color);
            border-radius: var(--radius-md);
            padding: 1.5rem;
            position: relative;
            box-shadow: var(--shadow-md);
            margin-top: 20px;
            transition: background-color var(--transition-normal);
        }
        
        .editor-actions {
            display: flex;
            justify-content: flex-end;
            gap: 10px;
            margin-top: 1rem;
        }
        
        .editor-textarea {
            width: 100%;
            min-height: 500px;
            padding: 15px;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border-color);
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: var(--font-mono);
            font-size: 14px;
            line-height: 1.6;
            resize: vertical;
            transition: border-color var(--transition-fast);
        }
        
        .editor-textarea:focus {
            outline: none;
            border-color: var(--primary-color);
        }
        
        /* Full page letter view */
        .letter-page {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: var(--bg-color);
            z-index: 1001;
            overflow-y: auto;
        }
        
        .letter-page-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 20px;
            background-color: var(--card-color);
            border-bottom: 1px solid var(--border-color);
            position: sticky;
            top: 0;
            z-index: 10;
            box-shadow: var(--shadow-sm);
            transition: background-color var(--transition-normal);
        }
        
        .letter-page-title {
            color: var(--primary-color);
            margin: 0;
            font-size: 1.2rem;
            font-weight: 600;
            transition: color var(--transition-normal);
        }
        
        .letter-page-actions {
            display: flex;
            gap: 12px;
        }
        
        .letter-page-content {
            max-width: 850px;
            margin: 0 auto;
            padding: 40px 30px;
        }
        
        .toc-container {
            position: fixed;
            top: 70px;
            right: 20px;
            width: 260px;
            max-height: calc(100vh - 100px);
            background-color: var(--card-color);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-md);
            padding: 15px;
            overflow-y: auto;
            z-index: 1005;
            border: 1px solid var(--border-color);
            display: none;
            transition: background-color var(--transition-normal);
        }
        
        .toc-title {
            font-size: 1rem;
            font-weight: 600;
            color: var(--primary-color);
            margin-bottom: 12px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border-color);
            transition: color var(--transition-normal);
        }
        
        .toc-list {
            list-style: none;
            padding: 0;
            margin: 0;
        }
        
        .toc-item {
            margin: 6px 0;
        }
        
        .toc-link {
            color: var(--text-color);
            text-decoration: none;
            display: block;
            padding: 6px 10px;
            border-radius: var(--radius-sm);
            transition: background-color var(--transition-fast);
            font-size: 0.9rem;
        }
        
        .toc-link:hover {
            background-color: var(--hover-color);
        }
        
        .toc-h2 {
            padding-left: 0px;
        }
        
        .toc-h3 {
            padding-left: 15px;
            font-size: 0.85rem;
        }
        
        .toc-h4 {
            padding-left: 30px;
            font-size: 0.8rem;
        }

        /* Letter content styling improvements */
        .letter-content {
            line-height: 1.7;
        }

        .letter-container {
            padding: 0 15px;
        }
        
        /* Code block styling enhancements */
        .markdown-body pre {
            background-color: var(--bg-color);
            border-radius: var(--radius-sm);
            padding: 1em;
            overflow: auto;
            margin: 1em 0;
            box-shadow: var(--shadow-sm);
            transition: background-color var(--transition-normal);
        }
        
        .markdown-body code {
            font-family: var(--font-mono);
            font-size: 0.9em;
            padding: 0.2em 0.4em;
            border-radius: 3px;
            background-color: rgba(0, 0, 0, 0.05);
        }
        
        .markdown-body pre code {
            background-color: transparent;
            padding: 0;
            border-radius: 0;
        }
        
        /* Quick Action Button */
        .quick-action-btn {
            position: fixed;
            right: 30px;
            bottom: 30px;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background-color: var(--secondary-color);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: var(--shadow-lg);
            cursor: pointer;
            z-index: 90;
            transition: transform var(--transition-fast), background-color var(--transition-fast);
        }
        
        .quick-action-btn:hover {
            transform: scale(1.1);
        }
        
        .quick-action-menu {
            position: fixed;
            right: 30px;
            bottom: 100px;
            display: none;
            flex-direction: column;
            gap: 10px;
            z-index: 90;
        }
        
        .quick-action-item {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background-color: var(--card-color);
            color: var(--primary-color);
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: var(--shadow-md);
            cursor: pointer;
            transition: transform var(--transition-fast), background-color var(--transition-fast);
            position: relative;
        }
        
        .quick-action-item:hover {
            transform: scale(1.1);
            background-color: var(--primary-color);
            color: white;
        }
        
        .quick-action-item .tooltiptext {
            right: 60px;
            bottom: 10px;
            left: auto;
            margin-left: 0;
        }
        
        /* Empty state */
        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 3rem;
            text-align: center;
            color: var(--muted-color);
        }
        
        .empty-state-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
            color: var(--border-color);
        }
        
        .empty-state-text {
            font-size: 1.1rem;
            margin-bottom: 1.5rem;
        }

        /* Media queries for responsiveness */
        @media (max-width: 1024px) {
            .main-content {
                grid-template-columns: 1fr 2fr;
            }
        }
        
        @media (max-width: 768px) {
            .main-content {
                grid-template-columns: 1fr;
                gap: 16px;
            }
            
            .sidebar {
                order: 2;
            }
            
            .calendar-view {
                order: 1;
            }
            
            .calendar-day {
                min-height: 80px;
            }
            
            .toc-container {
                display: none !important;
                width: 100%;
                left: 0;
                right: 0;
                top: 0;
                border-radius: 0;
            }
            
            .letter-page-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 10px;
            }
            
            .letter-page-actions {
                width: 100%;
                justify-content: space-between;
            }
            
            .letter-page-content {
                padding: 20px 15px;
            }
            
            .quick-action-btn {
                right: 20px;
                bottom: 20px;
            }
        }
        
        @media (max-width: 576px) {
            .calendar-grid,
            .calendar-days-container {
                grid-template-columns: repeat(7, 1fr);
                gap: 4px;
            }
            
            .calendar-day {
                min-height: 60px;
                padding: 5px;
            }
            
            .calendar-day-header {
                font-size: 0.7rem;
                padding: 4px;
            }
            
            .letter-card {
                padding: 4px;
            }
            
            .letter-card-title {
                font-size: 0.8rem;
            }
            
            .letter-card-author {
                font-size: 0.7rem;
            }
            
            .brand h1 {
                font-size: 1.2rem;
            }
            
            .nav-links a {
                padding: 0.4rem 0.6rem;
                font-size: 0.9rem;
            }
        }
    </style>
</head>
<body>
    <header>
        <div class="header-content">
            <div class="brand">
                <div class="brand-icon">
                    {% if app_icon == "lightbulb" %}
                    <i class="fas fa-lightbulb"></i>
                    {% elif app_icon == "sparkles" %}
                    <i class="fas fa-magic"></i>
                    {% elif app_icon == "star" %}
                    <i class="fas fa-star"></i>
                    {% elif app_icon == "compass" %}
                    <i class="fas fa-compass"></i>
                    {% elif app_icon == "rocket" %}
                    <i class="fas fa-rocket"></i>
                    {% else %}
                    <i class="fas fa-lightbulb"></i>
                    {% endif %}
                </div>
                <h1>Nova Project</h1>
            </div>
            <div class="nav-links">
                <a href="/" class="active"><i class="fas fa-calendar-alt"></i> Calendar</a>
                <a href="/settings"><i class="fas fa-cog"></i> Settings</a>
            </div>
        </div>
    </header>
    
    <div class="container">
        <div class="main-content">
            <div class="sidebar">
                <h2><i class="fas fa-tachometer-alt"></i> Dashboard</h2>
                <div class="sidebar-actions">
                    <button id="generate-letter" class="btn btn-success">
                        <i class="fas fa-pen-fancy"></i> Generate Today's Letter
                    </button>
                    <button id="sync-letters" class="btn">
                        <i class="fas fa-sync-alt"></i> Sync Letters
                    </button>
                    <button id="open-settings" class="btn btn-accent">
                        <i class="fas fa-cog"></i> Settings
                    </button>
                </div>
                
                <!-- Theme Switcher -->
                <div class="theme-switcher">
                    <span>Theme:</span>
                    <div class="theme-option theme-light" data-theme="light" title="Light Theme"></div>
                    <div class="theme-option theme-dark" data-theme="dark" title="Dark Theme"></div>
                    <div class="theme-option theme-custom" data-theme="custom" title="Custom Theme"></div>
                </div>
                
                <!-- Edit Mode Toggle -->
                <div class="edit-mode-toggle">
                    <span>Edit Mode:</span>
                    <label class="switch edit-toggle">
                        <input type="checkbox" id="edit-mode-toggle" checked>
                        <span class="slider"></span>
                    </label>
                </div>
                
                <div class="user-list">
                    <h3><i class="fas fa-users"></i> Community</h3>
                    <div id="user-list-container">
                        <div class="loading">
                            <div class="spinner"></div>
                            <p>Loading users...</p>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="calendar-view">
                <div class="calendar-header">
                    <h2><i class="fas fa-calendar-alt"></i> <span id="current-month">March 2025</span></h2>
                    <div class="calendar-controls">
                        <button id="prev-month" class="btn">
                            <i class="fas fa-chevron-left"></i>
                        </button>
                        <button id="next-month" class="btn">
                            <i class="fas fa-chevron-right"></i>
                        </button>
                    </div>
                </div>
                
                <div class="calendar-grid">
                    <div class="calendar-day-header">Sun</div>
                    <div class="calendar-day-header">Mon</div>
                    <div class="calendar-day-header">Tue</div>
                    <div class="calendar-day-header">Wed</div>
                    <div class="calendar-day-header">Thu</div>
                    <div class="calendar-day-header">Fri</div>
                    <div class="calendar-day-header">Sat</div>
                </div>
                
                <!-- Calendar days will be populated by JavaScript -->
                <div id="calendar-days-container" class="calendar-days-container">
                    <div id="calendar-days" class="loading">
                        <div class="spinner"></div>
                        <p>Loading calendar...</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Quick Action Button -->
    <div class="quick-action-btn" id="quick-action-toggle">
        <i class="fas fa-plus"></i>
    </div>
    
    <div class="quick-action-menu" id="quick-action-menu">
        <div class="quick-action-item tooltip" id="quick-generate" title="Generate Letter">
            <i class="fas fa-pen-fancy"></i>
            <span class="tooltiptext">Generate Letter</span>
        </div>
        <div class="quick-action-item tooltip" id="quick-sync" title="Sync Letters">
            <i class="fas fa-sync-alt"></i>
            <span class="tooltiptext">Sync Letters</span>
        </div>
        <div class="quick-action-item tooltip" id="quick-screenshot" title="Take Screenshot">
            <i class="fas fa-camera"></i>
            <span class="tooltiptext">Take Screenshot</span>
        </div>
    </div>
    
    <!-- Letter Edit Mode -->
    <div id="letter-editor" class="letter-editor">
        <h2>Edit Letter</h2>
        <textarea id="editor-content" class="editor-textarea"></textarea>
        <div class="editor-actions">
            <button id="cancel-edit" class="btn btn-warning">
                <i class="fas fa-times"></i> Cancel
            </button>
            <button id="save-edit" class="btn btn-success">
                <i class="fas fa-save"></i> Save Changes
            </button>
        </div>
    </div>
    
    <!-- Full Letter Page View -->
    <div id="letter-page" class="letter-page">
        <div class="letter-page-header">
            <h3 class="letter-page-title">Letter View</h3>
            <div class="letter-page-actions">
                <button id="edit-letter" class="btn btn-accent">
                    <i class="fas fa-edit"></i> Edit
                </button>
                <button id="toggle-toc" class="btn">
                    <i class="fas fa-list"></i> Table of Contents
                </button>
                <button id="close-letter-page" class="btn btn-warning">
                    <i class="fas fa-times"></i> Close
                </button>
            </div>
        </div>
        <div id="letter-page-content" class="letter-page-content">
            <!-- Letter content will be loaded here -->
        </div>
        <!-- TOC will be added dynamically -->
    </div>
    
    <!-- Legacy letter preview (will be replaced) -->
    <div id="letter-preview" class="letter-preview">
        <div class="close-preview" id="close-preview">
            <i class="fas fa-times"></i>
        </div>
        <div class="letter-preview-content" id="letter-preview-content">
            <!-- Letter content will be loaded as an iframe -->
        </div>
    </div>
    
    <div id="notification" class="notification">
        <!-- Notification message will be shown here -->
    </div>
    
    <!-- Required Libraries -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/marked/4.0.2/marked.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.7.0/highlight.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.9/MathJax.js?config=TeX-AMS_HTML"></script>
    
    <script>
// Global variables and DOM element references
const PORT = "{{ port }}";
const API_BASE = `http://localhost:${PORT}/api`;
const USERNAME = "{{ username }}";

// DOM element references
const calendarDaysContainerEl = document.getElementById('calendar-days-container');
const calendarDaysEl = document.getElementById('calendar-days');
const currentMonthEl = document.getElementById('current-month');
const prevMonthBtn = document.getElementById('prev-month');
const nextMonthBtn = document.getElementById('next-month');
const letterPreviewEl = document.getElementById('letter-preview');
const letterPreviewContentEl = document.getElementById('letter-preview-content');
const closePreviewBtn = document.getElementById('close-preview');
const generateLetterBtn = document.getElementById('generate-letter');
const syncLettersBtn = document.getElementById('sync-letters');
const openSettingsBtn = document.getElementById('open-settings');
const userListContainerEl = document.getElementById('user-list-container');
const themeOptions = document.querySelectorAll('.theme-option');
const editModeToggle = document.getElementById('edit-mode-toggle');
const letterEditorEl = document.getElementById('letter-editor');
const editorContentEl = document.getElementById('editor-content');
const cancelEditBtn = document.getElementById('cancel-edit');
const saveEditBtn = document.getElementById('save-edit');
const letterPageEl = document.getElementById('letter-page');
const letterPageContentEl = document.getElementById('letter-page-content');
const closeLettterPageBtn = document.getElementById('close-letter-page');
const editLetterBtn = document.getElementById('edit-letter');
const toggleTocBtn = document.getElementById('toggle-toc');
const notificationEl = document.getElementById('notification');
const quickActionToggleBtn = document.getElementById('quick-action-toggle');
const quickActionMenu = document.getElementById('quick-action-menu');
const quickGenerateBtn = document.getElementById('quick-generate');
const quickSyncBtn = document.getElementById('quick-sync');
const quickScreenshotBtn = document.getElementById('quick-screenshot');

// State variables
let myLetters = [];
let communityLetters = {};
let currentEditLetter = null;
let editMode = true;
let currentDate = new Date();
let quickActionsVisible = false;

document.addEventListener('DOMContentLoaded', () => {
    // Configure marked.js with syntax highlighting
    marked.setOptions({
        highlight: function(code, lang) {
            const language = hljs.getLanguage(lang) ? lang : 'plaintext';
            return hljs.highlight(code, { language }).value;
        },
        langPrefix: 'hljs language-',
        gfm: true,
        breaks: true
    });

    renderCalendar();
    loadLetters();
    loadCommunityLetters();
    initTheme();
    loadMathJax();
    
    // Event listeners
    prevMonthBtn.addEventListener('click', () => {
        currentDate.setMonth(currentDate.getMonth() - 1);
        renderCalendar();
    });
    
    nextMonthBtn.addEventListener('click', () => {
        currentDate.setMonth(currentDate.getMonth() + 1);
        renderCalendar();
    });
    
    closePreviewBtn.addEventListener('click', () => {
        letterPreviewEl.style.display = 'none';
        letterPreviewContentEl.innerHTML = ''; // Clear content to release memory
    });
    
    generateLetterBtn.addEventListener('click', generateLetter);
    syncLettersBtn.addEventListener('click', syncLetters);
    openSettingsBtn.addEventListener('click', () => {
        window.location.href = '/settings';
    });
    
    // Theme switcher
    themeOptions.forEach(option => {
        option.addEventListener('click', () => {
            const theme = option.getAttribute('data-theme');
            setTheme(theme);
        });
    });
    
    // Edit mode toggle - enabled by default
    editModeToggle.checked = true;
    editMode = true;
    editModeToggle.addEventListener('change', () => {
        editMode = editModeToggle.checked;
        showNotification(editMode ? "Edit mode enabled" : "Edit mode disabled");
    });
    
    // Editor buttons
    cancelEditBtn.addEventListener('click', cancelEdit);
    saveEditBtn.addEventListener('click', saveEdit);
    
    // Letter page buttons
    closeLettterPageBtn.addEventListener('click', () => {
        letterPageEl.style.display = 'none';
        // Hide the TOC when closing the letter page
        hideTOC();
    });
    
    editLetterBtn.addEventListener('click', () => {
        if (currentEditLetter) {
            startEdit(currentEditLetter.content, currentEditLetter.username, currentEditLetter.dateStr);
            letterPageEl.style.display = 'none';
            hideTOC();
        }
    });
    
    toggleTocBtn.addEventListener('click', toggleTableOfContents);
    
    // Quick action buttons
    quickActionToggleBtn.addEventListener('click', toggleQuickActions);
    quickGenerateBtn.addEventListener('click', () => {
        generateLetter();
        toggleQuickActions();
    });
    quickSyncBtn.addEventListener('click', () => {
        syncLetters();
        toggleQuickActions();
    });
    quickScreenshotBtn.addEventListener('click', () => {
        showNotification("This feature requires the desktop app");
        toggleQuickActions();
    });
    
    // Close quick actions menu when clicking elsewhere
    document.addEventListener('click', (e) => {
        if (quickActionsVisible && 
            !e.target.closest('#quick-action-toggle') && 
            !e.target.closest('#quick-action-menu')) {
            toggleQuickActions(false);
        }
    });
    
    // Check for letter hash in URL
    checkForLetterInUrl();
});

// Toggle quick actions menu
function toggleQuickActions(forcedState) {
    if (forcedState !== undefined) {
        quickActionsVisible = forcedState;
    } else {
        quickActionsVisible = !quickActionsVisible;
    }
    
    if (quickActionsVisible) {
        quickActionMenu.style.display = 'flex';
        quickActionToggleBtn.innerHTML = '<i class="fas fa-times"></i>';
    } else {
        quickActionMenu.style.display = 'none';
        quickActionToggleBtn.innerHTML = '<i class="fas fa-plus"></i>';
    }
}

// Hide the table of contents
function hideTOC() {
    const tocContainer = document.querySelector('.toc-container');
    if (tocContainer) {
        tocContainer.style.display = 'none';
    }
}

// Load MathJax dynamically
function loadMathJax() {
    const script = document.createElement('script');
    script.src = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js";
    script.async = true;
    document.head.appendChild(script);
    
    window.MathJax = {
        tex: {
            inlineMath: [['$', '$'], ['\\(', '\\)']],
            displayMath: [['$$', '$$'], ['\\[', '\\]']]
        },
        svg: {
            fontCache: 'global'
        },
        options: {
            enableMenu: false
        }
    };
}

// Check if URL has a letter hash to open
function checkForLetterInUrl() {
    if (window.location.hash.startsWith('#letter/')) {
        const dateStr = window.location.hash.substring(8);
        if (dateStr && dateStr.length === 8) {
            // Wait a bit for letters to load
            setTimeout(() => {
                openLetter(dateStr, USERNAME, true);
            }, 1000);
        }
    }
}

// Initialize theme
function initTheme() {
    const savedTheme = localStorage.getItem('nova-theme') || 'light';
    setTheme(savedTheme);
}

// Set theme
function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('nova-theme', theme);
    
    // Update theme option active state
    themeOptions.forEach(option => {
        if (option.getAttribute('data-theme') === theme) {
            option.classList.add('active');
        } else {
            option.classList.remove('active');
        }
    });
    
    // Update code highlighting theme
    if (theme === 'dark') {
        document.getElementById('light-theme-code').disabled = true;
        document.getElementById('dark-theme-code').disabled = false;
    } else {
        document.getElementById('light-theme-code').disabled = false;
        document.getElementById('dark-theme-code').disabled = true;
    }
}

// Toggle table of contents
function toggleTableOfContents() {
    const tocContainer = document.querySelector('.toc-container');
    if (tocContainer) {
        if (tocContainer.style.display === 'none' || !tocContainer.style.display) {
            tocContainer.style.display = 'block';
        } else {
            tocContainer.style.display = 'none';
        }
    }
}

// Function to render the calendar
function renderCalendar() {
    // Clear previous calendar
    calendarDaysContainerEl.innerHTML = '';
    if(calendarDaysEl) {
        calendarDaysEl.className = ''; 
        calendarDaysEl.innerHTML = '';
    }
    
    // Update month and year display
    const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 
                       'July', 'August', 'September', 'October', 'November', 'December'];
    currentMonthEl.textContent = `${monthNames[currentDate.getMonth()]} ${currentDate.getFullYear()}`;
    
    // Get first day of month and number of days
    const firstDay = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1);
    const lastDay = new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 0);
    
    // Get the day of week for the first day (0 = Sunday, 6 = Saturday)
    const firstDayIndex = firstDay.getDay();
    
    // Create empty cells for days before the first day of the month
    for (let i = 0; i < firstDayIndex; i++) {
        const emptyDay = document.createElement('div');
        emptyDay.className = 'calendar-day empty-day';
        calendarDaysContainerEl.appendChild(emptyDay);
    }
    
    // Create cells for each day of the month
    const today = new Date();
    for (let day = 1; day <= lastDay.getDate(); day++) {
        const dayEl = document.createElement('div');
        dayEl.className = 'calendar-day';
        
        // Check if this is today
        if (today.getDate() === day && 
            today.getMonth() === currentDate.getMonth() && 
            today.getFullYear() === currentDate.getFullYear()) {
            dayEl.classList.add('today');
        }
        
        // Add day number
        const dayNumber = document.createElement('div');
        dayNumber.className = 'calendar-day-number';
        dayNumber.textContent = day;
        dayEl.appendChild(dayNumber);
        
        // Add content container
        const dayContent = document.createElement('div');
        dayContent.className = 'day-content';
        dayEl.appendChild(dayContent);
        
        // Add data attributes for identification
        const dateObj = new Date(currentDate.getFullYear(), currentDate.getMonth(), day);
        const dateStr = formatDateForAPI(dateObj);
        dayEl.setAttribute('data-date', dateStr);
        
        calendarDaysContainerEl.appendChild(dayEl);
    }
    
    // After rendering the calendar, populate with letter data if available
    if (myLetters.length > 0) {
        populateCalendarWithLetters();
    }
}

// Function to format date for API (YYYYMMDD)
function formatDateForAPI(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}${month}${day}`;
}

// Function to format date for display (YYYY-MM-DD)
function formatDateForDisplay(dateStr) {
    // Convert from YYYYMMDD to YYYY-MM-DD
    return `${dateStr.substring(0, 4)}-${dateStr.substring(4, 6)}-${dateStr.substring(6, 8)}`;
}

// Load user's letters
function loadLetters() {
    fetch(`${API_BASE}/letters`)
        .then(response => response.json())
        .then(data => {
            myLetters = data;
            populateCalendarWithLetters();
        })
        .catch(error => {
            console.error('Error loading letters:', error);
            showNotification('Error loading letters', true);
        });
}

// Load community letters
function loadCommunityLetters() {
    fetch(`${API_BASE}/community_letters`)
        .then(response => response.json())
        .then(data => {
            communityLetters = data;
            populateCalendarWithLetters();
            renderUserList();
        })
        .catch(error => {
            console.error('Error loading community letters:', error);
            // Still render user list even if there's an error
            renderUserList();
        });
}

// Populate calendar with letter data
function populateCalendarWithLetters() {
    // Clear existing letter badges
    document.querySelectorAll('.letter-card').forEach(card => card.remove());
    
    // Add my letters
    myLetters.forEach(letter => {
        const dateStr = letter.date_str;
        const dayEl = document.querySelector(`.calendar-day[data-date="${dateStr}"]`);
        
        if (dayEl) {
            const dayContent = dayEl.querySelector('.day-content');
            
            const letterCard = document.createElement('div');
            letterCard.className = `letter-card ${letter.synced ? 'shared' : 'not-shared'} mine`;
            
            const cardHeader = document.createElement('div');
            cardHeader.className = 'letter-card-header';
            
            const cardTitle = document.createElement('div');
            cardTitle.className = 'letter-card-title';
            cardTitle.textContent = 'Your Letter';
            
            const letterBadge = document.createElement('span');
            letterBadge.className = 'badge';
            letterBadge.textContent = letter.format === 'markdown' ? 'MD' : 'HTML';
            
            cardHeader.appendChild(cardTitle);
            cardHeader.appendChild(letterBadge);
            
            const cardAuthor = document.createElement('div');
            cardAuthor.className = 'letter-card-author';
            cardAuthor.textContent = letter.synced ? 'Shared' : 'Private';
            
            letterCard.appendChild(cardHeader);
            letterCard.appendChild(cardAuthor);
            
            letterCard.setAttribute('data-date', dateStr);
            letterCard.setAttribute('data-user', USERNAME);
            letterCard.setAttribute('data-synced', letter.synced);
            letterCard.setAttribute('data-format', letter.format || 'unknown');
            
            letterCard.addEventListener('click', () => openLetter(dateStr, USERNAME, true));
            dayContent.appendChild(letterCard);
        }
    });
    
    // Add community letters
    Object.keys(communityLetters).forEach(username => {
        if (username !== USERNAME) {
            communityLetters[username].forEach(letter => {
                const dateStr = letter.date_str;
                const dayEl = document.querySelector(`.calendar-day[data-date="${dateStr}"]`);
                
                if (dayEl) {
                    const dayContent = dayEl.querySelector('.day-content');
                    
                    const letterCard = document.createElement('div');
                    letterCard.className = 'letter-card shared';
                    
                    const cardHeader = document.createElement('div');
                    cardHeader.className = 'letter-card-header';
                    
                    const cardTitle = document.createElement('div');
                    cardTitle.className = 'letter-card-title';
                    cardTitle.textContent = 'Community Letter';
                    
                    const letterBadge = document.createElement('span');
                    letterBadge.className = 'badge badge-accent';
                    letterBadge.textContent = letter.format === 'markdown' ? 'MD' : 'HTML';
                    
                    cardHeader.appendChild(cardTitle);
                    cardHeader.appendChild(letterBadge);
                    
                    const cardAuthor = document.createElement('div');
                    cardAuthor.className = 'letter-card-author';
                    cardAuthor.textContent = `by ${username}`;
                    
                    letterCard.appendChild(cardHeader);
                    letterCard.appendChild(cardAuthor);
                    
                    letterCard.setAttribute('data-date', dateStr);
                    letterCard.setAttribute('data-user', username);
                    letterCard.setAttribute('data-format', letter.format || 'unknown');
                    
                    letterCard.addEventListener('click', () => openLetter(dateStr, username, false));
                    dayContent.appendChild(letterCard);
                }
            });
        }
    });
    
    // Add empty state for days with no content
    document.querySelectorAll('.calendar-day:not(.empty-day)').forEach(dayEl => {
        const dayContent = dayEl.querySelector('.day-content');
        if (!dayContent.children.length && !dayEl.classList.contains('empty-day')) {
            dayContent.innerHTML = ''; // Clear existing content
        }
    });
}

// Render user list in sidebar
function renderUserList() {
    userListContainerEl.innerHTML = '';
    
    // Add current user first
    const currentUserItem = document.createElement('div');
    currentUserItem.className = 'user-item';
    
    const currentUserAvatar = document.createElement('div');
    currentUserAvatar.className = 'user-avatar';
    currentUserAvatar.textContent = getInitials(USERNAME);
    currentUserAvatar.style.backgroundColor = 'var(--primary-color)';
    
    const currentUserName = document.createElement('div');
    currentUserName.className = 'user-name';
    currentUserName.textContent = `${USERNAME} (You)`;
    
    const currentUserLetterCount = document.createElement('div');
    currentUserLetterCount.className = 'user-letter-count';
    currentUserLetterCount.textContent = myLetters.length;
    
    currentUserItem.appendChild(currentUserAvatar);
    currentUserItem.appendChild(currentUserName);
    currentUserItem.appendChild(currentUserLetterCount);
    userListContainerEl.appendChild(currentUserItem);
    
    // Add other community users
    const communityUsers = Object.keys(communityLetters).filter(username => username !== USERNAME);
    
    if (communityUsers.length) {
        communityUsers.forEach((username, index) => {
            const userItem = document.createElement('div');
            userItem.className = 'user-item';
            
            const userAvatar = document.createElement('div');
            userAvatar.className = 'user-avatar';
            userAvatar.textContent = getInitials(username);
            // Assign different colors to different users
            const avatarColors = [
                'var(--accent-color)', 
                'var(--secondary-color)', 
                '#E91E63', 
                '#FF9800', 
                '#9C27B0'
            ];
            userAvatar.style.backgroundColor = avatarColors[index % avatarColors.length];
            
            const userName = document.createElement('div');
            userName.className = 'user-name';
            userName.textContent = username;
            
            const userLetterCount = document.createElement('div');
            userLetterCount.className = 'user-letter-count';
            userLetterCount.textContent = communityLetters[username].length;
            
            userItem.appendChild(userAvatar);
            userItem.appendChild(userName);
            userItem.appendChild(userLetterCount);
            userListContainerEl.appendChild(userItem);
        });
    } else {
        // If no other users, show a message
        const noUsersEl = document.createElement('div');
        noUsersEl.className = 'empty-state';
        noUsersEl.innerHTML = `
            <div class="empty-state-icon"><i class="fas fa-users-slash"></i></div>
            <div class="empty-state-text">No other users have shared letters yet</div>
        `;
        userListContainerEl.appendChild(noUsersEl);
    }
}

// Get initials from username
function getInitials(username) {
    if (!username) return '?';
    return username.charAt(0).toUpperCase();
}

// Function to open letter in the modern full-page view
function openLetter(dateStr, username, isMyLetter) {
    // Show loading state in the letter page
    letterPageContentEl.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading letter...</p></div>';
    letterPageEl.style.display = 'block';
    
    // Hide any existing TOC first
    hideTOC();
    
    const apiEndpoint = isMyLetter 
        ? `${API_BASE}/letter/${dateStr}`
        : `${API_BASE}/community_letter/${username}/${dateStr}`;
    
    fetch(apiEndpoint)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                letterPageContentEl.innerHTML = `<div class="empty-state">
                    <div class="empty-state-icon"><i class="fas fa-exclamation-triangle"></i></div>
                    <div class="empty-state-text">${data.error}</div>
                </div>`;
                return;
            }
            
            // Store letter data for editing
            currentEditLetter = {
                content: data.content,
                username: username,
                dateStr: dateStr,
                isMyLetter: isMyLetter,
                format: data.format || 'markdown'
            };
            
            // Update letter page title
            document.querySelector('.letter-page-title').textContent = 
                `Letter from ${username} - ${formatDateForDisplay(dateStr)}`;
            
            // Show edit button only if edit mode is enabled and it's the user's letter
            editLetterBtn.style.display = (editMode && isMyLetter) ? 'block' : 'none';
            
            // Check if it's markdown or HTML
            if (data.format === 'markdown' || data.content.trim().startsWith('#') || data.content.indexOf('\n## ') > -1) {
                // It's markdown, render with marked
                renderMarkdownLetter(data.content, dateStr, username, isMyLetter);
            } else {
                // It's HTML, use the template renderer
                renderHtmlLetter(data.content, dateStr, username, isMyLetter);
            }
            
            // Update URL hash for direct linking
            if (isMyLetter) {
                window.location.hash = `letter/${dateStr}`;
            }
        })
        .catch(error => {
            console.error('Error loading letter:', error);
            letterPageContentEl.innerHTML = `<div class="empty-state">
                <div class="empty-state-icon"><i class="fas fa-exclamation-triangle"></i></div>
                <div class="empty-state-text">Failed to load letter: ${error.message}</div>
                <button class="btn btn-accent" onclick="window.location.reload()">Reload Page</button>
            </div>`;
        });
}

// Render markdown letter
function renderMarkdownLetter(markdownContent, dateStr, username, isMyLetter) {
    try {
        // Parse tags and title (if present at the beginning)
        let tags = [];
        let title = `Letter from ${username}`;
        
        const lines = markdownContent.split('\n');
        if (lines.length > 0 && lines[0].startsWith('tags:')) {
            // Extract tags
            tags = lines[0].substring(5).trim().split(',').map(tag => tag.trim());
            lines.shift(); // Remove tags line
        }
        
        if (lines.length > 0 && lines[0].startsWith('# ')) {
            // Extract title
            title = lines[0].substring(2).trim();
            lines.shift(); // Remove title line
        }
        
        // Create formatted date
        const formattedDate = formatDateForDisplay(dateStr);
        
        // Render markdown content safely
        let htmlContent;
        try {
            htmlContent = marked.parse(lines.join('\n'));
        } catch (markdownError) {
            console.error("Markdown parsing error:", markdownError);
            htmlContent = `<div class="error">Error parsing markdown: ${markdownError.message}</div>
                          <pre>${lines.join('\n')}</pre>`;
        }
        
        // Create the complete HTML with the original pretty styling
        const letterHtml = `
            <div class="letter-container">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;">
                    <div>
                        <h1 style="margin-bottom: 10px; color: var(--primary-color);">${title}</h1>
                        <div style="display: flex; gap: 15px; font-size: 0.9rem; color: var(--text-color); opacity: 0.7;">
                            <div><i class="fas fa-calendar-alt"></i> ${formattedDate}</div>
                            <div><i class="fas fa-user"></i> ${username}</div>
                        </div>
                    </div>
                    <div style="display: flex; flex-wrap: wrap; gap: 6px; max-width: 40%;">
                        ${tags.map(tag => `<span class="badge badge-accent">${tag}</span>`).join('')}
                    </div>
                </div>
                
                <div class="letter-content markdown-body">
                    ${htmlContent}
                </div>
            </div>
        `;
        
        letterPageContentEl.innerHTML = letterHtml;
        
        // Create and attach the table of contents
        createTableOfContents();
        
        // Let the browser render the content before applying MathJax
        setTimeout(() => {
            // Apply MathJax if available
            if (window.MathJax) {
                try {
                    if (window.MathJax.typesetPromise) {
                        window.MathJax.typesetPromise([letterPageContentEl]).catch(err => {
                            console.log('MathJax typeset error (safely handled):', err);
                        });
                    } else if (window.MathJax.Hub) {
                        window.MathJax.Hub.Queue(["Typeset", window.MathJax.Hub, letterPageContentEl]);
                    }
                } catch (mathJaxError) {
                    console.warn("MathJax processing error (safely handled):", mathJaxError);
                }
            }
               
            // Initialize syntax highlighting
            try {
                // Force re-highlighting of all code blocks
                document.querySelectorAll('pre code').forEach((block) => {
                    // Add default class if none exists
                    if (!block.className) {
                        block.className = 'language-plaintext';
                    }
                    hljs.highlightElement(block);
                    
                    // Add copy button to each code block
                    const pre = block.parentNode;
                    const copyButton = document.createElement('button');
                    copyButton.className = 'copy-button';
                    copyButton.textContent = 'Copy';
                    
                    copyButton.addEventListener('click', () => {
                        // Copy code to clipboard
                        const code = block.textContent;
                        navigator.clipboard.writeText(code).then(() => {
                            // Visual feedback
                            copyButton.textContent = 'Copied!';
                            copyButton.classList.add('copied');
                            
                            // Reset after 2 seconds
                            setTimeout(() => {
                                copyButton.textContent = 'Copy';
                                copyButton.classList.remove('copied');
                            }, 2000);
                        }).catch(err => {
                            console.error('Failed to copy: ', err);
                            copyButton.textContent = 'Error';
                            setTimeout(() => {
                                copyButton.textContent = 'Copy';
                            }, 2000);
                        });
                    });
                    
                    pre.appendChild(copyButton);
                });
            } catch (syntaxError) {
                console.warn("Syntax highlighting error (safely handled):", syntaxError);
            }

        }, 100);
    } catch (e) {
        console.error("Error rendering markdown:", e);
        letterPageContentEl.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon"><i class="fas fa-exclamation-triangle"></i></div>
                <div class="empty-state-text">Error rendering markdown: ${e.message}</div>
                <pre style="white-space: pre-wrap; overflow-wrap: break-word; padding: 20px; background: var(--bg-color); color: var(--text-color); margin-top: 20px; border-radius: 4px; max-height: 300px; overflow-y: auto;">${markdownContent}</pre>
            </div>
        `;
    }
}

// Render HTML letter
function renderHtmlLetter(htmlContent, dateStr, username, isMyLetter) {
    try {
        // Create formatted date
        const formattedDate = formatDateForDisplay(dateStr);
        
        // Create a safe container for the HTML content
        const safeContainer = document.createElement('div');
        safeContainer.className = 'html-letter-container';
        letterPageContentEl.innerHTML = '';
        letterPageContentEl.appendChild(safeContainer);
        
        // Two different approaches:
        // 1. If it looks like a complete HTML document, use iframe for isolation
        if (htmlContent.trim().toLowerCase().startsWith('<!doctype html>') || 
            htmlContent.trim().toLowerCase().startsWith('<html')) {
            
            const iframe = document.createElement('iframe');
            iframe.className = 'letter-iframe';
            iframe.style.width = '100%';
            iframe.style.height = 'calc(100vh - 100px)';
            iframe.style.border = 'none';
            iframe.style.borderRadius = 'var(--radius-md)';
            
            safeContainer.appendChild(iframe);
            
            try {
                const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                iframeDoc.open();
                iframeDoc.write(htmlContent);
                iframeDoc.close();
            } catch (iframeError) {
                console.error("Error with iframe rendering:", iframeError);
                safeContainer.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon"><i class="fas fa-exclamation-triangle"></i></div>
                        <div class="empty-state-text">Error rendering HTML in iframe.</div>
                        <p>Attempting direct rendering instead.</p>
                    </div>
                `;
                // Fallback to direct innerHTML
                setTimeout(() => {
                    safeContainer.innerHTML = htmlContent;
                }, 100);
            }
        } 
        // 2. Otherwise treat as HTML fragment and insert directly
        else {
            safeContainer.innerHTML = htmlContent;
            
            // Try to apply MathJax if needed
            setTimeout(() => {
                if (window.MathJax) {
                    try {
                        if (window.MathJax.typesetPromise) {
                            window.MathJax.typesetPromise([safeContainer]).catch(err => {
                                console.log('MathJax typeset error (safely handled):', err);
                            });
                        } else if (window.MathJax.Hub) {
                            window.MathJax.Hub.Queue(["Typeset", window.MathJax.Hub, safeContainer]);
                        }
                    } catch (mathJaxError) {
                        console.warn("MathJax processing error (safely handled):", mathJaxError);
                    }
                }
                
                // Also apply syntax highlighting to any code blocks
                try {
                    safeContainer.querySelectorAll('pre code').forEach((block) => {
                        if (!block.className) {
                            block.className = 'language-plaintext';
                        }
                        hljs.highlightElement(block);
                    });
                } catch (syntaxError) {
                    console.warn("Syntax highlighting error (safely handled):", syntaxError);
                }
            }, 100);
        }
    } catch (e) {
        console.error("Error rendering HTML:", e);
        letterPageContentEl.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon"><i class="fas fa-exclamation-triangle"></i></div>
                <div class="empty-state-text">Error rendering HTML: ${e.message}</div>
                <p>The HTML content cannot be displayed safely.</p>
            </div>
        `;
    }
}

// Create table of contents
function createTableOfContents() {
    try {
        const headings = letterPageContentEl.querySelectorAll('h2, h3, h4');
        
        // Remove any existing TOC
        const existingToc = document.querySelector('.toc-container');
        if (existingToc) {
            existingToc.remove();
        }
        
        if (headings.length > 0) {
            // Create TOC container
            const tocContainer = document.createElement('div');
            tocContainer.className = 'toc-container';
            
            const tocTitle = document.createElement('div');
            tocTitle.className = 'toc-title';
            tocTitle.textContent = 'Table of Contents';
            tocContainer.appendChild(tocTitle);
            
            const tocList = document.createElement('ul');
            tocList.className = 'toc-list';
            
            // Add TOC items
            headings.forEach((heading, index) => {
                // Create ID for the heading if it doesn't have one
                const headingId = heading.id || `heading-${index}`;
                heading.id = headingId;
                
                // Create TOC item
                const tocItem = document.createElement('li');
                tocItem.className = 'toc-item';
                
                const tocLink = document.createElement('a');
                tocLink.className = `toc-link toc-${heading.tagName.toLowerCase()}`;
                tocLink.href = `#${headingId}`;
                tocLink.textContent = heading.textContent;
                
                tocLink.addEventListener('click', function(e) {
                    e.preventDefault();
                    document.getElementById(headingId).scrollIntoView({ 
                        behavior: 'smooth' 
                    });
                });
                
                tocItem.appendChild(tocLink);
                tocList.appendChild(tocItem);
            });
            
            tocContainer.appendChild(tocList);
            document.body.appendChild(tocContainer);
            
            // Initially hide the TOC - will be toggled by button
            tocContainer.style.display = 'none';
        }
    } catch (e) {
        console.warn("Error creating table of contents:", e);
        // Non-critical error, so just log and continue
    }
}

// Start editing a letter
function startEdit(content, username, dateStr) {
    letterEditorEl.style.display = 'block';
    editorContentEl.value = content;
    
    // Scroll to editor
    letterEditorEl.scrollIntoView({ behavior: 'smooth' });
}

// Cancel editing
function cancelEdit() {
    letterEditorEl.style.display = 'none';
    editorContentEl.value = '';
    currentEditLetter = null;
}

// Save edited letter
function saveEdit() {
    if (!currentEditLetter) {
        showNotification('No letter to save', true);
        return;
    }
    
    const content = editorContentEl.value;
    const dateStr = currentEditLetter.dateStr;
    const username = currentEditLetter.username;
    const format = currentEditLetter.format || 'markdown';
    
    // Show saving notification
    showNotification('Saving letter...', false);
    
    fetch(`${API_BASE}/edit_letter`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            date_str: dateStr,
            username: username,
            content: content,
            format: format
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showNotification(data.error, true);
                return;
            }
            
            showNotification('Letter saved successfully');
            
            // Close editor
            letterEditorEl.style.display = 'none';
            
            // Reload letters to refresh the calendar
            loadLetters();
            
            // Wait a bit before reopening the letter
            setTimeout(() => {
                openLetter(dateStr, username, username === USERNAME);
            }, 500);
        })
        .catch(error => {
            console.error('Error saving letter:', error);
            showNotification('Failed to save letter: ' + error.message, true);
        });
}

// Generate a new letter
function generateLetter() {
    generateLetterBtn.disabled = true;
    generateLetterBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...';
    
    fetch(`${API_BASE}/generate_letter`, {
        method: 'POST'
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showNotification(data.error, true);
                return;
            }
            
            showNotification('Letter generation started. This may take a minute...');
            
            // Wait a bit and then reload letters
            setTimeout(() => {
                loadLetters();
                loadCommunityLetters();
            }, 5000);
        })
        .catch(error => {
            console.error('Error generating letter:', error);
            showNotification('Failed to generate letter: ' + error.message, true);
        })
        .finally(() => {
            generateLetterBtn.disabled = false;
            generateLetterBtn.innerHTML = '<i class="fas fa-pen-fancy"></i> Generate Today\'s Letter';
        });
}

// Sync letters
function syncLetters() {
    syncLettersBtn.disabled = true;
    syncLettersBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Syncing...';
    
    fetch(`${API_BASE}/sync_letters_now`, {
        method: 'POST'
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showNotification(data.error, true);
                return;
            }
            
            // Reload data
            loadLetters();
            loadCommunityLetters();
            
            showNotification(data.message || 'Letters synced successfully');
        })
        .catch(error => {
            console.error('Error syncing letters:', error);
            showNotification('Failed to sync letters: ' + error.message, true);
        })
        .finally(() => {
            syncLettersBtn.disabled = false;
            syncLettersBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Sync Letters';
        });
}

// Show notification
function showNotification(message, isError = false) {
    notificationEl.textContent = message;
    notificationEl.className = `notification ${isError ? 'error' : ''}`;
    
    // Trigger animation
    setTimeout(() => {
        notificationEl.classList.add('show');
    }, 10);
    
    // Hide after 3 seconds
    setTimeout(() => {
        notificationEl.classList.remove('show');
    }, 3000);
}
    </script>
</body>
</html>

```

## File: web\templates\settings.html

```html
<!-- web/templates/settings.html -->
<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nova Project - Settings</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            /* Theme variables will be set by JS */
            --primary-color: #0078D7;
            --secondary-color: #2AAA8A;
            --accent-color: #6A0DAD;
            --bg-color: #1E1E1E;
            --card-color: #252526;
            --text-color: #E1E1E1;
            --border-color: #444444;
            --hover-color: #2A2A2D;
            --success-color: #73C991;
            --warning-color: #DDB100;
            --danger-color: #F14C4C;
        }
        
        /* Dark theme */
        html[data-theme='dark'] {
            --primary-color: #4361ee;
            --secondary-color: #3ECF8E;
            --accent-color: #8A2BE2;
            --bg-color: #121212;
            --card-color: #1E1E1E;
            --text-color: #F5F5F5;
            --border-color: #333333;
            --hover-color: #252525;
            --success-color: #4CAF50;
            --warning-color: #FFC107;
            --danger-color: #F44336;
        }
        
        /* Light theme */
        html[data-theme='light'] {
            --primary-color: #1976D2;
            --secondary-color: #009688;
            --accent-color: #673AB7;
            --bg-color: #F5F5F5;
            --card-color: #FFFFFF;
            --text-color: #333333;
            --border-color: #E0E0E0;
            --hover-color: #EEEEEE;
            --success-color: #4CAF50;
            --warning-color: #FFC107;
            --danger-color: #F44336;
        }
        
        /* Custom theme */
        html[data-theme='custom'] {
            --primary-color: #FF5722;
            --secondary-color: #03A9F4;
            --accent-color: #9C27B0;
            --bg-color: #FFF8E1;
            --card-color: #FFFFFF;
            --text-color: #212121;
            --border-color: #BDBDBD;
            --hover-color: #F5F5F5;
            --success-color: #8BC34A;
            --warning-color: #FFEB3B;
            --danger-color: #FF5252;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 0;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 15px;
        }
        
        .brand {
            display: flex;
            align-items: center;
        }
        
        .brand h1 {
            margin: 0;
            color: var(--primary-color);
        }
        
        .brand-icon {
            margin-right: 15px;
            color: var(--primary-color);
            font-size: 2rem;
        }
        
        .nav-links a {
            color: var(--text-color);
            text-decoration: none;
            margin-left: 20px;
            padding: 8px 15px;
            border-radius: 4px;
            transition: background-color 0.2s ease;
        }
        
        .nav-links a:hover {
            background-color: var(--hover-color);
        }
        
        .nav-links a.active {
            background-color: var(--primary-color);
            color: white;
        }
        
        .settings-container {
            background-color: var(--card-color);
            border-radius: 8px;
            padding: 30px;
            max-width: 800px;
            margin: 0 auto;
        }
        
        .settings-header {
            margin-bottom: 30px;
            display: flex;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 15px;
        }
        
        .settings-header h2 {
            margin: 0;
            color: var(--primary-color);
        }
        
        .settings-header-icon {
            font-size: 1.8rem;
            margin-right: 15px;
            color: var(--primary-color);
        }
        
        .form-group {
            margin-bottom: 25px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
        }
        
        .form-group .help-text {
            display: block;
            margin-top: 5px;
            font-size: 0.85rem;
            color: var(--text-color);
            opacity: 0.7;
        }
        
        .form-control {
            width: 100%;
            padding: 10px;
            background-color: var(--bg-color);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            color: var(--text-color);
            font-family: inherit;
            font-size: 1rem;
        }
        
        .form-control:focus {
            outline: none;
            border-color: var(--primary-color);
        }
        
        .form-actions {
            display: flex;
            justify-content: space-between;
            margin-top: 40px;
        }
        
        .btn {
            background-color: var(--primary-color);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
            transition: background-color 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        
        .btn:hover {
            opacity: 0.9;
        }

        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .btn-success {
            background-color: var(--secondary-color);
        }
        
        .btn-accent {
            background-color: var(--accent-color);
        }
        
        .btn-warning {
            background-color: var(--warning-color);
        }
        
        .btn-danger {
            background-color: var(--danger-color);
        }
        
        .folder-browser {
            display: flex;
            gap: 10px;
        }
        
        .folder-browser input {
            flex-grow: 1;
        }
        
        .switch {
            position: relative;
            display: inline-block;
            width: 60px;
            height: 34px;
        }
        
        .switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #ccc;
            transition: .4s;
            border-radius: 34px;
        }
        
        .slider:before {
            position: absolute;
            content: "";
            height: 26px;
            width: 26px;
            left: 4px;
            bottom: 4px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        }
        
        input:checked + .slider {
            background-color: var(--secondary-color);
        }
        
        input:focus + .slider {
            box-shadow: 0 0 1px var(--secondary-color);
        }
        
        input:checked + .slider:before {
            transform: translateX(26px);
        }
        
        .toggle-container {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .toggle-label {
            font-weight: bold;
        }

        .notification {
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 4px;
            background-color: var(--success-color);
            color: white;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
            z-index: 1000;
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s ease;
        }

        .notification.show {
            transform: translateY(0);
            opacity: 1;
        }

        .notification.error {
            background-color: var(--danger-color);
        }
        
        .section-header {
            margin-top: 40px;
            margin-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
            color: var(--primary-color);
        }

        .note {
            padding: 10px;
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
            margin-top: 5px;
            font-size: 0.9rem;
            color: #FFA500;
        }
        
        /* Theme switcher */
        .theme-switcher {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .theme-option {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            cursor: pointer;
            border: 2px solid transparent;
            position: relative;
        }
        
        .theme-option.active {
            border-color: var(--primary-color);
            transform: scale(1.1);
        }
        
        .theme-light {
            background: linear-gradient(135deg, #f5f5f5 50%, #e0e0e0 50%);
        }
        
        .theme-dark {
            background: linear-gradient(135deg, #333333 50%, #121212 50%);
        }
        
        .theme-custom {
            background: linear-gradient(135deg, #FF5722 50%, #FFF8E1 50%);
        }
        
        /* Icon selector */
        .icon-selector {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin-top: 10px;
        }
        
        .icon-option {
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 8px;
            background-color: var(--bg-color);
            border: 1px solid var(--border-color);
            color: var(--primary-color);
            cursor: pointer;
            font-size: 1.2rem;
            transition: all 0.2s ease;
        }
        
        .icon-option:hover {
            background-color: var(--primary-color);
            color: white;
        }
        
        .icon-option.active {
            background-color: var(--primary-color);
            color: white;
            transform: scale(1.1);
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
        }
        
        /* New: Settings tabs */
        .settings-tabs {
            display: flex;
            margin-bottom: 25px;
            border-bottom: 1px solid var(--border-color);
        }
        
        .settings-tab {
            padding: 10px 20px;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            transition: all 0.2s ease;
        }
        
        .settings-tab.active {
            border-bottom-color: var(--primary-color);
            color: var(--primary-color);
            font-weight: bold;
        }
        
        .settings-tab:hover {
            background-color: var(--hover-color);
        }
        
        .settings-pane {
            display: none;
        }
        
        .settings-pane.active {
            display: block;
        }
        
        /* For range inputs */
        .range-container {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .range-value {
            min-width: 60px;
            text-align: center;
            font-weight: bold;
        }
        
        input[type="range"] {
            flex-grow: 1;
            -webkit-appearance: none;
            height: 8px;
            background: var(--border-color);
            border-radius: 4px;
            outline: none;
        }
        
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: var(--primary-color);
            cursor: pointer;
        }
        
        /* Dropdown styling */
        .select-wrapper {
            position: relative;
        }
        
        .select-wrapper::after {
            content: "▼";
            font-size: 0.8rem;
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            pointer-events: none;
        }
        
        select {
            appearance: none;
            width: 100%;
            padding: 10px;
            background-color: var(--bg-color);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            color: var(--text-color);
            font-family: inherit;
            font-size: 1rem;
            cursor: pointer;
        }
        
        select:focus {
            outline: none;
            border-color: var(--primary-color);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="brand">
                <div class="brand-icon">
                    <i class="fas fa-lightbulb"></i>
                </div>
                <h1>Nova Project</h1>
            </div>
            <div class="nav-links">
                <a href="/"><i class="fas fa-calendar-alt"></i> Calendar</a>
                <a href="/settings" class="active"><i class="fas fa-cog"></i> Settings</a>
            </div>
        </header>
        
        <div class="settings-container">
            <div class="settings-header">
                <div class="settings-header-icon">
                    <i class="fas fa-cog"></i>
                </div>
                <h2>Settings</h2>
            </div>
            
            <!-- Theme Switcher -->
            <div class="theme-switcher">
                <span>App Theme:</span>
                <div class="theme-option theme-light" data-theme="light" title="Light Theme"></div>
                <div class="theme-option theme-dark" data-theme="dark" title="Dark Theme"></div>
                <div class="theme-option theme-custom" data-theme="custom" title="Custom Theme"></div>
            </div>
            
            <!-- Tabs for organizing settings -->
            <div class="settings-tabs">
                <div class="settings-tab active" data-tab="general">General</div>
                <div class="settings-tab" data-tab="capture">Screenshot & Analysis</div>
                <div class="settings-tab" data-tab="letters">Letter Generation</div>
                <div class="settings-tab" data-tab="models">AI Models</div>
                <div class="settings-tab" data-tab="sync">Sync & Sharing</div>
            </div>
            
            <form id="settings-form">
                <!-- General Settings Pane -->
                <div class="settings-pane active" id="general-pane">
                    <!-- Icon Selector -->
                    <div class="form-group">
                        <label for="app-icon">App Icon</label>
                        <div class="icon-selector">
                            <div class="icon-option" data-icon="lightbulb"><i class="fas fa-lightbulb"></i></div>
                            <div class="icon-option" data-icon="magic"><i class="fas fa-magic"></i></div>
                            <div class="icon-option" data-icon="star"><i class="fas fa-star"></i></div>
                            <div class="icon-option" data-icon="compass"><i class="fas fa-compass"></i></div>
                            <div class="icon-option" data-icon="rocket"><i class="fas fa-rocket"></i></div>
                        </div>
                        <span class="help-text">Choose an icon for the Nova Project app.</span>
                    </div>
                    
                    <div class="form-group">
                        <label for="username">Username</label>
                        <input type="text" id="username" class="form-control" placeholder="Your name" value="{{ config.username }}">
                        <span class="help-text">This name will be displayed to others when you share your letters.</span>
                    </div>
                    
                    <div class="form-group">
                        <div class="toggle-container">
                            <span class="toggle-label">Auto-launch at startup</span>
                            <label class="switch">
                                <input type="checkbox" id="auto-launch" {% if config.auto_launch %}checked{% endif %}>
                                <span class="slider"></span>
                            </label>
                        </div>
                        <span class="help-text">Start Nova Project automatically when you log in to your computer.</span>
                    </div>
                    
                    <div class="form-group">
                        <label for="local-folder">Data Storage Folder</label>
                        <div class="folder-browser">
                            <input type="text" id="local-folder" class="form-control" placeholder="Path to your data storage folder" value="{{ config.local_folder }}">
                        </div>
                        <span class="help-text">This is the parent folder where all data (letters, screenshots, key points) will be stored. Subfolders will be created automatically for each data type.</span>
                    </div>
                </div>
                
                <!-- Screenshot & Analysis Settings Pane -->
                <div class="settings-pane" id="capture-pane">
                    <div class="form-group">
                        <label for="screenshot-interval">Screenshot Interval (seconds)</label>
                        <div class="range-container">
                            <input type="range" id="screenshot-interval" min="30" max="600" step="30" value="{{ config.screenshot_interval or 120 }}">
                            <span class="range-value" id="screenshot-interval-value">{{ config.screenshot_interval or 120 }}s</span>
                        </div>
                        <span class="help-text">How often screenshots are taken to capture your learning (in seconds).</span>
                    </div>
                    
                    <div class="form-group">
                        <label for="keypoints-threshold">Key Points Extraction Threshold</label>
                        <div class="range-container">
                            <input type="range" id="keypoints-threshold" min="5" max="100" step="5" value="{{ config.keypoints_threshold or 30 }}">
                            <span class="range-value" id="keypoints-threshold-value">{{ config.keypoints_threshold or 30 }} screenshots</span>
                        </div>
                        <span class="help-text">Number of screenshots needed before extracting key points.</span>
                    </div>
                    
                    <div class="form-group">
                        <label for="screenshot-retention">Screenshot Retention Period (days)</label>
                        <div class="range-container">
                            <input type="range" id="screenshot-retention" min="1" max="90" step="1" value="{{ config.screenshot_retention_days or 7 }}">
                            <span class="range-value" id="screenshot-retention-value">{{ config.screenshot_retention_days or 7 }} days</span>
                        </div>
                        <span class="help-text">How long to keep screenshot files (0 means keep indefinitely).</span>
                    </div>
                </div>
                
                <!-- Letter Generation Settings Pane -->
                <div class="settings-pane" id="letters-pane">
                    <div class="form-group">
                        <label for="letter-generation-time">Daily Letter Generation Time</label>
                        <input type="time" id="letter-generation-time" class="form-control" value="{{ config.letter_generation_time or '21:00' }}">
                        <span class="help-text">When Nova will automatically generate the daily summary letter.</span>
                    </div>
                    
                    <div class="form-group">
                        <label for="letter-style">Letter Style Customization</label>
                        <textarea id="letter-style" class="form-control" placeholder="Define custom style for your letters" rows="5">{{ config.letter_style }}</textarea>
                        <span class="help-text">Define custom styles for your letters (e.g., 'concise', 'technical', 'educational', etc.). This will be used for letter generation.</span>
                    </div>
                    
                    <div class="form-group">
                        <label for="letter-language">Letter Language</label>
                        <input type="text" id="letter-language" class="form-control" placeholder="e.g., English, Spanish, Chinese" value="{{ config.letter_language }}">
                        <span class="help-text">Specify the language for your letters. Leave empty for default (English).</span>
                    </div>
                </div>
                
                <!-- AI Models Settings Pane -->
                <div class="settings-pane" id="models-pane">
                    <div class="form-group">
                        <label for="screenshot-model">Screenshot Text Extraction Model</label>
                        <div class="select-wrapper">
                            <select id="screenshot-model" class="form-control">
                                <option value="google/gemma-3-27b-it" {% if config.screenshot_model == 'google/gemma-3-27b-it' %}selected{% endif %}>Gemma 3 (27B)</option>
                                <option value="openai/gpt-4o" {% if config.screenshot_model == 'openai/gpt-4o' %}selected{% endif %}>GPT-4o</option>
                                <option value="openai/gpt-4o-mini" {% if config.screenshot_model == 'openai/gpt-4o-mini' %}selected{% endif %}>GPT-4o Mini</option>
                                <option value="anthropic/claude-3-7-sonnet" {% if config.screenshot_model == 'anthropic/claude-3-7-sonnet' %}selected{% endif %}>Claude 3.7 Sonnet</option>
                            </select>
                        </div>
                        <span class="help-text">AI model used to extract text from screenshots.</span>
                    </div>
                    
                    <div class="form-group">
                        <label for="keypoints-model">Key Points Extraction Model</label>
                        <div class="select-wrapper">
                            <select id="keypoints-model" class="form-control">
                                <option value="openai/o3-mini" {% if config.keypoints_model == 'openai/o3-mini' %}selected{% endif %}>OpenAI O3 Mini</option>
                                <option value="google/gemma-3-27b-it" {% if config.keypoints_model == 'google/gemma-3-27b-it' %}selected{% endif %}>Gemma 3 (27B)</option>
                                <option value="openai/gpt-4o" {% if config.keypoints_model == 'openai/gpt-4o' %}selected{% endif %}>GPT-4o</option>
                                <option value="openai/gpt-4o-mini" {% if config.keypoints_model == 'openai/gpt-4o-mini' %}selected{% endif %}>GPT-4o Mini</option>
                                <option value="anthropic/claude-3-7-sonnet" {% if config.keypoints_model == 'anthropic/claude-3-7-sonnet' %}selected{% endif %}>Claude 3.7 Sonnet</option>
                                <option value="deepseek/deepseek-r1" {% if config.keypoints_model == 'deepseek/deepseek-r1' %}selected{% endif %}>Deepseek R1</option>
                            </select>
                        </div>
                        <span class="help-text">AI model used to extract key points from your screenshots.</span>
                    </div>
                    
                    <div class="form-group">
                        <label for="letter-model">Letter Generation Model</label>
                        <div class="select-wrapper">
                            <select id="letter-model" class="form-control">
                                <option value="anthropic/claude-3-7-sonnet" {% if config.letter_model == 'anthropic/claude-3-7-sonnet' %}selected{% endif %}>Claude 3.7 Sonnet</option>
                                <option value="openai/o3-mini" {% if config.letter_model == 'openai/o3-mini' %}selected{% endif %}>OpenAI O3 Mini</option>
                                <option value="openai/gpt-4o" {% if config.letter_model == 'openai/gpt-4o' %}selected{% endif %}>GPT-4o</option>
                                <option value="openai/gpt-4o-mini" {% if config.letter_model == 'openai/gpt-4o-mini' %}selected{% endif %}>GPT-4o Mini</option>
                                <option value="google/gemma-3-27b-it" {% if config.letter_model == 'google/gemma-3-27b-it' %}selected{% endif %}>Gemma 3 (27B)</option>
                                <option value="deepseek/deepseek-r1" {% if config.letter_model == 'deepseek/deepseek-r1' %}selected{% endif %}>Deepseek R1</option>
                            </select>
                        </div>
                        <span class="help-text">AI model used to generate your learning summary letters.</span>
                    </div>
                    
                    <div class="form-group">
                        <label for="openrouter-api-key">OpenRouter API Key</label>
                        <input type="password" id="openrouter-api-key" class="form-control" placeholder="Enter your OpenRouter API key" value="{{ config.openrouter_api_key }}">
                        <span class="help-text">Required for letter generation and screenshots processing. <a href="https://openrouter.ai/keys" target="_blank" style="color: var(--secondary-color);">Get an API key</a></span>
                    </div>
                </div>
                
                <!-- Sync & Sharing Settings Pane -->
                <div class="settings-pane" id="sync-pane">
                    <div class="form-group">
                        <div class="toggle-container">
                            <span class="toggle-label">Auto-sync letters</span>
                            <label class="switch">
                                <input type="checkbox" id="auto-sync" {% if config.auto_sync %}checked{% endif %}>
                                <span class="slider"></span>
                            </label>
                        </div>
                        <span class="help-text">When enabled, your letters will be automatically shared with others when they are generated.</span>
                    </div>
                    
                    <div class="form-group">
                        <label for="shared-folder">Shared Folder Path</label>
                        <div class="folder-browser">
                            <input type="text" id="shared-folder" class="form-control" placeholder="Path to your shared folder" value="{{ config.shared_folder }}">
                        </div>
                        <span class="help-text">This should be a folder where everyone can access (e.g., a OneDrive shared folder).</span>
                        <div class="note">
                            <i class="fas fa-info-circle"></i> Folder selection requires the Nova desktop app. Enter the path manually or use the desktop UI to select folders.
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label for="sync-frequency">Sync Frequency (minutes)</label>
                        <div class="range-container">
                            <input type="range" id="sync-frequency" min="5" max="120" step="5" value="{{ config.sync_frequency_minutes or 15 }}">
                            <span class="range-value" id="sync-frequency-value">{{ config.sync_frequency_minutes or 15 }} minutes</span>
                        </div>
                        <span class="help-text">How often to check for changes in the shared folder.</span>
                    </div>
                </div>
                
                <div class="form-actions">
                    <button type="button" id="reset-btn" class="btn btn-warning">
                        <i class="fas fa-undo"></i> Reset
                    </button>
                    <button type="submit" class="btn btn-success">
                        <i class="fas fa-save"></i> Save Settings
                    </button>
                </div>
            </form>
        </div>
    </div>
    
    <div id="notification" class="notification">
        <!-- Notification message will be shown here -->
    </div>
    
    <script>
        const PORT = "{{ port }}";
        const API_BASE = `http://localhost:${PORT}/api`;
        
        // DOM elements
        const settingsForm = document.getElementById('settings-form');
        const usernameInput = document.getElementById('username');
        const autoSyncToggle = document.getElementById('auto-sync');
        const autoLaunchToggle = document.getElementById('auto-launch');
        const sharedFolderInput = document.getElementById('shared-folder');
        const localFolderInput = document.getElementById('local-folder');
        const letterStyleInput = document.getElementById('letter-style');
        const letterLanguageInput = document.getElementById('letter-language');
        const openrouterApiKeyInput = document.getElementById('openrouter-api-key');
        const resetBtn = document.getElementById('reset-btn');
        const notificationEl = document.getElementById('notification');
        const themeOptions = document.querySelectorAll('.theme-option');
        const iconOptions = document.querySelectorAll('.icon-option');
        const settingsTabs = document.querySelectorAll('.settings-tab');
        const settingsPanes = document.querySelectorAll('.settings-pane');
        
        // New settings elements
        const screenshotIntervalInput = document.getElementById('screenshot-interval');
        const screenshotIntervalValue = document.getElementById('screenshot-interval-value');
        const keypointsThresholdInput = document.getElementById('keypoints-threshold');
        const keypointsThresholdValue = document.getElementById('keypoints-threshold-value');
        const screenshotRetentionInput = document.getElementById('screenshot-retention');
        const screenshotRetentionValue = document.getElementById('screenshot-retention-value');
        const letterGenerationTimeInput = document.getElementById('letter-generation-time');
        const syncFrequencyInput = document.getElementById('sync-frequency');
        const syncFrequencyValue = document.getElementById('sync-frequency-value');
        const screenshotModelSelect = document.getElementById('screenshot-model');
        const keypointsModelSelect = document.getElementById('keypoints-model');
        const letterModelSelect = document.getElementById('letter-model');
        
        // Original values for reset
        const originalValues = {
            username: "{{ config.username }}",
            autoSync: {{ 'true' if config.auto_sync else 'false' }},
            autoLaunch: {{ 'true' if config.auto_launch else 'false' }},
            sharedFolder: "{{ config.shared_folder }}",
            localFolder: "{{ config.local_folder }}",
            letterStyle: "{{ config.letter_style }}",
            letterLanguage: "{{ config.letter_language }}",
            openrouterApiKey: "{{ config.openrouter_api_key }}",
            appIcon: "{{ config.app_icon or 'lightbulb' }}",
            screenshotInterval: {{ config.screenshot_interval or 120 }},
            keypointsThreshold: {{ config.keypoints_threshold or 30 }},
            screenshotRetention: {{ config.screenshot_retention_days or 7 }},
            letterGenerationTime: "{{ config.letter_generation_time or '21:00' }}",
            syncFrequency: {{ config.sync_frequency_minutes or 15 }},
            screenshotModel: "{{ config.screenshot_model or 'google/gemma-3-27b-it' }}",
            keypointsModel: "{{ config.keypoints_model or 'openai/o3-mini' }}",
            letterModel: "{{ config.letter_model or 'anthropic/claude-3-7-sonnet' }}"
        };
        
        // Event listeners
        document.addEventListener('DOMContentLoaded', () => {
            settingsForm.addEventListener('submit', saveSettings);
            resetBtn.addEventListener('click', resetForm);
            
            // Initialize theme
            initTheme();
            
            // Initialize icon
            initIcon();
            
            // Theme switcher
            themeOptions.forEach(option => {
                option.addEventListener('click', () => {
                    const theme = option.getAttribute('data-theme');
                    setTheme(theme);
                });
            });
            
            // Icon selector
            iconOptions.forEach(option => {
                option.addEventListener('click', () => {
                    const icon = option.getAttribute('data-icon');
                    setIcon(icon);
                });
            });
            
            // Settings tabs
            settingsTabs.forEach(tab => {
                tab.addEventListener('click', () => {
                    const tabId = tab.getAttribute('data-tab');
                    setActiveTab(tabId);
                });
            });
            
            // Range input updates
            screenshotIntervalInput.addEventListener('input', () => {
                screenshotIntervalValue.textContent = `${screenshotIntervalInput.value}s`;
            });
            
            keypointsThresholdInput.addEventListener('input', () => {
                keypointsThresholdValue.textContent = `${keypointsThresholdInput.value} screenshots`;
            });
            
            screenshotRetentionInput.addEventListener('input', () => {
                screenshotRetentionValue.textContent = `${screenshotRetentionInput.value} days`;
            });
            
            syncFrequencyInput.addEventListener('input', () => {
                syncFrequencyValue.textContent = `${syncFrequencyInput.value} minutes`;
            });
        });
        
        // Set active tab
        function setActiveTab(tabId) {
            // Update tabs
            settingsTabs.forEach(tab => {
                if (tab.getAttribute('data-tab') === tabId) {
                    tab.classList.add('active');
                } else {
                    tab.classList.remove('active');
                }
            });
            
            // Update panes
            settingsPanes.forEach(pane => {
                if (pane.id === `${tabId}-pane`) {
                    pane.classList.add('active');
                } else {
                    pane.classList.remove('active');
                }
            });
        }
        
        // Initialize theme
        function initTheme() {
            const savedTheme = localStorage.getItem('nova-theme') || 'light';
            setTheme(savedTheme);
        }
        
        // Set theme
        function setTheme(theme) {
            document.documentElement.setAttribute('data-theme', theme);
            localStorage.setItem('nova-theme', theme);
            
            // Update theme option active state
            themeOptions.forEach(option => {
                if (option.getAttribute('data-theme') === theme) {
                    option.classList.add('active');
                } else {
                    option.classList.remove('active');
                }
            });
        }
        
        // Initialize icon
        function initIcon() {
            const savedIcon = localStorage.getItem('nova-icon') || originalValues.appIcon || 'lightbulb';
            setIcon(savedIcon);
        }
        
        // Set icon
        function setIcon(icon) {
            localStorage.setItem('nova-icon', icon);
            
            // Update icon option active state
            iconOptions.forEach(option => {
                if (option.getAttribute('data-icon') === icon) {
                    option.classList.add('active');
                } else {
                    option.classList.remove('active');
                }
            });
            
            // Update header icon
            const brandIcon = document.querySelector('.brand-icon i');
            brandIcon.className = ''; // Clear classes
            brandIcon.classList.add('fas', `fa-${icon}`);
        }

        // Save settings
        function saveSettings(event) {
            event.preventDefault();
            
            const data = {
                username: usernameInput.value.trim(),
                auto_sync: autoSyncToggle.checked,
                auto_launch: autoLaunchToggle.checked,
                shared_folder: sharedFolderInput.value.trim(),
                local_folder: localFolderInput.value.trim(),
                letter_style: letterStyleInput.value.trim(),
                letter_language: letterLanguageInput.value.trim(),
                openrouter_api_key: openrouterApiKeyInput.value.trim(),
                app_icon: localStorage.getItem('nova-icon') || 'lightbulb',
                screenshot_interval: parseInt(screenshotIntervalInput.value),
                keypoints_threshold: parseInt(keypointsThresholdInput.value),
                screenshot_retention_days: parseInt(screenshotRetentionInput.value),
                letter_generation_time: letterGenerationTimeInput.value,
                sync_frequency_minutes: parseInt(syncFrequencyInput.value),
                screenshot_model: screenshotModelSelect.value,
                keypoints_model: keypointsModelSelect.value,
                letter_model: letterModelSelect.value
            };
            
            fetch(`${API_BASE}/settings`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            })
                .then(response => response.json())
                .then(result => {
                    if (result.error) {
                        showNotification(result.error, true);
                        return;
                    }
                    
                    showNotification('Settings saved successfully');
                    
                    // Update original values
                    Object.assign(originalValues, {
                        username: data.username,
                        autoSync: data.auto_sync,
                        autoLaunch: data.auto_launch,
                        sharedFolder: data.shared_folder,
                        localFolder: data.local_folder,
                        letterStyle: data.letter_style,
                        letterLanguage: data.letter_language,
                        openrouterApiKey: data.openrouter_api_key,
                        appIcon: data.app_icon,
                        screenshotInterval: data.screenshot_interval,
                        keypointsThreshold: data.keypoints_threshold,
                        screenshotRetention: data.screenshot_retention_days,
                        letterGenerationTime: data.letter_generation_time,
                        syncFrequency: data.sync_frequency_minutes,
                        screenshotModel: data.screenshot_model,
                        keypointsModel: data.keypoints_model,
                        letterModel: data.letter_model
                    });
                })
                .catch(error => {
                    console.error('Error saving settings:', error);
                    showNotification('Failed to save settings', true);
                });
        }
        
        // Reset form to original values
        function resetForm() {
            usernameInput.value = originalValues.username;
            autoSyncToggle.checked = originalValues.autoSync === true;
            autoLaunchToggle.checked = originalValues.autoLaunch === true;
            sharedFolderInput.value = originalValues.sharedFolder;
            localFolderInput.value = originalValues.localFolder;
            letterStyleInput.value = originalValues.letterStyle;
            letterLanguageInput.value = originalValues.letterLanguage;
            openrouterApiKeyInput.value = originalValues.openrouterApiKey;
            
            // Reset new input values
            screenshotIntervalInput.value = originalValues.screenshotInterval;
            screenshotIntervalValue.textContent = `${originalValues.screenshotInterval}s`;
            
            keypointsThresholdInput.value = originalValues.keypointsThreshold;
            keypointsThresholdValue.textContent = `${originalValues.keypointsThreshold} screenshots`;
            
            screenshotRetentionInput.value = originalValues.screenshotRetention;
            screenshotRetentionValue.textContent = `${originalValues.screenshotRetention} days`;
            
            letterGenerationTimeInput.value = originalValues.letterGenerationTime;
            
            syncFrequencyInput.value = originalValues.syncFrequency;
            syncFrequencyValue.textContent = `${originalValues.syncFrequency} minutes`;
            
            screenshotModelSelect.value = originalValues.screenshotModel;
            keypointsModelSelect.value = originalValues.keypointsModel;
            letterModelSelect.value = originalValues.letterModel;
            
            // Reset icon
            setIcon(originalValues.appIcon);
            
            showNotification('Form reset to saved values');
        }
        
        // Show notification
        function showNotification(message, isError = false) {
            notificationEl.textContent = message;
            notificationEl.className = `notification ${isError ? 'error' : ''}`;
            
            // Trigger animation
            setTimeout(() => {
                notificationEl.classList.add('show');
            }, 10);
            
            // Hide after 3 seconds
            setTimeout(() => {
                notificationEl.classList.remove('show');
            }, 3000);
        }
    </script>
</body>
</html>

```
