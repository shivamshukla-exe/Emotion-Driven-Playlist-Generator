# Emotion-Based Playlist Generator 🎵

## What is this project? 

This is a smart music playlist generator that creates playlists based on your emotions! Whether you're feeling happy, sad, angry, anxious, or surprised, this application will suggest songs that match your mood.

## How does it work? 

1. **Text Analysis**: The system can analyze text (like your social media posts, journal entries, or any text you provide) to detect your current emotional state.
2. **Emotion Detection**: Using advanced text analysis, it identifies emotions like:
   - 😊 Happy
   - 😢 Sad
   - 😠 Angry
   - 😰 Anxious
   - 😲 Surprised
   - 😐 Neutral
3. **Playlist Generation**: Based on your detected emotion, it creates a personalized playlist of songs that match your mood.

## Features 

- **Smart Text Analysis**: Understands context, emojis, and common expressions
- **Emotion Recognition**: Detects subtle emotional cues in your text
- **Personalized Playlists**: Creates mood-matching music recommendations
- **User-Friendly Interface**: Easy to use, no technical knowledge required

## Getting Started 

### Prerequisites
- Python 3.8 or higher
- A modern web browser

### Installation

1. Clone this repository
2. Run the installation script:
   ```
   python install_dependencies.py
   ```
3. Start the application:
   ```
   python run.py
   ```

## Project Structure 

- `frontend/`: Contains the user interface code
- `backend/`: Contains the emotion detection and playlist generation logic
  - `models/`: Contains the emotion detection models
  - `services/`: Contains the playlist generation services

## How to Use 

1. Open the application in your web browser
2. Enter your text or select a source for emotion analysis
3. Wait for the emotion detection
4. Get your personalized playlist!


## License 📄

This project is licensed under the MIT License - see the LICENSE file for details.

