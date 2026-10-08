from contextlib import contextmanager
import sqlite3, os, json, time, urllib.request
DB=os.getenv('DATA_DB','data.sqlite3')
@contextmanager
def connect():
    c=sqlite3.connect(DB,timeout=10);c.row_factory=sqlite3.Row
    c.executescript('CREATE TABLE IF NOT EXISTS users(chat_id INTEGER PRIMARY KEY,enabled INTEGER NOT NULL); CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,chat_id INTEGER,text TEXT,status TEXT); CREATE TABLE IF NOT EXISTS updates(id INTEGER PRIMARY KEY); CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);')
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback();raise
    finally:
        c.close()
def state():
    with connect() as c: return {'users':[dict(r) for r in c.execute('SELECT * FROM users')],'events':[dict(r) for r in c.execute('SELECT * FROM events ORDER BY id DESC LIMIT 30')], 'live':bool(os.getenv('TELEGRAM_BOT_TOKEN'))}
def command(c,chat,text):
    token=text.split()[0].split('@')[0] if text.split() else ''
    if token=='/start':
        c.execute('INSERT INTO users VALUES(?,1) ON CONFLICT(chat_id) DO UPDATE SET enabled=1',(chat,));return 'Welcome to Signal Desk. /pause stops alerts, /resume enables them, /status shows settings.'
    if token in ('/pause','/resume'):
        c.execute('INSERT INTO users VALUES(?,?) ON CONFLICT(chat_id) DO UPDATE SET enabled=excluded.enabled',(chat,int(token=='/resume')));return 'Alerts paused.' if token=='/pause' else 'Alerts enabled.'
    if token=='/status':
        row=c.execute('SELECT enabled FROM users WHERE chat_id=?',(chat,)).fetchone();return 'Alerts enabled.' if row and row[0] else 'Alerts paused. Use /start to subscribe.'
    return 'Available commands: /start /pause /resume /status'
def process(update):
    if 'message' not in update: return False
    msg=update['message'];chat=int(msg['chat']['id']);uid=int(update['update_id'])
    with connect() as c:
        if c.execute('SELECT 1 FROM updates WHERE id=?',(uid,)).fetchone(): return False
        reply=command(c,chat,str(msg.get('text','')))
        c.execute('INSERT INTO events(chat_id,text,status) VALUES(?,?,?)',(chat,reply,'pending'))
        c.execute('INSERT INTO updates VALUES(?)',(uid,));return True
def action(path,data):
    if path=='/api/command':
        chat=int(data.get('chat_id',1001));text=str(data['command'])[:500]
        with connect() as c:
            answer=command(c,chat,text);c.execute('INSERT INTO events(chat_id,text,status) VALUES(?,?,?)',(chat,answer,'demo'));return {'answer':answer}
    if path=='/api/notify':
        text=str(data['text']).strip()
        if not text or len(text)>1000: raise ValueError('Notification must contain 1 to 1000 characters')
        with connect() as c:
            users=list(c.execute('SELECT chat_id FROM users WHERE enabled=1'))
            c.executemany('INSERT INTO events(chat_id,text,status) VALUES(?,?,?)',[(r[0],text,'pending' if os.getenv('TELEGRAM_BOT_TOKEN') else 'demo') for r in users]);return {'queued':len(users)}
    raise ValueError('Unknown operation')
def telegram(method,data):
    req=urllib.request.Request('https://api.telegram.org/bot'+os.environ['TELEGRAM_BOT_TOKEN']+'/'+method,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=40) as response:
        payload=json.load(response)
    if not payload.get('ok'): raise RuntimeError('Telegram rejected request')
    return payload['result']
def poll_once():
    with connect() as c:
        offset=c.execute('SELECT COALESCE(MAX(id),-1)+1 FROM updates').fetchone()[0]
    for update in telegram('getUpdates',{'offset':offset,'timeout':20}):
        if 'message' in update: process(update)
        else:
            with connect() as c: c.execute('INSERT OR IGNORE INTO updates VALUES(?)',(update['update_id'],))
    with connect() as c: pending=[dict(r) for r in c.execute("SELECT * FROM events WHERE status='pending' ORDER BY id LIMIT 20")]
    for event in pending:
        telegram('sendMessage',{'chat_id':event['chat_id'],'text':event['text']})
        with connect() as c: c.execute("UPDATE events SET status='sent' WHERE id=?",(event['id'],))
