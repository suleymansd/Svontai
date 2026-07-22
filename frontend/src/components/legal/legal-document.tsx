import { ReactNode } from 'react'
import { MarketingShell } from '@/components/marketing/marketing-shell'

type LegalSection = {
  title: string
  content: ReactNode
}

export function LegalDocument({
  title,
  updatedAt,
  introduction,
  sections,
  notice,
}: {
  title: string
  updatedAt: string
  introduction: ReactNode
  sections: LegalSection[]
  notice?: ReactNode
}) {
  return (
    <MarketingShell>
      <article className="mx-auto max-w-4xl px-4 py-14 sm:px-6 sm:py-20">
        <header className="border-b border-border pb-8">
          <p className="text-sm font-medium text-primary">Hukuki Bilgilendirme</p>
          <h1 className="mt-3 text-3xl font-bold sm:text-4xl">{title}</h1>
          <p className="mt-3 text-sm text-muted-foreground">Son güncelleme: {updatedAt}</p>
          <div className="mt-6 leading-7 text-muted-foreground">{introduction}</div>
        </header>
        {notice ? (
          <div className="my-8 border-l-4 border-amber-500 bg-amber-50 px-5 py-4 text-sm leading-6 text-amber-950 dark:bg-amber-950/30 dark:text-amber-100">
            {notice}
          </div>
        ) : null}
        <div className="divide-y divide-border">
          {sections.map((section, index) => (
            <section key={section.title} className="py-7">
              <h2 className="text-xl font-semibold">{index + 1}. {section.title}</h2>
              <div className="mt-3 space-y-3 leading-7 text-muted-foreground">{section.content}</div>
            </section>
          ))}
        </div>
      </article>
    </MarketingShell>
  )
}
