"""AWS Bedrock LLM provider — HIPAA-eligible under AWS BAA.

Uses the Bedrock Runtime invoke_model API with the Anthropic Claude
messages format. Falls back to Converse API if available.

Requires:
  - boto3 installed
  - AWS credentials available (IAM role on EC2, or env vars)
  - Model access enabled in the Bedrock console
"""

import asyncio
import json
import logging
from typing import Optional, List

import boto3
from botocore.config import Config

from server.llm.base import LLMProvider, LLMMessage, LLMResponse
from server.config import get_settings

logger = logging.getLogger(__name__)


class BedrockProvider(LLMProvider):

    def __init__(self):
        settings = get_settings()
        self._model_id = settings.bedrock_model_id
        self._region = settings.bedrock_region

        boto_config = Config(
            region_name=self._region,
            retries={"max_attempts": 2, "mode": "adaptive"},
        )
        self._client = boto3.client(
            "bedrock-runtime",
            config=boto_config,
        )

    @property
    def name(self) -> str:
        return "bedrock"

    async def complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: Optional[str] = None,
    ) -> LLMResponse:
        # Separate system message from conversation
        system_text = ""
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_text += m.content + "\n"
            else:
                chat_messages.append({"role": m.role, "content": m.content})

        if response_format == "json_object":
            system_text += "\nRespond with valid JSON only."

        # Build Anthropic messages API body (used by invoke_model)
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": chat_messages,
        }
        if system_text.strip():
            body["system"] = system_text.strip()

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.invoke_model(
                modelId=self._model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            ),
        )

        data = json.loads(response["body"].read())
        content = data["content"][0]["text"]
        usage = data.get("usage", {})

        logger.info(
            f"Bedrock completion: model={data.get('model', self._model_id)} "
            f"input_tokens={usage.get('input_tokens', 0)} "
            f"output_tokens={usage.get('output_tokens', 0)}"
        )

        return LLMResponse(
            content=content,
            model=data.get("model", self._model_id),
            usage={
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
            },
        )
