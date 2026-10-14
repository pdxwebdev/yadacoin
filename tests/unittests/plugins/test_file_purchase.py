"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import json
import os
import tempfile
import unittest

from plugins.fileannouncement.handlers import config_http_bases
from plugins.fileannouncement.purchase import (
    access_token,
    access_token_ok,
    invoice_amount,
    output_equals,
    output_pays,
    payer_matches,
)
from plugins.fileannouncement.service import is_announcer_identity


class TestPurchaseMatch(unittest.TestCase):
    def test_output_pays_announcement_address(self):
        txn = {"outputs": [{"to": "ann", "value": 10}]}
        self.assertTrue(output_pays(txn, "ann", "10.00000000"))
        self.assertFalse(output_pays(txn, "ann", "10.00000001"))
        self.assertFalse(output_pays(txn, "other", "1.00000000"))

    def test_payer_must_be_signer_or_inception(self):
        txn = {"public_key_hash": "buyer", "inception_public_key_hash": "kel"}
        self.assertTrue(payer_matches(txn, {"buyer"}))
        self.assertTrue(payer_matches(txn, {"kel"}))
        self.assertFalse(payer_matches(txn, {"stranger"}))
        self.assertFalse(payer_matches(txn, set()))

    def test_invoice_amount_is_above_price(self):
        amount = invoice_amount("10.00000000", 42)
        self.assertEqual(amount, "10.00000042")
        self.assertTrue(
            output_equals({"outputs": [{"to": "ann", "value": amount}]}, "ann", amount)
        )
        self.assertFalse(
            output_equals(
                {"outputs": [{"to": "ann", "value": "10.00000000"}]}, "ann", amount
            )
        )

    def test_access_token_is_bound_to_announcement(self):
        config = type("C", (), {"private_key": "secret"})()
        token = access_token(config, "ann", 9999999999)
        self.assertTrue(access_token_ok(config, "ann", token))
        self.assertFalse(access_token_ok(config, "other", token))

    def test_only_the_announcer_identity_serves_paid_bytes(self):
        self.assertTrue(
            is_announcer_identity(
                "local_node_B", "owner", announced_name="local_node_B"
            )
        )
        self.assertFalse(
            is_announcer_identity(
                "local_node_A",
                "owner",
                announced_name="local_node_B",
                inception="viewer",
                operator_id="viewer",
                address="viewer-addr",
                pay_to="creator-addr",
            )
        )

    def test_config_http_bases_use_the_announcer_web_port(self):
        with tempfile.TemporaryDirectory() as directory:
            with open(
                os.path.join(directory, "node.json"), "w", encoding="utf-8"
            ) as handle:
                json.dump(
                    {
                        "username": "local_node_B",
                        "web_server_port": 8110,
                        "peer_host": "127.0.0.1",
                        "private_key": "secret",
                    },
                    handle,
                )
            self.assertEqual(
                config_http_bases("local_node_B", directory),
                ["http://127.0.0.1:8110"],
            )
            self.assertEqual(config_http_bases("local_node_A", directory), [])
