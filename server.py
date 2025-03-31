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
def semantic_similarity(text1, text2):
    """İki metin arasındaki anlamsal benzerliği hesaplar"""
    # Metinleri temizle ve küçük harfe çevir
    def clean_text(text):
        # Özel karakterleri kaldır ve küçük harfe çevir
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
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
    
    # Toplam kelime sayısı
    total_words = sum(words1.values()) + sum(words2.values())
    
    # Normalize edilmiş benzerlik skoru
    return 2 * common_score / total_words if total_words > 0 else 0

# Dokümanları bölümlere ayırma fonksiyonu - paragraflardan daha mantıksal bölümler
def split_into_sections(text):
    """
    Metni daha anlamlı bölümlere ayırır.
    Boş satırlar, başlıklar ve noktalama işaretlerini dikkate alır.
    """
    # Önce metni paragraf ve olası başlıklara göre böl
    rough_splits = re.split(r'\n\s*\n', text)
    
    sections = []
    current_section = ""
    
    for split in rough_splits:
        split = split.strip()
        if not split:
            continue
            
        # Başlık olabilecek satırları kontrol et (kısa, tüm kelimeler büyük harf başlıyor veya sonunda : var)
        lines = split.split('\n')
        first_line = lines[0].strip()
        
        # Başlık olabilecek durumlar
        is_heading = (
            (len(first_line) < 100 and first_line.isupper()) or  # Tamamen büyük harf
            (len(first_line) < 100 and first_line.endswith(':')) or  # ":" ile biten
            (len(first_line) < 100 and all(w[0].isupper() for w in first_line.split() if w and w[0].isalpha())) or  # Her kelime büyük harfle başlıyor
            (len(first_line) < 50 and len(lines) == 1)  # Kısa tek satır
        )
        
        if is_heading and current_section:
            # Önceki bölümü kaydet ve yeni bölüme başla
            sections.append(current_section)
            current_section = split
        else:
            # Mevcut bölüme ekle
            if current_section:
                current_section += "\n\n" + split
            else:
                current_section = split
    
    # Son bölümü ekle
    if current_section:
        sections.append(current_section)
    
    return sections

# Cümlelere ayırma fonksiyonu - Türkçe özel durumlar için iyileştirilmiş
def split_into_sentences(text):
    """Metni cümlelere ayırır - Türkçe için iyileştirilmiş"""
    # Çeşitli kısaltmaları tanı (Dr., vb., bkz. gibi)
    abbreviations = r'(?<!\w)(Dr|vb|Bkz|bkz|A\.Ş|Ltd|Şti|T\.C|vs|Inc|S\.A|B\.V|[A-Z])\.'
    
    # Kısaltmaları geçici işaretle
    text = re.sub(abbreviations, r'\1_DOTABBR_', text)
    
    # Rakamlardan sonra gelen noktaları (1. 2. gibi) işaretle
    text = re.sub(r'(\d)\.', r'\1_DOTNUM_', text)
    
    # Cümleleri ayır
    sentences = re.split(r'(?<=[.!?…])\s+', text)
    
    # İşaretleri geri al
    sentences = [s.replace('_DOTABBR_', '.').replace('_DOTNUM_', '.').strip() for s in sentences]
    
    # Boş olanları filtrele
    return [s for s in sentences if s and len(s) > 5]  # En az 5 karakter olan cümleleri kabul et

# Türkçe stop kelimeler
TURKISH_STOPWORDS = {
    "acaba", "altı", "ama", "ancak", "arada", "artık", "asla", "aslında", "ayrıca", 
    "bana", "bazen", "bazı", "bazıları", "belki", "ben", "beni", "benim", "beş", 
    "bile", "bir", "birçok", "biri", "birkaç", "birkez", "birşey", "birşeyi", "biz", 
    "bize", "bizden", "bizi", "bizim", "böyle", "böylece", "bu", "buna", "bunda", 
    "bundan", "bunu", "bunun", "burada", "çok", "çünkü", "da", "daha", "dahi", 
    "de", "defa", "değil", "diğer", "diye", "dokuz", "dolayı", "dolayısıyla", 
    "dört", "elbette", "en", "fakat", "falan", "felan", "filan", "gene", "gibi", 
    "hangi", "hangisi", "hani", "hatta", "hem", "henüz", "hep", "hepsi", "her", 
    "herhangi", "herkes", "herkese", "herkesi", "hiç", "hiçbir", "hiçbiri", "için", 
    "içinde", "iki", "ile", "ilgili", "ise", "işte", "itibaren", "itibariyle", 
    "kaç", "kadar", "karşın", "kendi", "kendine", "kendini", "ki", "kim", "kime", 
    "kimi", "kimin", "kimisi", "madem", "mı", "mi", "mu", "mü", "nasıl", "ne", 
    "neden", "nedenle", "nerde", "nerede", "nereye", "neyse", "niçin", "niye", "on", 
    "ona", "ondan", "onlar", "onlara", "onlardan", "onların", "onu", "onun", "orada", 
    "oysa", "oysaki", "öbür", "ön", "önce", "ötürü", "öyle", "rağmen", "sana", "sekiz", 
    "sen", "senden", "seni", "senin", "siz", "sizden", "size", "sizi", "sizin", "son", 
    "sonra", "şayet", "şey", "şeyden", "şeye", "şeyi", "şeyler", "şu", "şuna", "şunda", 
    "şundan", "şunlar", "şunu", "şunun", "tabi", "tamam", "tüm", "tümü", "üç", "üzere", 
    "var", "ve", "veya", "ya", "yani", "yedi", "yerine", "yine", "yoksa", "zaten", "zira"
}

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
        
        # Sorunun anlamlı kelimelerini çıkar
        def extract_keywords(text):
            # Noktalama işaretlerini kaldır
            text = re.sub(r'[^\w\s]', ' ', text.lower())
            # Birden fazla boşlukları temizle
            text = re.sub(r'\s+', ' ', text).strip()
            words = text.split()
            # Stop kelimeleri ve 2 harften kısa kelimeleri çıkar
            return [w for w in words if w not in TURKISH_STOPWORDS and len(w) > 2]
        
        question_keywords = extract_keywords(question)
        print(f"Soru anahtar kelimeleri: {question_keywords}")
        
        # Soru türünü belirle
        question_type = "bilgi"  # Varsayılan soru türü
        question_lower = question.lower()
        
        if any(kw in question_lower for kw in ["ne zaman", "ne zamandır", "hangi tarihte", "tarihi", "tarihinde"]):
            question_type = "zaman"
        elif any(kw in question_lower for kw in ["nerede", "hangi ülke", "hangi şehir", "ülkesi", "şehri", "konumu"]):
            question_type = "mekan"
        elif any(kw in question_lower for kw in ["kim", "kime", "kimin", "kimdir", "kişi", "kimler"]):
            question_type = "kişi"
        elif any(kw in question_lower for kw in ["neden", "niçin", "niye", "sebebi", "nedeni"]):
            question_type = "neden"
        elif any(kw in question_lower for kw in ["nasıl", "ne şekilde", "hangi yöntemle", "yöntemi"]):
            question_type = "yöntem"
        
        print(f"Belirlenen soru türü: {question_type}")
        
        # Dokümanı anlamlı bölümlere ayır
        sections = split_into_sections(document)
        print(f"Doküman {len(sections)} bölüme ayrıldı.")
        
        # Her bölümü değerlendir
        scored_sections = []
        for section in sections:
            # Temel skor
            score = 0
            
            # Tam sorgu eşleşmesi kontrolü
            if question.lower() in section.lower():
                score += 100
                print("Tam eşleşme bulundu!")
            
            # Bölüm içindeki anahtar kelimeler
            section_keywords = extract_keywords(section)
            
            # Anahtar kelime eşleşmesi
            for keyword in question_keywords:
                if keyword in section_keywords:
                    # Eşleşen her anahtar kelime için puan
                    keyword_freq = section_keywords.count(keyword)
                    # Eğer kelime birden fazla geçiyorsa daha önemli olabilir
                    score += min(keyword_freq * 8, 40)  # Maksimum 40 puan
                    
                    # Yakın anahtar kelimeler için bonus
                    for other_kw in question_keywords:
                        if other_kw != keyword and other_kw in section_keywords:
                            # İki kelimenin yakın geçmesi için bonus
                            section_text = section.lower()
                            idx1 = section_text.find(keyword)
                            idx2 = section_text.find(other_kw)
                            if idx1 >= 0 and idx2 >= 0:
                                proximity = abs(idx1 - idx2)
                                if proximity < 50:  # Çok yakın
                                    score += 15
                                elif proximity < 100:  # Yakın
                                    score += 8
                                elif proximity < 200:  # Orta uzaklık
                                    score += 3
            
            # Sorudaki anahtar kelimelerin bölümde kapsanma oranı
            unique_section_kws = set(section_keywords)
            unique_question_kws = set(question_keywords)
            matched_kws = unique_question_kws.intersection(unique_section_kws)
            
            coverage_ratio = len(matched_kws) / len(unique_question_kws) if unique_question_kws else 0
            score += coverage_ratio * 100  # %100 kapsama için 100 puan
            
            # Sorunun tipine göre ekstra puanlama
            if question_type == "zaman" and re.search(r'\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b|\b\d{4}\b|ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık', section.lower()):
                score += 30
            elif question_type == "mekan" and re.search(r'\b(türkiye|istanbul|ankara|izmir|antalya|ülke|şehir|ilçe|cadde|sokak|mahalle)\b', section.lower()):
                score += 30
            elif question_type == "kişi" and re.search(r'\b(sayın|bay|bayan|müdür|başkan|direktör|yönetici|dr|prof|doç)\b', section.lower()):
                score += 30
            elif question_type == "neden" and re.search(r'\b(çünkü|nedeniyle|dolayı|sebebiyle|amacıyla)\b', section.lower()):
                score += 30
            elif question_type == "yöntem" and re.search(r'\b(şekilde|yöntemle|biçimde|suretiyle|aracılığıyla)\b', section.lower()):
                score += 30
            
            # Bölüm uzunluğuna göre normalizasyon
            words_count = len(section.split())
            if words_count < 20:  # Çok kısa
                score *= 0.7  # Kısa metinleri cezalandır
            elif words_count > 500:  # Çok uzun
                score *= 0.8  # Uzun metinleri biraz cezalandır
            elif words_count > 300:  # Uzun
                score *= 0.9  # Uzun metinleri az cezalandır
            
            # Belirli bir skorun üzerindeyse listeye ekle
            if score > 10:
                scored_sections.append((score, section))
        
        # Skorlarına göre sırala
        scored_sections.sort(key=lambda x: -x[0])
        
        # Debug: İlk 3 skoru ve bölümü yazdır
        for i, (score, _) in enumerate(scored_sections[:3]):
            print(f"Top {i+1} bölüm skoru: {score}")
        
        # Bağlam için en iyi bölümleri seç
        if not scored_sections:
            return "Üzgünüm, izahnamede bu soruya yanıt bulunamadı."
            
        # En alakalı bölümü seç
        best_section = scored_sections[0][1]
        
        # Eğer bölüm çok uzunsa, en alakalı cümleleri bul
        if len(best_section.split()) > 150:
            sentences = split_into_sentences(best_section)
            
            # Cümleleri puanla
            scored_sentences = []
            for sentence in sentences:
                score = 0
                sentence_keywords = extract_keywords(sentence)
                
                # Anahtar kelime eşleşmesi
                for keyword in question_keywords:
                    if keyword in sentence_keywords:
                        score += 15
                        
                        # Soru türüne özel puanlar
                        if question_type == "zaman" and re.search(r'\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b|\b\d{4}\b|ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık', sentence.lower()):
                            score += 20
                        elif question_type == "mekan" and re.search(r'\b(türkiye|istanbul|ankara|izmir|antalya|ülke|şehir|ilçe|cadde|sokak|mahalle)\b', sentence.lower()):
                            score += 20
                        elif question_type == "kişi" and re.search(r'\b(sayın|bay|bayan|müdür|başkan|direktör|yönetici|dr|prof|doç)\b', sentence.lower()):
                            score += 20
                        elif question_type == "neden" and re.search(r'\b(çünkü|nedeniyle|dolayı|sebebiyle|amacıyla)\b', sentence.lower()):
                            score += 20
                        elif question_type == "yöntem" and re.search(r'\b(şekilde|yöntemle|biçimde|suretiyle|aracılığıyla)\b', sentence.lower()):
                            score += 20
                
                # Sorudaki anahtar kelimelerin kapsanma oranı
                matched_kws = set(sentence_keywords) & set(question_keywords)
                coverage = len(matched_kws) / len(set(question_keywords)) if question_keywords else 0
                score += coverage * 30
                
                # Cümle uzunluğuna göre puanlama - çok kısa cümleleri cezalandır
                if len(sentence.split()) < 5:
                    score *= 0.5
                
                if score > 0:
                    scored_sentences.append((score, sentence))
            
            # Skorlarına göre sırala
            scored_sentences.sort(key=lambda x: -x[0])
            
            # Debug: Cümleleri ve skorlarını yazdır
            for i, (score, sentence) in enumerate(scored_sentences[:3]):
                print(f"Top {i+1} cümle ({score}): {sentence[:50]}...")
            
            # En alakalı cümleleri al (en fazla 5)
            top_sentences = [s for _, s in scored_sentences[:5]]
            
            # Orijinal sıralamaya göre düzenle
            if top_sentences:
                ordered_sentences = [s for s in sentences if s in top_sentences]
                
                # Cümleleri birleştir
                result_text = " ".join(ordered_sentences)
                
                # Yeterince bilgi verdiğine emin olmak için kontrol et
                if len(result_text.split()) < 30 and len(scored_sections) > 1:
                    # İkinci en iyi bölümden de bilgi ekle
                    second_best = scored_sections[1][1]
                    second_sentences = split_into_sentences(second_best)
                    second_scored = []
                    
                    for sentence in second_sentences:
                        score = 0
                        sentence_keywords = extract_keywords(sentence)
                        
                        for keyword in question_keywords:
                            if keyword in sentence_keywords:
                                score += 10
                        
                        matched_kws = set(sentence_keywords) & set(question_keywords)
                        coverage = len(matched_kws) / len(set(question_keywords)) if question_keywords else 0
                        score += coverage * 20
                        
                        if score > 0:
                            second_scored.append((score, sentence))
                    
                    second_scored.sort(key=lambda x: -x[0])
                    second_top = [s for _, s in second_scored[:2]]
                    
                    if second_top:
                        result_text += "\n\n" + " ".join(second_top)
            else:
                # Eğer cümle puanlaması başarısız olursa orijinal bölümü kısalt
                sentences = best_section.split('.')
                result_text = '. '.join(sentences[:5]) + '.' if len(sentences) > 5 else best_section
        else:
            # Bölüm zaten kısa, olduğu gibi kullan
            result_text = best_section
            
            # Çok kısa ise ikinci en iyi bölümden de bilgi ekle
            if len(result_text.split()) < 30 and len(scored_sections) > 1:
                second_best = scored_sections[1][1]
                
                # İkinci bölüm ilk bölüme çok benzerse ekleme
                similarity = semantic_similarity(best_section, second_best)
                
                if similarity < 0.6:  # Benzerlik %60'dan az ise farklı bilgi içeriyor olabilir
                    # Çok uzun değilse tamamını ekle
                    if len(second_best.split()) < 100:
                        result_text += "\n\n" + second_best
                    else:
                        # Uzunsa cümlelere ayır ve en alakalı birkaç cümleyi ekle
                        second_sentences = split_into_sentences(second_best)
                        second_scored = []
                        
                        for sentence in second_sentences:
                            score = 0
                            sentence_keywords = extract_keywords(sentence)
                            
                            for keyword in question_keywords:
                                if keyword in sentence_keywords:
                                    score += 10
                            
                            if score > 0:
                                second_scored.append((score, sentence))
                        
                        second_scored.sort(key=lambda x: -x[0])
                        second_top = [s for _, s in second_scored[:3]]
                        
                        if second_top:
                            result_text += "\n\n" + " ".join(second_top)
        
        # Yanıtın soruya uygunluğunu son bir kez kontrol et
        answer_relevance = 0
        answer_keywords = extract_keywords(result_text)
        
        # Soruda geçen anahtar kelimelerin yanıtta ne kadarı var
        matched_keywords = set(question_keywords) & set(answer_keywords)
        keyword_coverage = len(matched_keywords) / len(set(question_keywords)) if question_keywords else 0
        
        # Yanıtın anahtar kelime yoğunluğu
        keyword_density = sum(1 for w in answer_keywords if w in question_keywords) / len(answer_keywords) if answer_keywords else 0
        
        # Toplam alakalılık skoru
        answer_relevance = (keyword_coverage * 0.7) + (keyword_density * 0.3)
        
        # Eğer yanıt yeterince ilgili değilse uyarı ekle
        if answer_relevance < 0.3:
            result_text = "Üzgünüm, izahnamede bu soruya doğrudan bir yanıt bulamadım, ancak aşağıdaki bilgiler yardımcı olabilir:\n\n" + result_text
        elif answer_relevance < 0.5:
            result_text = "İzahnamede sorunuza kısmen uyan bilgiler buldum:\n\n" + result_text
        
        # Sonucu döndür (uzunlukla ilgili son kontroller)
        if len(result_text) > 1000:
            # Son noktalı cümleyi bul
            last_sentence_end = 997
            for i in range(997, 0, -1):
                if i < len(result_text) and result_text[i] == '.' and (i + 1 == len(result_text) or result_text[i + 1] == ' '):
                    last_sentence_end = i + 1
                    break
            
            return result_text[:last_sentence_end] + "..."
        
        return result_text
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
