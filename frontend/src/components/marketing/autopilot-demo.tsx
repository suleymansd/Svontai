import type { CSSProperties } from 'react'
import {
  Bot,
  CalendarCheck,
  Check,
  MessageCircle,
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

        <div className="grid h-[305px] grid-cols-1 gap-3 sm:h-[calc(100%-64px)] sm:grid-cols-[1.5fr_0.8fr]">
          <section className="relative overflow-hidden rounded-md border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <header className="flex h-12 items-center justify-between border-b border-slate-100 px-3 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400">
                  <MessageCircle className="h-3.5 w-3.5" />
                </div>
                <div>
                  <p className="text-[11px] font-semibold text-slate-900 sm:text-xs dark:text-white">WhatsApp görüşmesi</p>
                  <p className="text-[9px] text-emerald-600 sm:text-[10px]">AI asistan yanıtlıyor</p>
                </div>
              </div>
              <span className="rounded-full bg-slate-100 px-2 py-1 text-[9px] text-slate-500 dark:bg-slate-800">Canlı akış</span>
            </header>

            <div className="space-y-3 p-3 sm:p-4">
              <div className="sv-demo-message sv-demo-reveal ml-auto max-w-[82%] rounded-md rounded-br-sm bg-emerald-100 px-3 py-2 text-[10px] leading-relaxed text-emerald-950 sm:text-xs" style={{ '--demo-step': 1 } as CSSProperties}>
                Yarın saat 14.00 için randevu alabilir miyim?
                <span className="mt-1 block text-right text-[8px] text-emerald-700">12:42 ✓✓</span>
              </div>

              <div className="sv-demo-thinking sv-demo-reveal flex w-fit items-center gap-1 rounded-md bg-slate-100 px-3 py-2 dark:bg-slate-800" style={{ '--demo-step': 2 } as CSSProperties} aria-label="AI yanıt hazırlıyor">
                <span />
                <span />
                <span />
              </div>

              <div className="sv-demo-reveal max-w-[86%] rounded-md rounded-bl-sm bg-blue-600 px-3 py-2 text-[10px] leading-relaxed text-white shadow-md shadow-blue-600/10 sm:text-xs" style={{ '--demo-step': 4 } as CSSProperties}>
                Elbette. Yarın 14.00 için randevunuzu oluşturdum. Görüşmek üzere.
                <span className="mt-1 flex items-center justify-end gap-1 text-[8px] text-blue-100">
                  <Bot className="h-2.5 w-2.5" /> SvontAI · 12:42
                </span>
              </div>
            </div>

            <div className="absolute bottom-3 left-3 right-3 flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-800 dark:bg-slate-950">
              <Bot className="h-3.5 w-3.5 text-blue-600" />
              <span className="text-[9px] text-slate-500 sm:text-[10px]">SvontAI konuşmayı ve aksiyonları yönetiyor</span>
              <span className="ml-auto h-1.5 w-1.5 rounded-full bg-emerald-500" />
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
