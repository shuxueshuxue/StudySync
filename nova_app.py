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
