import os
import uvicorn
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "FastAPI uygulaması başarıyla çalışıyor!"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))  # Render'ın atadığı portu kullan
    uvicorn.run(app, host="0.0.0.0", port=port)

