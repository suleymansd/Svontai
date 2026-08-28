import type { CSSProperties } from 'react'
import {
  Activity,
  Bot,
  BrainCircuit,
  CalendarCheck,
  Check,
  Clock3,
  Database,
  MessageCircle,
  Send,
  ShieldCheck,
  Sparkles,
  UserPlus,
  Wifi,
  Zap,
} from 'lucide-react'

const pipelineItems = [
  { icon: MessageCircle, label: 'Talep anlaşıldı', detail: 'Randevu niyeti', step: 2 },
  { icon: Clock3, label: 'Uygunluk kontrolü', detail: 'Takvim senkronize', step: 3 },
  { icon: Database, label: 'Kayıt oluşturuldu', detail: 'Yarın, 14.00', step: 5 },
]

const activityItems = [
  { icon: Sparkles, title: 'Niyet algılandı', detail: 'Randevu talebi', time: 'şimdi', step: 2 },
  { icon: UserPlus, title: 'Müşteri güncellendi', detail: 'WhatsApp profili', time: '1 sn', step: 4 },
  { icon: CalendarCheck, title: 'Randevu oluşturuldu', detail: 'Yarın, 14.00', time: '2 sn', step: 6 },
]

const demoStyle = (step: number) => ({ '--demo-step': step } as CSSProperties)

export function AutopilotDemo() {
  return (
    <div
      className="sv-demo overflow-hidden rounded-[8px] border border-slate-700/80 bg-[#080d19] shadow-[0_32px_80px_-28px_rgba(15,23,42,0.55)]"
      data-testid="premium-autopilot-demo"
    >
      <div className="grid h-11 grid-cols-[1fr_auto_1fr] items-center border-b border-white/10 bg-[#0c1324] px-4">
        <div className="flex gap-1.5" aria-hidden="true">
          <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
        </div>
        <div className="flex h-6 items-center gap-2 rounded-md border border-white/[0.06] bg-white/[0.05] px-3 text-[10px] text-slate-400 sm:text-xs">
          <ShieldCheck className="h-3 w-3 text-emerald-400" />
          app.svontai.com/otonom
        </div>
        <div className="ml-auto flex items-center gap-1.5 text-[10px] font-medium text-emerald-400 sm:text-xs">
          <Wifi className="h-3 w-3" /> Canlı
        </div>
      </div>

      <div className="sv-demo-canvas relative min-h-[510px] overflow-hidden bg-[#f4f7fb] p-3 sm:aspect-[16/8.35] sm:min-h-0 sm:p-5">
        <div className="relative z-10 mb-3 flex items-center justify-between sm:mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="sv-demo-live-dot h-2 w-2 rounded-full bg-emerald-500" />
              <p className="text-[10px] font-semibold tracking-[0.08em] text-slate-500 sm:text-xs">OTONOM OPERASYON</p>
            </div>
            <p className="mt-1 text-xs font-semibold text-slate-950 sm:text-sm">Müşteri talebi uçtan uca işleniyor</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="hidden items-center gap-1.5 border-r border-slate-200 pr-3 text-[9px] text-slate-500 sm:flex">
              <Zap className="h-3 w-3 text-amber-500" /> 2.4 sn işlem süresi
            </div>
            <div className="flex items-center gap-1.5 rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-[9px] font-semibold text-emerald-700 sm:text-[10px]">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Otonom mod aktif
            </div>
          </div>
        </div>

        <div className="relative z-10 grid h-[425px] grid-cols-[0.9fr_1.1fr] gap-2.5 sm:h-[calc(100%-56px)] sm:grid-cols-[0.82fr_1.18fr_0.86fr] sm:gap-3">
          <section className="relative overflow-hidden rounded-[8px] border border-slate-200/90 bg-white shadow-[0_12px_30px_-24px_rgba(15,23,42,0.45)]">
            <div className="flex h-10 items-center justify-between border-b border-slate-100 px-3">
              <div className="flex items-center gap-2">
                <MessageCircle className="h-3.5 w-3.5 text-emerald-600" />
                <span className="text-[9px] font-semibold text-slate-800 sm:text-[10px]">WhatsApp</span>
              </div>
              <span className="text-[8px] text-slate-400">canlı görüşme</span>
            </div>

            <div className="flex h-[calc(100%-40px)] items-center justify-center bg-[linear-gradient(180deg,#f8fafc_0%,#eef3f7_100%)] p-2 sm:p-3">
              <div className="sv-demo-phone relative h-[345px] w-[158px] overflow-hidden rounded-[27px] border-[5px] border-[#111827] bg-[#efeae2] shadow-[0_20px_35px_-18px_rgba(15,23,42,0.65)] sm:h-[360px] sm:w-[168px]">
                <div className="absolute left-1/2 top-0 z-30 h-3.5 w-16 -translate-x-1/2 rounded-b-xl bg-[#111827]" />
                <div className="flex h-12 items-end gap-1.5 bg-[#075e54] px-2 pb-1.5 text-white">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-white/15 ring-1 ring-white/15"><Bot className="h-4 w-4" /></div>
                  <div className="min-w-0">
                    <p className="truncate text-[8px] font-semibold sm:text-[9px]">SvontAI İşletme</p>
                    <p className="flex items-center gap-1 text-[6px] text-emerald-100 sm:text-[7px]"><span className="h-1 w-1 rounded-full bg-emerald-300" /> çevrimiçi</p>
                  </div>
                </div>

                <div className="sv-demo-phone-chat relative h-[calc(100%-72px)] overflow-hidden px-2 py-3">
                  <div className="sv-demo-message ml-auto max-w-[92%] rounded-md rounded-tr-sm bg-[#d9fdd3] px-2 py-1.5 text-[8px] leading-snug text-slate-800 shadow-sm sm:text-[9px]" style={demoStyle(1)}>
                    Yarın saat 14.00 için uygun musunuz?
                    <span className="mt-0.5 block text-right text-[6px] text-slate-500">12:42 ✓✓</span>
                  </div>
                  <div className="sv-demo-thinking sv-demo-message mt-2 flex w-fit items-center gap-1 rounded-md rounded-tl-sm bg-white px-2 py-2 shadow-sm" style={demoStyle(2)} aria-label="AI yanıt hazırlıyor"><span /><span /><span /></div>
                  <div className="sv-demo-message mt-2 max-w-[96%] rounded-md rounded-tl-sm bg-white px-2 py-1.5 text-[8px] leading-snug text-slate-800 shadow-sm sm:text-[9px]" style={demoStyle(4)}>
                    Evet, 14.00 uygun. Randevunuzu oluşturmamı ister misiniz?
                    <span className="mt-0.5 block text-right text-[6px] text-slate-400">12:42</span>
                  </div>
                  <div className="sv-demo-message ml-auto mt-2 w-fit rounded-md rounded-tr-sm bg-[#d9fdd3] px-2 py-1.5 text-[8px] text-slate-800 shadow-sm" style={demoStyle(5)}>
                    Evet, onaylıyorum
                    <span className="mt-0.5 block text-right text-[6px] text-slate-500">12:43 ✓✓</span>
                  </div>
                  <div className="sv-demo-message mt-2 flex items-center gap-1.5 rounded-md border border-emerald-100 bg-emerald-50 px-2 py-2 text-[7px] font-semibold text-emerald-700" style={demoStyle(6)}>
                    <CalendarCheck className="h-3 w-3" /> Randevu takvime eklendi
                  </div>
                </div>
                <div className="absolute bottom-1.5 left-2 right-2 flex h-6 items-center rounded-full bg-white px-2 shadow-sm">
                  <span className="text-[6px] text-slate-400">Mesaj</span><Send className="ml-auto h-2.5 w-2.5 text-[#075e54]" />
                </div>
              </div>
            </div>
          </section>

          <section className="relative overflow-hidden rounded-[8px] border border-slate-200/90 bg-white p-3 shadow-[0_12px_30px_-24px_rgba(15,23,42,0.45)] sm:p-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <p className="text-[9px] font-semibold text-slate-900 sm:text-[11px]">Canlı karar akışı</p>
                <p className="text-[8px] text-slate-400 sm:text-[9px]">İşletme verisi ve takvim birlikte çalışıyor</p>
              </div>
              <div className="sv-demo-processing flex items-center gap-1 rounded-md bg-violet-50 px-2 py-1 text-[8px] font-semibold text-violet-700 sm:text-[9px]"><Activity className="h-3 w-3" /> işleniyor</div>
            </div>

            <div className="relative flex h-[calc(100%-46px)] flex-col justify-center py-2">
              <div className="sv-demo-scan-line" aria-hidden="true" />
              <div className="relative mx-auto mb-3 flex h-20 w-20 items-center justify-center sm:h-24 sm:w-24">
                <span className="sv-demo-orbit absolute inset-0 rounded-full border border-dashed border-blue-300/80" />
                <span className="absolute inset-2 rounded-full border border-violet-200 bg-white shadow-[0_12px_30px_-16px_rgba(79,70,229,0.55)]" />
                <span className="sv-demo-core-glow absolute inset-4 rounded-full bg-[#16213e]" />
                <BrainCircuit className="relative z-10 h-7 w-7 text-white sm:h-8 sm:w-8" />
                <span className="sv-demo-orbit-dot absolute left-1/2 top-0 h-2 w-2 -translate-x-1/2 rounded-full bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.9)]" />
              </div>
              <div className="mb-3 text-center">
                <p className="text-[10px] font-bold text-slate-950 sm:text-xs">SvontAI Otonom Motor</p>
                <p className="text-[8px] text-slate-500 sm:text-[9px]">Talebi anlar, doğrular ve tamamlar</p>
              </div>
              <div className="relative space-y-1.5">
                <div className="absolute bottom-3 left-[13px] top-3 w-px bg-slate-200" aria-hidden="true" />
                {pipelineItems.map((item) => (
                  <div key={item.label} className="sv-demo-stage relative flex min-w-0 items-center gap-2 rounded-md border border-slate-100 bg-slate-50/80 px-2 py-1.5 sm:px-2.5 sm:py-2" style={demoStyle(item.step)}>
                    <span className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-white bg-white text-blue-600 shadow-sm"><item.icon className="h-3 w-3" /></span>
                    <span className="min-w-0">
                      <span className="block truncate text-[8px] font-semibold text-slate-800 sm:text-[9px]">{item.label}</span>
                      <span className="block truncate text-[7px] text-slate-400 sm:text-[8px]">{item.detail}</span>
                    </span>
                    <Check className="ml-auto h-3 w-3 shrink-0 text-emerald-500" />
                  </div>
                ))}
              </div>
              <div className="sv-demo-stage mt-2 flex items-center justify-center gap-1.5 rounded-md border border-emerald-100 bg-emerald-50 px-2 py-2 text-[8px] font-semibold text-emerald-700 sm:text-[9px]" style={demoStyle(7)}>
                <ShieldCheck className="h-3 w-3" /> Güvenli otonomi tamamlandı
              </div>
            </div>
          </section>

          <aside className="hidden overflow-hidden rounded-[8px] border border-slate-200/90 bg-white shadow-[0_12px_30px_-24px_rgba(15,23,42,0.45)] sm:block">
            <div className="border-b border-slate-100 px-3 py-3">
              <div className="flex items-center justify-between">
                <div><p className="text-[11px] font-semibold text-slate-900">Operasyon merkezi</p><p className="text-[9px] text-slate-400">Gerçek zamanlı hareketler</p></div>
                <Sparkles className="h-4 w-4 text-violet-500" />
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <div className="border-r border-slate-100"><p className="text-base font-bold text-slate-950">2.4<span className="text-[9px] font-medium text-slate-400"> sn</span></p><p className="text-[8px] text-slate-400">Yanıt süresi</p></div>
                <div className="pl-1"><p className="text-base font-bold text-emerald-600">%100</p><p className="text-[8px] text-slate-400">Tamamlanma</p></div>
              </div>
            </div>
            <div className="relative space-y-2 px-3 py-3">
              <div className="absolute bottom-6 left-[26px] top-6 w-px bg-slate-200" />
              {activityItems.map((item) => (
                <div key={item.title} className="sv-demo-stage relative flex items-center gap-2.5 py-1.5" style={demoStyle(item.step)}>
                  <div className="relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-slate-100 bg-white text-violet-600 shadow-sm"><item.icon className="h-3.5 w-3.5" /></div>
                  <div className="min-w-0"><p className="truncate text-[9px] font-semibold text-slate-800">{item.title}</p><p className="truncate text-[8px] text-slate-400">{item.detail}</p></div>
                  <span className="ml-auto text-[7px] text-slate-400">{item.time}</span>
                </div>
              ))}
            </div>
            <div className="mx-3 border-t border-slate-100 py-3">
              <div className="sv-demo-stage flex items-center gap-2 rounded-md border border-emerald-100 bg-emerald-50 p-2.5" style={demoStyle(7)}>
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-600 text-white shadow-sm"><Check className="h-4 w-4" /></div>
                <div><p className="text-[9px] font-semibold text-emerald-800">İşlem tamamlandı</p><p className="text-[8px] text-emerald-600">Manuel müdahale gerekmedi</p></div>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  )
}
