from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from mcp.server.fastmcp import FastMCP
import os
import traceback
import re
from collections import Counter

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

# Metinler arasındaki benzerlik oranını gelişmiş hesaplama
def improved_similarity(text1, text2):
    """İki metin arasındaki geliştirilmiş benzerlik hesaplama"""
    # Metinleri temizle ve küçük harfe çevir
    def clean_text(text):
        # Özel karakterleri kaldır ve küçük harfe çevir
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        return text
    
    clean_text1 = clean_text(text1)
    clean_text2 = clean_text(text2)
    
    # Her iki metindeki kelime frekanslarını hesapla
    words1 = Counter(clean_text1.split())
    words2 = Counter(clean_text2.split())
    
    # Ortak kelimeleri bul
    common_words = set(words1.keys()) & set(words2.keys())
    
    # Ortak kelime yoksa benzerlik 0
    if not common_words:
        return 0
    
    # Ortak kelimelerin frekanslarını kullanarak benzerlik puanı hesapla
    common_score = sum(min(words1[word], words2[word]) for word in common_words)
    total_words = sum(words1.values()) + sum(words2.values())
    
    # Benzerlik oranı
    return 2 * common_score / total_words if total_words > 0 else 0

# Cümlelere ayırma fonksiyonu
def split_into_sentences(text):
    """Metni cümlelere ayırır"""
    # Temel cümle ayırıcıları: nokta, soru işareti, ünlem işareti
    # Türkçe için özel ayarlamalar
    sentences = re.split(r'(?<=[.!?])\s+', text)
    # Boş cümleleri filtrele
    return [s.strip() for s in sentences if s.strip()]

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
    """İzahnamede soru yanıtlar - Geliştirilmiş bağlam anlayışı ile"""
    try:
        # Debug için çalışma dizinini ve mevcut dosyaları yazdır
        print(f"Çalışma dizini: {os.getcwd()}")
        print(f"Aranan dosya: {doc_name}")
        print(f"Mevcut dosyalar: {os.listdir('.')}")
        
        # Dokümanı doğrudan kök dizinden oku
        doc_path = doc_name
        
        with open(doc_path, "r", encoding="utf-8") as f:
            document = f.read()
        
        # Türkçe stop kelimeleri
        stop_words = {"ve", "veya", "ile", "bu", "şu", "o", "bir", "için", "mi", "ne", "nasıl", 
                     "nedir", "midir", "hangi", "kaç", "ne kadar", "kim", "kime", "nerede", "ne zaman",
                     "da", "de", "ki", "ya", "ise", "ama", "fakat", "lakin", "ancak", "yani", "çünkü",
                     "zira", "eğer", "ise", "şayet", "gibi", "kadar", "öyle", "böyle", "şöyle", "göre"}
        
        # Sorunun anlamlı kelimelerini çıkar
        def extract_keywords(text):
            # Noktalama işaretlerini kaldır
            text = re.sub(r'[^\w\s]', ' ', text.lower())
            words = text.split()
            # Stop kelimeleri ve 2 harften kısa kelimeleri çıkar
            return [w for w in words if w not in stop_words and len(w) > 2]
        
        question_keywords = extract_keywords(question)
        print(f"Soru anahtar kelimeleri: {question_keywords}")
        
        # Dokümanı paragraf ve cümlelere böl
        paragraphs = [p.strip() for p in document.split('\n\n') if p.strip()]
        
        # Paragrafları puanla
        scored_paragraphs = []
        for para in paragraphs:
            # Skoru sıfırla
            score = 0
            para_keywords = extract_keywords(para)
            
            # Tam soru eşleşmesi kontrolü
            if question.lower() in para.lower():
                score += 100
            
            # Anahtar kelime eşleşmesi
            for keyword in question_keywords:
                if keyword in para_keywords:
                    # Her bir eşleşen anahtar kelime için puan
                    keyword_freq = para_keywords.count(keyword)
                    score += keyword_freq * 5
                    
                    # Yakın anahtar kelimeler için bonus
                    for other_kw in question_keywords:
                        if other_kw != keyword and other_kw in para_keywords:
                            # İki kelimenin paragraftaki yakınlığı
                            para_lower = para.lower()
                            if (abs(para_lower.find(keyword) - para_lower.find(other_kw)) < 100):
                                score += 3
            
            # Sorudaki anahtar kelimelerden kaç tanesinin paragrafta bulunduğu
            unique_matches = len(set(question_keywords) & set(para_keywords))
            match_ratio = unique_matches / len(question_keywords) if question_keywords else 0
            score += match_ratio * 50
            
            # Paragraf uzunluğunu normalize et (çok uzun veya çok kısa paragrafları cezalandır)
            words_count = len(para.split())
            if words_count < 10:  # Çok kısa
                score *= 0.5
            elif words_count > 300:  # Çok uzun
                score *= 0.7
            else:  # Orta uzunluk (ideal)
                score *= 1.2
                
            if score > 0:
                scored_paragraphs.append((score, para))
        
        # Skor bazında sırala (en yüksek skordan en düşüğe)
        scored_paragraphs.sort(key=lambda x: -x[0])
        
        # Bağlam için en iyi paragrafları seç
        best_paragraphs = []
        if scored_paragraphs:
            # En yüksek puanlı paragrafı al
            best_paragraphs.append(scored_paragraphs[0][1])
            
            # İkinci en iyi paragrafı al, ama birinciye çok benzer değilse
            if len(scored_paragraphs) > 1:
                similarity = improved_similarity(scored_paragraphs[0][1], scored_paragraphs[1][1])
                if similarity < 0.6:  # %60'tan az benzerlik varsa farklı bilgi içeriyor olabilir
                    best_paragraphs.append(scored_paragraphs[1][1])
            
            # Eğer ilk iki paragraf bağlam için yetersizse, üçüncüye bak
            if len(scored_paragraphs) > 2 and len(best_paragraphs) < 2:
                similarity1 = improved_similarity(scored_paragraphs[0][1], scored_paragraphs[2][1])
                similarity2 = improved_similarity(scored_paragraphs[1][1], scored_paragraphs[2][1]) if len(best_paragraphs) > 1 else 1
                
                if similarity1 < 0.6 and similarity2 < 0.6:
                    best_paragraphs.append(scored_paragraphs[2][1])
            
            # Paragraflar içinde en alakalı cümleleri bulmaya çalış
            if len(best_paragraphs) == 1 and len(best_paragraphs[0].split()) > 100:
                # Paragrafı cümlelere ayır
                sentences = split_into_sentences(best_paragraphs[0])
                
                # Cümleleri puanla
                scored_sentences = []
                for sentence in sentences:
                    score = 0
                    sentence_keywords = extract_keywords(sentence)
                    
                    # Anahtar kelime eşleşmesi
                    for keyword in question_keywords:
                        if keyword in sentence_keywords:
                            score += 10
                    
                    # Sorudaki kelimelerden kaç tanesinin cümlede bulunduğu
                    unique_matches = len(set(question_keywords) & set(sentence_keywords))
                    match_ratio = unique_matches / len(question_keywords) if question_keywords else 0
                    score += match_ratio * 40
                    
                    if score > 0:
                        scored_sentences.append((score, sentence))
                
                # Skorlarına göre sırala
                scored_sentences.sort(key=lambda x: -x[0])
                
                # En alakalı cümleleri seç (en fazla 3)
                relevant_sentences = [s[1] for s in scored_sentences[:3]]
                
                # Cümleler arası bağlamı korumak için orijinal sıralamada birleştir
                if relevant_sentences:
                    original_order = []
                    for sentence in sentences:
                        if sentence in relevant_sentences:
                            original_order.append(sentence)
                    
                    # Cümleleri birleştir
                    best_paragraphs[0] = " ".join(original_order)
            
            # Sonucu birleştir
            result = "\n\n".join(best_paragraphs)
            
            # Sonuç çok uzunsa kısalt, ama anlamı korumaya çalış
            if len(result) > 1000:
                # Paragrafları koru ama uzunluğu sınırla
                paragraphs = result.split('\n\n')
                shortened_result = []
                remaining_chars = 997  # 3 karakter "..." için ayrılacak
                
                for p in paragraphs:
                    if len(p) <= remaining_chars:
                        shortened_result.append(p)
                        remaining_chars -= len(p)
                        # Paragraf ayırıcısı için karakter sayısını düş
                        if remaining_chars > 2:
                            remaining_chars -= 2
                        else:
                            break
                    else:
                        # Paragrafı cümlelere böl ve sığacak kadar cümle ekle
                        sentences = split_into_sentences(p)
                        paragraph_parts = []
                        
                        for s in sentences:
                            s_len = len(s) + 1  # Boşluk için 1 ekle
                            if s_len <= remaining_chars:
                                paragraph_parts.append(s)
                                remaining_chars -= s_len
                            else:
                                break
                        
                        if paragraph_parts:
                            shortened_result.append(" ".join(paragraph_parts))
                        break
                
                result = "\n\n".join(shortened_result) + "..."
            
            return result
        else:
            return "Üzgünüm, izahnamede bu soruya yanıt bulunamadı."
    except FileNotFoundError:
        return f"Doküman bulunamadı: {doc_name}"
    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"QA hatası: {str(e)}\n{error_detail}")
        return f"QA hatası: {str(e)}"

@app.get("/")
async def root():
    # Ana sayfa için index.html dosyasını döndür
    return FileResponse("index.html")

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
