# Configuration file for application settings

# Spotify API Credentials
# Get these from https://developer.spotify.com/dashboard/
# Leave empty strings for using demo playlists
SPOTIFY_CLIENT_ID = 'c197ba86e6584a4289ac50513e094f26'
SPOTIFY_CLIENT_SECRET = '34a724d068824843b7be3a8543495b52'
SPOTIFY_REDIRECT_URI = 'http://localhost:3000/callback'

# Audio Emotion Detection Settings
AUDIO_SENSITIVITY = 0.18  # Increased for more sensitivity (was 0.12)

# Video Emotion Detection Settings
CONFIDENCE_THRESHOLD = 0.4  # Reduced threshold to detect emotions more easily (was 0.6)
VIDEO_EMOTION_THRESHOLD = 0.2  # Lower threshold for non-neutral emotions 