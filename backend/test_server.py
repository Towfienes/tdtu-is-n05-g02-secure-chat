import http.client
import json
import threading
import unittest

from backend.server import ChatServer, Handler


class MessageTests(unittest.TestCase):
    def setUp(self):
        self.server = ChatServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.conn = http.client.HTTPConnection(*self.server.server_address, timeout=3)

    def tearDown(self):
        self.conn.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, path="/messages", payload=None):
        self.conn.request(method, path, payload)
        response = self.conn.getresponse()
        return response.status, json.loads(response.read())

    def test_send_then_read(self):
        self.assertEqual(self.request("GET"), (200, []))
        status, sent = self.request("POST", payload=json.dumps({"text": " Chào nhóm "}))
        self.assertEqual(status, 201)
        self.assertEqual(sent, [{"id": 1, "text": "Chào nhóm"}])
        self.assertEqual(self.request("GET"), (200, sent))

    def test_post_returns_bounded_history_with_latest_message(self):
        for number in range(1, 32):
            status, conversation = self.request(
                "POST", payload=json.dumps({"text": f"Message {number} 🙂"})
            )
            self.assertEqual(status, 201)
        self.assertEqual(len(conversation), 30)
        self.assertEqual(conversation[0]["id"], 2)
        self.assertEqual(conversation[-1], {"id": 31, "text": "Message 31 🙂"})
        self.assertEqual(self.request("GET"), (200, conversation))

    def test_invalid_posts_leave_history_empty(self):
        for payload in (
            "{",
            "[]",
            '{"text":5}',
            '{"text":" "}',
            '{"text":"' + "x" * 281 + '"}',
        ):
            with self.subTest(payload=payload):
                self.assertEqual(self.request("POST", payload=payload)[0], 400)
        self.assertEqual(self.request("GET"), (200, []))

    def test_oversize_and_unknown_path(self):
        self.assertEqual(self.request("POST", payload="x" * 4097)[0], 413)
        self.assertEqual(self.request("GET", "/other")[0], 404)
