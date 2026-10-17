import unittest
from relay_discovery import select_gateway


class RelayDiscoveryTests(unittest.TestCase):
    def test_selects_gateway_on_same_private_subnet(self):
        self.assertEqual(select_gateway([
            {'address':'172.20.1.96','prefix':20,'gateway':'172.20.0.1'}
        ]), '172.20.0.1')

    def test_rejects_public_outside_and_ambiguous_gateways(self):
        for records in (
            [{'address':'172.20.1.96','prefix':20,'gateway':'8.8.8.8'}],
            [{'address':'172.20.1.96','prefix':24,'gateway':'172.20.0.1'}],
            [
                {'address':'172.20.1.96','prefix':20,'gateway':'172.20.0.1'},
                {'address':'192.168.3.6','prefix':24,'gateway':'192.168.3.1'},
            ],
        ):
            with self.assertRaises(RuntimeError): select_gateway(records)


if __name__ == '__main__': unittest.main()
