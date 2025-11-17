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

"""
The OpenTelemetry oslo.messaging instrumentation.

This module provides automatic instrumentation for oslo.messaging RPC calls.

Usage
---

.. code:: python

    from opentelemetry.instrumentation.oslomessaging import OsloMessagingInstrumentor
    
    # Instrument oslo.messaging
    OsloMessagingInstrumentor().instrument()

    # Uninstrument oslo.messaging
    OsloMessagingInstrumentor().uninstrument()

The instrumentation works by wrapping the core RPC client and server methods
of oslo.messaging to automatically create and propagate trace spans.
"""

import functools
import typing
from typing import Any, Callable

from opentelemetry import trace
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.propagate import inject, extract
from opentelemetry.trace import SpanKind

from opentelemetry.instrumentation.oslomessaging.version import __version__

_RPC_CALL_METHODS = ["cast", "call"]


class OsloMessagingInstrumentor(BaseInstrumentor):
    """
    An instrumentor for oslo.messaging RPC.
    
    See `BaseInstrumentor`
    """

    def instrumentation_dependencies(self) -> typing.Collection[str]:
        """
        Return a list of python packages that this instrumentation depends on.
        """
        from opentelemetry.instrumentation.oslomessaging.package import _instruments
        return _instruments

    def _instrument(self, **kwargs: Any) -> None:
        """
        Instrument the oslo.messaging RPC module.
        """
        tracer_provider = kwargs.get("tracer_provider")
        tracer = trace.get_tracer(
            "opentelemetry.instrumentation.oslomessaging",
            __version__,
            tracer_provider,
        )
        
        # Instrument RPC client methods
        self._instrument_client(tracer)
        # Instrument RPC server methods
        self._instrument_server(tracer)

    def _uninstrument(self, **kwargs: Any) -> None:
        """
        Uninstrument the oslo.messaging RPC module.
        """
        # Uninstrument RPC client methods
        self._uninstrument_client()
        # Uninstrument RPC server methods
        self._uninstrument_server()

    def _instrument_client(self, tracer: trace.Tracer) -> None:
        """
        Instrument RPC client methods to create spans and inject trace context.
        """
        try:
            import oslo_messaging.rpc.client
            
            # Get the original methods
            original_base_call_context = oslo_messaging.rpc.client._BaseCallContext
            
            # Create wrapper methods
            for method_name in _RPC_CALL_METHODS:
                if hasattr(original_base_call_context, method_name):
                    original_method = getattr(original_base_call_context, method_name)
                    wrapped_method = self._wrap_client_method(
                        original_method, tracer, method_name
                    )
                    setattr(original_base_call_context, method_name, wrapped_method)
            
            # Add trace context injection method
            if not hasattr(original_base_call_context, "_inject_trace_context"):
                setattr(
                    original_base_call_context,
                    "_inject_trace_context",
                    self._inject_trace_context
                )
                
        except ImportError:
            # oslo.messaging is not installed
            pass

    def _uninstrument_client(self) -> None:
        """
        Uninstrument RPC client methods.
        """
        try:
            import oslo_messaging.rpc.client
            
            for method_name in _RPC_CALL_METHODS:
                if hasattr(oslo_messaging.rpc.client._BaseCallContext, method_name):
                    unwrap(oslo_messaging.rpc.client._BaseCallContext, method_name)
            
            # Remove the trace context injection method if it exists
            if hasattr(oslo_messaging.rpc.client._BaseCallContext, "_inject_trace_context"):
                delattr(oslo_messaging.rpc.client._BaseCallContext, "_inject_trace_context")
                
        except ImportError:
            pass

    def _instrument_server(self, tracer: trace.Tracer) -> None:
        """
        Instrument RPC server methods to extract trace context and create spans.
        """
        try:
            import oslo_messaging.rpc.server
            
            # Wrap the process_incoming method
            original_process_incoming = oslo_messaging.rpc.server.RPCServer._process_incoming
            wrapped_process_incoming = self._wrap_server_process_incoming(
                original_process_incoming, tracer
            )
            setattr(
                oslo_messaging.rpc.server.RPCServer, 
                "_process_incoming", 
                wrapped_process_incoming
            )
            
        except ImportError:
            pass

    def _uninstrument_server(self) -> None:
        """
        Uninstrument RPC server methods.
        """
        try:
            import oslo_messaging.rpc.server
            
            # Unwrap the process_incoming method
            if hasattr(oslo_messaging.rpc.server.RPCServer, "_process_incoming"):
                unwrap(oslo_messaging.rpc.server.RPCServer, "_process_incoming")
                
        except ImportError:
            pass

    def _wrap_client_method(
        self, original_method: Callable[..., Any], tracer: trace.Tracer, method_name: str
    ) -> Callable[..., Any]:
        """
        Wrap an RPC client method to create a span and inject trace context.
        """
        @functools.wraps(original_method)
        def wrapper(self, ctxt, method, **kwargs):
            # Create a span for the RPC call
            with tracer.start_as_current_span(
                f"oslo_messaging.rpc.{method_name}",
                kind=SpanKind.CLIENT,
            ) as span:
                # Add span attributes
                span.set_attribute("rpc.method", method)
                span.set_attribute("rpc.system", "oslo_messaging")
                span.set_attribute("rpc.service", getattr(self, "target", None))
                
                # Inject trace context into the message
                if not ctxt:
                    ctxt = {}
                # Use the updated context returned by _inject_trace_context
                ctxt = self._inject_trace_context(ctxt)
                
                # Call the original method
                try:
                    result = original_method(self, ctxt, method, **kwargs)
                    return result
                except Exception as e:
                    # Record the exception
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR))
                    raise
        return wrapper

    def _inject_trace_context(self, ctxt):
        """
        Inject trace context into the message context.
        """
        # Use a carrier dictionary to hold the propagated context
        carrier = {}
        inject(carrier)
        
        # Handle different context types, including oslo_context.context.RequestContext
        if hasattr(ctxt, "to_dict"):
            ctxt_dict = ctxt.to_dict()
        else:
            ctxt_dict = dict(ctxt or {})
        ctxt_dict["_trace_context"] = carrier
        return ctxt_dict

    def _wrap_server_process_incoming(
        self, original_method: Callable[..., Any], tracer: trace.Tracer
    ) -> Callable[..., Any]:
        """
        Wrap the RPC server process_incoming method to extract trace context and create spans.
        """
        @functools.wraps(original_method)
        def wrapper(self, incoming):
            # Extract trace context from the message if available
            ctx = None
            if hasattr(incoming, "ctxt") and hasattr(incoming, "message"):
                # Try to extract from message context
                # Handle different context types, including oslo_context.context.RequestContext
                ctxt_dict = None
                if hasattr(incoming.ctxt, "to_dict"):
                    ctxt_dict = incoming.ctxt.to_dict()
                elif hasattr(incoming.ctxt, "get"):
                    ctxt_dict = dict(incoming.ctxt)
                elif incoming.ctxt is not None:
                    try:
                        ctxt_dict = dict(incoming.ctxt)
                    except (TypeError, ValueError):
                        ctxt_dict = None
                
                if ctxt_dict and "_trace_context" in ctxt_dict:
                    carrier = ctxt_dict["_trace_context"]
                    ctx = extract(carrier)
                
                # Get method information for span name
                method = incoming.message.get("method", "unknown")
                
                # Create a server span with the extracted context
                with tracer.start_as_current_span(
                    f"oslo_messaging.rpc.server.{method}",
                    context=ctx,
                    kind=SpanKind.SERVER,
                ) as span:
                    # Add span attributes
                    span.set_attribute("rpc.method", method)
                    span.set_attribute("rpc.system", "oslo_messaging")
                    span.set_attribute("rpc.service", getattr(self, "target", None))
                    
                    # Call the original method
                    try:
                        result = original_method(self, incoming)
                        return result
                    except Exception as e:
                        # Record the exception
                        span.record_exception(e)
                        span.set_status(trace.Status(trace.StatusCode.ERROR))
                        raise
            else:
                # If the message structure is not as expected, call the original method
                return original_method(self, incoming)
        return wrapper

__all__ = ["OsloMessagingInstrumentor"]
