from openai import OpenAI
from .logger import logger
import os
from langchain_core.documents import Document
from typing import List
from .utility_functions import get_max_tokens
import yaml


def merge_chunks(documents : List[Document], max_tokens: int) -> List[str]:
    """
    Merges small chunks of text into larger ones based on the maximum token limit.
    
    Args:
        documents (List[Document]): A list of Document objects containing text chunks.
        max_tokens (int): The maximum number of tokens allowed for each chunk.
    
    Returns:
        List[str]: A list of merged text strings.
    """
    merged_texts = []
    current_chunk = ""
    
    for doc in documents:
        text = doc.page_content
        if not text:
            continue
        
        # Check if adding the new text exceeds the max token limit
        if len(current_chunk.split()) + len(text.split()) > max_tokens:
            merged_texts.append(current_chunk)
            current_chunk = text
        else:
            current_chunk += " " + text
    
    if current_chunk:
        merged_texts.append(current_chunk)
    
    logger.debug(f"Merged {len(merged_texts)} chunks into larger text blocks.")
    return merged_texts



def summarize_documents(
        documents: List[Document],
        llm_settings: dict) -> str:
    """
    Summarizes a list of Document objects using OpenAI's GPT model.
    Args:
        documents (List[Document]): A list of Document objects containing text chunks.
        llm_settings (dict): The settings for the summarization.
    Returns:
        str: The summarized text.
    """

    if not documents:
        raise ValueError("The documents list is empty. Please provide valid Document objects.")
    
    if not isinstance(documents, list):
        raise ValueError("The documents parameter must be a list of Document objects.")
    
    # Get the maximum tokens for the model
    model = llm_settings.get("model", "gpt-4o")
    max_tokens = get_max_tokens(model)
    if not max_tokens:
        raise ValueError(f"Model {model} is not supported or does not have a defined max token limit.")
    
    # Summarize each document
    merged_texts = merge_chunks(documents, max_tokens)

    summaries = []
    for i, chunk in enumerate(merged_texts):
        logger.debug(f"Summarizing chunk {i+1}/{len(merged_texts)} with length {len(chunk.split())} tokens.")
        summary = summarize_text(chunk, llm_settings)
        summaries.append(summary)

    logger.debug(f"Generated {len(summaries)} summaries from the provided documents.")
    if len(summaries) == 0:
        return "No summaries generated. Please check the input documents."
    return "\n".join(summaries)


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
    if not text:
        return "No content to summarize."

    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OpenAI API key is not set. Please check your environment variables.")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    try:
        # Extract settings from the llm_settings dictionary
        model = llm_settings.get("model", "gpt-4o")
        temperature = llm_settings.get("temperature", 0.2)

        # Prepare the request for summarization
        text_guidelined = prepare_summary_request(text, llm_settings)
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
        logger.error(f"Error during OpenAI API call: {e}")

    summary = response.choices[0].message.content
    return summary


def prepare_summary_request(text: str, llm_settings: dict) -> str:

    yaml_config = {
        "Output language summary must be in": llm_settings.get("language", "italian"),
        "The length of the summary must be: ": llm_settings.get("length", "short"),
        "Style of the summary must be: ": llm_settings.get("style", "formal"),
        "Include quotes from the text": llm_settings.get("include_quotes", False),
        "Use bullet points in the summary": llm_settings.get("bullet_points", False),
        "Include statistics in the summary": llm_settings.get("include_stats", False),
    }

    # YAML stringa strutturata
    yaml_prompt = yaml.dump(yaml_config, sort_keys=False, default_flow_style=False)

    # Prompt finale completo
    final_prompt = (
        "You are a helpful assistant. Please summarize the following text according to these instructions:\n"
        f"```yaml\n{yaml_prompt}```\n"
        f"Here is the text:\n\n{text}"
    )

    logger.debug(f"Prepared yaml: {yaml_prompt}...")  

    return final_prompt
