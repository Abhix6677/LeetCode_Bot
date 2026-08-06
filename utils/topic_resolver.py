import logging
import difflib
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class TopicResolver:
    # Official topics supported by the bot
    VALID_TOPICS = [
        "Array", "Linked List", "Tree", "Graph", "Stack", "Queue", 
        "HashMap", "Two Pointer", "Sliding Window", "Binary Search", 
        "Dynamic Programming", "Design", "General"
    ]
    
    # Aliases mapping common abbreviations and plurals to official topics
    ALIASES = {
        "dp": "Dynamic Programming",
        "ll": "Linked List",
        "bst": "Tree",
        "bs": "Binary Search",
        "arrays": "Array",
        "strings": "String",
        "graphs": "Graph",
        "trees": "Tree",
        "hashmap": "HashMap",
        "hash map": "HashMap",
        "hash table": "HashMap",
        "hashtable": "HashMap",
        "two pointers": "Two Pointer",
        "two-pointer": "Two Pointer",
        "two-pointers": "Two Pointer",
        "2 pointer": "Two Pointer",
        "sliding-window": "Sliding Window",
        "slidingwindow": "Sliding Window",
        "dynamic-programming": "Dynamic Programming",
        "dynamicprogramming": "Dynamic Programming"
    }

    @classmethod
    def normalize(cls, text: str) -> str:
        """Lowercase and remove extra spaces."""
        return " ".join(text.lower().strip().split())

    @classmethod
    def resolve_topic(cls, user_input: str) -> Dict:
        """
        Resolves a user-provided topic string to a valid topic using exact matching,
        aliases, and fuzzy matching.
        """
        original_input = user_input
        normalized = cls.normalize(user_input)
        
        # 1. Exact Match against Valid Topics
        for valid_topic in cls.VALID_TOPICS:
            if normalized == valid_topic.lower():
                logger.info(f"Topic Resolution: '{original_input}' -> '{normalized}' -> Exact Match -> '{valid_topic}'")
                return {"status": "exact", "topic": valid_topic}
                
        # 2. Alias Match
        if normalized in cls.ALIASES:
            matched_topic = cls.ALIASES[normalized]
            logger.info(f"Topic Resolution: '{original_input}' -> '{normalized}' -> Alias Match -> '{matched_topic}'")
            return {"status": "exact", "topic": matched_topic}
            
        # 3. Fuzzy Matching
        # We will check both valid topics and aliases
        best_match = None
        best_score = 0
        all_scores = []
        
        # Check against valid topics
        for valid_topic in cls.VALID_TOPICS:
            score = difflib.SequenceMatcher(None, normalized, valid_topic.lower()).ratio() * 100
            all_scores.append((valid_topic, score))
            if score > best_score:
                best_score = score
                best_match = valid_topic
                
        # Check against aliases
        for alias, mapped_topic in cls.ALIASES.items():
            score = difflib.SequenceMatcher(None, normalized, alias).ratio() * 100
            # If an alias matches well, we map it to the actual topic
            all_scores.append((mapped_topic, score))
            if score > best_score:
                best_score = score
                best_match = mapped_topic
                
        # Sort all scores descending and remove duplicates while preserving order
        all_scores.sort(key=lambda x: x[1], reverse=True)
        unique_suggestions = []
        for topic, score in all_scores:
            if topic not in unique_suggestions and score >= 40: # Only suggest reasonable matches
                unique_suggestions.append(topic)
                if len(unique_suggestions) == 5:
                    break
                    
        # If similarity >= 85%, accept it automatically
        if best_score >= 85:
            logger.info(f"Topic Resolution: '{original_input}' -> '{normalized}' -> Fuzzy Match ({best_score:.1f}%) -> '{best_match}'")
            return {"status": "fuzzy", "topic": best_match}
            
        # Otherwise, return ambiguity with suggestions
        logger.info(f"Topic Resolution: '{original_input}' -> '{normalized}' -> Ambiguous (Best score {best_score:.1f}%) -> Suggested: {unique_suggestions}")
        if unique_suggestions:
            return {"status": "ambiguous", "options": unique_suggestions}
        else:
            return {"status": "not_found", "options": cls.VALID_TOPICS[:5]}
