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
        
        # Check if extraction is already in progress
        if hasattr(self.key_points_extractor, '_extraction_in_progress') and self.key_points_extractor._extraction_in_progress:
            # Log status but don't start another extraction
            if hasattr(self.key_points_extractor, '_extraction_start_time') and self.key_points_extractor._extraction_start_time:
                elapsed_time = time.time() - self.key_points_extractor._extraction_start_time
                if elapsed_time > 60:  # Only log if it's been running for more than a minute
                    print(f"Key points extraction already in progress for {elapsed_time:.1f} seconds")
            return
        
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
