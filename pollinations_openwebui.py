#!/usr/bin/env python3
"""
Pollinations client for OpenWebUI integrations.

Uses the updated API surface described in the OpenAPI document:
- Base URL: https://gen.pollinations.ai
- Chat completions: POST /v1/chat/completions
- Simple text: GET /text/{prompt}
- Image generation: GET /image/{prompt}
- Account endpoints: /account/*
"""

import requests
from typing import Optional, Dict, Any, List


class PollinationsClient:
    BASE_URL = "https://gen.pollinations.ai"

    def __init__(self, api_key: Optional[str] = None, timeout: int = 30):
        """
        Create a client.

        Args:
            api_key: Your Pollinations API key (Bearer). If None, some endpoints that require auth will fail.
            timeout: HTTP request timeout in seconds.
        """
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "pollinations-python-client/0.1"})
        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def _handle_response(self, resp: requests.Response) -> Any:
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            # Try to return JSON error body if present
            try:
                return {"error": True, "status_code": resp.status_code, "body": resp.json()}
            except ValueError:
                return {"error": True, "status_code": resp.status_code, "body": resp.text}
        # Try JSON, fallback to raw content/text
        content_type = resp.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return resp.json()
        return resp.content if "image/" in content_type or "audio/" in content_type else resp.text

    # ---------------------
    # Models & Account
    # ---------------------
    def list_v1_models(self) -> Dict[str, Any]:
        """GET /v1/models — OpenAI-compatible model list"""
        url = f"{self.BASE_URL}/v1/models"
        resp = self.session.get(url, timeout=self.timeout)
        return self._handle_response(resp)

    def list_text_models(self) -> Any:
        """GET /text/models — detailed text models"""
        url = f"{self.BASE_URL}/text/models"
        resp = self.session.get(url, timeout=self.timeout)
        return self._handle_response(resp)

    def account_profile(self) -> Any:
        """GET /account/profile"""
        url = f"{self.BASE_URL}/account/profile"
        resp = self.session.get(url, timeout=self.timeout)
        return self._handle_response(resp)

    def account_balance(self) -> Any:
        """GET /account/balance"""
        url = f"{self.BASE_URL}/account/balance"
        resp = self.session.get(url, timeout=self.timeout)
        return self._handle_response(resp)

    # ---------------------
    # Text & Chat
    # ---------------------
    def chat_completions(
        self,
        messages: List[Dict[str, Any]],
        model: str = "openai",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs,
    ) -> Any:
        """POST /v1/chat/completions (OpenAI-compatible)

        messages: list of {role: 'user'|'system'|'assistant', content: str|[...] } per OpenAI format.
        """
        url = f"{self.BASE_URL}/v1/chat/completions"
        payload: Dict[str, Any] = {"model": model, "messages": messages}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if stream:
            payload["stream"] = True
        payload.update(kwargs)
        resp = self.session.post(url, json=payload, timeout=self.timeout, stream=stream)
        # If streaming, return the raw response so caller can iterate. Otherwise parse.
        if stream:
            return resp
        return self._handle_response(resp)

    def text_simple(self, prompt: str, model: str = "openai", **query_params) -> Any:
        """GET /text/{prompt} — simple text response (plain text)

        query_params e.g. temperature, json=true, etc.
        """
        from urllib.parse import quote

        enc = quote(prompt, safe="")
        url = f"{self.BASE_URL}/text/{enc}"
        params = {"model": model}
        params.update(query_params)
        resp = self.session.get(url, params=params, timeout=self.timeout)
        return self._handle_response(resp)

    # ---------------------
    # Image
    # ---------------------
    def image(
        self,
        prompt: str,
        model: str = "zimage",
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
        save_path: Optional[str] = None,
        **query_params,
    ) -> Any:
        """GET /image/{prompt} — returns image binary (image/jpeg or image/png)

        If save_path is provided, image bytes will be saved and the save path returned.
        Otherwise, returns dict with either URL string or binary content depending on API response.
        """
        from urllib.parse import quote

        enc = quote(prompt, safe="")
        url = f"{self.BASE_URL}/image/{enc}"
        params = {"model": model, "width": width, "height": height}
        if seed is not None:
            params["seed"] = seed
        params.update(query_params)
        resp = self.session.get(url, params=params, timeout=self.timeout)
        # If success and content is image, save or return bytes
        content_type = resp.headers.get("Content-Type", "")
        if resp.status_code == 200 and ("image/" in content_type):
            if save_path:
                with open(save_path, "wb") as f:
                    f.write(resp.content)
                return {"saved_to": save_path}
            # return bytes for consumer
            return {"content_bytes": resp.content, "content_type": content_type}
        return self._handle_response(resp)

    # Convenience: generate an image and save to disk
    def generate_image_to_file(
        self, prompt: str, out_path: str, **kwargs
    ) -> Dict[str, Any]:
        return self.image(prompt=prompt, save_path=out_path, **kwargs)


# If executed as a script, show a tiny demo (no API key required for simple endpoints)
if __name__ == "__main__":
    client = PollinationsClient(api_key=None)
    print("Listing /v1/models (may work without API key)")
    models = client.list_v1_models()
    print(models)