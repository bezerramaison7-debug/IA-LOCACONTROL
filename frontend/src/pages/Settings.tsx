import { Monitor, Sun, Moon, Check, Palette, RotateCcw, Keyboard } from 'lucide-react'
import { useTheme, type ThemePreference } from '../theme/context'
import { Badge, Card, PageHeader, type Status } from '../components/ui'
import { Button } from '../components/Button'
import { ConfirmDialog } from '../components/Modal'
import { useToast } from '../components/toast-context'
import { HealthPanel } from '../components/HealthPanel'
import { useAuth } from '../auth/context'
import { ContractSettings } from './contracts-settings'

export function Settings() {
  const { preference, setPreference, resolved } = useTheme()
  const notify = useToast()
  const { user } = useAuth()
  return (
    <>
      <PageHeader
        title="Configurações"
        eyebrow="DO SEU JEITO"
        description="Um ambiente confortável para acompanhar a sua rotina."
      />
      <Card
        title="Aparência"
        description="Escolha como você prefere ver o LocaControl."
        action={<Palette size={20} aria-hidden="true" />}
      >
        <div className="settings-body">
          <fieldset className="theme-options">
            <legend className="sr-only">Escolher tema</legend>
            {(
              [
                { value: 'light', label: 'Claro', description: 'Leve e familiar', icon: Sun },
                {
                  value: 'dark',
                  label: 'Escuro',
                  description: 'Conforto em pouca luz',
                  icon: Moon,
                },
                {
                  value: 'system',
                  label: 'Sistema',
                  description: 'Acompanha o dispositivo',
                  icon: Monitor,
                },
              ] as const
            ).map((option) => (
              <label
                className={`theme-option ${preference === option.value ? 'selected' : ''}`}
                key={option.value}
              >
                <input
                  type="radio"
                  name="appearance"
                  value={option.value}
                  checked={preference === option.value}
                  onChange={() => setPreference(option.value as ThemePreference)}
                />
                <span className={`theme-preview preview-${option.value}`} aria-hidden="true">
                  <span />
                  <span>
                    <i />
                    <i />
                    <i />
                  </span>
                </span>
                <span className="theme-option-label">
                  <option.icon size={18} aria-hidden="true" />
                  <strong>{option.label}</strong>
                  {preference === option.value && <Check size={16} aria-hidden="true" />}
                </span>
                <span className="theme-option-description">{option.description}</span>
              </label>
            ))}
          </fieldset>
          <p className="setting-hint">
            Preferência salva neste navegador. Tema atual:{' '}
            {resolved === 'dark' ? 'escuro' : 'claro'}.
          </p>
          <div className="setting-row">
            <div>
              <h3>Restaurar a aparência padrão</h3>
              <p>Volta a acompanhar o tema do sistema operacional.</p>
            </div>
            <ConfirmDialog
              title="Restaurar aparência?"
              description="A preferência de tema deste navegador voltará para Sistema. Nenhum dado comercial será alterado."
              confirmLabel="Restaurar aparência"
              onConfirm={() => {
                setPreference('system')
                notify('A aparência voltou a seguir o sistema.')
              }}
              trigger={
                <Button variant="secondary">
                  <RotateCcw size={16} aria-hidden="true" />
                  Restaurar padrão
                </Button>
              }
            />
          </div>
        </div>
      </Card>
      <div className="settings-grid">
        <Card title="Linguagem visual" description="Status combinam texto, ícone e cor.">
          <div className="settings-body">
            <div className="badge-gallery">
              {(['Ativo', 'Vencendo', 'Vencido', 'Encerrado', 'Cancelado'] as Status[]).map(
                (status) => (
                  <Badge status={status} key={status} />
                ),
              )}
            </div>
            <p className="setting-hint">
              A informação continua clara mesmo sem distinguir as cores.
            </p>
            <div className="accessibility-note">
              <Keyboard size={21} aria-hidden="true" />
              <p>Use Tab para navegar, Enter para confirmar e Esc para fechar janelas.</p>
            </div>
          </div>
        </Card>
      </div>
      {user?.permissions.includes('contracts.configure') && <ContractSettings />}
      <HealthPanel />
    </>
  )
}
