const configuredLegalName = process.env.NEXT_PUBLIC_LEGAL_ENTITY_NAME?.trim() || ''
const configuredAddress = process.env.NEXT_PUBLIC_LEGAL_ENTITY_ADDRESS?.trim() || ''
const configuredTaxNumber = process.env.NEXT_PUBLIC_LEGAL_ENTITY_TAX_NUMBER?.trim() || ''

export const legalIdentity = {
  brandName: 'SvontAI',
  legalName: configuredLegalName,
  address: configuredAddress,
  taxOffice: process.env.NEXT_PUBLIC_LEGAL_ENTITY_TAX_OFFICE?.trim() || '',
  taxNumber: configuredTaxNumber,
  mersisNumber: process.env.NEXT_PUBLIC_LEGAL_ENTITY_MERSIS_NUMBER?.trim() || '',
  tradeRegistryNumber: process.env.NEXT_PUBLIC_LEGAL_ENTITY_TRADE_REGISTRY_NUMBER?.trim() || '',
  kepAddress: process.env.NEXT_PUBLIC_LEGAL_ENTITY_KEP_ADDRESS?.trim() || '',
  email: process.env.NEXT_PUBLIC_LEGAL_CONTACT_EMAIL?.trim() || 'support@svontai.com',
  phone: process.env.NEXT_PUBLIC_LEGAL_CONTACT_PHONE?.trim() || '',
  isComplete: Boolean(configuredLegalName && configuredAddress && configuredTaxNumber),
} as const
