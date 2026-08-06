import os
import logging
import asyncio
from typing import Dict, List
from telegram import Update, Bot, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, LinkPreviewOptions
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters
from scheduler.task_generator import TaskGenerator
from utils.video_fetcher import VideoFetcher
from utils.topic_resolver import TopicResolver
from utils.solution_provider import SolutionProvider
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
        self.video_fetcher = VideoFetcher()
        self.solution_provider = SolutionProvider()
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
    
    def _get_question_inline_keyboard(self, problem_url: str, video_url: str = None) -> InlineKeyboardMarkup:
        row1 = [InlineKeyboardButton("📖 Open Problem", url=problem_url)]
        if video_url:
            row1.append(InlineKeyboardButton("🎥 Watch Video", url=video_url))
            
        row2 = [
            InlineKeyboardButton("💡 Hint", callback_data="hint_action"),
            InlineKeyboardButton("📝 Solution", callback_data="solution_action")
        ]
            
        row3 = [
            InlineKeyboardButton("➡️ Next Question", callback_data="next_question"),
            InlineKeyboardButton("✅ Completed", callback_data="mark_done")
        ]
        return InlineKeyboardMarkup([row1, row2, row3])
    
    def _get_today_inline_keyboard(self, problem_url: str, video_url: str = None, is_completed: bool = False) -> InlineKeyboardMarkup:
        row1 = [InlineKeyboardButton("📖 Open Problem", url=problem_url)]
        if video_url:
            row1.append(InlineKeyboardButton("🎥 Watch Video", url=video_url))
            
        row2 = [
            InlineKeyboardButton("💡 Hint", callback_data="hint_action"),
            InlineKeyboardButton("📝 Solution", callback_data="solution_action")
        ]
            
        row3 = []
        if not is_completed:
            row3.append(InlineKeyboardButton("✅ Completed", callback_data="mark_done_today"))
            
        return InlineKeyboardMarkup([row1, row2, row3] if row3 else [row1, row2])
    
    def _get_completed_message(self, user_id: int = 1) -> str:
        try:
            progress = self.task_generator.load_progress(user_id)
            solved = progress.get('solved_questions', [])
            if not solved:
                return "📋 No questions completed yet."
            message = "📋 *Completed Questions*\n\n"
            
            for q in solved[-10:]:
                message += f"• [#{q['number']} {q['title']}]({q['url']})\n"
                
            return message
        except Exception as e:
            logger.error(f"Error building completed message: {e}")
            return "Unable to load completed questions."

    async def handle_hint_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query):
        try:
            await query.answer()
        except:
            pass
        user_id = update.effective_user.id
        q_num = context.user_data.get('current_question_number')
        if not q_num:
            await query.answer("❌ No active question context.")
            await query.message.reply_text("❌ No active question context.")
            return
            
        question = self.task_generator.leetcode_api.get_problem_by_number(q_num)
        if not question:
            await query.answer("❌ Error finding question.")
            return

        slug = question['titleSlug']
        lang = self.task_generator.get_preferred_language(user_id) or "Java"
        
        # Determine hint index
        progress = self.task_generator.load_progress(user_id)
        current = progress.get("hint_tracking", {}).get(slug, 0)
        hint_index = current + 1 if current < 3 else 3
        
        hint = self.solution_provider.get_hint(question, lang, hint_index)
        
        if hint:
            await query.answer()
            # Successfully got hint, so increment tracking
            self.task_generator.increment_hint_index(user_id, slug)
            import html
            await query.message.reply_text(f"💡 <b>Hint {hint_index}</b>\n{html.escape(hint)}", parse_mode="HTML")
        else:
            await query.answer("Hint not ready yet.", show_alert=True)
            await query.message.reply_text("⏳ <b>Hint is not available yet.</b>\nThe background generator is still processing this problem. Please try again later.", parse_mode="HTML")

    async def handle_solution_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query):
        await query.answer()
        keyboard = [
            [InlineKeyboardButton("☕ Java", callback_data="show_solution_Java"), InlineKeyboardButton("🐍 Python", callback_data="show_solution_Python")],
            [InlineKeyboardButton("⚙️ C++", callback_data="show_solution_C++"), InlineKeyboardButton("🟨 JavaScript", callback_data="show_solution_JavaScript")],
            [InlineKeyboardButton("🔙 Back", callback_data="cancel_lang_selection")]
        ]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

    async def handle_cancel_lang_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query):
        await query.answer()
        q_num = context.user_data.get('current_question_number')
        if not q_num:
            return await query.message.delete()
            
        question = self.task_generator.leetcode_api.get_problem_by_number(q_num)
        if not question:
            return await query.message.edit_text("❌ Problem data is currently unavailable. Please try again in a few moments.")
        import urllib.parse
        encoded_title = urllib.parse.quote_plus(f"LeetCode {question['title']} solution")
        video_url = f"https://www.youtube.com/results?search_query={encoded_title}"
        
        source = context.user_data.get('current_question_source')
        if source == 'today':
            progress = self.task_generator.load_progress(update.effective_user.id)
            solved_numbers = [q["number"] for q in progress.get("solved_questions", [])]
            is_completed = q_num in solved_numbers
            keyboard = self._get_today_inline_keyboard(question['url'], video_url, is_completed)
        else:
            keyboard = self._get_question_inline_keyboard(question['url'], video_url)
            
        await query.edit_message_reply_markup(reply_markup=keyboard)

    async def handle_show_solution(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query):
        try:
            await query.answer()
        except:
            pass
            
        user_id = update.effective_user.id
        q_num = context.user_data.get('current_question_number')
        
        if not q_num:
            await query.answer("❌ Context lost.")
            return await query.message.edit_text("❌ Context lost. Please open the question again.")
            
        lang = query.data.split("show_solution_")[1]
        self.task_generator.set_preferred_language(user_id, lang)
        
        question = self.task_generator.leetcode_api.get_problem_by_number(q_num)
        if not question:
            return await query.message.edit_text("❌ Problem data is currently unavailable. Please try again in a few moments.")
        slug = question['titleSlug']
        
        solution = self.solution_provider.get_solution(question, lang)
        
        if solution and solution.get('tg_msg_id') and solution.get('tg_chan_id'):
            # Phase 2: Solution archived in Telegram — instant copy_message delivery
            await query.message.delete()
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Question", callback_data="back_to_question")]])
            try:
                msg_id_obj = await context.bot.copy_message(
                    chat_id=query.message.chat_id,
                    from_chat_id=solution['tg_chan_id'],
                    message_id=solution['tg_msg_id'],
                    reply_markup=keyboard
                )
                context.user_data['solution_msg_id'] = msg_id_obj.message_id
            except Exception as e:
                logger.error(f"Error copying message from channel: {e}")
                msg_obj = await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="❌ Could not fetch solution from the cloud archive. Please try again later.",
                    reply_markup=keyboard
                )
                context.user_data['solution_msg_id'] = msg_obj.message_id

        elif solution and solution.get('code'):
            # Phase 1: Solution in local DB only — render text directly
            import html
            diff_emoji = "🟢" if question.get('difficulty') == "Easy" else "🟡" if question.get('difficulty') == "Medium" else "🔴"
            msg  = f"💡 <b>{html.escape(question['title'])}</b> ({lang})\n\n"
            if solution.get('intuition'):
                msg += f"📖 <b>Intuition</b>\n{html.escape(solution.get('intuition',''))}\n\n"
                msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                msg += f"🎯 <b>Key Idea</b>\n{html.escape(solution.get('key_idea',''))}\n\n"
                msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                msg += f"📋 <b>Step-by-Step</b>\n{html.escape(solution.get('step_by_step',''))}\n\n"
                msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            else:
                msg += f"📖 <b>Approach</b>\n{html.escape(solution.get('approach',''))}\n\n"
                msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"⚡ <b>Complexity</b>\n• <b>Time:</b> <code>{html.escape(solution.get('time',''))}</code>   |   • <b>Space:</b> <code>{html.escape(solution.get('space',''))}</code>\n"
            msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"💻 <b>Code ({lang})</b>\n<pre><code class=\"language-{lang.lower()}\">{html.escape(solution.get('code',''))}</code></pre>\n"
            msg += f"🍓 #{question.get('number','')}  |  🏷️ {question.get('topic','General')}  |  {diff_emoji} {question.get('difficulty','')}"
            await query.message.delete()
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Question", callback_data="back_to_question")]])
            msg_obj = await context.bot.send_message(
                chat_id=query.message.chat_id, text=msg,
                parse_mode="HTML", reply_markup=keyboard
            )
            context.user_data['solution_msg_id'] = msg_obj.message_id

        else:
            await query.message.delete()
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Question", callback_data="back_to_question")]])
            msg = f"⏳ <b>Solution for {lang} is not ready yet.</b>\n\nThe background generator is currently processing this problem. Please check back later."
            msg_obj = await context.bot.send_message(
                chat_id=query.message.chat_id, text=msg,
                parse_mode="HTML", reply_markup=keyboard
            )
            context.user_data['solution_msg_id'] = msg_obj.message_id


    async def handle_back_to_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query):
        await query.answer()
        q_num = context.user_data.get('current_question_number')
        if not q_num:
            return await query.message.delete()
            
        question = self.task_generator.leetcode_api.get_problem_by_number(q_num)
        if not question:
            return await query.message.edit_text("❌ Problem data is currently unavailable. Please try again in a few moments.")
        message, video_url = await self._format_question_message(question)
        source = context.user_data.get('current_question_source')
        
        if source == 'today':
            progress = self.task_generator.load_progress(update.effective_user.id)
            solved_numbers = [q["number"] for q in progress.get("solved_questions", [])]
            is_completed = q_num in solved_numbers
            message = "🔥 Today's LeetCode Task\n\n" + message
            if is_completed:
                message += "\n✅ This task is already completed!"
            keyboard = self._get_today_inline_keyboard(question['url'], video_url, is_completed)
        else:
            keyboard = self._get_question_inline_keyboard(question['url'], video_url)
            
        try:
            await query.message.edit_text(message, reply_markup=keyboard, link_preview_options=LinkPreviewOptions(is_disabled=True))
        except Exception:
            try:
                await query.message.delete()
            except:
                pass
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=message,
                reply_markup=keyboard,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
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
            
    async def dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if self.admin_user_id is None or user_id != self.admin_user_id:
            return
        try:
            msg = await update.message.reply_text("⏳ Loading dashboard...")
            await self._send_dashboard(context, msg.chat_id, msg.message_id)
        except Exception as e:
            logger.error(f"Error in /dashboard command: {e}")
            await update.message.reply_text("Sorry, there was an error retrieving dashboard metrics.")

    async def _send_dashboard(self, context, chat_id: int, message_id: int = None):
        """Build and send/edit the live dashboard message."""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        try:
            from generator_main import _build_dashboard_text
            msg = f"<pre>{_build_dashboard_text(self.solution_provider.db)}</pre>"
        except Exception as e:
            msg = f"Error generating dashboard: {e}"

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Refresh", callback_data="dashboard_refresh")
        ]])

        try:
            if message_id:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=msg, parse_mode="HTML", reply_markup=keyboard
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id, text=msg,
                    parse_mode="HTML", reply_markup=keyboard
                )
        except Exception as e:
            logger.warning(f"[Dashboard] edit failed: {e}")


    
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
    
    async def _format_question_message(self, question: Dict) -> str:
        message = "📝 LeetCode Question\n\n"
        message += f"📖 Title: {question['title']}\n"
        message += f"🆔 Problem ID: #{question['number']}\n"
        message += f"📚 Topic: {question['topic']}\n"
        message += f"🟢 Difficulty: {question['difficulty']}\n\n"
        
        import urllib.parse
        encoded_title = urllib.parse.quote_plus(f"LeetCode {question['title']} solution")
        video_url = f"https://www.youtube.com/results?search_query={encoded_title}"
        
        message += "Choose an action below."
        
        return message, video_url

    def _prefetch_all(self, question: Dict):
        """Fire-and-forget: Saves problem metadata to DB and queues AI generation as a fallback."""
        try:
            # Save problem to DB so Generator Worker has the title/difficulty
            self.solution_provider.db.save_problem(
                slug=question['titleSlug'],
                number=question['number'],
                title=question['title'],
                difficulty=question['difficulty'],
                topic=question['topic'],
                url=question['url'],
                description=None  # Worker will fetch from GraphQL if missing
            )
            # Enqueue generation as a fallback if it wasn't queued already
            self.solution_provider.db.enqueue(question['titleSlug'])
        except Exception as e:
            logger.warning(f"[Prefetch] enqueue error: {e}")

    async def _show_topic_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE, question: Dict):
        context.user_data['current_question_number'] = question['number']
        context.user_data['current_question_source'] = 'topic'
        
        self._prefetch_all(question)
        
        loading_message = await update.message.reply_text("⏳ Fetching question...")
        message, video_url = await self._format_question_message(question)
        await loading_message.edit_text(message, reply_markup=self._get_question_inline_keyboard(question['url'], video_url), link_preview_options=LinkPreviewOptions(is_disabled=True))
    
    async def _show_topic_question_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE, question: Dict):
        context.user_data['current_question_number'] = question['number']
        context.user_data['current_question_source'] = 'topic'
        
        self._prefetch_all(question)
        
        await update.callback_query.edit_message_text("⏳ Fetching question and video solution...")
        message, video_url = await self._format_question_message(question)
        await update.callback_query.edit_message_text(message, reply_markup=self._get_question_inline_keyboard(question['url'], video_url), link_preview_options=LinkPreviewOptions(is_disabled=True))
    
    async def get_next_topic_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_query=None):
        topic = context.user_data.get('topic')
        difficulty = context.user_data.get('difficulty')
        user_id = update.effective_user.id
        if not topic or not difficulty:
            if callback_query:
                await callback_query.answer("Please start over by selecting a topic and difficulty.", show_alert=True)
            return
        solved_numbers = [q["number"] for q in self.task_generator.load_progress(user_id)["solved_questions"]]
        current_q = context.user_data.get('current_question_number')
        if current_q and current_q not in solved_numbers:
            solved_numbers.append(current_q)
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
        elif text == "🔙 Back to Question":
            await update.message.delete()
            sol_msg_id = context.user_data.get('solution_msg_id')
            if sol_msg_id:
                try:
                    await context.bot.delete_message(chat_id=update.message.chat_id, message_id=sol_msg_id)
                except:
                    pass
                context.user_data.pop('solution_msg_id', None)
                
            q_num = context.user_data.get('current_question_number')
            if not q_num:
                return await update.message.reply_text("❌ Context lost. Please open the question again.", reply_markup=self.main_keyboard)
                
            question = self.task_generator.leetcode_api.get_problem_by_number(q_num)
            if not question:
                return await update.message.reply_text("❌ Problem data unavailable.", reply_markup=self.main_keyboard)
                
            message, video_url = await self._format_question_message(question)
            source = context.user_data.get('current_question_source')
            if source == 'today':
                progress = self.task_generator.load_progress(update.effective_user.id)
                solved_numbers = [q["number"] for q in progress.get("solved_questions", [])]
                is_completed = q_num in solved_numbers
                keyboard = self._get_today_inline_keyboard(question['url'], video_url, is_completed)
            else:
                keyboard = self._get_question_inline_keyboard(question['url'], video_url)
                
            dummy = await context.bot.send_message(chat_id=update.message.chat_id, text="Returning...", reply_markup=self.main_keyboard)
            await dummy.delete()
            
            await context.bot.send_message(
                chat_id=update.message.chat_id,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
        elif text in ["🔤 Easy", "🟡 Medium", "🔴 Hard"]:
            await self.handle_difficulty_selection(update, context, text)
        elif text == "🔙 Back to Main Menu":
            await update.message.reply_text("Back to main menu:", reply_markup=self.main_keyboard)
        else:
            if context.user_data.get('expecting_topic'):
                resolution = TopicResolver.resolve_topic(text)
                status = resolution["status"]
                
                if status in ("exact", "fuzzy"):
                    topic = resolution["topic"]
                    context.user_data['topic'] = topic
                    await update.message.reply_text(f"Selected Topic: *{topic}*\nNow select difficulty level:", reply_markup=self.topic_keyboard, parse_mode='Markdown')
                    del context.user_data['expecting_topic']
                else:
                    options = resolution["options"]
                    keyboard = [[InlineKeyboardButton(opt, callback_data=f"topic_{opt}")] for opt in options]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    if status == "ambiguous":
                        msg = f"I couldn't find an exact match for '{text}'. Did you mean one of these?"
                    else:
                        msg = f"I couldn't find a topic matching '{text}'. Here are some popular topics:"
                        
                    await update.message.reply_text(msg, reply_markup=reply_markup)
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
            elif query.data.startswith("topic_"):
                await query.answer()
                topic = query.data.split("_", 1)[1]
                context.user_data['topic'] = topic
                if 'expecting_topic' in context.user_data:
                    del context.user_data['expecting_topic']
                await query.edit_message_text(f"Selected Topic: *{topic}*", parse_mode='Markdown')
                await query.message.reply_text("Now select difficulty level:", reply_markup=self.topic_keyboard)
            elif query.data == "hint_action":
                await self.handle_hint_action(update, context, query)
            elif query.data == "solution_action":
                await self.handle_solution_action(update, context, query)
            elif query.data.startswith("show_solution_"):
                await self.handle_show_solution(update, context, query)
            elif query.data == "cancel_lang_selection":
                await self.handle_cancel_lang_selection(update, context, query)
            elif query.data == "back_to_question":
                await self.handle_back_to_question(update, context, query)
            elif query.data == "ignore":
                try:
                    await query.answer()
                except:
                    pass
            elif query.data == "dashboard_refresh":
                await query.answer("Refreshing...")
                await self._send_dashboard(context, query.message.chat_id, query.message.message_id)
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
            
            self._prefetch_all(task)
            
            # Check if this question is already completed
            progress = self.task_generator.load_progress(user_id)
            solved_numbers = [q["number"] for q in progress.get("solved_questions", [])]
            is_completed = task['number'] in solved_numbers
            
            loading_message = await update.message.reply_text("⏳ Generating today's tasks and video solutions...")
            message, video_url = await self._format_question_message(task)
            # Prepend today's tag
            message = "🔥 Today's LeetCode Task\n\n" + message
            
            if is_completed:
                message += "\n✅ This task is already completed!"
                await loading_message.edit_text(message, link_preview_options=LinkPreviewOptions(is_disabled=True))
            else:
                await loading_message.edit_text(message, reply_markup=self._get_today_inline_keyboard(task['url'], video_url, is_completed=False), link_preview_options=LinkPreviewOptions(is_disabled=True))
        except Exception as e:
            import traceback
            logger.error(f"Error in /today command: {e}\n{traceback.format_exc()}")
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
        application.add_handler(CommandHandler("dashboard", self.dashboard))
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
