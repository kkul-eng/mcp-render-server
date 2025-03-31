from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from mcp.server.fastmcp import FastMCP
import os
import traceback
import re
import string
import json
import requests
from collections import Counter
from dotenv import load_dotenv

# .env dosyasını yükle (eğer varsa)
load_dotenv()

# API anahtarını çevresel değişkenlerden veya doğrudan kod içinden al
API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyD4XHl_tmjeLX4SlENsngRy9auqNGpTuXk")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"
HEADERS = {"Content-Type": "application/json"}

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

def metni_temizle(metin):
    """Metni noktalama işaretlerinden arındırır ve küçük harfe çevirir."""
    translator = str.maketrans('', '', string.punctuation)
    temiz_metin = metin.translate(translator)
    return temiz_metin.lower()

def kelime_koklerini_bul(metin):
    """Metindeki kelimelerin köklerini bulur."""
    temiz_metin = metni_temizle(metin)
    kelimeler = temiz_metin.split()
    
    # Stop words'leri kaldır
    kelimeler = [k for k in kelimeler if k not in TURKISH_STOPWORDS and len(k) > 2]
    
    # Türkçe ekleri kaldır
    kokler = []
    for kelime in kelimeler:
        ekler = [
            'lar', 'ler', 'dir', 'dır', 'tir', 'tır', 'dan', 'den', 'tan', 'ten', 
            'nın', 'nin', 'nun', 'nün', 'ın', 'in', 'un', 'ün', 'da', 'de', 'ta', 'te',
            'ya', 'ye', 'yla', 'yle', 'sına', 'sine', 'arak', 'erek', 'mak', 'mek',
            'acak', 'ecek', 'muş', 'müş', 'mış', 'miş'
        ]
        
        orjinal_kelime = kelime
        degisti = True
        
        while degisti and len(kelime) > 3:
            degisti = False
            for ek in ekler:
                if kelime.endswith(ek) and len(kelime) - len(ek) > 2:
                    kelime = kelime[:-len(ek)]
                    degisti = True
                    break
        
        kokler.append(orjinal_kelime)
        if kelime != orjinal_kelime:
            kokler.append(kelime)
    
    return list(set(kokler))

def n_gram_olustur(metin, n=2):
    """Metinden n-gram'lar oluşturur."""
    kelimeler = metni_temizle(metin).split()
    ngrams = []
    
    for i in range(len(kelimeler) - n + 1):
        ngrams.append(' '.join(kelimeler[i:i+n]))
    
    return ngrams

def metinleri_bolumle(dokuman):
    """Dokümanı mantıksal bölümlere ayırma fonksiyonu."""
    # Önce metni paragraf ve olası başlıklara göre böl
    rough_splits = re.split(r'\n\s*\n', dokuman)
    
    sections = []
    current_section = ""
    
    for split in rough_splits:
        split = split.strip()
        if not split:
            continue
            
        # Başlık olabilecek satırları kontrol et
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

def soru_turu_belirle(soru):
    """Sorunun türünü belirler."""
    soru_lower = soru.lower()
    
    soru_tipi = "bilgi"  # Varsayılan
    
    if any(kw in soru_lower for kw in ["ne zaman", "ne zamandır", "hangi tarihte", "tarihi", "tarihinde"]):
        soru_tipi = "zaman"
    elif any(kw in soru_lower for kw in ["nerede", "hangi ülke", "hangi şehir", "ülkesi", "şehri", "konumu", "sınıflandırılır", "sınıflandırma"]):
        soru_tipi = "mekan"
    elif any(kw in soru_lower for kw in ["kim", "kime", "kimin", "kimdir", "kişi", "kimler"]):
        soru_tipi = "kişi"
    elif any(kw in soru_lower for kw in ["neden", "niçin", "niye", "sebebi", "nedeni"]):
        soru_tipi = "neden"
    elif any(kw in soru_lower for kw in ["nasıl", "ne şekilde", "hangi yöntemle", "yöntemi", "yöntem"]):
        soru_tipi = "yöntem"
    
    return soru_tipi

def bolumleri_puanla(bölümler, soru):
    """Bölümleri sorguya göre puanlar ve en iyi bölümleri döndürür."""
    
    soru_kokleri = kelime_koklerini_bul(soru)
    soru_kelimeler = soru.lower().split()
    soru_ngramlar = n_gram_olustur(soru, 2) + n_gram_olustur(soru, 3)
    soru_tipi = soru_turu_belirle(soru)
    
    puanlı_bölümler = []
    
    for bölüm in bölümler:
        bölüm_lower = bölüm.lower()
        bölüm_temiz = metni_temizle(bölüm_lower)
        
        # Tam eşleşme puanları
        tam_eslesme_puanı = 0
        if soru.lower() in bölüm_lower:
            tam_eslesme_puanı = 100
        
        # Kök eşleşme puanları
        kök_puanı = sum(3 for kök in soru_kokleri if kök in bölüm_temiz.split())
        
        # N-gram eşleşme puanları
        ngram_puanı = sum(5 for ng in soru_ngramlar if ng in bölüm_temiz)
        
        # Kelime eşleşme puanları
        kelime_puanı = sum(2 for kelime in soru_kelimeler if kelime in bölüm_temiz.split())
        
        # Özel kelime veya sınıflandırma ifadeleri arama
        özel_kelime_puanı = 0
        # Mekan/sınıflandırma soruları için özel
        if soru_tipi == "mekan":
            if any(ifade in bölüm_lower for ifade in [
                "sınıflandırılır", "sınıflandırma", "kategorisinde", "kategorize", 
                "grubunda", "grubuna", "grubu", "bölümde", "bölümünde", "kısmında",
                "kapsamında", "dahilinde", "içinde", "içerisinde", "arasında", "türünde"
            ]):
                özel_kelime_puanı += 50
        
        # Toplam puan hesapla
        toplam_puan = tam_eslesme_puanı + kök_puanı + ngram_puanı + kelime_puanı + özel_kelime_puanı
        
        # Bölüm içindeki anahtar kelime yoğunluğu
        bölüm_kelimeleri = bölüm_temiz.split()
        bölüm_uzunluğu = len(bölüm_kelimeleri)
        
        if bölüm_uzunluğu > 0:
            # Çok uzun bölümleri cezalandır
            if bölüm_uzunluğu > 500:
                toplam_puan *= 0.8
            elif bölüm_uzunluğu > 300:
                toplam_puan *= 0.9
            elif bölüm_uzunluğu < 20:  # Çok kısa bölümleri cezalandır
                toplam_puan *= 0.7
        
        # Puan yeterince yüksekse listeye ekle
        if toplam_puan > 5:
            puanlı_bölümler.append((toplam_puan, bölüm))
    
    # Puanlara göre sırala (en yüksekten en düşüğe)
    puanlı_bölümler.sort(key=lambda x: -x[0])
    
    return puanlı_bölümler

def api_ile_soru_sor(soru, metinler):
    """API'ye soruyu ve ilgili metinleri gönderir."""
    try:
        ilgili_icerik = "\n\n".join([f"Bölüm {i+1}:\n{metin}" for i, metin in enumerate(metinler)])
        istem = (
            f"Aşağıdaki metinlerden '{soru}' sorusunun cevabını bul:\n\n"
            f"{ilgili_icerik}\n\n"
            "Yanıtı kısa ve net şekilde, 2-3 cümle içinde ver. "
            "Eğer soruda geçen terimler veya kavramlar metinde tam olarak tanımlanmamışsa "
            "bile benzer ve ilgili bilgileri kullanarak yanıt oluştur. "
            "Eğer hiçbir ilgili bilgi yoksa 'Dokümanda bu bilgi bulunamadı.' yaz."
        )
        
        veri = {
            "contents": [
                {
                    "parts": [
                        {"text": istem}
                    ]
                }
            ]
        }
        
        yanit = requests.post(API_URL, headers=HEADERS, data=json.dumps(veri))
        yanit.raise_for_status()
        sonuc = yanit.json()
        cevap = sonuc.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "API yanıt vermedi.")
        return cevap.strip()
    except Exception as e:
        print(f"API hatası: {str(e)}")
        # API'de sorun olursa yerel algoritma sonuçlarını kullan
        return None

def yerel_yanit_olustur(puanlı_bölümler, soru):
    """En iyi bölümlerden soru için en uygun yanıtı oluşturur."""
    if not puanlı_bölümler:
        return "Dokümanda bu bilgi bulunamadı."
    
    # En yüksek puanlı bölümü al
    en_iyi_bölüm = puanlı_bölümler[0][1]
    
    # Bölüm uzunluğuna bak
    if len(en_iyi_bölüm.split()) < 150:
        # Kısa bölüm, olduğu gibi döndür
        return en_iyi_bölüm
    
    # Uzun bölüm, cümlelere ayır ve en iyilerini seç
    cümleler = cümlelere_böl(en_iyi_bölüm)
    puanlı_cümleler = cümleleri_puanla(cümleler, soru)
    
    # İlk 5 en iyi cümleyi orijinal sırasında birleştir
    en_iyi_cümleler = [pc[1] for pc in puanlı_cümleler[:5]]
    
    # Eğer tek bir cümle bulunabildiyse ve yetersizse, ikinci en iyi bölümü de kontrol et
    if len(en_iyi_cümleler) <= 1 and len(puanlı_bölümler) > 1:
        ikinci_bölüm = puanlı_bölümler[1][1]
        ikinci_cümleler = cümlelere_böl(ikinci_bölüm)
        ikinci_puanlı_cümleler = cümleleri_puanla(ikinci_cümleler, soru)
        
        # İkinci bölümden en iyi 2 cümleyi ekle
        ikinci_en_iyi = [pc[1] for pc in ikinci_puanlı_cümleler[:2]]
        en_iyi_cümleler.extend(ikinci_en_iyi)
    
    # Cümleleri orijinal sırada düzenle
    tüm_cümleler = []
    for bölüm in [puanlı_bölümler[0][1]] + ([puanlı_bölümler[1][1]] if len(puanlı_bölümler) > 1 else []):
        cümleler = cümlelere_böl(bölüm)
        for cümle in cümleler:
            if cümle in en_iyi_cümleler and cümle not in tüm_cümleler:
                tüm_cümleler.append(cümle)
    
    # Eğer hiç cümle bulunamadıysa, en iyi bölümü kısalt
    if not tüm_cümleler:
        cümleler = cümlelere_böl(en_iyi_bölüm)
        tüm_cümleler = cümleler[:3]  # İlk 3 cümleyi al
    
    # Cevabı düzenle
    yanıt = " ".join(tüm_cümleler)
    
    # Fazla uzunsa kısalt
    if len(yanıt) > 1000:
        yanıt = yanıt[:997] + "..."
    
    return yanıt

def cümlelere_böl(metin):
    """Metni cümlelere ayırır - Türkçe için iyileştirilmiş."""
    # Kısaltmaları tanı
    metin = re.sub(r'(?<!\w)(Dr|vb|Bkz|bkz|A\.Ş|Ltd|Şti|T\.C|vs)\.',
                 lambda m: m.group(0).replace('.', '<DOT>'), metin)
    
    # Rakamlardan sonra gelen noktaları işaretle
    metin = re.sub(r'(\d)\.', r'\1<DOT>', metin)
    
    # Cümleleri ayır
    cümleler = re.split(r'(?<=[.!?…])\s+', metin)
    
    # İşaretleri geri al
    cümleler = [c.replace('<DOT>', '.').strip() for c in cümleler]
    
    # Boş cümleleri filtrele
    return [c for c in cümleler if c and len(c) > 5]

def cümleleri_puanla(cümleler, soru):
    """Cümleleri sorguya göre puanlar ve en iyi cümleleri döndürür."""
    soru_kokleri = kelime_koklerini_bul(soru)
    soru_kelimeler = [k.lower() for k in soru.split()]
    
    puanlı_cümleler = []
    
    for cümle in cümleler:
        cümle_lower = cümle.lower()
        cümle_temiz = metni_temizle(cümle_lower)
        
        # Tam eşleşme puanları
        tam_eslesme_puanı = 0
        if soru.lower() in cümle_lower:
            tam_eslesme_puanı = 100
        
        # Kök eşleşme puanları
        kök_puanı = sum(3 for kök in soru_kokleri if kök in cümle_temiz.split())
        
        # Kelime eşleşme puanları
        kelime_puanı = sum(2 for kelime in soru_kelimeler if kelime in cümle_temiz.split())
        
        # Özel sınıflandırma ifadeleri
        if any(ifade in cümle_lower for ifade in [
            "sınıflandırılır", "sınıflandırma", "kategorisinde", "kategorize", 
            "grubunda", "grubuna", "grubu", "bölümde", "bölümünde", "kısmında",
            "kapsamında", "dahilinde", "içinde", "içerisinde", "arasında", "türünde",
            "yerleştirilir", "bulunmaktadır", "girebilir", "girer", "düşer"
        ]):
            kelime_puanı += 30
        
        toplam_puan = tam_eslesme_puanı + kök_puanı + kelime_puanı
        
        # Puan yeterince yüksekse listeye ekle
        if toplam_puan > 0:
            puanlı_cümleler.append((toplam_puan, cümle))
    
    # Puanlara göre sırala (en yüksekten en düşüğe)
    puanlı_cümleler.sort(key=lambda x: -x[0])
    
    return puanlı_cümleler

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
def document_qa(question: str, doc_name: str = "izahname.txt", use_api: bool = True) -> str:
    """İzahnamede soru yanıtlar - API ve yerel algoritma destekli"""
    try:
        # Debug için çalışma dizinini ve mevcut dosyaları yazdır
        print(f"Çalışma dizini: {os.getcwd()}")
        print(f"Aranan dosya: {doc_name}")
        print(f"Mevcut dosyalar: {os.listdir('.')}")
        
        # Dokümanı doğrudan kök dizinden oku
        doc_path = doc_name
        
        with open(doc_path, "r", encoding="utf-8") as f:
            document = f.read()
        
        # Özel soru anahtar kelimeleri kontrol et
        ozel_kelimeler = {
            "sınıflandırılır": ["kategori", "grup", "bölüm", "fasıl", "kısım", "alt başlık"],
            "metalize iplik": ["metalize iplik", "metal kaplı", "metal iplik", "metalleştirilmiş iplik", "metalik"],
        }
        
        # Soruyu analiz et ve özel kelimelerle genişlet
        genisletilmis_soru = question
        for anahtar, esanlamlar in ozel_kelimeler.items():
            if anahtar in question.lower():
                genisletilmis_soru = f"{question} {' '.join(esanlamlar)}"
        
        # Dokümanı mantıksal bölümlere ayır
        bölümler = metinleri_bolumle(document)
        print(f"Doküman {len(bölümler)} bölüme ayrıldı.")
        
        # Bölümleri puanla
        puanlı_bölümler = bolumleri_puanla(bölümler, genisletilmis_soru)
        
        if not puanlı_bölümler:
            return "Dokümanda bu bilgi bulunamadı."
        
        # En iyi bölümleri al
        en_iyi_metinler = [b[1] for b in puanlı_bölümler[:3]]
        
        # API kullanım seçeneği
        if use_api:
            try:
                # API ile yanıt oluştur
                api_yanıt = api_ile_soru_sor(question, en_iyi_metinler)
                
                # API yanıt verdiyse onu kullan
                if api_yanıt:
                    return api_yanıt
                # API yanıt vermediyse yerel algoritmaya düş
                else:
                    print("API yanıt vermedi, yerel algoritma kullanılıyor...")
                    return yerel_yanit_olustur(puanlı_bölümler, genisletilmis_soru)
            except Exception as e:
                print(f"API hatası: {str(e)}, yerel algoritma kullanılıyor...")
                return yerel_yanit_olustur(puanlı_bölümler, genisletilmis_soru)
        else:
            # API kullanılmıyorsa doğrudan yerel algoritmayı kullan
            return yerel_yanit_olustur(puanlı_bölümler, genisletilmis_soru)
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
            # API kullanım parametresini kontrol et
            use_api = args.get("use_api", True)
            if "use_api" in args:
                del args["use_api"]  # args'dan use_api'yi çıkar (document_qa'da kullanabilmek için)
            result = document_qa(**args, use_api=use_api)
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
