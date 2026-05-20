from setuptools import setup, find_packages

setup(
    name="zad13_1",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "uvicorn",
        "nats-py",
        "redis",
        "ollama",
        "pytest",
        "pytest-asyncio",
        "httpx",
        "opentelemetry-api",
        "opentelemetry-sdk",
        "opentelemetry-exporter-otlp",
        "opentelemetry-instrumentation-fastapi",
        "protobuf",
        "grpcio",
    ],
)