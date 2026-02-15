import { redirect } from 'next/navigation'

export default async function PanelToolWorkspacePage({
  params,
}: {
  params: Promise<{ toolId: string }>
}) {
  const { toolId } = await params
  redirect(`/dashboard/tools/${toolId}`)
}
