export type User = {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
};

export type Tenant = {
  id: string;
  name: string;
};

export type MeContext = {
  user: User;
  tenant: Tenant | null;
  permissions: string[];
  entitlements: Record<string, unknown>;
  feature_flags: Record<string, unknown>;
};

export type MobileTokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
};

export type DailyStats = {
  messages_sent: number;
  messages_received: number;
  ai_responses: number;
  conversations_started: number;
  leads_captured: number;
};

export type DashboardStats = {
  today: DailyStats;
  weekly: Record<string, number>;
  monthly: Record<string, number>;
  totals: Record<string, number>;
};

export type ActionCenterItem = {
  id: string;
  kind: string;
  severity: 'info' | 'warning' | 'critical' | string;
  title: string;
  description: string;
  href: string;
  cta_label: string;
  occurred_at: string;
};

export type UpcomingAppointment = {
  id: string;
  customer_name: string;
  subject: string;
  starts_at: string;
  duration_minutes: number;
};

export type ActionCenter = {
  generated_at: string;
  window_hours: number;
  required_count: number;
  items: ActionCenterItem[];
  upcoming_appointments: UpcomingAppointment[];
};

export type Conversation = {
  id: string;
  bot_id: string;
  external_user_id: string;
  source: 'whatsapp' | 'web_widget';
  status: string;
  ai_reply_enabled: boolean;
  customer_name: string | null;
  customer_phone: string;
  last_message: string | null;
  last_message_at: string | null;
};

export type Message = {
  id: string;
  conversation_id?: string;
  sender: 'user' | 'bot' | 'system' | 'operator';
  content: string;
  created_at: string;
};

export type OperatorSendResult = {
  success: boolean;
  message_id: string;
  sent_at: string;
  delivered: boolean;
  note: string | null;
};

export type Appointment = {
  id: string;
  customer_name: string;
  customer_phone: string | null;
  subject: string;
  starts_at: string;
  duration_minutes: number;
  status: 'scheduled' | 'completed' | 'cancelled' | string;
  calendar_sync_status: string;
};
