from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse
import asyncio

app = FastAPI()
mcp = FastMCP("filesystem")

# Örnek bir MCP aracı
@mcp.tool()
def read_file(path: str) -> str:
    """Belirtilen yoldaki dosyayı okur"""
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return "Dosya bulunamadı"

# SSE endpoint'i oluşturma
@app.get("/events")
async def sse_endpoint():
    async def event_generator():
        # MCP sunucusundan veri akışını simüle ediyoruz
        while True:
            yield {"event": "message", "data": "MCP sunucusu çalışıyor"}
            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
