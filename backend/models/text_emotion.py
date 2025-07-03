import re
import logging
import os
import json
import random
from collections import Counter

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("text_emotion")

class TextEmotionDetector:
    """Class for detecting emotions from text input"""
    
    def __init__(self):
        """Initialize the text emotion detector with emotion lexicons"""
        logger.info("Initializing text emotion detector")
        
        # Create a model cache directory if it doesn't exist
        self.model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'model_cache')
        os.makedirs(self.model_dir, exist_ok=True)
        
        # Load emotion lexicons
        self.emotion_lexicons = self._load_emotion_lexicons()
        
        # Load intensifiers and negation words
        self.intensifiers = set([
            'very', 'extremely', 'incredibly', 'really', 'so', 'too', 'absolutely',
            'completely', 'totally', 'utterly', 'quite', 'particularly', 'especially',
            'exceedingly', 'immensely', 'terribly', 'awfully', 'super', 'extra',
            'remarkably', 'unusually', 'exceptionally', 'decidedly', 'enormously',
            'drastically', 'intensely', 'highly', 'amazingly'
        ])
        
        self.negation_words = set([
            'not', 'no', "n't", 'never', 'neither', 'nor', 'none', 'nobody', 'nothing',
            'nowhere', 'hardly', 'scarcely', 'barely', 'rarely', 'seldom', 'few', 'little'
        ])
        
        # Default weights for different analysis methods
        self.weights = {
            'lexicon': 0.7,
            'pattern': 0.3
        }
        
        logger.info("Text emotion detector initialized successfully")
    
    def _load_emotion_lexicons(self):
        """Load emotion lexicons from files or use default built-in ones"""
        # Default emotion lexicons if files are not available
        lexicons = {
            'happy': [
                'happy', 'joy', 'joyful', 'glad', 'pleased', 'delighted', 'content', 'cheerful', 
                'merry', 'jolly', 'lively', 'thrilled', 'elated', 'excited', 'ecstatic', 'satisfied',
                'wonderful', 'great', 'excellent', 'amazing', 'fantastic', 'terrific', 'awesome',
                'love', 'loving', 'lovely', 'smile', 'smiling', 'laugh', 'laughing', 'haha', 'fun',
                'enjoy', 'enjoying', 'pleased', 'pleasant', 'blessing', 'blessed', 'positive',
                'optimistic', 'hopeful', 'encouraged', 'encouraging', 'yay', 'hurray', 'hurrah'
            ],
            'sad': [
                'sad', 'unhappy', 'sorrowful', 'depressed', 'downcast', 'miserable', 'heartbroken',
                'gloomy', 'downhearted', 'down', 'low', 'blue', 'melancholy', 'somber', 'morose',
                'dismal', 'disappointed', 'upset', 'distressed', 'despair', 'grief', 'sorrow',
                'crying', 'cry', 'tear', 'tears', 'weep', 'weeping', 'sob', 'sobbing', 'despair',
                'despairing', 'despondent', 'hopeless', 'dejected', 'regret', 'regretful', 'miss',
                'missing', 'lonely', 'alone', 'lonesome', 'abandoned', 'isolated', 'unwanted',
                'unloved', 'disheartened', 'devastated', 'crushed'
            ],
            'angry': [
                'angry', 'anger', 'mad', 'furious', 'enraged', 'outraged', 'irate', 'annoyed',
                'irritated', 'aggravated', 'agitated', 'exasperated', 'indignant', 'vexed', 'irked',
                'offended', 'insulted', 'provoked', 'hostile', 'bitter', 'hate', 'hatred', 'despise',
                'resent', 'resentment', 'temper', 'rage', 'wrath', 'fury', 'ferocious', 'fierce',
                'heated', 'livid', 'infuriated', 'incensed', 'disgusted', 'frustrated', 'fuming',
                'seething', 'raging', 'explosive', 'fight', 'fighting', 'argument', 'arguing',
                'conflict', 'confrontation', 'damn', 'darn', 'sucks', 'terrible', 'awful'
            ],
            'anxious': [
                'anxious', 'anxiety', 'worried', 'worry', 'nervous', 'stressed', 'stress',
                'tense', 'uneasy', 'afraid', 'scared', 'frightened', 'fearful', 'terrified',
                'panicked', 'panic', 'apprehensive', 'concerned', 'distressed', 'alarmed',
                'troubled', 'bothered', 'disturbed', 'restless', 'jittery', 'edgy', 'jumpy',
                'agitated', 'perturbed', 'fretting', 'fretful', 'overwrought', 'unsettled',
                'uncomfortable', 'on edge', 'uptight', 'freaking out', 'dreading', 'horror',
                'horrified', 'suspicious', 'paranoid', 'intimidated', 'threatened', 'helpless',
                'vulnerable', 'insecure', 'uncertain', 'doubt', 'doubting', 'hesitant'
            ],
            'surprised': [
                'surprised', 'surprise', 'astonished', 'amazed', 'shocked', 'startled',
                'stunned', 'astounded', 'dumbfounded', 'speechless', 'awestruck', 'taken aback',
                'unexpected', 'sudden', 'unforeseen', 'unpredicted', 'out of blue', 'disbelief',
                'bewildered', 'perplexed', 'baffled', 'confused', 'flabbergasted', 'wow',
                'whoa', 'omg', 'oh my god', 'oh my', 'gosh', 'goodness', 'unbelievable', 'incredible'
            ],
            'neutral': [
                'okay', 'ok', 'fine', 'alright', 'neutral', 'indifferent', 'whatever', 'meh',
                'moderate', 'mediocre', 'average', 'ordinary', 'standard', 'common', 'regular',
                'typical', 'normal', 'usual', 'routine', 'everyday', 'stable', 'steady',
                'balanced', 'fair', 'reasonable', 'acceptable', 'tolerable', 'passable',
                'adequate', 'sufficient', 'satisfactory'
            ]
        }
        
        # Check if we have json lexicon files in model_cache
        lexicon_path = os.path.join(self.model_dir, "emotion_lexicons.json")
        
        if os.path.exists(lexicon_path):
            try:
                logger.info(f"Loading emotion lexicons from {lexicon_path}")
                with open(lexicon_path, 'r') as f:
                    loaded_lexicons = json.load(f)
                
                # Validate structure
                if all(emotion in loaded_lexicons for emotion in ['happy', 'sad', 'angry', 'anxious', 'surprised', 'neutral']):
                    logger.info("Successfully loaded emotion lexicons")
                    return loaded_lexicons
                else:
                    logger.warning("Loaded lexicons missing required emotions, using default")
            except Exception as e:
                logger.error(f"Error loading lexicons: {str(e)}")
                logger.info("Using default emotion lexicons")
        else:
            logger.info("No custom lexicons found, using default emotion lexicons")
            
            # Save default lexicons for future use
            try:
                with open(lexicon_path, 'w') as f:
                    json.dump(lexicons, f, indent=2)
                logger.info(f"Default lexicons saved to {lexicon_path}")
            except Exception as e:
                logger.error(f"Error saving default lexicons: {str(e)}")
        
        return lexicons
    
    def detect_emotion(self, text):
        """Detect emotion from text using a combination of lexicon-based and pattern-based approaches"""
        if not text or not text.strip():
            logger.warning("Empty text received, returning neutral")
            return "neutral"
        
        logger.info(f"Detecting emotion from text: {text[:50]}...")
        
        # Normalize text
        processed_text = self._preprocess_text(text)
        
        # Lexicon-based approach - count emotion words
        lexicon_scores = self._lexicon_analysis(processed_text)
        
        # Pattern-based approach - look for specific patterns
        pattern_scores = self._pattern_analysis(processed_text, text)
        
        # Combine scores using weights
        combined_scores = {}
        for emotion in lexicon_scores:
            combined_scores[emotion] = (
                self.weights['lexicon'] * lexicon_scores[emotion] +
                self.weights['pattern'] * pattern_scores.get(emotion, 0)
            )
        
        # Get the emotion with the highest score
        if not combined_scores or max(combined_scores.values(), default=0) == 0:
            logger.info("No significant emotion detected, defaulting to neutral")
            return "neutral"
        
        detected_emotion = max(combined_scores.items(), key=lambda x: x[1])[0]
        logger.info(f"Detected emotion: {detected_emotion} with score {combined_scores[detected_emotion]:.2f}")
        
        # Map to simplified emotions for consistency with other detectors
        simplified_emotion = self._map_to_simplified_emotion(detected_emotion)
        if simplified_emotion != detected_emotion:
            logger.info(f"Mapped to simplified emotion: {simplified_emotion}")
        
        return simplified_emotion
    
    def _preprocess_text(self, text):
        """Preprocess text by converting to lowercase and tokenizing"""
        # Convert to lowercase
        text = text.lower()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Separate punctuation from words for better tokenization
        text = re.sub(r'([.,!?;])', r' \1 ', text)
        
        return text
    
    def _lexicon_analysis(self, text):
        """Analyze text using emotion lexicons"""
        words = text.split()
        
        # Initialize scores
        scores = {emotion: 0 for emotion in self.emotion_lexicons}
        
        # Analyze text word by word with context
        negate = False
        intensify = 1.0
        
        for i, word in enumerate(words):
            # Check if word is a negation
            if word in self.negation_words:
                negate = True
                continue
                
            # Check if word is an intensifier
            if word in self.intensifiers:
                intensify = 2.0
                continue
            
            # Reset negation after punctuation
            if word in '.!?;':
                negate = False
                intensify = 1.0
                continue
            
            # Check each emotion lexicon
            for emotion, lexicon in self.emotion_lexicons.items():
                if word in lexicon:
                    # Apply negation and intensification
                    modifier = -0.5 if negate else 1.0
                    scores[emotion] += modifier * intensify
                    
                    # Reset modifiers after use
                    negate = False
                    intensify = 1.0
                    break
        
        # Normalize scores
        max_score = max(scores.values(), default=0)
        if max_score > 0:
            scores = {e: s/max_score for e, s in scores.items()}
            
        return scores
    
    def _pattern_analysis(self, processed_text, original_text):
        """Analyze text using patterns like emojis, punctuation, capitalization"""
        scores = {emotion: 0 for emotion in self.emotion_lexicons}
        
        # Check for happy patterns
        if re.search(r'(\:|\=)(\-|\s)?(\)|\]|D|\})', processed_text):  # :) :D =) etc.
            scores['happy'] += 1
            
        if re.search(r'(haha|hehe|lol|lmao|rofl|lmfao)', processed_text):
            scores['happy'] += 0.8
            
        # Check for sad patterns
        if re.search(r'(\:|\=)(\-|\s)?(\(|\[|\\|\/)', processed_text):  # :( =( etc.
            scores['sad'] += 1
            
        if re.search(r'(\;\(|\;\-\()', processed_text):  # ;( ;-(
            scores['sad'] += 0.8
            
        # Check for angry patterns
        if re.search(r'(\>\:\(|\>\-\:|\>\:|\>\<)', processed_text):  # >:( >:< etc.
            scores['angry'] += 1
            
        if re.search(r'(\!\!\!+|\?\?\?+)', processed_text):  # !!! ???
            scores['angry'] += 0.4
            scores['surprised'] += 0.4
        
        # Check for surprised patterns - FIX: properly escape 'O' as a literal character
        if re.search(r'(:\s*[oO0]|=\s*[oO0])', processed_text):  # :O :0 =O etc.
            scores['surprised'] += 1
        
        # Check for anxious patterns
        if re.search(r'(:\s*[sS]|[sS]\s*:)', processed_text):  # :S S: etc.
            scores['anxious'] += 0.7
            
        # Check for multiple exclamation or question marks
        exclamation_count = len(re.findall(r'!', processed_text))
        if exclamation_count > 2:
            scores['excited'] = 0.3 * min(exclamation_count, 5)
            scores['angry'] += 0.2 * min(exclamation_count, 5)
            
        # Check for ALL CAPS (shouting)
        caps_ratio = sum(1 for c in original_text if c.isupper()) / max(len(original_text.replace(" ", "")), 1)
        if caps_ratio > 0.5 and len(original_text) > 10:
            scores['angry'] += 0.7
            scores['excited'] += 0.3
            
        # Normalize scores
        max_score = max(scores.values(), default=0)
        if max_score > 0:
            scores = {e: s/max_score for e, s in scores.items()}
            
        return scores
    
    def _map_to_simplified_emotion(self, emotion):
        """Map detailed emotions to simplified categories for consistency"""
        # Mapping of detailed emotions to simplified categories
        simplified_map = {
            'happy': 'happy',
            'joyful': 'happy',
            'excited': 'happy',
            'elated': 'happy',
            'content': 'happy',
            
            'sad': 'sad',
            'unhappy': 'sad',
            'depressed': 'sad',
            'disappointed': 'sad',
            'melancholy': 'sad',
            
            'angry': 'angry',
            'annoyed': 'angry',
            'irritated': 'angry',
            'furious': 'angry',
            
            'anxious': 'anxious',
            'worried': 'anxious',
            'nervous': 'anxious',
            'stressed': 'anxious',
            'fearful': 'anxious',
            
            'surprised': 'surprised',
            'shocked': 'surprised',
            'astonished': 'surprised',
            'amazed': 'surprised',
            
            'neutral': 'neutral'
        }
        
        # Return the simplified emotion or the original if not in the map
        return simplified_map.get(emotion, emotion)