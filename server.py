from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP
import os
import traceback

# FastAPI uygulamasını başlat
app = FastAPI(title="MCP Server API", 
              description="MicroCommand Protocol (MCP) sunucusu",
              version="1.0.0")

# CORS ayarlarını ekle
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MCP nesnesini oluştur
mcp = FastMCP("filesystem")

# Metinler arasındaki benzerlik oranını hesapla
def similarity_ratio(text1, text2):
    """İki metin arasındaki basit benzerlik oranını hesaplar"""
    # Metinleri küçük harfe çevir ve kelime listesi yap
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    # Kesişim ve birleşim büyüklüğünü hesapla
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    # Jaccard benzerlik katsayısı
    if union == 0:
        return 0
    return intersection / union

@mcp.tool()
def read_file(path: str) -> str:
    """Belirtilen yoldaki dosyayı okur"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Dosya bulunamadı"
    except Exception as e:
        return f"Dosya okuma hatası: {str(e)}"

@mcp.tool()
def document_qa(question: str, doc_name: str = "izahname.txt") -> str:
    """İzahnamede soru yanıtlar"""
    try:
        # Debug için çalışma dizinini ve mevcut dosyaları yazdır
        print(f"Çalışma dizini: {os.getcwd()}")
        print(f"Aranan dosya: {doc_name}")
        print(f"Mevcut dosyalar: {os.listdir('.')}")
        
        # Dokümanı doğrudan kök dizinden oku
        doc_path = doc_name
        
        with open(doc_path, "r", encoding="utf-8") as f:
            document = f.read()
        
        # Dokümanı bölümlere ayır
        sections = document.split('\n\n')
        
        # Soru kelimelerini hazırla
        # Stop kelimeleri çıkar (Türkçe için genel stop kelimeler)
        stop_words = {"ve", "veya", "ile", "bu", "şu", "o", "bir", "için", "mi", "ne", "nasıl", 
                     "nedir", "midir", "hangi", "kaç", "ne kadar", "kim", "kime", "nerede", "ne zaman"}
        
        # Soru kelimelerini çıkar
        words = []
        for word in question.lower().split():
            # Kelimeyi temizle (noktalama işaretlerini kaldır)
            word = ''.join(c for c in word if c.isalnum())
            if len(word) > 2 and word not in stop_words:
                words.append(word)
        
        # Daha sofistike bir puanlama algoritması
        scored_sections = []
        for section in sections:
            section_lower = section.lower()
            
            # Basit TF-IDF benzeri puanlama
            score = 0
            exact_match = False
            
            # Tam eşleşme için bonus
            if question.lower() in section_lower:
                exact_match = True
                score += 100
            
            # Her kelime için puan
            for word in words:
                if word in section_lower:
                    # Kelime frekansına göre puan
                    word_count = section_lower.count(word)
                    score += word_count * 10
                    
                    # Kelimeler birbirine yakınsa bonus puan
                    if len(words) > 1:
                        for other_word in words:
                            if other_word != word and other_word in section_lower:
                                # İki kelimenin yakınlığını kontrol et
                                if abs(section_lower.find(word) - section_lower.find(other_word)) < 100:
                                    score += 5
            
            # Bölüm uzunluğunu normalize et
            score = score / (len(section.split()) + 1)
            
            # Skorla birlikte bölümü sakla
            if score > 0:
                scored_sections.append((score, exact_match, section))
        
        # Skorlarına göre sırala (önce tam eşleşme, sonra puan)
        scored_sections.sort(key=lambda x: (not x[1], -x[0]))
        
        if scored_sections:
            # En alakalı 3 bölümü al, ama bunlar birbirine çok benziyorsa sadece 1-2 tane al
            top_sections = []
            for _, _, section in scored_sections[:3]:
                similar_to_existing = False
                for existing in top_sections:
                    if similarity_ratio(section, existing) > 0.7:  # %70 benzerlik eşiği
                        similar_to_existing = True
                        break
                
                if not similar_to_existing:
                    top_sections.append(section)
                
                # En fazla 2 bölüm al
                if len(top_sections) >= 2:
                    break
            
            result = "\n\n".join(top_sections)
            
            # Yanıt çok uzunsa, ilk 1000 karakterle sınırla
            if len(result) > 1000:
                result = result[:997] + "..."
                
            return result
        else:
            return "Üzgünüm, izahnamede bu soruya yanıt bulunamadı."
    except FileNotFoundError:
        return f"Doküman bulunamadı: {doc_name}"
    except Exception as e:
        return f"QA hatası: {str(e)}"

@app.get("/")
async def root():
    return {"message": "MCP Server çalışıyor", "info": "POST /mcp ile istek yapabilirsiniz"}

@app.post("/mcp")
async def run_mcp(query: dict = Body(...)):
    """
    MCP aracını çalıştır
    """
    try:
        # Debug için gelen isteği logla
        print(f"Gelen istek: {query}")
        
        tool_name = query.get("tool", "read_file")
        args = query.get("args", {"path": "sample.txt"})
        
        # Araç çalıştırma işlemini logla
        print(f"Çalıştırılıyor: tool={tool_name}, args={args}")
        
        # Doğru metodu kullanarak aracı çalıştır
        if tool_name == "read_file":
            result = read_file(**args)
        elif tool_name == "document_qa":
            result = document_qa(**args)
        else:
            raise ValueError(f"Bilinmeyen araç: {tool_name}")
        
        # Sonucu döndür
        return {"result": result}
    except Exception as e:
        # Hata detaylarını logla
        error_msg = str(e)
        stack_trace = traceback.format_exc()
        print(f"Hata: {error_msg}\n{stack_trace}")
        
        # Hata yanıtı döndür
        raise HTTPException(status_code=500, detail=f"MCP Hatası: {error_msg}")

# Uygulama başlat
if __name__ == "__main__":
    import uvicorn
    
    # Render'ın belirlediği port veya varsayılan 8000
    port = int(os.getenv("PORT", 8000))
    
    # Debug modunda çalıştır
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="debug")
