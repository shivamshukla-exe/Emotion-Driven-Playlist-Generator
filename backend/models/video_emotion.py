import cv2
import numpy as np
import tempfile
import os
import logging
from deepface import DeepFace
import time
import traceback

# Import config parameters
try:
    from config import CONFIDENCE_THRESHOLD, VIDEO_EMOTION_THRESHOLD
except ImportError:
    # Default values if config import fails
    CONFIDENCE_THRESHOLD = 0.4
    VIDEO_EMOTION_THRESHOLD = 0.3

class VideoEmotionDetector:
    def __init__(self):
        # Load OpenCV's face detector
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        print(f"Loaded face cascade classifier from: {cascade_path}")
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("VideoEmotionDetector")
        self.logger.info("Initializing VideoEmotionDetector with DeepFace...")
        
        # Store configuration parameters
        self.confidence_threshold = CONFIDENCE_THRESHOLD
        self.emotion_threshold = VIDEO_EMOTION_THRESHOLD
        self.logger.info(f"Using confidence threshold: {self.confidence_threshold}")
        self.logger.info(f"Using emotion threshold: {self.emotion_threshold}")
    
    def detect_emotion(self, video_path):
        self.logger.info(f"Processing video: {video_path}")
        # Verify file exists
        if not os.path.exists(video_path):
            self.logger.error(f"Error: Video file does not exist at {video_path}")
            return "neutral"
            
        # Open the video file
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            self.logger.error(f"Error: Could not open video file {video_path}")
            return "neutral"
            
        self.logger.info("Video file opened successfully")
        
        # Variables to store emotion counts
        emotion_counts = {
            "angry": 0,
            "disgust": 0,
            "fear": 0,
            "happy": 0,
            "sad": 0,
            "surprise": 0,
            "neutral": 0
        }
        
        frame_count = 0
        processed_frames = 0
        
        # Process video frames
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Only process every 10th frame to improve performance
            if frame_count % 10 == 0:
                try:
                    # Convert to grayscale for face detection
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    
                    # Detect faces
                    faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
                    
                    # Process each face in the frame
                    for (x, y, w, h) in faces:
                        # Extract face region
                        face_roi = frame[y:y+h, x:x+w]
                        
                        # Save the face temporarily to analyze with DeepFace
                        temp_face_path = os.path.join(tempfile.gettempdir(), f"face_{time.time()}.jpg")
                        cv2.imwrite(temp_face_path, face_roi)
                        
                        try:
                            # Analyze emotion with DeepFace
                            emotion_analysis = DeepFace.analyze(
                                img_path=temp_face_path,
                                actions=['emotion'],
                                enforce_detection=False,
                                silent=True
                            )
                            
                            # Get dominant emotion
                            if isinstance(emotion_analysis, list):
                                dominant_emotion = emotion_analysis[0]['dominant_emotion']
                            else:
                                dominant_emotion = emotion_analysis['dominant_emotion']
                            
                            # Increment count for this emotion
                            emotion_counts[dominant_emotion] += 1
                            self.logger.debug(f"Detected emotion: {dominant_emotion}")
                            
                            # Remove temporary file
                            if os.path.exists(temp_face_path):
                                os.remove(temp_face_path)
                                
                        except Exception as e:
                            self.logger.warning(f"Error analyzing face emotion: {str(e)}")
                            if os.path.exists(temp_face_path):
                                os.remove(temp_face_path)
                    
                    processed_frames += 1
                    
                except Exception as e:
                    self.logger.error(f"Error processing frame {frame_count}: {str(e)}")
            
            frame_count += 1
            
            # Limit processing to 50 frames for performance
            if processed_frames >= 20:
                break
                
        cap.release()
        
        # If no emotions detected, return neutral
        if sum(emotion_counts.values()) == 0:
            self.logger.info("No emotions detected, returning neutral")
            return "neutral"
        
        # Find the most frequent emotion
        dominant_emotion = max(emotion_counts, key=emotion_counts.get)
        self.logger.info(f"Processed {processed_frames} frames with faces")
        self.logger.info(f"Emotion counts: {emotion_counts}")
        self.logger.info(f"Dominant emotion detected: {dominant_emotion}")
        
        # Map to our simplified emotion set
        emotion_mapping = {
            "angry": "angry",
            "disgust": "angry",  # Map disgust to angry
            "fear": "sad",      # Map fear to sad
            "happy": "happy",
            "sad": "sad",
            "surprise": "happy", # Map surprise to happy
            "neutral": "neutral"
        }
        
        mapped_emotion = emotion_mapping.get(dominant_emotion, "neutral")
        self.logger.info(f"Mapped to simplified emotion: {mapped_emotion}")
        
        return mapped_emotion

    def detect_emotion_from_frame(self, frame_path):
        """Detect emotions from a single video frame"""
        self.logger.info(f"Detecting emotion from frame: {frame_path}")
        
        try:
            # Read the frame
            frame = cv2.imread(frame_path)
            if frame is None:
                self.logger.error(f"Failed to read frame from {frame_path}")
                raise ValueError(f"Failed to read frame from {frame_path}")
                
            # Detect faces in the frame
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(30, 30))
            
            if len(faces) == 0:
                self.logger.warning("No faces detected in the frame")
                return "neutral"  # Default emotion when no face is detected
                
            # Process the first face detected
            face_x, face_y, face_w, face_h = faces[0]
            
            # Extract the face region with some margin
            y_margin = int(face_h * 0.2)
            x_margin = int(face_w * 0.2)
            y_start = max(0, face_y - y_margin)
            y_end = min(frame.shape[0], face_y + face_h + y_margin)
            x_start = max(0, face_x - x_margin)
            x_end = min(frame.shape[1], face_x + face_w + x_margin)
            
            face_img = frame[y_start:y_end, x_start:x_end]
            
            try:
                # Analyze emotions using DeepFace with specific model
                # Try different models for better performance
                analysis = DeepFace.analyze(
                    img_path=face_img, 
                    actions=['emotion'],
                    enforce_detection=False,
                    detector_backend="opencv",
                    models={"emotion": ('Emotion', 'facial_expression_model_weights.h5')}
                )
                
                if isinstance(analysis, list):
                    analysis = analysis[0]
                    
                # Get the emotions with probabilities
                emotions = analysis['emotion']
                
                # Log all emotion scores for debugging
                self.logger.info(f"Emotion scores: {emotions}")
                
                # Apply a stronger bias toward non-neutral emotions to make detection more sensitive
                neutral_penalty = 0.25  # Increased from 0.1
                if 'neutral' in emotions:
                    emotions['neutral'] *= (1 - neutral_penalty)
                
                # Boost happy and angry emotions slightly to make them more likely to be detected
                emotion_boost = {
                    'happy': 0.12,
                    'angry': 0.1,
                    'sad': 0.05
                }

                for emotion, boost in emotion_boost.items():
                    if emotion in emotions:
                        emotions[emotion] *= (1 + boost)
                
                # Get the emotion with highest probability
                dominant_emotion = max(emotions.items(), key=lambda x: x[1])[0]
                
                self.logger.info(f"Original scores: {analysis['emotion']}")
                self.logger.info(f"Adjusted scores: {emotions}")
                self.logger.info(f"Detected dominant emotion from frame: {dominant_emotion}")
                
                # Map the emotion to simplified categories
                mapped_emotion = self.map_emotion(dominant_emotion)
                self.logger.info(f"Mapped emotion: {mapped_emotion}")
                
                return mapped_emotion
            except Exception as e:
                self.logger.error(f"Error in DeepFace analysis: {str(e)}")
                
                # Fallback to a more direct method if DeepFace fails
                try:
                    # Try with different backend
                    analysis = DeepFace.analyze(
                        img_path=face_img, 
                        actions=['emotion'],
                        enforce_detection=False,
                        detector_backend="ssd"
                    )
                    
                    if isinstance(analysis, list):
                        analysis = analysis[0]
                    
                    emotions = analysis['emotion']
                    dominant_emotion = max(emotions.items(), key=lambda x: x[1])[0]
                    mapped_emotion = self.map_emotion(dominant_emotion)
                    
                    self.logger.info(f"Fallback detection succeeded: {mapped_emotion}")
                    return mapped_emotion
                except Exception as nested_e:
                    self.logger.error(f"Fallback detection also failed: {str(nested_e)}")
                    return "neutral"
            
        except Exception as e:
            self.logger.error(f"Error detecting emotion from frame: {str(e)}")
            self.logger.error(traceback.format_exc())
            return "neutral"  # Default emotion on error

    def map_emotion(self, dominant_emotion):
        """Maps DeepFace emotions to our simplified set"""
        # Simple mapping
        emotion_mapping = {
            "angry": "angry",
            "disgust": "angry",
            "fear": "sad",
            "happy": "happy",
            "sad": "sad",
            "surprise": "happy",
            "neutral": "neutral"
        }
        
        return emotion_mapping.get(dominant_emotion, "neutral")