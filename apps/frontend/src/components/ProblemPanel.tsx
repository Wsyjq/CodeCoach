import { BarChart3, BookOpen, Bug, ClipboardCheck, FileQuestion, Lightbulb } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useId, useState } from 'react';
import { getServiceDefinition, serviceCatalog } from '../lib/serviceCatalog';
import type { WorkbenchServiceMode } from '../lib/types';

interface SubmitPayload {
  mode: WorkbenchServiceMode;
  problemText: string;
  code: string;
  message: string;
  userLevel: 'beginner' | 'basic' | 'advanced';
}

interface Props {
  disabled?: boolean;
  loading: boolean;
  onSubmit: (payload: SubmitPayload) => void | Promise<void>;
}

const serviceIcons: Record<WorkbenchServiceMode, LucideIcon> = {
  debug: Bug,
  knowledge: BookOpen,
  data: BarChart3,
  hint: Lightbulb,
  problem: FileQuestion,
  review: ClipboardCheck
};

const initialService = getServiceDefinition('debug');

export function ProblemPanel({ disabled = false, loading, onSubmit }: Props) {
  const fieldPrefix = useId();
  const [userLevel, setUserLevel] = useState<'beginner' | 'basic' | 'advanced'>('beginner');
  const [activeService, setActiveService] = useState<WorkbenchServiceMode>(initialService.id);
  const [problemText, setProblemText] = useState(initialService.example.problemText);
  const [code, setCode] = useState(initialService.example.code);
  const [message, setMessage] = useState(initialService.example.message);
  const [localError, setLocalError] = useState('');

  const service = getServiceDefinition(activeService);
  const showProblem = Boolean(service.problemLabel);
  const showCode = Boolean(service.codeLabel);
  const userLevelId = `${fieldPrefix}-user-level`;
  const problemId = `${fieldPrefix}-problem`;
  const codeId = `${fieldPrefix}-code`;
  const messageId = `${fieldPrefix}-message`;

  function applyService(id: WorkbenchServiceMode) {
    const nextService = getServiceDefinition(id);
    setActiveService(id);
    setProblemText(nextService.example.problemText);
    setCode(nextService.example.code);
    setMessage(nextService.example.message);
    setLocalError('');
  }

  function fillExample() {
    setProblemText(service.example.problemText);
    setCode(service.example.code);
    setMessage(service.example.message);
    setLocalError('');
  }

  function handleSubmit() {
    if (disabled) {
      setLocalError('当前处于维护模式，学习服务暂不可用。');
      return;
    }
    if (service.requiresProblem && !problemText.trim()) {
      setLocalError('这个服务需要先填写题目内容。');
      return;
    }
    if (service.requiresCode && !code.trim()) {
      setLocalError('代码纠错需要先粘贴 C 代码。');
      return;
    }
    if (!message.trim()) {
      setLocalError('请输入你的问题，或点击“填入示例”。');
      return;
    }
    onSubmit({ mode: activeService, problemText, code, message, userLevel });
  }

  function updateMessage(value: string) {
    setMessage(value);
    if (value.trim()) setLocalError('');
  }

  return (
    <section className="panel input-panel">
      <div className="panel-heading">
        <label htmlFor={userLevelId}>选择学习服务</label>
        <select id={userLevelId} value={userLevel} onChange={(event) => setUserLevel(event.target.value as 'beginner' | 'basic' | 'advanced')}>
          <option value="beginner">新手</option>
          <option value="basic">基础</option>
          <option value="advanced">进阶</option>
        </select>
      </div>

      <div className="service-grid" aria-label="学习服务">
        {serviceCatalog.map((item) => {
          const Icon = serviceIcons[item.id];
          return (
            <button
              className={`service-button ${activeService === item.id ? 'is-active' : ''}`}
              key={item.id}
              type="button"
              onClick={() => applyService(item.id)}
              disabled={loading}
            >
              <span className="service-icon"><Icon size={18} /></span>
              <strong>{item.label}</strong>
              <small>{item.description}</small>
            </button>
          );
        })}
      </div>

      <div className="service-context">
        <div>
          <span className="mini-label">当前服务</span>
          <strong>{service.label}</strong>
          <p>{service.helper}</p>
        </div>
        <button className="ghost-button compact" type="button" onClick={fillExample} disabled={loading}>
          填入示例
        </button>
      </div>

      {showProblem ? (
        <>
          <label className="field-label" htmlFor={problemId}>{service.problemLabel}</label>
          <textarea
            className="textarea problem"
            id={problemId}
            value={problemText}
            onChange={(event) => setProblemText(event.target.value)}
            placeholder={service.problemPlaceholder}
          />
        </>
      ) : null}

      {showCode ? (
        <>
          <label className="field-label" htmlFor={codeId}>{service.codeLabel}</label>
          <textarea
            className="textarea code"
            id={codeId}
            value={code}
            onChange={(event) => setCode(event.target.value)}
            placeholder={service.codePlaceholder}
            spellCheck={false}
          />
        </>
      ) : null}

      <label className="field-label" htmlFor={messageId}>{service.messageLabel}</label>
      <textarea
        className="textarea question"
        id={messageId}
        value={message}
        onChange={(event) => updateMessage(event.target.value)}
        placeholder={service.messagePlaceholder}
      />

      {localError ? <div className="form-error">{localError}</div> : null}

      <button className="primary-button" disabled={loading || disabled} onClick={handleSubmit}>
        {disabled ? '维护中，暂不可用' : loading ? '分析中...' : service.id === 'review' ? '生成复盘' : '开始分析'}
      </button>
    </section>
  );
}
