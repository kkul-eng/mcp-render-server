import json
import requests
import argparse

# Yapılandırma dosyasını oku
with open("config.json", "r") as f:
    config = json.load(f)

url = config["mcpServers"]["filesystem"]["url"]

def ask_question(question, doc_name="izahname.txt"):
    response = requests.post(url, json={
        "tool": "document_qa",
        "args": {
            "question": question,
            "doc_name": doc_name
        }
    })
    return response.json()["result"]

def main():
    parser = argparse.ArgumentParser(description='İzahname QA Sistemi')
    parser.add_argument('soru', help='İzahnameye soracağınız soru')
    
    args = parser.parse_args()
    
    print(f"SORU: {args.soru}")
    print("-" * 50)
    answer = ask_question(args.soru)
    print(f"CEVAP:\n{answer}")

if __name__ == "__main__":
    main()
