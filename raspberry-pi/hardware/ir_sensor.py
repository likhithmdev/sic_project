"""
IR Sensor Handler
Detects object presence for triggering detection
"""

import RPi.GPIO as GPIO
import time
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class IRSensor:
    """IR proximity sensor for object detection trigger"""
    
    def __init__(self, pin: int, callback: Optional[Callable] = None):
        """
        Initialize IR sensor
        
        Args:
            pin: GPIO pin number
            callback: Optional function to call on detection
        """
        self.pin = pin
        self.callback = callback
        self.last_trigger_time = 0
        self.debounce_delay = 2.0  # Seconds between triggers
        
        self._setup_gpio()
    
    def _setup_gpio(self):
        """Setup GPIO and event detection"""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        except Exception as e:
            logger.error(f"IR sensor GPIO base setup failed: {e}")
            raise

        # Try to attach edge detection, but don't crash the whole system
        # if this fails (e.g. due to noisy hardware or previous listeners).
        if self.callback:
            try:
                GPIO.add_event_detect(
                    self.pin,
                    GPIO.FALLING,
                    callback=self._debounced_callback,
                    bouncetime=300,
                )
            except Exception as e:
                logger.error(
                    f"IR sensor edge detection setup failed: {e} - "
                    f"falling back to polling only."
                )

        logger.info(f"IR sensor initialized on GPIO pin {self.pin}")
    
    def _debounced_callback(self, channel):
        """Debounced callback wrapper"""
        current_time = time.time()
        
        if current_time - self.last_trigger_time >= self.debounce_delay:
            logger.info("IR sensor triggered - object detected")
            self.last_trigger_time = current_time
            
            if self.callback:
                self.callback()
    
    def is_object_present(self) -> bool:
        """
        Check if object is currently present
        
        Returns:
            True if object detected
        """
        return GPIO.input(self.pin) == GPIO.LOW
    
    def wait_for_object(self, timeout: Optional[float] = None) -> bool:
        """
        Block until object detected
        
        Args:
            timeout: Maximum wait time in seconds
            
        Returns:
            True if object detected, False if timeout
        """
        start_time = time.time()
        
        while True:
            if self.is_object_present():
                logger.info("Object detected by IR sensor")
                return True
            
            if timeout and (time.time() - start_time) > timeout:
                logger.info("IR sensor wait timeout")
                return False
            
            time.sleep(0.1)
    
    def cleanup(self):
        """Cleanup GPIO"""
        GPIO.cleanup()
        logger.info("IR sensor cleanup complete")
