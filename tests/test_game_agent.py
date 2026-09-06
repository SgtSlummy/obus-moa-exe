import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from fastapi import HTTPException
from backend import game_agent as g

class GameAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = patch.object(g, 'ROOT', Path(self.temp.name)); self.root.start()
        self.scope = g.Scope(campaign='a', owner='p1', role='player')
        self.key = {'id':'key-local-ollama','provider':'ollama','model':'local','base_url':'http://127.0.0.1:11434','connected':True,'verified':True}
    def tearDown(self):
        self.root.stop(); self.temp.cleanup()
    def job(self, **changes):
        value = dict(contract=g.CONTRACT,scope=self.scope,session='s',requestId='r',task='narration',instructions='Describe known facts.',evidence={'question':'harbor'},policy={'namespace':'a'})
        value.update(changes); return g.Job(**value)
    def test_filter_before_retrieval_and_tombstone(self):
        for ref,campaign,audience,owner in [('public','a','party',''),('secret','a','host',''),('private','a','private','p2'),('foreign','b','party','')]:
            g.ingest(g.Source(campaign=campaign,ref=ref,revision=1,audience=audience,owner=owner,text='harbor',provenance='fixture'))
        self.assertEqual([s['ref'] for s in g.retrieve(self.scope,'harbor')],['public'])
        g.ingest(g.Source(campaign='a',ref='public',revision=2,audience='party',text='',provenance='fixture',deleted=True))
        g.ingest(g.Source(campaign='a',ref='public',revision=1,audience='party',text='harbor old',provenance='fixture'))
        self.assertEqual(g.retrieve(self.scope,'harbor'),[])
    def test_local_routing_and_saved_receipt(self):
        calls=[]
        def local(key,prompt,maximum): calls.append(prompt); return 'The harbor is open.'
        a=g.run_job(self.job(),lambda:[self.key],local)
        b=g.run_job(self.job(),lambda:[],lambda *args: self.fail('duplicate generation'))
        self.assertEqual(a,b); self.assertEqual(len(calls),1); self.assertEqual(a['trace'][0]['destination'],'local')
        with self.assertRaises(HTTPException) as error:
            g.run_job(self.job(evidence={'question':'different'}),lambda:[self.key],local)
        self.assertEqual(error.exception.status_code,409)
    def test_no_codex_or_opaque_proxy_dispatch(self):
        codex={'id':'key-codex-oauth','provider':'codex','connected':True,'verified':True}
        proxy={'id':'key-omniroute','provider':'omniroute','connected':True,'verified':True}
        with self.assertRaises(HTTPException):
            g.run_job(self.job(policy={'namespace':'a','codex':True,'exportable':True}),lambda:[codex,proxy],lambda *a:self.fail(),lambda *a:self.fail())
    def test_tools_and_cross_campaign_namespace_rejected(self):
        with self.assertRaises(Exception): self.job(policy={'namespace':'a','tools':True})
        with self.assertRaises(HTTPException): g.run_job(self.job(policy={'namespace':'b'}),lambda:[])
    def test_service_token_required(self):
        client=TestClient(g.app)
        self.assertEqual(client.get('/api/game/capabilities').status_code,401)
        result=client.get('/api/game/capabilities',headers={'X-Obus-Game-Token':g.token()})
        self.assertEqual(result.status_code,200); self.assertEqual(result.json()['contract'],g.CONTRACT)
    def test_private_source_does_not_reach_remote(self):
        g.ingest(g.Source(campaign='a',ref='local',revision=1,audience='party',text='harbor',provenance='fixture',exportable=False))
        with patch.object(g,'approved_free',side_effect=AssertionError('mixed consent must not select external routes')):
            with self.assertRaises(HTTPException):
                g.run_job(self.job(policy={'namespace':'a','mode':'local-free','exportable':True}),lambda:[],lambda *a:'')
if __name__ == '__main__': unittest.main()
