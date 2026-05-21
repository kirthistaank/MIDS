"""Zero-shot inference via OpenAI API or local Mistral-7B-Instruct."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from zeroshot.labels import DatasetConfig
from zeroshot.parsing import coerce_text, validate_prediction
from zeroshot.prompts import DOMAIN_PROMPTS


class ZeroShotClassifier:
    """GPT-4 / Mistral-7B-Instruct zero-shot classifier (paper Section 3.2)."""

    def __init__(
        self,
        model: str = "gpt-4",
        temperature: float = 0.0,
        max_tokens: int = 10,
        backend: str = "openai",
        device: Optional[str] = None,
        rate_limit_sleep: float = 0.05,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.backend = backend
        self.rate_limit_sleep = rate_limit_sleep
        self._local_model = None
        self._local_tokenizer = None

        if backend == "openai":
            self._client = self._init_openai_client()
        elif backend == "mistral_local":
            self._init_mistral_local(device)
        else:
            raise ValueError(f"Unknown backend: {backend}")

    def _init_openai_client(self):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError("Install openai: pip install openai") from exc
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("Set OPENAI_API_KEY for GPT-4 zero-shot evaluation.")
        return OpenAI(api_key=api_key)

    def _init_mistral_local(self, device: Optional[str]):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        model_id = self.model if "/" in self.model else "mistralai/Mistral-7B-Instruct-v0.3"
        self._local_tokenizer = AutoTokenizer.from_pretrained(model_id)
        if self._local_tokenizer.pad_token is None:
            self._local_tokenizer.pad_token = self._local_tokenizer.eos_token

        load_4bit = os.environ.get("ZEROSHOT_LOAD_4BIT", "1") == "1"
        if load_4bit:
            bnb = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
            )
            self._local_model = AutoModelForCausalLM.from_pretrained(
                model_id,
                quantization_config=bnb,
                device_map="auto",
            )
        else:
            dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
            self._local_model = AutoModelForCausalLM.from_pretrained(model_id).to(dev)

    def _build_prompt(self, text: Any, config: DatasetConfig) -> str:
        template = DOMAIN_PROMPTS[config.key]
        return template.format(text=coerce_text(text, max_len=2000))

    def classify(self, text: Any, config: DatasetConfig) -> Dict[str, Any]:
        user_prompt = self._build_prompt(text, config)
        system = "You are a precise clinical classifier."

        if self.backend == "openai":
            raw, usage = self._openai_complete(system, user_prompt)
        else:
            raw, usage = self._mistral_complete(system, user_prompt)

        validated = validate_prediction(raw, config.zs_labels)
        time.sleep(self.rate_limit_sleep)

        return {
            "raw": raw,
            "prediction": validated,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        }

    def _openai_complete(self, system: str, user: str) -> tuple[str, dict]:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        raw = response.choices[0].message.content or ""
        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
            "completion_tokens": response.usage.completion_tokens if response.usage else None,
        }
        return raw.strip(), usage

    def _mistral_complete(self, system: str, user: str) -> tuple[str, dict]:
        import torch

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        encoded = self._local_tokenizer.apply_chat_template(
            messages,
            return_tensors="pt",
            add_generation_prompt=True,
        )
        device = next(self._local_model.parameters()).device
        input_ids = encoded.to(device)

        with torch.no_grad():
            out = self._local_model.generate(
                input_ids,
                max_new_tokens=self.max_tokens,
                do_sample=self.temperature > 0,
                temperature=self.temperature if self.temperature > 0 else None,
                pad_token_id=self._local_tokenizer.pad_token_id,
            )

        gen = out[0][input_ids.shape[-1] :]
        raw = self._local_tokenizer.decode(gen, skip_special_tokens=True).strip()
        return raw, {"prompt_tokens": None, "completion_tokens": None}

    def classify_batch(
        self,
        texts: List[Any],
        config: DatasetConfig,
        show_progress: bool = True,
    ) -> List[Dict[str, Any]]:
        safe_texts = [coerce_text(t, max_len=None) for t in texts]
        iterator = safe_texts
        if show_progress:
            from tqdm import tqdm

            iterator = tqdm(safe_texts, desc="Zero-shot inference")

        return [self.classify(text, config) for text in iterator]
