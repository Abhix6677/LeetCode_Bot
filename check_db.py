import sqlite3

conn = sqlite3.connect('database/bot.db')
c = conn.cursor()
c.execute("SELECT * FROM solutions LIMIT 1")
row = c.fetchone()
print(row)
