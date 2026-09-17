import os

from openai import OpenAI


def get_openai_client():
    """
    Yahan-APP全体で共有するOpenAI API client。
    """

    api_key = os.environ.get(
        "OPENAI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured."
        )

    return OpenAI(
        api_key=api_key
    )