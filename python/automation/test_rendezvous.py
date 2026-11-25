import base64,json,unittest
from unittest.mock import patch
from rendezvous_publish import signed_manifest,publish
from rendezvous_client import verify

class RendezvousTests(unittest.TestCase):
    def test_signed_route_verified(self):
        value=signed_manifest('https://example-route.trycloudflare.com','a'*64,123)
        self.assertEqual(verify(value,'a'*64,122)['sequence'],123)
    def test_tampering_rejected(self):
        value=signed_manifest('https://example-route.trycloudflare.com','a'*64,123)
        value['payload']['base_url']='https://evil.trycloudflare.com'
        with self.assertRaisesRegex(ValueError,'signature'):verify(value,'a'*64)
    def test_replay_rejected(self):
        value=signed_manifest('https://example-route.trycloudflare.com','a'*64,123)
        with self.assertRaisesRegex(ValueError,'replay'):verify(value,'a'*64,124)
    def test_wrong_key_rejected(self):
        with self.assertRaisesRegex(ValueError,'signature'):verify(signed_manifest('https://example.trycloudflare.com','a'*64),'b'*64)
    def test_wrong_host_even_with_valid_signature_rejected(self):
        value=signed_manifest('https://example.trycloudflare.com','a'*64)
        value['payload']['base_url']='https://other.example.com'
        # Re-sign adversarial input to exercise the client's independent host check.
        import hashlib,hmac
        value['signature']=hmac.new(bytes.fromhex('a'*64),json.dumps(value['payload'],sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()
        with self.assertRaisesRegex(ValueError,'endpoint'):verify(value,'a'*64)
    def test_public_repository_rejected_without_opt_in(self):
        with patch('rendezvous_publish.api',return_value={'private':False}) as request:
            with self.assertRaisesRegex(RuntimeError,'explicit opt-in'):publish('https://example.trycloudflare.com','a'*64)
            self.assertEqual(request.call_count,1)
    def test_public_opt_in_publishes_only_signed_manifest(self):
        responses=[{'private':False},{'object':{'sha':'parent'}},{'sha':'blob'},{'sha':'tree'},{'sha':'commit'},{}]
        with patch('rendezvous_publish.api',side_effect=responses) as request:
            result=publish('https://example.trycloudflare.com','a'*64,allow_public=True)
        self.assertEqual(result['commit'],'commit')
        value=json.loads(base64.b64decode(request.call_args_list[2].args[1]['content']))
        self.assertEqual(set(value),{'payload','signature'})
        self.assertEqual(set(value['payload']),{'base_url','sequence','protocol'})
        self.assertNotIn('a'*64,json.dumps(value))
        self.assertEqual(verify(value,'a'*64)['base_url'],'https://example.trycloudflare.com')
    def test_unsafe_endpoint_rejected_before_network(self):
        with patch('rendezvous_publish.api') as request:
            for url in ['https://example.com','https://example.trycloudflare.com/?token=secret','https://user:secret@example.trycloudflare.com']:
                with self.assertRaises(ValueError):publish(url,'a'*64,allow_public=True)
            request.assert_not_called()

if __name__=='__main__':unittest.main()
