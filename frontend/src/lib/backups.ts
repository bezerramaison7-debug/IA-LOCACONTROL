import { z } from 'zod'
import type { AuthContextValue } from '../auth/context'
import { downloadFile } from './quotes'

const configSchema = z.object({
  enabled: z.boolean(),
  time: z.string(),
  keep: z.number(),
  directory: z.string(),
})
export const backupItemSchema = z.object({
  name: z.string(),
  size: z.number(),
  created_at: z.number(),
  kind: z.enum(['backup', 'pre-restore']),
})
export const backupsSchema = z.object({
  config: configSchema,
  directory: z.string(),
  items: z.array(backupItemSchema),
})
export const createdBackupSchema = z.object({
  name: z.string(),
  size: z.number(),
  kind: z.string(),
  revision: z.string(),
})
export const verificationSchema = z.object({
  name: z.string(),
  ok: z.boolean(),
  errors: z.array(z.string()),
  revision: z.string().nullable(),
  users: z.number().nullable(),
  created_at: z.string().nullable().optional(),
  kind: z.string().nullable().optional(),
  app_version: z.string().nullable().optional(),
  files: z.number(),
})
export const restoredSchema = z.object({
  restored: z.string(),
  safety_backup: z.string(),
  revision: z.string(),
  upgraded_to: z.string().nullable(),
  replaced_files: z.string().nullable(),
  message: z.string(),
})
export type BackupConfig = z.infer<typeof configSchema>
export type BackupItem = z.infer<typeof backupItemSchema>
export type Backups = z.infer<typeof backupsSchema>
export type Verification = z.infer<typeof verificationSchema>
export type Restored = z.infer<typeof restoredSchema>

export const backupKinds: Record<string, string> = {
  backup: 'Backup',
  'pre-restore': 'Cópia de segurança antes de restauração',
  manual: 'Backup manual',
  auto: 'Backup automático',
}
/** The exact phrase the server demands before replacing the data. */
export function restorePhrase(name: string) {
  return 'RESTAURAR ' + name
}
export function fileSize(bytes: number) {
  if (bytes < 1024) return bytes + ' B'
  const units = ['KB', 'MB', 'GB']
  let value = bytes / 1024
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit++
  }
  return value.toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + ' ' + units[unit]
}
/** Absolute Windows ("C:\pasta", "\\servidor\pasta") or POSIX path; empty keeps the default. */
export function absolutePath(value: string) {
  const text = value.trim()
  return !text || /^[A-Za-z]:[\\/]/.test(text) || /^\\\\/.test(text) || text.startsWith('/')
}

type Request = AuthContextValue['request']
export async function getBackups(request: Request) {
  return backupsSchema.parse(await request('/backups'))
}
export async function saveBackupConfig(request: Request, config: BackupConfig) {
  return backupsSchema.parse(await request('/backups/config', 'PUT', config))
}
export async function createBackup(request: Request) {
  return createdBackupSchema.parse(await request('/backups', 'POST'))
}
export async function verifyBackup(request: Request, name: string) {
  return verificationSchema.parse(
    await request('/backups/' + encodeURIComponent(name) + '/verify', 'POST'),
  )
}
/** Sends the phrase as typed: the server is the one that checks it before restoring.
 * The local edition has no password: it is left out of the request. */
export async function restoreBackup(
  request: Request,
  name: string,
  confirmation: string,
  password?: string,
) {
  return restoredSchema.parse(
    await request(
      '/backups/' + encodeURIComponent(name) + '/restore',
      'POST',
      password === undefined ? { confirmation } : { confirmation, password },
    ),
  )
}
export function downloadBackup(name: string) {
  return downloadFile(
    '/backups/' + encodeURIComponent(name) + '/download',
    name,
    'Não foi possível baixar o backup.',
  )
}
