import unittest
from rendezvous_publish import signed_manifest
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
        with self.assertRaisesRegex(ValueError,'endpoint'):verify(signed_manifest('https://other.example.com','a'*64),'a'*64)

if __name__=='__main__':unittest.main()
