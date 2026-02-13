export type Permission = string

export const hasPermission = (permissions: Permission[], permission: Permission) =>
  permissions.includes(permission)

export const hasAnyPermission = (permissions: Permission[], required: Permission[]) =>
  required.some((permission) => permissions.includes(permission))
