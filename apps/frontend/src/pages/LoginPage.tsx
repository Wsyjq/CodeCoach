import { LockKeyhole, UserRound } from 'lucide-react';
import { useId, useState } from 'react';
import { loginUser, registerUser } from '../lib/api';
import type { AuthSession } from '../lib/types';

export function LoginPage({ onAuthenticated }: { onAuthenticated: (session: AuthSession) => void }) {
  const fieldPrefix = useId();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const usernameId = `${fieldPrefix}-username`;
  const displayNameId = `${fieldPrefix}-display-name`;
  const passwordId = `${fieldPrefix}-password`;

  async function handleSubmit() {
    const trimmedUsername = username.trim();
    const trimmedDisplayName = displayName.trim();
    if (!trimmedUsername) {
      setError('请输入用户名。');
      return;
    }
    if (mode === 'register' && !/^[A-Za-z0-9_-]{3,32}$/.test(trimmedUsername)) {
      setError('用户名需为 3-32 位字母、数字、下划线或短横线。');
      return;
    }
    if (mode === 'login' && trimmedUsername.length > 64) {
      setError('用户名不能超过 64 位。');
      return;
    }
    if (mode === 'register' && trimmedDisplayName.length > 40) {
      setError('显示名称不能超过 40 位。');
      return;
    }
    if (password.length < 6) {
      setError('密码至少 6 位。');
      return;
    }
    if (password.length > 128) {
      setError('密码不能超过 128 位。');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const session = mode === 'login'
        ? await loginUser({ username: trimmedUsername, password })
        : await registerUser({ username: trimmedUsername, display_name: trimmedDisplayName || trimmedUsername, password });
      onAuthenticated(session);
    } catch (err) {
      setError(err instanceof Error ? mapAuthError(err.message) : '认证失败，请稍后再试。');
    } finally {
      setLoading(false);
    }
  }

  function changeMode(nextMode: 'login' | 'register') {
    setMode(nextMode);
    setError('');
  }

  return (
    <main className="app-stage auth-stage">
      <section className="auth-hero">
        <span className="eyebrow">CodeCoach Account</span>
        <h1>把每次 C 语言练习，存进自己的学习档案。</h1>
        <p>登录后，错题、复习计划和多轮会话都会按你的账号独立保存。</p>
        <div className="auth-feature-grid">
          <span>个人错题库</span>
          <span>到期复习</span>
          <span>会话记忆</span>
        </div>
      </section>

      <section className="auth-card">
        <div className="auth-switch" aria-label="登录或注册">
          <button aria-pressed={mode === 'login'} className={mode === 'login' ? 'is-active' : ''} type="button" onClick={() => changeMode('login')} disabled={loading}>登录</button>
          <button aria-pressed={mode === 'register'} className={mode === 'register' ? 'is-active' : ''} type="button" onClick={() => changeMode('register')} disabled={loading}>注册</button>
        </div>

        <div className="auth-heading">
          <span className="auth-icon"><UserRound size={22} /></span>
          <div>
            <span className="mini-label">{mode === 'login' ? '欢迎回来' : '创建账号'}</span>
            <h2>{mode === 'login' ? '登录个人学习空间' : '开始建立个人档案'}</h2>
          </div>
        </div>

        <label className="field-label" htmlFor={usernameId}>用户名</label>
        <input
          className="auth-input"
          id={usernameId}
          value={username}
          onChange={(event) => {
            setUsername(event.target.value);
            if (error) setError('');
          }}
          placeholder="例如 code_student"
          autoComplete="username"
        />

        {mode === 'register' ? (
          <>
            <label className="field-label" htmlFor={displayNameId}>显示名称</label>
            <input
              className="auth-input"
              id={displayNameId}
              value={displayName}
              onChange={(event) => {
                setDisplayName(event.target.value);
                if (error) setError('');
              }}
              placeholder="例如 小林"
              autoComplete="name"
            />
          </>
        ) : null}

        <label className="field-label" htmlFor={passwordId}>密码</label>
        <div className="auth-password-row">
          <LockKeyhole size={18} />
          <input
            id={passwordId}
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
              if (error) setError('');
            }}
            placeholder="至少 6 位"
            type="password"
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            onKeyDown={(event) => {
              if (event.key === 'Enter') handleSubmit();
            }}
          />
        </div>

        {error ? <div className="form-error" role="alert">{error}</div> : null}

        <button className="primary-button auth-submit" type="button" onClick={handleSubmit} disabled={loading}>
          {loading ? '处理中...' : mode === 'login' ? '登录 CodeCoach' : '注册并进入'}
        </button>
      </section>
    </main>
  );
}

function mapAuthError(message: string) {
  if (message === 'Invalid username or password') return '用户名或密码错误。';
  if (message === 'Username already exists') return '这个用户名已经被注册。';
  if (message.includes('String should have at least')) return '输入内容长度不符合要求。';
  if (message === 'Failed to fetch') return '无法连接服务器，请稍后再试。';
  return message;
}
