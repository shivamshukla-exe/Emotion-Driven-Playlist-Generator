import subprocess
import sys
import os

def install_dependencies():
    """Install all the required dependencies for the improved emotion detection models."""
    print("Installing dependencies for emotion detection project...")
    
    # List of dependencies to install
    dependencies = [
        "flask",
        "flask-cors",
        "numpy",
        "librosa==0.10.1",
        "opencv-python",
        "scikit-learn",
        "tensorflow",
        "spotipy",
        "deepface",
        "soundfile==0.12.1",
        "joblib",
        "scipy==1.10.1",
        "pillow==9.5.0"
    ]
    
    # Create model cache directory if it doesn't exist
    os.makedirs("backend/models/model_cache", exist_ok=True)
    
    # Install each dependency
    for dependency in dependencies:
        try:
            print(f"Installing {dependency}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", dependency])
            print(f"Successfully installed {dependency}")
        except subprocess.CalledProcessError as e:
            print(f"Error installing {dependency}: {e}")
    
    print("\nAll dependencies installed. You can now run the application.")
    print("\nTo start the backend server: python backend/app.py")
    print("To start the frontend (in a separate terminal): cd frontend && npm start")

if __name__ == "__main__":
    install_dependencies() 