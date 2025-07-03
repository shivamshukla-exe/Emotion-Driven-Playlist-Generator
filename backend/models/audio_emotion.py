import librosa
import numpy as np
import os
import logging
import joblib
import soundfile as sf
import tempfile
import time
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("audio_emotion")

# Fix the import path
try:
    from backend.config import AUDIO_SENSITIVITY
except ImportError:
    # Try relative import
    try:
        import sys
        import os.path
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from config import AUDIO_SENSITIVITY
    except ImportError:
        logger.warning("Could not import config, using default sensitivity")
        AUDIO_SENSITIVITY = 0.12

class AudioEmotionDetector:
    def __init__(self):
        # Dictionary to map emotion indices to labels
        self.emotion_labels = {
            0: 'neutral',
            1: 'calm',
            2: 'happy',
            3: 'sad',
            4: 'angry',
            5: 'fearful',
            6: 'disgust',
            7: 'surprised'
        }
        # Sensitivity adjustment from config
        self.sensitivity = AUDIO_SENSITIVITY
        logger.info(f"Initialized AudioEmotionDetector with sensitivity: {self.sensitivity}")
        
        # Create a model directory if it doesn't exist
        model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'model_cache')
        os.makedirs(model_dir, exist_ok=True)
        
        # Model path for cached model
        self.model_path = os.path.join(model_dir, 'audio_emotion_model.pkl')
        self.scaler_path = os.path.join(model_dir, 'audio_emotion_scaler.pkl')
        
        # Initialize or load the model
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize or load the RandomForest model"""
        try:
            if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
                logger.info(f"Loading audio emotion model from cache: {self.model_path}")
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
            else:
                # If model doesn't exist, create a default trained model with minimal data
                logger.info("Creating default audio emotion model")
                self.model = RandomForestClassifier(
                    n_estimators=10,
                    max_depth=3,
                    min_samples_split=2,
                    random_state=42
                )
                self.scaler = StandardScaler()
                
                # Create minimal training data for basic emotions
                # Format: [[volume, zcr, brightness, tempo], emotion_idx]
                X_train = [
                    [0.2, 0.1, 0.3, 120],  # happy (high energy + high tempo)
                    [0.15, 0.05, 0.1, 70],  # sad (low energy + low tempo)
                    [0.3, 0.02, 0.1, 90],   # angry (high energy + low frequency)
                    [0.05, 0.08, 0.2, 85]   # neutral (moderate values)
                ]
                y_train = [2, 3, 4, 0]  # happy, sad, angry, neutral
                
                # Fit the model with minimal data
                self.model.fit(X_train, y_train)
                logger.info("Fitted default model with minimal training data")
        except Exception as e:
            logger.error(f"Error initializing model: {str(e)}")
            # Create a fallback model
            self.model = RandomForestClassifier(n_estimators=10, random_state=42)
            self.scaler = StandardScaler()
            
            # Create and fit with minimal data
            X_train = [[0.1, 0.1, 0.1, 90]]  # Default neutral values
            y_train = [0]  # Neutral class
            self.model.fit(X_train, y_train)
            logger.info("Created fallback model with minimal training")
    
    def extract_features(self, audio_path):
        """Extract audio features using librosa."""
        try:
            logger.info(f"Extracting features from {audio_path}")
            
            # Verify file exists
            if not os.path.exists(audio_path):
                logger.error(f"Error: Audio file does not exist at {audio_path}")
                return None
            
            # Try to load the audio file, handling different formats
            try:
                y, sr = librosa.load(audio_path, sr=22050)
            except:
                # If librosa fails, try with soundfile
                logger.warning(f"Librosa failed to load the audio, trying with soundfile")
                try:
                    # Convert to WAV first if needed
                    temp_wav = os.path.join(tempfile.gettempdir(), f"temp_audio_{time.time()}.wav")
                    data, sr = sf.read(audio_path)
                    sf.write(temp_wav, data, sr)
                    y, sr = librosa.load(temp_wav, sr=22050)
                    # Remove temp file
                    if os.path.exists(temp_wav):
                        os.remove(temp_wav)
                except Exception as e:
                    logger.error(f"Failed to load audio with soundfile: {str(e)}")
                    return None
            
            # Handle very short audio clips
            if len(y) < sr:
                logger.warning("Warning: Audio clip is too short, padding with silence")
                y = np.pad(y, (0, sr - len(y)), 'constant')
            
            # Handle silence or very low volume audio
            if np.mean(np.abs(y)) < 0.001:  # Very low amplitude
                logger.warning("Warning: Audio contains mostly silence or very low volume")
                # Add a little noise to help with feature extraction
                y = y + (np.random.randn(len(y)) * 0.001)
            
            # Extract features
            # 1. MFCCs (Mel-frequency cepstral coefficients)
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
            mfccs_mean = np.mean(mfccs.T, axis=0)
            mfccs_std = np.std(mfccs.T, axis=0)
            
            # 2. Spectral Centroid (brightness of sound)
            spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            spectral_centroid_mean = np.mean(spectral_centroid)
            spectral_centroid_std = np.std(spectral_centroid)
            
            # 3. Spectral Rolloff
            spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
            spectral_rolloff_mean = np.mean(spectral_rolloff)
            
            # 4. Zero Crossing Rate
            zcr = librosa.feature.zero_crossing_rate(y=y)[0]
            zcr_mean = np.mean(zcr)
            zcr_std = np.std(zcr)
            
            # 5. Root Mean Square Energy
            rms = librosa.feature.rms(y=y)[0]
            rms_mean = np.mean(rms)
            rms_std = np.std(rms)
            
            # 6. Chroma features
            chroma = librosa.feature.chroma_stft(y=y, sr=sr)
            chroma_mean = np.mean(chroma.T, axis=0)
            
            # 7. Tempo and Beat Features
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            tempo, _ = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
            
            # 8. Spectral Contrast
            contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
            contrast_mean = np.mean(contrast.T, axis=0)
            
            # 9. Spectral Bandwidth
            bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
            bandwidth_mean = np.mean(bandwidth)
            
            # 10. Harmonic and Percussive components
            y_harmonic, y_percussive = librosa.effects.hpss(y)
            harmonic_mean = np.mean(y_harmonic**2)
            percussive_mean = np.mean(y_percussive**2)
            
            # Compile all features into a single vector
            feature_vector = np.concatenate([
                mfccs_mean, mfccs_std, 
                [spectral_centroid_mean, spectral_centroid_std], 
                [spectral_rolloff_mean], 
                [zcr_mean, zcr_std], 
                [rms_mean, rms_std], 
                [tempo],
                chroma_mean,
                contrast_mean, 
                [bandwidth_mean], 
                [harmonic_mean, percussive_mean]
            ])
            
            logger.info(f"Successfully extracted features: {len(feature_vector)} dimensions")
            return feature_vector
            
        except Exception as e:
            logger.error(f"Error extracting features: {str(e)}")
            return None
    
    def detect_emotion(self, audio_path):
        """Rule-based and model-based hybrid approach for emotion classification."""
        try:
            features = self.extract_features(audio_path)
            
            if features is None:
                logger.warning("Could not extract features, returning neutral")
                return "neutral"
            
            # Enhanced rule-based detection with more reliable features
            # Get indices for important audio features
            rms_mean_idx = 22  # Root Mean Square Energy (volume)
            zcr_mean_idx = 20  # Zero Crossing Rate (frequency characteristic)
            spectral_centroid_mean_idx = 12  # Spectral Centroid (brightness of sound)
            tempo_idx = 24  # Tempo (speed of audio)
            
            # Extract key features for enhanced rule-based classification
            volume = features[rms_mean_idx]  # Volume
            frequency = features[zcr_mean_idx]  # Frequency characteristics
            brightness = features[spectral_centroid_mean_idx]  # Brightness
            tempo = features[tempo_idx]  # Speed
            
            # Log the features for debugging
            logger.info(f"Audio features - Volume: {volume:.4f}, Frequency: {frequency:.4f}, " +
                       f"Brightness: {brightness:.4f}, Tempo: {tempo:.4f}")
            
            # Extract some more advanced features for better analysis
            spectral_rolloff = features[16] if len(features) > 16 else 0  # Frequency rolloff
            harmonic_ratio = features[27] if len(features) > 27 else 0  # Harmonic ratio
            
            # Apply sensitivity adjustment from config for better detection
            # Lower thresholds = more sensitivity to emotional changes
            volume_threshold = 0.06 * self.sensitivity  
            freq_threshold = 0.03 * self.sensitivity
            brightness_threshold = 0.0 * self.sensitivity
            
            # Simple feature vector for model prediction
            feature_vector = [volume, frequency, brightness, tempo]
            
            try:
                # Get model prediction (we've ensured it's minimally fitted in init)
                emotion_idx = self.model.predict([feature_vector])[0]
                emotion = self.emotion_labels.get(emotion_idx, 'neutral')
                logger.info(f"Model predicted emotion: {emotion}")
                
                # Override with rule-based if the features are very clear indicators
                # Enhanced rule-based classification with multiple features
                # These rules are more sensitive than the previous version
                
                # HAPPY: Higher volume OR higher pitch OR faster tempo
                if (volume > 0.12 or 
                    (frequency > 0.10 and brightness > -2.0) or 
                    tempo > 110):
                    rule_emotion = "happy"
                    logger.info(f"Rule override: {rule_emotion} (high energy/bright sound)")
                    return rule_emotion
                
                # ANGRY: High volume with lower pitch OR sharp spectral characteristics
                elif (volume > 0.15 and frequency < 0.06) or (spectral_rolloff > 0.6):
                    rule_emotion = "angry"
                    logger.info(f"Rule override: {rule_emotion} (high energy/sharp sound)")
                    return rule_emotion
                
                # SAD: Lower volume AND slower tempo OR low brightness
                elif ((volume < 0.08 and tempo < 90) or 
                      (brightness < -3.0 and volume < 0.12)):
                    rule_emotion = "sad"
                    logger.info(f"Rule override: {rule_emotion} (low energy/somber sound)")
                    return rule_emotion
                
                # If no clear rules match, use the model prediction
                # Map to simplified emotion set
                emotion_mapping = {
                    'neutral': 'neutral',
                    'calm': 'neutral',
                    'happy': 'happy',
                    'sad': 'sad',
                    'angry': 'angry',
                    'fearful': 'sad',
                    'disgust': 'angry',
                    'surprised': 'happy'
                }
                
                mapped_emotion = emotion_mapping.get(emotion, 'neutral')
                logger.info(f"Using model prediction: {mapped_emotion}")
                return mapped_emotion
                
            except Exception as e:
                logger.error(f"Model prediction failed: {str(e)}")
                logger.info("Using pure rule-based classification")
                
                # Enhanced rule-based classification without model
                # HAPPY: Higher volume OR higher pitch OR faster tempo 
                if (volume > 0.12 or 
                    (frequency > 0.10 and brightness > -2.0) or 
                    tempo > 110):
                    logger.info("Rule-based emotion detected: happy (high energy/bright sound)")
                    return "happy"
                
                # ANGRY: High volume with lower pitch OR sharp spectral characteristics
                elif (volume > 0.15 and frequency < 0.06) or (spectral_rolloff > 0.6):
                    logger.info("Rule-based emotion detected: angry (high energy/sharp sound)")
                    return "angry"
                
                # SAD: Lower volume AND slower tempo OR low brightness
                elif ((volume < 0.08 and tempo < 90) or 
                      (brightness < -3.0 and volume < 0.12)):
                    logger.info("Rule-based emotion detected: sad (low energy/somber sound)")
                    return "sad"
                    
                # Default to neutral for anything else
                else:
                    logger.info("Rule-based emotion detected: neutral (moderate characteristics)")
                    return "neutral"
                    
        except Exception as e:
            logger.error(f"Error detecting emotion: {str(e)}")
            return "neutral"  # Default fallback