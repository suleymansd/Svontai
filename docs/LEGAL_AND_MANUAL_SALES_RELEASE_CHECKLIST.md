# SvontAI Hukuki ve Manuel Satış Yayın Kontrolü

Son güncelleme: 22 Temmuz 2026

Bu belge ürün içinde yayımlanan metinlerin operasyon kontrolüdür; hukuki veya mali müşavir görüşü değildir. Ücretli satış açılmadan önce aşağıdaki alanlar gerçek bilgilerle tamamlanmalı ve Türkiye'de yetkili hukukçu/mali müşavir tarafından kontrol edilmelidir.

## Zorunlu Satıcı / Veri Sorumlusu Bilgileri

- Gerçek kişi adı-soyadı veya ticaret unvanı
- Tebligata elverişli açık adres
- Destek e-postası ve telefon
- Vergi dairesi ve vergi/T.C. kimlik numarası (uygun olan)
- Varsa MERSIS ve ticaret sicil bilgileri
- Ödemeyi kabul eden banka hesabının gerçek sahibi
- Düzenlenecek mali belge türü ve düzenleme yöntemi

Bu bilgiler olmadan müşteriden ödeme istenmez, ücretli plan etkinleştirilmez ve kamuya “satışa açık” beyanı yapılmaz.

## Uzman Kontrolü

- `/kvkk`: veri sorumlusu kimliği, işleme şartları, yurt dışı aktarım mekanizması ve başvuru kanalı
- `/privacy`: alt işleyenler, saklama süreleri ve veri silme prosedürü
- `/terms`: hizmet sınırları, sorumluluk, askıya alma ve uyuşmazlık hükümleri
- `/openwa-consent`: WhatsApp koşulları, hesap kısıtlama riski ve alternatif resmi bağlantı
- `/service-agreement`: taraf bilgileri, hizmet seviyesi, ücret, süre, fesih ve sorumluluk sınırları
- `/manual-payment`: ön bilgilendirme, ödeme teyidi, yasal belge, iptal/iade ve tüketici hükümleri

## Uygulama Kanıtları

- Kayıtta koşul kabulü ile KVKK/gizlilik okuma beyanı ayrı kutulardır.
- Kabul kaydı; kullanıcı, metin sürümleri, zaman, IP ve User-Agent ile audit log'a yazılır.
- OpenWA risk onayı ayrı alınır ve sürümlü audit kaydı üretilir.
- Admin ödeme kanıtı olmadan ücretli planı etkinleştirmez.
- Teklif, sipariş formu, ödeme kanıtı ve mali belge numarası müşteri dosyasında saklanır.

## Sürüm Yönetimi

Hukuki metin sürümleri `backend/app/core/legal.py` ve `frontend/src/lib/legal.ts` içinde eşit tutulur. Esaslı metin değişikliğinde sürüm tarihi artırılır; gerekiyorsa mevcut müşteriden yeniden kabul alınır.
