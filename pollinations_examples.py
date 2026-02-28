#!/usr/bin/env python3
"""
Examples that use pollinations_openwebui.PollinationsClient
Adjust API key as needed.
"""

from pollinations_openwebui import PollinationsClient

API_KEY = None  # set to "sk_..." or "pk_..." if you have one

def example_text_simple():
    client = PollinationsClient(api_key=API_KEY)
    prompt = "Write a haiku about coding"
    print("Simple text GET /text/{prompt}:")
    resp = client.text_simple(prompt, model="openai", temperature=0.5)
    print(resp)

def example_chat():
    client = PollinationsClient(api_key=API_KEY)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Give me three tips for writing clean Python code."}
    ]
    print("Chat completions /v1/chat/completions:")
    resp = client.chat_completions(messages, model="openai", temperature=0.7, max_tokens=300)
    print(resp)

def example_image_save():
    client = PollinationsClient(api_key=API_KEY)
    prompt = "A serene mountain landscape with a river at sunrise"
    print("Generating image and saving to file:")
    result = client.generate_image_to_file(prompt, out_path="mountain.png", model="flux", width=1024, height=1024)
    print(result)

def example_account():
    client = PollinationsClient(api_key=API_KEY)
    print("Account profile (requires API key):")
    print(client.account_profile())
    print("Account balance (requires API key):")
    print(client.account_balance())

if __name__ == "__main__":
    print("Running Pollinations examples (adjust API_KEY in file to use auth-required endpoints)\n")
    example_text_simple()
    example_chat()
    example_image_save()
    # example_account()  # enable if you set API_KEY
