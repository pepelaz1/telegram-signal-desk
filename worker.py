"""Optional live worker. Never starts unless a token is explicitly configured."""
import os,time,engine
if __name__=='__main__':
    if not os.getenv('TELEGRAM_BOT_TOKEN'): raise SystemExit('Set TELEGRAM_BOT_TOKEN first. UI simulator needs no token.')
    delay=1
    while True:
        try: engine.poll_once();delay=1
        except Exception:
            # Never print exceptions containing Telegram token URLs.
            print('Delivery/poll failed; pending events retained. Retrying.',flush=True)
            time.sleep(delay);delay=min(delay*2,60)
