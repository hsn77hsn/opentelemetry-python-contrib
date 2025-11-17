# Copyright The OpenTelemetry Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from unittest import mock

from opentelemetry.instrumentation.oslomessaging import OsloMessagingInstrumentor


class TestOsloMessagingIntegration(unittest.TestCase):
    """Test integration with oslo.messaging"""

    def setUp(self):
        # Mock oslo.messaging modules
        self.mock_rpc_client = mock.MagicMock()
        self.mock_rpc_server = mock.MagicMock()
        
        # Create a mock _BaseCallContext class with call, cast, call_async methods
        self.mock_base_call_context = mock.MagicMock()
        self.mock_base_call_context.call = mock.MagicMock()
        self.mock_base_call_context.cast = mock.MagicMock()
        self.mock_base_call_context.call_async = mock.MagicMock()
        
        # Create a mock RPCServer class with _process_incoming method
        self.mock_rpc_server_class = mock.MagicMock()
        self.mock_rpc_server_class._process_incoming = mock.MagicMock()
        
        # Configure the mock modules
        self.mock_rpc_client._BaseCallContext = self.mock_base_call_context
        self.mock_rpc_server.RPCServer = self.mock_rpc_server_class
        
        # Patch the import
        self.patcher = mock.patch.dict(
            "sys.modules",
            {
                "oslo.messaging.rpc.client": self.mock_rpc_client,
                "oslo.messaging.rpc.server": self.mock_rpc_server,
            },
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_instrument(self):
        """Test that instrument wraps the appropriate methods"""
        instrumentor = OsloMessagingInstrumentor()
        instrumentor.instrument()
        
        # Check that client methods are wrapped
        self.assertNotEqual(
            self.mock_base_call_context.call.__wrapped__,
            self.mock_base_call_context.call
        )
        self.assertNotEqual(
            self.mock_base_call_context.cast.__wrapped__,
            self.mock_base_call_context.cast
        )
        self.assertNotEqual(
            self.mock_base_call_context.call_async.__wrapped__,
            self.mock_base_call_context.call_async
        )
        
        # Check that _inject_trace_context method is added
        self.assertTrue(hasattr(self.mock_base_call_context, "_inject_trace_context"))
        
        # Check that server method is wrapped
        self.assertNotEqual(
            self.mock_rpc_server_class._process_incoming.__wrapped__,
            self.mock_rpc_server_class._process_incoming
        )

    def test_uninstrument(self):
        """Test that uninstrument unwraps the appropriate methods"""
        instrumentor = OsloMessagingInstrumentor()
        instrumentor.instrument()
        instrumentor.uninstrument()
        
        # Check that client methods are unwrapped
        with self.assertRaises(AttributeError):
            getattr(self.mock_base_call_context.call, "__wrapped__")
        with self.assertRaises(AttributeError):
            getattr(self.mock_base_call_context.cast, "__wrapped__")
        with self.assertRaises(AttributeError):
            getattr(self.mock_base_call_context.call_async, "__wrapped__")
        
        # Check that _inject_trace_context method is removed
        self.assertFalse(hasattr(self.mock_base_call_context, "_inject_trace_context"))
        
        # Check that server method is unwrapped
        with self.assertRaises(AttributeError):
            getattr(self.mock_rpc_server_class._process_incoming, "__wrapped__")

    def test_instrument_unavailable(self):
        """Test that instrument works even if oslo.messaging is not available"""
        # Remove oslo.messaging from sys.modules
        with mock.patch.dict("sys.modules", clear=True):
            instrumentor = OsloMessagingInstrumentor()
            # This should not raise an exception
            instrumentor.instrument()

    def test_uninstrument_unavailable(self):
        """Test that uninstrument works even if oslo.messaging is not available"""
        # Remove oslo.messaging from sys.modules
        with mock.patch.dict("sys.modules", clear=True):
            instrumentor = OsloMessagingInstrumentor()
            # This should not raise an exception
            instrumentor.uninstrument()


if __name__ == "__main__":
    unittest.main()