"""
Test script for the Recipe Assistant API.
Sends a random question from the ground-truth CSV to the API and prints the response.
Useful for quick automated checks that the API is running and functional.
"""

import pandas as pd
import requests

# Load ground-truth questions
df = pd.read_csv("data/ground-truth-retrieval.csv")
question = df.sample(n=1).iloc[0]['question']

print("question:", question)

url = "http://localhost:5000/question"
data = {"question": question}

# Send the question to the API
response = requests.post(url, json=data)

# Print the API's response
print(response.json())