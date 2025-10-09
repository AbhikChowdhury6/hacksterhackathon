# Muse Car Controller
# Controls robot car using Muse headband head tilt gestures
# - Head tilt for directional control

from pythonosc import dispatcher, osc_server
import time
import threading
from cammandsForCar import RobotCar

class MuseCarController:
    def __init__(self, car_host="172.22.111.167"):
        self.car = RobotCar(host=car_host)
        self.light_on = False
        
        # Gesture detection variables
        self.last_gesture_time = 0
        self.gesture_cooldown = 0.5  # minimum time between gestures (increased for stability)
        
        # Command management for robust control
        self.current_car_direction = "neutral"  # What the car is currently doing
        self.last_sent_command = "neutral"     # Last command actually sent to car
        self.command_history = []              # Track recent commands for stability
        self.max_history = 5                   # Keep last 5 commands
        self.command_in_progress = False       # Prevent multiple simultaneous commands
        
        # Rate limiting - targeting 4 requests per second (0.25s intervals)
        self.last_car_time = time.time()  # Initialize with current time
        self.min_command_interval = 0.25       # 4 commands per second
        self.neutral_interval = 0.5            # 2 neutral commands per second
        
        # Direction confidence tracking
        self.direction_confidence = 0
        self.confidence_threshold = 60         # Need 60 consecutive readings to change direction (very stable)
        self.current_detected_direction = "neutral"
        
        # Head tilt thresholds (tuned based on your actual data)
        self.neutral_x_range = (-0.35, -0.15)  # x around -0.24 for neutral
        self.neutral_y_range = (0.05, 0.25)    # y around 0.12 for neutral  
        self.neutral_z_range = (0.90, 1.00)    # z around 0.97 for neutral
        
        # Directional thresholds (more sensitive, left/right fixed)
        self.forward_x_min = 0.0       # x increases for forward (more sensitive)
        self.back_x_max = -0.6         # x goes negative for back (more sensitive)
        self.back_z_max = 0.7          # z decreases for back (more sensitive)
        self.left_y_max = 0.1          # y goes negative for left (even more sensitive)
        self.left_z_max = 0.98         # z decreases for left (very sensitive)
        self.right_y_min = 0.2         # y increases for right (much more sensitive)
        self.right_z_max = 0.95        # z decreases for right (more sensitive)
        
        # Current state tracking
        self.current_direction = "neutral"
        self.last_acc_data = None
        
        print(f"Initialized Muse Car Controller")
        print(f"Car host: {car_host}")
        print("Controls:")
        print("- Head tilt for direction:")
        print("  * Neutral: x high, y mid, z low")
        print("  * Forward: x lower, y and z like neutral")
        print("  * Back: x higher, z a bit higher too")
        print("  * Left: y goes up, z a bit higher too")
        print("  * Right: y goes down, z a bit higher too")
        print("\nFiltering Settings:")
        print(f"- Confidence threshold: {self.confidence_threshold} consecutive readings (extremely stable)")
        print(f"- Command rate: {1/self.min_command_interval:.1f} commands/sec (neutral: {1/self.neutral_interval:.1f}/sec)")
        print(f"- Command history: {self.max_history} commands")
        print("- This means you need to hold a head position for 60+ readings before the car responds")
        print("- At ~50 readings/sec, this requires holding position for 1.2+ seconds")
        print(f"- TARGETING: {1/self.min_command_interval:.1f} requests per second maximum")
        print("\nCurrent thresholds:")
        self.print_thresholds()

    def print_thresholds(self):
        """Print current threshold values for tuning"""
        print(f"  Neutral: x∈{self.neutral_x_range} y∈{self.neutral_y_range} z∈{self.neutral_z_range}")
        print(f"  Forward: x>={self.forward_x_min}")
        print(f"  Back: x<={self.back_x_max} z<={self.back_z_max}")
        print(f"  Left: y<={self.left_y_max} z<={self.left_z_max}")
        print(f"  Right: y>={self.right_y_min} z<={self.right_z_max}")

    def update_thresholds(self, **kwargs):
        """Update threshold values for tuning"""
        if 'neutral_x' in kwargs:
            self.neutral_x_range = kwargs['neutral_x']
        if 'neutral_y' in kwargs:
            self.neutral_y_range = kwargs['neutral_y']
        if 'neutral_z' in kwargs:
            self.neutral_z_range = kwargs['neutral_z']
        if 'forward_x' in kwargs:
            self.forward_x_max = kwargs['forward_x']
        if 'back_x' in kwargs:
            self.back_x_min = kwargs['back_x']
        if 'back_z' in kwargs:
            self.back_z_min = kwargs['back_z']
        if 'left_y' in kwargs:
            self.left_y_min = kwargs['left_y']
        if 'left_z' in kwargs:
            self.left_z_min = kwargs['left_z']
        if 'right_y' in kwargs:
            self.right_y_max = kwargs['right_y']
        if 'right_z' in kwargs:
            self.right_z_min = kwargs['right_z']
        
        print("Updated thresholds:")
        self.print_thresholds()

    def update_filtering(self, confidence_threshold=None, min_command_interval=None, neutral_interval=None, max_history=None):
        """Update filtering parameters for more/less aggressive filtering"""
        if confidence_threshold is not None:
            self.confidence_threshold = confidence_threshold
            print(f"Confidence threshold: {self.confidence_threshold}")
        if min_command_interval is not None:
            self.min_command_interval = min_command_interval
            print(f"Min command interval: {self.min_command_interval}s")
        if neutral_interval is not None:
            self.neutral_interval = neutral_interval
            print(f"Neutral interval: {self.neutral_interval}s")
        if max_history is not None:
            self.max_history = max_history
            print(f"Max command history: {self.max_history}")
        
        print("Filtering parameters updated!")
    
    def get_status(self):
        """Get current controller status for debugging"""
        return {
            'current_direction': self.current_detected_direction,
            'confidence': self.direction_confidence,
            'last_sent_command': self.last_sent_command,
            'command_history': self.command_history[-3:] if self.command_history else [],
            'time_since_last_command': time.time() - self.last_car_time if hasattr(self, 'last_car_time') else 0
        }

    def eeg_handler(self, address, *vals):
        """Handle EEG data - currently disabled for stability"""
        # Blink detection disabled due to noise issues
        pass

    def acc_handler(self, address, x, y, z):
        """Robust accelerometer handler with intelligent command management"""
        current_time = time.time()
        
        # Initialize timing variables and counters
        if not hasattr(self, 'last_print_time'):
            self.last_print_time = current_time
            self.acc_call_count = 0
            self.command_sent_count = 0
            self.last_debug_time = current_time
        
        # Count accelerometer calls for debugging
        self.acc_call_count += 1
        
        # Detect direction from current reading
        detected_direction = self.detect_head_tilt(float(x), float(y), float(z))
        
        # Update confidence tracking
        if detected_direction == self.current_detected_direction:
            self.direction_confidence += 1
        else:
            self.direction_confidence = 1
            self.current_detected_direction = detected_direction
        
        # Detailed debug info every 2 seconds
        if current_time - self.last_debug_time >= 2.0:
            timestamp = time.strftime("%H:%M:%S")
            time_diff = current_time - self.last_debug_time
            calls_per_sec = self.acc_call_count / time_diff if time_diff > 0 else 0
            time_since_last = current_time - self.last_car_time if hasattr(self, 'last_car_time') and self.last_car_time > 0 else 0
            print(f"[{timestamp}] DEBUG: {self.acc_call_count} ACC calls | {calls_per_sec:.1f} calls/sec | Commands sent: {self.command_sent_count}")
            print(f"  ACC: x={x:.3f} y={y:.3f} z={z:.3f} | DETECTED: {detected_direction} (conf: {self.direction_confidence}/{self.confidence_threshold})")
            print(f"  Last command: {getattr(self, 'last_sent_command', 'none')} | Time since last: {time_since_last:.2f}s")
            self.acc_call_count = 0
            self.command_sent_count = 0
            self.last_debug_time = current_time
        
        # Only process commands if we have enough confidence AND haven't sent a command recently
        time_since_last = current_time - self.last_car_time if hasattr(self, 'last_car_time') and self.last_car_time > 0 else 999
        min_interval = self.neutral_interval if detected_direction == "neutral" else self.min_command_interval
        
        if (self.direction_confidence >= self.confidence_threshold and 
            time_since_last >= min_interval):
            self._process_command(detected_direction, current_time)
        elif self.direction_confidence >= self.confidence_threshold:
            print(f"⏳ Command ready but too soon: {time_since_last:.1f}s < {min_interval}s")
    
    def _process_command(self, direction, current_time):
        """Process and potentially send commands with robust deduplication"""
        
        # Prevent multiple simultaneous commands
        if self.command_in_progress:
            print(f"⏳ Command already in progress, skipping '{direction}'")
            return
        
        # Determine required interval based on command type
        required_interval = self.neutral_interval if direction == "neutral" else self.min_command_interval
        
        # Check if enough time has passed since last command
        time_since_last = current_time - self.last_car_time
        print(f"🔍 DEBUG: Processing command '{direction}', time since last: {time_since_last:.3f}s, required: {required_interval}s")
        
        if time_since_last < required_interval:
            print(f"⏳ Too soon since last command ({time_since_last:.1f}s < {required_interval}s)")
            return
        
        # Check if this is actually a new command
        print(f"🔍 DEBUG: Checking if '{direction}' != '{self.last_sent_command}'")
        if direction == self.last_sent_command:
            print(f"🔄 Same command as last ({direction}), skipping")
            return
        
        # Send the command
        print(f"✅ Sending new command: {direction} (was: {self.last_sent_command})")
        self.command_in_progress = True
        try:
            self._send_command(direction, current_time)
        finally:
            self.command_in_progress = False
    
    def _send_command(self, direction, current_time):
        """Send command to car and update tracking"""
        print(f"🔍 DEBUG: About to send command '{direction}', current last_sent_command: '{self.last_sent_command}'")
        
        try:
            print(f"🚗 SENDING CAR COMMAND: {direction.upper()}")
            self.execute_direction(direction)
            
            # Update tracking IMMEDIATELY on SUCCESS
            print(f"🔍 DEBUG: Command executed successfully, updating last_sent_command from '{self.last_sent_command}' to '{direction}'")
            self.last_sent_command = direction
            self.last_car_time = current_time
            self.command_sent_count += 1
            
            print(f"✅ Command sent successfully, updated last_sent_command to: {self.last_sent_command}")
            
            # Add to command history
            self.command_history.append({
                'direction': direction,
                'timestamp': current_time
            })
            
            # Keep only recent history
            if len(self.command_history) > self.max_history:
                self.command_history.pop(0)
                
        except Exception as e:
            print(f"❌ Error sending command {direction}: {e}")
            print(f"⚠️ Keeping last_sent_command as: {self.last_sent_command} (NOT changing to neutral)")
            # DO NOT update last_sent_command on error - this was the bug!

    def detect_head_tilt(self, x, y, z):
        """Detect head tilt direction based on accelerometer data"""
        x, y, z = float(x), float(y), float(z)
        
        # Neutral position: x around -0.24, y around 0.12, z around 0.97
        if (self.neutral_x_range[0] <= x <= self.neutral_x_range[1] and
            self.neutral_y_range[0] <= y <= self.neutral_y_range[1] and
            self.neutral_z_range[0] <= z <= self.neutral_z_range[1]):
            return "neutral"
        
        # Forward: x increases significantly (0.4+)
        elif x >= self.forward_x_min:
            return "forward"
        
        # Back: x goes very negative (-0.97) and z decreases
        elif x <= self.back_x_max and z <= self.back_z_max:
            return "back"
        
        # Left: y goes negative and z decreases (switched from right)
        elif y <= self.left_y_max and z <= self.left_z_max:
            return "left"
        
        # Right: y increases and z decreases (switched from left)
        elif y >= self.right_y_min and z <= self.right_z_max:
            return "right"
        
        return self.current_direction  # Keep current direction if no clear gesture

    def execute_direction(self, direction):
        """Execute car movement based on detected direction"""
        
        if direction == "neutral":
            self.car.stop()
            print("�� STOP")
        elif direction == "forward":
            self.car.forward()
            print("⬆️ FORWARD")
        elif direction == "back":
            self.car.back()
            print("⬇️ BACK")
        elif direction == "left":
            self.car.left()
            print("⬅️ LEFT")
        elif direction == "right":
            self.car.right()
            print("➡️ RIGHT")
        else:
            print(f"⚠️ Unknown direction: {direction}")


    def start_control(self):
        """Start the OSC server and begin controlling the car"""
        disp = dispatcher.Dispatcher()
        disp.map("/muse/eeg", self.eeg_handler)
        disp.map("/muse/acc", self.acc_handler)
        
        server = osc_server.ThreadingOSCUDPServer(("0.0.0.0", 5000), disp)
        print("🎮 Muse Car Controller Started!")
        print("Listening for OSC data on port 5000...")
        print("Make sure your Muse headband is connected and streaming data.")
        print("\nGesture Guide:")
        print("📐 Head tilt = Direction control")
        print("   - Look straight = Stop")
        print("   - Look down = Forward") 
        print("   - Look up = Back")
        print("   - Look left = Turn left")
        print("   - Look right = Turn right")
        print("\nPress Ctrl+C to stop...")
        
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Stopping controller...")
            self.car.stop()
            print("Car stopped.")

if __name__ == "__main__":
    # Update the car host IP if needed
    controller = MuseCarController(car_host="172.22.111.167")
    controller.start_control()
