import asyncio
import random
import time
from abc import ABC, abstractmethod
from typing import List, Optional
import openai
import httpx
from dataclasses import dataclass

@dataclass
class RateLimitConfig:
    initial_delay: float = 1.0
    max_delay: float = 60.0
    multiplier: float = 2.0
    jitter: bool = True
    max_retries: int = 5

class AIProvider(ABC):
    def __init__(self, api_key: str, rate_limit_config: RateLimitConfig):
        self.api_key = api_key
        self.rate_limit_config = rate_limit_config
    
    @abstractmethod
    async def generate_subject_lines(self, email_content: str, original_subject: Optional[str] = None) -> List[str]:
        pass
    
    async def _exponential_backoff_retry(self, func, *args, **kwargs):
        """Implement exponential backoff with jitter"""
        delay = self.rate_limit_config.initial_delay
        
        for attempt in range(self.rate_limit_config.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt == self.rate_limit_config.max_retries - 1:
                    raise e
                
                # Add jitter to prevent thundering herd
                if self.rate_limit_config.jitter:
                    jitter_delay = delay * (0.5 + random.random() * 0.5)
                else:
                    jitter_delay = delay
                
                await asyncio.sleep(jitter_delay)
                delay = min(delay * self.rate_limit_config.multiplier, self.rate_limit_config.max_delay)

class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, rate_limit_config: RateLimitConfig):
        super().__init__(api_key, rate_limit_config)
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            http_client=httpx.AsyncClient(timeout=30.0)
        )
    
    async def _generate_subject_lines_impl(self, email_content: str, original_subject: Optional[str] = None) -> List[str]:
        prompt = self._build_prompt(email_content, original_subject)
        
        response = await self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert email marketer specializing in subject line optimization."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.85,
            max_tokens=300
        )
        
        content = response.choices[0].message.content
        return self._parse_subject_lines(content)
    
    async def generate_subject_lines(self, email_content: str, original_subject: Optional[str] = None) -> List[str]:
        return await self._exponential_backoff_retry(
            self._generate_subject_lines_impl, 
            email_content, 
            original_subject
        )
    
    def _build_prompt(self, email_content: str, original_subject: Optional[str] = None) -> str:
        base_prompt = f"""
Generate exactly 5 compelling email subject lines for the following email content. Each subject line must be 60 characters or less.

Email Content:
{email_content[:1000]}

Requirements:
- Maximum 60 characters per subject line
- Focus on urgency, curiosity, or value proposition
- Avoid spam trigger words
- Make them action-oriented
- Ensure variety in approach (different psychological triggers)

Original subject: {original_subject if original_subject else 'None provided'}

Format your response as a numbered list:
1. [Subject line 1]
2. [Subject line 2]
3. [Subject line 3]
4. [Subject line 4]
5. [Subject line 5]
"""
        return base_prompt
    
    def _parse_subject_lines(self, content: str) -> List[str]:
        lines = []
        for line in content.strip().split('\n'):
            if line.strip() and any(line.startswith(f"{i}.") for i in range(1, 6)):
                subject = line.split('.', 1)[1].strip()
                # Remove quotes if present
                subject = subject.strip('"').strip("'")
                if len(subject) <= 60:
                    lines.append(subject)
        
        # Ensure we have exactly 5 lines
        while len(lines) < 5:
            lines.append(f"Optimized Subject {len(lines) + 1}")
        
        return lines[:5]

