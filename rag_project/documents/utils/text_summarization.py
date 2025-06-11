from openai import OpenAI
from rag_project.settings import OPENAI_API_KEY
from .logger import logger

def summarize_text(
        text: str, 
        llm_settings: dict) -> str:
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
        # Extract settings from the llm_settings dictionary
        model = llm_settings.get("model", "gpt-4o")
        temperature = llm_settings.get("temperature", 0.2)
        language = llm_settings.get("language", "italian")
        length = llm_settings.get("length", "short")
        # style = llm_settings.get("style", "formal")
        focus = llm_settings.get("focus_areas", None)
        # include_quotes = llm_settings.get("include_quotes", False)
        # bullet_points = llm_settings.get("bullet_points", False)
        # include_stats = llm_settings.get("include_stats", False)
        logger.debug(f"Summarizing text with model: {model}, temperature: {temperature}, language: {language}, length: {length}, focus: {focus}")
        
        # Prepare the request for summarization
        text_guidelined = prepare_summary_request(text, llm_settings)
        logger.debug(f"Prepared text for summarization: {text_guidelined[:1000]}...")  # Log the first 1000 characters of the text
        # Call the OpenAI API to summarize the text
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes text."},
                {"role": "user", "content": text_guidelined}
            ],
            temperature=temperature,
        )
    except Exception as e:
        print(f"Error during OpenAI API call: {e}")

    logger.debug(f"OpenAI API response: {response}")
    summary = response.choices[0].message.content
    return summary

def prepare_summary_request(
        text: str,
        llm_settings: dict) -> dict:
    """
    Prepares the request for summarization.

    Args:
        text (str): The text to be summarized.
        llm_settings (dict): The settings for the summarization.

    Returns:
        dict: The prepared request.
    """
    guidelines = "Please follow these guidelines for summarization:\n"
    guidelines += f"Summarize the text in {llm_settings.get('language', 'italian')}.\n"
    guidelines += f"Keep the summary {llm_settings.get('length', 'short')}.\n"
    guidelines += f"Use a {llm_settings.get('style', 'formal')} style.\n"
    if llm_settings.get("focus"):
        focus = llm_settings.get("focus")
        guidelines += f"Focus on the following aspects: {focus}.\n"

    if llm_settings.get("include_quotes", False):
        guidelines += f"Include quotes in the summary: {text}\n"

    if llm_settings.get("bullet_points", False):
        guidelines += "Use bullet points in the summary.\n"

    if llm_settings.get("include_stats", False):
        guidelines += "Include statistics in the summary.\n"
    
    return guidelines + "Summarize this the following text: \n" + text


    