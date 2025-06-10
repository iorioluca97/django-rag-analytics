from openai import OpenAI
from rag_project.settings import OPENAI_API_KEY
from .logger import logger

def summarize_text(
        text: str, 
        model: str = "gpt-3.5-turbo",
        temperature: float = .5) -> str:
    """
    Summarizes the given text using OpenAI's GPT model.

    Args:
        text (str): The text to be summarized.
        model (str): The OpenAI model to use for summarization. Default is "gpt-3.5-turbo".

    Returns:
        str: The summarized text.
    """
    if not text.strip():
        return "No content to summarize."

    if not OPENAI_API_KEY:
        raise ValueError("OpenAI API key is not set. Please check your environment variables.")
    client = OpenAI(api_key=OPENAI_API_KEY)

    try:
        logger.debug(f"Summarizing text using model: {model}")
        logger.debug(f"Temperature setting: {temperature}")
        
        # Call the OpenAI API to summarize the text
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes text."},
                {"role": "user", "content": f"Please summarize the following text: {text}"}
            ],
            temperature=temperature,
        )
    except Exception as e:
        print(f"Error during OpenAI API call: {e}")


    summary = response.choices[0].message.content
    return summary