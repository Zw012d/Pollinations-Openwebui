import requests

class PollinationsAPI:
    BASE_URL = 'https://api.pollinations.ai/'

    def __init__(self, api_key):
        self.api_key = api_key

    def query(self, endpoint, data):
        headers = {'Authorization': f'Bearer {self.api_key}'}
        response = requests.post(self.BASE_URL + endpoint, json=data, headers=headers)
        return response.json()

# Example usage:
if __name__ == '__main__':
    api_key = 'your_api_key_here'
    pollinations = PollinationsAPI(api_key)
    data = {'prompt': 'A beautiful landscape', 'size': '1024x1024'}
    result = pollinations.query('generate', data)
    print(result)