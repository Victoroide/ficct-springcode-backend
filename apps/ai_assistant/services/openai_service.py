import logging
import json
import re
from datetime import datetime
from dotenv import load_dotenv
from base import settings

try:
    import tiktoken
    from openai import AzureOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    # For development without OpenAI dependencies
    OPENAI_AVAILABLE = False
    tiktoken = None
    AzureOpenAI = None


load_dotenv()


def handle_openai_errors(func):
    def wrapper(*args, **kwargs):
        for i in range(3):
            try:
                response = func(*args, **kwargs)
                return response
            except Exception as e:  
                logging.info(f"[OpenAI] Error on request {i+1}: {e}")
                if i < 2:
                    import time
                    time.sleep(1)
                else:
                    raise Exception(f"[OpenAI] Final error after {i} attempts: {e}")
    return wrapper


class OpenAIService():
    def __init__(self):
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI dependencies not available. Install 'openai' and 'tiktoken' packages.")
        
        self.client = AzureOpenAI(
            api_key=settings.OPENAI_AZURE_API_KEY,
            api_version=settings.OPENAI_AZURE_API_VERSION,
            azure_endpoint=settings.OPENAI_AZURE_API_BASE
        )
        self.token_limit = 8192
        self.safe_token_limit = 7500
        self.overlap_tokens = 500
        self.encoding = tiktoken.encoding_for_model("gpt-4o")  

    def chunk_text_by_tokens(self, text, max_tokens=None, overlap_tokens=None):
        max_tokens = max_tokens or self.safe_token_limit
        overlap_tokens = overlap_tokens if overlap_tokens is not None else self.overlap_tokens
        tokens = self.encoding.encode(text)
        chunks = []
        start = 0
        while start < len(tokens):
            end = min(start + max_tokens, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append(chunk_text)
            if overlap_tokens > 0 and end < len(tokens):
                start = end - overlap_tokens
            else:
                start = end
        return chunks

    def call_api(self, messages, model="paralex-gpt-4o"):
        try:
            if model == "paralex-o1-mini":
                for msg in messages:
                    if msg.get("role") == "system":
                        msg["role"] = "user"

            response = self.client.chat.completions.create(model=model, messages=messages)
            if response.choices:
                return response.choices[0].message.content
            return "No response"
        except Exception as e:
            logging.error(f"[OpenAI] An error occurred while calling the API: {e}")
            return f"[OpenAI] An error occurred while calling the API: {e}"

    def stream_api(self, messages, model="paralex-gpt-4o"):
        try:
            logging.info(f"Calling OpenAI API with model {model}")
            if model == "paralex-o1-mini":
                for msg in messages:
                    if msg.get("role") == "system":
                        msg["role"] = "user"

            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True
            )

            return response

        except Exception as e:
            logging.error(f"[OpenAI] An error occurred in Azure API: {e}")
            raise Exception(f"[OpenAI] An error occurred in Azure API: {e}")
