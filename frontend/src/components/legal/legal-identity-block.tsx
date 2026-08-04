import { legalIdentity } from '@/lib/legal-identity'

const optionalRows = [
  ['Vergi dairesi', legalIdentity.taxOffice],
  ['VKN / TCKN', legalIdentity.taxNumber],
  ['MERSİS numarası', legalIdentity.mersisNumber],
  ['Ticaret sicil numarası', legalIdentity.tradeRegistryNumber],
  ['KEP adresi', legalIdentity.kepAddress],
  ['Telefon', legalIdentity.phone],
] as const

export function LegalIdentityBlock() {
  return (
    <div className="space-y-4">
      {!legalIdentity.isComplete ? (
        <div className="border-l-4 border-amber-500 bg-amber-50 px-4 py-3 text-sm text-amber-950 dark:bg-amber-950/30 dark:text-amber-100">
          Yasal hizmet sağlayıcı ve veri sorumlusu bilgileri henüz kamuya açık yapılandırmada tamamlanmamıştır.
          Bu bilgiler tamamlanmadan ücretli hizmet aktivasyonu ve ödeme kabulü yapılmaz.
        </div>
      ) : null}
      <dl className="grid gap-x-6 gap-y-3 rounded-md border border-border bg-muted/20 p-5 text-sm sm:grid-cols-[180px_1fr]">
        <dt className="font-medium text-foreground">Marka</dt>
        <dd>{legalIdentity.brandName}</dd>
        <dt className="font-medium text-foreground">Hizmet sağlayıcı</dt>
        <dd>{legalIdentity.legalName || 'Yasal aktivasyon öncesi tamamlanacaktır'}</dd>
        <dt className="font-medium text-foreground">Adres</dt>
        <dd>{legalIdentity.address || 'Yasal aktivasyon öncesi tamamlanacaktır'}</dd>
        <dt className="font-medium text-foreground">İletişim</dt>
        <dd><a className="text-primary underline" href={`mailto:${legalIdentity.email}`}>{legalIdentity.email}</a></dd>
        {optionalRows.filter(([, value]) => value).map(([label, value]) => (
          <div className="contents" key={label}>
            <dt className="font-medium text-foreground">{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
