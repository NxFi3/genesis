"""Shared local-first model providers. Inference threads never receive a World."""
from dataclasses import asdict, dataclass
import json
import math
import os
import urllib.request
from urllib.parse import urlparse


@dataclass
class InferenceConfig:
    enabled: bool = False
    provider: str = 'ollama'
    endpoint: str = 'http://127.0.0.1:11434'
    model: str = 'qwen2.5:7b'
    context_limit: int = 14000  # character budget, approximately 3500 English tokens
    timeout: float = 12
    max_concurrency: int = 2
    per_agent_budget: int = 4
    global_budget: int = 64
    budget_window: int = 300   # simulation ticks
    reasoning_interval: int = 40
    max_queue: int = 64
    max_turns: int = 8
    retries: int = 1
    max_output_tokens: int = 700

    def validate(self):
        if not isinstance(self.enabled, bool):
            raise ValueError('enabled must be boolean')
        if self.provider not in ('ollama', 'openai'):
            raise ValueError('Provider must be ollama or openai')
        if not isinstance(self.endpoint, str) or len(self.endpoint) > 2048:
            raise ValueError('Endpoint must be bounded URL text')
        url = urlparse(self.endpoint)
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
            raise ValueError('Endpoint must be an HTTP(S) URL without embedded credentials')
        if not isinstance(self.model, str) or not self.model or len(self.model) > 200:
            raise ValueError('Model name is required (max 200 characters)')
        for name, low, high in [('context_limit', 6000, 64000), ('max_concurrency', 1, 8),
                                ('per_agent_budget', 1, 100), ('global_budget', 1, 1000),
                                ('budget_window', 20, 10000), ('reasoning_interval', 5, 1000),
                                ('max_queue', 1, 128), ('max_turns', 2, 16), ('retries', 0, 2),
                                ('max_output_tokens', 64, 2000)]:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise ValueError(f'{name} must be an integer in {low}..{high}')
        if isinstance(self.timeout, bool) or not isinstance(self.timeout, (int, float)) or not math.isfinite(self.timeout) or not .05 <= self.timeout <= 120:
            raise ValueError('timeout must be .05..120 seconds')
        return self

    def public(self):
        return asdict(self)


def generate(config, system, context):
    """Bounded response, verified HTTP/TLS, one common JSON result contract."""
    if not config.enabled:
        return {'ok': False, 'error': 'LLM mode is disabled'}
    prompt = json.dumps(context, ensure_ascii=False)
    if len(system)+len(prompt) > config.context_limit:
        return {'ok': False, 'error': 'Context exceeds configured character budget'}
    if config.provider == 'ollama':
        endpoint = config.endpoint.rstrip('/') + '/api/chat'
        payload = {'model': config.model, 'stream': False, 'format': 'json',
                   'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}],
                   'options': {'temperature': .6, 'num_predict': config.max_output_tokens}}
    else:
        base = config.endpoint.rstrip('/')
        endpoint = base + ('/chat/completions' if base.endswith('/v1') else '/v1/chat/completions')
        payload = {'model': config.model, 'stream': False, 'temperature': .6,
                   'max_tokens': config.max_output_tokens, 'response_format': {'type': 'json_object'},
                   'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}]}
    headers = {'Content-Type': 'application/json'}
    # Optional OpenAI-compatible credential is used normally; never serialized or exposed.
    token = os.environ.get('GENESIS_LLM_API_KEY')
    if config.provider == 'openai' and token:
        headers['Authorization'] = 'Bearer ' + token
    error = 'Model unavailable'
    for _ in range(config.retries+1):
        try:
            request = urllib.request.Request(endpoint, json.dumps(payload).encode(), headers)
            with urllib.request.urlopen(request, timeout=config.timeout) as response:
                raw = response.read(262145)
            if len(raw) > 262144:
                raise ValueError('Model response exceeds 256 KiB')
            body = json.loads(raw)
            content = body['message']['content'] if config.provider == 'ollama' else body['choices'][0]['message']['content']
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError('Expected JSON object from model')
            return {'ok': True, 'data': result}
        except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
            error = f'{type(exc).__name__}: {str(exc)[:200]}'
    return {'ok': False, 'error': error}
