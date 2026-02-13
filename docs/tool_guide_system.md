# Tool Rehber Sistemi (Animasyonlu & İnteraktif)

## Amaç
SvontAI panelinde her tool için kullanıcıyı adım adım yönlendiren, gerçek işlem tetiklemeyen, döngüsel ve kapatılabilir bir eğitim modu sunar.

## Özellikler
- Panel içine gömülü (overlay)
- Kapatılabilir ve minimize edilebilir
- Döngüsel akış (auto-play)
- Mouse ikonlu yönlendirme
- Tool bazlı rehber metinleri
- Gerçek işlem tetiklemez (demo mode)

## Sahne Akışı (Default)
1) Tool Seçimi
   - Sol panelde tool listesi highlight
   - Tooltip: “Bu tool’u sürükleyerek workflow’unuza ekleyin”

2) Sürükle & Bırak
   - Mouse tool’u tutup akış alanına taşır
   - Bırakıldığında snap animasyonu
   - Tooltip: “Tool’u akış alanına taşıyın, otomatik hizalanır”

3) Tool Sayfası Açılışı
   - Panel içinde slide/fade geçiş
   - Tooltip: “Entegrasyon adımları panel içinde açılır”

4) Adım Adım Entegrasyon
   - Input doldurma simülasyonu
   - “Devam Et” CTA vurgusu
   - Tooltip: “Alanları doldurun ve Devam Et ile ilerleyin”

5) Döngüsel Yapı
   - “Baştan İzle” + “Rehberi Kapat”
   - Tooltip: “İsterseniz baştan izleyin veya rehberi gizleyin”

## UI Durumları
- Açık (full overlay)
- Minimize (floating widget)
- Kapalı (manuel başlatma)
- Durumlar localStorage ile saklanır (`storageKey`).

## Teknik Uygulama
- Component: `frontend/src/components/shared/tool-guide.tsx`
- CSS animasyonları: `frontend/src/app/globals.css`
- Varsayılan sahneler `defaultSteps` içinde
- Tool bazlı özelleştirme için `steps` prop kullanılabilir
- Entegrasyon: `frontend/src/app/admin/tools/page.tsx`, `frontend/src/app/dashboard/bots/page.tsx`
- Kalıcılık: `storageKey` ile rehber durumu hatırlanır

## UX Yazım Rehberi
- Kısa, net, eylem odaklı metinler
- Teknik jargon minimum
- Kullanıcıyı gerçek işlem yerine demo modda yönlendirir

## Güvenlik Notu
Rehber gerçek API çağrısı veya workflow tetiklemesi yapmaz. Sadece görsel katmandır.
