import os
import uvicorn
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "FastAPI uygulaması başarıyla çalışıyor!"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))  # Varsayılan portu 10000 olarak ayarla
    uvicorn.run(app, host="0.0.0.0", port=port)
