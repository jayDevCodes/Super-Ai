from __future__ import annotations

import unittest

from core.observability import TraceContext, TraceContextError


class TraceContextTests(unittest.TestCase):
    def test_root_and_child_contexts_are_correlated(self):
        root = TraceContext.new_root()
        child = root.child()
        self.assertEqual(root.trace_id, child.trace_id)
        self.assertEqual(child.parent_span_id, root.span_id)
        self.assertNotEqual(root.span_id, child.span_id)

    def test_invalid_ids_are_rejected(self):
        with self.assertRaises(TraceContextError):
            TraceContext(trace_id="0" * 32, span_id="1" * 16)
        with self.assertRaises(TraceContextError):
            TraceContext(trace_id="1" * 32, span_id="0" * 16)

    def test_attributes_use_lowercase_hex(self):
        ctx = TraceContext.new_root()
        attrs = ctx.as_attributes()
        self.assertRegex(attrs["trace_id"], r"^[0-9a-f]{32}$")
        self.assertRegex(attrs["span_id"], r"^[0-9a-f]{16}$")


if __name__ == "__main__":
    unittest.main()
