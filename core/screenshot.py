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
        self.api_base = "https://openrouterai.aidb.site/api/v1"
        
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
