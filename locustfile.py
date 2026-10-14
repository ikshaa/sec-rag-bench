"""
Locust load test for the SEC-RAG-Bench API.

Each virtual user picks a random question from the pool, calls POST /query,
measures the response. The pool is diverse enough to produce a realistic
mix of cache hits and misses as the test progresses.

Run:
    locust -f locustfile.py --host http://localhost:8000

Then open http://localhost:8089 in your browser to configure the test.
"""

import random
from locust import HttpUser, task, between


QUESTIONS = [
    "What were Tesla total revenues in 2023?",
    "What were Tesla total revenues in 2024?",
    "What were Apple revenues in 2024?",
    "What were Apple revenues in 2023?",
    "What were Nvidia data center revenues in 2024?",
    "What were Microsoft total revenues in 2024?",
    "What were Google advertising revenues?",
    "What were Costco net sales in 2024?",
    "What were Netflix streaming revenues in 2024?",
    "What were Tesla main risk factors in 2023?",
    "What were Apple risk factors in 2024?",
    "How did Nvidia revenue change year over year?",
    "What was Apple R&D spending in 2024?",
    "What were Microsoft operating expenses in 2024?",
    "What are Tesla major product lines?",
    "What were Costco membership fees?",
    "What is Google main source of revenue?",
    "What were Apple services revenue in 2024?",
    "What were Microsoft cloud revenue in 2024?",
    "How much did Nvidia spend on R&D in 2024?",
]


class RAGUser(HttpUser):
    """
    Simulates one user hitting the /query endpoint repeatedly.
    wait_time is how long a user "thinks" between requests.
    """
    wait_time = between(1, 3)

    @task
    def query(self):
        question = random.choice(QUESTIONS)
        payload = {"question": question, "top_k": 5}
        self.client.post("/query", json=payload)