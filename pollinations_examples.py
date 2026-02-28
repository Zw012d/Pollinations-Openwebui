# pollinations_examples.py

"""
Pollinations API Examples
This script contains examples of how to interact with the Pollinations API for text generation,
image generation, and chat conversations.
"""

import requests

# Example 1: Text Generation
def generate_text(prompt):
    response = requests.post('https://api.pollinations.ai/text', json={'prompt': prompt})
    return response.json()

# Usage
text_response = generate_text("Once upon a time in a land far, far away...")
print("Generated Text:", text_response)

# Example 2: Image Generation
def generate_image(prompt):
    response = requests.post('https://api.pollinations.ai/image', json={'prompt': prompt})
    return response.json()

# Usage
image_response = generate_image("A beautiful sunset over the ocean")
print("Generated Image URL:", image_response.get('url'))

# Example 3: Chat Conversations
def chat_with_pollinations(message):
    response = requests.post('https://api.pollinations.ai/chat', json={'message': message})
    return response.json()

# Usage
chat_response = chat_with_pollinations("Hello, how are you?")
print("Chat Response:", chat_response)