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
