import os
import logging
from typing import Dict, List
from telegram import Update, Bot, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters
from scheduler.task_generator import TaskGenerator
from datetime import datetime

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class LeetCodeBot:
    def __init__(self, token: str, admin_user_id: int = None):
        self.token = token
        self.admin_user_id = admin_user_id
        self.task_generator = TaskGenerator()
        self.bot = Bot(token=token)
        
        self.main_keyboard = ReplyKeyboardMarkup(
            [
                ["📋 Today's Tasks", "📊 My Progress"],
                ["📚 Topic Questions", "📖 Help"]
            ],
            resize_keyboard=True
        )
        
        self.topic_keyboard = ReplyKeyboardMarkup(
            [
                ["🔤 Easy", "🟡 Medium"],
                ["🔴 Hard", "🔙 Back to Main Menu"]
            ],
            resize_keyboard=True
        )
    
    def _get_question_inline_keyboard(self) -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton("🔄 Next Question", callback_data="next_question")],
            [InlineKeyboardButton("✅ Completed", callback_data="mark_done")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def _get_today_inline_keyboard(self) -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton("✅ Completed", callback_data="mark_done_today")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def _get_completed_message(self, user_id: int = 1) -> str:
        try:
            progress = self.task_generator.get_progress_summary(user_id)
            solved = progress.get('solved_questions', [])
            if not solved:
                return "📋 No questions completed yet."
            message = "📋 *Completed Questions*\n\n"
            for i, q in enumerate(solved, 1):
                message += f"{i}. #{q['number']} | Topic: {q['topic']} | Level: {q['difficulty']}\n"
            return message.strip()
        except Exception:
            return "📋 No questions completed yet."
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.task_generator.track_user(user_id)
        await update.message.reply_text(
            "🔥 Welcome to LeetCode Daily Task Bot!\n\nUse the buttons below to interact with the bot:",
            reply_markup=self.main_keyboard
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📖 Help Menu:\n\n"
            "📋 Today's Tasks - Get today's LeetCode question\n"
            "📊 My Progress - View your progress and streak\n"
            "📚 Topic Questions - Get questions by topic and difficulty\n"
            "📖 Help - Show this help menu"
        )
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Only visible to the bot owner (admin)
        user_id = update.effective_user.id
        if self.admin_user_id is None or user_id != self.admin_user_id:
            logger.info(f"Unauthorized /stats attempt by user_id={user_id}")
            return  # Silently ignore for other users
        try:
            total_users = self.task_generator.get_total_users()
            progress = self.task_generator.get_progress_summary(user_id)
            
            message = "📊 Bot Statistics (Admin Only)\n\n"
            message += f"👥 Total Users: {total_users}\n"
            message += f"✅ Your Completed Questions: {progress['total_solved']}\n"
            message += f"🔥 Your Streak: {progress['current_streak']} days"
            await update.message.reply_text(message)
        except Exception as e:
            logger.error(f"Error in /stats command: {e}")
            await update.message.reply_text("Sorry, there was an error retrieving stats.")
    
    async def start_topic_questions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Please enter the topic you want to practice (e.g., Array, Linked List, Tree):")
        context.user_data['expecting_topic'] = True
    
    async def handle_difficulty_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, difficulty_text: str):
        difficulty_map = {"🔤 Easy": "Easy", "🟡 Medium": "Medium", "🔴 Hard": "Hard"}
        difficulty = difficulty_map.get(difficulty_text)
        if not difficulty:
            await update.message.reply_text("Invalid difficulty level selected.")
            return
        topic = context.user_data.get('topic')
        if not topic:
            await update.message.reply_text("Please start over and select a topic first.")
            return
        user_id = update.effective_user.id
        questions = self._get_topic_questions(topic, difficulty, user_id)
        if not questions:
            await update.message.reply_text(f"No questions found for topic '{topic}' with difficulty '{difficulty}'.")
            return
        context.user_data['difficulty'] = difficulty
        context.user_data['current_questions'] = questions
        context.user_data['current_question_index'] = 0
        await self._show_topic_question(update, context, questions[0])
    
    async def _show_topic_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE, question: Dict):
        context.user_data['current_question_number'] = question['number']
        context.user_data['current_question_source'] = 'topic'
        message = f"📚 Topic Question\n\n"
        message += f"#{question['number']} {question['title']}\n"
        message += f"Difficulty: {question['difficulty']}\n"
        message += f"Topic: {question['topic']}\n\n"
        message += "Choose an action:"
        await update.message.reply_text(message, reply_markup=self._get_question_inline_keyboard())
    
    async def _show_topic_question_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE, question: Dict):
        context.user_data['current_question_number'] = question['number']
        context.user_data['current_question_source'] = 'topic'
        message = f"📚 Topic Question\n\n"
        message += f"#{question['number']} {question['title']}\n"
        message += f"Difficulty: {question['difficulty']}\n"
        message += f"Topic: {question['topic']}\n\n"
        message += "Choose an action:"
        await update.callback_query.edit_message_text(message, reply_markup=self._get_question_inline_keyboard())
    
    async def get_next_topic_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_query=None):
        topic = context.user_data.get('topic')
        difficulty = context.user_data.get('difficulty')
        user_id = update.effective_user.id
        if not topic or not difficulty:
            if callback_query:
                await callback_query.answer("Please start over by selecting a topic and difficulty.", show_alert=True)
            return
        solved_numbers = [q["number"] for q in self.task_generator.load_progress(user_id)["solved_questions"]]
        new_question = self.task_generator.leetcode_api.get_random_problem_from_leetcode(difficulty, topic, solved_numbers)
        if new_question:
            if callback_query:
                await self._show_topic_question_edit(update, context, new_question)
            else:
                await self._show_topic_question(update, context, new_question)
        else:
            await callback_query.answer(f"No questions found for '{topic}' / '{difficulty}'.", show_alert=True)
    
    async def mark_question_done(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_query=None):
        question_number = context.user_data.get('current_question_number')
        user_id = update.effective_user.id
        logger.info(f"mark_question_done called: question_number={question_number}, user_id={user_id}")
        if not question_number:
            if callback_query:
                await callback_query.answer("No current question to mark as done.", show_alert=True)
            return
        success = self.task_generator.mark_question_solved(question_number, user_id)
        logger.info(f"mark_question_solved result: success={success}")
        if callback_query:
            try:
                if success:
                    await callback_query.answer(text=f"✅ Question #{question_number} marks as completed!", show_alert=True)
                else:
                    await callback_query.answer(text=f"✅ Question #{question_number} was already completed!", show_alert=True)
                # Always remove the buttons after pressing Completed (whether newly marked or already done)
                await callback_query.edit_message_reply_markup(reply_markup=None)
            except Exception as e:
                logger.error(f"Error answering callback query: {e}")
        else:
            completed_msg = self._get_completed_message(user_id)
            if success:
                await update.message.reply_text(f"✅ Problem #{question_number} completed!\n\n{completed_msg}")
            else:
                await update.message.reply_text(f"✅ Problem #{question_number} was already completed.\n\n{completed_msg}")
    
    def _get_topic_questions(self, topic: str, difficulty: str, user_id: int = 1) -> List[Dict]:
        solved_numbers = [q["number"] for q in self.task_generator.load_progress(user_id)["solved_questions"]]
        return self.task_generator.leetcode_api.get_random_problems(difficulty, topic, solved_numbers)
    
    async def handle_button_press(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.task_generator.track_user(user_id)
        text = update.message.text
        if text == "📋 Today's Tasks":
            await self.today(update, context)
        elif text == "📊 My Progress":
            await self.progress(update, context)
        elif text == "📚 Topic Questions":
            await self.start_topic_questions(update, context)
        elif text == "📖 Help":
            await self.help_command(update, context)
        elif text in ["🔤 Easy", "🟡 Medium", "🔴 Hard"]:
            await self.handle_difficulty_selection(update, context, text)
        elif text == "🔙 Back to Main Menu":
            await update.message.reply_text("Back to main menu:", reply_markup=self.main_keyboard)
        else:
            if context.user_data.get('expecting_topic'):
                context.user_data['topic'] = text
                await update.message.reply_text("Now select difficulty level:", reply_markup=self.topic_keyboard)
                del context.user_data['expecting_topic']
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        logger.info(f"Callback received: data={query.data}, user_id={update.effective_user.id}")
        try:
            if query.data == "next_question":
                await query.answer()
                await self.get_next_topic_question(update, context, callback_query=query)
            elif query.data == "mark_done":
                await self.mark_question_done(update, context, callback_query=query)
            elif query.data == "mark_done_today":
                await self.mark_question_done(update, context, callback_query=query)
            else:
                await query.answer()
        except Exception as e:
            logger.error(f"Error handling callback query: {e}")
            try:
                await query.answer("An error occurred. Please try again.", show_alert=True)
            except Exception:
                pass
    
    async def today(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            task = self.task_generator.get_daily_tasks(user_id)
            if not task:
                await update.message.reply_text("No tasks available for today.")
                return
            context.user_data['current_question_number'] = task['number']
            context.user_data['current_question_source'] = 'today'
            
            # Check if this question is already completed
            progress = self.task_generator.load_progress(user_id)
            solved_numbers = [q["number"] for q in progress.get("solved_questions", [])]
            is_completed = task['number'] in solved_numbers
            
            message = "🔥 Today's LeetCode Task\n\n"
            message += f"#{task['number']} {task['title']}\n"
            message += f"Difficulty: {task['difficulty']}\n"
            message += f"Topic: {task['topic']}\n\n"
            
            if is_completed:
                message += "✅ This task is already completed!"
                await update.message.reply_text(message)
            else:
                message += "Mark as completed when done:"
                await update.message.reply_text(message, reply_markup=self._get_today_inline_keyboard())
        except Exception as e:
            logger.error(f"Error in /today command: {e}")
            await update.message.reply_text("Sorry, there was an error generating today's tasks.")
    
    async def progress(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            progress = self.task_generator.get_progress_summary(user_id)
            message = "📊 Your Progress\n\n"
            message += f"Total Questions Solved: {progress['total_solved']}\n"
            message += f"Current Streak: {progress['current_streak']} days\n\n"
            if progress['solved_questions']:
                message += "📋 *Completed Questions*\n"
                for i, q in enumerate(progress['solved_questions'][-5:], 1):
                    message += f"{i}. #{q['number']} | Topic: {q['topic']} | Level: {q['difficulty']}\n"
            await update.message.reply_text(message)
        except Exception as e:
            logger.error(f"Error in /progress command: {e}")
            await update.message.reply_text("Sorry, there was an error retrieving your progress.")
    
    def run(self):
        application = Application.builder().token(self.token).build()
        
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("today", self.today))
        application.add_handler(CommandHandler("progress", self.progress))
        application.add_handler(CommandHandler("stats", self.stats))
        application.add_handler(CallbackQueryHandler(self.handle_callback_query))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_button_press))
        
        async def post_init(app):
            await app.bot.set_my_commands([
                BotCommand("start", "Start the bot"),
                BotCommand("today", "Get today's task"),
                BotCommand("progress", "View your progress"),
            ])
        
        application.post_init = post_init
        
        logger.info("Starting LeetCode Daily Task Bot...")
        application.run_polling()
