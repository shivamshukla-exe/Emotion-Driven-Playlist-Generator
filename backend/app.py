from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import tempfile
import traceback
import time
import logging
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("app")

from models.video_emotion import VideoEmotionDetector
from models.audio_emotion import AudioEmotionDetector
from models.text_emotion import TextEmotionDetector
from models.spotify_handler import SpotifyHandler

# Import configuration settings
try:
    from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, AUDIO_SENSITIVITY, CONFIDENCE_THRESHOLD
    logger.info(f"Loaded configuration from config.py")
except ImportError:
    logger.warning("Config file not found, using default settings")
    AUDIO_SENSITIVITY = 0.1
    CONFIDENCE_THRESHOLD = 0.6
    # Create empty config variables to avoid errors
    SPOTIFY_CLIENT_ID = ""
    SPOTIFY_CLIENT_SECRET = ""

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

logger.info("Initializing emotion detection models...")

# Initialize models with better error handling
try:
    video_detector = VideoEmotionDetector()
    logger.info("Video emotion detection model initialized")
except Exception as e:
    logger.error(f"Error initializing video detector: {str(e)}")
    video_detector = None

try:
    audio_detector = AudioEmotionDetector()
    logger.info("Audio emotion detection model initialized")
except Exception as e:
    logger.error(f"Error initializing audio detector: {str(e)}")
    audio_detector = None

try:
    text_detector = TextEmotionDetector()
    logger.info("Text emotion detection model initialized")
except Exception as e:
    logger.error(f"Error initializing text detector: {str(e)}")
    text_detector = None

try:
    spotify_handler = SpotifyHandler()
    # After initialization, explicitly update with config credentials if provided
    if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:
        spotify_handler.update_credentials(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
    logger.info("Spotify handler initialized")
except Exception as e:
    logger.error(f"Error initializing Spotify handler: {str(e)}")
    spotify_handler = None

logger.info("All models initialized and ready!")

# Dictionary to store active live detection sessions
live_sessions = {}

@app.route('/api/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'Emotion detection API is running',
        'models_status': {
            'video_detector': video_detector is not None,
            'audio_detector': audio_detector is not None,
            'text_detector': text_detector is not None,
            'spotify_connected': spotify_handler is not None and spotify_handler.sp is not None
        }
    })

@app.route('/api/detect/video', methods=['POST'])
def detect_video_emotion():
    """Endpoint for detecting emotions from video input"""
    logger.info("Received video emotion detection request")
    
    if not video_detector:
        logger.error("Video detector is not initialized")
        return jsonify({'error': 'Video emotion detector is not available'}), 500
    
    if 'video' not in request.files:
        logger.warning("No video file provided")
        return jsonify({'error': 'No video file provided'}), 400
    
    video_file = request.files['video']
    
    if video_file.filename == '':
        logger.warning("Empty video filename")
        return jsonify({'error': 'No video file selected'}), 400
    
    try:
        # Save video to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_path = temp_file.name
        temp_file.close()
        
        logger.info(f"Saving uploaded video to temporary file: {temp_path}")
        video_file.save(temp_path)
        
        try:
            # Detect emotion
            emotion = video_detector.detect_emotion(temp_path)
            logger.info(f"Video emotion detected: {emotion}")
            
            # Get playlist recommendations
            playlists = spotify_handler.get_playlist_for_emotion(emotion)
            
            # Remove temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                logger.info(f"Temporary file deleted: {temp_path}")
            
            return jsonify({
                'emotion': emotion,
                'playlists': playlists,
                'using_spotify_api': spotify_handler.sp is not None
            })
        except Exception as e:
            logger.error(f"Error processing video: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Remove temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                logger.info(f"Temporary file deleted: {temp_path}")
                
            return jsonify({'error': f'Error processing video: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Error handling video upload: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Error handling video upload: {str(e)}'}), 500

@app.route('/api/detect/audio', methods=['POST'])
def detect_audio_emotion():
    """Endpoint for detecting emotions from audio input"""
    logger.info("Received audio emotion detection request")
    
    if not audio_detector:
        logger.error("Audio detector is not initialized")
        return jsonify({'error': 'Audio emotion detector is not available'}), 500
    
    if 'audio' not in request.files:
        logger.warning("No audio file provided")
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['audio']
    
    if audio_file.filename == '':
        logger.warning("Empty audio filename")
        return jsonify({'error': 'No audio file selected'}), 400
    
    try:
        # Save audio to temporary file
        file_extension = os.path.splitext(audio_file.filename)[1].lower() or '.wav'
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension)
        temp_path = temp_file.name
        temp_file.close()
        
        logger.info(f"Saving uploaded audio to temporary file: {temp_path}")
        audio_file.save(temp_path)
        
        try:
            # Add a small delay to ensure file is fully written
            time.sleep(0.5)
            
            # Detect emotion with retry mechanism
            max_attempts = 3
            emotion = None
            last_error = None
            
            for attempt in range(max_attempts):
                try:
                    logger.info(f"Attempting audio emotion detection (attempt {attempt+1}/{max_attempts})")
                    emotion = audio_detector.detect_emotion(temp_path)
                    if emotion:
                        break
                except Exception as e:
                    last_error = e
                    logger.error(f"Attempt {attempt+1} failed: {str(e)}")
                    time.sleep(0.5)  # Wait before retrying
            
            if not emotion:
                if last_error:
                    raise last_error
                emotion = "neutral"  # Default fallback
            
            logger.info(f"Audio emotion detected: {emotion}")
            
            # Get playlist recommendations
            playlists = spotify_handler.get_playlist_for_emotion(emotion)
            
            # Remove temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                logger.info(f"Temporary file deleted: {temp_path}")
                
            return jsonify({
                'emotion': emotion,
                'playlists': playlists,
                'using_spotify_api': spotify_handler.sp is not None
            })
        except Exception as e:
            logger.error(f"Error processing audio: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Remove temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                logger.info(f"Temporary file deleted: {temp_path}")
                
            return jsonify({'error': f'Error processing audio: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Error handling audio upload: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Error handling audio upload: {str(e)}'}), 500

@app.route('/api/detect/text', methods=['POST'])
def detect_text_emotion():
    logger.info("Received text emotion detection request")
    if not text_detector:
        logger.error("Text detector is not initialized")
        return jsonify({'error': 'Text emotion detector is not available'}), 500

    if not request.is_json:
        logger.warning("Invalid request format: not JSON")
        return jsonify({'error': 'Request must be JSON'}), 400

    data = request.get_json()
    if not data or 'text' not in data:
        logger.warning("No text provided in request")
        return jsonify({'error': 'No text provided'}), 400

    try:
        text = data['text']
        logger.info(f"Detecting emotion in text: '{text[:20]}...' (truncated)")
        text = text.replace('\\', '\\\\')
        emotion = text_detector.detect_emotion(text)
        logger.info(f"Text emotion detected: {emotion}")

        user_id = request.headers.get('X-User-ID')
        playlists = []
        if user_id:
            logger.info(f"[TEXT] X-User-ID header present: {user_id}. Using personalized playlist logic for emotion '{emotion}'.")
            personalized_result = spotify_handler.get_emotion_personalized_playlist(user_id, emotion)
            if personalized_result['type'] == 'playlist':
                playlists = [personalized_result['playlist']]
                logger.info(f"[TEXT] Personalized playlist found and returned for user {user_id}.")
            elif personalized_result['type'] == 'custom':
                playlists = [{
                    'name': personalized_result['title'],
                    'tracks_list': personalized_result['tracks'],
                    'custom': True
                }]
                logger.info(f"[TEXT] Personalized custom track list returned for user {user_id}.")
            else:
                playlists = []
                logger.info(f"[TEXT] No personalized playlist or tracks found for user {user_id}.")
        else:
            logger.info(f"[TEXT] No X-User-ID header present. Using generic playlist logic for emotion '{emotion}'.")
            if spotify_handler:
                playlists = spotify_handler.get_playlist_for_emotion(emotion)

        emotion_output = {emotion: 1.0} if isinstance(emotion, str) else emotion
        return jsonify({
            'emotion': emotion_output,
            'emotions': emotion_output,
            'playlists': playlists,
            'using_spotify_api': spotify_handler is not None and spotify_handler.sp is not None
        })
    except Exception as e:
        logger.error(f"Error detecting emotion from text: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Error detecting emotion from text: {str(e)}'}), 500

@app.route('/api/models/status', methods=['GET'])
def models_status():
    """Get the status of all models"""
    return jsonify({
        'video_detector': video_detector is not None,
        'audio_detector': audio_detector is not None,
        'text_detector': text_detector is not None,
        'spotify_connected': spotify_handler is not None and spotify_handler.sp is not None
    })

@app.route('/api/spotify/config', methods=['POST', 'GET'])
def spotify_config():
    """Endpoint to get or update Spotify configuration"""
    # Safety check to ensure spotify_handler exists
    if spotify_handler is None:
        return jsonify({
            'error': 'Spotify handler is not available',
            'client_id': '',
            'has_secret': False,
            'using_spotify_api': False
        }), 500
        
    if request.method == 'GET':
        # Return current config (without the secret)
        try:
            client_id = os.environ.get('SPOTIFY_CLIENT_ID', SPOTIFY_CLIENT_ID)
            # Don't return the full secret for security
            has_secret = bool(os.environ.get('SPOTIFY_CLIENT_SECRET', SPOTIFY_CLIENT_SECRET))
            
            return jsonify({
                'client_id': client_id or '',
                'has_secret': has_secret,
                'using_spotify_api': spotify_handler.sp is not None
            })
        except Exception as e:
            logger.error(f"Error retrieving Spotify configuration: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'error': f'Error retrieving configuration: {str(e)}',
                'client_id': '',
                'has_secret': False,
                'using_spotify_api': False
            }), 500
    
    elif request.method == 'POST':
        if not request.is_json:
            logger.warning("Invalid request format for Spotify config: not JSON")
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.get_json()
        
        if not data or 'client_id' not in data or 'client_secret' not in data:
            logger.warning("Missing client_id or client_secret in Spotify config request")
            return jsonify({'error': 'Client ID and Client Secret are required'}), 400
        
        try:
            # Directly update the SpotifyHandler
            success = spotify_handler.update_credentials(data['client_id'], data['client_secret'])
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'Spotify configuration updated successfully',
                    'using_spotify_api': True
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Invalid Spotify credentials or connection failed',
                    'using_spotify_api': False
                }), 400
        except Exception as e:
            logger.error(f"Error updating Spotify configuration: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({'error': f'Error updating configuration: {str(e)}'}), 500

@app.route('/api/live-detection/start', methods=['POST'])
def start_live_detection():
    """Start a new live detection session"""
    try:
        data = request.json
        session_id = data.get('sessionId', str(uuid.uuid4()))
        
        # Create a new session with timestamp
        live_sessions[session_id] = {
            'start_time': time.time(),
            'last_activity': time.time(),
            'emotion_history': [],
            'tracks': [],
            'active': True
        }
        
        logger.info(f"Started live detection session: {session_id}")
        
        return jsonify({
            'session_id': session_id,
            'status': 'started',
            'message': 'Live detection session started successfully'
        })
        
    except Exception as e:
        logger.error(f"Error starting live detection session: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Error starting live detection session: {str(e)}'}), 500

@app.route('/api/live-detection/stop', methods=['POST'])
def stop_live_detection():
    """Stop an active live detection session"""
    try:
        data = request.json
        session_id = data.get('sessionId')
        
        if not session_id or session_id not in live_sessions:
            return jsonify({'error': 'Invalid session ID'}), 400
        
        # Mark session as inactive
        live_sessions[session_id]['active'] = False
        live_sessions[session_id]['end_time'] = time.time()
        
        logger.info(f"Stopped live detection session: {session_id}")
        
        # Cleanup old sessions
        cleanup_old_sessions()
        
        return jsonify({
            'session_id': session_id,
            'status': 'stopped',
            'message': 'Live detection session stopped successfully'
        })
        
    except Exception as e:
        logger.error(f"Error stopping live detection session: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Error stopping live detection session: {str(e)}'}), 500

@app.route('/api/live-detection/status', methods=['GET'])
def get_live_detection_status():
    """Get the status of a live detection session"""
    try:
        session_id = request.args.get('sessionId')
        
        if not session_id or session_id not in live_sessions:
            return jsonify({'error': 'Invalid session ID'}), 400
        
        # Get session data
        session = live_sessions[session_id]
        
        return jsonify({
            'session_id': session_id,
            'status': 'active' if session['active'] else 'inactive',
            'start_time': session['start_time'],
            'last_activity': session['last_activity'],
            'emotion_history': session['emotion_history'][-10:] if session['emotion_history'] else [],
            'tracks_count': len(session['tracks'])
        })
        
    except Exception as e:
        logger.error(f"Error getting live detection status: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Error getting live detection status: {str(e)}'}), 500

def cleanup_old_sessions():
    """Clean up old inactive sessions"""
    current_time = time.time()
    sessions_to_remove = []
    
    # Find sessions older than 1 hour
    for session_id, session in live_sessions.items():
        if not session['active'] and (current_time - session['last_activity']) > 3600:
            sessions_to_remove.append(session_id)
    
    # Remove old sessions
    for session_id in sessions_to_remove:
        del live_sessions[session_id]
    
    if sessions_to_remove:
        logger.info(f"Cleaned up {len(sessions_to_remove)} old live detection sessions")

@app.route('/api/detect/realtime-frame', methods=['POST'])
def detect_realtime_frame():
    """Endpoint for detecting emotions from a single video frame"""
    logger.info("Received real-time frame detection request")
    
    # Check if session ID is provided
    session_id = request.form.get('sessionId')
    if session_id and session_id in live_sessions:
        # Update session activity
        live_sessions[session_id]['last_activity'] = time.time()
    
    if not video_detector:
        logger.error("Video detector is not initialized")
        return jsonify({'error': 'Video emotion detector is not available'}), 500
    
    if 'frame' not in request.files:
        logger.warning("No frame file provided")
        return jsonify({'error': 'No frame file provided'}), 400
    
    frame_file = request.files['frame']
    
    if frame_file.filename == '':
        logger.warning("Empty frame filename")
        return jsonify({'error': 'No frame file selected'}), 400
    
    try:
        # Save frame to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        temp_path = temp_file.name
        temp_file.close()
        
        logger.info(f"Saving uploaded frame to temporary file: {temp_path}")
        frame_file.save(temp_path)
        
        try:
            # Detect emotion from frame
            emotion = video_detector.detect_emotion_from_frame(temp_path)
            logger.info(f"Real-time frame emotion detected: {emotion}")
            
            # Get track recommendations
            tracks = spotify_handler.get_realtime_tracks(emotion)
            
            # If session exists, update session data
            if session_id and session_id in live_sessions:
                # Add emotion to history
                live_sessions[session_id]['emotion_history'].append({
                    'emotion': emotion,
                    'timestamp': time.time()
                })
                
                # Add new tracks for this emotion to the session
                existing_track_ids = {track['id'] for track in live_sessions[session_id]['tracks']}
                new_tracks = [track for track in tracks if track['id'] not in existing_track_ids]
                live_sessions[session_id]['tracks'].extend(new_tracks)
            
            # Remove temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                logger.info(f"Temporary file deleted: {temp_path}")
            
            return jsonify({
                'emotion': emotion,
                'tracks': tracks,
                'session_id': session_id,
                'timestamp': time.time()
            })
            
        except Exception as e:
            logger.error(f"Error processing frame: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Remove temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                logger.info(f"Temporary file deleted: {temp_path}")
                
            return jsonify({'error': f'Error processing frame: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Error handling frame upload: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Error handling frame upload: {str(e)}'}), 500

@app.route('/api/spotify/auth-url', methods=['GET'])
def get_spotify_auth_url():
    """Get the Spotify authorization URL"""
    try:
        auth_url = spotify_handler.get_auth_url()
        return jsonify({'url': auth_url})
    except Exception as e:
        logger.error(f"Error getting Spotify auth URL: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/spotify/callback', methods=['POST'])
def spotify_callback():
    """Handle the Spotify callback with authorization code"""
    try:
        data = request.get_json()
        if not data or 'code' not in data:
            return jsonify({'error': 'No authorization code provided'}), 400
            
        code = data['code']
        state = data.get('state')  # Optional state parameter
        
        user_info = spotify_handler.handle_callback(code, state)
        return jsonify(user_info)
    except Exception as e:
        logger.error(f"Error handling Spotify callback: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/spotify/login-status', methods=['GET'])
def spotify_login_status():
    """Get the current login status"""
    try:
        # Get user ID from request headers or cookies
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'isLoggedIn': False})
            
        # Check if user is authenticated
        client = spotify_handler._init_user_client(user_id)
        if not client:
            return jsonify({'isLoggedIn': False})
            
        # Get user profile
        user_profile = spotify_handler.get_user_profile(user_id)
        return jsonify({
            'isLoggedIn': True,
            'userProfile': user_profile
        })
    except Exception as e:
        logger.error(f"Error checking login status: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'isLoggedIn': False})

@app.route('/api/spotify/logout', methods=['POST'])
def spotify_logout():
    """Log out a user"""
    try:
        # Get user ID from request headers or cookies
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'error': 'No user ID provided'}), 400
            
        # Log out the user
        spotify_handler.logout(user_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error logging out: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/spotify/user-profile', methods=['GET'])
def spotify_user_profile():
    """Get the user's Spotify profile"""
    try:
        # Get user ID from request headers or cookies
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'error': 'No user ID provided'}), 400
            
        # Get user profile
        user_profile = spotify_handler.get_user_profile(user_id)
        return jsonify(user_profile)
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/spotify/top-artists', methods=['GET'])
def spotify_top_artists():
    """Get the user's top artists"""
    try:
        # Get user ID from request headers or cookies
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'error': 'No user ID provided'}), 400
            
        # Get time range and limit from query parameters
        time_range = request.args.get('time_range', 'medium_term')
        limit = int(request.args.get('limit', 20))
        
        # Get top artists
        top_artists = spotify_handler.get_top_artists(user_id, time_range, limit)
        return jsonify(top_artists)
    except Exception as e:
        logger.error(f"Error getting top artists: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/spotify/top-tracks', methods=['GET'])
def spotify_top_tracks():
    """Get the user's top tracks"""
    try:
        # Get user ID from request headers or cookies
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'error': 'No user ID provided'}), 400
            
        # Get time range and limit from query parameters
        time_range = request.args.get('time_range', 'medium_term')
        limit = int(request.args.get('limit', 20))
        
        # Get top tracks
        top_tracks = spotify_handler.get_top_tracks(user_id, time_range, limit)
        return jsonify(top_tracks)
    except Exception as e:
        logger.error(f"Error getting top tracks: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/spotify/recently-played', methods=['GET'])
def spotify_recently_played():
    """Get the user's recently played tracks"""
    try:
        # Get user ID from request headers or cookies
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'error': 'No user ID provided'}), 400
            
        # Get limit from query parameters
        limit = int(request.args.get('limit', 20))
        
        # Get recently played tracks
        recently_played = spotify_handler.get_recently_played(user_id, limit)
        return jsonify(recently_played)
    except Exception as e:
        logger.error(f"Error getting recently played tracks: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/spotify/personalized-recommendations', methods=['GET'])
def spotify_personalized_recommendations():
    """Get personalized recommendations based on emotion and user history"""
    try:
        # Get user ID from request headers or cookies
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'error': 'No user ID provided'}), 400
            
        # Get emotion from query parameters
        emotion = request.args.get('emotion')
        if not emotion:
            return jsonify({'error': 'No emotion provided'}), 400
            
        # Get personalized recommendations
        recommendations = spotify_handler.get_personalized_recommendations(user_id, emotion)
        return jsonify(recommendations)
    except Exception as e:
        logger.error(f"Error getting personalized recommendations: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/spotify/emotion-personalized', methods=['GET'])
def spotify_emotion_personalized():
    """Get a playlist or custom track list based on emotion and user's top artists."""
    try:
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'type': 'error', 'message': 'No user ID provided'}), 400
        emotion = request.args.get('emotion')
        if not emotion:
            return jsonify({'type': 'error', 'message': 'No emotion provided'}), 400
        result = spotify_handler.get_emotion_personalized_playlist(user_id, emotion)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in /api/spotify/emotion-personalized: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'type': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting Flask application on http://127.0.0.1:5000")
    app.run(debug=True, host='0.0.0.0')