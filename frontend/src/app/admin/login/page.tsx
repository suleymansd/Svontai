import { redirect } from 'next/navigation'

export default function AdminLoginPage() {
  redirect('/login?portal=super_admin')
}
