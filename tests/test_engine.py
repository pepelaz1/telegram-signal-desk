import unittest,tempfile,os
import engine
from unittest.mock import patch
class Bot(unittest.TestCase):
    def setUp(self): engine.DB=os.path.join(os.getcwd(),'test-'+__import__('uuid').uuid4().hex+'.sqlite3')
    def tearDown(self): os.remove(engine.DB) if os.path.exists(engine.DB) else None
    def test_subscribe_pause_notify(self):
        engine.action('/api/command',{'chat_id':1,'command':'/start'})
        engine.action('/api/command',{'chat_id':2,'command':'/start'})
        engine.action('/api/command',{'chat_id':2,'command':'/pause'})
        self.assertEqual(engine.action('/api/notify',{'text':'Release ready'})['queued'],1)
        self.assertEqual(engine.state()['events'][0]['chat_id'],1)
    def test_update_deduplication(self):
        u={'update_id':42,'message':{'chat':{'id':1},'text':'/start'}}
        self.assertTrue(engine.process(u));self.assertFalse(engine.process(u));self.assertEqual(len(engine.state()['events']),1)
    def test_pending_delivery_survives_transport_failure(self):
        engine.process({'update_id':5,'message':{'chat':{'id':1},'text':'/start'}})
        def failing(method,data):
            if method=='getUpdates': return []
            raise OSError('Offline')
        with patch('engine.telegram',side_effect=failing):
            with self.assertRaises(OSError): engine.poll_once()
        self.assertEqual(engine.state()['events'][0]['status'],'pending')
        with patch('engine.telegram',side_effect=lambda method,data: [] if method=='getUpdates' else {'message_id':1}): engine.poll_once()
        self.assertEqual(engine.state()['events'][0]['status'],'sent')
