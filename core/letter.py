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
        self.api_base = "https://openrouterai.aidb.site/api/v1"
        
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
                system_prompt = "You are Nova, the user's personal secretary. "
                
                # Add language instruction if specified
                if letter_language and letter_language.lower() != "english":
                    system_prompt += f"You write daily work recaps in {letter_language}. "
                else:
                    system_prompt += "You write daily work recaps in English. "
                
                # Add style instruction if specified
                if letter_style:
                    system_prompt += f"Your writing style should be {letter_style}. "
                else:
                    system_prompt += "Focus on knowledge and insights."
                
                # Create letter template once to avoid duplication
                letter_template = f"""
As the user's personal secretary, create a comprehensive, inspirational letter for him/her about today's work.
Today is {today_formatted}.

STRUCTURE AND CONTENT REQUIREMENTS:
1. FORMAT:
   - First line: Add tags as "tags: tag1, tag2, tag3, tag4, tag5" (extract 5 relevant tags from the content)
   - Second line: Add a title as "# Title"
   - Use proper markdown formatting throughout (headings, lists, code blocks, math expressions)
   - Minimum length: 2000+ words

2. INTRODUCTION:
   - Begin with a warm greeting
   - Provide a brief overview of today's focus
   - Include a thought-provoking quote or insight related to the topic

3. CORE CONCEPTS:
   - Identify 5-7 fundamental concepts / knowledge details related to the user's recent learning
   - For each concept:
      * Provide a clear definition
      * Include an illustrative example or analogy
   - Balance technical accuracy with self-containability
   - Include at least one (could be more) diagram description or visual concept

4. PRACTICAL EXERCISES:
   - Include 3-4 diverse exercises that challenge different aspects of understanding
   - For each exercise:
      * Clearly state the objective
      * Provide necessary context and parameters
      * Include a detailed, step-by-step solution with explanations
      * Add reflection questions after the solution

5. HISTORICAL CONTEXT & REAL APPLICATION:
   - Share the life story of a key figure/company/association that created this knowledge
   - OR
   - Detail a classic real-world application where a specific person used these concepts to solve a concrete problem
   - Include specific names, dates, challenges faced, and outcomes achieved

6. CONCLUSION:
   - Summarize key takeaways
   - Provide an intellectually motivating closing message
   - Suggest 1-2 specific resources for further exploration
   - End with a warm, professional sign-off

IMPORTANT GUIDELINES:
- Feel free to use sophisticated HTML elements within the markdown for better illustrations and visual effects (tables, callouts, etc.)
- Balance self-contained educational content with personalization
- Ensure 50% of content is universally valuable even without context of user's specific learning
- Don't repeat content from previous letters (or instead you can try to extend them): {previous_letters_summary}
- This is the user's learning today: {' '.join([kp["content"] for kp in key_points])}

THE MOST IMPORTANT: Return the letter in MARKDOWN format!
Do not wrap the content in a markdown code block.
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
                web_url = f'http://localhost:11000/#letter/{date_str}'
                try:
                    print(f"Opening letter in web browser: {web_url}")
                    webbrowser.open(web_url)
                except Exception as e:
                    print(f"Error opening letter in browser: {e}")
            else:
                # Just display the URL without opening
                print(f"Letter can be viewed through the web UI at http://localhost:11000/#letter/{date_str}")
            
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

