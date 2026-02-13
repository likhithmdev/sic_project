"""
Ultrasonic Sensor Handler
Measures bin fill levels using HC-SR04
"""

import RPi.GPIO as GPIO
import time
import logging

logger = logging.getLogger(__name__)


class UltrasonicSensor:
    """Handles ultrasonic distance measurement for bin fill detection"""
    
    def __init__(self, trigger_pin: int, echo_pin: int, bin_depth: float = 30.0):
        """
        Initialize ultrasonic sensor
        
        Args:
            trigger_pin: GPIO pin for trigger
            echo_pin: GPIO pin for echo
            bin_depth: Total bin depth in cm
        """
        self.trigger_pin = trigger_pin
        self.echo_pin = echo_pin
        self.bin_depth = bin_depth
        
        self._setup_gpio()
    
    def _setup_gpio(self):
        """Setup GPIO pins"""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.trigger_pin, GPIO.OUT)
            GPIO.setup(self.echo_pin, GPIO.IN)
            
            GPIO.output(self.trigger_pin, False)
            time.sleep(0.1)
            
            logger.info(f"Ultrasonic sensor initialized (Trigger: {self.trigger_pin}, Echo: {self.echo_pin})")
        except Exception as e:
            logger.error(f"Ultrasonic GPIO setup failed: {e}")
            raise
    
    def measure_distance(self, samples: int = 3) -> float:
        """
        Measure distance to object
        
        Args:
            samples: Number of measurements to average
            
        Returns:
            Distance in centimeters
        """
        distances = []
        last_pulse_duration = 0.0
        last_distance = 0.0

        for _ in range(samples):
            # Send trigger pulse
            GPIO.output(self.trigger_pin, True)
            time.sleep(0.00001)
            GPIO.output(self.trigger_pin, False)

            # Wait for echo
            pulse_start = time.time()
            timeout_start = pulse_start

            while GPIO.input(self.echo_pin) == 0:
                pulse_start = time.time()
                if pulse_start - timeout_start > 0.1:
                    break

            pulse_end = time.time()
            timeout_end = pulse_end

            while GPIO.input(self.echo_pin) == 1:
                pulse_end = time.time()
                if pulse_end - timeout_end > 0.1:
                    break

            # Calculate distance
            pulse_duration = pulse_end - pulse_start
            last_pulse_duration = pulse_duration
            distance = pulse_duration * 17150  # Speed of sound / 2
            distance = round(distance, 2)
            last_distance = distance

            if 2 < distance < 400:  # Valid range for HC-SR04
                distances.append(distance)

            time.sleep(0.05)

        if not distances:
            logger.warning(
                "No valid distance (Trig=%s Echo=%s). Last: pulse=%.4fs dist=%.1fcm. "
                "Check wiring, Echo 5V->3.3V divider, and pins in gpio_setup.py",
                self.trigger_pin, self.echo_pin, last_pulse_duration, last_distance,
            )
            return -1
        
        avg_distance = sum(distances) / len(distances)
        logger.debug(f"Measured distance: {avg_distance:.2f} cm")
        
        return avg_distance
    
    def get_fill_level(self) -> float:
        """
        Calculate bin fill percentage
        
        Returns:
            Fill level as percentage (0-100)
        """
        distance = self.measure_distance()
        
        if distance < 0:
            return 0
        
        fill_height = self.bin_depth - distance
        fill_percentage = (fill_height / self.bin_depth) * 100
        
        fill_percentage = max(0, min(100, fill_percentage))
        
        logger.debug(f"Bin fill level: {fill_percentage:.1f}%")
        return fill_percentage
    
    def is_full(self, threshold: float = 80.0) -> bool:
        """
        Check if bin is full
        
        Args:
            threshold: Fill percentage threshold
            
        Returns:
            True if bin is full
        """
        fill_level = self.get_fill_level()
        return fill_level >= threshold


class MultiBinMonitor:
    """Monitors multiple bins with ultrasonic sensors"""
    
    def __init__(self, bin_configs: dict):
        """
        Initialize multiple bin monitors
        
        Args:
            bin_configs: Dict mapping bin names to (trigger_pin, echo_pin, depth) tuples
        """
        self.sensors = {}
        
        for bin_name, (trigger, echo, depth) in bin_configs.items():
            self.sensors[bin_name] = UltrasonicSensor(trigger, echo, depth)
            logger.info(f"Initialized sensor for {bin_name} bin")
    
    def get_all_fill_levels(self) -> dict:
        """
        Get fill levels for all bins
        
        Returns:
            Dictionary mapping bin names to fill percentages
        """
        levels = {}
        for bin_name, sensor in self.sensors.items():
            levels[bin_name] = sensor.get_fill_level()
        
        return levels
    
    def check_any_full(self, threshold: float = 80.0) -> list:
        """
        Check which bins are full
        
        Args:
            threshold: Fill threshold percentage
            
        Returns:
            List of full bin names
        """
        full_bins = []
        
        for bin_name, sensor in self.sensors.items():
            if sensor.is_full(threshold):
                full_bins.append(bin_name)
                logger.warning(f"{bin_name} bin is full!")
        
        return full_bins
