import re

with open("bot/telegram_bot.py", "r", encoding="utf-8") as f:
    code = f.read()

poll_func = """
    async def _poll_and_update_solution(self, context, chat_id, message_id, question, lang):
        import asyncio, html
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        
        for _ in range(30): # 30 * 2 = 60s
            await asyncio.sleep(2)
            solution = self.solution_provider.get_solution(question, lang)
            if solution:
                msg  = f"💡 <b>{html.escape(question['title'])}</b> ({lang})\\n\\n"
                msg += f"📖 <b>Approach</b>\\n{html.escape(solution.get('approach', ''))}\\n\\n"
                msg += f"⚡ <b>Complexity</b>\\n"
                msg += f"• <b>Time:</b> <code>{html.escape(solution.get('time', ''))}</code>\\n"
                msg += f"• <b>Space:</b> <code>{html.escape(solution.get('space', ''))}</code>\\n\\n"
                msg += f"💻 <b>Code</b>\\n<pre><code class=\\"language-{lang.lower()}\\">{html.escape(solution.get('code', ''))}</code></pre>"
                
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_to_question")]])
                try:
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=msg, parse_mode="HTML", reply_markup=keyboard)
                except Exception:
                    pass
                return
                
        try:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_to_question")]])
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="❌ <b>Generation Timed Out</b>\\n\\nSorry, generating the solution took too long. Please try again.", parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            pass

    async def _poll_and_update_hint(self, context, chat_id, message_id, question, lang, hint_index, current_hints_shown):
        import asyncio, html
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        
        for _ in range(30): # 60s timeout
            await asyncio.sleep(2)
            hint = self.solution_provider.get_hint(question, lang, hint_index)
            if hint:
                msg = f"💡 <b>Hint {hint_index}</b> ({lang})\\n\\n{html.escape(hint)}"
                keyboard = []
                if hint_index < 3:
                    keyboard.append([InlineKeyboardButton("💡 Next Hint", callback_data="hint_action")])
                keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_question")])
                
                try:
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
                except Exception:
                    pass
                return
                
        try:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_to_question")]])
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="❌ <b>Generation Timed Out</b>\\n\\nSorry, generating the hint took too long.", parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            pass
"""

# Inject poll functions at the end of LeetCodeBot class
code = code.replace("        self.application.run_polling(drop_pending_updates=True)", poll_func + "\\n        self.application.run_polling(drop_pending_updates=True)")

# Update handle_show_solution
target_sol = """        else:
            keyboard = [
                [InlineKeyboardButton("☕ Java", callback_data="show_solution_Java"), InlineKeyboardButton("🐍 Python", callback_data="show_solution_Python")],
                [InlineKeyboardButton("⚙️ C++", callback_data="show_solution_C++"), InlineKeyboardButton("🟨 JavaScript", callback_data="show_solution_JavaScript")],
                [InlineKeyboardButton("🔙 Back", callback_data="cancel_lang_selection")]
            ]
            await query.message.edit_text("⏳ <b>Solution is being prepared.</b>\\nIt will be ready soon. Tap the language button again in ~10 seconds.", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))"""

replacement_sol = """        else:
            msg = f"⏳ <b>Generating solution for {lang}...</b>\\n\\nPlease wait, this usually takes 10-15 seconds. The message will automatically update when ready."
            await query.message.edit_text(msg, parse_mode="HTML")
            
            import asyncio
            asyncio.create_task(self._poll_and_update_solution(
                context=context,
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                question=question,
                lang=lang
            ))"""
code = code.replace(target_sol, replacement_sol)

# Update handle_hint_action
target_hint = """        else:
            await query.message.edit_text(
                "⏳ <b>Hints are being generated.</b>\\nPlease wait about 10 seconds and tap Hint again.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_to_question")]])
            )"""

replacement_hint = """        else:
            await query.message.edit_text(
                f"⏳ <b>Generating Hint {hint_index}...</b>\\nPlease wait, this usually takes 10-15 seconds. The message will automatically update when ready.",
                parse_mode="HTML"
            )
            import asyncio
            asyncio.create_task(self._poll_and_update_hint(
                context=context,
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                question=question,
                lang=lang,
                hint_index=hint_index,
                current_hints_shown=current_hints_shown
            ))"""
code = code.replace(target_hint, replacement_hint)

with open("bot/telegram_bot.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Patched!")
