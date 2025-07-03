import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
import os
import json
import logging
import time
import traceback
import random
import secrets
from urllib.parse import urlencode

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("spotify_handler")

# Fix the import path
try:
    from backend.config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
except ImportError:
    # Try direct import
    try:
        import sys
        import os.path
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
    except ImportError:
        logger.warning("Could not import config, using empty credentials")
        SPOTIFY_CLIENT_ID = ""
        SPOTIFY_CLIENT_SECRET = ""
        SPOTIFY_REDIRECT_URI = "http://localhost:3000/callback"

class SpotifyHandler:
    def __init__(self):
        # Get credentials from config file
        self.client_id = SPOTIFY_CLIENT_ID
        self.client_secret = SPOTIFY_CLIENT_SECRET
        self.redirect_uri = SPOTIFY_REDIRECT_URI
        self.sp = None
        self.user_sp = None  # User-authenticated Spotify client
        self.last_api_call = 0
        self.rate_limit_delay = 1  # 1 second between API calls to avoid rate limiting
        self.user_tokens = {}  # Store user tokens in memory (in production, use a database)
        
        # Check for environment variables which would override config
        if os.environ.get('SPOTIFY_CLIENT_ID'):
            self.client_id = os.environ.get('SPOTIFY_CLIENT_ID')
            logger.info("Using Spotify client ID from environment")
        if os.environ.get('SPOTIFY_CLIENT_SECRET'):
            self.client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
            logger.info("Using Spotify client secret from environment")
        if os.environ.get('SPOTIFY_REDIRECT_URI'):
            self.redirect_uri = os.environ.get('SPOTIFY_REDIRECT_URI')
            logger.info("Using Spotify redirect URI from environment")
        
        logger.info(f"Initializing Spotify handler with client ID: {'CONFIGURED' if self.client_id else 'NOT CONFIGURED'}")
        
        # Initialize Spotify client if credentials are provided
        self._init_spotify_client()
    
    def _init_spotify_client(self):
        """Initialize the Spotify client with the current credentials"""
        # Only initialize if credentials are provided and not empty
        if self.client_id and self.client_secret:
            try:
                logger.info("Connecting to Spotify API...")
                auth_manager = SpotifyClientCredentials(
                    client_id=self.client_id,
                    client_secret=self.client_secret
                )
                self.sp = spotipy.Spotify(auth_manager=auth_manager)
                
                # Test the connection with a simple request
                test_result = self.sp.search(q="test", limit=1, type='track')
                if not test_result or 'tracks' not in test_result:
                    raise Exception("Test search did not return expected structure")
                
                logger.info("✅ Spotify API connected successfully!")
                return True
            except Exception as e:
                logger.error(f"❌ Error connecting to Spotify API: {str(e)}")
                logger.error(traceback.format_exc())
                self.sp = None
                logger.info("Using demo playlists instead")
                return False
        else:
            self.sp = None
            logger.info("No valid Spotify credentials provided. Using demo playlists.")
            return False
    
    def _init_user_client(self, user_id):
        """Initialize a user-authenticated Spotify client"""
        if not user_id or user_id not in self.user_tokens:
            return None
            
        try:
            token_info = self.user_tokens[user_id]
            
            # Check if token is expired
            if time.time() > token_info['expires_at']:
                # Token expired, refresh it
                auth_manager = SpotifyOAuth(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    redirect_uri=self.redirect_uri,
                    scope='user-read-private user-read-email user-top-read user-read-recently-played playlist-read-private'
                )
                
                # Refresh the token
                token_info = auth_manager.refresh_access_token(token_info['refresh_token'])
                self.user_tokens[user_id] = token_info
            
            # Create a new client with the token
            self.user_sp = spotipy.Spotify(auth=token_info['access_token'])
            return self.user_sp
        except Exception as e:
            logger.error(f"Error initializing user Spotify client: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    def get_auth_url(self):
        """Get the Spotify authorization URL"""
        if not self.client_id or not self.client_secret:
            raise Exception("Spotify credentials not configured")
            
        # Generate a random state for security
        state = secrets.token_hex(16)
        
        # Define the scopes we need
        scopes = [
            'user-read-private',
            'user-read-email',
            'user-top-read',
            'user-read-recently-played',
            'playlist-read-private'
        ]
        
        # Create the authorization URL
        auth_url = 'https://accounts.spotify.com/authorize?' + urlencode({
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'state': state,
            'scope': ' '.join(scopes)
        })
        
        return auth_url
    
    def handle_callback(self, code, state):
        """Handle the Spotify callback with authorization code"""
        if not self.client_id or not self.client_secret:
            raise Exception("Spotify credentials not configured")
            
        try:
            # Create an OAuth manager
            auth_manager = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope='user-read-private user-read-email user-top-read user-read-recently-played playlist-read-private'
            )
            
            # Exchange the code for tokens
            token_info = auth_manager.get_access_token(code)
            
            # Create a temporary client to get the user ID
            temp_client = spotipy.Spotify(auth=token_info['access_token'])
            user_info = temp_client.current_user()
            user_id = user_info['id']
            
            # Store the token info
            self.user_tokens[user_id] = token_info
            
            return {
                'user_id': user_id,
                'display_name': user_info['display_name'],
                'email': user_info['email'],
                'images': user_info['images']
            }
        except Exception as e:
            logger.error(f"Error handling Spotify callback: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def get_user_profile(self, user_id):
        """Get the user's Spotify profile"""
        client = self._init_user_client(user_id)
        if not client:
            raise Exception("User not authenticated")
            
        try:
            return client.current_user()
        except Exception as e:
            logger.error(f"Error getting user profile: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def get_top_artists(self, user_id, time_range='medium_term', limit=20):
        """Get the user's top artists"""
        client = self._init_user_client(user_id)
        if not client:
            raise Exception("User not authenticated")
            
        try:
            return client.current_user_top_artists(time_range=time_range, limit=limit)
        except Exception as e:
            logger.error(f"Error getting top artists: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def get_top_tracks(self, user_id, time_range='medium_term', limit=20):
        """Get the user's top tracks"""
        client = self._init_user_client(user_id)
        if not client:
            raise Exception("User not authenticated")
            
        try:
            return client.current_user_top_tracks(time_range=time_range, limit=limit)
        except Exception as e:
            logger.error(f"Error getting top tracks: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def get_recently_played(self, user_id, limit=20):
        """Get the user's recently played tracks"""
        client = self._init_user_client(user_id)
        if not client:
            raise Exception("User not authenticated")
            
        try:
            return client.current_user_recently_played(limit=limit)
        except Exception as e:
            logger.error(f"Error getting recently played: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def get_personalized_recommendations(self, user_id, emotion):
        """Get personalized recommendations based on emotion and user history"""
        client = self._init_user_client(user_id)
        if not client:
            # Fall back to non-personalized recommendations
            return self.get_playlist_for_emotion(emotion)
            
        try:
            # Get user's top artists and tracks
            top_artists = client.current_user_top_artists(limit=5)
            top_tracks = client.current_user_top_tracks(limit=5)
            
            # Extract seed values for recommendations
            seed_artists = [artist['id'] for artist in top_artists['items']]
            seed_tracks = [track['id'] for track in top_tracks['items']]
            
            # Map emotions to Spotify audio features
            emotion_to_features = {
                'happy': {'min_valence': 0.7, 'min_energy': 0.7, 'min_danceability': 0.7},
                'sad': {'max_valence': 0.3, 'max_energy': 0.3, 'max_danceability': 0.3},
                'angry': {'min_energy': 0.8, 'min_tempo': 120},
                'fearful': {'max_valence': 0.3, 'max_energy': 0.4},
                'neutral': {'min_valence': 0.4, 'max_valence': 0.6, 'min_energy': 0.4, 'max_energy': 0.6},
                'surprised': {'min_energy': 0.6, 'min_valence': 0.5},
                'disgust': {'max_valence': 0.3, 'max_energy': 0.5},
                'calm': {'max_energy': 0.3, 'max_tempo': 100}
            }
            
            # Get the audio features for the emotion
            features = emotion_to_features.get(emotion, {})
            
            # Get recommendations
            recommendations = client.recommendations(
                seed_artists=seed_artists[:2],  # Limit to 2 artists
                seed_tracks=seed_tracks[:2],    # Limit to 2 tracks
                limit=20,
                **features
            )
            
            # Format the recommended tracks
            recommended_tracks_list = []
            for track in recommendations.get('tracks', []):
                try:
                    track_info = {
                        'name': track.get('name'),
                        'artists': [artist['name'] for artist in track.get('artists', [])],
                        'url': track.get('external_urls', {}).get('spotify'),
                        'image': track.get('album', {}).get('images', [{}])[0].get('url') if track.get('album', {}).get('images') else None,
                        'preview_url': track.get('preview_url')
                    }
                    recommended_tracks_list.append(track_info)
                except Exception as e:
                    logger.error(f"Error processing recommended track: {str(e)}")
                    continue
            
            # Structure the response as a list containing a single personalized playlist object
            # This object will now contain the list of recommended tracks
            personalized_playlist = {
                'name': f'Personalized {emotion.capitalize()} Recommendations',
                'url': None, # No single playlist URL for recommendations
                'image': recommended_tracks_list[0].get('image') if recommended_tracks_list else None, # Use first track image as cover
                'tracks': len(recommended_tracks_list), # Still include total count for summary
                'from_api': True,
                'personalized': True,
                'tracks_list': recommended_tracks_list # Include the list of track objects
            }
            
            playlists = [personalized_playlist]
            
            return playlists
        except Exception as e:
            logger.error(f"Error getting personalized recommendations: {str(e)}")
            logger.error(traceback.format_exc())
            # Fall back to non-personalized recommendations
            return self.get_playlist_for_emotion(emotion)
    
    def logout(self, user_id):
        """Log out a user"""
        if user_id in self.user_tokens:
            del self.user_tokens[user_id]
        self.user_sp = None
        return True
    
    def _respect_rate_limit(self):
        """Simple rate limiter to avoid Spotify API rate limits"""
        elapsed = time.time() - self.last_api_call
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_api_call = time.time()
    
    def get_playlist_for_emotion(self, emotion):
        """Get a playlist recommendation based on the detected emotion.
        Now using opposite/complementary emotions for recommendations (e.g. sad -> uplifting)
        """
        logger.info(f"Getting playlist for emotion: {emotion}")
        
        # Map emotions to complementary search terms (mood-boosting approach)
        emotion_to_search_terms = {
            'happy': 'happy upbeat cheerful feel good',  # Happy -> Keep happy
            'sad': 'uplifting motivational positive',    # Sad -> Make happy
            'angry': 'calming peaceful chill',           # Angry -> Calm down
            'fearful': 'comforting relaxing safe',       # Fearful -> Feel safe
            'neutral': 'energetic lively upbeat',        # Neutral -> Energize
            'surprised': 'smooth groove chill',          # Surprised -> Ground
            'disgust': 'beautiful classical piano',      # Disgust -> Beauty
            'calm': 'ambient focus productive'           # Calm -> Maintain calm
        }
        
        # Get the appropriate search term for the detected emotion
        search_term = emotion_to_search_terms.get(emotion, 'relaxing acoustic')
        logger.info(f"Mapped emotion '{emotion}' to search term: '{search_term}'")
        
        # If Spotify client is initialized, search for actual playlists
        if self.sp:
            try:
                logger.info(f"Searching Spotify for: {search_term}")
                
                # Apply rate limiting
                self._respect_rate_limit()
                
                # Search for playlists with explicit parameters
                results = None
                
                try:
                    # Log that we're about to make a Spotify API call
                    logger.info("Making Spotify API call with search term: " + search_term)
                    
                    # Make the actual API call with robust parameters
                    results = self.sp.search(
                        q=search_term, 
                        type='playlist', 
                        limit=10,  # Request more to ensure we get some valid ones
                        market='US'  # Specify a market to ensure results
                    )
                    
                    # Log the keys in the results to debug
                    logger.info(f"Spotify search returned structure with keys: {list(results.keys()) if results else 'None'}")
                    
                    if results and 'playlists' in results:
                        logger.info(f"Found {len(results['playlists']['items'])} playlists from Spotify API")
                    else:
                        logger.warning("No 'playlists' key in Spotify API results")
                
                except Exception as e:
                    logger.error(f"Exception during Spotify search call: {str(e)}")
                    logger.error(traceback.format_exc())
                    results = None
                
                # Check if 'playlists' key exists in results and handle empty results
                if not results or 'playlists' not in results or not results['playlists']['items']:
                    logger.warning("No playlists found from Spotify API, falling back to demo playlists")
                    return self._get_demo_playlists(emotion)
                
                # Format results
                playlists = []
                for item in results['playlists']['items']:
                    try:
                        # Get image URL safely
                        image_url = None
                        if 'images' in item and item['images'] and len(item['images']) > 0:
                            image_url = item['images'][0].get('url')
                        
                        # Get track count safely
                        track_count = 0
                        if 'tracks' in item and isinstance(item['tracks'], dict):
                            track_count = item['tracks'].get('total', 0)
                        
                        # Get external URL safely
                        spotify_url = None
                        if 'external_urls' in item and isinstance(item['external_urls'], dict):
                            spotify_url = item['external_urls'].get('spotify')
                        
                        # Only add the playlist if we have the minimum required info
                        if item.get('name') and spotify_url:
                            playlists.append({
                                'name': item['name'],
                                'url': spotify_url,
                                'image': image_url,
                                'tracks': track_count,
                                'from_api': True  # Mark this as coming from the API
                            })
                    except Exception as e:
                        logger.error(f"Error processing playlist item: {str(e)}")
                        continue
                
                logger.info(f"✅ Extracted {len(playlists)} valid playlists from Spotify API")
                
                # If no valid playlists were found, use demo playlists
                if not playlists:
                    logger.warning("No valid playlists extracted from API results, using demo playlists")
                    return self._get_demo_playlists(emotion)
                
                # Log the playlist names to verify they're real
                playlist_names = [p['name'] for p in playlists[:5]]
                logger.info(f"Returning playlists: {', '.join(playlist_names)}")
                
                return playlists
                
            except Exception as e:
                logger.error(f"❌ Error searching Spotify: {str(e)}")
                logger.error(traceback.format_exc())
                return self._get_demo_playlists(emotion)
        else:
            # Return demo playlists if no Spotify client
            return self._get_demo_playlists(emotion)
    
    def update_credentials(self, client_id, client_secret):
        """Update the Spotify credentials and reinitialize the client"""
        logger.info("Updating Spotify credentials")
        self.client_id = client_id
        self.client_secret = client_secret
        
        # Set environment variables for future use
        os.environ['SPOTIFY_CLIENT_ID'] = client_id
        os.environ['SPOTIFY_CLIENT_SECRET'] = client_secret
        
        # Reinitialize the client
        success = self._init_spotify_client()
        return success
    
    def _get_demo_playlists(self, emotion):
        """Return demo playlists when Spotify API is not available.
        Updated to match the new emotion mapping (mood-boosting approach)
        """
        logger.info(f"Using demo playlists for emotion: {emotion}")
        
        # Map emotions to demo playlists with a random element
        def randomize_playlists(playlist_list):
            # Slightly randomize track numbers and add a random element to names
            suffixes = [' Mix', ' Selection', ' Collection', ' Playlist', ' Radio']
            for p in playlist_list:
                p['tracks'] = max(1, p['tracks'] + random.randint(-5, 5))
                if random.random() > 0.7:  # 30% chance to modify name
                    p['name'] = p['name'] + random.choice(suffixes)
            return playlist_list
        
        # Updated demo playlists to be mood-boosting rather than mood-matching
        demo_playlists = {
            'happy': [
                {
                    'name': 'Happy Hits!',
                    'url': 'https://open.spotify.com/playlist/37i9dQZF1DXdPec7aLTmlC',
                    'image': 'https://i.scdn.co/image/ab67706f00000003bd0e19e810bb4b55ab164a95',
                    'tracks': 50,
                    'from_api': False  # Mark this as a demo playlist
                },
                {
                    'name': 'Good Vibes',
                    'url': 'https://open.spotify.com/playlist/37i9dQZF1DX3rxVfibe1L0',
                    'image': 'https://i.scdn.co/image/ab67706f00000003bd0e19e810bb4b55ab164a95',
                    'tracks': 100,
                    'from_api': False
                }
            ],
            'sad': [
                {
                    'name': 'Mood Booster',
                    'url': 'https://open.spotify.com/playlist/37i9dQZF1DX3rxVfibe1L0',
                    'image': 'https://i.scdn.co/image/ab67706f000000034d26d431869cabfc53c67d8e',
                    'tracks': 50,
                    'from_api': False
                },
                {
                    'name': 'Confidence Boost',
                    'url': 'https://open.spotify.com/playlist/37i9dQZF1DX4fpCWaHpCzD',
                    'image': 'https://i.scdn.co/image/ab67706f000000034d26d431869cabfc53c67d8e',
                    'tracks': 75,
                    'from_api': False
                }
            ],
            'angry': [
                {
                    'name': 'Peaceful Piano',
                    'url': 'https://open.spotify.com/playlist/37i9dQZF1DX4sWSpwq3LiO',
                    'image': 'https://i.scdn.co/image/ab67706f00000003d644502338d33f5fa4156d95',
                    'tracks': 60,
                    'from_api': False
                },
                {
                    'name': 'Calming Acoustics',
                    'url': 'https://open.spotify.com/playlist/37i9dQZF1DWZeKCadgRdKQ',
                    'image': 'https://i.scdn.co/image/ab67706f00000003d644502338d33f5fa4156d95',
                    'tracks': 80,
                    'from_api': False
                }
            ],
            'fearful': [
                {
                    'name': 'Comfort Zone',
                    'url': 'https://open.spotify.com/playlist/37i9dQZF1DX1s9knjP51Oa',
                    'image': 'https://i.scdn.co/image/ab67706f00000003a4a7d5543630e626ff5f8a97',
                    'tracks': 45,
                    'from_api': False
                },
                {
                    'name': 'Cozy Acoustic',
                    'url': 'https://open.spotify.com/playlist/37i9dQZF1DWTwnEm1IYyoj',
                    'image': 'https://i.scdn.co/image/ab67706f00000003a4a7d5543630e626ff5f8a97',
                    'tracks': 55,
                    'from_api': False
                }
            ],
            'neutral': [
                {
                    'name': 'Energy Boost',
                    'url': 'https://open.spotify.com/playlist/37i9dQZF1DX8a1tdzq5tbM',
                    'image': 'https://i.scdn.co/image/ab67706f00000003f79c33a0e63041630e5b2efe',
                    'tracks': 65,
                    'from_api': False
                },
                {
                    'name': 'Workout Beats',
                    'url': 'https://open.spotify.com/playlist/37i9dQZF1DX76Wlfdnj7AP',
                    'image': 'https://i.scdn.co/image/ab67706f00000003f79c33a0e63041630e5b2efe',
                    'tracks': 70,
                    'from_api': False
                }
            ],
            'surprised': [
                {
                    'name': 'Chill Vibes',
                    'url': 'https://open.spotify.com/playlist/37i9dQZF1DX8a1tdzq5tbM',
                    'image': 'https://i.scdn.co/image/ab67706f000000030bee51aad6c0af4ba5cdee33',
                    'tracks': 55,
                    'from_api': False
                },
                {
                    'name': 'Focus Flow',
                    'url': 'https://open.spotify.com/playlist/37i9dQZF1DX4fpCWaHpCzD',
                    'image': 'https://i.scdn.co/image/ab67706f000000030bee51aad6c0af4ba5cdee33',
                    'tracks': 50,
                    'from_api': False
                }
            ],
            'calm': [
                {
                    'name': 'Deep Focus',
                    'url': 'https://open.spotify.com/playlist/37i9dQZF1DX3Ogo9pFvBkY',
                    'image': 'https://i.scdn.co/image/ab67706f00000003e4eadd5b72d749c8ef25300d',
                    'tracks': 40,
                    'from_api': False
                },
                {
                    'name': 'Productive Morning',
                    'url': 'https://open.spotify.com/playlist/37i9dQZF1DX6T5dWVMqUt3',
                    'image': 'https://i.scdn.co/image/ab67706f00000003e4eadd5b72d749c8ef25300d',
                    'tracks': 75,
                    'from_api': False
                }
            ]
        }
        
        # Return playlists for the detected emotion or a default set
        playlists = demo_playlists.get(emotion, demo_playlists.get('neutral', []))
        playlists = randomize_playlists(playlists.copy())  # Make a copy to avoid modifying the original
        logger.info(f"Returning {len(playlists)} demo playlists")
        return playlists

    def get_realtime_tracks(self, emotion, limit=5):
        """Get tracks for real-time emotion detection
        Returns individual tracks instead of playlists for dynamic playlist building
        """
        logger.info(f"Getting real-time tracks for emotion: {emotion}")
        
        # Map emotions to complementary search terms (mood-boosting approach)
        emotion_to_search_terms = {
            'happy': 'happy upbeat cheerful feel good',  # Happy -> Keep happy
            'sad': 'uplifting motivational positive',    # Sad -> Make happy
            'angry': 'calming peaceful chill',           # Angry -> Calm down
            'fearful': 'comforting relaxing safe',       # Fearful -> Feel safe
            'neutral': 'energetic lively upbeat',        # Neutral -> Energize
            'surprised': 'smooth groove chill',          # Surprised -> Ground
            'disgust': 'beautiful classical piano',      # Disgust -> Beauty
            'calm': 'ambient focus productive'           # Calm -> Maintain calm
        }
        
        # Get the appropriate search term for the detected emotion
        search_term = emotion_to_search_terms.get(emotion, 'relaxing acoustic')
        logger.info(f"Mapped emotion '{emotion}' to search term: '{search_term}'")
        
        # If Spotify client is initialized, search for actual tracks
        if self.sp:
            try:
                logger.info(f"Searching Spotify for tracks: {search_term}")
                
                # Apply rate limiting
                self._respect_rate_limit()
                
                # Search for tracks with explicit parameters
                try:
                    # Make the actual API call
                    results = self.sp.search(
                        q=search_term, 
                        type='track', 
                        limit=limit,
                        market='US'
                    )
                    
                    # Log the success
                    if results and 'tracks' in results:
                        logger.info(f"Found {len(results['tracks']['items'])} tracks from Spotify API")
                    else:
                        logger.warning("No 'tracks' key in Spotify API results")
                        return self._get_demo_tracks(emotion)
                    
                    # Format track results
                    tracks = []
                    for item in results['tracks']['items']:
                        try:
                            # Get artist names
                            artists = [artist['name'] for artist in item['artists']] if 'artists' in item else []
                            
                            # Get album image URL
                            image_url = None
                            if 'album' in item and 'images' in item['album'] and item['album']['images']:
                                image_url = item['album']['images'][0].get('url')
                            
                            # Get track URL
                            track_url = None
                            if 'external_urls' in item and 'spotify' in item['external_urls']:
                                track_url = item['external_urls']['spotify']
                            
                            # Get track preview URL
                            preview_url = item.get('preview_url')
                            
                            # Only add the track if we have the minimum required info
                            if item.get('name') and track_url:
                                tracks.append({
                                    'id': item.get('id'),
                                    'name': item.get('name'),
                                    'artists': artists,
                                    'album': item.get('album', {}).get('name'),
                                    'image': image_url,
                                    'url': track_url,
                                    'preview_url': preview_url,
                                    'duration_ms': item.get('duration_ms', 0),
                                    'emotion': emotion,
                                    'from_api': True
                                })
                        except Exception as e:
                            logger.error(f"Error processing track item: {str(e)}")
                            continue
                    
                    logger.info(f"✅ Extracted {len(tracks)} valid tracks from Spotify API")
                    
                    # If no valid tracks were found, use demo tracks
                    if not tracks:
                        logger.warning("No valid tracks extracted from API results, using demo tracks")
                        return self._get_demo_tracks(emotion)
                    
                    return tracks
                    
                except Exception as e:
                    logger.error(f"Exception during Spotify search call: {str(e)}")
                    logger.error(traceback.format_exc())
                    return self._get_demo_tracks(emotion)
                
            except Exception as e:
                logger.error(f"❌ Error searching Spotify for tracks: {str(e)}")
                logger.error(traceback.format_exc())
                return self._get_demo_tracks(emotion)
        else:
            # Return demo tracks if no Spotify client
            return self._get_demo_tracks(emotion)

    def _get_demo_tracks(self, emotion):
        """Get demo tracks for real-time emotion detection when Spotify API is not available"""
        logger.info(f"Using demo tracks for emotion: {emotion}")
        
        # Demo tracks for different emotions
        demo_tracks = {
            'happy': [
                {
                    'id': '1',
                    'name': 'Happy Together',
                    'artists': ['The Turtles'],
                    'album': 'Happy Days',
                    'image': 'https://i.scdn.co/image/ab67616d0000b2736c5c2425b9d68c0977fb99a7',
                    'url': 'https://open.spotify.com/track/1JO1xLtVc8mWhIoE3YaCL0',
                    'preview_url': None,
                    'duration_ms': 180000,
                    'emotion': 'happy',
                    'from_api': False
                },
                {
                    'id': '2',
                    'name': 'Walking On Sunshine',
                    'artists': ['Katrina & The Waves'],
                    'album': 'Greatest Hits',
                    'image': 'https://i.scdn.co/image/ab67616d0000b2736c5c2425b9d68c0977fb99a7',
                    'url': 'https://open.spotify.com/track/05wIrZSwuaVWhcv5FfqeH0',
                    'preview_url': None,
                    'duration_ms': 210000,
                    'emotion': 'happy',
                    'from_api': False
                },
                {
                    'id': '3',
                    'name': 'Can\'t Stop the Feeling!',
                    'artists': ['Justin Timberlake'],
                    'album': 'Trolls',
                    'image': 'https://i.scdn.co/image/ab67616d0000b2736c5c2425b9d68c0977fb99a7',
                    'url': 'https://open.spotify.com/track/1WkMMavIMc4JZ8cfMmxHkI',
                    'preview_url': None,
                    'duration_ms': 230000,
                    'emotion': 'happy',
                    'from_api': False
                },
            ],
            'sad': [
                {
                    'id': '4',
                    'name': 'Rise Up',
                    'artists': ['Andra Day'],
                    'album': 'Inspiration',
                    'image': 'https://i.scdn.co/image/ab67616d0000b273db887a462f714d10ed14a8a3',
                    'url': 'https://open.spotify.com/track/1sJkIpzj9Uy6PsKYpjSYDJ',
                    'preview_url': None,
                    'duration_ms': 240000,
                    'emotion': 'sad',
                    'from_api': False
                },
                {
                    'id': '5',
                    'name': 'Fight Song',
                    'artists': ['Rachel Platten'],
                    'album': 'Motivation',
                    'image': 'https://i.scdn.co/image/ab67616d0000b273db887a462f714d10ed14a8a3',
                    'url': 'https://open.spotify.com/track/0xCiTTagXfOJJiGTnkzXXN',
                    'preview_url': None,
                    'duration_ms': 200000,
                    'emotion': 'sad',
                    'from_api': False
                },
            ],
            'angry': [
                {
                    'id': '6',
                    'name': 'Weightless',
                    'artists': ['Marconi Union'],
                    'album': 'Calm',
                    'image': 'https://i.scdn.co/image/ab67616d0000b2732f8f5ee4bfd273e6ee5a40b5',
                    'url': 'https://open.spotify.com/track/3nozxoXDGZSP1P3hIbYJvK',
                    'preview_url': None,
                    'duration_ms': 360000,
                    'emotion': 'angry',
                    'from_api': False
                },
                {
                    'id': '7',
                    'name': 'Breathe Me',
                    'artists': ['Sia'],
                    'album': 'Peaceful',
                    'image': 'https://i.scdn.co/image/ab67616d0000b2732f8f5ee4bfd273e6ee5a40b5',
                    'url': 'https://open.spotify.com/track/5UiWdnQIpJUwJXPJfg8lgm',
                    'preview_url': None,
                    'duration_ms': 260000,
                    'emotion': 'angry',
                    'from_api': False
                },
            ],
            'neutral': [
                {
                    'id': '8',
                    'name': 'Uptown Funk',
                    'artists': ['Mark Ronson', 'Bruno Mars'],
                    'album': 'Energy',
                    'image': 'https://i.scdn.co/image/ab67616d0000b2738410fc89ea4e2f951a410cf7',
                    'url': 'https://open.spotify.com/track/32OlwWuMpZ6b0aN2RZOeMS',
                    'preview_url': None,
                    'duration_ms': 270000,
                    'emotion': 'neutral',
                    'from_api': False
                },
                {
                    'id': '9',
                    'name': 'Can\'t Hold Us',
                    'artists': ['Macklemore & Ryan Lewis'],
                    'album': 'Active',
                    'image': 'https://i.scdn.co/image/ab67616d0000b2738410fc89ea4e2f951a410cf7',
                    'url': 'https://open.spotify.com/track/3bidbhpOYeV4knLkAg5T5b',
                    'preview_url': None,
                    'duration_ms': 250000,
                    'emotion': 'neutral',
                    'from_api': False
                },
            ]
        }
        
        # Return tracks for the detected emotion or a default set
        tracks = demo_tracks.get(emotion, demo_tracks.get('happy', []))
        
        # Add some randomization
        for track in tracks:
            # Slight variation in duration
            track['duration_ms'] = track['duration_ms'] + random.randint(-10000, 10000)
        
        # Shuffle the list to get different order each time
        random.shuffle(tracks)
        
        logger.info(f"Returning {len(tracks)} demo tracks")
        return tracks

    EMOTION_TO_MOOD = {
        'sad': 'emotional soft',
        'happy': 'lively energetic',
        'energetic': 'upbeat powerful',
        'angry': 'calm relaxing',
        'fearful': 'comforting safe',
        'neutral': 'chill balanced',
        'surprised': 'exciting fresh',
        'disgust': 'beautiful soothing',
        'calm': 'peaceful ambient',
    }

    def get_emotion_personalized_playlist(self, user_id, emotion):
        client = self._init_user_client(user_id)
        if not client:
            logger.info(f"[PERSONALIZED] User not authenticated: {user_id}")
            return {'type': 'error', 'message': 'User not authenticated'}
        mood = self.EMOTION_TO_MOOD.get(emotion, 'mood')
        try:
            top_artists = client.current_user_top_artists(limit=3)['items']
            artist_names = [a['name'] for a in top_artists]
            logger.info(f"[PERSONALIZED] Top artists for user {user_id}: {artist_names}")
            search_terms = [f"{artist['name']} {mood} playlist" for artist in top_artists]
            logger.info(f"[PERSONALIZED] Search terms: {search_terms}")
            # Try to find a playlist for each search term
            personalized_playlists = []
            found_playlist = None
            for search_term in search_terms:
                logger.info(f"[PERSONALIZED] Searching for playlist with term: {search_term}")
                results = client.search(q=search_term, type='playlist,track', limit=10)
                playlists = results.get('playlists', {}).get('items', [])
                if playlists:
                    playlist = playlists[0]
                    logger.info(f"[PERSONALIZED] Found playlist: {playlist.get('name')}")
                    personalized_playlists.append({
                        'name': playlist.get('name'),
                        'url': playlist.get('external_urls', {}).get('spotify'),
                        'image': playlist.get('images', [{}])[0].get('url') if playlist.get('images') else None,
                        'tracks': playlist.get('tracks', {}).get('total', 0),
                        'from_api': True
                    })
                    found_playlist = True
                    break
                else:
                    tracks = results.get('tracks', {}).get('items', [])
                    logger.info(f"[PERSONALIZED] No playlist found for term: {search_term}")
                    if tracks:
                        logger.info(f"[PERSONALIZED] Tracks found: count={len(tracks)}, first_track_type={type(tracks[0])}, first_track_keys={list(tracks[0].keys())}")
                    else:
                        logger.info(f"[PERSONALIZED] No tracks found for term: {search_term}")
            # If no playlist found, fetch up to 10 tracks for those terms
            if not found_playlist:
                tracks = []
                for term in search_terms:
                    logger.info(f"[PERSONALIZED] Searching for tracks with term: {term}")
                    track_results = client.search(q=term, type='track', limit=10)
                    for track in track_results.get('tracks', {}).get('items', []):
                        tracks.append({
                            'name': track.get('name'),
                            'artists': [a['name'] for a in track.get('artists', [])],
                            'url': track.get('external_urls', {}).get('spotify'),
                            'image': track.get('album', {}).get('images', [{}])[0].get('url') if track.get('album', {}).get('images') else None
                        })
                        if len(tracks) >= 10:
                            break
                    if len(tracks) >= 10:
                        break
                if tracks:
                    logger.info(f"[PERSONALIZED] Returning custom track list with {len(tracks)} tracks.")
                    personalized_playlists.append({
                        'name': 'Most Recommended Songs According to Your Taste',
                        'custom': True,
                        'tracks_list': tracks
                    })
            # Always add 1-2 generic playlists to the result
            generic_playlists = self.get_playlist_for_emotion(emotion)
            logger.info(f"[PERSONALIZED] Adding {min(2, len(generic_playlists))} generic playlists to personalized result.")
            for g in generic_playlists[:2]:
                personalized_playlists.append(g)
            if personalized_playlists:
                return {'type': 'multi', 'playlists': personalized_playlists}
            logger.info(f"[PERSONALIZED] No playlists or tracks found for user {user_id} and emotion {emotion}.")
            return {'type': 'error', 'message': 'No playlists or tracks found.'}
        except Exception as e:
            logger.error(f"Error in get_emotion_personalized_playlist: {str(e)}")
            logger.error(traceback.format_exc())
            return {'type': 'error', 'message': str(e)}