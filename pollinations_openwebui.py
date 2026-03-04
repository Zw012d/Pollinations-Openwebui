"""
title: Pollinations AI (Enterprise Gateway)
author: amanverasia (Updated by AI)
version: 7.6 (Production Grade - Fast Release)
description: Ultra-resilient API gateway. Fixes broken image links by aligning with official Pollinations endpoints, resolves streaming hangs, and applies dynamic budget cutoffs.
"""

from pydantic import BaseModel, Field
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import urllib.parse
import time
from typing import Dict, List, Any, Optional, Union, Generator, Iterator


class Pipe:
    class Valves(BaseModel):
        # --- Authentication ---
        POLLINATIONS_API_KEY: str = Field(
            default="",
            description="Your API key from enter.pollinations.ai (starts with sk_ or pk_). Leave blank to use free tier.",
        )

        # --- Editable Base URLs & Endpoints ---
        API_BASE_URL: str = Field(
            default="https://text.pollinations.ai",
            description="The core domain for the Pollinations Text API.",
        )
        IMAGE_API_BASE_URL: str = Field(
            default="https://image.pollinations.ai",
            description="The core domain for the Pollinations Image/Video API.",
        )
        ENDPOINT_CHAT_COMPLETIONS: str = Field(
            default="/openai/v1/chat/completions",
            description="Path for text generation.",
        )
        ENDPOINT_TEXT_MODELS: str = Field(
            default="/models",
            description="Path to fetch text models.",
        )
        ENDPOINT_IMAGE_MODELS: str = Field(
            default="/models", description="Path to fetch image/video models."
        )
        ENDPOINT_AUDIO_MODELS: str = Field(
            default="/models", description="Path to fetch audio models."
        )

        # --- Filtering & Cost Limits (Budget) ---
        SHOW_PAID_MODELS: bool = Field(
            default=False,
            description="Toggle to True to show Pollen-costing models.",
        )
        MAX_TEXT_COST: float = Field(
            default=0.0,
            description="Cut-off limit for text models per token (e.g., 0.000005). Set to 0 to disable.",
        )
        MAX_IMAGE_COST: float = Field(
            default=0.0,
            description="Cut-off limit for image models per image (e.g., 0.05). Set to 0 to disable.",
        )
        MAX_VIDEO_COST: float = Field(
            default=0.0,
            description="Cut-off limit for video models per second/token (e.g., 0.1). Set to 0 to disable.",
        )
        MAX_AUDIO_COST: float = Field(
            default=0.0,
            description="Cut-off limit for audio models per token/second (e.g., 0.00002). Set to 0 to disable.",
        )

        EMIT_RAW_API_ERRORS: bool = Field(
            default=True,
            description="Strict Mode: Raise exceptions on API errors to show them in the UI.",
        )

        # =========================================
        #  Default Generation Parameters by Modality
        # =========================================

        # --- Text Generation Defaults ---
        DEFAULT_TEXT_TEMPERATURE: float = Field(
            default=0.7,
            description="Controls randomness (0.0 to 2.0). Higher = more creative.",
        )
        DEFAULT_TEXT_TOP_P: float = Field(
            default=1.0,
            description="Nucleus sampling (0.0 to 1.0). Lower = more focused.",
        )
        DEFAULT_TEXT_PRESENCE_PENALTY: float = Field(
            default=0.0,
            description="Penalty for new tokens based on presence so far (-2.0 to 2.0).",
        )
        DEFAULT_TEXT_FREQUENCY_PENALTY: float = Field(
            default=0.0,
            description="Penalty for new tokens based on frequency so far (-2.0 to 2.0).",
        )
        DEFAULT_TEXT_SEED: str = Field(
            default="",
            description="Fixed seed for reproducibility (leave blank for random).",
        )
        DEFAULT_TEXT_MAX_TOKENS: int = Field(
            default=0,
            description="Maximum number of tokens to generate. Set to 0 to use model default.",
        )

        # --- Image Generation Defaults ---
        DEFAULT_IMAGE_WIDTH: int = Field(
            default=1024, description="Default width for images."
        )
        DEFAULT_IMAGE_HEIGHT: int = Field(
            default=1024, description="Default height for images."
        )
        DEFAULT_IMAGE_NEGATIVE_PROMPT: str = Field(
            default="worst quality, blurry", description="What to avoid in images."
        )
        DEFAULT_IMAGE_SEED: str = Field(
            default="", description="Fixed seed for reproducibility."
        )
        DEFAULT_IMAGE_ENHANCE: bool = Field(
            default=False, description="Let AI improve your image prompt."
        )
        DEFAULT_IMAGE_SAFE: bool = Field(
            default=True, description="Enable safety filters for images."
        )
        DEFAULT_IMAGE_NOLOGO: bool = Field(
            default=True, description="Remove Pollinations watermark from images."
        )
        DEFAULT_IMAGE_PRIVATE: bool = Field(
            default=False, description="Keep generated images private."
        )

        # --- Video Generation Defaults ---
        DEFAULT_VIDEO_WIDTH: int = Field(
            default=1024, description="Default width for videos."
        )
        DEFAULT_VIDEO_HEIGHT: int = Field(
            default=576, description="Default height for videos (16:9)."
        )
        DEFAULT_VIDEO_NEGATIVE_PROMPT: str = Field(
            default="", description="What to avoid in videos."
        )
        DEFAULT_VIDEO_SEED: str = Field(
            default="", description="Fixed seed for reproducibility."
        )
        DEFAULT_VIDEO_ENHANCE: bool = Field(
            default=False, description="Let AI improve your video prompt."
        )
        DEFAULT_VIDEO_SAFE: bool = Field(
            default=True, description="Enable safety filters for videos."
        )
        DEFAULT_VIDEO_NOLOGO: bool = Field(
            default=True, description="Remove Pollinations watermark from videos."
        )
        DEFAULT_VIDEO_PRIVATE: bool = Field(
            default=False, description="Keep generated videos private."
        )

        # --- Audio Generation Defaults ---
        DEFAULT_AUDIO_VOICE: str = Field(
            default="alloy",
            description="Default TTS Voice (e.g., alloy, echo, fable, onyx, nova, shimmer).",
        )
        DEFAULT_AUDIO_SEED: str = Field(
            default="", description="Fixed seed for reproducibility."
        )

        # --- Network Resilience ---
        REQUEST_TIMEOUT: int = Field(
            default=120, description="Timeout for API requests in seconds."
        )
        MAX_RETRIES: int = Field(
            default=3,
            description="Number of times to retry failed requests (handles degraded models).",
        )
        BACKOFF_FACTOR: float = Field(
            default=1.5,
            description="Multiplier for exponential backoff sleep between retries.",
        )

    def __init__(self):
        self.valves = self.Valves()
        self._models_cache = None
        self._cache_timestamp = 0
        self._cache_ttl = 3600  # Cache raw model data for 1 hour

        self._session = self._create_resilient_session()

    def _create_resilient_session(self) -> requests.Session:
        """Configures a requests session with automatic retries."""
        session = requests.Session()
        retry_strategy = Retry(
            total=self.valves.MAX_RETRIES,
            backoff_factor=self.valves.BACKOFF_FACTOR,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST"],
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy, pool_connections=15, pool_maxsize=15
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.valves.POLLINATIONS_API_KEY:
            headers["Authorization"] = f"Bearer {self.valves.POLLINATIONS_API_KEY}"
        return headers

    def _fetch_all_models_cached(self) -> Dict[str, List[Dict]]:
        """Fetches ALL models into a cache. Valve filters are applied later."""
        current_time = time.time()
        if (
            self._models_cache
            and (current_time - self._cache_timestamp) < self._cache_ttl
        ):
            return self._models_cache

        models = {"text": [], "image": [], "video": [], "audio": []}

        def get_cost(item: Dict, keys: List[str]) -> float:
            pricing = item.get("pricing", {})
            for k in keys:
                if k in pricing:
                    return float(pricing[k])
            return 0.0

        KNOWN_PAID_TEXT_MODELS = [
            "grok",
            "claude",
            "claude-large",
            "claude-legacy",
            "openai-large",
            "gemini-large",
            "midijourney",
            "openai-audio",
        ]

        # 1. Fetch Text Models
        try:
            url = f"{self.valves.API_BASE_URL}{self.valves.ENDPOINT_TEXT_MODELS}"
            resp = self._session.get(url, headers=self._get_headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", []) if isinstance(data, dict) else data
                for model in items:
                    model_id = model.get("id") or model.get("name")
                    if not model_id:
                        continue
                    is_paid = (
                        model.get("paid_only", False)
                        or model_id in KNOWN_PAID_TEXT_MODELS
                    )
                    cost = get_cost(model, ["completionTextTokens"])
                    models["text"].append(
                        {
                            "id": model_id,
                            "name": model_id.upper(),
                            "is_paid": is_paid,
                            "cost": cost,
                        }
                    )
        except Exception:
            pass

        # 2. Fetch Image & Video Models
        try:
            url = f"{self.valves.IMAGE_API_BASE_URL}{self.valves.ENDPOINT_IMAGE_MODELS}"
            resp = self._session.get(url, headers=self._get_headers(), timeout=10)
            if resp.status_code == 200:
                for item in resp.json():
                    if not isinstance(item, dict):
                        continue
                    model_id = item.get("name") or item.get("id")
                    if not model_id:
                        continue
                    is_paid = item.get("paid_only", False)
                    output_modalities = item.get("output_modalities", [])

                    if "video" in output_modalities:
                        cost = get_cost(
                            item, ["completionVideoSeconds", "completionVideoTokens"]
                        )
                        models["video"].append(
                            {
                                "id": model_id,
                                "name": model_id.upper(),
                                "is_paid": is_paid,
                                "cost": cost,
                            }
                        )
                    else:
                        cost = get_cost(item, ["completionImageTokens"])
                        models["image"].append(
                            {
                                "id": model_id,
                                "name": model_id.upper(),
                                "is_paid": is_paid,
                                "cost": cost,
                            }
                        )
        except Exception:
            pass

        # 3. Fetch Audio Models
        try:
            url = f"{self.valves.API_BASE_URL}{self.valves.ENDPOINT_AUDIO_MODELS}"
            resp = self._session.get(url, headers=self._get_headers(), timeout=10)
            if resp.status_code == 200:
                for item in resp.json():
                    if isinstance(item, dict):
                        model_id = item.get("name") or item.get("id")
                        is_paid = item.get("paid_only", False)
                        cost = get_cost(
                            item, ["completionAudioTokens", "completionAudioSeconds"]
                        )
                    else:
                        model_id = item
                        is_paid = False
                        cost = 0.0
                    if model_id:
                        models["audio"].append(
                            {
                                "id": model_id,
                                "name": str(model_id).upper(),
                                "is_paid": is_paid,
                                "cost": cost,
                            }
                        )
        except Exception:
            pass

        # Fallbacks
        if not models["text"]:
            models["text"] = [
                {"id": "openai", "name": "OPENAI", "is_paid": False, "cost": 0.0}
            ]
        if not models["image"]:
            models["image"] = [
                {"id": "flux", "name": "FLUX", "is_paid": False, "cost": 0.0}
            ]
        if not models["video"]:
            models["video"] = [
                {"id": "seedance", "name": "SEEDANCE", "is_paid": False, "cost": 0.0}
            ]
        if not models["audio"]:
            models["audio"] = [
                {
                    "id": "elevenlabs",
                    "name": "ELEVENLABS TTS",
                    "is_paid": False,
                    "cost": 0.0,
                }
            ]

        self._models_cache = models
        self._cache_timestamp = current_time
        return models

    def pipes(self) -> List[Dict[str, str]]:
        """Dynamically applies Valve filters to the cached models."""
        all_models = self._fetch_all_models_cached()
        pipes_list = []

        # Filter Text Models
        for m in all_models["text"]:
            if not self.valves.SHOW_PAID_MODELS and m["is_paid"]:
                continue
            if self.valves.MAX_TEXT_COST > 0 and m["cost"] > self.valves.MAX_TEXT_COST:
                continue
            pipes_list.append({"id": f"text.{m['id']}", "name": f"[Text] {m['name']}"})

        # Filter Image Models
        for m in all_models["image"]:
            if not self.valves.SHOW_PAID_MODELS and m["is_paid"]:
                continue
            if (
                self.valves.MAX_IMAGE_COST > 0
                and m["cost"] > self.valves.MAX_IMAGE_COST
            ):
                continue
            pipes_list.append(
                {"id": f"image.{m['id']}", "name": f"[Image] {m['name']}"}
            )

        # Filter Video Models
        for m in all_models["video"]:
            if not self.valves.SHOW_PAID_MODELS and m["is_paid"]:
                continue
            if (
                self.valves.MAX_VIDEO_COST > 0
                and m["cost"] > self.valves.MAX_VIDEO_COST
            ):
                continue
            pipes_list.append(
                {"id": f"video.{m['id']}", "name": f"[Video] {m['name']}"}
            )

        # Filter Audio Models
        for m in all_models["audio"]:
            if not self.valves.SHOW_PAID_MODELS and m["is_paid"]:
                continue
            if (
                self.valves.MAX_AUDIO_COST > 0
                and m["cost"] > self.valves.MAX_AUDIO_COST
            ):
                continue
            pipes_list.append(
                {"id": f"audio.{m['id']}", "name": f"[Audio] {m['name']}"}
            )

        return pipes_list

    def _handle_text_generation(
        self, body: Dict[str, Any], model: str
    ) -> Union[str, Generator]:
        url = f"{self.valves.API_BASE_URL}{self.valves.ENDPOINT_CHAT_COMPLETIONS}"
        payload = {
            "model": model,
            "messages": body.get("messages", []),
            "stream": body.get("stream", False),
        }

        payload["temperature"] = body.get(
            "temperature", self.valves.DEFAULT_TEXT_TEMPERATURE
        )
        payload["top_p"] = body.get("top_p", self.valves.DEFAULT_TEXT_TOP_P)
        payload["presence_penalty"] = body.get(
            "presence_penalty", self.valves.DEFAULT_TEXT_PRESENCE_PENALTY
        )
        payload["frequency_penalty"] = body.get(
            "frequency_penalty", self.valves.DEFAULT_TEXT_FREQUENCY_PENALTY
        )

        user_seed = body.get("seed")
        if user_seed is not None:
            payload["seed"] = user_seed
        elif self.valves.DEFAULT_TEXT_SEED.isdigit():
            payload["seed"] = int(self.valves.DEFAULT_TEXT_SEED)

        user_max_tokens = body.get("max_tokens")
        if user_max_tokens is not None:
            payload["max_tokens"] = user_max_tokens
        elif self.valves.DEFAULT_TEXT_MAX_TOKENS > 0:
            payload["max_tokens"] = self.valves.DEFAULT_TEXT_MAX_TOKENS

        try:
            response = self._session.post(
                url,
                headers=self._get_headers(),
                json=payload,
                stream=payload["stream"],
                timeout=self.valves.REQUEST_TIMEOUT,
            )

            if response.status_code != 200:
                err = response.text
                if self.valves.EMIT_RAW_API_ERRORS:
                    raise Exception(f"API Error {response.status_code}: {err}")
                return f"**API Error {response.status_code}:** `{err}`"

            if payload["stream"] and "text/event-stream" in response.headers.get(
                "Content-Type", ""
            ):

                def stream_generator():
                    try:
                        for line in response.iter_lines():
                            if line:
                                decoded = line.decode("utf-8")
                                if decoded.startswith("data: "):
                                    data_str = decoded[6:].strip()
                                    if data_str == "[DONE]":
                                        break
                                    try:
                                        chunk = json.loads(data_str)
                                        if (
                                            "choices" in chunk
                                            and len(chunk["choices"]) > 0
                                        ):
                                            choice = chunk["choices"][0]

                                            # Yield text content
                                            content = choice.get("delta", {}).get(
                                                "content"
                                            )
                                            if content:
                                                yield content

                                            # CRITICAL FIX UPDATE:
                                            # Check for TRUTHY finish_reason ("stop", "length").
                                            # Ignoring "" (empty string) and None to prevent premature stream death.
                                            finish_reason = choice.get("finish_reason")
                                            if finish_reason:
                                                break
                                    except Exception:
                                        continue
                    finally:
                        response.close()

                return stream_generator()

            data = response.json()
            return (
                data["choices"][0]["message"]["content"]
                if "choices" in data
                else "Error: Bad response structure."
            )

        except requests.exceptions.Timeout:
            return "**Error:** Request timed out after multiple retries. The model is currently unresponsive."
        except requests.exceptions.RetryError:
            return "**Error:** Model failed to respond after maximum retries due to rate limits or degraded health."
        except Exception as e:
            if self.valves.EMIT_RAW_API_ERRORS:
                raise e
            return f"**Failed:** {str(e)}"

    def _handle_media_generation(
        self,
        prompt: str,
        model_type: str,
        model_name: str,
        stream: bool = False,
        **kwargs,
    ) -> Union[str, Iterator[str]]:

        safe_prompt = prompt[:1000]
        encoded_prompt = urllib.parse.quote(safe_prompt)
        params = {"model": model_name}
        base_endpoint = ""

        if model_type == "image":
            defaults = {
                "width": self.valves.DEFAULT_IMAGE_WIDTH,
                "height": self.valves.DEFAULT_IMAGE_HEIGHT,
                "enhance": self.valves.DEFAULT_IMAGE_ENHANCE,
                "safe": self.valves.DEFAULT_IMAGE_SAFE,
                "nologo": self.valves.DEFAULT_IMAGE_NOLOGO,
                "private": self.valves.DEFAULT_IMAGE_PRIVATE,
                "negative_prompt": self.valves.DEFAULT_IMAGE_NEGATIVE_PROMPT,
                "seed": self.valves.DEFAULT_IMAGE_SEED,
            }
            # FIXED: Pointing directly to standard Pollinations Image prompt endpoint
            base_endpoint = f"{self.valves.IMAGE_API_BASE_URL}/prompt/{encoded_prompt}"

        elif model_type == "video":
            defaults = {
                "width": self.valves.DEFAULT_VIDEO_WIDTH,
                "height": self.valves.DEFAULT_VIDEO_HEIGHT,
                "enhance": self.valves.DEFAULT_VIDEO_ENHANCE,
                "safe": self.valves.DEFAULT_VIDEO_SAFE,
                "nologo": self.valves.DEFAULT_VIDEO_NOLOGO,
                "private": self.valves.DEFAULT_VIDEO_PRIVATE,
                "negative_prompt": self.valves.DEFAULT_VIDEO_NEGATIVE_PROMPT,
                "seed": self.valves.DEFAULT_VIDEO_SEED,
            }
            # FIXED: Video generation runs through the same core engine interface
            base_endpoint = f"{self.valves.IMAGE_API_BASE_URL}/prompt/{encoded_prompt}"

        elif model_type == "audio":
            params["voice"] = kwargs.get("voice", self.valves.DEFAULT_AUDIO_VOICE)
            seed = kwargs.get("seed", self.valves.DEFAULT_AUDIO_SEED)
            if seed and str(seed).isdigit():
                params["seed"] = int(seed)
            # FIXED: Audio currently resolves through the text domain
            base_endpoint = f"{self.valves.API_BASE_URL}/prompt/{encoded_prompt}"

        if model_type in ["image", "video"]:
            try:
                params["width"] = int(float(kwargs.get("width", defaults["width"])))
                params["height"] = int(float(kwargs.get("height", defaults["height"])))
            except:
                params["width"], params["height"] = (
                    defaults["width"],
                    defaults["height"],
                )

            params["enhance"] = str(kwargs.get("enhance", defaults["enhance"])).lower()
            params["safe"] = str(kwargs.get("safe", defaults["safe"])).lower()
            params["nologo"] = str(kwargs.get("nologo", defaults["nologo"])).lower()
            params["private"] = str(kwargs.get("private", defaults["private"])).lower()

            neg_prompt = kwargs.get("negative_prompt", defaults["negative_prompt"])
            if neg_prompt:
                params["negative_prompt"] = neg_prompt

            seed = kwargs.get("seed", defaults["seed"])
            if seed and str(seed).isdigit():
                params["seed"] = int(seed)

        if self.valves.POLLINATIONS_API_KEY:
            params["key"] = self.valves.POLLINATIONS_API_KEY

        query_string = urllib.parse.urlencode(params)
        full_url = f"{base_endpoint}?{query_string}"

        if model_type == "audio":
            media_output = (
                f"🎵 **Audio Generated Successfully**\n\n"
                f"**[▶️ Click Here to Listen or Download Audio]({full_url}#audio.mp3)**"
            )
        elif model_type == "video":
            media_output = (
                f"🎬 **Video Generated Successfully**\n\n"
                f"**[▶️ Click Here to Watch or Download Video]({full_url}#video.mp4)**"
            )
        else:
            media_output = f"![Generated Image]({full_url})"

        if stream:

            def fast_stream():
                yield media_output

            return fast_stream()

        return media_output

    def pipe(
        self, body: Dict[str, Any], __user__: Optional[Dict] = None
    ) -> Union[str, Generator, Dict]:
        model_id = body.get("model", "")
        parts = model_id.split(".")

        if len(parts) < 2:
            return f"Error: Malformed model ID {model_id}"

        model_type, model_name = parts[-2], parts[-1]

        user_message = next(
            (
                msg.get("content", "")
                for msg in reversed(body.get("messages", []))
                if msg.get("role") == "user"
            ),
            "",
        )

        if not user_message:
            return "Error: Please provide a prompt."

        if model_type in ["image", "video", "audio"]:
            media_kwargs = {
                k: v
                for k, v in body.items()
                if k not in ["stream", "model_type", "model_name", "prompt"]
            }

            return self._handle_media_generation(
                prompt=user_message,
                model_type=model_type,
                model_name=model_name,
                stream=body.get("stream", False),
                **media_kwargs,
            )
        elif model_type == "text":
            return self._handle_text_generation(body, model_name)

        return f"Error: Unknown route type '{model_type}'"
