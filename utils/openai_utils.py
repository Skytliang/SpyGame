import openai
import tiktoken
import backoff
import requests
from openai.error import RateLimitError, APIError, ServiceUnavailableError, APIConnectionError


model2max_context = {
    "gpt-4": 7800,
    "gpt-4-0314": 7800,
    "gpt-4-0613": 7800,
    "gpt-3.5-turbo": 3800,
    "gpt-3.5-turbo-0301": 3800,
    "gpt-3.5-turbo-0613": 3800,
    "text-davinci-003": 3800,
    "curie": 1800,
    "text-curie-001": 1800,
    "text-babbage-001": 1800,
    "text-ada-001": 1800,
    "text-davinci-002": 3800,
}

def valid_location():
    res = requests.get('http://myip.ipip.net', timeout=5).text
    print(res)
    # return "美国" in res

class OutOfQuotaException(Exception):
    "Raised when the key exceeded the current quota"
    def __init__(self, key, cause=None):
        super().__init__(f"No quota for key: {key}")
        self.key = key
        self.cause = cause

    def __str__(self):
        if self.cause:
            return f"{super().__str__()}. Caused by {self.cause}"
        else:
            return super().__str__()

class AccessTerminatedException(Exception):
    "Raised when the key has been terminated"
    def __init__(self, key, cause=None):
        super().__init__(f"Access terminated key: {key}")
        self.key = key
        self.cause = cause

    def __str__(self):
        if self.cause:
            return f"{super().__str__()}. Caused by {self.cause}"
        else:
            return super().__str__()

class TimeOutException(Exception):
    "Raised when time out error"
    def __init__(self, cause=None):
        super().__init__(f"Time Out Error")
        self.cause = cause

    def __str__(self):
        if self.cause:
            return f"{super().__str__()}. Caused by {self.cause}"
        else:
            return super().__str__()

def num_tokens_from_string(string: str, model_name: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.encoding_for_model(model_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens