import json
import os
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from utils.leetcode_api import LeetCodeAPI

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TaskGenerator:
    def __init__(self, progress_dir: str = "database"):
        self.leetcode_api = LeetCodeAPI()
        self.progress_dir = progress_dir
        # Ensure the progress directory exists on startup
        os.makedirs(self.progress_dir, exist_ok=True)
        self.dsa_progression = [
            "Array", "HashMap", "Two Pointer", "Sliding Window", "Stack",
            "Queue", "Linked List", "Binary Search", "Tree", "Graph", "Dynamic Programming"
        ]
    
    def _get_progress_file(self, user_id: int) -> str:
        """Get the progress file path for a specific user"""
        return f"{self.progress_dir}/user_{user_id}.json"
    
    def load_progress(self, user_id: int = 1) -> Dict:
        """Load user progress from JSON file"""
        progress_file = self._get_progress_file(user_id)
        try:
            with open(progress_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            return {"solved_questions": [], "streak": 0, "last_question_date": None, "daily_tasks": None, "daily_tasks_date": None}
        except Exception as e:
            logger.error(f"Unexpected error loading progress: {e}")
            return {"solved_questions": [], "streak": 0, "last_question_date": None, "daily_tasks": None, "daily_tasks_date": None}
    
    def save_progress(self, progress: Dict, user_id: int = 1):
        """Save user progress to JSON file"""
        progress_file = self._get_progress_file(user_id)
        try:
            os.makedirs(self.progress_dir, exist_ok=True)
            with open(progress_file, 'w') as f:
                json.dump(progress, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving progress: {e}")
            raise
    
    def get_daily_tasks(self, user_id: int = 1) -> Optional[Dict]:
        """Get today's task (single random question). Returns cached task if same day,
        otherwise generates a new one. Resets at 11:59 PM each day."""
        progress = self.load_progress(user_id)
        
        # Get today's date string
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # Check if we already have a task for today
        if progress.get("daily_tasks") and progress.get("daily_tasks_date") == today_str:
            return progress["daily_tasks"][0] if progress["daily_tasks"] else None
        
        # Generate new task for today - any difficulty, any topic (random)
        solved_numbers = [q["number"] for q in progress.get("solved_questions", [])]
        
        # Pick a random difficulty
        difficulty = random.choice(["Easy", "Medium", "Hard"])
        
        # Fetch one random problem from any topic
        problem_list = self.leetcode_api.get_random_problems(difficulty, None, solved_numbers)
        daily_task = problem_list[0] if problem_list else None
        
        # Save task to progress with today's date
        progress["daily_tasks"] = [daily_task] if daily_task else []
        progress["daily_tasks_date"] = today_str
        self.save_progress(progress, user_id)
        
        return daily_task
    
    def _get_current_topic(self, progress: Dict) -> Optional[str]:
        """Get current topic based on user progress"""
        solved_count = len(progress.get("solved_questions", []))
        
        # Calculate which topic to focus on based on number of problems solved
        # Each topic gets approximately 10 problems before moving to next
        topic_index = min(solved_count // 10, len(self.dsa_progression) - 1)
        
        return self.dsa_progression[topic_index]
    
    def mark_question_solved(self, problem_number: int, user_id: int = 1) -> bool:
        """Mark a question as solved and update progress"""
        progress = self.load_progress(user_id)
        
        # Check if already solved
        if any(q["number"] == problem_number for q in progress.get("solved_questions", [])):
            return False
        
        # Get problem details
        problem = self.leetcode_api.get_problem_by_number(problem_number)
        if not problem:
            return False
        
        # Add to solved questions
        if "solved_questions" not in progress:
            progress["solved_questions"] = []
        progress["solved_questions"].append({
            "number": problem_number,
            "title": problem["title"],
            "difficulty": problem["difficulty"],
            "topic": problem["topic"],
            "date_solved": datetime.now().isoformat()
        })
        
        # Update streak
        today = datetime.now().date()
        last_date = datetime.fromisoformat(progress["last_question_date"]).date() if progress.get("last_question_date") else None
        
        if last_date == today:
            # Already solved a problem today, don't increment streak
            pass
        elif last_date == today - timedelta(days=1):
            # Continued streak
            progress["streak"] = progress.get("streak", 0) + 1
        else:
            # Reset streak
            progress["streak"] = 1
        
        progress["last_question_date"] = datetime.now().isoformat()
        
        self.save_progress(progress, user_id)
        return True
    
    def get_progress_summary(self, user_id: int = 1) -> Dict:
        """Get user progress summary"""
        progress = self.load_progress(user_id)
        
        return {
            "total_solved": len(progress.get("solved_questions", [])),
            "current_streak": progress.get("streak", 0),
            "solved_questions": progress.get("solved_questions", [])
        }
    
    def _get_active_users_file(self) -> str:
        """Get path to the active users tracking file"""
        return os.path.join(self.progress_dir, "active_users.json")
    
    def track_user(self, user_id: int):
        """Track a unique user who interacts with the bot"""
        try:
            active_file = self._get_active_users_file()
            try:
                with open(active_file, 'r') as f:
                    users = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                users = []
            
            if user_id not in users:
                users.append(user_id)
                os.makedirs(self.progress_dir, exist_ok=True)
                with open(active_file, 'w') as f:
                    json.dump(users, f, indent=2)
        except Exception as e:
            logger.error(f"Error tracking user: {e}")
    
    def get_total_users(self) -> int:
        """Count total unique users who have interacted with the bot"""
        try:
            active_file = self._get_active_users_file()
            with open(active_file, 'r') as f:
                users = json.load(f)
            return len(users)
        except (FileNotFoundError, json.JSONDecodeError):
            return 0
        except Exception as e:
            logger.error(f"Error counting users: {e}")
            return 0
