"""
Main Application Entry Point
Orchestrates all system components
"""

import logging
import time
import signal
import sys
from threading import Thread

from config import get_config
from detection.tflite_model import TFLiteWasteClassifier
from detection.heuristic_model import HeuristicWasteClassifier
from detection.inference import InferencePipeline
from detection.preprocessing import preprocess_for_inference
from hardware.servo_control import BinServoController
from hardware.ultrasonic import MultiBinMonitor
from hardware.ir_sensor import IRSensor
from hardware.gpio_setup import GPIOConfig
from mqtt.mqtt_publish import MQTTPublisher

# Load configuration
config = get_config()

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SmartBinSystem:
    """Main system orchestrator"""
    
    def __init__(self):
        """Initialize all system components"""
        logger.info("Initializing Smart Bin System")
        
        # Initialize GPIO
        GPIOConfig.initialize()
        GPIOConfig.setup_leds()
        
        # Initialize detector (YOLO, TFLite, or heuristic)
        det_type = getattr(config, "DETECTOR_TYPE", "tflite").lower()

        if det_type == "yolo":
            # Lazy import so Raspberry Pi can run TFLite / heuristic
            # without requiring ultralytics to be installed
            from detection.yolo_model import WasteDetector

            logger.info("Detector: YOLO")
            self.detector = WasteDetector(
                model_path=config.MODEL_PATH,
                conf_threshold=config.CONFIDENCE_THRESHOLD,
            )
        elif det_type == "heuristic":
            logger.info("Detector: Heuristic (no ML, OpenCV only)")
            self.detector = HeuristicWasteClassifier(
                conf_threshold=config.CONFIDENCE_THRESHOLD,
            )
        else:
            logger.info("Detector: TFLite")
            self.detector = TFLiteWasteClassifier(
                model_path=config.TFLITE_MODEL_PATH,
                labels_path=config.TFLITE_LABELS_PATH,
                input_size=config.TFLITE_INPUT_SIZE,
                conf_threshold=config.CONFIDENCE_THRESHOLD,
            )
        
        self.camera = InferencePipeline(
            camera_id=config.CAMERA_ID,
            resolution=config.CAMERA_RESOLUTION
        )
        
        # Multi-servo setup: one motor per bin door
        self.servo = BinServoController(
            dry_pin=GPIOConfig.SERVO_DRY_PIN,
            wet_pin=GPIOConfig.SERVO_WET_PIN,
            electronic_pin=GPIOConfig.SERVO_ELECTRONIC_PIN,
            unknown_pin=GPIOConfig.SERVO_UNKNOWN_PIN,
        )
        
        self.bin_monitor = MultiBinMonitor(GPIOConfig.get_bin_sensors())
        
        self.mqtt = MQTTPublisher(
            broker=config.MQTT_BROKER,
            port=config.MQTT_PORT,
            client_id=config.MQTT_CLIENT_ID
        )
        
        self.ir_sensor = IRSensor(
            pin=GPIOConfig.IR_SENSOR_PIN,
            callback=self.on_object_detected
        )
        
        # System state
        self.running = False
        self.processing = False
        
        # Connect to MQTT
        self.mqtt.connect()
        time.sleep(2)
        
        logger.info("System initialization complete")
    
    def on_object_detected(self):
        """Callback when IR sensor detects object"""
        if self.processing:
            logger.info("Already processing, ignoring trigger")
            return
        
        logger.info("Object detected - starting detection")
        self.process_waste()
    
    def process_waste(self):
        """Main waste processing pipeline"""
        self.processing = True
        GPIOConfig.set_status_led(True)
        
        try:
            # Capture frame
            logger.info("Capturing frame")
            frame = self.camera.capture_frame()
            
            if frame is None:
                logger.error("Failed to capture frame")
                return
            
            # Preprocess if enabled
            if config.ENABLE_PREPROCESSING:
                frame = preprocess_for_inference(frame, resize=True, enhance=True)
            
            # Run detection
            logger.info("Running waste detection")
            detections = self.detector.detect(frame)
            
            # Get detection summary
            summary = self.detector.get_detection_summary(detections)
            
            # Publish to MQTT
            self.mqtt.publish_detection(summary)
            
            # Control servo based on detection
            destination = summary['destination']
            
            if destination != 'none':
                logger.info(f"Routing to: {destination}")
                self.servo.rotate_to_bin(destination)
                time.sleep(2)  # Allow time for waste to drop
                self.servo.reset()
            else:
                logger.info("No objects detected")
            
            GPIOConfig.set_status_led(False)
            
        except Exception as e:
            logger.error(f"Processing error: {e}")
            GPIOConfig.set_error_led(True)
            self.mqtt.publish_system_status('error', str(e))
            time.sleep(1)
            GPIOConfig.set_error_led(False)
        
        finally:
            self.processing = False
    
    def monitor_bins(self):
        """Background thread for monitoring bin levels"""
        while self.running:
            try:
                # Get fill levels
                levels = self.bin_monitor.get_all_fill_levels()
                
                # Publish status
                self.mqtt.publish_bin_status(levels)
                
                # Check for full bins
                full_bins = self.bin_monitor.check_any_full(config.BIN_FULL_THRESHOLD)
                
                if full_bins:
                    for bin_name in full_bins:
                        self.mqtt.publish_system_status('alert', f'{bin_name} bin is full')
                
                time.sleep(config.BIN_STATUS_INTERVAL)
                
            except Exception as e:
                logger.error(f"Bin monitoring error: {e}")
                time.sleep(10)
    
    def run(self):
        """Start the system"""
        self.running = True
        
        # Publish system ready
        self.mqtt.publish_system_status('ready', 'System online')
        GPIOConfig.set_status_led(True)
        time.sleep(0.5)
        GPIOConfig.set_status_led(False)
        
        # Start bin monitoring thread
        monitor_thread = Thread(target=self.monitor_bins, daemon=True)
        monitor_thread.start()
        
        logger.info("Smart Bin System running - waiting for objects")
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutdown requested")
            self.shutdown()
    
    def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down system")
        
        self.running = False
        
        # Publish shutdown status
        self.mqtt.publish_system_status('shutdown', 'System shutting down')
        
        # Cleanup components
        self.servo.cleanup()
        self.camera.release()
        self.mqtt.disconnect()
        GPIOConfig.cleanup()
        
        logger.info("Shutdown complete")
        sys.exit(0)


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("Signal received, shutting down")
    if hasattr(signal_handler, 'system'):
        signal_handler.system.shutdown()
    else:
        sys.exit(0)


def main():
    """Main entry point"""
    logger.info("Starting Smart AI Bin System")
    
    # Create system instance
    system = SmartBinSystem()
    signal_handler.system = system
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run system
    system.run()


if __name__ == "__main__":
    main()
