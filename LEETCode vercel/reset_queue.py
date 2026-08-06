import sqlite3

def reset_queue():
    with sqlite3.connect('database/bot.db') as c:
        # Reset any stuck or retried jobs back to NEW so they can be picked up
        c.execute("UPDATE generator_queue SET status='NEW', retries=0 WHERE status != 'COMPLETED'")
        c.commit()
        print("Queue reset successfully!")

if __name__ == '__main__':
    reset_queue()
