import { useState } from 'react'
import { getDefaults, DB_TYPE_LIST, getLabel } from '../data/providers'
import DbIcon from './DbIcon'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'

function parseConnectionString(str) {
  try {
    const s = str.trim().replace(/^postgres:\/\//, 'postgresql://')
    const url = new URL(s)
    const proto = url.protocol.replace(':', '')
    const dbType = proto === 'postgresql' ? 'postgresql' : proto === 'mysql' ? 'mysql' : null
    if (!dbType) return null
    return {
      db_type: dbType,
      host: url.hostname || 'localhost',
      port: url.port ? parseInt(url.port) : (dbType === 'postgresql' ? 5432 : 3306),
      database: url.pathname.replace(/^\//, ''),
      username: decodeURIComponent(url.username || ''),
      password: decodeURIComponent(url.password || ''),
    }
  } catch {
    return null
  }
}

export default function ConnectionForm({
  formData, onChange, onTest, onSave, testResult, testing, saving, isNew,
}) {
  const [showPassword, setShowPassword] = useState(false)
  const [connStr, setConnStr] = useState('')
  const [parseError, setParseError] = useState(null)

  const handleChange = (e) => {
    const { name, value } = e.target
    if (name === 'db_type') {
      const defaults = getDefaults(value) || {}
      onChange({ ...formData, ...defaults, db_type: value })
    } else {
      onChange({ ...formData, [name]: name === 'port' ? Number(value) || '' : value })
    }
  }

  const handleParseConnStr = () => {
    setParseError(null)
    const parsed = parseConnectionString(connStr)
    if (!parsed) {
      setParseError('Could not parse. Expected: postgresql://user:pass@host:5432/dbname')
      return
    }
    onChange({ ...formData, ...parsed })
    setConnStr('')
  }

  const canTest = formData.host && formData.database && formData.username
  const canSave = canTest && (isNew ? formData.database_id?.trim() : true)
  const busy = testing || saving

  const title = isNew ? 'NEW CONNECTION' : `EDIT — ${formData.nickname || formData.database_id}`

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <h2 className="text-lg font-heading mb-6">{title}</h2>

      <div className="space-y-4 max-w-lg">
        {/* Connection string shortcut */}
        <Alert className="bg-info/20">
          <AlertTitle>Paste a connection URL</AlertTitle>
          <AlertDescription>
            <div className="flex gap-2 mt-2">
              <Input
                type="text"
                value={connStr}
                onChange={e => { setConnStr(e.target.value); setParseError(null) }}
                onKeyDown={e => e.key === 'Enter' && handleParseConnStr()}
                placeholder="postgresql://user:pass@localhost:5432/mydb"
                className="flex-1 font-mono text-xs"
              />
              <Button size="sm" onClick={handleParseConnStr} disabled={!connStr.trim()}>
                FILL ↓
              </Button>
            </div>
            {parseError && <p className="text-xs text-danger font-heading mt-1.5">{parseError}</p>}
          </AlertDescription>
        </Alert>

        {/* Divider */}
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t-2 border-border" />
          </div>
          <div className="relative flex justify-center">
            <span className="bg-secondary-background px-3 text-xs font-heading text-foreground/50 uppercase">or fill in manually</span>
          </div>
        </div>

        {isNew && (
          <Field label="Connection ID" required>
            <Input name="database_id" value={formData.database_id} onChange={handleChange} placeholder="e.g. local-postgres" />
            <p className="text-xs text-foreground/50 mt-1 font-base">Unique identifier. Cannot be changed later.</p>
          </Field>
        )}

        <Field label="Display Name" hint="(optional)">
          <Input name="nickname" value={formData.nickname} onChange={handleChange} placeholder="e.g. Local Dev DB" />
        </Field>

        <Field label="Database Type" required>
          {isNew ? (
            <div className="space-y-2">
              {DB_TYPE_LIST.map(t => (
                <label
                  key={t.id}
                  className={`flex items-center gap-3 px-3 py-2.5 border-2 border-border rounded-base cursor-pointer transition-all duration-150 ${
                    formData.db_type === t.id
                      ? 'bg-main shadow-shadow'
                      : 'bg-secondary-background hover:translate-x-boxShadowX hover:translate-y-boxShadowY hover:shadow-none shadow-shadow'
                  }`}
                >
                  <input
                    type="radio"
                    name="db_type"
                    value={t.id}
                    checked={formData.db_type === t.id}
                    onChange={handleChange}
                    className="sr-only"
                  />
                  <DbIcon dbType={t.id} className="w-5 h-5" />
                  <span className="text-sm font-heading">{t.label}</span>
                </label>
              ))}
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3 py-2 bg-main/20 border-2 border-border rounded-base text-sm font-heading">
              <DbIcon dbType={formData.db_type} className="w-4 h-4" />
              {getLabel(formData.db_type)}
            </div>
          )}
        </Field>

        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2">
            <Field label="Host" required>
              <Input name="host" value={formData.host} onChange={handleChange} placeholder="localhost" />
            </Field>
          </div>
          <Field label="Port" required>
            <Input type="number" name="port" value={formData.port} onChange={handleChange} />
          </Field>
        </div>

        <Field label="Database Name" required>
          <Input name="database" value={formData.database} onChange={handleChange} placeholder="myapp" />
        </Field>

        <Field label="Username" required>
          <Input name="username" value={formData.username} onChange={handleChange} placeholder="postgres" />
        </Field>

        <Field label="Password" required={isNew}>
          <div className="relative">
            <Input
              type={showPassword ? 'text' : 'password'}
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder={isNew ? 'Enter password' : 'Leave blank to keep current'}
              className="pr-10"
            />
            <button
              type="button"
              onClick={() => setShowPassword(p => !p)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-foreground/40 hover:text-foreground"
            >
              {showPassword ? (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></svg>
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
              )}
            </button>
          </div>
        </Field>

        <Field label="SSL Mode">
          <select name="ssl_mode" value={formData.ssl_mode} onChange={handleChange}
            className="flex h-10 w-full rounded-base border-2 border-border bg-secondary-background px-3 py-2 text-sm font-base text-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2">
            <option value="disable">Disable (recommended for local)</option>
            <option value="prefer">Prefer</option>
            <option value="require">Require</option>
          </select>
        </Field>

        {testResult && (
          <Alert className={testResult.success ? 'bg-success/30' : 'bg-danger/30'}>
            {testResult.success ? (
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" /></svg>
            ) : (
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" /></svg>
            )}
            <AlertTitle>{testResult.success ? 'Connected successfully!' : 'Connection failed'}</AlertTitle>
            <AlertDescription>
              {testResult.success && testResult.info && (
                <span className="text-xs">{testResult.info.version?.split('\n')[0].split(',')[0]}{testResult.info.size ? ` · ${testResult.info.size}` : ''}</span>
              )}
              {!testResult.success && testResult.error && <span className="text-xs">{testResult.error}</span>}
            </AlertDescription>
          </Alert>
        )}

        <div className="flex gap-3 pt-2">
          <Button variant="neutral" onClick={onTest} disabled={!canTest || busy}>
            {testing && !saving ? <><Spinner />TESTING...</> : 'TEST CONNECTION'}
          </Button>
          <Button className="flex-1" onClick={onSave} disabled={!canSave || busy}>
            {saving ? <><Spinner />{testing ? 'TESTING...' : 'SAVING...'}</> : isNew ? 'SAVE CONNECTION' : 'UPDATE CONNECTION'}
          </Button>
        </div>

        {saving && testing && (
          <p className="text-xs text-foreground/50 text-center font-heading">Verifying connection before saving…</p>
        )}
      </div>
    </div>
  )
}

function Field({ label, required, hint, children }) {
  return (
    <div>
      <Label className="mb-1.5 block">
        {label}
        {required && <span className="text-danger ml-0.5">*</span>}
        {hint && <span className="text-foreground/40 ml-1 font-base">{hint}</span>}
      </Label>
      {children}
    </div>
  )
}

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
  )
}
