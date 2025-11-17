OpenTelemetry oslo.messaging Instrumentation
=============================================

|pypi| |python| |license|

.. |pypi| image:: https://badge.fury.io/py/opentelemetry-instrumentation-oslomessaging.svg
    :target: https://pypi.org/project/opentelemetry-instrumentation-oslomessaging/
    :alt: PyPI Version

.. |python| image:: https://img.shields.io/pypi/pyversions/opentelemetry-instrumentation-oslomessaging.svg
    :alt: Python Versions

.. |license| image:: https://img.shields.io/pypi/l/opentelemetry-instrumentation-oslomessaging.svg
    :alt: License

This library provides automatic OpenTelemetry instrumentation for `oslo.messaging <https://docs.openstack.org/oslo.messaging/latest/>`_ RPC calls.

Installation
------------

.. code:: console

    pip install opentelemetry-instrumentation-oslomessaging

Usage
-----

To instrument oslo.messaging, you need to initialize the instrumentation before using any oslo.messaging RPC functionality.

Client Example:
~~~~~~~~~~~~~~~

.. code:: python

    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter
    from opentelemetry.instrumentation.oslomessaging import OsloMessagingInstrumentor
    import oslo.messaging

    # Set up OpenTelemetry
    provider = TracerProvider()
    processor = BatchSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Instrument oslo.messaging
    OsloMessagingInstrumentor().instrument()

    # Now use oslo.messaging as normal
    transport = oslo.messaging.get_transport("rabbit://localhost")
    target = oslo.messaging.Target(topic="test_topic")
    client = oslo.messaging.RPCClient(transport, target)
    
    # This call will be traced automatically
    client.call({}, "hello", name="world")

Server Example:
~~~~~~~~~~~~~~~

.. code:: python

    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter
    from opentelemetry.instrumentation.oslomessaging import OsloMessagingInstrumentor
    import oslo.messaging

    # Set up OpenTelemetry
    provider = TracerProvider()
    processor = BatchSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Instrument oslo.messaging
    OsloMessagingInstrumentor().instrument()

    # Define a handler for RPC calls
    class TestEndpoint(object):
        def hello(self, ctxt, name):
            return "Hello, %s!" % name

    # Set up the RPC server
    transport = oslo.messaging.get_transport("rabbit://localhost")
    target = oslo.messaging.Target(topic="test_topic")
    endpoints = [TestEndpoint()]
    server = oslo.messaging.get_rpc_server(transport, target, endpoints)
    
    # Start the server (in a real application)
    # server.start()

Features
--------

- Automatically creates spans for RPC calls and responses
- Propagates trace context between client and server
- Adds important attributes to spans:
  - RPC method name
  - RPC service/target
  - RPC system identifier
- Records exceptions that occur during RPC calls

Configuration
-------------  

The instrumentation can be configured with the following parameters when calling ``instrument()``:

- ``tracer_provider``: An optional tracer provider to use for creating spans.

Uninstallation
-------------  

To uninstrument oslo.messaging, call the ``uninstrument()`` method:

.. code:: python

    OsloMessagingInstrumentor().uninstrument()

Contributing
------------

Contributions to this library are welcome. Please see the `OpenTelemetry Python contributing guide <https://github.com/open-telemetry/opentelemetry-python/blob/main/CONTRIBUTING.md>`_ for more information.

License
-------

Apache 2.0 License.