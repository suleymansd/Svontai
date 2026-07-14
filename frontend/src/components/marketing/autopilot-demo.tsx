import type { CSSProperties } from 'react'
import {
  Bot,
  BrainCircuit,
  CalendarCheck,
  Check,
  Send,
  Sparkles,
  UserPlus,
  Wifi,
} from 'lucide-react'

const activityItems = [
  { icon: Sparkles, title: 'Niyet algılandı', detail: 'Randevu talebi', step: 3 },
  { icon: UserPlus, title: 'Müşteri güncellendi', detail: 'WhatsApp kişisi', step: 5 },
  { icon: CalendarCheck, title: 'Randevu oluşturuldu', detail: 'Yarın, 14.00', step: 6 },
]

export function AutopilotDemo() {
  return (
    <div className="sv-demo overflow-hidden rounded-[8px] border border-slate-700/70 bg-slate-950 shadow-2xl shadow-slate-950/20">
      <div className="flex h-11 items-center gap-3 border-b border-white/10 bg-slate-900 px-4">
        <div className="flex gap-1.5" aria-hidden="true">
          <span className="h-2.5 w-2.5 rounded-full bg-red-500" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
        </div>
        <div className="mx-auto flex h-6 items-center gap-2 rounded-md bg-white/5 px-3 text-[10px] text-slate-400 sm:text-xs">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          app.svontai.com/autopilot
        </div>
        <div className="flex items-center gap-1.5 text-[10px] text-emerald-400 sm:text-xs">
          <Wifi className="h-3 w-3" />
          Canlı
        </div>
      </div>

      <div className="relative min-h-[390px] bg-slate-50 p-3 sm:aspect-[16/8.6] sm:min-h-0 sm:p-5 dark:bg-slate-950">
        <div className="mb-3 grid grid-cols-3 gap-2 sm:mb-4 sm:gap-3">
          {[
            ['WhatsApp', 'Bağlı'],
            ['AI Asistan', 'Çalışıyor'],
            ['Otonom Mod', 'Aktif'],
          ].map(([label, value], index) => (
            <div
              key={label}
              className="sv-demo-reveal flex min-w-0 items-center gap-2 rounded-md border border-slate-200 bg-white px-2 py-2 shadow-sm sm:px-3 dark:border-slate-800 dark:bg-slate-900"
              style={{ '--demo-step': index } as CSSProperties}
            >
              <span className="relative flex h-2 w-2 shrink-0">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-40" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
              </span>
              <div className="min-w-0">
                <p className="truncate text-[9px] text-slate-500 sm:text-[11px]">{label}</p>
                <p className="truncate text-[10px] font-semibold text-slate-900 sm:text-xs dark:text-white">{value}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="grid h-[330px] grid-cols-1 gap-3 sm:h-[calc(100%-64px)] sm:grid-cols-[1.5fr_0.8fr]">
          <section className="relative overflow-hidden rounded-md border border-slate-200 bg-white p-3 shadow-sm sm:p-4 dark:border-slate-800 dark:bg-slate-900">
            <div className="grid h-full grid-cols-[0.85fr_1.15fr] items-center gap-3 sm:gap-5">
              <div className="sv-demo-phone relative mx-auto h-[274px] w-[142px] rounded-[24px] border-[5px] border-slate-900 bg-[#efeae2] shadow-xl sm:h-[310px] sm:w-[164px]">
                <div className="absolute left-1/2 top-0 z-20 h-3 w-14 -translate-x-1/2 rounded-b-xl bg-slate-900" />
                <div className="flex h-11 items-end gap-1.5 bg-[#075e54] px-2 pb-1.5 text-white">
                  <div className="flex h-6 w-6 items-center justify-center rounded-full bg-white/15">
                    <Bot className="h-3.5 w-3.5" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-[8px] font-semibold sm:text-[9px]">SvontAI İşletme</p>
                    <p className="text-[7px] text-emerald-100">çevrimiçi</p>
                  </div>
                </div>

                <div className="sv-demo-phone-chat relative h-[calc(100%-68px)] overflow-hidden px-2 py-3">
                  <div className="sv-demo-reveal ml-auto max-w-[92%] rounded-md rounded-tr-sm bg-[#d9fdd3] px-2 py-1.5 text-[8px] leading-snug text-slate-800 shadow-sm sm:text-[9px]" style={{ '--demo-step': 1 } as CSSProperties}>
                    Yarın 14.00 için randevu alabilir miyim?
                    <span className="mt-0.5 block text-right text-[6px] text-slate-500">12:42 ✓✓</span>
                  </div>

                  <div className="sv-demo-thinking sv-demo-reveal mt-2 flex w-fit items-center gap-1 rounded-md bg-white px-2 py-1.5 shadow-sm" style={{ '--demo-step': 2 } as CSSProperties} aria-label="AI yanıt hazırlıyor">
                    <span />
                    <span />
                    <span />
                  </div>

                  <div className="sv-demo-reveal mt-2 max-w-[94%] rounded-md rounded-tl-sm bg-white px-2 py-1.5 text-[8px] leading-snug text-slate-800 shadow-sm sm:text-[9px]" style={{ '--demo-step': 4 } as CSSProperties}>
                    Tabii. Randevunuz yarın 14.00 için oluşturuldu.
                    <span className="mt-0.5 block text-right text-[6px] text-slate-400">12:42</span>
                  </div>

                  <div className="sv-demo-reveal mt-2 flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-1.5 text-[7px] font-medium text-emerald-700" style={{ '--demo-step': 6 } as CSSProperties}>
                    <CalendarCheck className="h-3 w-3" /> Takvime eklendi
                  </div>
                </div>

                <div className="absolute bottom-1.5 left-2 right-2 flex h-6 items-center rounded-full bg-white px-2 shadow-sm">
                  <span className="text-[6px] text-slate-400">Mesaj</span>
                  <Send className="ml-auto h-2.5 w-2.5 text-[#075e54]" />
                </div>
              </div>

              <div className="relative flex h-full min-w-0 flex-col justify-center">
                <div className="sv-demo-flow-track absolute -left-5 top-1/2 hidden h-px w-8 bg-blue-200 sm:block">
                  <span className="sv-demo-flow-dot" />
                </div>

                <div className="mb-3 text-center">
                  <div className="sv-demo-ai-core relative mx-auto mb-2 flex h-14 w-14 items-center justify-center rounded-full bg-blue-600 text-white shadow-lg shadow-blue-500/25 sm:h-16 sm:w-16">
                    <BrainCircuit className="h-7 w-7 sm:h-8 sm:w-8" />
                    <span className="absolute inset-[-7px] rounded-full border border-blue-400/40" />
                  </div>
                  <p className="text-[10px] font-bold text-slate-900 sm:text-xs dark:text-white">SvontAI Otonom Motor</p>
                  <p className="text-[8px] text-slate-500 sm:text-[9px]">Mesajı anlar ve işlemi tamamlar</p>
                </div>

                <div className="space-y-1.5">
                  {[
                    ['Mesaj anlaşıldı', 2],
                    ['Uygun saat kontrol edildi', 3],
                    ['Yanıt ve randevu hazırlandı', 4],
                  ].map(([label, step]) => (
                    <div key={label} className="sv-demo-reveal flex min-w-0 items-center gap-2 rounded-md border border-slate-100 bg-slate-50 px-2 py-1.5 dark:border-slate-800 dark:bg-slate-950" style={{ '--demo-step': step } as CSSProperties}>
                      <span className="sv-demo-check flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300">
                        <Check className="h-2.5 w-2.5" />
                      </span>
                      <span className="truncate text-[8px] font-medium text-slate-700 sm:text-[9px] dark:text-slate-200">{label}</span>
                    </div>
                  ))}
                </div>

                <div className="sv-demo-reveal mt-2 flex items-center justify-center gap-1 rounded-md bg-emerald-50 px-2 py-1.5 text-[8px] font-semibold text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300" style={{ '--demo-step': 7 } as CSSProperties}>
                  <Check className="h-3 w-3" /> Tam otonom tamamlandı
                </div>
              </div>
            </div>
          </section>

          <aside className="hidden rounded-md border border-slate-200 bg-white p-3 shadow-sm sm:block dark:border-slate-800 dark:bg-slate-900">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-900 dark:text-white">Otonom aksiyonlar</p>
                <p className="text-[10px] text-slate-500">Gerçek zamanlı</p>
              </div>
              <Sparkles className="h-4 w-4 text-violet-500" />
            </div>

            <div className="relative space-y-2.5">
              <div className="absolute bottom-4 left-[15px] top-4 w-px bg-slate-200 dark:bg-slate-700" />
              {activityItems.map((item) => (
                <div key={item.title} className="sv-demo-reveal relative flex items-center gap-2.5 rounded-md border border-slate-100 bg-slate-50 p-2.5 dark:border-slate-800 dark:bg-slate-950" style={{ '--demo-step': item.step } as CSSProperties}>
                  <div className="z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white text-violet-600 shadow-sm dark:bg-slate-800 dark:text-violet-400">
                    <item.icon className="h-3.5 w-3.5" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-[10px] font-semibold text-slate-800 dark:text-slate-100">{item.title}</p>
                    <p className="truncate text-[9px] text-slate-500">{item.detail}</p>
                  </div>
                  <Check className="ml-auto h-3.5 w-3.5 shrink-0 text-emerald-500" />
                </div>
              ))}
            </div>

            <div className="sv-demo-reveal mt-3 rounded-md bg-emerald-50 p-2.5 text-center dark:bg-emerald-500/10" style={{ '--demo-step': 7 } as CSSProperties}>
              <p className="text-[10px] font-semibold text-emerald-800 dark:text-emerald-300">İşlem tamamlandı</p>
              <p className="text-[9px] text-emerald-600 dark:text-emerald-400">Manuel müdahale gerekmedi</p>
            </div>
          </aside>
        </div>
      </div>
    </div>
  )
}
